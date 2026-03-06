import os
import threading
import time
from flask import Flask, jsonify, request, send_from_directory, abort
from flask_cors import CORS

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

    return app


if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', '5000'))
    print(f"Starting web server on 127.0.0.1:{port}")
    try:
        app.run(host='127.0.0.1', port=port, debug=False)
    except OSError as e:
        print(f"Failed to start server: {e}")
