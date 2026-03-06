"""
Управление TCP соединениями с пирами
"""
import socket
import json
import threading
from typing import Optional, Callable

from .protocols import MESSAGE_PORT, Limits, Timeouts


class ConnectionManager:
    """
    Отвечает за установку соединений и передачу данных
    """

    def __init__(self):
        self.listener_socket = None
        self.running = False
        self.on_message: Optional[Callable] = None

    def start(self, on_message_callback: Callable):
        """Запуск прослушивания входящих соединений"""
        self.on_message = on_message_callback
        self.running = True

        self.listener_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listener_socket.bind(('', MESSAGE_PORT))
        self.listener_socket.listen(5)

        threading.Thread(target=self._accept_loop, daemon=True).start()

    def stop(self):
        """Остановка"""
        self.running = False
        if self.listener_socket:
            self.listener_socket.close()

    def _accept_loop(self):
        """Цикл принятия соединений"""
        while self.running:
            try:
                client, addr = self.listener_socket.accept()
                threading.Thread(
                    target=self._handle_connection,
                    args=(client, addr),
                    daemon=True
                ).start()
            except Exception as e:
                if self.running:
                    print(f"Accept error: {e}")

    def _handle_connection(self, sock: socket.socket, addr: tuple):
        """Обработка одного соединения"""
        try:
            data = sock.recv(Limits.MAX_MESSAGE_SIZE)
            if not data:
                return

            message = json.loads(data.decode())

            if self.on_message:
                self.on_message(message, addr)

        except json.JSONDecodeError:
            print(f"Invalid JSON from {addr}")
        except Exception as e:
            print(f"Connection error: {e}")
        finally:
            sock.close()

    def send_to_peer(self, ip: str, data: dict) -> bool:
        """
        Отправить данные пиру

        Returns:
            True если успешно, False если пир недоступен
        """
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(Timeouts.CONNECTION)
                sock.connect((ip, MESSAGE_PORT))
                sock.sendall(json.dumps(data).encode())
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False
        except Exception as e:
            print(f"Send error to {ip}: {e}")
            return False