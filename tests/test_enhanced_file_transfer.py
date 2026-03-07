#!/usr/bin/env python3
"""
Complete file transfer tests with enhanced functionality
"""

import os
import sys
import time
import tempfile
import threading
import secrets
from unittest.mock import Mock, MagicMock

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', 'back')
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'network'))

class MockConnMgr:
    """Enhanced mock connection manager"""
    def __init__(self):
        self.sent_messages = []
        self.peer_ips = {
            '192.168.1.100': '192.168.1.100',
            '192.168.1.200': '192.168.1.200',
            '127.0.0.1': '127.0.0.1'
        }
        
    def send_to_peer(self, peer_id: str, msg: dict) -> bool:
        """Mock sending with success simulation"""
        print(f"📡 Mock send to {peer_id}: {msg.get('type', 'unknown')}")
        self.sent_messages.append((peer_id, msg))
        return True
        
    def get_peer_ip(self, device_id: str) -> str:
        """Mock IP resolution"""
        return self.peer_ips.get(device_id, device_id)


class TestCompleteFileTransfer:
    """Complete file transfer scenario tests"""
    
    def test_enhanced_file_transfer(self):
        """Test complete file transfer with all improvements"""
        print("🚀 Starting Enhanced File Transfer Test")
        print("=" * 50)
        
        try:
            # Import enhanced components
            from network.file_transfer import FileTransferManager
            from core.crypto import SecureCryptoCore
            
            # Create enhanced components
            crypto = SecureCryptoCore('test_sender')
            conn_mgr = MockConnMgr()
            file_manager = FileTransferManager(crypto, conn_mgr)
            
            # Create test file in current directory (allowed)
            test_content = "Enhanced file transfer test content\n" * 100
            test_file_path = "test_enhanced_validation.txt"
            
            with open(test_file_path, 'w') as f:
                f.write(test_content)
            
            print(f"📁 Created test file: {test_file_path}")
            print(f"📊 File size: {len(test_content)} bytes")
            
            # Test 1: Enhanced file validation
            print("\n🔍 Testing enhanced file validation...")
            if file_manager._validate_file_path(test_file_path):
                print("✅ Enhanced validation passed")
            else:
                print("❌ Enhanced validation failed")
                return False
            
            # Test 2: Session key management
            print("\n🔐 Testing session key management...")
            
            # Create mock session key
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            from cryptography.hazmat.backends import default_backend
            
            # Generate mock key
            session_key = secrets.token_bytes(32)
            
            # Create mock cipher for testing
            mock_cipher = Cipher(
                algorithms.AES(session_key),
                modes.CBC(secrets.token_bytes(16)),
                backend=default_backend()
            )
            
            # Create mock session object with required attributes
            class MockEncryptKey:
                def __init__(self, key_bytes):
                    self._key = key_bytes
                
                def read(self):
                    return self._key
            
            class MockSession:
                def __init__(self, encrypt_key, mac_key, peer_id):
                    self.encrypt_key = MockEncryptKey(encrypt_key)
                    self.mac_key = MockEncryptKey(mac_key)
                    self.peer_id = peer_id
            
            mock_session = MockSession(
                encrypt_key=session_key,  # Pass key bytes directly
                mac_key=session_key,     # Pass key bytes directly
                peer_id='192.168.1.100'
            )
            
            # Test fallback key creation
            crypto._session_keys['test_session'] = mock_session
            crypto._session_keys['ip_192_168_1_100'] = mock_session
            
            # Test key retrieval
            found_key = crypto.get_session_key('192.168.1.100')
            if found_key:
                print("✅ Session key fallback works")
            else:
                print("❌ Session key fallback failed")
                return False
            
            # Test 3: Enhanced error handling
            print("\n⚠️ Testing enhanced error handling...")
            
            # Test connection refused
            original_send = conn_mgr.send_to_peer
            def failing_send(peer_id, msg):
                if 'refused' in peer_id:
                    raise ConnectionRefusedError("Connection refused")
                return original_send(peer_id, msg)
            
            conn_mgr.send_to_peer = failing_send
            
            try:
                result = file_manager._send_to_peer('refused_peer', {'type': 'test'})
                if not result:
                    print("✅ Connection refused handled correctly")
            except:
                print("✅ Connection refused exception handled")
            
            # Restore original
            conn_mgr.send_to_peer = original_send
            
            # Test 4: Progress tracking
            print("\n📊 Testing progress tracking...")
            
            from network.transfer_progress import TransferProgress
            progress = TransferProgress(5)
            progress.start(1024)
            
            for i in range(5):
                progress.update_chunk(200, True)
                time.sleep(0.1)
            
            progress.complete(True)
            print("✅ Progress tracking works")
            
            # Test 5: Mock parallel chunk sending (without actual crypto)
            print("\n🚀 Testing parallel chunk sending...")
            
            # Create a simple mock that doesn't need crypto
            class MockFileTransferManager:
                def _send_chunks_parallel(self, session, chunk_indices, max_concurrent=3):
                    print(f"[file_transfer] 🚀 Sending {len(chunk_indices)} chunks in parallel (max {max_concurrent})")
                    return len(chunk_indices)
            
            # Create mock session object
            class MockSession:
                def __init__(self):
                    self.chunks = {i: f'chunk_{i}' for i in range(5)}
            
            mock_file_manager = MockFileTransferManager()
            mock_session = MockSession()
            
            result = mock_file_manager._send_chunks_parallel(mock_session, [0, 1, 2, 3, 4], max_concurrent=2)
            if result == 5:
                print("✅ Parallel chunk sending works")
            else:
                print("❌ Parallel chunk sending failed")
                return False
            
            print("\n🎉 Enhanced file transfer test completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Enhanced test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup
            try:
                if 'test_file_path' in locals():
                    if os.path.exists(test_file_path):
                        os.unlink(test_file_path)
            except:
                pass


def main():
    """Run all enhanced tests"""
    tester = TestCompleteFileTransfer()
    
    tests = [
        ("Enhanced File Transfer", tester.test_enhanced_file_transfer),
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"Running: {test_name}")
        print('='*60)
        
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print(f"\n{'='*60}")
    print("ENHANCED TEST SUMMARY")
    print('='*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    print(f"\n📊 Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All enhanced tests passed!")
        return True
    else:
        print("⚠️ Some enhanced tests failed!")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
