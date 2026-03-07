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
                INSERT OR REPLACE INTO sessions (chat_id, peer_id, created, last_used, metadata)
                VALUES (?, ?, ?, ?, ?)
            ''', (chat_id, peer_id, time.time(), time.time(), json.dumps(metadata)))
            self.conn.commit()

    def get_session(self, chat_id: str) -> Optional[dict]:
        """Получить информацию о сессии"""
        with self.lock:
            self.cursor.execute('''
                SELECT * FROM sessions WHERE chat_id=?
            ''', (chat_id,))
            row = self.cursor.fetchone()
            if row:
                return {
                    'chat_id': row[0],
                    'peer_id': row[1],
                    'created': row[2],
                    'last_used': row[3],
                    'metadata': json.loads(row[4])
                }
            return None