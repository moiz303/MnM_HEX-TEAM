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
# use our API handler implementation rather than any unrelated package
try:
    from back.api import LocalAPI
except ImportError:
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
            messenger = SecureMessenger('web_user')
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

            def send_file(self, peer_name, file_path):
                return 'mock-transfer-id'

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

    # call_handler supports three modes: local_api (in-process), remote_client (unix socket), messenger (mock/wrapper)
    def call_handler(name, params):
        params = params or {}

        # Helper to attempt start_chat then retry send
        def _try_send_with_handshake(call_fn, peer, params):
            try:
                return call_fn(name, params)
            except Exception:
                try:
                    call_fn('start_chat', {'username': peer})
                except Exception:
                    pass
                return call_fn(name, params)

        # In-process LocalAPI: call handler functions directly
        if local_api:
            handler = local_api.methods.get(name)
            if not handler:
                print(f"[web] local_api missing handler for {name}, falling back to messenger if available")
            else:
                try:
                    if name == 'send_message':
                        try:
                            result = handler(params)
                            return result, 200
                        except Exception:
                            # attempt handshake then retry
                            try:
                                local_api.methods.get('start_chat')({'username': params.get('peer')})
                            except Exception:
                                pass
                            result = handler(params)
                            return result, 200
                    result = handler(params)
                    return result, 200
                except Exception as e:
                    return {'error': str(e)}, 400
    # if we reach here either local_api wasn't set, or it lacked a handler

        # Remote LocalAPI over unix socket
        if remote_client:
            try:
                if name == 'send_message':
                    # first try, then attempt start_chat and retry
                    try:
                        res = remote_client.call(name, params)
                        return res, 200
                    except Exception:
                        try:
                            remote_client.call('start_chat', {'username': params.get('peer')})
                        except Exception:
                            pass
                        res = remote_client.call(name, params)
                        return res, 200

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

                if name == 'send_file':
                    peer = params.get('peer')
                    file_path = params.get('file_path')
                    try:
                        transfer_id = messenger.send_file(peer, file_path)
                        return {'status': 'initiated', 'transfer_id': transfer_id}, 200
                    except Exception as e:
                        raise ValueError(f'send file failed: {e}')

                if name == 'get_messages':
                    peer = params.get('peer')
                    limit = params.get('limit', 50)
                    msgs = messenger.get_conversation(peer, limit)
                    return {'messages': msgs, 'total': len(msgs), 'count': len(msgs)}, 200

                if name == 'get_my_info':
                    return messenger.get_my_info() if hasattr(messenger, 'get_my_info') else {'username': messenger.username}, 200

                if name == 'send_file':
                    peer = params.get('peer')
                    file_path = params.get('file_path')
                    try:
                        transfer_id = messenger.send_file(peer, file_path)
                        return {'status': 'initiated', 'transfer_id': transfer_id}, 200
                    except Exception as e:
                        raise ValueError(f'send file failed: {e}')

                if name == 'get_transfers':
                    if hasattr(messenger, 'router') and hasattr(messenger.router, 'file_manager'):
                        transfers = messenger.router.file_manager.get_all_transfers()
                        return {'transfers': transfers, 'total': len(transfers)}, 200
                    else:
                        return {'transfers': [], 'total': 0}, 200

                if name == 'get_transfer_info':
                    transfer_id = params.get('transfer_id')
                    if not transfer_id:
                        raise ValueError('transfer_id required')
                    if hasattr(messenger, 'router') and hasattr(messenger.router, 'file_manager'):
                        info = messenger.router.file_manager.get_transfer_info(transfer_id)
                        if info:
                            return info, 200
                        else:
                            raise ValueError('Transfer not found')
                    else:
                        raise ValueError('File transfer manager not available')

                if name == 'cancel_transfer':
                    transfer_id = params.get('transfer_id')
                    if not transfer_id:
                        raise ValueError('transfer_id required')
                    if hasattr(messenger, 'router') and hasattr(messenger.router, 'file_manager'):
                        success = messenger.router.file_manager.cancel_transfer(transfer_id)
                        if success:
                            return {'status': 'cancelled', 'transfer_id': transfer_id}, 200
                        else:
                            raise ValueError('Failed to cancel transfer')
                    else:
                        raise ValueError('File transfer manager not available')

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

    @app.route('/api/send_file', methods=['POST'])
    def api_send_file():
        data = request.get_json(force=True) or {}
        res, code = call_handler('send_file', data)
        return jsonify(res), code

    @app.route('/api/transfers', methods=['GET'])
    def api_transfers():
        res, code = call_handler('get_transfers', {})
        return jsonify(res), code

    @app.route('/api/transfer/<transfer_id>', methods=['GET'])
    def api_transfer_info(transfer_id):
        res, code = call_handler('get_transfer_info', {'transfer_id': transfer_id})
        return jsonify(res), code

    @app.route('/api/transfer/<transfer_id>/cancel', methods=['POST'])
    def api_cancel_transfer(transfer_id):
        res, code = call_handler('cancel_transfer', {'transfer_id': transfer_id})
        return jsonify(res), code)

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

    # keep mapping of upload_id -> file path to avoid glob issues
    uploads_map = {}

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

        # record mapping so send_uploaded_file can find it easily
        uploads_map[upload_id] = out_path

        file_url = f"/uploads/{out_name}"
        return jsonify({'file_url': file_url, 'filename': safe_name, 'upload_id': upload_id}), 200

    @app.route('/uploads/<path:filename>')
    def serve_uploaded_file(filename):
        file_path = os.path.join(UPLOAD_ROOT, filename)
        if not os.path.exists(file_path):
            return abort(404)
        return send_from_directory(UPLOAD_ROOT, filename)

    @app.route('/downloads/<path:filename>')
    def serve_downloaded_file(filename):
        download_root = os.path.join(BASE_DIR, 'downloads')
        file_path = os.path.join(download_root, filename)
        if not os.path.exists(file_path):
            return abort(404)
        return send_from_directory(download_root, filename)

    @app.route('/api/send_uploaded_file', methods=['POST'])
    def api_send_uploaded_file():
        data = request.get_json(force=True) or {}
        upload_id = data.get('upload_id')
        peer = data.get('peer')
        print(f"[web] send_uploaded_file called with upload_id={upload_id}, peer={peer}")
        if not upload_id or not peer:
            print(f"[web] missing data")
            return jsonify({'error': 'upload_id and peer required'}), 400

        # lookup path from map first
        file_path = uploads_map.get(upload_id)
        if not file_path or not os.path.exists(file_path):
            # fallback to scanning directory
            import glob
            pattern = os.path.join(UPLOAD_ROOT, f"{upload_id}_*")
            print(f"[web] scanning with pattern {pattern}")
            matches = glob.glob(pattern)
            if not matches:
                print(f"[web] file not found for upload_id {upload_id}")
                return jsonify({'error': 'file not found'}), 404
            file_path = matches[0]
            uploads_map[upload_id] = file_path
        else:
            print(f"[web] found file_path {file_path} via map")

        print(f"[web] file {file_path} exists: {os.path.exists(file_path)}, size: {os.path.getsize(file_path) if os.path.exists(file_path) else 0}")

        # Now call send_file
        print(f"[web] calling send_file peer={peer} path={file_path}")
        res, code = call_handler('send_file', {'peer': peer, 'file_path': file_path})
        print(f"[web] send_file result {res} code {code}")
        return jsonify(res), code

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', '5000'))
    print(f"Starting web server on 127.0.0.1:{port}")
    try:
        app.run(host='127.0.0.1', port=port, debug=False)
    except OSError as e:
        print(f"Failed to start server: {e}")
