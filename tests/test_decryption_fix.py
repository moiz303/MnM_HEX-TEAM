#!/usr/bin/env python3
"""
Test for decryption fix - verifies that session keys with SecureMemory work correctly
"""

import os
import sys
import secrets
import base64

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', 'back')
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'network'))

def test_decryption_fix():
    """Test that fallback session keys with SecureMemory work for encryption/decryption"""
    print("🔐 Testing Decryption Fix")
    print("=" * 50)
    
    try:
        from core.crypto import SecureCryptoCore, SessionKeys, SecureMemory
        
        # Create crypto manager
        crypto = SecureCryptoCore('test_device')
        
        # Test 1: Create a mock session key
        print("\n📋 Test 1: Create mock session key")
        
        # Generate test keys
        encrypt_key_bytes = secrets.token_bytes(32)
        mac_key_bytes = secrets.token_bytes(32)
        
        # Create session key (SessionKeys ожидает bytes, не SecureMemory)
        session_key = SessionKeys(
            encrypt_key=encrypt_key_bytes,
            mac_key=mac_key_bytes,
            peer_id='test_peer'
        )
        
        # Store session
        crypto._session_keys['test_session'] = session_key
        print("✅ Created mock session key")
        
        # Test 2: Retrieve session key
        print("\n📋 Test 2: Retrieve session key")
        retrieved_key = crypto.get_session_key('test_peer')
        if retrieved_key:
            print("✅ Session key retrieved successfully")
        else:
            print("❌ Session key retrieval failed")
            return False
        
        # Test 3: Create fallback IP session key
        print("\n📋 Test 3: Create fallback IP session key")
        
        # Get existing session
        existing_session = crypto._session_keys['test_session']
        
        # Create fallback key using same logic as file_transfer.py
        encrypt_key_bytes = existing_session.encrypt_key.read()
        mac_key_bytes = existing_session.mac_key.read()
        
        # Save under IP address (SessionKeys ожидает bytes, не SecureMemory)
        ip_session_id = "ip_192_168_0_231"
        crypto._session_keys[ip_session_id] = SessionKeys(
            encrypt_key=encrypt_key_bytes,  # bytes, не SecureMemory
            mac_key=mac_key_bytes,          # bytes, не SecureMemory
            peer_id='192.168.0.231'
        )
        
        print(f"✅ Created fallback session key: {ip_session_id}")
        
        # Test 4: Retrieve fallback session key
        print("\n📋 Test 4: Retrieve fallback session key")
        fallback_key = crypto.get_session_key('192.168.0.231')
        if fallback_key:
            print("✅ Fallback session key found")
        else:
            print("❌ Fallback session key not found")
            return False
        
        # Test 5: Encrypt and decrypt with fallback key
        print("\n📋 Test 5: Encrypt and decrypt with fallback key")
        
        test_data = b"Test message for decryption"
        print(f"📝 Original data: {test_data}")
        
        # Encrypt
        encrypted = crypto.encrypt_with_key(test_data, fallback_key)
        print(f"🔐 Encrypted: {len(encrypted)} bytes")
        
        # Decrypt
        decrypted = crypto.decrypt_with_key(encrypted, fallback_key)
        print(f"🔓 Decrypted: {decrypted}")
        
        if decrypted == test_data:
            print("✅ Encryption/decryption with fallback key works!")
            return True
        else:
            print("❌ Encryption/decryption with fallback key failed!")
            print(f"Expected: {test_data}")
            print(f"Got: {decrypted}")
            return False
            
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run decryption fix test"""
    success = test_decryption_fix()
    
    print(f"\n{'='*50}")
    if success:
        print("🎉 DECRYPTION FIX TEST PASSED!")
        print("✅ Session keys with SecureMemory work correctly")
        print("✅ Fallback IP session keys work for encryption/decryption")
        print("✅ The 'Invalid padding bytes' error should be fixed")
    else:
        print("❌ DECRYPTION FIX TEST FAILED!")
        print("⚠️ Session key encryption/decryption still has issues")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
