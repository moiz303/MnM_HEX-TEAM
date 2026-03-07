"""
File Transfer Manager for Mesh Network.

Provides secure, encrypted file transfers with chunked transmission,
retry logic, and comprehensive validation.
"""

import hashlib
import mimetypes
import os
import random
import socket
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Callable

from .protocols import ErrorCodes, Limits, MessageType, create_message


@dataclass
class FileInfo:
    """File metadata."""
    file_id: str
    filename: str
    file_size: int
    file_hash: str
    mime_type: str
    chunk_count: int
    sender_id: str
    receiver_id: str


@dataclass
class ChunkInfo:
    """Chunk information."""
    chunk_index: int
    data: bytes
    chunk_hash: str
    chunk_size: int
    sent_at: float = 0.0
    ack_received: bool = False
    retry_count: int = 0


@dataclass
class TransferSession:
    """File transfer session."""
    transfer_id: str
    file_info: FileInfo
    status: str = 'pending'
    direction: str = 'upload'
    local_path: Optional[str] = None
    target_ip: Optional[str] = None
    sender_ip: Optional[str] = None
    chunks: Dict[int, ChunkInfo] = field(default_factory=dict)
    completed_chunks: List[int] = field(default_factory=list)
    failed_chunks: List[int] = field(default_factory=list)
    started_at: float = 0.0
    completed_at: float = 0.0
    bytes_transferred: int = 0
    error_message: Optional[str] = None
    circuit_id: Optional[str] = None


