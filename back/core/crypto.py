"""
Ядро криптографической системы мессенджера.
Реализует ECDH, цифровые подписи, шифрование с аутентификацией.
"""
import secrets
import hashlib
import hmac
import struct
import base64
import time
import json
from typing import Dict, Tuple, Optional, Any

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding, hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from .secure_memory import SecureMemory
from .exceptions import CryptoError, InvalidSignatureError, ReplayAttackError


class SessionKeys:
    """
    Ключи одной сессии чата с автоматическим затиранием
    """
    def __init__(self, encrypt_key: bytes, mac_key: bytes, peer_id: str):
        self.encrypt_key = SecureMemory(32)
        self.encrypt_key.write(encrypt_key)
        self.mac_key = SecureMemory(32)
        self.mac_key.write(mac_key)
        self.created = time.time()
        self.last_used = time.time()
        self.peer_id = peer_id
        self.counter = 0


class SecureCryptoCore:
    """
    Главный криптографический класс.
    Управляет идентификационными ключами, сессиями, шифрованием.
    """

    def __init__(self, device_id: str):
        """
        Args:
            device_id: уникальный идентификатор устройства
        """
        # Идентификационные ключи (долговременные)
        self._identity_private = ec.generate_private_key(ec.SECP384R1())
        self._identity_public = self._identity_private.public_key()

        # Мастер-ключ в защищённой памяти
        self._master_key = SecureMemory(32)
        self._master_key.write(secrets.token_bytes(32))

        self.device_id = device_id
        self._session_keys: Dict[str, SessionKeys] = {}  # локальный chat_id -> ключи

        # Маппинг между локальными и удалёнными chat_id
        self._local_to_remote: Dict[str, str] = {}  # локальный -> удалённый
        self._remote_to_local: Dict[str, str] = {}  # удалённый -> локальный

        self._peer_identity_keys: Dict[str, Any] = {}  # peer_id -> public_key
        self._seen_nonces = set()

    def get_identity_public_bytes(self) -> bytes:
        """Получить публичный ключ для отправки пирам"""
        return self._identity_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

    def verify_peer_identity(self, peer_id: str, peer_public_bytes: bytes) -> bool:
        """Проверить и сохранить идентификационный ключ пира"""
        try:
            peer_public = serialization.load_der_public_key(peer_public_bytes)
            self._peer_identity_keys[peer_id] = peer_public
            return True
        except Exception as e:
            print(f"Ошибка загрузки ключа пира: {e}")
            return False

    def sign_data(self, data: bytes) -> bytes:
        """Подписать данные идентификационным ключом"""
        return self._identity_private.sign(
            data,
            ec.ECDSA(hashes.SHA256())
        )

    def verify_signature(self, data: bytes, signature: bytes, peer_id: str) -> bool:
        """Проверить подпись пира"""
        if peer_id not in self._peer_identity_keys:
            print(f"  ⚠️ Нет публичного ключа для {peer_id}")
            return False

        try:
            self._peer_identity_keys[peer_id].verify(
                signature,
                data,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except InvalidSignature as e:
            print(f"  ⚠️ Недействительная подпись: {e}")
            return False

    def create_secure_session(self, peer_id: str, peer_ephemeral_bytes: bytes,
                             peer_chat_id: Optional[str] = None) -> Tuple[str, dict]:
        """
        Создать защищённую сессию с пиром

        Args:
            peer_id: идентификатор пира
            peer_ephemeral_bytes: байты эфемерного ключа пира (DER)
            peer_chat_id: chat_id пира (если известен, например при ответе на handshake)

        Returns:
            local_chat_id: локальный идентификатор чата
            response_data: данные для ответа (публичный ключ и подпись)
        """
        # Загружаем эфемерный ключ пира
        try:
            peer_ephemeral = serialization.load_der_public_key(peer_ephemeral_bytes)
        except Exception as e:
            raise CryptoError(f"Не удалось загрузить ключ пира: {e}")

        # Генерируем свою эфемерную ключевую пару
        my_ephemeral_private = ec.generate_private_key(ec.SECP384R1())
        my_ephemeral_public = my_ephemeral_private.public_key()

        # Вычисляем общий секрет через ECDH
        shared_secret = my_ephemeral_private.exchange(ec.ECDH(), peer_ephemeral)

        # Получаем байты идентификационных ключей
        my_identity_bytes = self._identity_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        peer_identity_bytes = self._peer_identity_keys[peer_id].public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Смешиваем с идентификационными ключами для защиты от MITM
        combined = shared_secret + my_identity_bytes + peer_identity_bytes

        # Генерируем ключи сессии через HKDF
        session_key_material = HKDF(
            algorithm=hashes.SHA256(),
            length=64,  # 32 для шифрования + 32 для MAC
            salt=secrets.token_bytes(16),
            info=b'secure_chat_session',
            backend=default_backend()
        ).derive(combined)

        encrypt_key = session_key_material[:32]
        mac_key = session_key_material[32:]

        # Создаём локальный ID чата
        local_chat_id = hashlib.sha256(
            f"{self.device_id}:{peer_id}:{time.time()}:{secrets.token_hex(8)}".encode()
        ).hexdigest()[:16]

        # Сохраняем сессию
        self._session_keys[local_chat_id] = SessionKeys(encrypt_key, mac_key, peer_id)

        # Если известен chat_id пира, сохраняем маппинг
        if peer_chat_id:
            self._local_to_remote[local_chat_id] = peer_chat_id
            self._remote_to_local[peer_chat_id] = local_chat_id
            print(f"  📍 Маппинг: {local_chat_id[:8]} <-> {peer_chat_id[:8]}")

        # Получаем байты своего эфемерного ключа для ответа
        my_ephemeral_bytes = my_ephemeral_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Подписываем эти байты
        signature = self.sign_data(my_ephemeral_bytes)

        return local_chat_id, {
            'ephemeral_public': base64.b64encode(my_ephemeral_bytes).decode(),
            'signature': base64.b64encode(signature).decode(),
            'chat_id': local_chat_id  # Отправляем свой chat_id пиру
        }

    def get_session_for_message(self, chat_id: str, is_remote: bool = True) -> Optional[Tuple[str, SessionKeys]]:
        """
        Получить сессию для сообщения по ID чата

        Args:
            chat_id: ID чата из сообщения
            is_remote: True если это ID от пира, False если локальный

        Returns:
            Tuple (локальный_chat_id, сессия) или None
        """
        local_chat_id = chat_id

        if is_remote:
            # Конвертируем удалённый ID в локальный
            local_chat_id = self._remote_to_local.get(chat_id)
            if not local_chat_id:
                print(f"  ❌ Нет маппинга для удалённого chat_id {chat_id[:8]}...")
                print(f"     Доступные remote->local: {list(self._remote_to_local.keys())}")
                return None

        session = self._session_keys.get(local_chat_id)
        if not session:
            print(f"  ❌ Нет сессии для локального chat_id {local_chat_id[:8]}...")
            return None

        return local_chat_id, session

    def encrypt_message(self, local_chat_id: str, message: str, from_peer: str) -> dict:
        """
        Зашифровать сообщение с аутентификацией

        Args:
            local_chat_id: локальный ID чата
            message: текст сообщения
            from_peer: отправитель

        Returns:
            dict: зашифрованные данные
        """
        if local_chat_id not in self._session_keys:
            raise CryptoError(f"No session for local chat {local_chat_id}")

        session = self._session_keys[local_chat_id]
        session.last_used = time.time()
        session.counter += 1
        counter = session.counter

        # Генерируем nonce
        nonce = secrets.token_bytes(16)

        # Подготавливаем данные
        message_data = {
            'content': message,
            'from': from_peer,
            'timestamp': time.time(),
            'counter': counter,
            'nonce': base64.b64encode(nonce).decode()
        }

        message_json = json.dumps(message_data)

        # Шифруем
        iv = secrets.token_bytes(16)
        cipher = Cipher(
            algorithms.AES(session.encrypt_key.read()),
            modes.CBC(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()

        padder = padding.PKCS7(128).padder()
        padded = padder.update(message_json.encode()) + padder.finalize()
        ciphertext = encryptor.update(padded) + encryptor.finalize()

        # Создаём MAC
        mac_data = struct.pack('>Q', counter) + nonce + iv + ciphertext
        mac = hmac.new(
            session.mac_key.read(),
            mac_data,
            hashlib.sha256
        ).digest()

        # Получаем remote_chat_id для пира
        remote_chat_id = self._local_to_remote.get(local_chat_id)

        return {
            'local_chat_id': local_chat_id,      # для себя
            'remote_chat_id': remote_chat_id,    # для пира
            'counter': counter,
            'nonce': base64.b64encode(nonce).decode(),
            'iv': base64.b64encode(iv).decode(),
            'ciphertext': base64.b64encode(ciphertext).decode(),
            'mac': base64.b64encode(mac).decode()
        }

    def decrypt_message(self, encrypted: dict, expected_from: str) -> dict:
        """
        Расшифровать и проверить сообщение

        Args:
            encrypted: зашифрованные данные
            expected_from: ожидаемый отправитель

        Returns:
            dict: расшифрованные данные
        """
        # Определяем, какой chat_id использовать для поиска сессии
        if 'remote_chat_id' in encrypted and encrypted['remote_chat_id']:
            # Это сообщение от пира, используем его remote_chat_id для маппинга
            chat_id = encrypted['remote_chat_id']
            result = self.get_session_for_message(chat_id, is_remote=True)
            if not result:
                raise CryptoError(f"No session for remote chat {chat_id[:8]}...")
            local_chat_id, session = result
        else:
            # Старый формат - пробуем как есть
            chat_id = encrypted.get('chat_id')
            if not chat_id:
                raise CryptoError("No chat_id in message")

            session = self._session_keys.get(chat_id)
            if not session:
                raise CryptoError(f"No session for chat {chat_id[:8]}...")
            local_chat_id = chat_id

        counter = encrypted['counter']
        nonce = base64.b64decode(encrypted['nonce'])
        iv = base64.b64decode(encrypted['iv'])
        ciphertext = base64.b64decode(encrypted['ciphertext'])
        received_mac = base64.b64decode(encrypted['mac'])

        # Проверяем nonce на повтор
        nonce_key = f"{local_chat_id}:{base64.b64encode(nonce).decode()}"
        if nonce_key in self._seen_nonces:
            raise ReplayAttackError(local_chat_id, counter, nonce_key)
        self._seen_nonces.add(nonce_key)

        # Очищаем старые nonce
        if len(self._seen_nonces) > 10000:
            self._seen_nonces.clear()

        # Проверяем счётчик
        if counter <= session.counter:
            raise CryptoError(f"Invalid counter: {counter} <= {session.counter}")
        session.counter = counter

        # Проверяем MAC
        mac_data = struct.pack('>Q', counter) + nonce + iv + ciphertext
        expected_mac = hmac.new(
            session.mac_key.read(),
            mac_data,
            hashlib.sha256
        ).digest()

        if not hmac.compare_digest(expected_mac, received_mac):
            raise CryptoError("Invalid MAC - message tampered")

        # Расшифровываем
        cipher = Cipher(
            algorithms.AES(session.encrypt_key.read()),
            modes.CBC(iv),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        padded = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        data = unpadder.update(padded) + unpadder.finalize()

        message_data = json.loads(data.decode())

        # Проверяем отправителя
        if message_data['from'] != expected_from:
            raise CryptoError(f"Sender mismatch: {message_data['from']} != {expected_from}")

        session.last_used = time.time()
        return message_data

    def rotate_keys(self, chat_id: str) -> Optional[dict]:
        """Смена ключей для Perfect Forward Secrecy"""
        if chat_id not in self._session_keys:
            return None

        old_session = self._session_keys[chat_id]

        # Создаём новые ключи
        new_encrypt = secrets.token_bytes(32)
        new_mac = secrets.token_bytes(32)

        # Заменяем сессию
        self._session_keys[chat_id] = SessionKeys(new_encrypt, new_mac, old_session.peer_id)

        return {
            'type': 'key_rotation',
            'chat_id': chat_id,
            'timestamp': time.time()
        }