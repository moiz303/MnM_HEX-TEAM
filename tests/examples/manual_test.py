#!/usr/bin/env python3
"""
Пример ручного тестирования mesh-сети
"""

import sys
import os
import time

# Добавить пути
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))

from test_config import TestConfig
from utils.test_node import TestNodeManager
from utils.report_generator import ReportGenerator

def main():
    """Пример ручного тестирования"""
    print("🎮 Пример ручного тестирования mesh-сети")
    print("=" * 50)
    
    # Создание менеджера узлов
    node_manager = TestNodeManager()
    report_generator = ReportGenerator()
    
    try:
        # Добавление узлов
        print("👥 Добавление узлов...")
        node_manager.add_node("Alice", port_offset=0)
        node_manager.add_node("Bob", port_offset=10)
        node_manager.add_node("Charlie", port_offset=20)
        
        # Запуск узлов
        print("🚀 Запуск узлов...")
        results = node_manager.start_all()
        
        if not any(results.values()):
            print("❌ Не удалось запустить узлы")
            return
        
        # Ожидание инициализации
        print("⏳ Ожидание инициализации (5 сек)...")
        time.sleep(5)
        
        # Ручное тестирование хендшейков
        print("\n🤝 Ручное тестирование хендшейков...")
        alice = node_manager.get_node("Alice")
        bob = node_manager.get_node("Bob")
        charlie = node_manager.get_node("Charlie")
        
        handshake_results = {
            'total_handshakes': 0,
            'successful_handshakes': 0,
            'details': []
        }
        
        # Alice <-> Bob
        handshake_results['total_handshakes'] += 1
        if alice.simulate_handshake("Bob"):
            handshake_results['successful_handshakes'] += 1
            handshake_results['details'].append("Alice-Bob: ✅")
        else:
            handshake_results['details'].append("Alice-Bob: ❌")
        
        # Alice <-> Charlie
        handshake_results['total_handshakes'] += 1
        if alice.simulate_handshake("Charlie"):
            handshake_results['successful_handshakes'] += 1
            handshake_results['details'].append("Alice-Charlie: ✅")
        else:
            handshake_results['details'].append("Alice-Charlie: ❌")
        
        # Bob <-> Charlie
        handshake_results['total_handshakes'] += 1
        if bob.simulate_handshake("Charlie"):
            handshake_results['successful_handshakes'] += 1
            handshake_results['details'].append("Bob-Charlie: ✅")
        else:
            handshake_results['details'].append("Bob-Charlie: ❌")
        
        # Вывод результатов хендшейков
        print("📊 Результаты хендшейков:")
        for detail in handshake_results['details']:
            print(f"   {detail}")
        
        handshake_success_rate = (handshake_results['successful_handshakes'] / 
                                handshake_results['total_handshakes'] * 100) if handshake_results['total_handshakes'] > 0 else 0
        
        report_generator.add_test_result(
            "manual_handshakes",
            handshake_success_rate,
            5.0,
            handshake_results
        )
        
        # Ручное тестирование сообщений
        print("\n📤 Ручное тестирование сообщений...")
        
        message_results = {
            'total_messages': 0,
            'successful_deliveries': 0,
            'details': []
        }
        
        test_messages = [
            ("Alice", "Bob", "Hello from Alice!"),
            ("Bob", "Charlie", "Hey Charlie!"),
            ("Charlie", "Alice", "Hi Alice!"),
            ("Alice", "Charlie", "How are you?"),
            ("Bob", "Alice", "Good morning!"),
        ]
        
        for sender_name, receiver_name, message in test_messages:
            sender = node_manager.get_node(sender_name)
            receiver = node_manager.get_node(receiver_name)
            
            message_results['total_messages'] += 1
            
            if sender.send_message_to(receiver_name, message):
                receiver.receive_message(sender_name, message)
                message_results['successful_deliveries'] += 1
                message_results['details'].append(f"{sender_name}→{receiver_name}: ✅")
            else:
                message_results['details'].append(f"{sender_name}→{receiver_name}: ❌")
            
            time.sleep(0.5)
        
        # Вывод результатов сообщений
        print("📊 Результаты сообщений:")
        for detail in message_results['details']:
            print(f"   {detail}")
        
        message_success_rate = (message_results['successful_deliveries'] / 
                                message_results['total_messages'] * 100) if message_results['total_messages'] > 0 else 0
        
        report_generator.add_test_result(
            "manual_messages",
            message_success_rate,
            10.0,
            message_results
        )
        
        # Итоговая оценка
        overall_score = (handshake_success_rate + message_success_rate) / 2
        
        print(f"\n🎯 Общая оценка: {overall_score:.1f}%")
        
        # Статистика узлов
        print("\n📈 Статистика узлов:")
        for node_name, node in node_manager.nodes.items():
            stats = node.get_status()
            custom_stats = stats.get('custom_stats', {})
            print(f"   {node_name}:")
            print(f"     Отправлено: {custom_stats.get('messages_sent', 0)}")
            print(f"     Получено: {custom_stats.get('messages_received', 0)}")
            print(f"     Хендшейки: {custom_stats.get('handshakes_completed', 0)}")
            print(f"     Ошибки: {custom_stats.get('errors', 0)}")
        
        # Экспорт результатов
        report_generator.print_summary()
        filename = report_generator.export_json()
        print(f"\n💾 Детальный отчет: {filename}")
        
    except Exception as e:
        print(f"❌ Ошибка тестирования: {e}")
        import traceback
        traceback.print_exc()
    finally:
        node_manager.stop_all()

if __name__ == "__main__":
    main()
