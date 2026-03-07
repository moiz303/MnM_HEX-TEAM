import threading
import time
import random
import json
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from .protocols import MessageType, RelayLimits


@dataclass
class PeerRelayInfo:
    """Информация о пире как о потенциальном ретрансляторе"""
    peer_id: str
    ip: str
    port: int
    bandwidth: int
    last_seen: float
    is_relay: bool = True
    reputation_score: float = 1.0
    messages_relayed: int = 0
    bytes_relayed: int = 0


@dataclass
class Circuit:
    """Активная цепь маршрутизации"""
    circuit_id: str
    path: List[str]
    created_at: float
    last_activity: float
    is_initiator: bool = True
    layer_keys: Dict[str, bytes] = field(default_factory=dict)
    ttl: int = 0
    status: str = 'active'


class AutoRelayManager:
    """Mesh-by-Default Manager."""

    def __init__(self, connection_manager, crypto_core):
        self.conn_mgr = connection_manager
        self.crypto = crypto_core
        self.is_enabled = True
        self.known_relays: Dict[str, PeerRelayInfo] = {}
        self.active_circuits: Dict[str, Circuit] = {}
        self.pending_circuits: Dict[str, dict] = {}
        self.transit_circuits: Dict[str, Circuit] = {}
        self.lock = threading.RLock()
        self.stats = {
            'relayed_msgs': 0,
            'relayed_bytes': 0,
            'circuits_created': 0,
            'circuits_failed': 0,
            'rate_limit_hits': 0
        }
        self.rate_limits = defaultdict(list)
        self.max_requests_per_minute = 60
        self._stop_event = threading.Event()
        self._start_background_threads()

    def _start_background_threads(self):
        threads = [
            threading.Thread(target=self._cleanup_loop, daemon=True),
            threading.Thread(target=self._heartbeat_loop, daemon=True),
            threading.Thread(target=self._rate_limit_cleanup, daemon=True),
        ]
        for t in threads:
            t.start()

    def toggle_relay(self, enabled: bool):
        self.is_enabled = enabled
        print(f"🔄 Mesh Relay: {'ENABLED' if enabled else 'DISABLED'}")
        if enabled:
            self._broadcast_status()
        else:
            with self.lock:
                self.transit_circuits.clear()

    def _cleanup_loop(self):
        while not self._stop_event.is_set():
            time.sleep(RelayLimits.CLEANUP_INTERVAL_SEC)
            now = time.time()
            with self.lock:
                stale_peers = [pid for pid, info in self.known_relays.items() if now - info.last_seen > 120]
                for pid in stale_peers:
                    del self.known_relays[pid]
                expired_circuits = [cid for cid, circuit in self.active_circuits.items() if now - circuit.last_activity > RelayLimits.CIRCUIT_TIMEOUT_SEC]
                for cid in expired_circuits:
                    self._destroy_circuit(cid, 'timeout')
                expired_transit = [cid for cid, circuit in self.transit_circuits.items() if now - circuit.last_activity > RelayLimits.CIRCUIT_TIMEOUT_SEC]
                for cid in expired_transit:
                    del self.transit_circuits[cid]

    def _heartbeat_loop(self):
        while not self._stop_event.is_set():
            time.sleep(RelayLimits.HEARTBEAT_INTERVAL_SEC)
            if self.is_enabled:
                self._broadcast_status()

    def _rate_limit_cleanup(self):
        while not self._stop_event.is_set():
            time.sleep(60)
            now = time.time()
            with self.lock:
                for peer_id in list(self.rate_limits.keys()):
                    self.rate_limits[peer_id] = [ts for ts in self.rate_limits[peer_id] if now - ts < 60]
                    if not self.rate_limits[peer_id]:
                        del self.rate_limits[peer_id]

    def _broadcast_status(self):
        msg = {
            'type': MessageType.RELAY_STATUS.value if hasattr(MessageType, 'RELAY_STATUS') else 10,
            'bandwidth': RelayLimits.MAX_BANDWIDTH_KBPS,
            'max_hops': RelayLimits.MAX_HOPS,
            'is_relay': self.is_enabled,
            'timestamp': time.time()
        }
        if hasattr(self.conn_mgr, 'peers'):
            for peer_id in list(self.conn_mgr.peers.keys()):
                try:
                    self.conn_mgr.send_message(peer_id, msg)
                except Exception as e:
                    print(f"Failed to send relay status to {peer_id}: {e}")

    def update_peer_status(self, peer_id: str, data: dict, addr: tuple):
        with self.lock:
            if peer_id in self.known_relays:
                info = self.known_relays[peer_id]
                info.last_seen = time.time()
                info.bandwidth = data.get('bandwidth', info.bandwidth)
                info.is_relay = data.get('is_relay', True)
            else:
                self.known_relays[peer_id] = PeerRelayInfo(
                    peer_id=peer_id,
                    ip=addr[0],
                    port=addr[1],
                    bandwidth=data.get('bandwidth', 100),
                    last_seen=time.time(),
                    is_relay=data.get('is_relay', True),
                    reputation_score=1.0
                )

    def create_mesh_circuit(self, target_peer_id: str) -> Optional[str]:
        if not self.is_enabled:
            return None
        with self.lock:
            candidates = [pid for pid, info in self.known_relays.items() if pid != target_peer_id and info.is_relay and info.reputation_score > 0.5]
            if not candidates:
                self.stats['circuits_failed'] += 1
                return None
            num_hops = min(RelayLimits.MAX_HOPS, len(candidates))
            hops = random.sample(candidates, num_hops)
            circuit_id = f"mesh_{int(time.time())}_{random.randint(10000, 99999)}"
            full_path = hops + [target_peer_id]
            layer_keys = {}
            for i, hop in enumerate(full_path):
                layer_keys[hop] = self.crypto.generate_symmetric_key()
            circuit = Circuit(
                circuit_id=circuit_id,
                path=full_path,
                created_at=time.time(),
                last_activity=time.time(),
                is_initiator=True,
                layer_keys=layer_keys,
                ttl=RelayLimits.CIRCUIT_TIMEOUT_SEC,
                status='pending'
            )
            self.active_circuits[circuit_id] = circuit
            self.stats['circuits_created'] += 1
        init_msg = {
            'type': MessageType.CIRCUIT_CREATE.value if hasattr(MessageType, 'CIRCUIT_CREATE') else 11,
            'circuit_id': circuit_id,
            'path': full_path,
            'command': 'INIT',
            'sender': self.conn_mgr.peer_id if hasattr(self.conn_mgr, 'peer_id') else 'unknown',
            'timestamp': time.time()
        }
        first_hop = hops[0] if hops else target_peer_id
        success = self.conn_mgr.send_message(first_hop, init_msg)
        if not success:
            with self.lock:
                self._destroy_circuit(circuit_id, 'init_failed')
            return None
        return circuit_id

    def handle_circuit_create(self, circuit_id: str, data: dict, sender_id: str):
        command = data.get('command', '')
        path = data.get('path', [])
        if command == 'INIT':
            if not self.is_enabled:
                self._send_circuit_response(circuit_id, sender_id, 'REJECT', 'relay_disabled')
                return
            if not self._check_rate_limit(sender_id):
                self.stats['rate_limit_hits'] += 1
                self._send_circuit_response(circuit_id, sender_id, 'REJECT', 'rate_limited')
                return
            try:
                my_index = path.index(sender_id)
                next_index = my_index + 1
                if next_index < len(path):
                    next_hop = path[next_index]
                    with self.lock:
                        self.transit_circuits[circuit_id] = Circuit(
                            circuit_id=circuit_id,
                            path=path,
                            created_at=time.time(),
                            last_activity=time.time(),
                            is_initiator=False,
                            status='active'
                        )
                    forward_msg = {
                        'type': MessageType.CIRCUIT_CREATE.value if hasattr(MessageType, 'CIRCUIT_CREATE') else 11,
                        'circuit_id': circuit_id,
                        'path': path,
                        'command': 'INIT',
                        'sender': sender_id,
                        'timestamp': time.time()
                    }
                    self.conn_mgr.send_message(next_hop, forward_msg)
                    self._send_circuit_response(circuit_id, sender_id, 'CONFIRM', 'ok')
                else:
                    with self.lock:
                        self.transit_circuits[circuit_id] = Circuit(
                            circuit_id=circuit_id,
                            path=path,
                            created_at=time.time(),
                            last_activity=time.time(),
                            is_initiator=False,
                            status='active'
                        )
                    self._send_circuit_response(circuit_id, sender_id, 'CONFIRM', 'final_reached')
            except ValueError:
                self._send_circuit_response(circuit_id, sender_id, 'REJECT', 'path_error')
        elif command == 'DESTROY':
            self._destroy_transit_circuit(circuit_id)

    def _send_circuit_response(self, circuit_id: str, target: str, status: str, reason: str):
        msg = {
            'type': MessageType.CIRCUIT_CONFIRM.value if hasattr(MessageType, 'CIRCUIT_CONFIRM') else 12,
            'circuit_id': circuit_id,
            'status': status,
            'reason': reason,
            'timestamp': time.time()
        }
        self.conn_mgr.send_message(target, msg)

    def handle_circuit_confirm(self, circuit_id: str, data: dict, sender_id: str):
        status = data.get('status', '')
        with self.lock:
            circuit = self.active_circuits.get(circuit_id)
            if not circuit:
                return
            if status == 'CONFIRM':
                circuit.status = 'active'
                circuit.last_activity = time.time()
                print(f"✅ Circuit {circuit_id} confirmed by {sender_id}")
            elif status == 'REJECT':
                self._destroy_circuit(circuit_id, f'rejected: {data.get("reason")}')
                print(f"❌ Circuit {circuit_id} rejected: {data.get('reason')}")

    def handle_relay_data(self, circuit_id: str, payload: dict, sender_id: str):
        if not self.is_enabled:
            return
        with self.lock:
            circuit = self.active_circuits.get(circuit_id)
            if circuit and circuit.is_initiator:
                self._handle_initiator_relay(circuit_id, payload, sender_id, circuit)
            else:
                self._forward_unknown_circuit(circuit_id, payload, sender_id)

    def _handle_initiator_relay(self, circuit_id: str, payload: dict, sender_id: str, circuit: Circuit):
        try:
            path = circuit.path
            my_index = -1
            for i, pid in enumerate(path):
                if pid == sender_id:
                    my_index = i
                    break
            if my_index == -1:
                return
            next_index = my_index + 1
            if next_index >= len(path):
                decrypted = self._decrypt_onion_layers(payload, circuit)
                self._deliver_message(decrypted, circuit_id)
            else:
                next_hop = path[next_index]
                encrypted = self._encrypt_for_hop(payload, next_hop, circuit)
                self.conn_mgr.send_message(next_hop, {
                    'type': MessageType.RELAY_DATA.value if hasattr(MessageType, 'RELAY_DATA') else 13,
                    'circuit_id': circuit_id,
                    'payload': encrypted,
                    'timestamp': time.time()
                })
                circuit.last_activity = time.time()
        except Exception as e:
            print(f"Error handling initiator relay: {e}")

    def _forward_unknown_circuit(self, circuit_id: str, payload: dict, sender_id: str):
        with self.lock:
            circuit = self.transit_circuits.get(circuit_id)
            if not circuit:
                print(f"⚠️ Unknown circuit {circuit_id} from {sender_id}")
                return
            if not self._check_rate_limit(sender_id):
                self.stats['rate_limit_hits'] += 1
                return
            circuit.last_activity = time.time()
            self.stats['relayed_msgs'] += 1
            self.stats['relayed_bytes'] += len(json.dumps(payload))
            if sender_id in self.known_relays:
                self.known_relays[sender_id].messages_relayed += 1
                self.known_relays[sender_id].bytes_relayed += len(json.dumps(payload))
            try:
                path = circuit.path
                my_index = -1
                for i, pid in enumerate(path):
                    if pid == sender_id:
                        my_index = i
                        break
                if my_index == -1:
                    return
                next_index = my_index + 1
                if next_index >= len(path):
                    return
                next_hop = path[next_index]
                if hasattr(self.conn_mgr, 'peers'):
                    if next_hop not in self.conn_mgr.peers:
                        print(f"⚠️ Next hop {next_hop} not connected")
                        return
                forward_msg = {
                    'type': MessageType.RELAY_DATA.value if hasattr(MessageType, 'RELAY_DATA') else 13,
                    'circuit_id': circuit_id,
                    'payload': payload,
                    'timestamp': time.time()
                }
                success = self.conn_mgr.send_message(next_hop, forward_msg)
                if not success:
                    self._send_circuit_error(circuit_id, path[0], 'hop_unreachable')
            except Exception as e:
                print(f"Error forwarding circuit data: {e}")

    def _send_circuit_error(self, circuit_id: str, target: str, error: str):
        msg = {
            'type': MessageType.CIRCUIT_DESTROY.value if hasattr(MessageType, 'CIRCUIT_DESTROY') else 14,
            'circuit_id': circuit_id,
            'reason': error,
            'timestamp': time.time()
        }
        self.conn_mgr.send_message(target, msg)

    def _encrypt_for_hop(self, payload: dict, hop_id: str, circuit: Circuit) -> dict:
        key = circuit.layer_keys.get(hop_id)
        if not key:
            return payload
        encrypted_data = self.crypto.encrypt_with_key(json.dumps(payload).encode(), key)
        return {'encrypted': True, 'data': encrypted_data.hex(), 'hop': hop_id}

    def _decrypt_onion_layers(self, payload: dict, circuit: Circuit) -> dict:
        decrypted = payload
        for hop in reversed(circuit.path[:-1]):
            key = circuit.layer_keys.get(hop)
            if key and isinstance(decrypted, dict) and decrypted.get('encrypted'):
                try:
                    encrypted_bytes = bytes.fromhex(decrypted['data'])
                    decrypted_bytes = self.crypto.decrypt_with_key(encrypted_bytes, key)
                    decrypted = json.loads(decrypted_bytes.decode())
                except Exception as e:
                    print(f"Decryption error for hop {hop}: {e}")
                    break
        return decrypted

    def _deliver_message(self, message: dict, circuit_id: str):
        with self.lock:
            circuit = self.active_circuits.get(circuit_id)
            if circuit:
                circuit.last_activity = time.time()
        if hasattr(self.conn_mgr, 'on_incoming_message'):
            try:
                self.conn_mgr.on_incoming_message(message)
            except Exception as e:
                print(f"Error delivering message: {e}")

    def _destroy_circuit(self, circuit_id: str, reason: str):
        with self.lock:
            circuit = self.active_circuits.pop(circuit_id, None)
            if not circuit:
                return
            circuit.status = 'closed'
            if circuit.path:
                destroy_msg = {
                    'type': MessageType.CIRCUIT_DESTROY.value if hasattr(MessageType, 'CIRCUIT_DESTROY') else 14,
                    'circuit_id': circuit_id,
                    'reason': reason,
                    'timestamp': time.time()
                }
                try:
                    self.conn_mgr.send_message(circuit.path[0], destroy_msg)
                except:
                    pass
        print(f"🗑️ Circuit {circuit_id} destroyed: {reason}")

    def _destroy_transit_circuit(self, circuit_id: str):
        with self.lock:
            circuit = self.transit_circuits.pop(circuit_id, None)
            if circuit:
                print(f"🗑️ Transit circuit {circuit_id} destroyed")

    def handle_circuit_destroy(self, circuit_id: str, data: dict, sender_id: str):
        with self.lock:
            if circuit_id in self.active_circuits:
                self._destroy_circuit(circuit_id, data.get('reason', 'remote_request'))
            elif circuit_id in self.transit_circuits:
                self._destroy_transit_circuit(circuit_id)

    def _check_rate_limit(self, peer_id: str) -> bool:
        now = time.time()
        with self.lock:
            timestamps = self.rate_limits[peer_id]
            timestamps = [ts for ts in timestamps if now - ts < 60]
            if len(timestamps) >= self.max_requests_per_minute:
                return False
            timestamps.append(now)
            self.rate_limits[peer_id] = timestamps
            return True

    def get_stats(self) -> dict:
        with self.lock:
            total_bytes = sum(p.bytes_relayed for p in self.known_relays.values())
            total_msgs = sum(p.messages_relayed for p in self.known_relays.values())
            return {
                'enabled': self.is_enabled,
                'known_relays': len(self.known_relays),
                'active_circuits': len(self.active_circuits),
                'transit_circuits': len(self.transit_circuits),
                'relayed_msgs': self.stats['relayed_msgs'],
                'relayed_bytes': self.stats['relayed_bytes'],
                'circuits_created': self.stats['circuits_created'],
                'circuits_failed': self.stats['circuits_failed'],
                'rate_limit_hits': self.stats['rate_limit_hits'],
                'total_network_msgs': total_msgs,
                'total_network_bytes': total_bytes,
                'uptime': time.time() - (self.active_circuits[list(self.active_circuits.keys())[0]].created_at if self.active_circuits else time.time())
            }

    def get_relay_peers(self) -> List[dict]:
        with self.lock:
            return [{'peer_id': info.peer_id, 'ip': info.ip, 'bandwidth': info.bandwidth, 'reputation': info.reputation_score, 'messages_relayed': info.messages_relayed, 'last_seen': info.last_seen} for info in self.known_relays.values()]

    def shutdown(self):
        self._stop_event.set()
        with self.lock:
            for circuit_id in list(self.active_circuits.keys()):
                self._destroy_circuit(circuit_id, 'shutdown')
            self.transit_circuits.clear()
            self.known_relays.clear()