"""
Secure P2P Messenger
Главный файл - объединяет все модули
"""
import sys
import time
import hashlib
import socket
import json
import base64

from core.crypto import SecureCryptoCore
from core.exceptions import CryptoError

from network.discovery import PeerDiscovery
from network.connection import ConnectionManager
from network.protocols import MessageType

from storage.database import SecureDatabase

from messaging.handshake import HandshakeManager

from api import LocalAPI


class SecureMessenger:
    """
    Главный класс приложения
    """
    def __init__(self, username: str):
        self.username = username
        self.device_id = hashlib.sha256(
            f"{username}{socket.gethostname()}".encode()
        ).hexdigest()[:16]

        print(f"[*] Инициализация криптографического ядра...")
        self.crypto = SecureCryptoCore(self.device_id)

        print(f"[*] Подготовка публичного ключа...")
        pub_key_b64 = base64.b64encode(
            self.crypto.get_identity_public_bytes()
        ).decode()

        print(f"[*] Запуск обнаружения пиров...")
        self.discovery = PeerDiscovery(username, self.device_id, pub_key_b64)
        self.discovery.on_peer_found = self._on_peer_found
        self.discovery.start()

        print(f"[*] Запуск менеджера соединений...")
        self.connection = ConnectionManager()
        self.connection.start(self._on_message)

        print(f"[*] Инициализация базы данных...")
        self.db = SecureDatabase()

        print(f"[*] Подготовка handshake-менеджера...")
        self.handshake = HandshakeManager(self.crypto, self.username)

        # Активные чаты: peer_name -> chat_id
        self.active_chats = {}

        print(f"\n✅ {username} готов к работе!\n")

    def _on_peer_found(self, ip: str, info: dict):
        """Колбэк при обнаружении нового пира"""
        print(f"\n[+] Найден пир: {info['username']} ({ip})")

        # Сохраняем публичный ключ
        if info.get('public_key'):
            self.crypto.verify_peer_identity(
                info['device_id'],
                base64.b64decode(info['public_key'])
            )

    def _on_message(self, data: dict, addr: tuple):
        """Колбэк при получении сообщения"""
        msg_type = data.get('type')

        try:
            if msg_type == MessageType.HANDSHAKE_INIT:
                self._handle_handshake_init(data, addr)
            elif msg_type == MessageType.HANDSHAKE_RESPONSE:
                self._handle_handshake_response(data, addr)
            elif msg_type == MessageType.SECURE_MESSAGE:
                self._handle_secure_message(data, addr)
            else:
                print(f"\n[?] Неизвестный тип сообщения: {msg_type}")
        except Exception as e:
            print(f"\n[!] Ошибка обработки сообщения: {e}")

    def _handle_handshake_init(self, data: dict, addr: tuple):
        """Обработка handshake инициации"""
        response = self.handshake.handle_initiation(data, addr)
        if response:
            self.connection.send_to_peer(addr[0], response)

    def _handle_handshake_response(self, data: dict, addr: tuple):
        """Обработка ответа на handshake"""
        success, chat_id = self.handshake.handle_response(data)
        if success:
            peer_name = data['from']
            self.active_chats[peer_name] = chat_id
            print(f"\n[✓] Защищённый канал с {peer_name} установлен!")

    def _handle_secure_message(self, data: dict, addr: tuple):
        """Обработка защищённого сообщения"""
        encrypted = data['encrypted']
        chat_id =  data['chat_id']

        # Определяем отправителя
        sender = None
        for ip, info in self.discovery.get_all_peers().items():
            if ip == addr[0]:
                sender = info['username']
                break

        if not sender:
            print(f"[!] Неизвестный отправитель {addr[0]}")
            return

        try:
            # Расшифровываем - функция сама найдёт правильную сессию
            decrypted = self.crypto.decrypt_message(encrypted, sender)
            print(f"\n[{sender}]: {decrypted['content']}")

            # Сохраняем в историю
            self.db.add_message(
                decrypted.get('msg_id', 'unknown'),
                chat_id,
                sender,
                json.dumps(encrypted).encode(),
                'incoming'
            )

        except CryptoError as e:
            print(f"\n[!] Ошибка расшифровки: {e}")

    def start_chat(self, peer_name: str):
        """Начать чат с пиром"""
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"[-] Пир {peer_name} не найден")
            return False

        ip, info = peer

        handshake_msg = self.handshake.initiate(
            peer_name, ip, info['device_id']
        )

        if self.connection.send_to_peer(ip, handshake_msg):
            print(f"[*] Устанавливаем соединение с {peer_name}...")
            return True
        else:
            print(f"[-] {peer_name} не отвечает")
            return False

    def send_message(self, peer_name: str, text: str) -> bool:
        """Отправить сообщение"""
        if peer_name not in self.active_chats:
            print(f"[-] Нет активного чата с {peer_name}")
            return False

        local_chat_id = self.active_chats[peer_name]  # Это локальный chat_id

        # Находим пира
        peer = self.discovery.get_peer_by_name(peer_name)
        if not peer:
            print(f"[-] {peer_name} не в сети")
            return False

        ip, info = peer

        # Шифруем сообщение (используем локальный chat_id)
        encrypted = self.crypto.encrypt_message(local_chat_id, text, self.username)

        # Отправляем пиру
        message = {
            'type': MessageType.SECURE_MESSAGE,
            'encrypted': encrypted  # В encrypted уже есть remote_chat_id для пира
        }

        if self.connection.send_to_peer(ip, message):
            print(f"[→] {peer_name}: {text}")
            return True
        return False

    def list_peers(self):
        """Показать активных пиров"""
        peers = self.discovery.get_all_peers()
        if not peers:
            print("[-] Нет активных пиров")
            return

        print("\nАктивные пиры:")
        for ip, info in peers.items():
            age = time.time() - info['last_seen']
            if age < 30:
                status = "🟢"
            elif age < 120:
                status = "🟡"
            else:
                status = "⚫"

            chat_status = "💬" if info['username'] in self.active_chats else ""
            print(f"  {status} {info['username']} {chat_status} ({ip})")

    def run(self):
        """Запуск командного интерфейса"""
        print("Команды:")
        print("  /list           - показать пиров")
        print("  /chat <имя>     - начать чат")
        print("  /send <имя> <т> - отправить сообщение")
        print("  /exit           - выход")

        while True:
            try:
                cmd = input("\n> ").strip()

                if cmd == "/list":
                    self.list_peers()

                elif cmd.startswith("/chat "):
                    name = cmd[6:].strip()
                    self.start_chat(name)

                elif cmd.startswith("/send "):
                    parts = cmd.split(" ", 2)
                    if len(parts) < 3:
                        print("Использование: /send <имя> <текст>")
                        continue
                    _, name, text = parts
                    self.send_message(name, text)

                elif cmd == "/exit":
                    break

                elif cmd:
                    print("Неизвестная команда")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Ошибка: {e}")

        self.cleanup()

    def cleanup(self):
        """Очистка ресурсов"""
        print("\n[*] Завершение работы...")
        self.discovery.stop()
        self.connection.stop()


def main():
    if len(sys.argv) < 2:
        print("Использование: python main.py <имя_пользователя>")
        sys.exit(1)

    messenger = SecureMessenger(sys.argv[1])
    messenger.run()


if __name__ == "__main__":
    main()