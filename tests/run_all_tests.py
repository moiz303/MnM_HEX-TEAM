#!/usr/bin/env python3
"""
Единый файл для запуска всех тестов системы Secure P2P Messenger
Включает:
- Unit тесты файловой передачи
- Интеграционные тесты
- Тесты исправленных кейсов
- Полный сценарий передачи файлов
"""

import sys
import os
import time
import subprocess
from pathlib import Path

# Добавляем путь к back директории
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'back'))

def run_test_file(test_file_path, test_name):
    """Запуск одного тестового файла"""
    print(f"\n{'='*80}")
    print(f"🧪 Running {test_name}")
    print(f"📁 File: {test_file_path}")
    print(f"{'='*80}")
    
    try:
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, test_file_path],
            cwd=os.path.join(os.path.dirname(__file__), '..'),  # Корневая директория
            capture_output=True,
            text=True,
            timeout=60  # 60 секунд таймаут
        )
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {test_name}: PASSED ({duration:.2f}s)")
            print("📋 Output:")
            print(result.stdout)
            return True
        else:
            print(f"❌ {test_name}: FAILED ({duration:.2f}s)")
            print("📋 Output:")
            print(result.stdout)
            if result.stderr:
                print("📋 Errors:")
                print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_name}: TIMEOUT (60s)")
        return False
    except Exception as e:
        print(f"💥 {test_name}: ERROR - {e}")
        return False

def run_import_test():
    """Тест импорта всех модулей"""
    print(f"\n{'='*80}")
    print("🔍 Testing Module Imports")
    print(f"{'='*80}")
    
    try:
        # Тест импорта основных модулей
        modules_to_test = [
            'core.crypto',
            'core.exceptions', 
            'core.secure_memory',
            'network.connection',
            'network.discovery',
            'network.file_transfer',
            'network.onion_router',
            'network.protocols',
            'messaging.handshake',
            'storage.database',
            'api',
            'main'
        ]
        
        failed_imports = []
        
        for module in modules_to_test:
            try:
                __import__(module)
                print(f"✅ {module}")
            except ImportError as e:
                print(f"❌ {module}: {e}")
                failed_imports.append(module)
        
        if failed_imports:
            print(f"\n❌ {len(failed_imports)} modules failed to import")
            return False
        else:
            print(f"\n✅ All {len(modules_to_test)} modules imported successfully")
            return True
            
    except Exception as e:
        print(f"💥 Import test error: {e}")
        return False

def run_basic_functionality_test():
    """Базовый тест функциональности"""
    print(f"\n{'='*80}")
    print("🔧 Testing Basic Functionality")
    print(f"{'='*80}")
    
    try:
        from core.crypto import SecureCryptoCore
        from network.file_transfer import FileTransferManager
        from network.protocols import MessageType, Limits
        from network.onion_router import OnionRouter
        
        # Тест криптографии
        crypto = SecureCryptoCore('test_device')
        print("✅ SecureCryptoCore initialization")
        
        # Тест файлового менеджера с mock объектами
        class MockCrypto:
            def get_session_key(self, peer_id):
                return b'test_key_123456789012345678901234'
        
        class MockConnMgr:
            def send_to_peer(self, ip, data):
                return True
        
        manager = FileTransferManager(MockConnMgr(), MockCrypto())
        print("✅ FileTransferManager initialization")
        
        # Тест onion router
        router = OnionRouter(MockConnMgr(), MockCrypto())
        print("✅ OnionRouter initialization")
        
        # Тест протоколов
        assert MessageType.FILE_OFFER == "file_offer"
        assert Limits.MAX_FILE_SIZE > 0
        print("✅ Protocol constants")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic functionality test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Запуск всех тестов"""
    print("🚀 Starting Comprehensive Test Suite")
    print("🔧 Secure P2P Messenger - All Tests")
    print(f"📅 {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📍 Working Directory: {os.getcwd()}")
    
    # Список всех тестов
    tests = [
        ("Module Imports", run_import_test),
        ("Basic Functionality", run_basic_functionality_test),
        ("File Transfer System", "tests/test_file_transfer.py"),
        ("Integration Tests", "tests/test_integration.py"), 
        ("File Transfer Fixes", "tests/test_file_transfer_fixes.py"),
        ("Complete File Transfer Scenario", "tests/test_complete_file_transfer.py"),
    ]
    
    results = []
    total_start_time = time.time()
    
    for test_name, test_func in tests:
        if callable(test_func):
            # Встроенная функция теста
            success = test_func()
        else:
            # Внешний тестовый файл
            success = run_test_file(test_func, test_name)
        
        results.append((test_name, success))
        
        # Небольшая пауза между тестами
        time.sleep(0.5)
    
    # Итоговые результаты
    total_duration = time.time() - total_start_time
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    print(f"\n{'='*80}")
    print("📊 FINAL TEST RESULTS")
    print(f"{'='*80}")
    print(f"⏱️  Total Duration: {total_duration:.2f} seconds")
    print(f"📈 Tests Passed: {passed}/{total}")
    print(f"📊 Success Rate: {(passed/total)*100:.1f}%")
    
    print(f"\n📋 Detailed Results:")
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"  {status} {test_name}")
    
    if passed == total:
        print(f"\n🎉 ALL TESTS PASSED! 🎉")
        print("✨ System is ready for production use!")
        return True
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        print("🔧 Please review and fix the failing tests before deployment")
        return False

if __name__ == '__main__':
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
