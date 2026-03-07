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
from network.protocols import MessageType
from storage.database import SecureDatabase
from messaging.handshake import HandshakeManager


class SecureMessenger:
    """
    Главный класс мессенджера
    """

    def __init__(self, username: str):
        self.username = username
        self.start_time = time.time()

        # Генерируем device_id из имени и hostname
        self.device_id = hashlib.sha256(
            f"{username}{socket.gethostname()}".encode()
        ).hexdigest()[:16]

        print(f"\n🚀 Запуск Secure P2P Messenger")
        print(f"   Пользователь: {username}")
        print(f"   Device ID: {self.device_id}")
        print(f"   Время: {time.strftime('%H:%M:%S')}")

        # Криптоядро
        print(f"\n🔐 Инициализация криптографического ядра...")
        self.crypto = SecureCryptoCore(self.device_id)

        # Получаем публичный ключ в base64 для передачи
        pub_key_bytes = self.crypto.get_identity_public_bytes()
        self.public_key_b64 = base64.b64encode(pub_key_bytes).decode()
        print(f"   Публичный ключ: {len(pub_key_bytes)} байт")
        print(f"   Base64: {self.public_key_b64[:50]}...")

        # Обнаружение пиров
        print(f"\n📡 Запуск обнаружения пиров...")
        self.discovery = PeerDiscovery(
            username=self.username,
            device_id=self.device_id,
            public_key_b64=self.public_key_b64
        )
        self.discovery.on_peer_found = self._on_peer_found
        self.discovery.start()

        # Менеджер соединений
        print(f"🔌 Запуск менеджера соединений...")
        self.connection = ConnectionManager()
        self.connection.start(self._on_message)

        # База данных
        print(f"💾 Инициализация базы данных...")
        self.db = SecureDatabase()

        # Handshake менеджер
        print(f"🤝 Инициализация handshake менеджера...")
        self.handshake = HandshakeManager(self.crypto, self.username)

        # Активные чаты: peer_name -> local_chat_id
        self.active_chats = {}

        print(f"\n✅ {username} готов к работе!\n")

    def _on_peer_found(self, ip: str, info: dict):
        """Колбэк при обнаружении нового пира"""
        print(f"\n📢 Найден пир: {info['username']} ({ip})")
        print(f"   Device ID: {info['device_id']}")
        print(f"   Последняя активность: {time.strftime('%H:%M:%S', time.localtime(info['last_seen']))}")

        # Сохраняем публичный ключ пира
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
        """Колбэк при получении сообщения"""
        msg_type = data.get('type')

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

            else:
                print(f"\n❓ Неизвестный тип сообщения: {msg_type}")

        except Exception as e:
            print(f"\n❌ Ошибка обработки сообщения: {e}")
            import traceback
            traceback.print_exc()

    def _handle_handshake_init(self, data: dict, addr: tuple):
        """Обработка handshake инициации"""
        response = self.handshake.handle_initiation(data, addr)
        if response:
            print(f"   ✅ Отправляем ответ на handshake")
            self.connection.send_to_peer(addr[0], response)
            return

        # Если подпись недействительна, возможно у нас ещё нет
        # публичного ключа пира из discovery. Попробуем загрузить
        # публичный ключ по IP и повторить верификацию.
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
        """Обработка ответа на handshake"""
        success, chat_id, follow_up = self.handshake.handle_response(data)
        if success:
            peer_name = data['from']
            self.active_chats[peer_name] = chat_id
            print(f"\n✅ Защищённый канал с {peer_name} установлен!")
            print(f"   Локальный chat_id: {chat_id[:8]}...")

            # Если есть follow-up сообщение (HANDSHAKE_COMPLETE), отправим его
            if follow_up:
                print(f"   ✅ Отправляем HANDSHAKE_COMPLETE для финализации маппинга")
                self.connection.send_to_peer(addr[0], follow_up)
            return

        # Retry: try to load peer public key from discovery (maybe handshake
        # arrived before discovery broadcast) and retry handling response.
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
        """Обработка финального сообщения handshake, регистрируем маппинг"""
        ok = self.handshake.handle_complete(data)
        if ok:
            print(f"   ✅ Маппинг зарегистрирован (HANDSHAKE_COMPLETE)")
        else:
            print(f"   ❌ Не удалось зарегистрировать маппинг")

    def _handle_secure_message(self, data: dict, addr: tuple):
        """Обработка защищённого сообщения"""
        encrypted = data['encrypted']

        # Определяем отправителя по IP
        sender = None
        for ip, info in self.discovery.get_all_peers().items():
            if ip == addr[0]:
                sender = info['username']
                break

        if not sender:
            print(f"   ❌ Неизвестный отправитель {addr[0]}")
            return

        try:
            # Расшифровываем сообщение
            decrypted = self.crypto.decrypt_message(encrypted, sender)
            print(f"\n💬 [{sender}]: {decrypted['content']}")

            # Сохраняем в историю
            msg_id = hashlib.sha256(
                f"{sender}{decrypted['timestamp']}{decrypted['content']}".encode()
            ).hexdigest()[:16]
            # Попытаемся определить локальный chat_id
            local_chat_id = None
            if sender in self.active_chats:
                local_chat_id = self.active_chats[sender]
            else:
                # Попробуем получить через crypto mapping
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
            # Здесь нужно сохранить в БД
            # self.db.add_message(...)

        except CryptoError as e:
            print(f"\n❌ Ошибка расшифровки: {e}")

    def start_chat(self, peer_name: str) -> bool:
        """Начать чат с пиром"""
        print(f"\n🔐 Начинаем чат с {peer_name}...")

        # Ищем пира
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"❌ Пир {peer_name} не найден")
            return False

        ip, info = peer
        print(f"   IP: {ip}")
        print(f"   Device ID: {info['device_id']}")

        # Создаём handshake сообщение
        handshake_msg = self.handshake.initiate(
            peer_name, ip, info['device_id']
        )

        # Отправляем
        if self.connection.send_to_peer(ip, handshake_msg):
            print(f"   ✅ Handshake отправлен")
            return True
        else:
            print(f"   ❌ {peer_name} не отвечает")
            return False

    def send_message(self, peer_name: str, text: str) -> bool:
        """Отправить сообщение"""
        if peer_name not in self.active_chats:
            print(f"❌ Нет активного чата с {peer_name}")
            return False

        local_chat_id = self.active_chats[peer_name]

        # Находим пира
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"❌ {peer_name} не в сети")
            return False

        ip, info = peer

        try:
            # Шифруем сообщение
            encrypted = self.crypto.encrypt_message(local_chat_id, text, self.username)

            # Отправляем
            message = {
                'type': MessageType.SECURE_MESSAGE,
                'encrypted': encrypted
            }

            if self.connection.send_to_peer(ip, message):
                print(f"   ✅ {peer_name}: {text}")
                # Сохраняем исходящее сообщение в БД
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

    def list_peers(self):
        """Показать активных пиров"""
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
        """Информация о пире"""
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

        # Информация о ключе
        if 'public_key' in info:
            print(f"   Публичный ключ: {info['public_key'][:50]}...")
        print("-" * 60)

    def my_info(self):
        """Информация о себе"""
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

    def cleanup(self):
        """Очистка ресурсов"""
        print("\n🧹 Очистка ресурсов...")
        self.discovery.stop()
        self.connection.stop()
        print("✅ Завершено")


