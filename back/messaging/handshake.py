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
        """
        Args:
            crypto: экземпляр криптоядра
            username: имя текущего пользователя
        """
        self.crypto = crypto
        self.username = username
        self.pending_handshakes: Dict[str, dict] = {}  # nonce -> handshake_data

    def initiate(self, peer_name: str, peer_ip: str, peer_device_id: str) -> dict:
        """
        Инициировать handshake с пиром

        Args:
            peer_name: имя пира
            peer_ip: IP пира
            peer_device_id: device_id пира

        Returns:
            dict: сообщение для отправки
        """
        # Генерируем эфемерную ключевую пару
        ephemeral_private = ec.generate_private_key(ec.SECP384R1())
        ephemeral_public = ephemeral_private.public_key()

        # Получаем байты ключа в DER формате
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
            'ephemeral_public_bytes': key_bytes,
            'timestamp': time.time()
        }

        print(f"  🔐 Инициируем handshake с {peer_name}, nonce={nonce[:8]}...")

        return {
            'type': MessageType.HANDSHAKE_INIT,
            'nonce': nonce,
            'from': self.username,
            'device_id': self.crypto.device_id,
            'ephemeral_public': base64.b64encode(key_bytes).decode(),
            'signature': base64.b64encode(signature).decode()
        }

    def handle_initiation(self, data: dict, addr: tuple) -> Optional[dict]:
        """
        Обработать входящий handshake

        Args:
            data: данные запроса
            addr: адрес отправителя

        Returns:
            Optional[dict]: ответное сообщение или None при ошибке
        """
        peer_name = data['from']
        peer_device = data['device_id']
        nonce = data['nonce']

        # Получаем байты ключа пира
        peer_ephemeral_bytes = base64.b64decode(data['ephemeral_public'])
        signature = base64.b64decode(data['signature'])

        print(f"  📥 Получен handshake от {peer_name}, nonce={nonce[:8]}...")

        # Проверяем подпись на байтах ключа
        if not self.crypto.verify_signature(peer_ephemeral_bytes, signature, peer_device):
            print(f"  ❌ Недействительная подпись от {peer_name}")
            return None

        print(f"  ✅ Подпись пира {peer_name} верна")

        # ВАЖНО: Создаём сессию, НО мы ещё не знаем chat_id пира
        # Поэтому peer_chat_id=None, маппинг будет создан позже
        local_chat_id, response_data = self.crypto.create_secure_session(
            peer_device,
            peer_ephemeral_bytes,
            peer_chat_id=None  # Пока не знаем chat_id пира
        )

        print(f"  ✅ Создана локальная сессия {local_chat_id[:8]}...")

        # ВАЖНО: Сохраняем информацию о том, что мы ответили на handshake
        # Это нужно для связи с отправителем
        self.pending_handshakes[nonce] = {
            'peer_name': peer_name,
            'peer_device': peer_device,
            'local_chat_id': local_chat_id,
            'timestamp': time.time()
        }

        # Формируем ответ
        response = {
            'type': MessageType.HANDSHAKE_RESPONSE,
            'nonce': nonce,
            'from': self.username,
            'device_id': self.crypto.device_id,
            'chat_id': local_chat_id,  # Отправляем свой chat_id пиру
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
            (успех, локальный chat_id)
        """
        nonce = data['nonce']
        peer_name = data['from']
        peer_device = data['device_id']
        peer_chat_id = data['chat_id']  # Это chat_id пира!
        peer_ephemeral_bytes = base64.b64decode(data['ephemeral_public'])
        signature = base64.b64decode(data['signature'])

        print(f"  📥 Получен ответ на handshake от {peer_name}, nonce={nonce[:8]}...")
        print(f"     Пир прислал свой chat_id: {peer_chat_id[:8]}...")

        # Проверяем, есть ли ожидающий handshake
        if nonce not in self.pending_handshakes:
            print(f"  ❌ Нет ожидающего handshake с nonce {nonce[:8]}...")
            return False, None

        handshake_data = self.pending_handshakes[nonce]

        # Проверяем подпись на байтах ключа
        if not self.crypto.verify_signature(peer_ephemeral_bytes, signature, peer_device):
            print(f"  ❌ Недействительная подпись в handshake response от {peer_name}")
            return False, None

        print(f"  ✅ Подпись пира {peer_name} верна")

        # ВАЖНО: Завершаем создание сессии и ПЕРЕДАЁМ peer_chat_id для маппинга!
        local_chat_id, _ = self.crypto.create_secure_session(
            peer_device,
            peer_ephemeral_bytes,
            peer_chat_id=peer_chat_id  # Теперь мы знаем chat_id пира!
        )

        print(f"  ✅ Создана локальная сессия {local_chat_id[:8]}...")
        print(f"  📍 Маппинг: local={local_chat_id[:8]} <-> remote={peer_chat_id[:8]}")

        # Очищаем pending
        del self.pending_handshakes[nonce]

        return True, local_chat_id

    def cleanup_old(self, max_age: float = 30.0):
        """Очистка старых handshake"""
        now = time.time()
        to_delete = [
            nonce for nonce, data in self.pending_handshakes.items()
            if now - data['timestamp'] > max_age
        ]
        for nonce in to_delete:
            print(f"  🧹 Очистка старого handshake {nonce[:8]}...")
            del self.pending_handshakes[nonce]