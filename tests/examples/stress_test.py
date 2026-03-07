#!/usr/bin/env python3
"""
Пример нагрузочного тестирования mesh-сети
"""

import sys
import os
import time

# Добавить пути
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))

from test_config import TestConfig
from utils.mesh_simulator import MeshSimulator
from utils.report_generator import ReportGenerator

def main():
    """Пример нагрузочного тестирования"""
    print("⚡ Пример нагрузочного тестирования mesh-сети")
    print("=" * 50)
    
    # Создание симулятора
    simulator = MeshSimulator()
    report_generator = ReportGenerator()
    
    try:
        # Настройка сети для нагрузочного теста
        print("👥 Настройка сети для нагрузочного теста...")
        
        # Создаем больше узлов для нагрузочного теста
        node_names = [f"Node{i}" for i in range(1, 8)]  # 7 узлов
        
        print(f"   Запуск {len(node_names)} узлов...")
        results = simulator.start_network(node_names)
        
        if not any(results.values()):
            print("❌ Не удалось запустить узлы")
            return
        
        # Ожидание инициализации
        print("⏳ Ожидание полной инициализации (10 сек)...")
        time.sleep(10)
        
        # Фаза 1: Базовая нагрузка
        print("\n📊 Фаза 1: Базовая нагрузка (5 сообщений/сек, 30 сек)...")
        phase1_results = simulator.simulate_network_stress(
            duration=30,
            message_rate=5
        )
        
        print(f"   Отправлено: {phase1_results['actual_messages_sent']}")
        print(f"   Доставлено: {phase1_results['actual_messages_delivered']}")
        print(f"   Пропускная способность: {phase1_results['throughput']:.2f} msg/s")
        print(f"   Средняя задержка: {phase1_results['average_latency']:.3f}s")
        
        phase1_score = min(100.0, (phase1_results['throughput'] / (len(node_names) * 6.5) * 100))  # Ожидаемая пропускная способность
        
        report_generator.add_test_result(
            "stress_phase1_basic",
            phase1_score,
            30.0,
            phase1_results
        )
        
        # Пауза между фазами
        print("\n⏸️ Пауза между фазами (5 сек)...")
        time.sleep(5)
        
        # Фаза 2: Высокая нагрузка
        print("\n📊 Фаза 2: Высокая нагрузка (10 сообщений/сек, 30 сек)...")
        phase2_results = simulator.simulate_network_stress(
            duration=30,
            message_rate=10
        )
        
        print(f"   Отправлено: {phase2_results['actual_messages_sent']}")
        print(f"   Доставлено: {phase2_results['actual_messages_delivered']}")
        print(f"   Пропускная способность: {phase2_results['throughput']:.2f} msg/s")
        print(f"   Средняя задержка: {phase2_results['average_latency']:.3f}s")
        print(f"   Ошибки сети: {phase2_results['network_errors']}")
        
        phase2_score = min(100.0, (phase2_results['throughput'] / (len(node_names) * 13) * 100))
        
        report_generator.add_test_result(
            "stress_phase2_high",
            phase2_score,
            30.0,
            phase2_results
        )
        
        # Пауза между фазами
        print("\n⏸️ Пауза между фазами (5 сек)...")
        time.sleep(5)
        
        # Фаза 3: Экстремальная нагрузка
        print("\n📊 Фаза 3: Экстремальная нагрузка (15 сообщений/сек, 20 сек)...")
        phase3_results = simulator.simulate_network_stress(
            duration=20,
            message_rate=15
        )
        
        print(f"   Отправлено: {phase3_results['actual_messages_sent']}")
        print(f"   Доставлено: {phase3_results['actual_messages_delivered']}")
        print(f"   Пропускная способность: {phase3_results['throughput']:.2f} msg/s")
        print(f"   Средняя задержка: {phase3_results['average_latency']:.3f}s")
        print(f"   Ошибки сети: {phase3_results['network_errors']}")
        
        phase3_score = min(100.0, (phase3_results['throughput'] / (len(node_names) * 20) * 100))
        
        report_generator.add_test_result(
            "stress_phase3_extreme",
            phase3_score,
            20.0,
            phase3_results
        )
        
        # Анализ результатов
        print("\n📈 Анализ результатов нагрузочного теста:")
        
        total_score = (phase1_score + phase2_score + phase3_score) / 3
        total_duration = phase1_results['actual_duration'] + phase2_results['actual_duration'] + phase3_results['actual_duration']
        total_messages = phase1_results['actual_messages_sent'] + phase2_results['actual_messages_sent'] + phase3_results['actual_messages_sent']
        total_delivered = phase1_results['actual_messages_delivered'] + phase2_results['actual_messages_delivered'] + phase3_results['actual_messages_delivered']
        
        print(f"   Общая длительность: {total_duration:.1f} сек")
        print(f"   Всего отправлено: {total_messages}")
        print(f"   Всего доставлено: {total_delivered}")
        print(f"   Общая пропускная способность: {total_delivered/total_duration:.2f} msg/s")
        print(f"   Общая успешность: {(total_delivered/total_messages*100):.1f}%")
        
        # Оценка производительности
        performance_rating = "Отлично"
        if total_score < 70:
            performance_rating = "Требует улучшения"
        elif total_score < 85:
            performance_rating = "Хорошо"
        
        print(f"   Оценка производительности: {performance_rating}")
        
        # Добавление общего результата
        report_generator.add_test_result(
            "stress_test_overall",
            total_score,
            total_duration,
            {
                'total_messages': total_messages,
                'total_delivered': total_delivered,
                'throughput': total_delivered/total_duration,
                'performance_rating': performance_rating,
                'phases': {
                    'phase1': phase1_results,
                    'phase2': phase2_results,
                    'phase3': phase3_results
                }
            }
        )
        
        # Метрики сети
        print("\n🌐 Метрики сети:")
        network_status = simulator.get_network_status()
        print(f"   Активных узлов: {network_status['node_summary']['running_nodes']}/{network_status['node_summary']['total_nodes']}")
        print(f"   Событий в сети: {network_status['total_events']}")
        
        performance_metrics = simulator.get_performance_metrics()
        print(f"   Успешность доставки: {performance_metrics['success_rate']:.1f}%")
        print(f"   Уровень ошибок: {performance_metrics['error_rate']:.1f}%")
        
        # Вывод отчета
        print(f"\n🎯 Общая оценка нагрузочного теста: {total_score:.1f}%")
        
        report_generator.print_summary()
        filename = report_generator.export_json()
        print(f"💾 Детальный отчет: {filename}")
        
        # Рекомендации по оптимизации
        print("\n💡 Рекомендации по оптимизации:")
        if total_score >= 85:
            print("   ✅ Система отлично справляется с нагрузкой")
            print("   ✅ Можно рассмотреть увеличение количества узлов")
        elif total_score >= 70:
            print("   ⚠️ Система работает хорошо, но есть возможности для улучшения")
            print("   ⚠️ Рассмотрите оптимизацию алгоритмов маршрутизации")
        else:
            print("   ❌ Система требует оптимизации для работы под нагрузкой")
            print("   ❌ Увеличьте ресурсы и оптимизируйте сетевые компоненты")
        
    except Exception as e:
        print(f"❌ Ошибка нагрузочного теста: {e}")
        import traceback
        traceback.print_exc()
    finally:
        simulator.stop_network()

if __name__ == "__main__":
    main()
