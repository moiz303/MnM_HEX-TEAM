import os
import threading
import time
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS
import uuid
from werkzeug.utils import secure_filename

# Import backend classes (runs in-process)
from main import SecureMessenger
from api import LocalAPI


BASE_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), '..'))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')


def create_app():
    app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path='')
    CORS(app)

    # Start backend messenger and local API in background threads.
    # If SecureMessenger fails (e.g. network port already in use), fall back to a minimal mock backend
    try:
        messenger = SecureMessenger('web_user')
    except Exception as e:
        print(f"[web] Warning: SecureMessenger failed to start: {e}")

        class MockBackend:
            def __init__(self):
                self.username = 'web_user'
                self.device_id = 'mock-device'
                self.start_time = time.time()
                self.active_chats = {}
                self.db = self
                self.discovery = self

            # discovery methods
            def get_all_peers(self):
                # return empty dict (no peers)
                return {}

            def get_peer_by_name(self, name):
                return None

            # chat methods
            def start_chat(self, peer_name):
                return False

            def send_message(self, peer_name, text):
                return False

            # db stub
            def get_conversation(self, chat_id, limit=50):
                return []

        messenger = MockBackend()

    local_api = LocalAPI(messenger)
    threading.Thread(target=local_api.start, daemon=True).start()

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

    # Simple API endpoints that call LocalAPI handlers
    def call_handler(name, params):
        handler = local_api.methods.get(name)
        if not handler:
            return {'error': f'method {name} not found'}, 404
        try:
            result = handler(params or {})
            return result, 200
        except Exception as e:
            return {'error': str(e)}, 400

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

    # ---------- File upload (chunked) endpoints ----------
    UPLOAD_ROOT = os.path.join(BASE_DIR, 'downloads', 'uploads')
    TMP_ROOT = os.path.join(UPLOAD_ROOT, 'tmp')
    os.makedirs(TMP_ROOT, exist_ok=True)
    os.makedirs(UPLOAD_ROOT, exist_ok=True)

    @app.route('/api/upload/init', methods=['POST'])
    def api_upload_init():
        # JSON: {filename, size}
        data = request.get_json(force=True) or {}
        filename = data.get('filename')
        size = int(data.get('size', 0))
        MAX_SIZE = 200 * 1024 * 1024  # 200 MB
        if not filename:
            return jsonify({'error': 'filename required'}), 400
        if size <= 0 or size > MAX_SIZE:
            return jsonify({'error': 'invalid size or exceeds 200MB limit'}), 400

        upload_id = uuid.uuid4().hex
        # create temp dir for this upload
        upload_tmp = os.path.join(TMP_ROOT, upload_id)
        os.makedirs(upload_tmp, exist_ok=True)

        # store metadata
        meta = {
            'filename': filename,
            'size': size,
            'received': 0
        }
        with open(os.path.join(upload_tmp, 'meta.json'), 'w') as f:
            import json as _json
            _json.dump(meta, f)

        return jsonify({'upload_id': upload_id}), 200

    @app.route('/api/upload/chunk', methods=['POST'])
    def api_upload_chunk():
        # multipart form-data: upload_id, index, chunk (file)
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

        # update received count (not strict)
        try:
            import json as _json
            meta_path = os.path.join(upload_tmp, 'meta.json')
            if os.path.exists(meta_path):
                meta = _json.load(open(meta_path))
                meta['received'] = meta.get('received', 0) + 1
                _json.dump(meta, open(meta_path, 'w'))
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

        import json as _json
        meta = _json.load(open(meta_path))
        filename = meta.get('filename') or 'file'

        # assemble parts
        parts = [p for p in os.listdir(upload_tmp) if p.endswith('.part')]
        if not parts:
            return jsonify({'error': 'no parts uploaded'}), 400

        # sort by numeric prefix
        parts_sorted = sorted(parts, key=lambda x: int(x.split('.')[0]))

        safe_name = secure_filename(filename)
        # prefix with upload_id to avoid clashes
        out_name = f"{upload_id}_{safe_name}"
        out_path = os.path.join(UPLOAD_ROOT, out_name)

        with open(out_path, 'wb') as out_f:
            for part in parts_sorted:
                with open(os.path.join(upload_tmp, part), 'rb') as pf:
                    out_f.write(pf.read())

        # cleanup temp
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
