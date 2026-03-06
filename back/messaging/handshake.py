"""
Протокол установки защищённого соединения (handshake)
"""
import secrets
import base64
import time
from typing import Dict, Optional, Tuple

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

from back.core.crypto import SecureCryptoCore
from back.network.protocols import MessageType


class HandshakeManager:
    """
    Управление handshake-протоколом
    """

    def __init__(self, crypto: SecureCryptoCore, username: str):
        self.crypto = crypto
        self.username = username  # Добавляем имя пользователя
        self.pending_handshakes: Dict[str, dict] = {}  # nonce -> handshake_data

    def initiate(self, peer_name: str, peer_ip: str, peer_device_id: str) -> dict:
        """
        Инициировать handshake с пиром
        """
        # Генерируем эфемерную ключевую пару
        ephemeral_private = ec.generate_private_key(ec.SECP384R1())
        ephemeral_public = ephemeral_private.public_key()

        # Получаем байты ключа в DER формате (для подписи и передачи)
        key_bytes = ephemeral_public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        # Подписываем байты ключа
        signature = self.crypto.sign_data(key_bytes)

        nonce = secrets.token_hex(8)

        # Сохраняем для завершения handshake
        self.pending_handshakes[nonce] = {
            'peer_name': peer_name,
            'peer_ip': peer_ip,
            'peer_device_id': peer_device_id,
            'ephemeral_private': ephemeral_private,
            'ephemeral_public_bytes': key_bytes,  # Сохраняем байты для проверки
            'timestamp': time.time()
        }

        return {
            'type': MessageType.HANDSHAKE_INIT,
            'nonce': nonce,
            'from': self.username,  # Было peer_name, должно быть self.username!
            'device_id': self.crypto.device_id,  # Свой device_id!
            'ephemeral_public': base64.b64encode(key_bytes).decode(),
            'signature': base64.b64encode(signature).decode()
        }

    def handle_initiation(self, data: dict, addr: tuple) -> Optional[dict]:
        """
        Обработать входящий handshake
        """
        peer_name = data['from']
        peer_device = data['device_id']
        nonce = data['nonce']

        # Получаем байты ключа пира
        peer_ephemeral_bytes = base64.b64decode(data['ephemeral_public'])
        signature = base64.b64decode(data['signature'])

        # Проверяем подпись на байтах ключа
        if not self.crypto.verify_signature(peer_ephemeral_bytes, signature, peer_device):
            print(f"❌ Недействительная подпись от {peer_name}")
            return None

        # ВАЖНО: создаём сессию, передавая байты ключа (не объект!)
        # Функция create_secure_session сама загрузит ключ через load_der_public_key
        chat_id, response_data = self.crypto.create_secure_session(
            peer_device,
            peer_ephemeral_bytes  # Передаём байты, а не объект!
        )

        # Формируем ответ
        response = {
            'type': MessageType.HANDSHAKE_RESPONSE,
            'nonce': nonce,
            'from': self.username,
            'device_id': self.crypto.device_id,
            'chat_id': chat_id,
            'ephemeral_public': response_data['ephemeral_public'],
            'signature': response_data['signature']
        }

        return response

    def handle_response(self, data: dict) -> Tuple[bool, Optional[str]]:
        """
        Обработать ответ на handshake

        Args:
            data: данные ответа

        Returns:
            (успех, chat_id)
        """
        nonce = data['nonce']
        peer_name = data['from']
        peer_device = data['device_id']
        chat_id = data['chat_id']

        # Получаем байты ключа пира из ответа
        peer_ephemeral_bytes = base64.b64decode(data['ephemeral_public'])
        signature = base64.b64decode(data['signature'])

        # Проверяем, есть ли ожидающий handshake
        if nonce not in self.pending_handshakes:
            print(f"❌ Нет ожидающего handshake с nonce {nonce}")
            return False, None

        handshake_data = self.pending_handshakes[nonce]

        # Проверяем подпись на байтах ключа
        if not self.crypto.verify_signature(peer_ephemeral_bytes, signature, peer_device):
            print(f"❌ Недействительная подпись в handshake response от {peer_name}")
            return False, None

        # ВАЖНО: завершаем создание сессии, получая те же данные, что и в initiate
        # Но теперь мы - инициатор, поэтому нам не нужны response_data
        self.crypto.create_secure_session(
            peer_device,
            peer_ephemeral_bytes  # Передаём байты ключа пира
        )

        # Очищаем pending
        del self.pending_handshakes[nonce]

        return True, chat_id

    def cleanup_old(self, max_age: float = 30.0):
        """Очистка старых handshake"""
        now = time.time()
        to_delete = [
            nonce for nonce, data in self.pending_handshakes.items()
            if now - data['timestamp'] > max_age
        ]
        for nonce in to_delete:
            print(f"🧹 Очистка старого handshake {nonce}")
            del self.pending_handshakes[nonce]