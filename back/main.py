"""
Secure P2P Messenger
Главный файл - поддерживает и GUI, и консольный режим
"""

import sys
import time
import hashlib
import socket
import base64
import cmd
import uuid
import subprocess
import threading
import json

from core.crypto import SecureCryptoCore
from core.exceptions import CryptoError
from network.discovery import PeerDiscovery
from network.connection import ConnectionManager
from network.onion_router import OnionRouter
from network.protocols import MessageType
from storage.database import SecureDatabase
from messaging.handshake import HandshakeManager


def get_mac_address():
    """Получить MAC-адрес для уникальной генерации ID"""
    try:
        # Попытка получить MAC через системные вызовы
        if sys.platform == "win32":
            result = subprocess.run(['getmac'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if ':' in line and not line.startswith('  '):
                    mac = line.split(':')[0].strip().replace('-', ':')
                    if len(mac) == 17:
                        return mac
        else:
            # Linux/macOS
            result = subprocess.run(['ifconfig'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            for line in lines:
                if 'ether' in line.lower():
                    parts = line.split()
                    for part in parts:
                        if ':' in part and len(part) == 17:
                            return part
    except:
        pass
    
    # Fallback: сгенерировать случайный MAC
    return ':'.join(['{:02x}'.format(uuid.getnode() >> elements & 0xff) for elements in range(0, 8*6, 8)][::-1])


def generate_unique_device_id(username: str) -> str:
    """Сгенерировать уникальный device_id с MAC-адресом"""
    mac = get_mac_address()
    hostname = socket.gethostname()
    timestamp = str(int(time.time()))
    unique_string = f"{username}{hostname}{mac}{timestamp}"
    return hashlib.sha256(unique_string.encode()).hexdigest()[:16]


class SecureMessenger:
    """Главный класс мессенджера"""

    def __init__(self, username: str):
        if not username or not username.strip():
            raise ValueError("Username cannot be None or empty")
        
        self.username = username.strip()
        self.start_time = time.time()
        self.device_id = generate_unique_device_id(username)
        self.mac_address = get_mac_address()
        
        # Mesh-сеть компоненты
        self.id_conflicts = {}  # device_id -> conflict_info
        self.mesh_queue = {}    # target_id -> messages
        self.relay_nodes = {}   # node_id -> RelayNode

        print(f"\n🚀 Запуск Secure P2P Messenger")
        print(f"   Пользователь: {username}")
        print(f"   Device ID: {self.device_id}")
        print(f"   Время: {time.strftime('%H:%M:%S')}")

        print(f"\n🔐 Инициализация криптографического ядра...")
        self.crypto = SecureCryptoCore(self.device_id)
        pub_key_bytes = self.crypto.get_identity_public_bytes()
        self.public_key_b64 = base64.b64encode(pub_key_bytes).decode()
        print(f"   Публичный ключ: {len(pub_key_bytes)} байт")
        print(f"   Base64: {self.public_key_b64[:50]}...")

        print(f"\n📡 Запуск обнаружения пиров...")
        self.discovery = PeerDiscovery(username=self.username, device_id=self.device_id, public_key_b64=self.public_key_b64)
        self.discovery.on_peer_found = self._on_peer_found
        self.discovery.start()

        print(f"🔌 Запуск менеджера соединений...")
        self.connection = ConnectionManager()
        self.connection.start(self._on_message)
        self.connection.peer_id = self.device_id

        # keep track of names user asked to handshake with (keyed by IP)
        self.pending_chat_requests = {}  # ip -> requested_peer_name

        print(f"🧅 Инициализация Onion Router...")
        self.router = OnionRouter(self.connection, self.crypto)
        self.router.file_manager.on_file_offer = self._on_incoming_file_offer
        
        # Включить mesh-функциональность
        self.router.enable()

        print(f"💾 Инициализация базы данных...")
        self.db = SecureDatabase()
        
        # Инициализация mesh-компонентов
        print(f"🌐 Инициализация Mesh-сети...")
        self._init_mesh_components()

        print(f"🤝 Инициализация handshake менеджера...")
        self.handshake = HandshakeManager(self.crypto, self.username, self.discovery)
        self.active_chats = {}

        print(f"\n✅ {username} готов к работе!\n")

    def _on_peer_found(self, ip: str, info: dict):
        print(f"\n📢 Найден пир: {info['username']} ({ip})")
        print(f"   Device ID: {info['device_id']}")
        print(f"   Последняя активность: {time.strftime('%H:%M:%S', time.localtime(info['last_seen']))}")
        
        # Зарегистрировать пира в connection manager для mesh-сети
        self.connection.register_peer(info['device_id'], ip, info.get('port', 37021))
        
        # Добавить как потенциального ретранслятора
        if hasattr(self.router, 'relay_manager'):
            self.router.relay_manager.update_peer_status(info['device_id'], {
                'bandwidth': 100,
                'is_relay': True,
                'reputation': 1.0
            }, (ip, info.get('port', 37021)))
        
        if info.get('public_key'):
            try:
                pub_key_bytes = base64.b64decode(info['public_key'])
                print(f"  🔍 Пытаемся сохранить ключ для device_id: {info['device_id']}")
                if self.crypto.verify_peer_identity(info['device_id'], pub_key_bytes):
                    print(f"   ✅ Ключ пира сохранён")
                else:
                    print(f"   ❌ Ошибка сохранения ключа")
            except Exception as e:
                print(f"   ❌ Ошибка обработки ключа: {e}")
        else:
            print(f"   ⚠️ Нет публичного ключа у пира")

    def _on_message(self, data: dict, addr: tuple):
        msg_type = data.get('type')
        print(f"[main] _on_message called: type={msg_type}, addr={addr[0]}, msg_keys={list(data.keys())}")
        if msg_type == 'file_chunk':
            chunk_data_size = len(data.get('data', ''))
            print(f"[main] FILE_CHUNK data field size: {chunk_data_size} chars")
        try:
            if msg_type == MessageType.HANDSHAKE_INIT:
                print(f"\n📥 Получен handshake INIT от {addr[0]}")
                self._handle_handshake_init(data, addr)
            elif msg_type == MessageType.HANDSHAKE_RESPONSE:
                print(f"\n📥 Получен handshake RESPONSE от {addr[0]}")
                self._handle_handshake_response(data, addr)
            elif msg_type == MessageType.HANDSHAKE_COMPLETE:
                print(f"\n📥 Получен handshake COMPLETE от {addr[0]}")
                self._handle_handshake_complete(data, addr)
            elif msg_type == MessageType.SECURE_MESSAGE:
                print(f"\n📥 Получено SECURE MESSAGE от {addr[0]}")
                self._handle_secure_message(data, addr)
            elif msg_type == MessageType.DELIVERY_RECEIPT:
                print(f"\n📥 Получено DELIVERY RECEIPT от {addr[0]}")
                self.router.handle_incoming(msg_type, data, addr[0])
            elif msg_type in [MessageType.FILE_OFFER, MessageType.FILE_ACCEPT, MessageType.FILE_CHUNK, MessageType.FILE_COMPLETE, MessageType.FILE_REJECT, MessageType.FILE_ERROR]:
                print(f"\n📁 Получено FILE сообщение: {msg_type} от {addr[0]}")
                # always forward IP address for file routing
                self.router.handle_incoming(msg_type, data, addr[0])
            # Mesh-сеть сообщения
            elif msg_type == MessageType.MESSAGE_RELAY:
                print(f"\n🔄 Получено MESSAGE RELAY от {addr[0]}")
                self._handle_message_relay(data, addr)
            elif msg_type == MessageType.MESSAGE_STORE:
                print(f"\n📦 Получено MESSAGE STORE от {addr[0]}")
                self._handle_message_store(data, addr)
            elif msg_type == MessageType.QUEUE_REQUEST:
                print(f"\n📋 Получено QUEUE REQUEST от {addr[0]}")
                self._handle_queue_request(data, addr)
            elif msg_type == MessageType.QUEUE_SYNC:
                print(f"\n🔄 Получено QUEUE SYNC от {addr[0]}")
                self._handle_queue_sync(data, addr)
            elif msg_type == MessageType.RELAY_STATUS_UPDATE:
                print(f"\n📊 Получено RELAY STATUS от {addr[0]}")
                self._handle_relay_status_update(data, addr)
            elif msg_type == MessageType.ID_CONFLICT:
                print(f"\n⚠️ Получен ID CONFLICT от {addr[0]}")
                self._handle_id_conflict(data, addr)
            else:
                print(f"\n❓ Неизвестный тип сообщения: {msg_type}")
        except Exception as e:
            print(f"\n❌ Ошибка обработки сообщения: {e}")
            import traceback
            traceback.print_exc()

    def _handle_handshake_init(self, data: dict, addr: tuple):
        response = self.handshake.handle_initiation(data, addr)
        if response:
            print(f"   ✅ Отправляем ответ на handshake")
            self.connection.send_to_peer(addr[0], response)
            return
        try:
            peer_info = self.discovery.get_all_peers().get(addr[0])
            if peer_info and peer_info.get('public_key'):
                print(f"   ⚠️ Попытка загрузить публичный ключ пира из discovery ({addr[0]}) и повторить")
                try:
                    pub_bytes = base64.b64decode(peer_info.get('public_key'))
                    if self.crypto.verify_peer_identity(peer_info.get('device_id'), pub_bytes):
                        response = self.handshake.handle_initiation(data, addr)
                        if response:
                            print(f"   ✅ Отправляем ответ на handshake (после загрузки ключа)")
                            self.connection.send_to_peer(addr[0], response)
                            return
                except Exception as e:
                    print(f"   ❌ Ошибка загрузки ключа из discovery: {e}")
        except Exception:
            pass
        print(f"   ❌ Ошибка обработки handshake")

    def _handle_handshake_response(self, data: dict, addr: tuple):
        success, chat_id, follow_up = self.handshake.handle_response(data)
        if success:
            peer_name = data['from']
            # register chat under actual name
            self.active_chats[peer_name] = chat_id
            # also register under requested name if different
            req = self.pending_chat_requests.pop(addr[0], None)
            if req and req != peer_name:
                print(f"   ℹ️ Handshake requested as '{req}', actual name is '{peer_name}', linking both")
                self.active_chats[req] = chat_id
            print(f"\n✅ Защищённый канал с {peer_name} установлен!")
            print(f"   Локальный chat_id: {chat_id[:8]}...")
            if follow_up:
                print(f"   ✅ Отправляем HANDSHAKE_COMPLETE для финализации маппинга")
                self.connection.send_to_peer(addr[0], follow_up)
            return
        try:
            peer_info = self.discovery.get_all_peers().get(addr[0])
            if peer_info and peer_info.get('public_key'):
                print(f"   ⚠️ Попытка загрузить публичный ключ пира из discovery ({addr[0]}) и повторить обработку response")
                try:
                    pub_bytes = base64.b64decode(peer_info.get('public_key'))
                    if self.crypto.verify_peer_identity(peer_info.get('device_id'), pub_bytes):
                        success, chat_id, follow_up = self.handshake.handle_response(data)
                        if success:
                            peer_name = data['from']
                            self.active_chats[peer_name] = chat_id
                            print(f"\n✅ Защищённый канал с {peer_name} установлен (после загрузки ключа)!")
                            if follow_up:
                                self.connection.send_to_peer(addr[0], follow_up)
                            return
                except Exception as e:
                    print(f"   ❌ Ошибка загрузки ключа из discovery: {e}")
        except Exception:
            pass
        print(f"\n❌ Ошибка установки канала с {data['from']}")

    def _handle_handshake_complete(self, data: dict, addr: tuple):
        ok = self.handshake.handle_complete(data)
        if ok:
            print(f"   ✅ Маппинг зарегистрирован (HANDSHAKE_COMPLETE)")
            # Находим имя пира по IP
            peer_name = None
            for ip, info in self.discovery.get_all_peers().items():
                if ip == addr[0]:
                    peer_name = info['username']
                    break
            # Добавляем в активные чаты если еще нет
            if peer_name and peer_name not in self.active_chats:
                # Ищем chat_id из маппинга
                for local_id, remote_id in self.crypto._local_to_remote.items():
                    if remote_id == data.get('chat_id'):
                        self.active_chats[peer_name] = local_id
                        print(f"   ✅ Чат с {peer_name} активирован после HANDSHAKE_COMPLETE")
                        break
        else:
            print(f"   ❌ Не удалось зарегистрировать маппинг")

    def _handle_secure_message(self, data: dict, addr: tuple):
        encrypted = data['encrypted']
        sender = None
        for ip, info in self.discovery.get_all_peers().items():
            if ip == addr[0]:
                sender = info['username']
                break
        if not sender:
            print(f"   ❌ Неизвестный отправитель {addr[0]}")
            return
        try:
            decrypted = self.crypto.decrypt_message(encrypted, sender)
        except CryptoError as e:
            msg = str(e)
            # попытка восстановления маппинга если у нас уже есть чат с отправителем
            if "No session for remote chat" in msg and sender in self.active_chats:
                remote_id = encrypted.get('remote_chat_id') or encrypted.get('chat_id')
                local_id = self.active_chats[sender]
                if remote_id:
                    print(f"[main] 🔄 Восстанавливаем маппинг {remote_id[:8]} -> {local_id[:8]}")
                    self.crypto.register_chat_mapping(local_id, remote_id)
                    try:
                        decrypted = self.crypto.decrypt_message(encrypted, sender)
                        print(f"[main] ✅ Расшифровка после восстановления маппинга успешна")
                    except CryptoError as e2:
                        print(f"\n❌ Ошибка расшифровки после маппинга: {e2}")
                        return
                else:
                    print(f"\n❌ Ошибка расшифровки: {e}")
                    return
            else:
                print(f"\n❌ Ошибка расшифровки: {e}")
                return

        # если мы попали сюда, decrypted определён
        print(f"\n💬 [{sender}]: {decrypted['content']}")
        msg_id = hashlib.sha256(f"{sender}{decrypted['timestamp']}{decrypted['content']}".encode()).hexdigest()[:16]
        local_chat_id = None
        if sender in self.active_chats:
            local_chat_id = self.active_chats[sender]
        else:
            try:
                remote_id = encrypted.get('remote_chat_id') or encrypted.get('chat_id')
                res = self.crypto.get_session_for_message(remote_id, is_remote=True) if remote_id else None
                if res:
                    local_chat_id = res[0]
            except Exception:
                local_chat_id = None
        try:
            self.db.add_message(msg_id, local_chat_id or 'unknown', sender, decrypted['content'].encode(), 'in')
        except Exception as e:
            print(f"   ❌ Не удалось сохранить сообщение в БД: {e}")

    def _on_incoming_file_offer(self, session):
        sender_id = session.file_info.sender_id
        filename = session.file_info.filename
        file_size = session.file_info.file_size
        print(f"\n📥 Incoming file: {filename} ({file_size} bytes) from {sender_id}")
        # store a local chat message (so UI shows link)
        # determine the username of the sender for chat_id
        sender_username = None
        for ip, info in self.discovery.get_all_peers().items():
            if info.get('device_id') == sender_id:
                sender_username = info.get('username')
                break
        chat_id = sender_username or 'unknown'
        try:
            msg_id = hashlib.sha256(f"{chat_id}{time.time()}{filename}".encode()).hexdigest()[:16]
            # plaintext content for file notification plus download link
            link = f"/downloads/{filename}"
            content = f"📥 Received file: {filename} ({file_size} bytes) {link}"
            self.db.add_message(msg_id, self.active_chats.get(chat_id, 'unknown'), 'system', content.encode(), 'in')
        except Exception as e:
            print(f"   ⚠️ Не удалось сохранить локальное уведомление о файле: {e}")

    def start_chat(self, peer_name: str) -> bool:
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"❌ Пир {peer_name} не найден")
            return False
        ip, info = peer
        print(f"   IP: {ip}")
        print(f"   Device ID: {info['device_id']}")

        # Проверяем наличие публичного ключа пира
        if not info.get('public_key'):
            print(f"❌ Нет публичного ключа для {peer_name}")
            print(f"   💡 Дождитесь broadcast от пира или проверьте соединение")
            return False
        
        print(f"   ✅ Публичный ключ найден")

        # Создаём handshake сообщение
        handshake_msg = self.handshake.initiate(
            peer_name, ip, info['device_id']
        )

        # Отправляем
        if self.connection.send_to_peer(ip, handshake_msg):
            print(f"   ✅ Handshake отправлен")
            # record the requested name for this IP, in case the peer reports itself with another username
            self.pending_chat_requests[ip] = peer_name
            # Ждем ответ, проверяя статус в цикле до таймаута
            deadline = time.time() + 5.0
            while time.time() < deadline:
                if peer_name in self.active_chats:
                    print(f"   ✅ Чат с {peer_name} установлен")
                    self.pending_chat_requests.pop(ip, None)
                    return True
                time.sleep(0.2)
            # если вышли из цикла -- еще не установился
            if peer_name in self.active_chats:
                print(f"   ✅ Чат с {peer_name} установлен")
                self.pending_chat_requests.pop(ip, None)
                return True
            else:
                print(f"   ❌ Handshake с {peer_name} не завершён (таймаут)")
                self.pending_chat_requests.pop(ip, None)
                return False
        else:
            print(f"   ❌ {peer_name} не отвечает")
            self.pending_chat_requests.pop(ip, None)
            return False

    def send_message(self, peer_name: str, text: str) -> bool:
        if peer_name not in self.active_chats:
            print(f"[main] 🤝 No active chat with {peer_name}, initiating handshake")
            if self.start_chat(peer_name):
                print(f"[main] ✅ Handshake successful with {peer_name}")
            else:
                print(f"❌ Нет активного чата с {peer_name}")
                return False
        local_chat_id = self.active_chats[peer_name]
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"❌ {peer_name} не в сети")
            return False
        ip, info = peer
        try:
            encrypted = self.crypto.encrypt_message(local_chat_id, text, self.username)
            message = {'type': MessageType.SECURE_MESSAGE, 'encrypted': encrypted}
            if self.connection.send_to_peer(ip, message):
                print(f"   ✅ {peer_name}: {text}")
                try:
                    msg_id = hashlib.sha256(f"{self.username}{time.time()}{text}".encode()).hexdigest()[:16]
                    self.db.add_message(msg_id, local_chat_id, self.username, text.encode(), 'out')
                except Exception as e:
                    print(f"   ⚠️ Не удалось сохранить исходящее сообщение: {e}")
                return True
            else:
                print(f"   ❌ Не удалось отправить")
                return False
        except CryptoError as e:
            print(f"   ❌ Ошибка шифрования: {e}")
            return False

    def send_file(self, peer_name: str, file_path: str) -> str:
        print(f"[main] 🔍 Looking for peer: {peer_name}")
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"[main] ❌ Peer {peer_name} not found in discovery")
            raise ValueError(f"Peer {peer_name} not found")
        
        ip, info = peer
        device_id = info.get('device_id')
        if not device_id:
            raise ValueError(f"Device ID for {peer_name} not found")
        
        print(f"[main] ✅ Found peer {peer_name}: ip={ip}, device_id={device_id}")
        
        # Проверяем есть ли активный чат
        if peer_name not in self.active_chats:
            print(f"[main] 🤝 No active chat with {peer_name}, initiating handshake")
            if not self.start_chat(peer_name):
                raise ValueError(f"Could not establish secure session with {peer_name}")
        
        return self.router.send_file(ip, file_path, device_id)

    def list_peers(self):
        peers = self.discovery.get_all_peers()
        if not peers:
            print("📭 Нет активных пиров")
            return
        print("\n📋 Активные пиры:")
        print("-" * 60)
        for ip, info in peers.items():
            age = time.time() - info['last_seen']
            if age < 30:
                status = "🟢 ONLINE"
            elif age < 120:
                status = "🟡 AWAY"
            else:
                status = "⚫ OFFLINE"
            chat_mark = "💬" if info['username'] in self.active_chats else ""
            print(f"  {status} {info['username']} {chat_mark}")
            print(f"     IP: {ip}")
            print(f"     Device: {info['device_id'][:8]}...")
            print(f"     Last seen: {age:.0f} сек назад")
            if info['username'] in self.active_chats:
                chat_id = self.active_chats[info['username']]
                print(f"     Chat ID: {chat_id[:8]}...")
        print("-" * 60)

    def peer_info(self, peer_name: str):
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"❌ Пир {peer_name} не найден")
            return
        ip, info = peer
        age = time.time() - info['last_seen']
        print(f"\n👤 Информация о {peer_name}:")
        print("-" * 60)
        print(f"   IP: {ip}")
        print(f"   Device ID: {info['device_id']}")
        print(f"   Порт: {info.get('port', 37021)}")
        print(f"   Последняя активность: {age:.0f} сек назад")
        print(f"   Статус чата: {'✅ активен' if peer_name in self.active_chats else '❌ нет'}")
        if peer_name in self.active_chats:
            chat_id = self.active_chats[peer_name]
            print(f"   Локальный chat_id: {chat_id}")
        if 'public_key' in info:
            print(f"   Публичный ключ: {info['public_key'][:50]}...")
        print("-" * 60)

    def my_info(self):
        print(f"\n👤 Моя информация:")
        print("-" * 60)
        print(f"   Имя: {self.username}")
        print(f"   Device ID: {self.device_id}")
        print(f"   Публичный ключ (base64): {self.public_key_b64[:50]}...")
        print(f"   Время работы: {(time.time() - self.start_time):.0f} сек")
        print(f"   Активных чатов: {len(self.active_chats)}")
        print(f"   Известных пиров: {len(self.discovery.get_all_peers())}")
        print("-" * 60)

    def get_my_info(self):
        """Получить информацию о себе для API"""
        return {
            'username': self.username,
            'device_id': self.device_id,
            'ip': '127.0.0.1',
            'port': 37021,
            'status': 'online',
            'uptime': time.time() - self.start_time,
            'active_chats': len(self.active_chats)
        }

    def get_all_peers(self):
        """Получить всех пиров для API"""
        return self.discovery.get_all_peers()

    def get_peer_by_name(self, name):
        """Найти пира по имени для API"""
        return self.discovery.get_peer_by_name(name)

    def get_conversation(self, chat_id, limit=50):
        """Получить историю сообщений для API"""
        try:
            return self.db.get_conversation(chat_id, limit)
        except:
            return []

    def get_incoming_messages(self, chat_id, limit=50):
        """Получить только входящие сообщения для API"""
        try:
            return self.db.get_incoming_messages(chat_id, limit)
        except:
            return []

    def cleanup(self):
        """Очистка ресурсов"""
        print("\n🧹 Очистка ресурсов...")
        try:
            if hasattr(self, 'discovery'):
                self.discovery.stop()
            if hasattr(self, 'connection'):
                self.connection.stop()
            if hasattr(self, 'router') and hasattr(self.router, 'relay_manager'):
                self.router.relay_manager.shutdown()
            print("✅ Ресурсы очищены")
        except Exception as e:
            print(f"❌ Ошибка очистки: {e}")

    # ==================== MESH-СЕТЬ МЕТОДЫ ====================

    def _init_mesh_components(self):
        """Инициализация mesh-компонентов"""
        try:
            # Зарегистрировать себя как ретранслятор
            if hasattr(self.router, 'relay_manager'):
                self.db.add_mesh_relay(
                    node_id=self.device_id,
                    ip='127.0.0.1',  # Будет обновлено при обнаружении
                    port=37021,
                    capacity=100
                )
                print(f"   ✅ Зарегистрирован как mesh-ретранслятор: {self.device_id}")
            
            # Запустить фоновую очистку истекших сообщений
            threading.Thread(target=self._cleanup_expired_messages, daemon=True).start()
            print(f"   ✅ Запущена очистка mesh-очередей")
            
        except Exception as e:
            print(f"   ❌ Ошибка инициализации mesh: {e}")

    def _handle_message_relay(self, data: dict, addr: tuple):
        """Обработка ретранслируемого сообщения"""
        try:
            target_id = data.get('target_id')
            original_sender = data.get('original_sender')
            path = data.get('path', [])
            encrypted_payload = data.get('encrypted_payload')
            
            if not all([target_id, original_sender, encrypted_payload]):
                print("   ❌ Некорректное MESSAGE_RELAY")
                return
            
            # Проверить, не является ли этот узел целью
            if target_id == self.device_id:
                # Расшифровать и обработать сообщение
                try:
                    original_message = json.loads(encrypted_payload)
                    self._on_message(original_message, addr)
                    print(f"   ✅ Получено ретранслированное сообщение от {original_sender}")
                except Exception as e:
                    print(f"   ❌ Ошибка расшифровки: {e}")
                return
            
            # Продолжить ретрансляцию
            if hasattr(self.router, 'relay_manager'):
                success = self.router.relay_manager.relay_message(
                    target_id, json.loads(encrypted_payload), original_sender, path
                )
                if success:
                    print(f"   ✅ Сообщение ретранслировано далее к {target_id}")
                else:
                    print(f"   ❌ Не удалось ретранслировать сообщение к {target_id}")
            
        except Exception as e:
            print(f"   ❌ Ошибка обработки MESSAGE_RELAY: {e}")

    def _handle_message_store(self, data: dict, addr: tuple):
        """Обработка запроса на хранение сообщения"""
        try:
            target_id = data.get('target_id')
            original_sender = data.get('original_sender')
            message_data = data.get('message_data')
            
            if not all([target_id, original_sender, message_data]):
                print("   ❌ Некорректное MESSAGE_STORE")
                return
            
            # Сохранить в mesh-очередь
            queue_id = f"store_{target_id}_{int(time.time())}"
            self.db.add_mesh_message(
                queue_id=queue_id,
                target_id=target_id,
                message_id=message_data.get('msg_id', 'unknown'),
                original_sender=original_sender,
                encrypted_payload=json.dumps(message_data),
                ttl=data.get('ttl', 3600),
                priority=data.get('priority', 1)
            )
            
            print(f"   ✅ Сообщение сохранено в mesh-очереди для {target_id}")
            
            # Отправить подтверждение
            receipt = {
                'type': MessageType.DELIVERY_RECEIPT,
                'in_response_to': message_data.get('msg_id'),
                'status': 'delivered',
                'msg_id': f"receipt_{int(time.time())}",
                'timestamp': time.time()
            }
            self.connection.send_to_peer(addr[0], receipt)
            
        except Exception as e:
            print(f"   ❌ Ошибка обработки MESSAGE_STORE: {e}")

    def _handle_queue_request(self, data: dict, addr: tuple):
        """Обработка запроса сообщений из очереди"""
        try:
            requester_id = data.get('requester_id')
            since_timestamp = data.get('since_timestamp', 0)
            
            if requester_id != self.device_id:
                print("   ❌ QUEUE_REQUEST не для этого узла")
                return
            
            # Получить сообщения из очереди
            messages = self.db.get_mesh_messages_for_target(self.device_id, limit=50)
            
            if messages:
                print(f"   📤 Найдено {len(messages)} сообщений в очереди")
                
                for queue_id, message_id, original_sender, encrypted_payload, path, priority, created in messages:
                    # Отправить сообщение
                    try:
                        original_message = json.loads(encrypted_payload)
                        success = self.connection.send_message(original_sender, original_message)
                        
                        if success:
                            # Отметить как доставленное
                            self.db.mark_mesh_message_delivered(queue_id)
                            print(f"   ✅ Доставлено сообщение {message_id} от {original_sender}")
                        else:
                            print(f"   ❌ Не удалось доставить сообщение {message_id}")
                            
                    except Exception as e:
                        print(f"   ❌ Ошибка доставки сообщения {message_id}: {e}")
            else:
                print(f"   📭 Нет сообщений в очереди")
                
        except Exception as e:
            print(f"   ❌ Ошибка обработки QUEUE_REQUEST: {e}")

    def _handle_queue_sync(self, data: dict, addr: tuple):
        """Обработка синхронизации очередей"""
        try:
            queue_data = data.get('queue_data', {})
            sync_timestamp = data.get('sync_timestamp', time.time())
            
            target_id = queue_data.get('target_id')
            message_count = queue_data.get('message_count', 0)
            oldest_message = queue_data.get('oldest_message', 0)
            
            print(f"   🔄 Синхронизация очереди для {target_id}: {message_count} сообщений")
            
            # Можно добавить логику синхронизации здесь
            # Например, запросить недостающие сообщения
            
        except Exception as e:
            print(f"   ❌ Ошибка обработки QUEUE_SYNC: {e}")

    def _handle_relay_status_update(self, data: dict, addr: tuple):
        """Обработка обновления статуса ретранслятора"""
        try:
            relay_id = data.get('relay_id')
            capacity = data.get('capacity', 100)
            current_load = data.get('current_load', 0)
            reputation = data.get('reputation', 1.0)
            
            if not relay_id:
                print("   ❌ Некорректное RELAY_STATUS_UPDATE")
                return
            
            # Обновить в базе данных
            self.db.update_mesh_relay_status(
                node_id=relay_id,
                current_load=current_load,
                reputation=reputation,
                is_active=True
            )
            
            # Обновить в relay manager
            if hasattr(self.router, 'relay_manager'):
                self.router.relay_manager.update_peer_status(relay_id, {
                    'bandwidth': capacity,
                    'is_relay': True,
                    'reputation': reputation
                }, addr)
            
            print(f"   ✅ Обновлен статус ретранслятора {relay_id}")
            
        except Exception as e:
            print(f"   ❌ Ошибка обработки RELAY_STATUS_UPDATE: {e}")

    def _handle_id_conflict(self, data: dict, addr: tuple):
        """Обработка конфликта ID"""
        try:
            conflicting_id = data.get('conflicting_id')
            claimant_info = data.get('claimant_info', {})
            
            if conflicting_id == self.device_id:
                print(f"   ⚠️ Обнаружен конфликт ID для {self.device_id}")
                
                # Сгенерировать новый ID
                new_id = generate_unique_device_id(self.username)
                print(f"   🔄 Генерируем новый ID: {new_id}")
                
                # Отправить разрешение конфликта
                resolution = {
                    'type': MessageType.ID_RESOLUTION,
                    'resolved_id': new_id,
                    'resolution_type': 'regenerated',
                    'msg_id': f"resolve_{int(time.time())}",
                    'timestamp': time.time()
                }
                self.connection.send_to_peer(addr[0], resolution)
                
                # Обновить свой ID (требуется перезапуск)
                print(f"   ⚠️ Требуется перезапуск с новым ID: {new_id}")
                
        except Exception as e:
            print(f"   ❌ Ошибка обработки ID_CONFLICT: {e}")

    def _cleanup_expired_messages(self):
        """Фоновая очистка истекших сообщений"""
        while True:
            try:
                time.sleep(300)  # Каждые 5 минут
                deleted = self.db.cleanup_expired_mesh_messages()
                if deleted > 0:
                    print(f"   🗑️ Удалено {deleted} истекших mesh-сообщений")
            except Exception as e:
                print(f"   ❌ Ошибка очистки: {e}")

    def send_message_via_mesh(self, target_device_id: str, message: dict) -> bool:
        """Отправить сообщение через mesh-сеть"""
        try:
            if hasattr(self.router, 'relay_manager'):
                success = self.router.relay_manager.relay_message(
                    target_device_id, message, self.device_id
                )
                if success:
                    print(f"   📤 Сообщение отправлено через mesh к {target_device_id}")
                    return True
                else:
                    print(f"   ❌ Не удалось отправить сообщение через mesh")
                    return False
            else:
                # Fallback to direct connection
                return self.connection.send_message(target_device_id, message)
                
        except Exception as e:
            print(f"   ❌ Ошибка отправки через mesh: {e}")
            return False

    def get_mesh_stats(self) -> dict:
        """Получить статистику mesh-сети"""
        stats = {
            'device_id': self.device_id,
            'relays': 0,
            'queued_messages': 0,
            'active_circuits': 0
        }
        
        try:
            if hasattr(self.router, 'relay_manager'):
                relay_stats = self.router.relay_manager.get_stats()
                stats.update(relay_stats)
            
            queue_stats = self.db.get_mesh_queue_stats()
            stats['queued_messages'] = queue_stats['total_queued']
            
        except Exception as e:
            print(f"   ❌ Ошибка получения статистики: {e}")
        
        return stats


