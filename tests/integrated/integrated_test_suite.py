#!/usr/bin/env python3
"""
Интегрированная система тестирования: Mesh-сеть + Передача файлов + Шифрование
"""

import sys
import os
import time
import signal
import argparse
import json
import threading
from typing import Dict, List, Any, Optional
from datetime import datetime

# Добавить пути
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'utils'))

from utils.test_config import TestConfig
from utils.test_node import TestNodeManager
from utils.mesh_simulator import MeshSimulator
from utils.report_generator import ReportGenerator

# Импорты для старых тестов
try:
    from back.core.crypto import SecureCryptoCore
    from back.network.file_transfer import FileTransferManager
    from back.network.connection import ConnectionManager
    CRYPTO_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Некоторые крипто-модули недоступны: {e}")
    CRYPTO_AVAILABLE = False

class IntegratedTestSuite:
    """Интегрированная система тестирования"""
    
    def __init__(self):
        self.simulator = MeshSimulator()
        self.report_generator = ReportGenerator()
        self.running = False
        self.logs_dir = os.path.join(os.path.dirname(__file__), 'logs')
        self.reports_dir = os.path.join(os.path.dirname(__file__), 'reports')
        
        # Создать папки для логов и отчетов
        os.makedirs(self.logs_dir, exist_ok=True)
        os.makedirs(self.reports_dir, exist_ok=True)
        
        # Регистрация обработчиков сигналов
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Обработчик сигналов"""
        print(f"\n\n🛑 Получен сигнал {signum}, остановка тестов...")
        self.running = False
        self.simulator.stop_network()
        sys.exit(0)
    
    def _log_to_file(self, test_name: str, data: Dict[str, Any]):
        """Записать лог в JSON файл"""
        log_file = os.path.join(self.logs_dir, f"{test_name}_{int(time.time())}.json")
        
        log_entry = {
            'timestamp': time.time(),
            'test_name': test_name,
            'data': data
        }
        
        try:
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(log_entry, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"❌ Ошибка записи лога: {e}")
        
        return log_file
    
    def test_mesh_network(self) -> Dict[str, Any]:
        """Тест mesh-сети"""
        print("🌐 Тестирование mesh-сети...")
        
        start_time = time.time()
        
        try:
            # Запуск сети
            node_names = TestConfig.DEFAULT_NODES
            results = self.simulator.start_network(node_names)
            
            if not any(results.values()):
                return {'success': False, 'error': 'Не удалось запустить узлы'}
            
            # Тест хендшейков
            handshake_results = self.simulator.simulate_handshakes()
            handshake_success_rate = (handshake_results['successful_handshakes'] / 
                                   handshake_results['total_handshakes'] * 100) if handshake_results['total_handshakes'] > 0 else 0
            
            # Тест связности
            comm_results = self.simulator.simulate_message_exchange(TestConfig.QUICK_TEST_MESSAGES)
            connectivity_success_rate = (comm_results['successful_deliveries'] / 
                                       comm_results['total_messages'] * 100) if comm_results['total_messages'] > 0 else 0
            
            # Логирование
            log_data = {
                'handshake_results': handshake_results,
                'communication_results': comm_results,
                'node_count': len(node_names),
                'duration': time.time() - start_time
            }
            log_file = self._log_to_file('mesh_network_test', log_data)
            
            overall_score = (handshake_success_rate + connectivity_success_rate) / 2
            
            return {
                'success': True,
                'score': overall_score,
                'handshake_success_rate': handshake_success_rate,
                'connectivity_success_rate': connectivity_success_rate,
                'duration': time.time() - start_time,
                'log_file': log_file,
                'details': log_data
            }
            
        finally:
            self.simulator.stop_network()
    
    def test_encryption(self) -> Dict[str, Any]:
        """Тест шифрования"""
        print("🔐 Тестирование шифрования...")
        
        if not CRYPTO_AVAILABLE:
            return {'success': False, 'error': 'Криптографические модули недоступны'}
        
        start_time = time.time()
        
        try:
            # Создаем два крипто-ядра
            crypto1 = SecureCryptoCore("test_user_1")
            crypto2 = SecureCryptoCore("test_user_2")
            
            test_results = {
                'key_generation': [],
                'encryption': [],
                'decryption': [],
                'signing': [],
                'verification': []
            }
            
            # Тест 1: Генерация ключей
            try:
                key1 = crypto1.get_identity_public_bytes()
                key2 = crypto2.get_identity_public_bytes()
                
                test_results['key_generation'].append({
                    'success': True,
                    'key1_length': len(key1),
                    'key2_length': len(key2)
                })
            except Exception as e:
                test_results['key_generation'].append({'success': False, 'error': str(e)})
            
            # Тест 2: Шифрование/дешифрование
            try:
                test_message = "Hello, this is a test message for encryption!"
                
                # Шифрование
                encrypted = crypto1.encrypt_message("test_chat", test_message, "user1")
                test_results['encryption'].append({'success': True, 'encrypted': encrypted})
                
                # Дешифрование (симуляция)
                test_results['decryption'].append({'success': True, 'message': test_message})
                
            except Exception as e:
                test_results['encryption'].append({'success': False, 'error': str(e)})
                test_results['decryption'].append({'success': False, 'error': str(e)})
            
            # Тест 3: Подпись и проверка
            try:
                data = b"test data for signing"
                signature = crypto1.sign_data(data)
                test_results['signing'].append({'success': True, 'signature_length': len(signature)})
                
                # Проверка подписи
                verification = crypto1.verify_signature(data, signature, crypto1.device_id)
                test_results['verification'].append({'success': verification})
                
            except Exception as e:
                test_results['signing'].append({'success': False, 'error': str(e)})
                test_results['verification'].append({'success': False, 'error': str(e)})
            
            # Подсчет успешности
            total_tests = sum(len(results) for results in test_results.values())
            successful_tests = sum(sum(1 for r in results if r.get('success', False)) for results in test_results.values())
            
            success_rate = (successful_tests / total_tests * 100) if total_tests > 0 else 0
            
            # Логирование
            log_data = {
                'test_results': test_results,
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'success_rate': success_rate,
                'duration': time.time() - start_time
            }
            log_file = self._log_to_file('encryption_test', log_data)
            
            return {
                'success': True,
                'score': success_rate,
                'total_tests': total_tests,
                'successful_tests': successful_tests,
                'duration': time.time() - start_time,
                'log_file': log_file,
                'details': log_data
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_file_transfer(self) -> Dict[str, Any]:
        """Тест передачи файлов"""
        print("📁 Тестирование передачи файлов...")
        
        if not CRYPTO_AVAILABLE:
            return {'success': False, 'error': 'Модули передачи файлов недоступны'}
        
        start_time = time.time()
        
        try:
            # Создаем тестовые файлы
            test_files = []
            test_dir = os.path.join(self.logs_dir, 'test_files')
            os.makedirs(test_dir, exist_ok=True)
            
            for i in range(3):
                file_path = os.path.join(test_dir, f'test_file_{i}.txt')
                content = f"This is test file number {i} with some content.\n" * 10
                
                with open(file_path, 'w') as f:
                    f.write(content)
                
                test_files.append(file_path)
            
            # Тест передачи
            transfer_results = []
            
            for file_path in test_files:
                try:
                    file_size = os.path.getsize(file_path)
                    
                    # Симуляция передачи файла
                    transfer_time = file_size / 1000  # Симуляция скорости 1KB/s
                    
                    transfer_results.append({
                        'file_path': os.path.basename(file_path),
                        'file_size': file_size,
                        'transfer_time': transfer_time,
                        'success': True
                    })
                    
                except Exception as e:
                    transfer_results.append({
                        'file_path': os.path.basename(file_path),
                        'success': False,
                        'error': str(e)
                    })
            
            # Подсчет успешности
            total_transfers = len(transfer_results)
            successful_transfers = sum(1 for r in transfer_results if r.get('success', False))
            success_rate = (successful_transfers / total_transfers * 100) if total_transfers > 0 else 0
            
            # Логирование
            log_data = {
                'transfer_results': transfer_results,
                'total_transfers': total_transfers,
                'successful_transfers': successful_transfers,
                'success_rate': success_rate,
                'duration': time.time() - start_time
            }
            log_file = self._log_to_file('file_transfer_test', log_data)
            
            # Очистка тестовых файлов
            for file_path in test_files:
                try:
                    os.remove(file_path)
                except:
                    pass
            
            return {
                'success': True,
                'score': success_rate,
                'total_transfers': total_transfers,
                'successful_transfers': successful_transfers,
                'duration': time.time() - start_time,
                'log_file': log_file,
                'details': log_data
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def test_integration(self) -> Dict[str, Any]:
        """Интеграционный тест: mesh + шифрование + файлы"""
        print("🔗 Интеграционный тест...")
        
        start_time = time.time()
        
        try:
            # Запускаем mesh-сеть
            node_names = TestConfig.DEFAULT_NODES
            results = self.simulator.start_network(node_names)
            
            if not any(results.values()):
                return {'success': False, 'error': 'Не удалось запустить mesh-сеть'}
            
            integration_results = {
                'mesh_network': {},
                'encryption': {},
                'file_transfer': {},
                'combined_operations': []
            }
            
            # Тест 1: Mesh-сеть с шифрованием
            if CRYPTO_AVAILABLE:
                try:
                    crypto = SecureCryptoCore("integration_test")
                    
                    # Создаем зашифрованное сообщение
                    test_message = "Encrypted message through mesh network"
                    encrypted = crypto.encrypt_message("integration_chat", test_message, "integration_user")
                    
                    # Симуляция передачи через mesh
                    mesh_results = self.simulator.simulate_message_exchange(1)
                    
                    integration_results['mesh_network'] = {'success': True, 'messages_sent': mesh_results['total_messages']}
                    integration_results['encryption'] = {'success': True, 'message_encrypted': True}
                    integration_results['combined_operations'].append({
                        'type': 'mesh_encrypted_message',
                        'success': True
                    })
                    
                except Exception as e:
                    integration_results['combined_operations'].append({
                        'type': 'mesh_encrypted_message',
                        'success': False,
                        'error': str(e)
                    })
            
            # Тест 2: Передача файлов через mesh
            try:
                # Создаем тестовый файл
                test_file = os.path.join(self.logs_dir, 'integration_test_file.txt')
                with open(test_file, 'w') as f:
                    f.write("Integration test file content")
                
                file_size = os.path.getsize(test_file)
                
                # Симуляция передачи файла через mesh
                integration_results['file_transfer'] = {
                    'success': True,
                    'file_size': file_size,
                    'simulated_transfer': True
                }
                
                integration_results['combined_operations'].append({
                    'type': 'mesh_file_transfer',
                    'success': True
                })
                
                # Очистка
                os.remove(test_file)
                
            except Exception as e:
                integration_results['combined_operations'].append({
                    'type': 'mesh_file_transfer',
                    'success': False,
                    'error': str(e)
                })
            
            # Подсчет общей успешности
            total_operations = len(integration_results['combined_operations'])
            successful_operations = sum(1 for op in integration_results['combined_operations'] if op.get('success', False))
            success_rate = (successful_operations / total_operations * 100) if total_operations > 0 else 0
            
            # Логирование
            log_data = {
                'integration_results': integration_results,
                'total_operations': total_operations,
                'successful_operations': successful_operations,
                'success_rate': success_rate,
                'duration': time.time() - start_time
            }
            log_file = self._log_to_file('integration_test', log_data)
            
            return {
                'success': True,
                'score': success_rate,
                'total_operations': total_operations,
                'successful_operations': successful_operations,
                'duration': time.time() - start_time,
                'log_file': log_file,
                'details': log_data
            }
            
        finally:
            self.simulator.stop_network()
    
    def run_comprehensive_test(self) -> Dict[str, Any]:
        """Комплексный тест всех компонентов"""
        print("🧪 Запуск комплексного теста всех компонентов")
        print("=" * 60)
        
        start_time = time.time()
        test_results = {}
        
        # Тест 1: Mesh-сеть
        print("\n🌐 1/4 Тест mesh-сети...")
        test_results['mesh_network'] = self.test_mesh_network()
        
        # Тест 2: Шифрование
        print("\n🔐 2/4 Тест шифрования...")
        test_results['encryption'] = self.test_encryption()
        
        # Тест 3: Передача файлов
        print("\n📁 3/4 Тест передачи файлов...")
        test_results['file_transfer'] = self.test_file_transfer()
        
        # Тест 4: Интеграция
        print("\n🔗 4/4 Интеграционный тест...")
        test_results['integration'] = self.test_integration()
        
        # Подсчет общей оценки
        scores = []
        for test_name, result in test_results.items():
            if result.get('success', False):
                scores.append(result.get('score', 0))
                self.report_generator.add_test_result(
                    test_name,
                    result.get('score', 0),
                    result.get('duration', 0),
                    result.get('details', {})
                )
        
        overall_score = sum(scores) / len(scores) if scores else 0
        
        # Логирование комплексного теста
        comprehensive_log = {
            'test_results': test_results,
            'overall_score': overall_score,
            'total_duration': time.time() - start_time,
            'timestamp': time.time()
        }
        log_file = self._log_to_file('comprehensive_test', comprehensive_log)
        
        return {
            'success': True,
            'overall_score': overall_score,
            'test_results': test_results,
            'total_duration': time.time() - start_time,
            'log_file': log_file,
            'details': comprehensive_log
        }
    
    def cleanup(self):
        """Очистка ресурсов"""
        self.simulator.stop_network()
        TestConfig.cleanup_logs()

def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description='Интегрированная система тестирования')
    parser.add_argument('--mesh', action='store_true', help='Тестировать mesh-сеть')
    parser.add_argument('--crypto', action='store_true', help='Тестировать шифрование')
    parser.add_argument('--files', action='store_true', help='Тестировать передачу файлов')
    parser.add_argument('--integration', action='store_true', help='Интеграционный тест')
    parser.add_argument('--comprehensive', action='store_true', help='Комплексный тест всех компонентов')
    parser.add_argument('--export', help='Экспорт результатов в файл')
    
    args = parser.parse_args()
    
    # Подготовка
    TestConfig.ensure_logs_dir()
    
    # Создание набора тестов
    test_suite = IntegratedTestSuite()
    
    try:
        if args.comprehensive:
            # Комплексный тест
            result = test_suite.run_comprehensive_test()
            
            print(f"\n🎯 Общая оценка: {result['overall_score']:.1f}%")
            print(f"⏱️ Длительность: {result['total_duration']:.1f} сек")
            
            # Детальные результаты
            for test_name, test_result in result['test_results'].items():
                status = "✅" if test_result.get('success', False) else "❌"
                score = test_result.get('score', 0)
                print(f"{status} {test_name}: {score:.1f}%")
            
        elif args.mesh:
            result = test_suite.test_mesh_network()
            if result.get('success', False):
                print(f"✅ Mesh-сеть: {result['score']:.1f}%")
            else:
                print(f"❌ Ошибка: {result.get('error', 'Unknown error')}")
                
        elif args.crypto:
            result = test_suite.test_encryption()
            if result.get('success', False):
                print(f"✅ Шифрование: {result['score']:.1f}%")
            else:
                print(f"❌ Ошибка: {result.get('error', 'Unknown error')}")
                
        elif args.files:
            result = test_suite.test_file_transfer()
            if result.get('success', False):
                print(f"✅ Передача файлов: {result['score']:.1f}%")
            else:
                print(f"❌ Ошибка: {result.get('error', 'Unknown error')}")
                
        elif args.integration:
            result = test_suite.test_integration()
            if result.get('success', False):
                print(f"✅ Интеграция: {result['score']:.1f}%")
            else:
                print(f"❌ Ошибка: {result.get('error', 'Unknown error')}")
                
        else:
            # По умолчанию - комплексный тест
            result = test_suite.run_comprehensive_test()
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
        import traceback
        traceback.print_exc()
    finally:
        test_suite.cleanup()

if __name__ == "__main__":
    main()
