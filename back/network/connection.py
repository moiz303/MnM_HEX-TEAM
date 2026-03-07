"""
Управление TCP соединениями с пирами
"""
import socket
import json
import threading
import time
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
        self.peer_id: Optional[str] = None
        
        # Mesh-сеть компоненты
        self.active_connections: Dict[str, dict] = {}  # peer_id -> connection_info
        self.peer_addresses: Dict[str, tuple] = {}     # peer_id -> (ip, port)
        self.connection_stats: Dict[str, dict] = {}    # peer_id -> stats

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
            # Read message length prefix first (4 bytes)
            sock.settimeout(10.0)
            
            # Read length prefix
            length_data = b''
            while len(length_data) < 4:
                chunk = sock.recv(4 - len(length_data))
                if not chunk:
                    return
                length_data += chunk
            
            message_length = int.from_bytes(length_data, byteorder='big')
            
            if message_length > Limits.MAX_MESSAGE_SIZE:
                print(f"[connection] Message too large from {addr}: {message_length} bytes")
                return
            
            # Read the actual message
            data = b''
            while len(data) < message_length:
                chunk = sock.recv(min(message_length - len(data), 16384))
                if not chunk:
                    break
                data += chunk
            
            if len(data) != message_length:
                print(f"[connection] Incomplete message from {addr}: expected {message_length}, got {len(data)}")
                return
            
            message = json.loads(data.decode())

            if self.on_message:
                self.on_message(message, addr)

        except json.JSONDecodeError as e:
            print(f"[connection] Invalid JSON from {addr}: {e}, data size: {len(data) if 'data' in locals() else 'unknown'}")
        except Exception as e:
            print(f"[connection] Connection error from {addr}: {e}")
        finally:
            sock.close()

    def send_to_peer(self, ip: str, data: dict) -> bool:
        """
        Отправить данные пиру

        Returns:
            True если успешно, False если пир недоступен
        """
        try:
            import json
            json_data = json.dumps(data).encode()
            
            if len(json_data) > Limits.MAX_MESSAGE_SIZE:
                print(f"[connection] Message to {ip} too large: {len(json_data)} > {Limits.MAX_MESSAGE_SIZE}")
                return False

            # Add length prefix (4 bytes big-endian)
            message_with_prefix = len(json_data).to_bytes(4, byteorder='big') + json_data

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(Timeouts.CONNECTION)
                sock.connect((ip, MESSAGE_PORT))
                sock.sendall(message_with_prefix)
                return True
        except (socket.timeout, ConnectionRefusedError):
            return False
        except Exception as e:
            print(f"[connection] Send error to {ip}: {e}")
            return False

    def send_message(self, peer_id: str, data: dict) -> bool:
        """
        Отправить сообщение по ID пира через mesh-сеть
        
        Args:
            peer_id: ID получателя
            data: данные для отправки
            
        Returns:
            True если успешно, False если пир недоступен
        """
        # Проверить прямой адрес
        if peer_id in self.peer_addresses:
            ip, port = self.peer_addresses[peer_id]
            success = self.send_to_peer(ip, data)
            if success:
                self._update_connection_stats(peer_id, 'sent', len(str(data)))
            return success
        
        # Проверить активные соединения
        if peer_id in self.active_connections:
            conn_info = self.active_connections[peer_id]
            success = self.send_to_peer(conn_info['ip'], data)
            if success:
                self._update_connection_stats(peer_id, 'sent', len(str(data)))
            return success
        
        print(f"[connection] Peer {peer_id} not found in address book")
        return False

    def is_peer_connected(self, peer_id: str) -> bool:
        """
        Проверить, подключен ли пир
        
        Args:
            peer_id: ID пира для проверки
            
        Returns:
            True если пир подключен или был активен недавно
        """
        if peer_id in self.active_connections:
            conn_info = self.active_connections[peer_id]
            # Считаем подключенным, если была активность за последние 2 минуты
            return time.time() - conn_info.get('last_activity', 0) < 120
        
        # Проверить по адресу
        if peer_id in self.peer_addresses:
            ip, port = self.peer_addresses[peer_id]
            # Попытаться проверить доступность
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.settimeout(3.0)
                    result = sock.connect_ex((ip, port))
                    if result == 0:
                        self._update_connection_stats(peer_id, 'connected', 0)
                        return True
            except:
                pass
        
        return False

    def register_peer(self, peer_id: str, ip: str, port: int = MESSAGE_PORT):
        """
        Зарегистрировать адрес пира
        
        Args:
            peer_id: ID пира
            ip: IP адрес
            port: порт
        """
        self.peer_addresses[peer_id] = (ip, port)
        self.active_connections[peer_id] = {
            'ip': ip,
            'port': port,
            'connected_at': time.time(),
            'last_activity': time.time()
        }
        print(f"[connection] Registered peer {peer_id} at {ip}:{port}")

    def update_peer_address(self, peer_id: str, ip: str, port: int = MESSAGE_PORT):
        """
        Обновить адрес пира
        
        Args:
            peer_id: ID пира
            ip: новый IP адрес
            port: новый порт
        """
        old_addr = self.peer_addresses.get(peer_id)
        self.peer_addresses[peer_id] = (ip, port)
        
        if peer_id in self.active_connections:
            self.active_connections[peer_id]['ip'] = ip
            self.active_connections[peer_id]['port'] = port
            self.active_connections[peer_id]['last_activity'] = time.time()
        
        if old_addr and old_addr != (ip, port):
            print(f"[connection] Updated peer {peer_id}: {old_addr} -> {ip}:{port}")

    def _update_connection_stats(self, peer_id: str, action: str, bytes_count: int):
        """
        Обновить статистику соединения
        
        Args:
            peer_id: ID пира
            action: тип действия ('sent', 'received', 'connected')
            bytes_count: количество байт
        """
        if peer_id not in self.connection_stats:
            self.connection_stats[peer_id] = {
                'messages_sent': 0,
                'messages_received': 0,
                'bytes_sent': 0,
                'bytes_received': 0,
                'last_activity': time.time()
            }
        
        stats = self.connection_stats[peer_id]
        stats['last_activity'] = time.time()
        
        if action == 'sent':
            stats['messages_sent'] += 1
            stats['bytes_sent'] += bytes_count
        elif action == 'received':
            stats['messages_received'] += 1
            stats['bytes_received'] += bytes_count
        elif action == 'connected':
            pass  # Just update last_activity

    def get_connection_stats(self, peer_id: str = None) -> dict:
        """
        Получить статистику соединений
        
        Args:
            peer_id: конкретный пир или None для всех
            
        Returns:
            Словарь со статистикой
        """
        if peer_id:
            return self.connection_stats.get(peer_id, {})
        
        return {
            'total_peers': len(self.active_connections),
            'connected_peers': len([p for p in self.active_connections.values() 
                                  if time.time() - p.get('last_activity', 0) < 120]),
            'total_messages_sent': sum(s.get('messages_sent', 0) for s in self.connection_stats.values()),
            'total_messages_received': sum(s.get('messages_received', 0) for s in self.connection_stats.values()),
            'total_bytes_sent': sum(s.get('bytes_sent', 0) for s in self.connection_stats.values()),
            'total_bytes_received': sum(s.get('bytes_received', 0) for s in self.connection_stats.values())
        }