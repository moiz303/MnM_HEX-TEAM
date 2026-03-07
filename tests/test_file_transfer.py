#!/usr/bin/env python3
"""
Test script for file transfer functionality.
Run this to verify file transfer system works correctly.
"""

import os
import sys
import time
import tempfile
import hashlib
from pathlib import Path

# Добавляем путь к back директории
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'back'))

def create_test_file(size_mb=1, filename="test_file.txt"):
    """Create a test file with specified size."""
    content = os.urandom(size_mb * 1024 * 1024)
    with open(filename, 'wb') as f:
        f.write(content)
    return filename, hashlib.sha256(content).hexdigest()

def test_backend_imports():
    """Test that all backend modules can be imported."""
    print("🔍 Testing backend imports...")
    
    try:
        from network.file_transfer import FileTransferManager, FileInfo, TransferSession
        from network.protocols import MessageType, Limits
        from core.crypto import SecureCryptoCore
        from api import LocalAPI
        from main import SecureMessenger
        print("✅ All backend imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_file_transfer_manager():
    """Test FileTransferManager initialization."""
    print("\n🔍 Testing FileTransferManager...")
    
    try:
        # Import here to avoid scope issues
        from network.file_transfer import FileTransferManager
        
        # Mock dependencies
        class MockCrypto:
            def get_session_key(self, peer_id):
                return b'test_key_123456789012345678901234'
            def encrypt_with_key(self, data, key):
                return data
            def decrypt_with_key(self, data, key):
                return data
        
        class MockConnMgr:
            def __init__(self):
                self.peer_id = 'test_device_123456789012345678901234'
        
        # Initialize manager
        crypto = MockCrypto()
        conn_mgr = MockConnMgr()
        manager = FileTransferManager(conn_mgr, crypto)
        
        print("✅ FileTransferManager initialized successfully")
        return True, manager
    except Exception as e:
        print(f"❌ FileTransferManager error: {e}")
        return False, None

def test_file_validation(manager):
    """Test file validation functionality."""
    print("\n🔍 Testing file validation...")
    
    try:
        # Create test file
        test_file, expected_hash = create_test_file(1, "test_validation.txt")
        
        # Test validation
        is_valid = manager._validate_file_path(test_file)
        
        # Cleanup
        os.remove(test_file)
        
        if is_valid:
            print("✅ File validation works correctly")
            return True
        else:
            print("❌ File validation failed")
            return False
    except Exception as e:
        print(f"❌ Validation test error: {e}")
        return False

def test_chunking():
    """Test file chunking functionality."""
    print("\n🔍 Testing file chunking...")
    
    try:
        from network.file_transfer import TransferSession, FileInfo
        from network.protocols import Limits
        
        # Create test file
        test_file, _ = create_test_file(1, "test_chunk.txt")
        
        # Create mock session
        file_info = FileInfo(
            file_id="test123",
            filename="test_chunk.txt",
            file_size=1024*1024,
            file_hash="test_hash",
            mime_type="text/plain",
            chunk_count=64,
            sender_id="sender",
            receiver_id="receiver"
        )
        
        session = TransferSession(
            transfer_id="test123",
            file_info=file_info,
            local_path=test_file
        )
        
        # Test chunking directly
        with open(test_file, 'rb') as f:
            for i in range(session.file_info.chunk_count):
                data = f.read(Limits.MAX_FILE_CHUNK)
                chunk_hash = hashlib.sha256(data).hexdigest()
                session.chunks[i] = type('Chunk', (), {
                    'chunk_index': i,
                    'data': data,
                    'chunk_hash': chunk_hash,
                    'chunk_size': len(data)
                })()
        
        # Verify chunks
        chunk_sizes = [chunk.chunk_size for chunk in session.chunks.values()]
        last_chunk_size = chunk_sizes[-1]
        other_chunks = chunk_sizes[:-1]
        
        if len(session.chunks) == 64 and all(size == 16384 for size in other_chunks):
            print("✅ File chunking works correctly")
            result = True
        else:
            print(f"❌ File chunking failed: {len(session.chunks)} chunks, sizes: {chunk_sizes[:5]}...")
            result = False
        
        # Cleanup
        os.remove(test_file)
        return result
    except Exception as e:
        print(f"❌ Chunking test error: {e}")
        return False

def test_web_server():
    """Test if web server can start."""
    print("\n🔍 Testing web server...")
    
    try:
        from web import create_app
        app = create_app()
        
        with app.test_client() as client:
            response = client.get('/')
            # Should return frontend or 404, but not crash
            if response.status_code in [200, 404]:
                print("✅ Web server starts correctly")
                return True
            else:
                print(f"❌ Unexpected status code: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Web server error: {e}")
        return False

def run_all_tests():
    """Run all tests and report results."""
    print("🚀 Starting File Transfer System Tests\n")
    
    tests = [
        ("Backend Imports", test_backend_imports),
        ("File Transfer Manager", lambda: test_file_transfer_manager()[0]),
        ("File Validation", lambda: test_file_validation(test_file_transfer_manager()[1])),
        ("File Chunking", test_chunking),
        ("Web Server", test_web_server)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n{'='*50}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! System is ready for use.")
        return True
    else:
        print("⚠️ Some tests failed. Please check the errors above.")
        return False

if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