class FileTransferManager:
    """Manages secure file transfers over mesh network.
    
    Features:
    - End-to-end encryption
    - Chunked transmission with retry logic
    - Comprehensive validation
    - Automatic cleanup
    - Progress tracking
    """

    def __init__(self, connection_manager, crypto_core, router=None):
        """Initialize file transfer manager.
        
        Args:
            connection_manager: Connection manager for peer communication
            crypto_core: Cryptographic core for encryption/decryption
            router: Onion router for relayed transfers (optional)
        """
        self.conn_mgr = connection_manager
        self.crypto = crypto_core
        self.router = router

        self.active_transfers: Dict[str, TransferSession] = {}
        self.pending_acks: Dict[str, threading.Event] = {}
        self.transfer_lock = threading.RLock()

        # Setup directories
        self.download_dir = Path('./downloads')
        self.upload_dir = Path('./uploads')
        self.download_dir.mkdir(exist_ok=True)
        self.upload_dir.mkdir(exist_ok=True)

        # Statistics
        self.stats = {
            'transfers_started': 0,
            'transfers_completed': 0,
            'transfers_failed': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }

        # Callbacks
        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_file_offer: Optional[Callable] = None

        self._stop_event = threading.Event()
        self._start_background_tasks()

    def _start_background_tasks(self):
        """Start background monitoring threads."""
        threading.Thread(target=self._timeout_monitor, daemon=True).start()
        threading.Thread(target=self._retry_manager, daemon=True).start()

    def _retry_chunk(self, session: TransferSession, chunk: ChunkInfo):
        """Retry sending a chunk."""
        try:
            success = self._send_chunk_with_ack(session, chunk)
            if not success:
                with self.transfer_lock:
                    if chunk.chunk_index not in session.failed_chunks:
                        session.failed_chunks.append(chunk.chunk_index)
        except Exception as e:
            print(f"[file_transfer] ❌ Retry failed for chunk {chunk.chunk_index}: {e}")
            with self.transfer_lock:
                if chunk.chunk_index not in session.failed_chunks:
                    session.failed_chunks.append(chunk.chunk_index)
                    
    def send_file(self, receiver_ip: str, file_path: str, receiver_device_id: str, circuit_id: Optional[str] = None) -> str:
        """Initiate file upload with validation.
        
        Args:
            receiver_ip: Target peer IP address
            file_path: Local file path to send
            receiver_device_id: Target device ID
            circuit_id: Circuit ID for relayed transfers (optional)
            
        Returns:
            Transfer ID for tracking
            
        Raises:
            ValueError: For invalid file path or type
            FileNotFoundError: If file doesn't exist
            RuntimeError: If failed to send file offer
        """
        # Validate file path
        if not self._validate_file_path(file_path):
            raise ValueError(f"Invalid file path or file too large: {file_path}")
            
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = path.stat().st_size
        if file_size > Limits.MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size} > {Limits.MAX_FILE_SIZE}")
        
        # Validate filename
        if len(path.name) > Limits.MAX_FILENAME_LENGTH:
            raise ValueError(f"Filename too long: {len(path.name)} > {Limits.MAX_FILENAME_LENGTH}")

        transfer_id = str(uuid.uuid4())
        file_hash = self._calculate_file_hash(file_path)
        chunk_count = (file_size + Limits.MAX_FILE_CHUNK - 1) // Limits.MAX_FILE_CHUNK
        
        # Validate MIME type
        mime_type = self._guess_mime_type(path.name)
        if mime_type.startswith('application/x-executable') or mime_type == 'application/x-msdownload':
            raise ValueError(f"Dangerous file type not allowed: {mime_type}")

        file_info = FileInfo(
            file_id=transfer_id,
            filename=path.name,
            file_size=file_size,
            file_hash=file_hash,
            mime_type=mime_type,
            chunk_count=chunk_count,
            sender_id=self.conn_mgr.peer_id if hasattr(self.conn_mgr, 'peer_id') else 'unknown',
            receiver_id=receiver_device_id
        )

        session = TransferSession(
            transfer_id=transfer_id,
            file_info=file_info,
            status='pending',
            direction='upload',
            local_path=file_path,
            circuit_id=circuit_id,
            target_ip=receiver_ip
        )
        print(f"[file_transfer] 📤 Initialized upload {transfer_id} to {receiver_ip}")

        with self.transfer_lock:
            self.active_transfers[transfer_id] = session
            self.stats['transfers_started'] += 1

        self._chunk_file(file_path, session)

        offer_msg = create_message(
            MessageType.FILE_OFFER,
            chat_id=receiver_device_id,
            file_id=transfer_id,
            filename=file_info.filename,
            size=file_info.file_size,
            mime_type=file_info.mime_type,
            encrypted_metadata=self._encrypt_metadata({
                'file_hash': file_info.file_hash,
                'chunk_count': file_info.chunk_count
            })
        )

        # Send initial offer
        if not self._send_to_peer(receiver_ip, offer_msg, circuit_id):
            raise RuntimeError(f"Failed to send file offer to {receiver_ip}")
            
        session.status = 'in_progress'
        session.started_at = time.time()

        threading.Thread(target=self._send_chunks_loop, args=(session,), daemon=True).start()
        return transfer_id

    def _chunk_file(self, file_path: str, session: TransferSession):
        """Split file into chunks."""
        with open(file_path, 'rb') as f:
            for i in range(session.file_info.chunk_count):
                data = f.read(Limits.MAX_FILE_CHUNK)
                chunk_hash = hashlib.sha256(data).hexdigest()
                session.chunks[i] = ChunkInfo(
                    chunk_index=i,
                    data=data,
                    chunk_hash=chunk_hash,
                    chunk_size=len(data)
                )
                data_preview = data[:50].hex()
                print(f"[file_transfer] 📦 Chunk {i}: {len(data)} bytes, hash={chunk_hash[:8]}...")

    def _send_chunks_loop(self, session: TransferSession):
        """Send chunks with exponential backoff retry logic."""
        try:
            failed_chunks = []
            retry_count = 0
            max_retries = 5
            
            while retry_count < max_retries:
                chunks_to_send = failed_chunks if failed_chunks else range(session.file_info.chunk_count)
                
                for chunk_index in chunks_to_send:
                    with self.transfer_lock:
                        if session.status != 'in_progress':
                            break
                        chunk = session.chunks.get(chunk_index)
                        if not chunk:
                            print(f"[file_transfer] ⚠️ Missing chunk {chunk_index}")
                            continue

                    success = self._send_chunk_with_ack(session, chunk)
                    if not success:
                        if chunk_index not in failed_chunks:
                            failed_chunks.append(chunk_index)
                        print(f"[file_transfer] ⚠️ Failed to send chunk {chunk_index}")
                    else:
                        if chunk_index in failed_chunks:
                            failed_chunks.remove(chunk_index)

                if not failed_chunks:
                    break
                    
                retry_count += 1
                # Exponential backoff with jitter
                base_delay = min(2 ** retry_count, 30)
                jitter = random.uniform(0.1, 0.3) * base_delay
                delay = base_delay + jitter
                print(f"[file_transfer] 🔄 Retry {retry_count}/{max_retries} for {len(failed_chunks)} chunks, wait {delay:.1f}s")
                time.sleep(delay)

            # Final status check
            with self.transfer_lock:
                if len(session.completed_chunks) >= session.file_info.chunk_count:
                    self._finalize_transfer(session, success=True)
                else:
                    failed_count = len(failed_chunks)
                    error = f"Failed to send {failed_count}/{session.file_info.chunk_count} chunks after {max_retries} retries"
                    self._finalize_transfer(session, success=False, error=error)
                    
        except Exception as e:
            print(f"[file_transfer] ❌ Error in chunk loop: {e}")
            import traceback
            traceback.print_exc()
            self._finalize_transfer(session, success=False, error=str(e))

    def _send_chunk_with_ack(self, session: TransferSession, chunk: ChunkInfo) -> bool:
        """Send encrypted chunk with ACK confirmation."""
        import base64
        session_key = self.crypto.get_session_key(session.file_info.receiver_id)
        
        # Encryption is mandatory
        if not session_key:
            print(f"[file_transfer] ❌ No session key for {session.file_info.receiver_id}")
            return False
            
        try:
            encrypted_data = self.crypto.encrypt_with_key(chunk.data, session_key)
            data_hex = base64.b64encode(encrypted_data).decode()
            print(f"[file_transfer] 📤 Chunk {chunk.chunk_index}: {len(chunk.data)}→{len(encrypted_data)} bytes")
        except Exception as e:
            print(f"[file_transfer] ❌ Encryption failed: {e}")
            return False

        msg = create_message(
            MessageType.FILE_CHUNK,
            file_id=session.transfer_id,
            chunk_index=chunk.chunk_index,
            total_chunks=session.file_info.chunk_count,
            data=data_hex,
            checksum=chunk.chunk_hash
        )
        
        # Store msg_id in chunk for ACK matching
        chunk.msg_id = msg.get('msg_id')

        import json
        msg_size = len(json.dumps(msg).encode())
        if msg_size > Limits.MAX_ENCRYPTED_SIZE:
            print(f"[file_transfer] ❌ Message too large: {msg_size} bytes")
            return False

        dest = session.target_ip or session.file_info.receiver_id
        print(f"[file_transfer] 📡 Sending chunk {chunk.chunk_index} to {dest}")
        
        # Send with exponential backoff retry
        for attempt in range(3):
            success = self._send_to_peer(dest, msg, session.circuit_id)
            if success:
                break
            print(f"[file_transfer] ⚠️ Attempt {attempt + 1} failed")
            retry_delay = min(0.5 * (2 ** attempt), 2.0)
            time.sleep(retry_delay)
        
        if not success:
            print(f"[file_transfer] ❌ Failed after 3 attempts")
            return False
        
        print(f"[file_transfer] ✅ Chunk {chunk.chunk_index} sent")
        chunk.sent_at = time.time()

        # Wait for ACK
        ack_received = self._wait_for_ack(session.transfer_id, chunk.chunk_index, timeout=10.0)
        if ack_received:
            with self.transfer_lock:
                if chunk.chunk_index not in session.completed_chunks:
                    session.completed_chunks.append(chunk.chunk_index)
            return True
        else:
            print(f"[file_transfer] ⚠️ No ACK for chunk {chunk.chunk_index}")
            return False

    def _wait_for_ack(self, transfer_id: str, chunk_index: int, timeout: float) -> bool:
        """Wait for ACK for a specific chunk"""
        ack_key = f"{transfer_id}:{chunk_index}"
        ack_event = threading.Event()
        
        with self.transfer_lock:
            self.pending_acks[ack_key] = ack_event
        
        return ack_event.wait(timeout)

    def _send_to_peer(self, peer_identifier: str, msg: dict, circuit_id: Optional[str] = None) -> bool:
        """Send a message to a peer. peer_identifier can be IP address or device_id.
        Circuit_id is used for relayed transfers. Returns True if sent successfully.
        """
        if circuit_id and self.router:
            # forward through relay network if a circuit exists
            try:
                self.router.relay_manager.handle_relay_data(circuit_id, msg, 'local')
                return True
            except Exception as e:
                print(f"[file_transfer] Relay send error: {e}")
                return False
        
        # Try to determine if peer_identifier is an IP address or device_id
        if self._is_ip_address(peer_identifier):
            # It's an IP address, send directly
            return self.conn_mgr.send_to_peer(peer_identifier, msg)
        else:
            # It's likely a device_id, try to find the corresponding IP
            peer_ip = self._find_ip_by_device_id(peer_identifier)
            if peer_ip:
                return self.conn_mgr.send_to_peer(peer_ip, msg)
            else:
                print(f"[file_transfer] Cannot find IP for device_id {peer_identifier}")
                return False

    def _is_ip_address(self, identifier: str) -> bool:
        """Check if the identifier looks like an IP address"""
        try:
            socket.inet_aton(identifier)
            return True
        except socket.error:
            return False

    def _find_ip_by_device_id(self, device_id: str) -> Optional[str]:
        """Find IP address by device_id using connection manager or discovery"""
        # Try to get from connection manager if it has peer mapping
        if hasattr(self.conn_mgr, 'get_peer_ip'):
            return self.conn_mgr.get_peer_ip(device_id)
        
        # Try to find through discovery if available
        if hasattr(self.conn_mgr, 'discovery') or hasattr(self, 'router'):
            discovery = getattr(self.conn_mgr, 'discovery', getattr(self.router, 'discovery', None))
            if discovery:
                for ip, info in discovery.get_all_peers().items():
                    if info.get('device_id') == device_id:
                        return ip
        
        return None

    def handle_file_offer(self, data: dict, sender_id: str):
        """Обработка предложения файла"""
        file_id = data.get('file_id')
        filename = data.get('filename', 'unknown')
        file_size = data.get('size', 0)
        encrypted_metadata = data.get('encrypted_metadata', '')
        metadata = self._decrypt_metadata(encrypted_metadata, sender_id)

        # Normalize sender_id to get the actual device_id for encryption
        actual_sender_device_id = self._normalize_sender_id(sender_id)

        session = TransferSession(
            transfer_id=file_id,
            file_info=FileInfo(
                file_id=file_id,
                filename=filename,
                file_size=file_size,
                file_hash=metadata.get('file_hash', ''),
                mime_type=data.get('mime_type', 'application/octet-stream'),
                chunk_count=metadata.get('chunk_count', 0),
                sender_id=actual_sender_device_id,  # Use device_id instead of IP
                receiver_id=self.conn_mgr.peer_id if hasattr(self.conn_mgr, 'peer_id') else 'unknown'
            ),
            status='pending',
            direction='download',
            local_path=str(self.download_dir / filename),
            sender_ip=sender_id  # Keep original IP for routing
        )

        with self.transfer_lock:
            self.active_transfers[file_id] = session

        print(f"📥 File offer received: {filename} ({file_size} bytes) from {sender_id}")
        if self.on_file_offer:
            self.on_file_offer(session)
        # automatically accept for now
        print(f"[file_transfer] auto-accepting file {file_id}")
        self.accept_file(file_id)

    def accept_file(self, transfer_id: str) -> bool:
        """Принять файл"""
        with self.transfer_lock:
            session = self.active_transfers.get(transfer_id)
            if not session:
                return False
            session.status = 'in_progress'
            session.started_at = time.time()

        Path(session.local_path).parent.mkdir(parents=True, exist_ok=True)
        open(session.local_path, 'wb').close()

        msg = create_message(
            MessageType.FILE_ACCEPT,
            chat_id=session.file_info.sender_id,  # Use device_id as chat_id for proper routing
            file_id=transfer_id,
            port=5000
        )

        # send ack/accept using stored sender IP for routing
        if session.sender_ip:
            self._send_to_peer(session.sender_ip, msg, None)
        else:
            self._send_to_peer(session.file_info.sender_id, msg, None)
        return True

    def handle_file_accept(self, data: dict, sender_id: str):
        """Обработка подтверждения принятия файла"""
        file_id = data.get('file_id')
        print(f"[file_transfer] 📥 File accept received for {file_id} from {sender_id}")
        
        with self.transfer_lock:
            session = self.active_transfers.get(file_id)
            if not session:
                print(f"[file_transfer] ❌ No transfer session found for {file_id}")
                return
            
            if session.direction == 'upload':
                print(f"[file_transfer] ✅ File {file_id} accepted by receiver, starting chunk transmission")
                # The chunk transmission is already started in send_file method
                # This accept is just a confirmation that receiver is ready
            else:
                print(f"[file_transfer] ⚠️ Received file_accept for download session, ignoring")

    def handle_delivery_receipt(self, data: dict, sender_id: str):
        """Обработка delivery receipt (ACK) для чанков"""
        in_response_to = data.get('in_response_to')
        status = data.get('status')
        
        if status != 'delivered':
            return
            
        print(f"[file_transfer] 📥 Delivery receipt for message {in_response_to} from {sender_id}")
        
        # Find the transfer and chunk that this ACK corresponds to
        with self.transfer_lock:
            for transfer_id, session in self.active_transfers.items():
                if session.direction == 'upload':
                    # Check each chunk to find the one with matching msg_id
                    for chunk_index, chunk in session.chunks.items():
                        if hasattr(chunk, 'msg_id') and chunk.msg_id == in_response_to:
                            if chunk_index not in session.completed_chunks:
                                print(f"[file_transfer] ✅ ACK received for chunk {chunk_index} of transfer {transfer_id}")
                                session.completed_chunks.append(chunk_index)
                                session.bytes_transferred += chunk.chunk_size
                                self.stats['bytes_sent'] += chunk.chunk_size
                                
                                # Signal ACK for this chunk
                                ack_key = f"{transfer_id}:{chunk_index}"
                                if ack_key in self.pending_acks:
                                    self.pending_acks[ack_key].set()
                                    del self.pending_acks[ack_key]
                                
                                # Check if transfer is complete
                                if len(session.completed_chunks) >= session.file_info.chunk_count:
                                    self._finalize_transfer(session, success=True)
                                return
                            break  # Found matching chunk, no need to check others

    def handle_file_chunk(self, data: dict, sender_id: str):
        """Обработка входящего чанка с улучшенной валидацией"""
        transfer_id = data.get('file_id')
        chunk_index = data.get('chunk_index')
        chunk_hash = data.get('checksum')
        chunk_data_hex = data.get('data', '')

        print(f"[file_transfer] handle_file_chunk called: transfer_id={transfer_id}, chunk_index={chunk_index}, sender_id={sender_id}")

        # Валидация входных данных
        if not all([transfer_id, chunk_index is not None, chunk_hash, chunk_data_hex]):
            print(f"[file_transfer] ❌ Invalid chunk data: missing required fields")
            return
            
        if chunk_index < 0 or chunk_index >= 10000:  # Reasonable limit
            print(f"[file_transfer] ❌ Invalid chunk index: {chunk_index}")
            return
            
        if len(chunk_data_hex) > Limits.MAX_ENCRYPTED_SIZE * 2:  # Base64 can double size
            print(f"[file_transfer] ❌ Chunk data too large: {len(chunk_data_hex)} chars")
            return

        with self.transfer_lock:
            session = self.active_transfers.get(transfer_id)
            if not session:
                print(f"[file_transfer] no session found for transfer_id={transfer_id}, available: {list(self.active_transfers.keys())}")
                return

            # Use the device_id from the session for encryption (already normalized)
            actual_sender_id = session.file_info.sender_id

            # Проверка дубликатов
            if chunk_index in session.completed_chunks:
                print(f"[file_transfer] ⚠️ Duplicate chunk {chunk_index}, sending ACK only")
                self._send_chunk_ack(transfer_id, chunk_index, sender_id, data.get('msg_id', ''))
                return

            try:
                import base64
                session_key = self.crypto.get_session_key(actual_sender_id)
                
                # Декодирование из base64
                try:
                    encrypted_bytes = base64.b64decode(chunk_data_hex, validate=True)
                except Exception as e:
                    print(f"[file_transfer] ❌ Invalid base64 data for chunk {chunk_index}: {e}")
                    return
                
                # Дешифрование обязательно
                if not session_key:
                    print(f"[file_transfer] ❌ No session key for {actual_sender_id}, cannot decrypt chunk {chunk_index}")
                    return
                    
                try:
                    decrypted_data = self.crypto.decrypt_with_key(encrypted_bytes, session_key)
                except Exception as e:
                    print(f"[file_transfer] ❌ Decryption failed for chunk {chunk_index}: {e}")
                    return
                    
                # Валидация размера чанка
                expected_size = Limits.MAX_FILE_CHUNK
                if chunk_index == session.file_info.chunk_count - 1:  # Last chunk
                    expected_size = session.file_info.file_size % Limits.MAX_FILE_CHUNK
                    if expected_size == 0:
                        expected_size = Limits.MAX_FILE_CHUNK
                        
                if len(decrypted_data) != expected_size:
                    print(f"[file_transfer] ❌ Chunk size mismatch: got {len(decrypted_data)}, expected {expected_size}")
                    return
                    
            except Exception as e:
                print(f"[file_transfer] ❌ Processing error for chunk {chunk_index}: {e}")
                import traceback
                traceback.print_exc()
                return

            # Строгая проверка хеша
            actual_hash = hashlib.sha256(decrypted_data).hexdigest()
            if actual_hash != chunk_hash:
                print(f"[file_transfer] ❌ Hash mismatch chunk {chunk_index}: expected {chunk_hash[:16]} got {actual_hash[:16]}")
                return

            # Запись чанка
            try:
                self._write_chunk(session.local_path, chunk_index, decrypted_data)
            except Exception as e:
                print(f"[file_transfer] ❌ Failed to write chunk {chunk_index}: {e}")
                return
                
            session.completed_chunks.append(chunk_index)
            session.bytes_transferred += len(decrypted_data)
            self.stats['bytes_received'] += len(decrypted_data)

            # Отправка ACK
            self._send_chunk_ack(transfer_id, chunk_index, sender_id, data.get('msg_id', ''))

            # Проверка завершения
            if len(session.completed_chunks) >= session.file_info.chunk_count:
                self._finalize_transfer(session, success=True)

        if self.on_progress:
            progress = len(session.completed_chunks) / session.file_info.chunk_count * 100
            self.on_progress(transfer_id, progress, session.bytes_transferred)
            
    def _send_chunk_ack(self, transfer_id: str, chunk_index: int, sender_id: str, msg_id: str):
        """Отправка ACK для чанка"""
        ack_msg = create_message(
            MessageType.DELIVERY_RECEIPT,
            chat_id=sender_id,  # Use sender_id directly (this is the IP for routing)
            in_response_to=msg_id,
            status='delivered'
        )
        # Use the original IP address for routing, not the device_id
        self.conn_mgr.send_to_peer(sender_id, ack_msg)
        
        # Signal ACK for this chunk
        ack_key = f"{transfer_id}:{chunk_index}"
        with self.transfer_lock:
            if ack_key in self.pending_acks:
                self.pending_acks[ack_key].set()
                del self.pending_acks[ack_key]

    def _normalize_sender_id(self, sender_id: str) -> str:
        """Convert sender_id to device_id format for encryption purposes"""
        # If it's already a device_id (hex-like), return as is
        if len(sender_id) >= 16 and all(c in '0123456789abcdefABCDEF' for c in sender_id):
            return sender_id
        
        # If it's an IP address, try to find the corresponding device_id
        if self._is_ip_address(sender_id):
            device_id = self._find_device_id_by_ip(sender_id)
            if device_id:
                return device_id
            else:
                # As a fallback, try to find any session that might be associated with this IP
                # by checking if we have any sessions where we can cross-reference
                device_id = self._find_device_id_by_session_lookup(sender_id)
                if device_id:
                    return device_id
        
        # Return original if we can't determine
        return sender_id

    def _find_device_id_by_session_lookup(self, ip: str) -> Optional[str]:
        """Fallback method: try to find device_id by checking existing sessions"""
        # This is a fallback when discovery doesn't have the peer
        # We'll try to find sessions that might be associated with this IP
        if hasattr(self, 'router') and self.router:
            # Try to get from router's discovery
            discovery = getattr(self.router, 'discovery', None)
            if discovery:
                info = discovery.get_all_peers().get(ip)
                if info:
                    device_id = info.get('device_id')
                    if device_id:
                        return device_id
        
        # If we have the connection manager, try to get peer info from it
        if hasattr(self.conn_mgr, 'discovery'):
            discovery = self.conn_mgr.discovery
            if discovery:
                info = discovery.get_all_peers().get(ip)
                if info:
                    device_id = info.get('device_id')
                    if device_id:
                        return device_id
        
        # Additional fallback: try to find device_id from crypto sessions
        # This is a last resort when discovery fails
        if hasattr(self, 'crypto') and hasattr(self.crypto, '_session_keys'):
            sessions = list(self.crypto._session_keys.values())
            if sessions:
                # If there's only one session, use it (most likely the correct one)
                if len(sessions) == 1:
                    return sessions[0].peer_id
                else:
                    # If multiple sessions, try to find one that's not our own device_id
                    our_id = getattr(self.crypto, 'device_id', None)
                    for session in sessions:
                        if session.peer_id != our_id:
                            return session.peer_id
                    # If all else fails, use the first one
                    return sessions[0].peer_id
        
        return None

    def _find_device_id_by_ip(self, ip: str) -> Optional[str]:
        """Find device_id by IP address using discovery"""
        if hasattr(self.conn_mgr, 'discovery') or hasattr(self, 'router'):
            discovery = getattr(self.conn_mgr, 'discovery', getattr(self.router, 'discovery', None))
            if discovery:
                info = discovery.get_all_peers().get(ip)
                if info:
                    return info.get('device_id')
        return None

    def _write_chunk(self, file_path: str, chunk_index: int, data: bytes):
        """Запись чанка в файл по смещению"""
        offset = chunk_index * Limits.MAX_FILE_CHUNK
        print(f"[file_transfer] writing chunk {chunk_index}, offset {offset}, size {len(data)}")
        with open(file_path, 'r+b') as f:
            f.seek(offset)
            bytes_written = f.write(data)
            print(f"[file_transfer] wrote {bytes_written} bytes at offset {offset}")

    def handle_file_complete(self, data: dict, sender_id: str):
        """Обработка завершения передачи"""
        transfer_id = data.get('file_id')
        with self.transfer_lock:
            session = self.active_transfers.get(transfer_id)
            if session:
                self._finalize_transfer(session, success=True)

    def _finalize_transfer(self, session: TransferSession, success: bool, error: str = None):
        """Завершение сессии передачи"""
        if session.status in ['completed', 'failed']:
            return

        if success:
            session.status = 'completed'
            session.completed_at = time.time()
            self.stats['transfers_completed'] += 1

            if session.direction == 'download':
                actual_hash = self._calculate_file_hash(session.local_path)
                if actual_hash != session.file_info.file_hash:
                    session.status = 'failed'
                    session.error_message = "File hash verification failed"
                    self.stats['transfers_completed'] -= 1
                    self.stats['transfers_failed'] += 1
                else:
                    print(f"[file_transfer] download completed, file {session.local_path} size {os.path.getsize(session.local_path) if os.path.exists(session.local_path) else 0}")

            if session.direction == 'upload':
                msg = create_message(
                    MessageType.FILE_COMPLETE,
                    file_id=session.transfer_id,
                    chat_id=session.file_info.receiver_id
                )
                dest = session.target_ip or session.file_info.receiver_id
                self._send_to_peer(dest, msg, session.circuit_id)

            if self.on_complete:
                self.on_complete(session.transfer_id, session.status)
            print(f"✅ Transfer {session.transfer_id} completed: {session.file_info.filename}")
        else:
            session.status = 'failed'
            session.error_message = error
            self.stats['transfers_failed'] += 1
            if self.on_error:
                self.on_error(session.transfer_id, error)
            print(f"❌ Transfer {session.transfer_id} failed: {error}")

    def _calculate_file_hash(self, file_path: str) -> str:
        """SHA256 хеш файла"""
        sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                sha256.update(chunk)
        return sha256.hexdigest()

    def _guess_mime_type(self, filename: str) -> str:
        """Улучшенное определение MIME типа с валидацией"""
        # Валидация имени файла
        if not filename or len(filename) > Limits.MAX_FILENAME_LENGTH:
            return 'application/octet-stream'
            
        # Проверка на опасные расширения
        dangerous_exts = {'.exe', '.bat', '.cmd', '.com', '.pif', '.scr', '.vbs', '.js', '.jar', '.app'}
        ext = Path(filename).suffix.lower()
        
        if ext in dangerous_exts:
            print(f"[file_transfer] ⚠️ Potentially dangerous file extension: {ext}")
            return 'application/octet-stream'
        
        # Использование mimetypes для лучшего определения
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type
            
        # Fallback к ручному маппингу
        mime_map = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.mp4': 'video/mp4',
            '.avi': 'video/x-msvideo',
            '.mov': 'video/quicktime',
            '.zip': 'application/zip',
            '.rar': 'application/x-rar-compressed',
            '.tar': 'application/x-tar',
            '.gz': 'application/gzip',
            '.doc': 'application/msword',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            '.xls': 'application/vnd.ms-excel',
            '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }
        
        return mime_map.get(ext, 'application/octet-stream')

    def _find_device_id_by_session_lookup(self, ip: str) -> Optional[str]:
        """Fallback method: try to find device_id by checking existing sessions"""
        # This is a fallback when discovery doesn't have the peer
        # We'll try to find sessions that might be associated with this IP
        if hasattr(self, 'router') and self.router:
            # Try to get from router's discovery
            discovery = getattr(self.router, 'discovery', None)
            if discovery:
                info = discovery.get_all_peers().get(ip)
                if info:
                    device_id = info.get('device_id')
                    if device_id:
                        return device_id
        return None

    def _encrypt_metadata(self, metadata: dict) -> str:
        import json
        data = json.dumps(metadata).encode()
        return data.hex()

    def _decrypt_metadata(self, encrypted_hex: str, sender_id: str) -> dict:
        import json
        try:
            data = bytes.fromhex(encrypted_hex)
            return json.loads(data.decode())
        except:
            return {}

    def _timeout_monitor(self):
        """Монитор таймаутов с улучшенным cleanup"""
        while not self._stop_event.is_set():
            time.sleep(10)  # Увеличим интервал для снижения нагрузки
            now = time.time()
            with self.transfer_lock:
                # Cleanup старых передач
                self._cleanup_old_transfers(now)
                
                # Проверка таймаутов чанков
                for session in list(self.active_transfers.values()):
                    if session.status != 'in_progress':
                        continue
                    
                    # Проверка общего таймаута передачи (30 минут)
                    if now - session.started_at > 1800:  # 30 minutes
                        print(f"[file_transfer] ❌ Transfer {session.transfer_id} timed out")
                        self._finalize_transfer(session, success=False, error="Transfer timeout")
                        continue
                        
                    for chunk in session.chunks.values():
                        if chunk.sent_at > 0 and not chunk.ack_received:
                            if now - chunk.sent_at > 60.0:  # 60 секунд timeout
                                chunk.retry_count += 1
                                if chunk.retry_count > 5:
                                    print(f"[file_transfer] ❌ Chunk {chunk.chunk_index} max retries exceeded")
                                    if chunk.chunk_index not in session.failed_chunks:
                                        session.failed_chunks.append(chunk.chunk_index)
    
    def _cleanup_old_transfers(self, current_time: float):
        """Очистка старых завершенных передач"""
        cleanup_threshold = 3600  # 1 час
        transfers_to_remove = []
        
        for transfer_id, session in self.active_transfers.items():
            # Удаляем завершенные передачи старше часа
            if session.status in ['completed', 'failed', 'cancelled']:
                completion_time = session.completed_at if session.completed_at > 0 else session.started_at
                if current_time - completion_time > cleanup_threshold:
                    transfers_to_remove.append(transfer_id)
                    
        # Удаляем старые передачи
        for transfer_id in transfers_to_remove:
            session = self.active_transfers.get(transfer_id)
            if session:
                print(f"[file_transfer] 🧹 Cleaning up old transfer {transfer_id}")
                # Очистка временных файлов для неудачных загрузок
                if session.status == 'failed' and session.direction == 'download':
                    try:
                        if session.local_path and os.path.exists(session.local_path):
                            os.remove(session.local_path)
                            print(f"[file_transfer] 🗑️ Removed incomplete file {session.local_path}")
                    except Exception as e:
                        print(f"[file_transfer] ⚠️ Failed to remove file {session.local_path}: {e}")
                        
                del self.active_transfers[transfer_id]
                
        # Cleanup старых ACK событий
        acks_to_remove = []
        for ack_key, event in self.pending_acks.items():
            # Удаляем ACK события старше 5 минут
            if hasattr(event, '_created_at'):
                if current_time - event._created_at > 300:
                    acks_to_remove.append(ack_key)
                    
        for ack_key in acks_to_remove:
            del self.pending_acks[ack_key]
            
    def _retry_manager(self):
        """Улучшенный менеджер retry с экспоненциальным backoff"""
        while not self._stop_event.is_set():
            time.sleep(5)  # Увеличим интервал
            now = time.time()
            with self.transfer_lock:
                for session in list(self.active_transfers.values()):
                    if session.status != 'in_progress':
                        continue
                        
                    # Retry для failed chunks
                    chunks_to_retry = []
                    for chunk_index in list(session.failed_chunks):
                        chunk = session.chunks.get(chunk_index)
                        if chunk and chunk.retry_count < 5:
                            # Экспоненциальный backoff
                            delay = min(300, 30 * (2 ** chunk.retry_count))  # Max 5 минут
                            if now - chunk.sent_at > delay:
                                chunks_to_retry.append(chunk_index)
                                
                    for chunk_index in chunks_to_retry:
                        chunk = session.chunks.get(chunk_index)
                        if chunk:
                            session.failed_chunks.remove(chunk_index)
                            print(f"[file_transfer] 🔄 Retrying chunk {chunk_index}, attempt {chunk.retry_count + 1}")
                            # Отправляем в отдельном потоке чтобы не блокировать
                            threading.Thread(
                                target=self._retry_chunk, 
                                args=(session, chunk), 
                                daemon=True
                            ).start()

    def get_transfer_info(self, transfer_id: str) -> Optional[dict]:
        with self.transfer_lock:
            session = self.active_transfers.get(transfer_id)
            if not session:
                return None
            progress = len(session.completed_chunks) / session.file_info.chunk_count * 100 if session.file_info.chunk_count > 0 else 0
            return {
                'transfer_id': session.transfer_id,
                'filename': session.file_info.filename,
                'file_size': session.file_info.file_size,
                'status': session.status,
                'direction': session.direction,
                'progress': progress,
                'bytes_transferred': session.bytes_transferred,
                'completed_chunks': len(session.completed_chunks),
                'total_chunks': session.file_info.chunk_count,
                'started_at': session.started_at,
                'error': session.error_message
            }

    def get_all_transfers(self) -> List[dict]:
        with self.transfer_lock:
            return [info for info in [self.get_transfer_info(tid) for tid in self.active_transfers.keys()] if info]

    def cancel_transfer(self, transfer_id: str) -> bool:
        with self.transfer_lock:
            session = self.active_transfers.get(transfer_id)
            if not session:
                return False
            session.status = 'cancelled'
            msg = create_message(
                MessageType.FILE_ERROR,
                file_id=transfer_id,
                chat_id=session.file_info.receiver_id if session.direction == 'upload' else session.file_info.sender_id,
                error_code=1,
                error_message='user_cancelled'
            )
            target = session.file_info.receiver_id if session.direction == 'upload' else session.file_info.sender_id
            self.conn_mgr.send_to_peer(target, msg)
            return True

    def shutdown(self):
        self._stop_event.set()
        with self.transfer_lock:
            for session in self.active_transfers.values():
                if session.status == 'in_progress':
                    session.status = 'failed'
                    session.error_message = "Shutdown"

    def _validate_file_path(self, file_path: str) -> bool:
        """Валидация пути к файлу"""
        try:
            path = Path(file_path)
            
            # Проверка на path traversal
            if '..' in path.parts:
                return False
            
            # Разрешаем абсолютные пути если они в разрешенных директориях
            if str(path).startswith('/'):
                # Проверяем что путь в разрешенной директории (downloads/uploads)
                allowed_dirs = ['/downloads/', '/uploads/', './downloads/', './uploads/']
                if not any(str(path).startswith(allowed_dir) for allowed_dir in allowed_dirs):
                    return False
            elif str(path).startswith('./'):
                # Относительные пути должны начинаться с downloads/ или uploads/
                if not (str(path).startswith('./downloads/') or str(path).startswith('./uploads/')):
                    return False
            
            # Проверка размера
            if path.stat().st_size > Limits.MAX_FILE_SIZE:
                return False
            
            return True
        except Exception:
            return False