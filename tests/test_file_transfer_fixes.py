#!/usr/bin/env python3
"""
Комплексные тесты для исправленных кейсов передачи файлов:
1. Нормализация IP адресов в device ID
2. Обработка FILE_ACCEPT сообщений
3. Обработка DELIVERY_RECEIPT (ACK) сообщений
4. Исправленные вызовы методов соединения
"""

import sys
import os
import time
import threading
from pathlib import Path

# Добавляем путь к back директории
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'back'))

def test_ip_to_device_id_normalization():
    """Тест нормализации IP адресов в device ID"""
    print("\n🔍 Testing IP to Device ID normalization...")
    
    try:
        from network.file_transfer import FileTransferManager
        
        # Mock зависимости
        class MockCrypto:
            def __init__(self):
                self._session_keys = {}
                self.device_id = 'test_device_123456789012'
            
            def get_session_key(self, peer_id):
                return b'test_key_123456789012345678901234'
        
        class MockDiscovery:
            def get_all_peers(self):
                return {
                    '192.168.1.100': {
                        'device_id': 'peer_device_abcdef123456',
                        'username': 'test_peer'
                    }
                }
        
        class MockConnMgr:
            def __init__(self):
                self.discovery = MockDiscovery()
            
            def send_to_peer(self, ip, data):
                return True
        
        class MockRouter:
            def __init__(self):
                self.discovery = MockDiscovery()
        
        # Тест нормализации
        crypto = MockCrypto()
        conn_mgr = MockConnMgr()
        router = MockRouter()
        manager = FileTransferManager(conn_mgr, crypto, router)
        
        # Тест 1: IP адрес должен конвертироваться в device_id
        ip_address = '192.168.1.100'
        normalized = manager._normalize_sender_id(ip_address)
        expected_device_id = 'peer_device_abcdef123456'
        
        assert normalized == expected_device_id, f"Expected {expected_device_id}, got {normalized}"
        print("✅ IP address normalization works correctly")
        
        # Тест 2: Device ID должен остаться без изменений
        device_id = 'existing_device_id_123456'
        normalized = manager._normalize_sender_id(device_id)
        assert normalized == device_id, f"Device ID should remain unchanged"
        print("✅ Device ID passthrough works correctly")
        
        # Тест 3: Неизвестный IP должен использовать fallback
        unknown_ip = '10.0.0.1'
        normalized = manager._normalize_sender_id(unknown_ip)
        assert normalized == unknown_ip, f"Unknown IP should fallback to original"
        print("✅ Unknown IP fallback works correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Normalization test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_file_accept_handling():
    """Тест обработки FILE_ACCEPT сообщений"""
    print("\n🔍 Testing FILE_ACCEPT message handling...")
    
    try:
        from network.file_transfer import FileTransferManager, TransferSession, FileInfo
        from network.protocols import MessageType
        
        # Mock зависимости
        class MockCrypto:
            def get_session_key(self, peer_id):
                return b'test_key_123456789012345678901234'
        
        class MockConnMgr:
            def send_to_peer(self, ip, data):
                return True
        
        manager = FileTransferManager(MockConnMgr(), MockCrypto())
        
        # Создаем тестовую сессию загрузки
        file_info = FileInfo(
            file_id='test_file_123',
            filename='test.txt',
            file_size=1024,
            file_hash='abc123',
            mime_type='text/plain',
            chunk_count=1,
            sender_id='sender_device_123',
            receiver_id='receiver_device_456'
        )
        
        session = TransferSession(
            transfer_id='test_file_123',
            file_info=file_info,
            direction='upload',
            target_ip='192.168.1.100'
        )
        
        with manager.transfer_lock:
            manager.active_transfers['test_file_123'] = session
        
        # Тест обработки FILE_ACCEPT
        accept_data = {
            'file_id': 'test_file_123',
            'port': 5000
        }
        
        # Не должно вызывать исключений
        manager.handle_file_accept(accept_data, '192.168.1.100')
        print("✅ FILE_ACCEPT handling works correctly")
        
        # Тест обработки FILE_ACCEPT для несуществующего файла
        try:
            manager.handle_file_accept({'file_id': 'nonexistent'}, '192.168.1.100')
            print("✅ Non-existent file accept handled gracefully")
        except Exception:
            print("❌ Non-existent file accept caused exception")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ FILE_ACCEPT test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_delivery_receipt_handling():
    """Тест обработки DELIVERY_RECEIPT (ACK) сообщений"""
    print("\n🔍 Testing DELIVERY_RECEIPT message handling...")
    
    try:
        from network.file_transfer import FileTransferManager, TransferSession, FileInfo, ChunkInfo
        
        # Mock зависимости
        class MockCrypto:
            def get_session_key(self, peer_id):
                return b'test_key_123456789012345678901234'
        
        class MockConnMgr:
            def send_to_peer(self, ip, data):
                return True
        
        manager = FileTransferManager(MockConnMgr(), MockCrypto())
        
        # Создаем тестовую сессию загрузки с чанками
        file_info = FileInfo(
            file_id='test_file_456',
            filename='test.txt',
            file_size=1024,
            file_hash='abc123',
            mime_type='text/plain',
            chunk_count=2,
            sender_id='sender_device_123',
            receiver_id='receiver_device_456'
        )
        
        chunk1 = ChunkInfo(
            chunk_index=0,
            data=b'test data 1',
            chunk_hash='hash1',
            chunk_size=10
        )
        chunk1.msg_id = 'msg_123'  # Add msg_id for ACK matching
        
        chunk2 = ChunkInfo(
            chunk_index=1,
            data=b'test data 2',
            chunk_hash='hash2',
            chunk_size=10
        )
        
        session = TransferSession(
            transfer_id='test_file_456',
            file_info=file_info,
            direction='upload',
            target_ip='192.168.1.100'
        )
        session.chunks[0] = chunk1
        session.chunks[1] = chunk2
        
        with manager.transfer_lock:
            manager.active_transfers['test_file_456'] = session
        
        # Тест обработки ACK для первого чанка
        ack_data = {
            'in_response_to': 'msg_123',
            'status': 'delivered'
        }
        
        # Создаем ожидание ACK для чанка 0
        ack_key = f"test_file_456:0"
        manager.pending_acks[ack_key] = threading.Event()
        
        # Обрабатываем ACK
        manager.handle_delivery_receipt(ack_data, '192.168.1.100')
        
        # Проверяем что чанк отмечен как завершенный
        assert 0 in session.completed_chunks, "Chunk 0 should be marked as completed"
        print("✅ DELIVERY_RECEIPT handling works correctly")
        
        # Тест обработки ACK с неверным статусом
        wrong_ack_data = {
            'in_response_to': 'msg_456',
            'status': 'failed'
        }
        
        initial_completed = len(session.completed_chunks)
        manager.handle_delivery_receipt(wrong_ack_data, '192.168.1.100')
        assert len(session.completed_chunks) == initial_completed, "Failed ACK should not mark chunk as completed"
        print("✅ Failed ACK status handled correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ DELIVERY_RECEIPT test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_method_call_fixes():
    """Тест исправленных вызовов методов"""
    print("\n🔍 Testing method call fixes...")
    
    try:
        from network.file_transfer import FileTransferManager
        from network.protocols import MessageType, create_message
        
        # Mock зависимости с правильными методами
        class MockConnMgr:
            def __init__(self):
                self.send_to_peer_called = False
                self.last_ip = None
                self.last_data = None
            
            def send_to_peer(self, ip, data):
                self.send_to_peer_called = True
                self.last_ip = ip
                self.last_data = data
                return True
        
        class MockCrypto:
            def get_session_key(self, peer_id):
                return b'test_key_123456789012345678901234'
        
        conn_mgr = MockConnMgr()
        manager = FileTransferManager(conn_mgr, MockCrypto())
        
        # Тетод _send_chunk_ack должен использовать send_to_peer
        manager._send_chunk_ack('test_transfer', 0, '192.168.1.100', 'msg_123')
        
        assert conn_mgr.send_to_peer_called, "send_to_peer should be called"
        assert conn_mgr.last_ip == '192.168.1.100', "Correct IP should be used"
        assert conn_mgr.last_data['type'] == MessageType.DELIVERY_RECEIPT, "Should send DELIVERY_RECEIPT"
        print("✅ _send_chunk_ack uses correct method")
        
        # Сброс
        conn_mgr.send_to_peer_called = False
        
        # Тестируем отмену передачи
        with manager.transfer_lock:
            session = type('MockSession', (), {
                'status': 'in_progress',
                'file_info': type('MockFileInfo', (), {
                    'receiver_id': 'receiver_123',
                    'sender_id': 'sender_456'
                })(),
                'direction': 'upload'
            })()
            manager.active_transfers['test_transfer'] = session
        
        result = manager.cancel_transfer('test_transfer')
        
        assert conn_mgr.send_to_peer_called, "cancel_transfer should use send_to_peer"
        assert conn_mgr.last_data['type'] == MessageType.FILE_ERROR, "Should send FILE_ERROR"
        print("✅ cancel_transfer uses correct method")
        
        return True
        
    except Exception as e:
        print(f"❌ Method call fixes test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_onion_router_integration():
    """Тест интеграции с Onion Router"""
    print("\n🔍 Testing Onion Router integration...")
    
    try:
        from network.onion_router import OnionRouter
        from network.file_transfer import FileTransferManager
        
        # Mock зависимости
        class MockConnMgr:
            def send_to_peer(self, ip, data):
                return True
        
        class MockCrypto:
            def get_session_key(self, peer_id):
                return b'test_key_123456789012345678901234'
        
        conn_mgr = MockConnMgr()
        crypto = MockCrypto()
        router = OnionRouter(conn_mgr, crypto)
        
        # Тест маршрутизации FILE_ACCEPT
        accept_data = {
            'file_id': 'test_file',
            'port': 5000
        }
        
        # Не должно вызывать исключений
        router.handle_incoming('file_accept', accept_data, '192.168.1.100')
        print("✅ Onion Router routes FILE_ACCEPT correctly")
        
        # Тест маршрутизации DELIVERY_RECEIPT
        receipt_data = {
            'in_response_to': 'msg_123',
            'status': 'delivered'
        }
        
        router.handle_incoming('delivery_receipt', receipt_data, '192.168.1.100')
        print("✅ Onion Router routes DELIVERY_RECEIPT correctly")
        
        return True
        
    except Exception as e:
        print(f"❌ Onion Router integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Запуск всех тестов"""
    print("🚀 Starting File Transfer Fixes Tests")
    print("=" * 60)
    
    tests = [
        ("IP to Device ID Normalization", test_ip_to_device_id_normalization),
        ("FILE_ACCEPT Handling", test_file_accept_handling),
        ("DELIVERY_RECEIPT Handling", test_delivery_receipt_handling),
        ("Method Call Fixes", test_method_call_fixes),
        ("Onion Router Integration", test_onion_router_integration),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: PASSED")
            else:
                print(f"❌ {test_name}: FAILED")
        except Exception as e:
            print(f"❌ {test_name}: ERROR - {e}")
    
    print(f"\n{'='*60}")
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All file transfer fixes tests passed!")
        return True
    else:
        print(f"⚠️ {total - passed} test(s) failed")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
