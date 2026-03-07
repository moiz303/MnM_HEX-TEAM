import os
import threading
import time
import json
import socket
import uuid
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import backend classes (runs in-process)
from main import SecureMessenger
from api import LocalAPI

SOCKET_PATH = "/tmp/secure_chat.sock"

BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')


class UnixLocalAPIClient:
    def __init__(self, path):
        self.path = path
        self._id = 1
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            self.sock.connect(self.path)
            self.sock_file = self.sock.makefile('rwb')
        except Exception:
            self.sock = None

    def call(self, method, params=None):
        if not self.sock:
            raise RuntimeError('No connection to LocalAPI')
        req = {'id': self._id, 'method': method, 'params': params or {}}
        self._id += 1
        data = (json.dumps(req) + '\n').encode()
        self.sock.sendall(data)
        line = self.sock_file.readline()
        if not line:
            raise RuntimeError('Empty response from LocalAPI')
        resp = json.loads(line.decode())
        if 'error' in resp:
            raise RuntimeError(resp['error'])
        return resp.get('result')


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
    CORS(app)

    # Prefer connecting to an existing LocalAPI over UNIX socket (another process).
    # If that fails, start SecureMessenger in-process and expose a LocalAPI server.
    local_api = None
    remote_client = None
    messenger = None

    try:
        remote_client = UnixLocalAPIClient(SOCKET_PATH)
        if remote_client.sock:
            print('[web] Connected to existing LocalAPI via UNIX socket')
        else:
            remote_client = None
    except Exception:
        remote_client = None

    if not remote_client:
        try:
            # Generate unique username for web instance
            import uuid
            web_user_id = str(uuid.uuid4())[:8]
            username = f'web_user_{web_user_id}'
            messenger = SecureMessenger(username)
            local_api = LocalAPI(messenger)
            threading.Thread(target=local_api.start, daemon=True).start()
            print('[web] Started in-process SecureMessenger')
        except Exception as e:
            print(f"[web] Could not start SecureMessenger: {e}")

    if not local_api and not remote_client:
        print('[web] Falling back to MockBackend')

        class MockBackend:
            def __init__(self):
                self.username = 'web_user'
                self.device_id = 'mock-device'
                self.start_time = time.time()
                self.active_chats = {}
                self.db = self
                self.discovery = self

            def get_all_peers(self):
                return {}

            def get_peer_by_name(self, name):
                return None

            def start_chat(self, peer_name):
                return False

            def send_message(self, peer_name, text):
                return False

            def get_conversation(self, chat_id, limit=50):
                return []

        messenger = MockBackend()

    # Serve index and static files
    @app.route('/')
    def index():
        return send_from_directory(FRONTEND_DIR, 'index.html')

    @app.route('/<path:filename>')
    def static_files(filename):
        file_path = os.path.join(FRONTEND_DIR, filename)
        if not os.path.exists(file_path):
            abort(404)
        return send_from_directory(FRONTEND_DIR, filename)

    def call_handler(name, params):
        params = params or {}

        # In-process LocalAPI: call handler functions directly
        if local_api:
            handler = local_api.methods.get(name)
            if not handler:
                return {'error': f'method {name} not found'}, 404
            try:
                result = handler(params)
                return result, 200
            except Exception as e:
                return {'error': str(e)}, 400

        # Remote LocalAPI over unix socket
        if remote_client:
            try:
                res = remote_client.call(name, params)
                return res, 200
            except Exception as e:
                return {'error': str(e)}, 400

        # fallback to messenger methods if available
        if messenger:
            try:
                if name == 'get_peers':
                    peers = messenger.get_all_peers()
                    out = []
                    for ip, info in peers.items():
                        has_chat = info.get('username') in getattr(messenger, 'active_chats', {})
                        out.append({
                            'username': info.get('username'),
                            'device_id': info.get('device_id'),
                            'ip': ip,
                            'status': 'online',
                            'last_seen': info.get('last_seen', time.time()),
                            'has_chat': has_chat,
                            'capabilities': ['files']
                        })
                    return {'peers': out}, 200

                if name == 'get_peer_info':
                    username = params.get('username')
                    res = messenger.get_peer_by_name(username)
                    if not res:
                        raise ValueError('peer not found')
                    ip, info = res
                    return info, 200

                if name == 'start_chat':
                    ok = messenger.start_chat(params.get('username'))
                    if ok:
                        return {'status': 'handshake_initiated', 'chat_id': messenger.active_chats.get(params.get('username'))}, 200
                    else:
                        raise ValueError('start failed')

                if name == 'send_message':
                    peer = params.get('peer')
                    text = params.get('text')
                    ok = messenger.send_message(peer, text)
                    if ok:
                        return {'status': 'sent', 'timestamp': time.time()}, 200
                    else:
                        raise ValueError('send failed')

                if name == 'get_messages':
                    peer = params.get('peer')
                    limit = params.get('limit', 50)
                    only_incoming = params.get('only_incoming', False)
                    # Get chat_id for this peer
                    chat_id = messenger.active_chats.get(peer)
                    if not chat_id:
                        return {'messages': [], 'total': 0, 'count': 0}, 200
                    
                    if only_incoming:
                        msgs_raw = messenger.get_incoming_messages(chat_id, limit)
                        print(f"🔍 DEBUG: Получено {len(msgs_raw)} входящих сообщений для chat_id={chat_id}")
                    else:
                        msgs_raw = messenger.get_conversation(chat_id, limit)
                        print(f"🔍 DEBUG: Получено {len(msgs_raw)} всех сообщений для chat_id={chat_id}")
                    
                    # Обрабатываем сообщения как в api.py
                    result = []
                    for msg in msgs_raw:
                        sender, encrypted, timestamp, delivered = msg
                        text = "[encrypted]"
                        try:
                            # если в БД хранится читаемый текст — вернём его
                            if isinstance(encrypted, (bytes, bytearray)):
                                try:
                                    decoded = encrypted.decode('utf-8')
                                    text = decoded
                                except Exception:
                                    text = "[encrypted]"
                            elif isinstance(encrypted, str):
                                text = encrypted
                        except Exception:
                            text = "[encrypted]"

                        result.append({
                            'msg_id': f"msg_{timestamp}",
                            'from': 'me' if sender == messenger.username else sender,
                            'text': text,
                            'timestamp': timestamp,
                            'status': 'delivered' if delivered else 'sent'
                        })
                        print(f"🔍 DEBUG: Обработано сообщение от={sender}, text={text[:20]}, from_field={'me' if sender == messenger.username else sender}")
                    return {'messages': result, 'total': len(result), 'count': len(result)}, 200

                if name == 'get_my_info':
                    return messenger.get_my_info() if hasattr(messenger, 'get_my_info') else {'username': messenger.username}, 200

            except Exception as e:
                return {'error': str(e)}, 400

        return {'error': 'no backend available'}, 500

    @app.route('/api/peers', methods=['GET'])
    def api_peers():
        res, code = call_handler('get_peers', {})
        return jsonify(res), code

    @app.route('/api/peer_info', methods=['GET'])
    def api_peer_info():
        username = request.args.get('username')
        res, code = call_handler('get_peer_info', {'username': username})
        return jsonify(res), code

    @app.route('/api/start_chat', methods=['POST'])
    def api_start_chat():
        data = request.get_json(force=True) or {}
        res, code = call_handler('start_chat', data)
        return jsonify(res), code

    @app.route('/api/send_message', methods=['POST'])
    def api_send_message():
        data = request.get_json(force=True) or {}
        res, code = call_handler('send_message', data)
        return jsonify(res), code

    @app.route('/api/get_messages', methods=['GET'])
    def api_get_messages():
        peer = request.args.get('peer')
        limit = int(request.args.get('limit', 50))
        res, code = call_handler('get_messages', {'peer': peer, 'limit': limit})
        return jsonify(res), code

    @app.route('/api/my_info', methods=['GET'])
    def api_my_info():
        res, code = call_handler('get_my_info', {})
        return jsonify(res), code

    @app.route('/api/debug_backend', methods=['GET'])
    def api_debug_backend():
        info = {
            'has_local_api': bool(local_api),
            'has_remote_client': bool(remote_client),
            'has_messenger_obj': bool(messenger)
        }
        if remote_client:
            try:
                info['remote_my_info'] = remote_client.call('get_my_info', {})
            except Exception as e:
                info['remote_error'] = str(e)
        return jsonify(info), 200

    # ---------- File upload (chunked) endpoints ----------
    UPLOAD_ROOT = os.path.join(BASE_DIR, 'downloads', 'uploads')
    TMP_ROOT = os.path.join(UPLOAD_ROOT, 'tmp')
    os.makedirs(TMP_ROOT, exist_ok=True)
    os.makedirs(UPLOAD_ROOT, exist_ok=True)

    @app.route('/api/upload/init', methods=['POST'])
    def api_upload_init():
        data = request.get_json(force=True) or {}
        filename = data.get('filename')
        size = int(data.get('size', 0))
        MAX_SIZE = 200 * 1024 * 1024
        if not filename:
            return jsonify({'error': 'filename required'}), 400
        if size <= 0 or size > MAX_SIZE:
            return jsonify({'error': 'invalid size or exceeds 200MB limit'}), 400

        upload_id = uuid.uuid4().hex
        upload_tmp = os.path.join(TMP_ROOT, upload_id)
        os.makedirs(upload_tmp, exist_ok=True)

        meta = {'filename': filename, 'size': size, 'received': 0}
        with open(os.path.join(upload_tmp, 'meta.json'), 'w') as f:
            json.dump(meta, f)

        return jsonify({'upload_id': upload_id}), 200

    @app.route('/api/upload/chunk', methods=['POST'])
    def api_upload_chunk():
        upload_id = request.form.get('upload_id')
        index = request.form.get('index')
        if not upload_id or index is None:
            return jsonify({'error': 'upload_id and index required'}), 400

        upload_tmp = os.path.join(TMP_ROOT, upload_id)
        if not os.path.exists(upload_tmp):
            return jsonify({'error': 'invalid upload_id'}), 400

        chunk = request.files.get('chunk')
        if not chunk:
            return jsonify({'error': 'chunk file required'}), 400

        try:
            idx = int(index)
        except:
            return jsonify({'error': 'invalid index'}), 400

        part_path = os.path.join(upload_tmp, f"{idx}.part")
        chunk.save(part_path)

        try:
            meta_path = os.path.join(upload_tmp, 'meta.json')
            if os.path.exists(meta_path):
                meta = json.load(open(meta_path))
                meta['received'] = meta.get('received', 0) + 1
                json.dump(meta, open(meta_path, 'w'))
        except Exception:
            pass

        return jsonify({'status': 'ok'}), 200

    @app.route('/api/upload/complete', methods=['POST'])
    def api_upload_complete():
        data = request.get_json(force=True) or {}
        upload_id = data.get('upload_id')
        if not upload_id:
            return jsonify({'error': 'upload_id required'}), 400

        upload_tmp = os.path.join(TMP_ROOT, upload_id)
        meta_path = os.path.join(upload_tmp, 'meta.json')
        if not os.path.exists(meta_path):
            return jsonify({'error': 'invalid upload_id'}), 400

        meta = json.load(open(meta_path))
        filename = meta.get('filename') or 'file'

        parts = [p for p in os.listdir(upload_tmp) if p.endswith('.part')]
        if not parts:
            return jsonify({'error': 'no parts uploaded'}), 400

        parts_sorted = sorted(parts, key=lambda x: int(x.split('.')[0]))

        safe_name = secure_filename(filename)
        out_name = f"{upload_id}_{safe_name}"
        out_path = os.path.join(UPLOAD_ROOT, out_name)

        with open(out_path, 'wb') as out_f:
            for part in parts_sorted:
                with open(os.path.join(upload_tmp, part), 'rb') as pf:
                    out_f.write(pf.read())

        try:
            import shutil
            shutil.rmtree(upload_tmp)
        except Exception:
            pass

        file_url = f"/uploads/{out_name}"
        return jsonify({'file_url': file_url, 'filename': safe_name}), 200

    @app.route('/uploads/<path:filename>')
    def serve_uploaded_file(filename):
        file_path = os.path.join(UPLOAD_ROOT, filename)
        if not os.path.exists(file_path):
            return abort(404)
        return send_from_directory(UPLOAD_ROOT, filename)

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', '5000'))
    print(f"Starting web server on 127.0.0.1:{port}")
    try:
        app.run(host='127.0.0.1', port=port, debug=False)
    except OSError as e:
        print(f"Failed to start server: {e}")
