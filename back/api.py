"""
Локальный API для общения с Android-фронтендом на том же устройстве.
Используем Unix Domain Socket (быстрее и безопаснее TCP)
"""
import os
import socket
import threading
import json
import time
from typing import Any, Optional

# Путь к сокету (в Android-песочнице)
#SOCKET_PATH = "/data/data/com.your.app/cache/chat.sock"


# Или для отладки на ПК:
SOCKET_PATH = "/tmp/secure_chat.sock"

class LocalAPI:
    """
    Локальный API для общения с Android-фронтендом.
    Работает через Unix Domain Socket на том же устройстве.
    """

    def __init__(self, backend):
        """
        Args:
            backend: ссылка на основной объект бэкенда (SecureMessenger)
        """
        self.backend = backend
        self.running = False
        self.server_socket = None
        self.client_socket = None  # Один клиент (наше приложение)

        # Очередь для отправки уведомлений
        self.notification_queue = []
        self.notification_lock = threading.Lock()

        # Словарь методов API
        self.methods = {
            # Пиры
            'get_peers': self._handle_get_peers,
            'get_peer_info': self._handle_get_peer_info,

            # Чаты
            'start_chat': self._handle_start_chat,
            'send_message': self._handle_send_message,
            'get_messages': self._handle_get_messages,
            'mark_read': self._handle_mark_read,

            # Своя информация
            'get_my_info': self._handle_get_my_info,
        }

        # ID запросов и их обработчики
        self.pending = {}

    def start(self):
        """Запуск локального сервера"""
        self.running = True

        # Удаляем старый сокет, если есть
        try:
            os.unlink(SOCKET_PATH)
        except OSError:
            pass

        # Создаём Unix Domain Socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(SOCKET_PATH)
        self.server_socket.listen(1)

        # Даём права на чтение/запись (для Android)
        os.chmod(SOCKET_PATH, 0o666)

        # Запускаем потоки
        threading.Thread(target=self._accept_loop, daemon=True).start()
        threading.Thread(target=self._notification_loop, daemon=True).start()

        print(f"[API] Local server started at {SOCKET_PATH}")

    def _accept_loop(self):
        """Принимаем подключение от Android-фронтенда"""
        while self.running:
            try:
                client, addr = self.server_socket.accept()
                # Закрываем старый клиент, если был
                if self.client_socket:
                    try:
                        self.client_socket.close()
                    except:
                        pass

                self.client_socket = client
                print("[API] Frontend connected")

                # Отправляем приветствие
                self._send_notification({
                    'event': 'connected',
                    'data': {'status': 'ready'}
                })

                # Обрабатываем запросы
                self._handle_client(client)

            except Exception as e:
                if self.running:
                    print(f"[API] Accept error: {e}")
                    time.sleep(1)

    def _handle_client(self, client_socket):
        """Обработка запросов от клиента"""
        buffer = ""
        while self.running:
            try:
                data = client_socket.recv(4096).decode()
                if not data:
                    break

                buffer += data

                # Разделяем по \n (каждое сообщение на отдельной строке)
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._process_request(line.strip())

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[API] Client error: {e}")
                break

        # Клиент отключился
        self.client_socket = None
        print("[API] Frontend disconnected")

    def _process_request(self, line: str):
        """Обработка одного JSON-RPC запроса"""
        try:
            request = json.loads(line)
            request_id = request.get('id')
            method = request.get('method')
            params = request.get('params', {})

            if not method:
                self._send_error(request_id, -32600, "Method not specified")
                return

            # Ищем обработчик
            handler = self.methods.get(method)
            if not handler:
                self._send_error(request_id, -32601, f"Method '{method}' not found")
                return

            # Выполняем в отдельном потоке, чтобы не блокировать
            threading.Thread(
                target=self._execute_handler,
                args=(request_id, handler, params),
                daemon=True
            ).start()

        except json.JSONDecodeError:
            self._send_error(None, -32700, "Parse error")
        except Exception as e:
            self._send_error(None, -32603, f"Internal error: {e}")

    def _execute_handler(self, request_id: int, handler, params: dict):
        """Выполнить обработчик и отправить результат"""
        try:
            result = handler(params)
            self._send_response(request_id, result)
        except Exception as e:
            self._send_error(request_id, -32000, str(e))

    def _send_response(self, request_id: int, result: Any):
        """Отправить успешный ответ"""
        if not self.client_socket:
            return

        response = {
            'id': request_id,
            'result': result
        }
        try:
            self.client_socket.sendall((json.dumps(response) + '\n').encode())
        except:
            pass

    def _send_error(self, request_id: Optional[int], code: int, message: str):
        """Отправить ошибку"""
        if not self.client_socket:
            return

        response = {
            'id': request_id,
            'error': {
                'code': code,
                'message': message
            }
        }
        try:
            self.client_socket.sendall((json.dumps(response) + '\n').encode())
        except:
            pass

    def _send_notification(self, notification: dict):
        """Отправить уведомление (без запроса)"""
        with self.notification_lock:
            self.notification_queue.append(notification)

    def _notification_loop(self):
        """Отправляем уведомления клиенту"""
        while self.running:
            try:
                if self.client_socket and self.notification_queue:
                    with self.notification_lock:
                        notif = self.notification_queue.pop(0)

                    self.client_socket.sendall((json.dumps(notif) + '\n').encode())

                time.sleep(0.1)
            except Exception as e:
                print(f"[API] Notification error: {e}")
                time.sleep(1)

    # ==================== Обработчики методов ====================

    def _handle_get_peers(self, params: dict) -> dict:
        """Получить список пиров"""
        peers = []
        for ip, info in self.backend.discovery.get_all_peers().items():
            # Проверяем, есть ли активный чат
            has_chat = info['username'] in self.backend.active_chats

            peers.append({
                'username': info['username'],
                'device_id': info['device_id'],
                'ip': ip,
                'status': self._get_status(info['last_seen']),
                'last_seen': info['last_seen'],
                'has_chat': has_chat,
                'capabilities': ['files']  # Заглушка
            })

        return {'peers': peers}

    def _handle_get_peer_info(self, params: dict) -> dict:
        """Детальная информация о пире"""
        username = params.get('username')
        if not username:
            raise ValueError("username required")

        # Ищем пира
        for ip, info in self.backend.discovery.get_all_peers().items():
            if info['username'] == username:
                chat_id = self.backend.active_chats.get(username)

                return {
                    'username': info['username'],
                    'device_id': info['device_id'],
                    'ip': ip,
                    'port': info.get('port', 37021),
                    'status': self._get_status(info['last_seen']),
                    'last_seen': info['last_seen'],
                    'first_seen': info.get('first_seen', info['last_seen']),
                    'chat_id': chat_id,
                    'capabilities': {
                        'file_transfer': True,
                        'voice_calls': False,
                        'video_calls': False
                    }
                }

        raise ValueError(f"Peer {username} not found")

    def _handle_start_chat(self, params: dict) -> dict:
        """Начать чат с пиром"""
        username = params.get('username')
        if not username:
            raise ValueError("username required")

        success = self.backend.start_chat(username)
        if success:
            return {
                'status': 'handshake_initiated',
                'chat_id': self.backend.active_chats.get(username),
                'message': f"Handshake sent to {username}"
            }
        else:
            raise ValueError(f"Failed to start chat with {username}")

    def _handle_send_message(self, params: dict) -> dict:
        """Отправить сообщение"""
        peer = params.get('peer')
        text = params.get('text')

        if not peer or not text:
            raise ValueError("peer and text required")

        success = self.backend.send_message(peer, text)
        if success:
            # Генерируем временный ID сообщения
            msg_id = f"msg_{int(time.time())}_{hash(text) % 10000}"

            return {
                'status': 'sent',
                'msg_id': msg_id,
                'timestamp': time.time(),
                'chat_id': self.backend.active_chats.get(peer)
            }
        else:
            raise ValueError(f"Failed to send message to {peer}")

    def _handle_get_messages(self, params: dict) -> dict:
        """Получить историю сообщений"""
        peer = params.get('peer')
        limit = params.get('limit', 50)

        if not peer:
            raise ValueError("peer required")

        # Получаем chat_id
        chat_id = self.backend.active_chats.get(peer)
        if not chat_id:
            return {'messages': [], 'total': 0, 'count': 0}

        # Запрашиваем из базы
        messages = self.backend.db.get_conversation(chat_id, limit)

        result = []
        for msg in messages:
            sender, encrypted, timestamp, delivered = msg
            text = "[encrypted]"
            try:
                # если в БД хранится читаемый текст — вернём его
                if isinstance(encrypted, (bytes, bytearray)):
                    try:
                        decoded = encrypted.decode('utf-8')
                        text = decoded
                    except Exception:
                        # возможно это сериализованный JSON или бинарные данные
                        text = "[encrypted]"
                elif isinstance(encrypted, str):
                    text = encrypted
            except Exception:
                text = "[encrypted]"

            result.append({
                'msg_id': f"msg_{timestamp}",
                'from': 'me' if sender == self.backend.username else sender,
                'text': text,
                'timestamp': timestamp,
                'status': 'delivered' if delivered else 'sent'
            })

        return {
            'total': len(result),
            'count': len(result),
            'messages': result
        }

    def _handle_mark_read(self, params: dict) -> dict:
        """Отметить сообщения как прочитанные"""
        chat_id = params.get('chat_id')
        up_to = params.get('up_to')

        if not chat_id:
            raise ValueError("chat_id required")

        # В реальности - обновить статус в БД и отправить уведомление пиру
        return {
            'status': 'marked',
            'count': 1,
            'chat_id': chat_id
        }

    def _handle_get_my_info(self, params: dict) -> dict:
        """Информация о себе"""
        return {
            'username': self.backend.username,
            'device_id': self.backend.device_id,
            'ip': '127.0.0.1',  # Локальный
            'port': 37021,
            'status': 'online',
            'uptime': time.time() - self.backend.start_time if hasattr(self.backend, 'start_time') else 0,
            'active_chats': len(self.backend.active_chats),
            'total_messages': 0  # Заглушка
        }

    def _handle_rotate_keys(self, params: dict) -> dict:
        """Смена ключей"""
        chat_id = params.get('chat_id')

        if chat_id:
            self.backend.crypto.rotate_keys(chat_id)
            return {'status': 'rotated', 'chat_id': chat_id}
        else:
            # Ротировать все ключи
            for cid in self.backend.active_chats.values():
                self.backend.crypto.rotate_keys(cid)
            return {'status': 'rotated', 'count': len(self.backend.active_chats)}

    def _get_status(self, last_seen: float) -> str:
        """Определить статус по времени последнего появления"""
        age = time.time() - last_seen
        if age < 30:
            return 'online'
        elif age < 120:
            return 'away'
        else:
            return 'offline'

    # ==================== Методы для отправки уведомлений ====================

    def notify_message_received(self, from_peer: str, message: dict):
        """Уведомить о новом сообщении"""
        self._send_notification({
            'event': 'message_received',
            'data': {
                'from': from_peer,
                'chat_id': self.backend.active_chats.get(from_peer),
                'message': {
                    'msg_id': message.get('msg_id'),
                    'text': message.get('content'),
                    'timestamp': message.get('timestamp')
                }
            }
        })

    def notify_peer_status(self, peer: str, old_status: str, new_status: str):
        """Уведомить об изменении статуса пира"""
        self._send_notification({
            'event': 'peer_status_changed',
            'data': {
                'username': peer,
                'old_status': old_status,
                'new_status': new_status,
                'timestamp': time.time()
            }
        })

    def notify_message_delivered(self, msg_id: str, to: str):
        """Уведомить о доставке сообщения"""
        self._send_notification({
            'event': 'message_delivered',
            'data': {
                'msg_id': msg_id,
                'to': to,
                'delivered_at': time.time()
            }
        })

    def stop(self):
        """Остановка сервера"""
        self.running = False
        if self.client_socket:
            self.client_socket.close()
        if self.server_socket:
            self.server_socket.close()
        try:
            os.unlink(SOCKET_PATH)
        except:
            pass