class ConsoleFrontend(cmd.Cmd):
    """Консольный интерфейс для тестирования"""
    intro = """
Команды:
  peers              - показать список пиров
  chat <имя>         - начать чат с пиром
  send <имя> <текст> - отправить сообщение
  info [имя]         - информация о себе или пире
  myinfo             - информация о себе
  mesh               - показать статистику mesh-сети
  mesh send <id> <msg> - отправить сообщение через mesh
  exit               - выход
"""
    prompt = "(messenger) "

    def __init__(self, messenger: SecureMessenger):
        super().__init__()
        self.messenger = messenger
        self.running = True

    def do_peers(self, arg):
        self.messenger.list_peers()

    def do_chat(self, arg):
        if not arg:
            print("❌ Укажите имя пира: chat <имя>")
            return
        self.messenger.start_chat(arg.strip())

    def do_send(self, arg):
        parts = arg.split(' ', 1)
        if len(parts) < 2:
            print("❌ Использование: send <имя> <текст>")
            return
        name, text = parts
        self.messenger.send_message(name.strip(), text.strip())

    def do_info(self, arg):
        if not arg:
            self.messenger.my_info()
        else:
            self.messenger.peer_info(arg.strip())

    def do_myinfo(self, arg):
        self.messenger.my_info()

    def do_exit(self, arg):
        print("👋 Завершение работы...")
        self.messenger.cleanup()
        return True

    def do_EOF(self, arg):
        return self.do_exit(arg)

    def do_mesh(self, arg):
        """Mesh-сеть команды: stats, send <device_id> <message>"""
        if not arg:
            stats = self.messenger.get_mesh_stats()
            print("\n📊 Mesh-сеть статистика:")
            print(f"  Device ID: {stats['device_id']}")
            print(f"  Активные ретрансляторы: {stats.get('known_relays', 0)}")
            print(f"  Сообщений в очередях: {stats.get('queued_messages', 0)}")
            print(f"  Активных цепей: {stats.get('active_circuits', 0)}")
            print(f"  Ретранслировано сообщений: {stats.get('relayed_msgs', 0)}")
            print(f"  Доставлено сообщений: {stats.get('messages_delivered', 0)}")
            return
        
        parts = arg.split()
        if parts[0] == "send" and len(parts) >= 3:
            device_id = parts[1]
            message_text = " ".join(parts[2:])
            
            # Создать тестовое сообщение
            test_message = {
                'type': 'SECURE_MESSAGE',
                'chat_id': f"mesh_{device_id}",
                'encrypted': {'content': message_text},
                'msg_id': f"mesh_{int(time.time())}",
                'timestamp': time.time()
            }
            
            success = self.messenger.send_message_via_mesh(device_id, test_message)
            if success:
                print(f"   ✅ Сообщение отправлено через mesh-сеть")
            else:
                print(f"   ❌ Не удалось отправить сообщение")
        else:
            print("Использование:")
            print("  mesh              - показать статистику mesh-сети")
            print("  mesh send <id> <msg> - отправить сообщение через mesh")

    def complete_chat(self, text, line, begidx, endidx):
        peers = self.messenger.discovery.get_all_peers()
        names = [info['username'] for info in peers.values()]
        return [name for name in names if name.startswith(text)]

    def complete_info(self, text, line, begidx, endidx):
        return self.complete_chat(text, line, begidx, endidx)

    def complete_send(self, text, line, begidx, endidx):
        parts = line.split()
        if len(parts) <= 2:
            return self.complete_chat(text, line, begidx, endidx)
        return []


