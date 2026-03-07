from .auto_relay import AutoRelayManager
from .file_transfer import FileTransferManager


class OnionRouter:
    """Facade для маршрутизации."""

    def __init__(self, connection_manager, crypto_core):
        self.relay_manager = AutoRelayManager(connection_manager, crypto_core)
        self.connection_manager = connection_manager
        self.file_manager = FileTransferManager(connection_manager, crypto_core, self)
        self.file_manager.on_progress = self._on_file_progress
        self.file_manager.on_complete = self._on_file_complete
        self.file_manager.on_file_offer = self._on_file_offer

    def enable(self):
        self.relay_manager.toggle_relay(True)

    def disable(self):
        self.relay_manager.toggle_relay(False)

    def send_message(self, target_peer_id: str, message: dict):
        if self.connection_manager.is_peer_connected(target_peer_id):
            self.connection_manager.send_message(target_peer_id, message)
            return True
        circuit_id = self.relay_manager.create_mesh_circuit(target_peer_id)
        if circuit_id:
            self.relay_manager.handle_relay_data(circuit_id, message, 'local')
            return True
        return False

    def send_file(self, target_peer_id: str, file_path: str) -> str:
        circuit_id = None
        if not self.connection_manager.is_peer_connected(target_peer_id):
            circuit_id = self.relay_manager.create_mesh_circuit(target_peer_id)
        return self.file_manager.send_file(target_peer_id, file_path, circuit_id)

    def handle_incoming(self, msg_type, data: dict, sender_id: str):
        if isinstance(msg_type, int):
            msg_type_str = self._int_to_msg_type(msg_type)
        else:
            msg_type_str = msg_type
        if msg_type_str in ['file_offer', 'file_chunk', 'file_complete', 'file_accept', 'file_reject', 'file_error']:
            self._handle_file_message(msg_type_str, data, sender_id)
            return
        if msg_type == 10:
            self.relay_manager.update_peer_status(sender_id, data, ('0.0.0.0', 0))
        elif msg_type == 13:
            self.relay_manager.handle_relay_data(data['circuit_id'], data['payload'], sender_id)
        elif msg_type == 11:
            self.relay_manager.handle_circuit_create(data.get('circuit_id'), data, sender_id)
        elif msg_type == 12:
            self.relay_manager.handle_circuit_confirm(data.get('circuit_id'), data, sender_id)
        elif msg_type == 14:
            self.relay_manager.handle_circuit_destroy(data.get('circuit_id'), data, sender_id)

    def _handle_file_message(self, msg_type: str, data: dict, sender_id: str):
        if msg_type == 'file_offer':
            self.file_manager.handle_file_offer(data, sender_id)
        elif msg_type == 'file_chunk':
            self.file_manager.handle_file_chunk(data, sender_id)
        elif msg_type == 'file_complete':
            self.file_manager.handle_file_complete(data, sender_id)

    def _on_file_progress(self, transfer_id: str, progress: float, bytes_transferred: int):
        print(f"📊 Transfer {transfer_id}: {progress:.1f}% ({bytes_transferred} bytes)")

    def _on_file_complete(self, transfer_id: str, status: str):
        print(f"🏁 Transfer {transfer_id} finished with status: {status}")

    def _on_file_offer(self, session):
        print(f"📥 Incoming file offer: {session.file_info.filename} from {session.file_info.sender_id}")

    def _int_to_msg_type(self, msg_type_int: int) -> str:
        mapping = {10: 'relay_status', 11: 'circuit_create', 12: 'circuit_confirm', 13: 'relay_data', 14: 'circuit_destroy'}
        return mapping.get(msg_type_int, 'unknown')

    def get_stats(self):
        relay_stats = self.relay_manager.get_stats()
        file_stats = {
            'transfers_active': len(self.file_manager.active_transfers),
            'transfers_completed': self.file_manager.stats['transfers_completed'],
            'bytes_sent': self.file_manager.stats['bytes_sent'],
            'bytes_received': self.file_manager.stats['bytes_received']
        }
        return {**relay_stats, **file_stats}