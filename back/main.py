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

from core.crypto import SecureCryptoCore
from core.exceptions import CryptoError
from network.discovery import PeerDiscovery
from network.connection import ConnectionManager
from network.onion_router import OnionRouter
from network.protocols import MessageType
from storage.database import SecureDatabase
from messaging.handshake import HandshakeManager


class SecureMessenger:
    """Главный класс мессенджера"""

    def __init__(self, username: str):
        self.username = username
        self.start_time = time.time()
        self.device_id = hashlib.sha256(f"{username}{socket.gethostname()}".encode()).hexdigest()[:16]

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

        print(f"🧅 Инициализация Onion Router...")
        self.router = OnionRouter(self.connection, self.crypto)
        self.router.file_manager.on_file_offer = self._on_incoming_file_offer

        print(f"💾 Инициализация базы данных...")
        self.db = SecureDatabase()

        print(f"🤝 Инициализация handshake менеджера...")
        self.handshake = HandshakeManager(self.crypto, self.username)
        self.active_chats = {}

        print(f"\n✅ {username} готов к работе!\n")

    def _on_peer_found(self, ip: str, info: dict):
        print(f"\n📢 Найден пир: {info['username']} ({ip})")
        print(f"   Device ID: {info['device_id']}")
        print(f"   Последняя активность: {time.strftime('%H:%M:%S', time.localtime(info['last_seen']))}")
        if info.get('public_key'):
            try:
                pub_key_bytes = base64.b64decode(info['public_key'])
                if self.crypto.verify_peer_identity(info['device_id'], pub_key_bytes):
                    print(f"   ✅ Ключ пира сохранён")
                else:
                    print(f"   ❌ Ошибка сохранения ключа")
            except Exception as e:
                print(f"   ❌ Ошибка обработки ключа: {e}")

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
            elif msg_type in [MessageType.FILE_OFFER, MessageType.FILE_ACCEPT, MessageType.FILE_CHUNK, MessageType.FILE_COMPLETE, MessageType.FILE_REJECT, MessageType.FILE_ERROR]:
                print(f"\n📁 Получено FILE сообщение: {msg_type} от {addr[0]}")
                # always forward IP address for file routing
                self.router.handle_incoming(msg_type, data, addr[0])
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
            self.active_chats[peer_name] = chat_id
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
                for local_id, remote_id in self.crypto.chat_mappings.items():
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
        except CryptoError as e:
            print(f"\n❌ Ошибка расшифровки: {e}")

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
        handshake_msg = self.handshake.initiate(peer_name, ip, info['device_id'])
        if self.connection.send_to_peer(ip, handshake_msg):
            print(f"   ✅ Handshake отправлен")
            # Ждем ответа 1 секунду
            time.sleep(1.0)
            # Проверяем установился ли чат
            if peer_name in self.active_chats:
                print(f"   ✅ Чат с {peer_name} установлен")
                return True
            else:
                print(f"   ⏳ Ожидаем ответа от {peer_name}...")
                return False
        else:
            print(f"   ❌ {peer_name} не отвечает")
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

    def cleanup(self):
        print("\n🧹 Очистка ресурсов...")
        self.discovery.stop()
        self.connection.stop()
        print("✅ Завершено")


class ConsoleFrontend(cmd.Cmd):
    """Консольный интерфейс для тестирования"""
    intro = """
Команды:
  peers              - показать список пиров
  chat <имя>         - начать чат с пиром
  send <имя> <текст> - отправить сообщение
  info [имя]         - информация о себе или пире
  myinfo             - информация о себе
  exit               - выход
"""
    prompt = '> '

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