"""
Обнаружение других пиров в локальной сети через UDP broadcast
"""
import socket
import json
import threading
import time
from typing import Dict, Callable, Optional

from .protocols import BROADCAST_PORT, MESSAGE_PORT, Timeouts, Intervals


class PeerDiscovery:
    """
    Отвечает за обнаружение других устройств в сети
    """

    def __init__(self, username: str, device_id: str, public_key_b64: str):
        self.username = username
        self.device_id = device_id
        self.public_key_b64 = public_key_b64

        self.peers: Dict[str, dict] = {}  # ip -> peer_info
        self.running = False

        # Сокеты
        self.broadcast_socket = None
        self.listen_socket = None

        # Колбэки
        self.on_peer_found: Optional[Callable] = None
        self.on_peer_lost: Optional[Callable] = None

    def start(self):
        """Запуск обнаружения"""
        self.running = True

        # Сокет для рассылки
        self.broadcast_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.broadcast_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self.broadcast_socket.settimeout(Timeouts.BROADCAST)

        # Сокет для прослушивания
        self.listen_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.listen_socket.bind(('', BROADCAST_PORT))
        self.listen_socket.settimeout(Timeouts.BROADCAST)

        # Запуск потоков
        threading.Thread(target=self._broadcast_loop, daemon=True).start()
        threading.Thread(target=self._listen_loop, daemon=True).start()
        threading.Thread(target=self._cleanup_loop, daemon=True).start()

    def stop(self):
        """Остановка"""
        self.running = False
        if self.broadcast_socket:
            self.broadcast_socket.close()
        if self.listen_socket:
            self.listen_socket.close()

    def _broadcast_loop(self):
        """Периодическая рассылка информации о себе"""
        while self.running:
            try:
                presence = {
                    'type': 'presence',
                    'username': self.username,
                    'device_id': self.device_id,
                    'public_key': self.public_key_b64,
                    'port': MESSAGE_PORT,
                    'timestamp': time.time()
                }
                self.broadcast_socket.sendto(
                    json.dumps(presence).encode(),
                    ('<broadcast>', BROADCAST_PORT)
                )
            except Exception as e:
                print(f"Broadcast error: {e}")
            time.sleep(Intervals.PRESENCE_BROADCAST)

    def _listen_loop(self):
        """Прослушивание broadcast сообщений"""
        while self.running:
            try:
                data, addr = self.listen_socket.recvfrom(4096)
                peer_info = json.loads(data.decode())

                # Игнорируем себя
                if peer_info.get('device_id') == self.device_id:
                    continue

                ip = addr[0]
                old_info = self.peers.get(ip)

                # Обновляем информацию
                self.peers[ip] = {
                    'username': peer_info['username'],
                    'device_id': peer_info['device_id'],
                    'public_key': peer_info.get('public_key'),
                    'port': peer_info.get('port', MESSAGE_PORT),
                    'last_seen': time.time()
                }

                # Вызываем колбэк если это новый пир
                if not old_info and self.on_peer_found:
                    self.on_peer_found(ip, self.peers[ip])

            except socket.timeout:
                continue
            except Exception as e:
                print(f"Listen error: {e}")

    def _cleanup_loop(self):
        """Удаляем старых пиров"""
        while self.running:
            now = time.time()
            to_remove = []

            for ip, info in self.peers.items():
                if now - info['last_seen'] > Timeouts.PEER_TIMEOUT:
                    to_remove.append(ip)

            for ip in to_remove:
                if self.on_peer_lost:
                    self.on_peer_lost(ip, self.peers[ip])
                del self.peers[ip]

            time.sleep(Timeouts.PEER_TIMEOUT / 2)

    def get_peer_by_name(self, name: str) -> Optional[tuple]:
        """Найти пира по имени"""
        for ip, info in self.peers.items():
            if info['username'] == name:
                return ip, info
        return None

    def get_all_peers(self) -> Dict:
        """Получить всех активных пиров"""
        return self.peers.copy()