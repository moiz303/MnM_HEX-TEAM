#!/usr/bin/env python3
"""
Быстрый запуск основных тестов для проверки работоспособности системы
"""

import subprocess
import sys
import os

def quick_test():
    """Быстрый тест основных компонентов"""
    print("🚀 Quick Test - Secure P2P Messenger")
    print("=" * 50)
    
    tests = [
        ("tests/test_file_transfer.py", "File Transfer"),
        ("tests/test_integration.py", "Integration"),
        ("tests/test_file_transfer_fixes.py", "File Transfer Fixes")
    ]
    
    passed = 0
    total = len(tests)
    
    for test_file, test_name in tests:
        print(f"\n🧪 {test_name}...")
        try:
            result = subprocess.run(
                [sys.executable, test_file],
                cwd=os.path.join(os.path.dirname(__file__), '..'),  # Корневая директория
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                print(f"✅ {test_name}: PASSED")
                passed += 1
            else:
                print(f"❌ {test_name}: FAILED")
                print(result.stdout[-500:])  # Последние 500 символов
                
        except Exception as e:
            print(f"💥 {test_name}: ERROR - {e}")
    
    print(f"\n📊 Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 System ready!")
        return True
    else:
        print("⚠️ Some tests failed")
        return False

if __name__ == '__main__':
    success = quick_test()
    sys.exit(0 if success else 1)
