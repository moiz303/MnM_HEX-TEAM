"""
Протоколы обмена: порты, типы сообщений, форматы, схемы валидации.
Централизованное описание всех сетевых констант и структур данных.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


# ====================== СЕТЕВЫЕ ПОРТЫ ======================

# Все порты в диапазоне 37020-37029 зарезервированы для приложения
BROADCAST_PORT = 37020  # UDP для обнаружения пиров
MESSAGE_PORT = 37021    # TCP для основных сообщений
DHT_PORT = 37022        # TCP для DHT (задел на будущее)
FILE_TRANSFER_PORT = 37023  # TCP для передачи файлов (задел)
CALL_SIGNALING_PORT = 37024  # TCP для сигнализации звонков (задел)


# ====================== ТИПЫ СООБЩЕНИЙ ======================

class MessageType(str, Enum):
    """
    Все возможные типы сообщений в системе.
    Используем str-наследование для удобной сериализации в JSON.
    """
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

    # Максимальные размеры сообщений
    MAX_MESSAGE_SIZE = 64 * 1024  # 64KB
    MAX_ENCRYPTED_SIZE = 68 * 1024  # 68KB (с учётом overhead)

    # Файлы
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_FILE_CHUNK = 32 * 1024  # 32KB
    MAX_FILENAME_LENGTH = 255

    # Сеть
    MAX_HOPS = 5  # Максимальная длина луковой цепи
    MAX_PEERS_IN_BUCKET = 20  # Для DHT
    MAX_CIRCUITS = 10  # Максимум одновременных цепей

    # Криптография
    MAX_NONCE_AGE = 3600  # 1 час - хранить nonce для защиты от replay
    MAX_SESSION_AGE = 24 * 3600  # 24 часа - максимальное время жизни сессии

    # Очереди
    MAX_OFFLINE_ATTEMPTS = 10  # Максимум попыток оффлайн-доставки
    MAX_OFFLINE_QUEUE = 1000  # Максимум сообщений в очереди

# ====================== ТАЙМАУТЫ ======================

class Timeouts:
    """Таймауты для различных операций (в секундах)"""

    # Соединения
    CONNECTION = 5.0  # Таймаут установки TCP соединения
    READ = 30.0  # Таймаут чтения данных
    WRITE = 10.0  # Таймаут записи данных

    # Сокеты
    BROADCAST = 1.0  # Таймаут broadcast сокета
    UDP_RECV = 1.0  # Таймаут приёма UDP

    # Протоколы
    HANDSHAKE = 10.0  # Максимальное время handshake
    DELIVERY_RECEIPT = 5.0  # Ожидание подтверждения доставки
    PING_INTERVAL = 30.0  # Интервал ping'а

    # Пиры
    PEER_TIMEOUT = 120.0  # Считать пира оффлайн через 2 минуты
    PEER_CLEANUP = 60.0  # Проверять пиров каждую минуту

    # DHT
    DHT_QUERY = 3.0  # Таймаут DHT запроса
    DHT_REPLICATE = 3600.0  # Репликация DHT каждый час


# ====================== ИНТЕРВАЛЫ ======================

class Intervals:
    """Интервалы для периодических операций"""

    # Рассылки
    PRESENCE_BROADCAST = 5.0  # Рассылать присутствие каждые 5 сек
    DHT_BROADCAST = 30.0  # Рассылать DHT информацию

    # Очереди
    OFFLINE_RETRY = 30.0  # Проверять оффлайн-очередь каждые 30 сек
    OFFLINE_BACKOFF = [30, 60, 120, 300, 600]  # Экспоненциальная задержка

    # Криптография
    KEY_ROTATION = 3600.0  # Менять ключи каждый час
    NONCE_CLEANUP = 300.0  # Очищать старые nonce каждые 5 минут

    # Статистика
    STATS_UPDATE = 60.0  # Обновлять статистику раз в минуту


# ====================== СТАТУСЫ ======================

class PeerStatus(str, Enum):
    """Статус пира в сети"""
    ONLINE = "online"
    AWAY = "away"  # Недавно был, но молчит
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class MessageStatus(str, Enum):
    """Статус доставки сообщения"""
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    PENDING = "pending"  # В оффлайн-очереди


class CircuitStatus(str, Enum):
    """Статус луковой цепи"""
    BUILDING = "building"
    READY = "ready"
    FAILED = "failed"
    EXPIRED = "expired"


# ====================== СХЕМЫ СООБЩЕНИЙ ======================

class MessageSchemas:
    """
    Схемы валидации для всех типов сообщений.
    Каждая схема определяет обязательные поля и их типы.
    """

    # Базовая структура всех сообщений
    BASE = {
        "type": str,  # MessageType
        "timestamp": float,  # Время отправки
        "msg_id": str  # Уникальный ID сообщения
    }

    # Обнаружение пиров
    PRESENCE = {
        **BASE,
        "type": MessageType.PRESENCE,
        "username": str,
        "device_id": str,
        "public_key": str,  # base64
        "port": int,
        "capabilities": list  # [file_transfer, calls, etc]
    }

    PRESENCE_RESPONSE = {
        **BASE,
        "type": MessageType.PRESENCE_RESPONSE,
        "username": str,
        "device_id": str,
        "public_key": str
    }

    # Handshake
    HANDSHAKE_INIT = {
        **BASE,
        "type": MessageType.HANDSHAKE_INIT,
        "nonce": str,  # Уникальный идентификатор handshake
        "from": str,  # Имя отправителя
        "device_id": str,
        "ephemeral_public": str,  # base64 ephemeral public key
        "signature": str  # base64 подпись эфемерного ключа
    }

    HANDSHAKE_RESPONSE = {
        **BASE,
        "type": MessageType.HANDSHAKE_RESPONSE,
        "nonce": str,  # Тот же nonce из запроса
        "from": str,
        "device_id": str,
        "chat_id": str,  # ID созданного чата
        "ephemeral_public": str,
        "signature": str
    }

    HANDSHAKE_REJECT = {
        **BASE,
        "type": MessageType.HANDSHAKE_REJECT,
        "nonce": str,
        "reason": str  # Причина отказа
    }

    # Защищённые сообщения
    SECURE_MESSAGE = {
        **BASE,
        "type": MessageType.SECURE_MESSAGE,
        "chat_id": str,
        "encrypted": {  # Зашифрованная часть
            "counter": int,
            "nonce": str,
            "iv": str,
            "ciphertext": str,
            "mac": str
        }
    }

    # Внутренняя структура расшифрованного сообщения
    DECRYPTED_MESSAGE = {
        "content": str,  # Текст сообщения
        "from": str,  # Отправитель
        "timestamp": float,
        "counter": int,
        "nonce": str,
        "reply_to": Optional[str]  # ID сообщения, на которое отвечаем
    }

    DELIVERY_RECEIPT = {
        **BASE,
        "type": MessageType.DELIVERY_RECEIPT,
        "chat_id": str,
        "in_response_to": str,  # msg_id исходного сообщения
        "status": MessageStatus
    }

    # Луковая маршрутизация
    RELAY = {
        **BASE,
        "type": MessageType.RELAY,
        "circuit_id": str,
        "layer": {  # Зашифрованный слой
            "iv": str,
            "ciphertext": str,
            "hop_index": int
        }
    }

    # Внутренняя структура слоя лука
    ONION_LAYER = {
        "next_node": Optional[str],  # Следующий узел или None
        "payload": Any,  # Данные или следующий слой
        "circuit_id": str
    }

    # Файлы
    FILE_OFFER = {
        **BASE,
        "type": MessageType.FILE_OFFER,
        "chat_id": str,
        "file_id": str,  # UUID файла
        "filename": str,
        "size": int,
        "mime_type": str,
        "encrypted_metadata": str  # Зашифрованные метаданные
    }

    FILE_ACCEPT = {
        **BASE,
        "type": MessageType.FILE_ACCEPT,
        "chat_id": str,
        "file_id": str,
        "port": int  # Порт для передачи файла
    }

    FILE_CHUNK = {
        **BASE,
        "type": MessageType.FILE_CHUNK,
        "file_id": str,
        "chunk_index": int,
        "total_chunks": int,
        "data": str,  # base64 chunk data
        "checksum": str  # SHA256 chunk'а
    }

    # DHT
    DHT_FIND_NODE = {
        **BASE,
        "type": MessageType.DHT_FIND_NODE,
        "target_id": str,
        "requester_id": str
    }

    DHT_FOUND_NODE = {
        **BASE,
        "type": MessageType.DHT_FOUND_NODE,
        "target_id": str,
        "nodes": list  # [(node_id, ip, port)]
    }

    # Системные
    PING = {
        **BASE,
        "type": MessageType.PING
    }

    PONG = {
        **BASE,
        "type": MessageType.PONG,
        "in_response_to": str  # msg_id ping'а
    }

    ERROR = {
        **BASE,
        "type": MessageType.ERROR,
        "in_response_to": str,
        "error_code": int,
        "error_message": str
    }

    BYE = {
        **BASE,
        "type": MessageType.BYE,
        "reason": str  # Причина отключения
    }


# ====================== DATACLASSES ДЛЯ СОСТОЯНИЙ ======================

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
    rtt: Optional[float]  # Время ответа на ping


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


# ====================== КОДЫ ОШИБОК ======================

class ErrorCodes:
    """Коды ошибок для системных сообщений"""

    # Общие ошибки (1-99)
    SUCCESS = 0
    UNKNOWN_ERROR = 1
    INTERNAL_ERROR = 2
    NOT_IMPLEMENTED = 3

    # Сетевые ошибки (100-199)
    PEER_UNREACHABLE = 100
    CONNECTION_TIMEOUT = 101
    CONNECTION_REFUSED = 102
    NETWORK_UNREACHABLE = 103

    # Протокольные ошибки (200-299)
    INVALID_MESSAGE_TYPE = 200
    MALFORMED_MESSAGE = 201
    UNSUPPORTED_VERSION = 202
    RATE_LIMITED = 203

    # Криптографические ошибки (300-399)
    HANDSHAKE_FAILED = 300
    INVALID_SIGNATURE = 301
    DECRYPTION_FAILED = 302
    INTEGRITY_VIOLATION = 303
    REPLAY_ATTACK = 304
    KEY_EXPIRED = 305
    SESSION_NOT_FOUND = 306

    # Ошибки аутентификации (400-499)
    UNAUTHORIZED = 400
    FORBIDDEN = 401
    PEER_REJECTED = 402

    # Ошибки файлов (500-599)
    FILE_TOO_LARGE = 500
    INVALID_CHUNK = 501
    CHECKSUM_MISMATCH = 502
    INSUFFICIENT_SPACE = 503

    # DHT ошибки (600-699)
    NODE_NOT_FOUND = 600
    VALUE_NOT_FOUND = 601
    STORE_FAILED = 602

    # Описания ошибок
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
        """Получить описание ошибки по коду"""
        return cls.MESSAGES.get(code, f"Unknown error code: {code}")


# ====================== ФУНКЦИИ ВАЛИДАЦИИ ======================

def validate_message(message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Проверить сообщение на соответствие схеме.
    Returns: (is_valid, error_message)
    """
    if 'type' not in message:
        return False, "Missing 'type' field"

    msg_type = message['type']

    # Находим соответствующую схему
    schema_name = msg_type.upper()
    if not hasattr(MessageSchemas, schema_name):
        return False, f"Unknown message type: {msg_type}"

    schema = getattr(MessageSchemas, schema_name)

    # Проверяем обязательные поля
    for field, field_type in schema.items():
        if field not in message:
            return False, f"Missing required field: {field}"

        # Проверяем тип (базовая проверка)
        if field_type not in (str, int, float, bool, list, dict, type(None)):
            # Для сложных типов пропускаем
            continue

        if not isinstance(message[field], field_type):
            return False, f"Field {field} should be {field_type.__name__}"

    return True, None


