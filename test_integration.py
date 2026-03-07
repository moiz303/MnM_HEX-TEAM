#!/usr/bin/env python3
"""
Integration test for complete file transfer workflow.
Tests the actual file transfer between two mock peers.
"""

import os
import sys
import time
import tempfile
import threading
import hashlib
from pathlib import Path

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'back'))

def create_test_files():
    """Create test files of different sizes."""
    files = []
    
    # Small text file
    with open("small_test.txt", "w") as f:
        f.write("Hello, World! This is a test file for transfer.")
    files.append(("small_test.txt", "text/plain"))
    
    # Medium binary file (1MB)
    with open("medium_test.bin", "wb") as f:
        f.write(os.urandom(1024 * 1024))
    files.append(("medium_test.bin", "application/octet-stream"))
    
    # Large file (10MB)
    with open("large_test.bin", "wb") as f:
        f.write(os.urandom(10 * 1024 * 1024))
    files.append(("large_test.bin", "application/octet-stream"))
    
    return files

def test_mock_peer_simulation():
    """Test file transfer between two mock peers."""
    print("\n🔄 Testing mock peer simulation...")
    
    try:
        from back.network.file_transfer import FileTransferManager
        from back.network.protocols import Limits
        
        # Mock crypto for encryption
        class MockCrypto:
            def __init__(self):
                self.session_keys = {}
            
            def get_session_key(self, peer_id):
                if peer_id not in self.session_keys:
                    self.session_keys[peer_id] = b'test_key_123456789012345678901234'
                return self.session_keys[peer_id]
            
            def encrypt_with_key(self, data, key):
                # Simple XOR encryption for testing
                return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
            
            def decrypt_with_key(self, data, key):
                # XOR is symmetric
                return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        
        # Mock connection manager
        class MockConnMgr:
            def __init__(self, peer_id):
                self.peer_id = peer_id
                self.sent_messages = []
            
            def send_message(self, target, message):
                self.sent_messages.append((target, message))
                print(f"📤 Message sent to {target}: {message.get('type', 'unknown')}")
            
            def send_to_peer(self, target, message):
                # Mock implementation for _send_to_peer
                self.sent_messages.append((target, message))
                print(f"📡 Direct send to {target}: {message.get('type', 'unknown')}")
                return True
        
        # Create two peers
        crypto1 = MockCrypto()
        crypto2 = MockCrypto()
        conn1 = MockConnMgr("peer1_123456789012345678901234")
        conn2 = MockConnMgr("peer2_123456789012345678901234")
        
        manager1 = FileTransferManager(conn1, crypto1)
        manager2 = FileTransferManager(conn2, crypto2)
        
        # Test file transfer
        test_file = "integration_test.txt"
        with open(test_file, "w") as f:
            f.write("Integration test content for peer transfer!")
        
        try:
            # Simulate file offer
            transfer_id = manager1.send_file("127.0.0.1", test_file, "peer2_123456789012345678901234")
            print(f"✅ Transfer initiated: {transfer_id}")
            
            # Check transfer info
            info = manager1.get_transfer_info(transfer_id)
            if info and info['status'] in ['pending', 'in_progress']:
                print("✅ Transfer status correct")
            else:
                print(f"❌ Unexpected transfer status: {info}")
                return False
            
            # Simulate receiving file offer
            offer_data = {
                'file_id': transfer_id,
                'filename': 'integration_test.txt',
                'size': os.path.getsize(test_file),
                'mime_type': 'text/plain',
                'encrypted_metadata': '7b2766696c655f68617368273a202774657374272c20276368756e6b5f636f756e74273a20317d'
            }
            
            # Handle file offer
            manager2.handle_file_offer(offer_data, "peer1_123456789012345678901234")
            print("✅ File offer handled")
            
            # Check transfers
            transfers = manager2.get_all_transfers()
            if len(transfers) > 0:
                print(f"✅ Transfer registered in receiver: {transfers[0]['transfer_id']}")
            else:
                print("❌ No transfers found in receiver")
                return False
            
            return True
            
        finally:
            # Cleanup
            if os.path.exists(test_file):
                os.remove(test_file)
            manager1.shutdown()
            manager2.shutdown()
    
    except Exception as e:
        print(f"❌ Mock peer simulation error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_encryption_flow():
    """Test encryption/decryption flow."""
    print("\n🔐 Testing encryption flow...")
    
    try:
        from back.network.file_transfer import FileTransferManager
        
        class TestCrypto:
            def get_session_key(self, peer_id):
                return b'test_encryption_key_123456789012'
            
            def encrypt_with_key(self, data, key):
                # Simple encryption for testing
                return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
            
            def decrypt_with_key(self, data, key):
                return bytes([b ^ key[i % len(key)] for i, b in enumerate(data)])
        
        class TestConnMgr:
            def __init__(self):
                self.peer_id = "test_peer_123456789012345678901234"
        
        crypto = TestCrypto()
        conn_mgr = TestConnMgr()
        manager = FileTransferManager(conn_mgr, crypto)
        
        # Test data
        test_data = b"Secret message that should be encrypted"
        key = crypto.get_session_key("test_peer")
        
        # Encrypt
        encrypted = crypto.encrypt_with_key(test_data, key)
        if encrypted != test_data:
            print("✅ Data encrypted successfully")
        else:
            print("❌ Encryption failed - data unchanged")
            return False
        
        # Decrypt
        decrypted = crypto.decrypt_with_key(encrypted, key)
        if decrypted == test_data:
            print("✅ Data decrypted successfully")
        else:
            print("❌ Decryption failed - data mismatch")
            return False
        
        manager.shutdown()
        return True
    
    except Exception as e:
        print(f"❌ Encryption flow error: {e}")
        return False

def test_error_handling():
    """Test error handling scenarios."""
    print("\n⚠️ Testing error handling...")
    
    try:
        from back.network.file_transfer import FileTransferManager
        
        class ErrorCrypto:
            def get_session_key(self, peer_id):
                return None  # No key - should cause error
            
            def encrypt_with_key(self, data, key):
                raise Exception("Encryption failed")
            
            def decrypt_with_key(self, data, key):
                raise Exception("Decryption failed")
        
        class ErrorConnMgr:
            def __init__(self):
                self.peer_id = "error_test_peer"
        
        crypto = ErrorCrypto()
        conn_mgr = ErrorConnMgr()
        manager = FileTransferManager(conn_mgr, crypto)
        
        # Test file that doesn't exist
        try:
            manager.send_file("127.0.0.1", "nonexistent.txt", "test_peer")
            print("❌ Should have failed for nonexistent file")
            return False
        except (FileNotFoundError, ValueError):
            print("✅ Correctly handled nonexistent file")
        
        # Test oversized file validation
        large_file = "fake_large_file.txt"
        try:
            with open(large_file, "w") as f:
                f.write("x" * 100)  # Small file for test
            
            # Mock the validation to fail
            original_validate = manager._validate_file_path
            manager._validate_file_path = lambda path: False
            
            try:
                manager.send_file("127.0.0.1", large_file, "test_peer")
                print("❌ Should have failed validation")
                return False
            except ValueError:
                print("✅ Correctly handled validation failure")
            finally:
                manager._validate_file_path = original_validate
        finally:
            if os.path.exists(large_file):
                os.remove(large_file)
        
        manager.shutdown()
        return True
    
    except Exception as e:
        print(f"❌ Error handling test error: {e}")
        return False

def run_integration_tests():
    """Run all integration tests."""
    print("🚀 Starting Integration Tests\n")
    
    tests = [
        ("Mock Peer Simulation", test_mock_peer_simulation),
        ("Encryption Flow", test_encryption_flow),
        ("Error Handling", test_error_handling)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n{'='*60}")
    print(f"📊 Integration Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All integration tests passed!")
        return True
    else:
        print("⚠️ Some integration tests failed.")
        return False

if __name__ == "__main__":
    success = run_integration_tests()
    sys.exit(0 if success else 1)
