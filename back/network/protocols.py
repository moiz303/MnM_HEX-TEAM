"""
Протоколы обмена: порты, типы сообщений, форматы, схемы валидации.
Централизованное описание всех сетевых констант и структур данных.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


# ====================== СЕТЕВЫЕ ПОРТЫ ======================

BROADCAST_PORT = 37020  # UDP для обнаружения пиров
MESSAGE_PORT = 37021    # TCP для основных сообщений
DHT_PORT = 37022        # TCP для DHT
FILE_TRANSFER_PORT = 37023  # TCP для передачи файлов
CALL_SIGNALING_PORT = 37024  # TCP для сигнализации звонков


# ====================== ТИПЫ СООБЩЕНИЙ ======================

class MessageType(str, Enum):
    """Все возможные типы сообщений в системе."""
    # Обнаружение пиров (UDP broadcast)
    PRESENCE = "presence"
    PRESENCE_RESPONSE = "presence_response"

    # Установка защищённого соединения
    HANDSHAKE_INIT = "handshake_init"
    HANDSHAKE_RESPONSE = "handshake_response"
    HANDSHAKE_COMPLETE = "handshake_complete"
    HANDSHAKE_REJECT = "handshake_reject"

    # Основные сообщения
    SECURE_MESSAGE = "secure_message"
    DELIVERY_RECEIPT = "delivery_receipt"
    MESSAGE_READ = "message_read"
    TYPING_NOTIFICATION = "typing"

    # Управление ключами
    KEY_ROTATION = "key_rotation"
    KEY_ROTATION_ACK = "key_rotation_ack"

    # Маршрутизация (Onion)
    RELAY = "relay"
    RELAY_ERROR = "relay_error"
    CIRCUIT_CREATE = "circuit_create"
    CIRCUIT_CREATED = "circuit_created"

    # Файлы
    FILE_OFFER = "file_offer"
    FILE_ACCEPT = "file_accept"
    FILE_REJECT = "file_reject"
    FILE_CHUNK = "file_chunk"
    FILE_COMPLETE = "file_complete"
    FILE_ERROR = "file_error"

    # Звонки (задел)
    CALL_OFFER = "call_offer"
    CALL_ANSWER = "call_answer"
    CALL_ICE_CANDIDATE = "call_ice"
    CALL_HANGUP = "call_hangup"
    CALL_MUTE = "call_mute"

    # DHT операции
    DHT_FIND_NODE = "dht_find_node"
    DHT_FOUND_NODE = "dht_found_node"
    DHT_STORE = "dht_store"
    DHT_STORED = "dht_stored"
    DHT_FIND_VALUE = "dht_find_value"
    DHT_FOUND_VALUE = "dht_found_value"

    # Системные
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    BYE = "bye"


# ====================== РАЗМЕРЫ И ЛИМИТЫ ======================

class Limits:
    """Ограничения на размеры данных"""
    MAX_MESSAGE_SIZE = 64 * 1024  # 64KB
    MAX_ENCRYPTED_SIZE = 68 * 1024  # 68KB
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_FILE_CHUNK = 32 * 1024  # 32KB
    MAX_FILENAME_LENGTH = 255
    MAX_HOPS = 5
    MAX_PEERS_IN_BUCKET = 20
    MAX_CIRCUITS = 10
    MAX_NONCE_AGE = 3600
    MAX_SESSION_AGE = 24 * 3600
    MAX_OFFLINE_ATTEMPTS = 10
    MAX_OFFLINE_QUEUE = 1000


@dataclass
class RelayLimits:
    """Лимиты для режима Mesh-by-Default"""
    MAX_HOPS = 2
    MAX_BANDWIDTH_KBPS = 50
    CIRCUIT_TIMEOUT_SEC = 60
    CLEANUP_INTERVAL_SEC = 30
    HEARTBEAT_INTERVAL_SEC = 10
    MAX_PENDING_CIRCUITS = 10


# ====================== ТАЙМАУТЫ ======================

class Timeouts:
    """Таймауты для различных операций (в секундах)"""
    CONNECTION = 5.0
    READ = 30.0
    WRITE = 10.0
    BROADCAST = 1.0
    UDP_RECV = 1.0
    HANDSHAKE = 10.0
    DELIVERY_RECEIPT = 5.0
    PING_INTERVAL = 30.0
    PEER_TIMEOUT = 120.0
    PEER_CLEANUP = 60.0
    DHT_QUERY = 3.0
    DHT_REPLICATE = 3600.0


# ====================== ИНТЕРВАЛЫ ======================

class Intervals:
    """Интервалы для периодических операций"""
    PRESENCE_BROADCAST = 5.0
    DHT_BROADCAST = 30.0
    OFFLINE_RETRY = 30.0
    OFFLINE_BACKOFF = [30, 60, 120, 300, 600]
    KEY_ROTATION = 3600.0
    NONCE_CLEANUP = 300.0
    STATS_UPDATE = 60.0


# ====================== СТАТУСЫ ======================

class PeerStatus(str, Enum):
    ONLINE = "online"
    AWAY = "away"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class MessageStatus(str, Enum):
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    PENDING = "pending"


class CircuitStatus(str, Enum):
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


# ====================== СХЕМЫ СООБЩЕНИЙ ======================

class MessageSchemas:
    """Схемы валидации для всех типов сообщений."""
    BASE = {
        "type": str,
        "timestamp": float,
        "msg_id": str
    }

    PRESENCE = {**BASE, "type": MessageType.PRESENCE, "username": str, "device_id": str, "public_key": str, "port": int, "capabilities": list}
    PRESENCE_RESPONSE = {**BASE, "type": MessageType.PRESENCE_RESPONSE, "username": str, "device_id": str, "public_key": str}
    HANDSHAKE_INIT = {**BASE, "type": MessageType.HANDSHAKE_INIT, "nonce": str, "from": str, "device_id": str, "ephemeral_public": str, "signature": str}
    HANDSHAKE_RESPONSE = {**BASE, "type": MessageType.HANDSHAKE_RESPONSE, "nonce": str, "from": str, "device_id": str, "chat_id": str, "ephemeral_public": str, "signature": str}
    HANDSHAKE_REJECT = {**BASE, "type": MessageType.HANDSHAKE_REJECT, "nonce": str, "reason": str}
    SECURE_MESSAGE = {**BASE, "type": MessageType.SECURE_MESSAGE, "chat_id": str, "encrypted": dict}
    DELIVERY_RECEIPT = {**BASE, "type": MessageType.DELIVERY_RECEIPT, "chat_id": str, "in_response_to": str, "status": MessageStatus}
    RELAY = {**BASE, "type": MessageType.RELAY, "circuit_id": str, "layer": dict}
    FILE_OFFER = {**BASE, "type": MessageType.FILE_OFFER, "chat_id": str, "file_id": str, "filename": str, "size": int, "mime_type": str, "encrypted_metadata": str}
    FILE_ACCEPT = {**BASE, "type": MessageType.FILE_ACCEPT, "chat_id": str, "file_id": str, "port": int}
    FILE_CHUNK = {**BASE, "type": MessageType.FILE_CHUNK, "file_id": str, "chunk_index": int, "total_chunks": int, "data": str, "checksum": str}
    PING = {**BASE, "type": MessageType.PING}
    PONG = {**BASE, "type": MessageType.PONG, "in_response_to": str}
    ERROR = {**BASE, "type": MessageType.ERROR, "in_response_to": str, "error_code": int, "error_message": str}
    BYE = {**BASE, "type": MessageType.BYE, "reason": str}


@dataclass
class PeerInfo:
    """Информация о пире"""
    username: str
    device_id: str
    ip: str
    port: int
    public_key: Optional[bytes]
    last_seen: float
    status: PeerStatus
    capabilities: list
    rtt: Optional[float]


@dataclass
class ChatSession:
    """Информация о сессии чата"""
    chat_id: str
    peer_id: str
    peer_name: str
    created: float
    last_activity: float
    message_count: int
    is_active: bool


@dataclass
class QueuedMessage:
    """Сообщение в оффлайн-очереди"""
    queue_id: int
    chat_id: str
    peer_name: str
    message_data: dict
    attempts: int
    last_attempt: float
    created: float


class ErrorCodes:
    """Коды ошибок для системных сообщений"""
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    INTERNAL_ERROR = 2
    NOT_IMPLEMENTED = 3
    PEER_UNREACHABLE = 100
    CONNECTION_TIMEOUT = 101
    CONNECTION_REFUSED = 102
    NETWORK_UNREACHABLE = 103
    INVALID_MESSAGE_TYPE = 200
    MALFORMED_MESSAGE = 201
    UNSUPPORTED_VERSION = 202
    RATE_LIMITED = 203
    HANDSHAKE_FAILED = 300
    INVALID_SIGNATURE = 301
    DECRYPTION_FAILED = 302
    INTEGRITY_VIOLATION = 303
    REPLAY_ATTACK = 304
    KEY_EXPIRED = 305
    SESSION_NOT_FOUND = 306
    UNAUTHORIZED = 400
    FORBIDDEN = 401
    PEER_REJECTED = 402
    FILE_TOO_LARGE = 500
    INVALID_CHUNK = 501
    CHECKSUM_MISMATCH = 502
    INSUFFICIENT_SPACE = 503
    NODE_NOT_FOUND = 600
    VALUE_NOT_FOUND = 601
    STORE_FAILED = 602

    MESSAGES = {
        SUCCESS: "Success",
        UNKNOWN_ERROR: "Unknown error",
        PEER_UNREACHABLE: "Peer is unreachable",
        HANDSHAKE_FAILED: "Handshake failed",
        INVALID_SIGNATURE: "Invalid signature",
        REPLAY_ATTACK: "Replay attack detected",
        SESSION_NOT_FOUND: "Session not found"
    }

    @classmethod
    def get_message(cls, code: int) -> str:
        return cls.MESSAGES.get(code, f"Unknown error code: {code}")


def validate_message(message: Dict[str, Any]) -> tuple:
    """Проверить сообщение на соответствие схеме."""
    if 'type' not in message:
        return False, "Missing 'type' field"
    msg_type = message['type']
    schema_name = msg_type.upper()
    if not hasattr(MessageSchemas, schema_name):
        return False, f"Unknown message type: {msg_type}"
    schema = getattr(MessageSchemas, schema_name)
    for field, field_type in schema.items():
        if field not in message:
            return False, f"Missing required field: {field}"
        if field_type not in (str, int, float, bool, list, dict, type(None)):
            continue
        if not isinstance(message[field], field_type):
            return False, f"Field {field} should be {field_type.__name__}"
    return True, None


def create_message(msg_type: MessageType, **kwargs) -> Dict[str, Any]:
    """Создать сообщение с правильной структурой."""
    import secrets
    import time
    message = {
        "type": msg_type.value if isinstance(msg_type, Enum) else msg_type,
        "msg_id": secrets.token_hex(8),
        "timestamp": time.time(),
        **kwargs
    }
    return message


class AppConfig:
    """Глобальная конфигурация приложения"""
    DEBUG = False
    DB_PATH = "secure_chat.db"
    LOG_PATH = "chat.log"
    MAX_CONNECTIONS = 50
    BUFFER_SIZE = 65536
    ENFORCE_ENCRYPTION = True
    AUTO_ROTATE_KEYS = True
    REJECT_SELF_SIGNED = False
    ENABLE_FILE_TRANSFER = True
    ENABLE_CALLS = False
    ENABLE_ONION_ROUTING = True

    @classmethod
    def from_env(cls):
        import os
        if os.getenv("CHAT_DEBUG"):
            cls.DEBUG = True
        if os.getenv("CHAT_DB_PATH"):
            cls.DB_PATH = os.getenv("CHAT_DB_PATH")
        return cls