class ConsoleFrontend(cmd.Cmd):
    """
    Консольный интерфейс для тестирования
    """

    intro = """
Команды:
  peers              - показать список пиров
  chat <имя>         - начать чат с пиром
  send <имя> <текст> - отправить сообщение
  info [имя]         - информация о себе или пире
  myinfo             - информация о себе
  exit               - выход

Для автодополнения используйте TAB
"""
    prompt = '> '

    def __init__(self, messenger: SecureMessenger):
        super().__init__()
        self.messenger = messenger
        self.running = True

    def do_peers(self, arg):
        """Показать список пиров"""
        self.messenger.list_peers()

    def do_chat(self, arg):
        """Начать чат с пиром: chat <имя>"""
        if not arg:
            print("❌ Укажите имя пира: chat <имя>")
            return

        self.messenger.start_chat(arg.strip())

    def do_send(self, arg):
        """Отправить сообщение: send <имя> <текст>"""
        parts = arg.split(' ', 1)
        if len(parts) < 2:
            print("❌ Использование: send <имя> <текст>")
            return

        name, text = parts
        self.messenger.send_message(name.strip(), text.strip())

    def do_info(self, arg):
        """Информация о пире: info <имя>"""
        if not arg:
            self.messenger.my_info()
        else:
            self.messenger.peer_info(arg.strip())

    def do_myinfo(self, arg):
        """Информация о себе"""
        self.messenger.my_info()

    def do_exit(self, arg):
        """Выход из программы"""
        print("👋 Завершение работы...")
        self.messenger.cleanup()
        return True

    def do_EOF(self, arg):
        """Ctrl-D для выхода"""
        return self.do_exit(arg)

    # Автодополнение
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

    # Создаём мессенджер
    messenger = SecureMessenger(username)

    # Даём время на обнаружение пиров
    print("\n⏳ Ожидание обнаружения пиров (3 сек)...")
    time.sleep(3)

    if len(sys.argv) == 2:
        # Консольный режим
        console = ConsoleFrontend(messenger)
        try:
            console.cmdloop()
        except KeyboardInterrupt:
            print("\n\n👋 Пока!")
        finally:
            messenger.cleanup()

    else:
        # Режим одной команды
        mode = sys.argv[2]

        if mode == "--peers":
            messenger.list_peers()

        elif mode == "--chat" and len(sys.argv) > 3:
            messenger.start_chat(sys.argv[3])
            time.sleep(2)  # Ждём handshake

        elif mode == "--send" and len(sys.argv) > 4:
            peer = sys.argv[3]
            text = sys.argv[4]
            messenger.send_message(peer, text)

        else:
            print("❌ Неверные аргументы")

        messenger.cleanup()


if __name__ == "__main__":
    main()