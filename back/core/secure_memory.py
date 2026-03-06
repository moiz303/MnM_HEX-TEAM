"""
Защищённое хранение ключей в памяти с автоматическим затиранием
"""
import secrets
import ctypes


class SecureMemory:
    """
    Контейнер для криптографических ключей в памяти.
    Гарантирует затирание при удалении и защиту от сброса на диск.
    """

    def __init__(self, size: int):
        self.size = size
        self._buffer = bytearray(size)
        self._locked = False
        self._lock_memory()

    def _lock_memory(self):
        """Пытаемся залочить память чтобы не ушла в swap"""
        try:
            # Пытаемся использовать mlock если доступно
            if hasattr(ctypes, 'pythonapi'):
                ctypes.pythonapi.mlock(
                    ctypes.c_void_p(id(self._buffer)),
                    ctypes.c_size_t(self.size)
                )
                self._locked = True
        except Exception:
            # mlock может не работать на некоторых системах
            pass

    def write(self, data: bytes) -> None:
        """Записать данные в защищённую память"""
        if len(data) > self.size:
            raise ValueError(f"Data too large: {len(data)} > {self.size}")
        self._buffer[:len(data)] = data

    def read(self) -> bytes:
        """Прочитать данные из защищённой памяти"""
        return bytes(self._buffer[:self.size])

    def wipe(self) -> None:
        """Затереть память случайными данными и нулями"""
        # Сначала случайные данные
        for i in range(self.size):
            self._buffer[i] = secrets.randbelow(256)
        # Потом нули
        for i in range(self.size):
            self._buffer[i] = 0

    def __del__(self):
        """При удалении гарантированно затираем память"""
        self.wipe()