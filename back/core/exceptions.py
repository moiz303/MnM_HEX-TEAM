"""
Иерархия исключений для криптографического ядра и всего приложения.
Позволяет точно определить тип ошибки и корректно на неё среагировать.
"""
class CryptoError(Exception):
    """
    Базовое криптографическое исключение.
    Все остальные крипто-исключения наследуются от него.
    """

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.details:
            return f"{self.message} | Details: {self.details}"
        return self.message


class KeyError(CryptoError):
    """Ошибки, связанные с ключами"""
    pass


class SessionNotFoundError(KeyError):
    """Сессия не найдена (чат не инициализирован)"""

    def __init__(self, chat_id: str):
        super().__init__(
            f"Session not found for chat {chat_id}",
            {"chat_id": chat_id}
        )


class KeyExpiredError(KeyError):
    """Ключ истёк (нужна ротация или переустановка соединения)"""

    def __init__(self, chat_id: str, last_used: float, max_age: float):
        super().__init__(
            f"Session keys expired for chat {chat_id}",
            {
                "chat_id": chat_id,
                "last_used": last_used,
                "max_age": max_age
            }
        )


class SignatureError(CryptoError):
    """Ошибки верификации подписей"""
    pass


class InvalidSignatureError(SignatureError):
    """Подпись недействительна - возможна атака или повреждение"""

    def __init__(self, expected_peer: str = None):
        details = {"expected_peer": expected_peer} if expected_peer else {}
        super().__init__(
            "Invalid signature - message may be tampered",
            details
        )


class MissingPeerKeyError(SignatureError):
    """Нет ключа пира для проверки подписи"""

    def __init__(self, peer_id: str):
        super().__init__(
            f"No public key for peer {peer_id}",
            {"peer_id": peer_id}
        )


class EncryptionError(CryptoError):
    """Ошибки при шифровании"""
    pass


class DecryptionError(CryptoError):
    """Ошибки при расшифровке"""
    pass


class ReplayAttackError(DecryptionError):
    """Обнаружена replay-атака (повтор сообщения)"""

    def __init__(self, chat_id: str, counter: int, nonce: str):
        super().__init__(
            "Replay attack detected",
            {
                "chat_id": chat_id,
                "counter": counter,
                "nonce": nonce
            }
        )


class CounterError(DecryptionError):
    """Ошибка счётчика сообщений (нарушение порядка)"""

    def __init__(self, expected: int, received: int):
        super().__init__(
            f"Invalid counter: expected >={expected}, got {received}",
            {"expected": expected, "received": received}
        )


class IntegrityError(DecryptionError):
    """Нарушение целостности (не совпадает MAC)"""

    def __init__(self, chat_id: str):
        super().__init__(
            "Message integrity check failed - MAC mismatch",
            {"chat_id": chat_id}
        )


class PaddingError(DecryptionError):
    """Ошибка удаления padding (обычно признак повреждения)"""

    def __init__(self):
        super().__init__("Invalid padding - message corrupted")


class HandshakeError(Exception):
    """Ошибки при установке соединения"""

    def __init__(self, message: str, peer: str = None):
        self.peer = peer
        details = {"peer": peer} if peer else {}
        super().__init__(message, details)


class HandshakeTimeoutError(HandshakeError):
    """Таймаут при handshake"""

    def __init__(self, peer: str, timeout: float):
        super().__init__(
            f"Handshake timeout with {peer} after {timeout}s",
            peer
        )


class HandshakeRejectedError(HandshakeError):
    """Пир отклонил handshake"""

    def __init__(self, peer: str, reason: str = None):
        msg = f"Handshake rejected by {peer}"
        if reason:
            msg += f": {reason}"
        super().__init__(msg, peer)


class ProtocolError(Exception):
    """Ошибки протокола обмена"""

    def __init__(self, message: str, msg_type: str = None):
        self.msg_type = msg_type
        details = {"type": msg_type} if msg_type else {}
        super().__init__(message, details)


class InvalidMessageTypeError(ProtocolError):
    """Неизвестный тип сообщения"""

    def __init__(self, msg_type: str):
        super().__init__(
            f"Invalid message type: {msg_type}",
            msg_type
        )


class MalformedMessageError(ProtocolError):
    """Сообщение имеет неверный формат"""

    def __init__(self, missing_field: str):
        super().__init__(
            f"Malformed message - missing field: {missing_field}"
        )


class NetworkError(Exception):
    """Сетевые ошибки"""
    pass


class PeerUnreachableError(NetworkError):
    """Пир недоступен"""

    def __init__(self, peer: str, ip: str = None):
        msg = f"Peer {peer} is unreachable"
        if ip:
            msg += f" ({ip})"
        super().__init__(msg)


class ConnectionTimeoutError(NetworkError):
    """Таймаут соединения"""

    def __init__(self, peer: str, timeout: float):
        super().__init__(
            f"Connection to {peer} timed out after {timeout}s"
        )


class StorageError(Exception):
    """Ошибки базы данных"""
    pass


class DatabaseError(StorageError):
    """Общие ошибки БД"""

    def __init__(self, operation: str, reason: str):
        super().__init__(
            f"Database error during {operation}: {reason}"
        )


class MessageNotFoundError(StorageError):
    """Сообщение не найдено в БД"""

    def __init__(self, msg_id: str):
        super().__init__(f"Message {msg_id} not found in database")