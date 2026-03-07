#!/usr/bin/env python3
"""
Проверка целостности и структуры проекта
"""

import os
import sys
from pathlib import Path

def check_project_structure():
    """Проверка структуры проекта"""
    print("🔍 Проверка структуры проекта Secure P2P Messenger")
    print("=" * 60)
    
    base_dir = Path(".")
    
    # Ожидаемая структура
    expected_structure = {
        "back": {
            "core": ["crypto.py", "exceptions.py", "secure_memory.py"],
            "network": ["connection.py", "discovery.py", "file_transfer.py", "onion_router.py"],
            "messaging": ["handshake.py", "offline_queue.py"],
            "storage": ["database.py"],
            "api": ["local_api.py"],
            "web.py": "file",
            "main.py": "file"
        },
        "frontend": {
            "css": ["styles.css"],
            "js": ["app.js"],
            "index.html": "file"
        },
        "tests": {
            "run_all_tests.py": "file",
            "quick_test.py": "file",
            "test_file_transfer.py": "file",
            "test_integration.py": "file",
            "test_file_transfer_fixes.py": "file",
            "test_complete_file_transfer.py": "file"
        },
        "downloads": "dir",
        "uploads": "dir",
        "requirements.txt": "file",
        "README.md": "file"
    }
    
    missing_items = []
    extra_items = []
    
    def check_structure(path, structure, current_path=""):
        """Рекурсивная проверка структуры"""
        for item, expected in structure.items():
            item_path = path / item
            
            if isinstance(expected, dict):
                # Директория
                if not item_path.is_dir():
                    missing_items.append(f"📁 {current_path}{item}/ (директория)")
                else:
                    check_structure(item_path, expected, f"{current_path}{item}/")
            elif expected == "dir":
                # Директория (без проверки содержимого)
                if not item_path.is_dir():
                    missing_items.append(f"📁 {current_path}{item}/ (директория)")
            elif expected == "file":
                # Файл
                if not item_path.is_file():
                    missing_items.append(f"📄 {current_path}{item} (файл)")
            elif isinstance(expected, list):
                # Директория с ожидаемыми файлами
                if not item_path.is_dir():
                    missing_items.append(f"📁 {current_path}{item}/ (директория)")
                else:
                    for subfile in expected:
                        subfile_path = item_path / subfile
                        if not subfile_path.is_file():
                            missing_items.append(f"📄 {current_path}{item}/{subfile}")
    
    # Проверка структуры
    check_structure(base_dir, expected_structure)
    
    # Проверка на лишние файлы в основных директориях
    core_files = [f for f in (base_dir / "back" / "core").glob("*.py") if f.is_file()]
    expected_core = {"crypto.py", "exceptions.py", "secure_memory.py"}
    extra_core = [f.name for f in core_files if f.name not in expected_core]
    
    network_files = [f for f in (base_dir / "back" / "network").glob("*.py") if f.is_file()]
    expected_network = {"connection.py", "discovery.py", "file_transfer.py", "onion_router.py", "protocols.py", "auto_relay.py"}
    extra_network = [f.name for f in network_files if f.name not in expected_network]
    
    # Результаты
    print(f"📋 Проверка завершена")
    print(f"📁 Рабочая директория: {base_dir.absolute()}")
    
    if missing_items:
        print(f"\n❌ Отсутствуют ({len(missing_items)}):")
        for item in missing_items:
            print(f"  {item}")
    else:
        print(f"\n✅ Все ожидаемые файлы и директории на месте")
    
    if extra_core:
        print(f"\n📄 Дополнительные файлы в core/: {extra_core}")
    
    if extra_network:
        print(f"\n📄 Дополнительные файлы в network/: {extra_network}")
    
    # Проверка тестов
    print(f"\n🧪 Проверка тестов...")
    try:
        import subprocess
        result = subprocess.run(
            [sys.executable, "tests/quick_test.py"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode == 0:
            print("✅ Быстрые тесты проходят")
        else:
            print("❌ Быстрые тесты не проходят")
            print(result.stdout[-500:])
    except Exception as e:
        print(f"❌ Ошибка запуска тестов: {e}")
    
    # Итог
    total_issues = len(missing_items)
    if total_issues == 0:
        print(f"\n🎉 Структура проекта корректна!")
        print("✨ Проект готов к использованию")
        return True
    else:
        print(f"\n⚠️ Обнаружено {total_issues} проблем в структуре")
        return False

if __name__ == "__main__":
    success = check_project_structure()
    sys.exit(0 if success else 1)
