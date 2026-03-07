#!/usr/bin/env python3
"""
Пример быстрого теста mesh-сети
"""

import sys
import os

# Добавить пути
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))

from mesh.mesh_test_suite import MeshTestSuite

def main():
    """Пример быстрого теста"""
    print("🚀 Пример быстрого теста mesh-сети")
    print("=" * 40)
    
    # Создание набора тестов
    test_suite = MeshTestSuite()
    
    try:
        # Запуск быстрого теста
        score = test_suite.run_quick_test()
        
        # Вывод результатов
        print(f"\n🎯 Результат быстрого теста: {score:.1f}%")
        
        # Оценка результата
        if score >= 85:
            print("✅ Отлично! Mesh-сеть работает идеально.")
        elif score >= 70:
            print("⚠️ Хорошо, но есть возможности для улучшения.")
        else:
            print("❌ Требуется настройка сети.")
        
        # Экспорт результатов
        filename = test_suite.report_generator.export_json()
        print(f"💾 Детальный отчет: {filename}")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
    finally:
        test_suite.cleanup()

if __name__ == "__main__":
    main()
