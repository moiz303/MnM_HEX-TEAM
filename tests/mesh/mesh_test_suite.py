#!/usr/bin/env python3
"""
Единый скрипт тестирования mesh-сети
"""

import sys
import os
import time
import signal
import argparse
from typing import Dict, List, Any

# Добавить пути
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))

from utils.test_config import TestConfig
from utils.test_node import TestNodeManager
from utils.mesh_simulator import MeshSimulator
from utils.report_generator import ReportGenerator

class MeshTestSuite:
    """Основной набор тестов mesh-сети"""
    
    def __init__(self):
        self.simulator = MeshSimulator()
        self.report_generator = ReportGenerator()
        self.running = False
        
        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов"""
        print(f"\n\n🛑 Получен сигнал {signum}, остановка тестов...")
        self.running = False
        self.simulator.stop_network()
        sys.exit(0)
    
    def run_quick_test(self) -> float:
        """Быстрый тест (3 узла)"""
        print("🚀 Запуск быстрого теста mesh-сети")
        print("=" * 40)
        
        start_time = time.time()
        
        try:
            # Настройка и запуск сети
            node_names = TestConfig.DEFAULT_NODES
            results = self.simulator.start_network(node_names)
            
            if not any(results.values()):
                print("❌ Не удалось запустить ни один узел")
                return 0.0
            
            # Тест 1: Хендшейки
            print("\n🤝 Тестирование хендшейков...")
            handshake_results = self.simulator.simulate_handshakes()
            handshake_success_rate = (handshake_results['successful_handshakes'] / 
                                   handshake_results['total_handshakes'] * 100) if handshake_results['total_handshakes'] > 0 else 0
            
            self.report_generator.add_test_result(
                "handshakes", 
                handshake_success_rate,
                time.time() - start_time,
                handshake_results
            )
            
            # Тест 2: Связность
            print("\n🔗 Тестирование связности...")
            comm_results = self.simulator.simulate_message_exchange(TestConfig.QUICK_TEST_MESSAGES)
            connectivity_success_rate = (comm_results['successful_deliveries'] / 
                                       comm_results['total_messages'] * 100) if comm_results['total_messages'] > 0 else 0
            
            self.report_generator.add_test_result(
                "connectivity",
                connectivity_success_rate,
                time.time() - start_time,
                comm_results
            )
            
            # Общая оценка
            overall_score = (handshake_success_rate + connectivity_success_rate) / 2
            
            return overall_score
            
        finally:
            self.simulator.stop_network()
    
    def run_full_test(self) -> float:
        """Полный тест (5 узлов)"""
        print("🧪 Запуск полного теста mesh-сети")
        print("=" * 50)
        
        start_time = time.time()
        
        try:
            # Настройка и запуск сети
            node_names = TestConfig.FULL_TEST_NODES
            results = self.simulator.start_network(node_names)
            
            if not any(results.values()):
                print("❌ Не удалось запустить ни один узел")
                return 0.0
            
            test_scores = []
            
            # Тест 1: Хендшейки
            print("\n🤝 Тестирование хендшейков...")
            handshake_results = self.simulator.simulate_handshakes()
            handshake_success_rate = (handshake_results['successful_handshakes'] / 
                                   handshake_results['total_handshakes'] * 100) if handshake_results['total_handshakes'] > 0 else 0
            
            self.report_generator.add_test_result(
                "handshakes",
                handshake_success_rate,
                time.time() - start_time,
                handshake_results
            )
            test_scores.append(handshake_success_rate)
            
            # Тест 2: Связность
            print("\n🔗 Тестирование связности...")
            comm_results = self.simulator.simulate_message_exchange(TestConfig.FULL_TEST_MESSAGES)
            connectivity_success_rate = (comm_results['successful_deliveries'] / 
                                       comm_results['total_messages'] * 100) if comm_results['total_messages'] > 0 else 0
            
            self.report_generator.add_test_result(
                "connectivity",
                connectivity_success_rate,
                time.time() - start_time,
                comm_results
            )
            test_scores.append(connectivity_success_rate)
            
            # Тест 3: Офлайн-доставка
            print("\n📦 Тестирование офлайн-доставки...")
            offline_results = self.simulator.simulate_offline_delivery()
            offline_success_rate = 100.0 if offline_results.get('success', False) else 0.0
            
            self.report_generator.add_test_result(
                "offline_delivery",
                offline_success_rate,
                time.time() - start_time,
                offline_results
            )
            test_scores.append(offline_success_rate)
            
            # Тест 4: Производительность
            print("\n⚡ Тестирование производительности...")
            perf_results = self.simulator.simulate_network_stress(duration=30, message_rate=5)
            performance_score = min(100.0, (perf_results['actual_messages_delivered'] / 
                                         perf_results['actual_messages_sent'] * 100)) if perf_results['actual_messages_sent'] > 0 else 0
            
            self.report_generator.add_test_result(
                "performance",
                performance_score,
                time.time() - start_time,
                perf_results
            )
            test_scores.append(performance_score)
            
            # Общая оценка
            overall_score = sum(test_scores) / len(test_scores)
            
            return overall_score
            
        finally:
            self.simulator.stop_network()
    
    def run_stress_test(self) -> float:
        """Нагрузочный тест (10 узлов)"""
        print("⚡ Запуск нагрузочного теста mesh-сети")
        print("=" * 50)
        
        start_time = time.time()
        
        try:
            # Настройка и запуск сети
            node_names = TestConfig.STRESS_TEST_NODES
            results = self.simulator.start_network(node_names)
            
            if not any(results.values()):
                print("❌ Не удалось запустить ни один узел")
                return 0.0
            
            # Нагрузочное тестирование
            print("\n⚡ Нагрузочное тестирование...")
            stress_results = self.simulator.simulate_network_stress(duration=60, message_rate=10)
            
            # Оценка производительности
            target_throughput = TestConfig.STRESS_TEST_MESSAGES * 9  # 10 узлов, каждый с 9 другими
            actual_throughput = stress_results['throughput']
            performance_score = min(100.0, (actual_throughput / target_throughput * 100))
            
            self.report_generator.add_test_result(
                "stress_test",
                performance_score,
                time.time() - start_time,
                stress_results
            )
            
            return performance_score
            
        finally:
            self.simulator.stop_network()
    
    def run_interactive_test(self):
        """Интерактивный режим тестирования"""
        print("🎮 Интерактивный режим тестирования mesh-сети")
        print("Доступные команды:")
        print("  quick    - быстрый тест")
        print("  full     - полный тест")
        print("  stress   - нагрузочный тест")
        print("  status   - показать статус сети")
        print("  report   - показать отчет")
        print("  export   - экспорт результатов")
        print("  quit     - выход")
        print()
        
        # Запуск базовой сети для интерактивного режима
        node_names = TestConfig.DEFAULT_NODES
        self.simulator.start_network(node_names)
        
        try:
            while True:
                command = input("(mesh-test) ").strip().lower()
                
                if command == 'quit' or command == 'exit':
                    break
                elif command == 'quick':
                    score = self.run_quick_test()
                    print(f"🎯 Результат: {score:.1f}%")
                elif command == 'full':
                    score = self.run_full_test()
                    print(f"🎯 Результат: {score:.1f}%")
                elif command == 'stress':
                    score = self.run_stress_test()
                    print(f"🎯 Результат: {score:.1f}%")
                elif command == 'status':
                    status = self.simulator.get_network_status()
                    print(f"📊 Статус сети: {status['node_summary']['running_nodes']}/{status['node_summary']['total_nodes']} узлов активно")
                elif command == 'report':
                    self.report_generator.print_summary()
                elif command == 'export':
                    json_file = self.report_generator.export_json()
                    print(f"💾 Отчет экспортирован: {json_file}")
                else:
                    print("❌ Неизвестная команда")
        
        finally:
            self.simulator.stop_network()
    
    def run_web_interface(self):
        """Запуск веб-интерфейса"""
        print("🌐 Запуск веб-интерфейса тестирования...")
        
        try:
            from http.server import HTTPServer, SimpleHTTPRequestHandler
            import webbrowser
            import threading
            
            class CustomHandler(SimpleHTTPRequestHandler):
                def __init__(self, *args, **kwargs):
                    super().__init__(*args, directory=os.path.dirname(__file__), **kwargs)
                
                def end_headers(self):
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                    self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                    super().end_headers()
            
            # Создаем простой HTML интерфейс
            html_content = self._generate_web_interface()
            
            with open(os.path.join(os.path.dirname(__file__), 'test_interface.html'), 'w') as f:
                f.write(html_content)
            
            # Запуск сервера
            port = TestConfig.WEB_PORT
            server = HTTPServer(('localhost', port), CustomHandler)
            
            print(f"🌐 Веб-интерфейс доступен: http://localhost:{port}/test_interface.html")
            webbrowser.open(f"http://localhost:{port}/test_interface.html")
            
            # Запуск в отдельном потоке
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()
            
            print("Нажмите Ctrl+C для остановки...")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n🛑 Остановка веб-сервера...")
                server.shutdown()
                
        except Exception as e:
            print(f"❌ Ошибка запуска веб-интерфейса: {e}")
    
    def _generate_web_interface(self) -> str:
        """Сгенерировать HTML интерфейс"""
        return """
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mesh Network Test Suite</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            min-height: 100vh;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            background: rgba(255,255,255,0.1);
            padding: 30px;
            border-radius: 15px;
            backdrop-filter: blur(10px);
        }
        h1 {
            text-align: center;
            margin-bottom: 30px;
        }
        .test-button {
            display: block;
            width: 100%;
            padding: 15px;
            margin: 10px 0;
            background: linear-gradient(45deg, #4CAF50, #45a049);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 1.1em;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        .test-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.3);
        }
        .test-button.secondary {
            background: linear-gradient(45deg, #2196F3, #1976D2);
        }
        .test-button.danger {
            background: linear-gradient(45deg, #f44336, #d32f2f);
        }
        .results {
            margin-top: 30px;
            padding: 20px;
            background: rgba(0,0,0,0.2);
            border-radius: 10px;
        }
        .status {
            text-align: center;
            font-size: 1.2em;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🧪 Mesh Network Test Suite</h1>
        
        <div class="status" id="status">
            Готов к тестированию
        </div>
        
        <button class="test-button" onclick="runTest('quick')">
            🚀 Быстрый тест (3 узла)
        </button>
        
        <button class="test-button" onclick="runTest('full')">
            🧪 Полный тест (5 узлов)
        </button>
        
        <button class="test-button secondary" onclick="runTest('stress')">
            ⚡ Нагрузочный тест (10 узлов)
        </button>
        
        <button class="test-button danger" onclick="stopTests()">
            🛑 Остановить тесты
        </button>
        
        <div class="results" id="results">
            <h3>📊 Результаты</h3>
            <div id="results-content">
                Запустите тест для просмотра результатов
            </div>
        </div>
    </div>

    <script>
        async function runTest(type) {
            const status = document.getElementById('status');
            const results = document.getElementById('results-content');
            
            status.textContent = `Запуск ${type} теста...`;
            
            try {
                const response = await fetch(`/run_test?type=${type}`);
                const data = await response.json();
                
                if (data.success) {
                    status.textContent = `✅ Тест завершен: ${data.score.toFixed(1)}%`;
                    results.innerHTML = `
                        <h4>📊 Результаты теста "${type}"</h4>
                        <p><strong>Общая оценка:</strong> ${data.score.toFixed(1)}%</p>
                        <p><strong>Длительность:</strong> ${data.duration.toFixed(1)} сек</p>
                        <p><strong>Статус:</strong> ${data.status}</p>
                        <details>
                            <summary>Детальная информация</summary>
                            <pre>${JSON.stringify(data.details, null, 2)}</pre>
                        </details>
                    `;
                } else {
                    status.textContent = `❌ Ошибка: ${data.error}`;
                    results.innerHTML = `<p style="color: #ff6b6b;">${data.error}</p>`;
                }
            } catch (error) {
                status.textContent = '❌ Ошибка соединения с сервером тестов';
                results.innerHTML = `<p style="color: #ff6b6b;">${error.message}</p>`;
            }
        }
        
        function stopTests() {
            const status = document.getElementById('status');
            status.textContent = '🛑 Тесты остановлены';
        }
        
        // Автообновление статуса
        setInterval(async () => {
            try {
                const response = await fetch('/status');
                const data = await response.json();
                // Обновление статуса
            } catch (error) {
                // Игнорировать ошибки
            }
        }, 5000);
    </script>
</body>
</html>
        """
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.simulator.stop_network()
        TestConfig.cleanup_logs()

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Mesh Network Test Suite')
    parser.add_argument('--quick', action='store_true', help='Запустить быстрый тест')
    parser.add_argument('--full', action='store_true', help='Запустить полный тест')
    parser.add_argument('--stress', action='store_true', help='Запустить нагрузочный тест')
    parser.add_argument('--interactive', action='store_true', help='Интерактивный режим')
    parser.add_argument('--web', action='store_true', help='Веб-интерфейс')
    parser.add_argument('--export', help='Экспорт результатов в файл')
    
    args = parser.parse_args()
    
    # Подготовка
    TestConfig.ensure_logs_dir()
    
    # Создание набора тестов
    test_suite = MeshTestSuite()
    
    try:
        if args.web:
            test_suite.run_web_interface()
        elif args.interactive:
            test_suite.run_interactive_test()
        elif args.stress:
            score = test_suite.run_stress_test()
            test_suite.report_generator.print_summary()
        elif args.full:
            score = test_suite.run_full_test()
            test_suite.report_generator.print_summary()
        elif args.quick:
            score = test_suite.run_quick_test()
            test_suite.report_generator.print_summary()
        else:
            # По умолчанию - быстрый тест
            score = test_suite.run_quick_test()
            test_suite.report_generator.print_summary()
        
        # Экспорт результатов
        if args.export:
            filename = test_suite.report_generator.export_json(args.export)
            print(f"💾 Результаты экспортированы: {filename}")
        elif test_suite.report_generator.test_results:
            filename = test_suite.report_generator.export_json()
            print(f"💾 Результаты сохранены: {filename}")
    
    except KeyboardInterrupt:
        print("\n👋 Тестирование прервано")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        test_suite.cleanup()

if __name__ == "__main__":
    main()