def create_message(msg_type: MessageType, **kwargs) -> Dict[str, Any]:
    """
    Создать сообщение с правильной структурой.
    Автоматически добавляет msg_id и timestamp.
    """
    import secrets
    import time

    message = {
        "type": msg_type.value if isinstance(msg_type, Enum) else msg_type,
        "msg_id": secrets.token_hex(8),
        "timestamp": time.time(),
        **kwargs
    }

    # Валидируем (опционально)
    # is_valid, error = validate_message(message)
    # if not is_valid:
    #     raise ValueError(f"Invalid message: {error}")

    return message


# ====================== КОНФИГУРАЦИЯ ПРИЛОЖЕНИЯ ======================

class AppConfig:
    """Глобальная конфигурация приложения"""

    # Режим отладки
    DEBUG = False

    # Пути
    DB_PATH = "secure_chat.db"
    LOG_PATH = "chat.log"

    # Сеть
    MAX_CONNECTIONS = 50
    BUFFER_SIZE = 65536

    # Безопасность
    ENFORCE_ENCRYPTION = True  # Не принимать незашифрованные сообщения
    AUTO_ROTATE_KEYS = True
    REJECT_SELF_SIGNED = False  # В реальном мире - True

    # Функции
    ENABLE_FILE_TRANSFER = True
    ENABLE_CALLS = False  # Пока не реализовано
    ENABLE_ONION_ROUTING = True

    @classmethod
    def from_env(cls):
        """Загрузить конфигурацию из переменных окружения"""
        import os

        if os.getenv("CHAT_DEBUG"):
            cls.DEBUG = True
        if os.getenv("CHAT_DB_PATH"):
            cls.DB_PATH = os.getenv("CHAT_DB_PATH")

        return cls