#!/usr/bin/env python3
"""
Test web API messaging
"""

import requests
import time

def test_web_messaging():
    """Test messaging through web API"""
    print("🔍 TESTING WEB API MESSAGING")
    print("=" * 50)
    
    try:
        # Test 1: Get peers
        print("📋 Test 1: Get peers")
        response = requests.get('http://localhost:8080/api/peers')
        if response.status_code == 200:
            peers = response.json()
            print(f"✅ Got peers: {len(peers.get('peers', []))} peers")
            for peer in peers.get('peers', []):
                print(f"   - {peer.get('username')} ({peer.get('ip')})")
        else:
            print(f"❌ Failed to get peers: {response.status_code}")
            return False
        
        # Test 2: Send message
        print("\n📋 Test 2: Send message")
        
        # Find first peer
        peers_list = peers.get('peers', [])
        if not peers_list:
            print("⚠️ No peers available, creating test message to web_user")
            test_peer = 'web_user'
        else:
            test_peer = peers_list[0].get('username')
        
        message_data = {
            'peer': test_peer,
            'text': f'Test message from API at {time.time()}'
        }
        
        response = requests.post('http://localhost:8080/api/send_message', 
                               json=message_data)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Message sent successfully: {result}")
        else:
            print(f"❌ Failed to send message: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        # Test 3: Get messages
        print("\n📋 Test 3: Get messages")
        response = requests.get(f'http://localhost:8080/api/messages?peer={test_peer}')
        
        if response.status_code == 200:
            messages = response.json()
            print(f"✅ Got messages: {len(messages.get('messages', []))} messages")
            for msg in messages.get('messages', [])[-3:]:  # Last 3 messages
                print(f"   - {msg.get('text')} ({msg.get('time')})")
        else:
            print(f"❌ Failed to get messages: {response.status_code}")
            print(f"Response: {response.text}")
            return False
        
        print(f"\n🎉 WEB API MESSAGING TEST PASSED!")
        print(f"✅ Peers API works")
        print(f"✅ Send message API works")
        print(f"✅ Get messages API works")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_web_messaging()
    exit(0 if success else 1)
