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

    def __init__(self, crypto: SecureCryptoCore):
        self.crypto = crypto
        self.pending_handshakes: Dict[str, dict] = {}  # nonce -> handshake_data

    def initiate(self, peer_name: str, peer_ip: str, peer_device_id: str) -> dict:
        """
        Инициировать handshake с пиром
        """
        # Генерируем эфемерную ключевую пару
        ephemeral_private = ec.generate_private_key(ec.SECP384R1())
        ephemeral_public = ephemeral_private.public_key()

        # Генерируем nonce
        nonce = secrets.token_hex(8)

        # Создаём handshake сообщение
        handshake = {
            'type': MessageType.HANDSHAKE_INIT,
            'nonce': nonce,
            'from': peer_name,
            'device_id': peer_device_id,
            'ephemeral_public': base64.b64encode(
                ephemeral_public.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                )
            ).decode(),
            'signature': base64.b64encode(
                self.crypto.sign_data(ephemeral_public.public_bytes(
                    encoding=serialization.Encoding.DER,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo
                ))
            ).decode()
        }

        # Сохраняем для завершения handshake
        self.pending_handshakes[nonce] = {
            'peer': peer_name,
            'peer_ip': peer_ip,
            'ephemeral_private': ephemeral_private,
            'timestamp': time.time()
        }

        return handshake

    def handle_initiation(self, data: dict, addr: tuple) -> Optional[dict]:
        """
        Обработать входящий handshake

        Returns:
            Optional[dict]: ответное сообщение или None при ошибке
        """
        peer_name = data['from']
        peer_device = data['device_id']
        nonce = data['nonce']
        peer_ephemeral = base64.b64decode(data['ephemeral_public'])
        signature = base64.b64decode(data['signature'])

        # Проверяем подпись
        if not self.crypto.verify_signature(peer_ephemeral, signature, peer_device):
            print(f"Недействительная подпись от {peer_name}")
            return None

        # Создаём сессию
        chat_id, response_data = self.crypto.create_secure_session(
            peer_device,
            peer_ephemeral
        )

        # Формируем ответ
        response = {
            'type': MessageType.HANDSHAKE_RESPONSE,
            'nonce': nonce,
            'from': peer_name,
            'device_id': peer_device,
            'chat_id': chat_id,
            'ephemeral_public': response_data['ephemeral_public'],
            'signature': response_data['signature']
        }

        return response

    def handle_response(self, data: dict) -> Tuple[bool, Optional[str]]:
        """
        Обработать ответ на handshake

        Returns:
            (успех, chat_id)
        """
        nonce = data['nonce']
        peer_name = data['from']
        peer_device = data['device_id']
        chat_id = data['chat_id']
        peer_ephemeral = base64.b64decode(data['ephemeral_public'])
        signature = base64.b64decode(data['signature'])

        if nonce not in self.pending_handshakes:
            return False, None

        handshake_data = self.pending_handshakes[nonce]

        # Проверяем подпись
        if not self.crypto.verify_signature(peer_ephemeral, signature, peer_device):
            print(f"Недействительная подпись в handshake response")
            return False, None

        # Завершаем создание сессии
        self.crypto.create_secure_session(peer_device, peer_ephemeral)

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
            del self.pending_handshakes[nonce]