#!/usr/bin/env python3
"""
Diagnostic test for peer decryption issues
"""

import os
import sys
import time
import secrets

# Add backend to path
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.join(current_dir, '..', 'back')
sys.path.insert(0, backend_dir)
sys.path.insert(0, os.path.join(backend_dir, 'network'))

def diagnose_peer_decryption():
    """Diagnose peer decryption issues"""
    print("🔍 DIAGNOSING PEER DECRYPTION ISSUES")
    print("=" * 50)
    
    try:
        from core.crypto import SecureCryptoCore, SessionKeys
        
        # Create two crypto managers (simulating two peers)
        peer1 = SecureCryptoCore('peer1')
        peer2 = SecureCryptoCore('peer2')
        
        print("✅ Created two crypto managers")
        
        # Test 1: Check basic encryption/decryption
        print("\n📋 Test 1: Basic encryption/decryption")
        
        test_data = b"Test message for peer decryption"
        print(f"📝 Original data: {test_data}")
        
        # Create a simple session key for both peers
        session_key = secrets.token_bytes(32)
        
        # Encrypt with peer1
        encrypted1 = peer1.encrypt_with_key(test_data, session_key)
        print(f"🔐 Peer1 encrypted: {len(encrypted1)} bytes")
        
        # Decrypt with peer1
        decrypted1 = peer1.decrypt_with_key(encrypted1, session_key)
        print(f"🔓 Peer1 decrypted: {decrypted1}")
        
        if decrypted1 == test_data:
            print("✅ Peer1 encryption/decryption works")
        else:
            print("❌ Peer1 encryption/decryption failed")
            return False
        
        # Encrypt with peer2
        encrypted2 = peer2.encrypt_with_key(test_data, session_key)
        print(f"🔐 Peer2 encrypted: {len(encrypted2)} bytes")
        
        # Decrypt with peer2
        decrypted2 = peer2.decrypt_with_key(encrypted2, session_key)
        print(f"🔓 Peer2 decrypted: {decrypted2}")
        
        if decrypted2 == test_data:
            print("✅ Peer2 encryption/decryption works")
        else:
            print("❌ Peer2 encryption/decryption failed")
            return False
        
        # Test 2: Cross-peer decryption
        print("\n📋 Test 2: Cross-peer decryption")
        
        # Peer1 encrypts, peer2 decrypts
        try:
            decrypted_cross = peer2.decrypt_with_key(encrypted1, session_key)
            if decrypted_cross == test_data:
                print("✅ Cross-peer decryption works")
            else:
                print("❌ Cross-peer decryption failed - wrong data")
                return False
        except Exception as e:
            print(f"❌ Cross-peer decryption failed with error: {e}")
            return False
        
        # Test 3: Session key management
        print("\n📋 Test 3: Session key management")
        
        # Create session keys for both peers
        peer1_session = SessionKeys(
            encrypt_key=session_key,
            mac_key=session_key,
            peer_id='peer2'
        )
        
        peer2_session = SessionKeys(
            encrypt_key=session_key,
            mac_key=session_key,
            peer_id='peer1'
        )
        
        # Store sessions
        peer1._session_keys['session_with_peer2'] = peer1_session
        peer2._session_keys['session_with_peer1'] = peer2_session
        
        print("✅ Session keys created and stored")
        
        # Test retrieval
        retrieved_key1 = peer1.get_session_key('peer2')
        retrieved_key2 = peer2.get_session_key('peer1')
        
        if retrieved_key1 and retrieved_key2:
            print("✅ Session keys retrieved successfully")
        else:
            print("❌ Session key retrieval failed")
            return False
        
        # Test 4: IP fallback session keys
        print("\n📋 Test 4: IP fallback session keys")
        
        # Create IP fallback for peer1
        peer1_ip_session = SessionKeys(
            encrypt_key=session_key,
            mac_key=session_key,
            peer_id='192.168.0.231'  # Your peer's IP
        )
        
        peer1._session_keys['ip_192_168_0_231'] = peer1_ip_session
        
        # Test IP key retrieval
        ip_key = peer1.get_session_key('192.168.0.231')
        
        if ip_key:
            print("✅ IP fallback session key works")
            
            # Test encryption/decryption with IP key
            ip_encrypted = peer1.encrypt_with_key(test_data, ip_key)
            ip_decrypted = peer1.decrypt_with_key(ip_encrypted, ip_key)
            
            if ip_decrypted == test_data:
                print("✅ IP fallback encryption/decryption works")
            else:
                print("❌ IP fallback encryption/decryption failed")
                return False
        else:
            print("❌ IP fallback session key failed")
            return False
        
        # Test 5: Simulate file chunk scenario
        print("\n📋 Test 5: File chunk scenario")
        
        # Simulate file chunk data
        file_data = b"This is a test file chunk content" * 10  # Larger data
        print(f"📁 File data size: {len(file_data)} bytes")
        
        # Encrypt as file chunk
        chunk_encrypted = peer1.encrypt_with_key(file_data, session_key)
        print(f"🔐 Chunk encrypted: {len(chunk_encrypted)} bytes")
        
        # Decrypt as file chunk
        chunk_decrypted = peer2.decrypt_with_key(chunk_encrypted, session_key)
        print(f"🔓 Chunk decrypted: {len(chunk_decrypted)} bytes")
        
        if chunk_decrypted == file_data:
            print("✅ File chunk encryption/decryption works")
        else:
            print("❌ File chunk encryption/decryption failed")
            print(f"Expected: {file_data[:50]}...")
            print(f"Got: {chunk_decrypted[:50]}...")
            return False
        
        print(f"\n🎉 ALL DIAGNOSTIC TESTS PASSED!")
        print(f"✅ Basic encryption/decryption works")
        print(f"✅ Cross-peer decryption works")
        print(f"✅ Session key management works")
        print(f"✅ IP fallback keys work")
        print(f"✅ File chunk scenario works")
        
        return True
        
    except Exception as e:
        print(f"❌ Diagnostic test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_common_issues():
    """Check for common decryption issues"""
    print(f"\n🔍 CHECKING COMMON ISSUES")
    print("=" * 50)
    
    issues = []
    
    # Check 1: Session key mismatch
    print("📋 Check 1: Session key consistency")
    try:
        from core.crypto import SecureCryptoCore, SessionKeys
        
        crypto1 = SecureCryptoCore('test1')
        crypto2 = SecureCryptoCore('test2')
        
        # Same key for both
        key = secrets.token_bytes(32)
        
        session1 = SessionKeys(encrypt_key=key, mac_key=key, peer_id='test2')
        session2 = SessionKeys(encrypt_key=key, mac_key=key, peer_id='test1')
        
        crypto1._session_keys['test'] = session1
        crypto2._session_keys['test'] = session2
        
        retrieved1 = crypto1.get_session_key('test2')
        retrieved2 = crypto2.get_session_key('test1')
        
        if retrieved1 == retrieved2 == key:
            print("✅ Session keys are consistent")
        else:
            print("❌ Session keys are inconsistent")
            issues.append("Session key mismatch")
            
    except Exception as e:
        print(f"❌ Session key check failed: {e}")
        issues.append("Session key error")
    
    # Check 2: Memory issues
    print("📋 Check 2: Memory management")
    try:
        from core.crypto import SecureMemory
        
        mem = SecureMemory(32)
        test_data = secrets.token_bytes(32)
        mem.write(test_data)
        read_data = mem.read()
        
        if read_data == test_data:
            print("✅ SecureMemory works correctly")
        else:
            print("❌ SecureMemory has issues")
            issues.append("SecureMemory error")
            
    except Exception as e:
        print(f"❌ SecureMemory check failed: {e}")
        issues.append("SecureMemory error")
    
    # Check 3: Algorithm consistency
    print("📋 Check 3: Algorithm consistency")
    try:
        from core.crypto import SecureCryptoCore
        
        crypto = SecureCryptoCore('test')
        
        data = b"Test data"
        key = secrets.token_bytes(32)
        
        encrypted1 = crypto.encrypt_with_key(data, key)
        encrypted2 = crypto.encrypt_with_key(data, key)
        
        # Same data and key should produce different ciphertext (due to random IV)
        if encrypted1 != encrypted2:
            print("✅ Encryption uses random IV (correct)")
        else:
            print("⚠️ Encryption might not use random IV")
        
        # But both should decrypt to the same data
        decrypted1 = crypto.decrypt_with_key(encrypted1, key)
        decrypted2 = crypto.decrypt_with_key(encrypted2, key)
        
        if decrypted1 == decrypted2 == data:
            print("✅ Algorithm consistency verified")
        else:
            print("❌ Algorithm inconsistency detected")
            issues.append("Algorithm inconsistency")
            
    except Exception as e:
        print(f"❌ Algorithm check failed: {e}")
        issues.append("Algorithm error")
    
    if issues:
        print(f"\n⚠️ FOUND ISSUES: {', '.join(issues)}")
        return False
    else:
        print(f"\n✅ NO COMMON ISSUES FOUND")
        return True

def main():
    """Run diagnostic tests"""
    print("🔍 PEER DECRYPTION DIAGNOSTIC TOOL")
    print("=" * 60)
    
    # Run comprehensive diagnostic
    diagnostic_success = diagnose_peer_decryption()
    
    # Check common issues
    common_issues_ok = check_common_issues()
    
    print(f"\n{'='*60}")
    print("🎯 DIAGNOSTIC SUMMARY:")
    print(f"   Comprehensive tests: {'✅ PASSED' if diagnostic_success else '❌ FAILED'}")
    print(f"   Common issues check: {'✅ PASSED' if common_issues_ok else '❌ FOUND ISSUES'}")
    
    if diagnostic_success and common_issues_ok:
        print(f"\n🎉 ALL DIAGNOSTICS PASSED!")
        print(f"✅ Encryption/decryption system is working correctly")
        print(f"✅ The issue might be in peer communication or session synchronization")
        print(f"\n💡 RECOMMENDATIONS:")
        print(f"   1. Ensure both peers use the same session key")
        print(f"   2. Check that session keys are properly synchronized")
        print(f"   3. Verify that IP fallback keys are created correctly")
        print(f"   4. Check network message delivery order")
    else:
        print(f"\n❌ DIAGNOSTICS FAILED!")
        print(f"⚠️ There are issues with the encryption/decryption system")
        print(f"\n🔧 TROUBLESHOOTING:")
        print(f"   1. Check session key creation and storage")
        print(f"   2. Verify SecureMemory implementation")
        print(f"   3. Ensure algorithm consistency")
        print(f"   4. Check for memory corruption or key mismatch")
    
    return diagnostic_success and common_issues_ok

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