def main():
    if len(sys.argv) < 2:
        print("Использование:")
        print("  python main.py <имя>              # Консольный режим")
        print("  python main.py <имя> --peers      # Показать пиров и выйти")
        print("  python main.py <имя> --chat <peer> # Начать чат")
        print("  python main.py <имя> --send <peer> <текст> # Отправить сообщение")
        sys.exit(1)

    username = sys.argv[1]
    messenger = SecureMessenger(username)
    print("\n⏳ Ожидание обнаружения пиров (3 сек)...")
    time.sleep(3)

    if len(sys.argv) == 2:
        console = ConsoleFrontend(messenger)
        try:
            console.cmdloop()
        except KeyboardInterrupt:
            print("\n\n👋 Пока!")
        finally:
            messenger.cleanup()
    else:
        mode = sys.argv[2]
        if mode == "--peers":
            messenger.list_peers()
        elif mode == "--chat" and len(sys.argv) > 3:
            messenger.start_chat(sys.argv[3])
            time.sleep(2)
        elif mode == "--send" and len(sys.argv) > 4:
            peer = sys.argv[3]
            text = sys.argv[4]
            messenger.send_message(peer, text)
        else:
            print("❌ Неверные аргументы")
        messenger.cleanup()


if __name__ == "__main__":
    main()