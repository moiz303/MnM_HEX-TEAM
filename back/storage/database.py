"""
Безопасное хранение сообщений и ключей в SQLite
"""
import sqlite3
import threading
import time
import json
from typing import List, Tuple, Optional


class SecureDatabase:
    """
    Хранилище сообщений с поддержкой оффлайн-очереди
    """

    def __init__(self, db_path: str = 'secure_chat.db'):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Инициализация таблиц"""
        with self.lock:
            # Сообщения
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    msg_id TEXT UNIQUE,
                    chat_id TEXT,
                    sender TEXT,
                    content_encrypted BLOB,
                    timestamp REAL,
                    delivered BOOLEAN DEFAULT 0,
                    read BOOLEAN DEFAULT 0,
                    direction TEXT
                )
            ''')

            # Индекс для быстрого поиска по чату
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_chat_time 
                ON messages(chat_id, timestamp)
            ''')

            # Сессии
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    chat_id TEXT PRIMARY KEY,
                    peer_id TEXT,
                    created REAL,
                    last_used REAL,
                    metadata TEXT
                )
            ''')

            # Оффлайн-очередь
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS offline_queue (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id TEXT,
                    message_data BLOB,
                    attempts INTEGER DEFAULT 0,
                    last_attempt REAL,
                    created REAL
                )
            ''')

            # Индекс для очереди
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_offline_pending 
                ON offline_queue(attempts, created)
            ''')

            # Mesh-сеть: таблица ретрансляторов
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS mesh_relays (
                    node_id TEXT PRIMARY KEY,
                    ip TEXT,
                    port INTEGER,
                    capacity INTEGER,
                    current_load INTEGER DEFAULT 0,
                    reputation REAL DEFAULT 1.0,
                    last_seen REAL,
                    is_active BOOLEAN DEFAULT 1,
                    created REAL
                )
            ''')

            # Mesh-сеть: таблица очередей сообщений
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS mesh_queues (
                    queue_id TEXT PRIMARY KEY,
                    target_id TEXT,
                    message_id TEXT,
                    original_sender TEXT,
                    encrypted_payload TEXT,
                    path TEXT,
                    ttl INTEGER,
                    priority INTEGER DEFAULT 1,
                    created REAL,
                    expires_at REAL,
                    delivered BOOLEAN DEFAULT 0
                )
            ''')

            # Индексы для mesh-таблиц
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_mesh_queues_target 
                ON mesh_queues(target_id, expires_at)
            ''')
            
            self.cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_mesh_relays_active 
                ON mesh_relays(is_active, last_seen)
            ''')

            self.conn.commit()

    def add_message(self, msg_id: str, chat_id: str, sender: str,
                    encrypted: bytes, direction: str) -> None:
        """Сохранить сообщение"""
        with self.lock:
            self.cursor.execute('''
                INSERT INTO messages 
                (msg_id, chat_id, sender, content_encrypted, timestamp, direction)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (msg_id, chat_id, sender, encrypted, time.time(), direction))
            self.conn.commit()

    def mark_delivered(self, msg_id: str) -> None:
        """Отметить сообщение как доставленное"""
        with self.lock:
            self.cursor.execute('''
                UPDATE messages SET delivered=1 WHERE msg_id=?
            ''', (msg_id,))
            self.conn.commit()

    def get_conversation(self, chat_id: str, limit: int = 50) -> List[Tuple]:
        """Получить историю переписки"""
        with self.lock:
            self.cursor.execute('''
                SELECT sender, content_encrypted, timestamp, delivered
                FROM messages 
                WHERE chat_id=?
                ORDER BY timestamp DESC LIMIT ?
            ''', (chat_id, limit))
            return self.cursor.fetchall()

    def get_incoming_messages(self, chat_id: str, limit: int = 50) -> List[Tuple]:
        """Получить только входящие сообщения (исключая исходящие)"""
        with self.lock:
            self.cursor.execute('''
                SELECT sender, content_encrypted, timestamp, delivered
                FROM messages 
                WHERE chat_id=? AND direction='in'
                ORDER BY timestamp DESC LIMIT ?
            ''', (chat_id, limit))
            return self.cursor.fetchall()

    def add_offline(self, chat_id: str, message_data: bytes) -> int:
        """Добавить сообщение в оффлайн-очередь"""
        with self.lock:
            self.cursor.execute('''
                INSERT INTO offline_queue (chat_id, message_data, created)
                VALUES (?, ?, ?)
            ''', (chat_id, message_data, time.time()))
            self.conn.commit()
            return self.cursor.lastrowid

    def get_pending_offline(self, max_attempts: int = 5) -> List[Tuple]:
        """Получить сообщения, ожидающие отправки"""
        with self.lock:
            self.cursor.execute('''
                SELECT * FROM offline_queue 
                WHERE attempts < ?
                ORDER BY created
            ''', (max_attempts,))
            return self.cursor.fetchall()

    def update_offline_attempt(self, queue_id: int) -> None:
        """Обновить счётчик попыток"""
        with self.lock:
            self.cursor.execute('''
                UPDATE offline_queue 
                SET attempts=attempts+1, last_attempt=?
                WHERE id=?
            ''', (time.time(), queue_id))
            self.conn.commit()

    def remove_offline(self, queue_id: int) -> None:
        """Удалить доставленное сообщение из очереди"""
        with self.lock:
            self.cursor.execute('DELETE FROM offline_queue WHERE id=?', (queue_id,))
            self.conn.commit()

    def save_session(self, chat_id: str, peer_id: str, metadata: dict) -> None:
        """Сохранить информацию о сессии"""
        with self.lock:
            self.cursor.execute('''
                INSERT OR REPLACE INTO sessions 
                (chat_id, peer_id, created, last_used, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, peer_id, time.time(), time.time(), json.dumps(metadata)))
            self.conn.commit()

    # ==================== MESH-СЕТЬ МЕТОДЫ ====================

    def add_mesh_relay(self, node_id: str, ip: str, port: int, capacity: int = 100) -> None:
        """Добавить или обновить информацию о ретрансляторе"""
        with self.lock:
            self.cursor.execute('''
                INSERT OR REPLACE INTO mesh_relays 
                (node_id, ip, port, capacity, last_seen, created)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (node_id, ip, port, capacity, time.time(), time.time()))
            self.conn.commit()

    def update_mesh_relay_status(self, node_id: str, current_load: int = None, 
                               reputation: float = None, is_active: bool = None) -> None:
        """Обновить статус ретранслятора"""
        with self.lock:
            updates = ["last_seen=?"]
            params = [time.time()]
            
            if current_load is not None:
                updates.append("current_load=?")
                params.append(current_load)
            
            if reputation is not None:
                updates.append("reputation=?")
                params.append(reputation)
            
            if is_active is not None:
                updates.append("is_active=?")
                params.append(is_active)
            
            params.append(node_id)
            
            self.cursor.execute(f'''
                UPDATE mesh_relays 
                SET {", ".join(updates)}
                WHERE node_id=?
            ''', params)
            self.conn.commit()

    def get_active_relays(self, min_reputation: float = 0.3) -> List[Tuple]:
        """Получить список активных ретрансляторов"""
        with self.lock:
            self.cursor.execute('''
                SELECT node_id, ip, port, capacity, current_load, reputation, last_seen
                FROM mesh_relays 
                WHERE is_active=1 AND reputation>=? AND last_seen>?
                ORDER BY reputation DESC, last_seen DESC
            ''', (min_reputation, time.time() - 300))  # 5 минут
            return self.cursor.fetchall()

    def add_mesh_message(self, queue_id: str, target_id: str, message_id: str, 
                        original_sender: str, encrypted_payload: str, path: str = None,
                        ttl: int = 3600, priority: int = 1) -> None:
        """Добавить сообщение в mesh-очередь"""
        with self.lock:
            expires_at = time.time() + ttl
            self.cursor.execute('''
                INSERT OR REPLACE INTO mesh_queues 
                (queue_id, target_id, message_id, original_sender, encrypted_payload, 
                 path, ttl, priority, created, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (queue_id, target_id, message_id, original_sender, encrypted_payload,
                  path or "[]", ttl, priority, time.time(), expires_at))
            self.conn.commit()

    def get_mesh_messages_for_target(self, target_id: str, limit: int = 50) -> List[Tuple]:
        """Получить сообщения для конкретного получателя"""
        with self.lock:
            self.cursor.execute('''
                SELECT queue_id, message_id, original_sender, encrypted_payload, path, priority, created
                FROM mesh_queues 
                WHERE target_id=? AND delivered=0 AND expires_at>?
                ORDER BY priority DESC, created ASC
                LIMIT ?
            ''', (target_id, time.time(), limit))
            return self.cursor.fetchall()

    def mark_mesh_message_delivered(self, queue_id: str) -> None:
        """Отметить mesh-сообщение как доставленное"""
        with self.lock:
            self.cursor.execute('''
                UPDATE mesh_queues 
                SET delivered=1 
                WHERE queue_id=?
            ''', (queue_id,))
            self.conn.commit()

    def cleanup_expired_mesh_messages(self) -> int:
        """Удалить истекшие mesh-сообщения"""
        with self.lock:
            self.cursor.execute('''
                DELETE FROM mesh_queues 
                WHERE expires_at<=?
            ''', (time.time(),))
            deleted = self.cursor.rowcount
            self.conn.commit()
            return deleted

    def get_mesh_queue_stats(self) -> dict:
        """Получить статистику mesh-очередей"""
        with self.lock:
            # Общее количество сообщений в очередях
            self.cursor.execute('''
                SELECT COUNT(*) FROM mesh_queues WHERE delivered=0 AND expires_at>?
            ''', (time.time(),))
            total_queued = self.cursor.fetchone()[0]
            
            # Сообщения по получателям
            self.cursor.execute('''
                SELECT target_id, COUNT(*) as count
                FROM mesh_queues 
                WHERE delivered=0 AND expires_at>?
                GROUP BY target_id
                ORDER BY count DESC
            ''', (time.time(),))
            by_target = dict(self.cursor.fetchall())
            
            # Самые старые сообщения
            self.cursor.execute('''
                SELECT target_id, MIN(created) as oldest
                FROM mesh_queues 
                WHERE delivered=0 AND expires_at>?
                GROUP BY target_id
            ''', (time.time(),))
            oldest = dict(self.cursor.fetchall())
            
            return {
                'total_queued': total_queued,
                'by_target': by_target,
                'oldest_messages': oldest
            }

    def sync_mesh_queues_with_relays(self) -> List[Tuple]:
        """Получить данные для синхронизации с другими ретрансляторами"""
        with self.lock:
            self.cursor.execute('''
                SELECT target_id, COUNT(*) as message_count, MIN(created) as oldest_message
                FROM mesh_queues 
                WHERE delivered=0 AND expires_at>?
                GROUP BY target_id
            ''', (time.time(),))
            return self.cursor.fetchall()