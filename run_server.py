#!/usr/bin/env python3
"""
Start the secure messenger with file transfer for manual testing.
Run this and then open http://localhost:5000 in your browser.
"""

import os
import sys
import signal
import time

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'back'))

def signal_handler(sig, frame):
    print('\n🛑 Shutting down server...')
    sys.exit(0)

def main():
    print("🚀 Starting Secure Messenger with File Transfer")
    print("=" * 50)
    
    # Set up signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Import and start the web server
        from back.web import create_app
        
        app = create_app()
        
        print("✅ Web server starting on http://localhost:8080")
        print("📁 File uploads will be stored in ./downloads/uploads")
        print("🔗 API endpoints available at:")
        print("   - POST /api/upload/init")
        print("   - POST /api/upload/chunk")
        print("   - POST /api/upload/complete")
        print("   - POST /api/send_uploaded_file")
        print("   - GET /api/transfers")
        print("   - GET /api/transfer/<id>")
        print("   - POST /api/transfer/<id>/cancel")
        print("\n📝 Test steps:")
        print("1. Open http://localhost:8080 in your browser")
        print("2. Connect to a peer or use test mode")
        print("3. Try sending a file to test the transfer")
        print("4. Check browser console for transfer progress")
        print("\n⚠️  Press Ctrl+C to stop the server")
        print("=" * 50)
        
        # Run the app
        app.run(host='0.0.0.0', port=8080, debug=False)
        
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
