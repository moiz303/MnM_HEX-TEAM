"""
Менеджер передачи файлов через Mesh-сеть.
Интегрируется с существующим OnionRouter и AutoRelayManager.
"""

import threading
import time
import hashlib
import uuid
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from .protocols import MessageType, Limits, create_message


@dataclass
class FileInfo:
    """Метаданные файла"""
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
    """Информация о чанке"""
    chunk_index: int
    data: bytes
    chunk_hash: str
    chunk_size: int
    sent_at: float = 0.0
    ack_received: bool = False
    retry_count: int = 0


@dataclass
class TransferSession:
    """Сессия передачи файла"""
    transfer_id: str
    file_info: FileInfo
    status: str = 'pending'
    direction: str = 'upload'
    local_path: Optional[str] = None
    # store IP address of the peer (used for sending chunks/acks)
    target_ip: Optional[str] = None
    # for downloads, remember sender IP separately
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
    """Менеджер передачи файлов."""

    def __init__(self, connection_manager, crypto_core, router=None):
        self.conn_mgr = connection_manager
        self.crypto = crypto_core
        self.router = router

        self.active_transfers: Dict[str, TransferSession] = {}
        self.pending_acks: Dict[str, threading.Event] = {}
        self.transfer_lock = threading.RLock()

        self.download_dir = Path('./downloads')
        self.upload_dir = Path('./uploads')
        self.download_dir.mkdir(exist_ok=True)
        self.upload_dir.mkdir(exist_ok=True)

        self.stats = {
            'transfers_started': 0,
            'transfers_completed': 0,
            'transfers_failed': 0,
            'bytes_sent': 0,
            'bytes_received': 0
        }

        self.on_progress: Optional[Callable] = None
        self.on_complete: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        self.on_file_offer: Optional[Callable] = None

        self._stop_event = threading.Event()
        self._start_background_tasks()

    def _start_background_tasks(self):
        threading.Thread(target=self._timeout_monitor, daemon=True).start()
        threading.Thread(target=self._retry_manager, daemon=True).start()

    def send_file(self, receiver_ip: str, file_path: str, receiver_device_id: str, circuit_id: Optional[str] = None) -> str:
        """Инициация отправки файла."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = path.stat().st_size
        if file_size > Limits.MAX_FILE_SIZE:
            raise ValueError(f"File too large: {file_size} > {Limits.MAX_FILE_SIZE}")

        transfer_id = str(uuid.uuid4())
        file_hash = self._calculate_file_hash(file_path)
        chunk_count = (file_size + Limits.MAX_FILE_CHUNK - 1) // Limits.MAX_FILE_CHUNK

        file_info = FileInfo(
            file_id=transfer_id,
            filename=path.name,
            file_size=file_size,
            file_hash=file_hash,
            mime_type=self._guess_mime_type(path.name),
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
        print(f"[file_transfer] initialized upload session {transfer_id} to {receiver_ip} device={receiver_device_id}")

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

        # send initial offer using the IP address
        self._send_to_peer(receiver_ip, offer_msg, circuit_id)
        session.status = 'in_progress'
        session.started_at = time.time()

        threading.Thread(target=self._send_chunks_loop, args=(session,), daemon=True).start()
        return transfer_id

    def _chunk_file(self, file_path: str, session: TransferSession):
        """Разбиение файла на чанки"""
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
                data_first_50 = data[:50].hex()
                print(f"[file_transfer] chunk {i}: size={len(data)}, hash={chunk_hash[:8]}..., first50={data_first_50}")

    def _send_chunks_loop(self, session: TransferSession):
        """Цикл отправки чанков с flow control"""
        max_parallel = 3
        next_chunk = 0

        while session.status == 'in_progress':
            with self.transfer_lock:
                if len(session.completed_chunks) >= session.file_info.chunk_count:
                    self._finalize_transfer(session, success=True)
                    break

                pending = len(session.chunks) - len(session.completed_chunks) - len(session.failed_chunks)
                if pending >= max_parallel:
                    time.sleep(0.1)
                    continue

                if next_chunk < session.file_info.chunk_count:
                    chunk = session.chunks[next_chunk]
                    self._send_chunk(session, chunk)
                    next_chunk += 1

            time.sleep(0.05)

            if time.time() - session.started_at > 3600:
                self._finalize_transfer(session, success=False, error="Transfer timeout")

    def _send_chunk(self, session: TransferSession, chunk: ChunkInfo):
        """Отправка одного чанка"""
        import base64
        session_key = self.crypto.get_session_key(session.file_info.receiver_id)
        if session_key:
            encrypted_data = self.crypto.encrypt_with_key(chunk.data, session_key)
            data_hex = base64.b64encode(encrypted_data).decode()
            print(f"[file_transfer] SEND chunk {chunk.chunk_index}: orig={len(chunk.data)}, encr={len(encrypted_data)}, b64_len={len(data_hex)}, hash={chunk.chunk_hash[:8]}...")
        else:
            data_hex = base64.b64encode(chunk.data).decode()
            print(f"[file_transfer] SEND chunk {chunk.chunk_index}: size={len(chunk.data)}, b64_len={len(data_hex)}, hash={chunk.chunk_hash[:8]}..., no_encrypt")

        msg = create_message(
            MessageType.FILE_CHUNK,
            file_id=session.transfer_id,
            chunk_index=chunk.chunk_index,
            total_chunks=session.file_info.chunk_count,
            data=data_hex,
            checksum=chunk.chunk_hash
        )

        import json
        msg_size = len(json.dumps(msg).encode())
        print(f"[file_transfer] chunk {chunk.chunk_index} message size: {msg_size} bytes, hash={chunk.chunk_hash[:8]}...")
        if msg_size > 64000:
            print(f"[file_transfer] ⚠️ WARNING: chunk {chunk.chunk_index} message exceeds 64KB threshold!")

        # use target_ip stored in session (should be the peer's IP)
        dest = session.target_ip or session.file_info.receiver_id
        print(f"[file_transfer] sending chunk {chunk.chunk_index} to {dest}")
        success = self._send_to_peer(dest, msg, session.circuit_id)
        if not success:
            print(f"[file_transfer] ⚠️  Failed to send chunk {chunk.chunk_index} to {dest}")
        else:
            print(f"[file_transfer] ✅ Chunk {chunk.chunk_index} sent successfully")
        chunk.sent_at = time.time()

        ack_event = threading.Event()
        ack_key = f"{session.transfer_id}:{chunk.chunk_index}"
        self.pending_acks[ack_key] = ack_event

        if not ack_event.wait(timeout=30.0):
            with self.transfer_lock:
                chunk.retry_count += 1
                if chunk.retry_count >= 5:
                    session.failed_chunks.append(chunk.chunk_index)

        with self.transfer_lock:
            if ack_key in self.pending_acks:
                del self.pending_acks[ack_key]

    def _send_to_peer(self, peer_ip: str, msg: dict, circuit_id: Optional[str] = None) -> bool:
        """Send a message to a peer IP (ignores device_id confusion).
        Circuit_id is currently only used for relaying; router logic is minimal.
        Returns True if sent successfully, False otherwise.
        """
        if circuit_id and self.router:
            # forward through relay network if a circuit exists
            try:
                self.router.relay_manager.handle_relay_data(circuit_id, msg, 'local')
                return True
            except Exception as e:
                print(f"[file_transfer] Relay send error: {e}")
                return False
        else:
            # always send directly by IP
            return self.conn_mgr.send_to_peer(peer_ip, msg)

    def handle_file_offer(self, data: dict, sender_id: str):
        """Обработка предложения файла"""
        file_id = data.get('file_id')
        filename = data.get('filename', 'unknown')
        file_size = data.get('size', 0)
        encrypted_metadata = data.get('encrypted_metadata', '')
        metadata = self._decrypt_metadata(encrypted_metadata, sender_id)

        session = TransferSession(
            transfer_id=file_id,
            file_info=FileInfo(
                file_id=file_id,
                filename=filename,
                file_size=file_size,
                file_hash=metadata.get('file_hash', ''),
                mime_type=data.get('mime_type', 'application/octet-stream'),
                chunk_count=metadata.get('chunk_count', 0),
                sender_id=sender_id,
                receiver_id=self.conn_mgr.peer_id if hasattr(self.conn_mgr, 'peer_id') else 'unknown'
            ),
            status='pending',
            direction='download',
            local_path=str(self.download_dir / filename),
            sender_ip=sender_id
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
            chat_id=session.file_info.sender_id,
            file_id=transfer_id,
            port=5000
        )

        # send ack/accept using stored sender IP
        if session.sender_ip:
            self._send_to_peer(session.sender_ip, msg, None)
        else:
            self._send_to_peer(session.file_info.sender_id, msg, None)
        return True

    def handle_file_chunk(self, data: dict, sender_id: str):
        """Обработка входящего чанка"""
        transfer_id = data.get('file_id')
        chunk_index = data.get('chunk_index')
        chunk_hash = data.get('checksum')
        chunk_data_hex = data.get('data', '')

        print(f"[file_transfer] handle_file_chunk called: transfer_id={transfer_id}, chunk_index={chunk_index}, sender_id={sender_id}")

        with self.transfer_lock:
            session = self.active_transfers.get(transfer_id)
            if not session:
                print(f"[file_transfer] no session found for transfer_id={transfer_id}, available: {list(self.active_transfers.keys())}")
                return

            try:
                import base64
                session_key = self.crypto.get_session_key(sender_id)
                
                # Decode from base64
                print(f"[file_transfer] RECV chunk {chunk_index}: encrypted_b64_len={len(chunk_data_hex)}")
                encrypted_bytes = base64.b64decode(chunk_data_hex)
                print(f"[file_transfer] RECV chunk {chunk_index}: encrypted_bytes_len={len(encrypted_bytes)}")
                
                if session_key:
                    decrypted_data = self.crypto.decrypt_with_key(encrypted_bytes, session_key)
                else:
                    decrypted_data = encrypted_bytes
                    print(f"[file_transfer] RECV chunk {chunk_index}: no session key, using raw data")
            except Exception as e:
                print(f"[file_transfer] Decryption/decoding error for chunk {chunk_index}: {e}")
                import traceback
                traceback.print_exc()
                return

            actual_hash = hashlib.sha256(decrypted_data).hexdigest()
            expected_hash = chunk_hash
            data_first_50 = decrypted_data[:50].hex()
            print(f"[file_transfer] RCV_HASH chunk {chunk_index}: exp={expected_hash[:8]}..., got={actual_hash[:8]}..., size={len(decrypted_data)}, first50={data_first_50}")
            if actual_hash != expected_hash:
                print(f"[file_transfer] ❌ Hash mismatch chunk {chunk_index}: expected {expected_hash} got {actual_hash}")
                return

            self._write_chunk(session.local_path, chunk_index, decrypted_data)
            session.completed_chunks.append(chunk_index)
            session.bytes_transferred += len(decrypted_data)
            self.stats['bytes_received'] += len(decrypted_data)

            if len(session.completed_chunks) >= session.file_info.chunk_count:
                self._finalize_transfer(session, success=True)

        ack_msg = create_message(
            MessageType.DELIVERY_RECEIPT,
            chat_id=session.file_info.sender_id,
            in_response_to=data.get('msg_id', ''),
            status='delivered'
        )
        self.conn_mgr.send_message(sender_id, ack_msg)

        if self.on_progress:
            progress = len(session.completed_chunks) / session.file_info.chunk_count * 100
            self.on_progress(transfer_id, progress, session.bytes_transferred)

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
        """Определение MIME типа по расширению"""
        ext = Path(filename).suffix.lower()
        mime_map = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.png': 'image/png',
            '.mp4': 'video/mp4',
            '.zip': 'application/zip',
        }
        return mime_map.get(ext, 'application/octet-stream')

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
        while not self._stop_event.is_set():
            time.sleep(5)
            now = time.time()
            with self.transfer_lock:
                for session in list(self.active_transfers.values()):
                    if session.status != 'in_progress':
                        continue
                    for chunk in session.chunks.values():
                        if chunk.sent_at > 0 and not chunk.ack_received:
                            if now - chunk.sent_at > 30.0:
                                chunk.retry_count += 1

    def _retry_manager(self):
        while not self._stop_event.is_set():
            time.sleep(2)
            with self.transfer_lock:
                for session in list(self.active_transfers.values()):
                    if session.status != 'in_progress':
                        continue
                    for chunk_index in list(session.failed_chunks):
                        chunk = session.chunks.get(chunk_index)
                        if chunk and chunk.retry_count < 5:
                            session.failed_chunks.remove(chunk_index)
                            self._send_chunk(session, chunk)

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
            self.conn_mgr.send_message(target, msg)
            return True

    def shutdown(self):
        self._stop_event.set()
        with self.transfer_lock:
            for session in self.active_transfers.values():
                if session.status == 'in_progress':
                    session.status = 'failed'
                    session.error_message = "Shutdown"