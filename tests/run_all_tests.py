#!/usr/bin/env python3
"""
Главный скрипт для запуска всех тестов проекта
"""

import sys
import os
import time
import subprocess
import json
from datetime import datetime

# Добавить пути
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'utils'))

def run_test_suite(script_name, description):
    """Запустить набор тестов"""
    print(f"\n{'='*60}")
    print(f"🧪 {description}")
    print(f"{'='*60}")
    
    start_time = time.time()
    
    try:
        # Полный путь к скрипту
        script_path = os.path.join(os.path.dirname(__file__), script_name)
        
        # Запуск скрипта
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, cwd=os.path.dirname(__file__))
        
        duration = time.time() - start_time
        
        if result.returncode == 0:
            print(f"✅ {description} завершен успешно")
            print(f"⏱️ Длительность: {duration:.1f} сек")
            
            # Вывод результатов
            if "Общая оценка:" in result.stdout:
                for line in result.stdout.split('\n'):
                    if "Общая оценка:" in line:
                        print(f"📊 {line.strip()}")
                        break
        else:
            print(f"❌ {description} завершился с ошибкой")
            print(f"⏱️ Длительность: {duration:.1f} сек")
            if result.stderr:
                print(f"🔍 Ошибка: {result.stderr.strip()}")
        
        return {
            'success': result.returncode == 0,
            'duration': duration,
            'stdout': result.stdout,
            'stderr': result.stderr
        }
        
    except Exception as e:
        print(f"❌ Критическая ошибка при запуске {description}: {e}")
        return {
            'success': False,
            'duration': time.time() - start_time,
            'error': str(e)
        }

def main():
    """Основная функция"""
    print("🚀 Запуск всех тестов проекта")
    print(f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📁 Директория: {os.path.dirname(__file__)}")
    
    total_start_time = time.time()
    test_results = []
    
    # 1. Интегрированные тесты (все компоненты)
    test_results.append(run_test_suite(
        'integrated/integrated_test_suite.py',
        'Интегрированные тесты (Mesh + Шифрование + Файлы)'
    ))
    
    # 2. Быстрый тест mesh-сети
    test_results.append(run_test_suite(
        'mesh/mesh_test_suite.py',
        'Быстрый тест Mesh-сети'
    ))
    
    # 3. Примеры тестов
    examples = [
        ('examples/quick_test.py', 'Пример быстрого теста'),
        ('examples/manual_test.py', 'Пример ручного теста'),
        ('examples/stress_test.py', 'Пример нагрузочного теста')
    ]
    
    for script, description in examples:
        test_results.append(run_test_suite(script, description))
    
    # Итоги
    total_duration = time.time() - total_start_time
    successful_tests = sum(1 for r in test_results if r['success'])
    total_tests = len(test_results)
    
    print(f"\n{'='*60}")
    print("🎯 ИТОГИ ВСЕХ ТЕСТОВ")
    print(f"{'='*60}")
    print(f"📊 Всего тестов: {total_tests}")
    print(f"✅ Успешных: {successful_tests}")
    print(f"❌ Неудачных: {total_tests - successful_tests}")
    print(f"⏱️ Общая длительность: {total_duration:.1f} сек")
    print(f"📈 Успешность: {(successful_tests/total_tests*100):.1f}%")
    
    # Детальная статистика
    print(f"\n📋 Детальная статистика:")
    for i, result in enumerate(test_results, 1):
        status = "✅" if result['success'] else "❌"
        print(f"  {i}. {status} {result.get('duration', 0):.1f} сек")
    
    # Сохранение отчета
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_duration': total_duration,
        'total_tests': total_tests,
        'successful_tests': successful_tests,
        'success_rate': successful_tests/total_tests*100,
        'test_results': [
            {
                'index': i+1,
                'success': result['success'],
                'duration': result.get('duration', 0),
                'error': result.get('error')
            }
            for i, result in enumerate(test_results)
        ]
    }
    
    reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
    os.makedirs(reports_dir, exist_ok=True)
    
    report_file = os.path.join(reports_dir, f'all_tests_report_{int(time.time())}.json')
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Отчет сохранен: {report_file}")
    
    # Рекомендации
    if successful_tests == total_tests:
        print("\n🎉 Отлично! Все тесты пройдены успешно!")
    elif successful_tests >= total_tests * 0.8:
        print("\n✅ Хорошо! Большинство тестов пройдены.")
    elif successful_tests >= total_tests * 0.5:
        print("\n⚠️ Требуется внимание. Некоторые тесты не пройдены.")
    else:
        print("\n❌ Критические проблемы. Большинство тестов не пройдены.")
    
    print(f"\n🌐 Проверьте детальные отчеты в папке: {reports_dir}")

if __name__ == "__main__":
    main()
