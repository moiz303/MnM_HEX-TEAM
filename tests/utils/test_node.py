"""
Утилита тестового узла mesh-сети
"""

import sys
import os
import time
import threading
import json
from typing import Dict, List, Optional, Any

# Добавить путь к бэкенду
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'back'))

class TestNode:
    """Изолированный тестовый узел mesh-сети"""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.messenger = None
        self.running = False
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'handshakes_completed': 0,
            'errors': 0,
            'start_time': None,
            'last_activity': None
        }
        self.message_log = []
        
    def start(self) -> bool:
        """Запустить узел"""
        try:
            print(f"🚀 Запуск узла {self.name}...")
            
            # Изменяем порты для изоляции
            self._patch_ports()
            
            # Импортируем после изменения портов
            from main import SecureMessenger
            
            self.messenger = SecureMessenger(self.name)
            self.running = True
            self.stats['start_time'] = time.time()
            
            print(f"✅ Узел {self.name} запущен (ID: {self.messenger.device_id})")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка запуска узла {self.name}: {e}")
            self.stats['errors'] += 1
            return False
    
    def stop(self):
        """Остановить узел"""
        self.running = False
        if self.messenger:
            self.messenger.cleanup()
        print(f"🛑 Узел {self.name} остановлен")
    
    def _patch_ports(self):
        """Изменить порты для изоляции"""
        import back.network.protocols as protocols
        
        original_ports = {
            'BROADCAST_PORT': protocols.BROADCAST_PORT,
            'MESSAGE_PORT': protocols.MESSAGE_PORT,
            'DHT_PORT': protocols.DHT_PORT,
            'FILE_TRANSFER_PORT': protocols.FILE_TRANSFER_PORT,
            'CALL_SIGNALING_PORT': protocols.CALL_SIGNALING_PORT,
        }
        
        # Применяем новые порты
        protocols.BROADCAST_PORT = self.config['ports']['broadcast']
        protocols.MESSAGE_PORT = self.config['ports']['message']
        protocols.DHT_PORT = self.config['ports']['dht']
        protocols.FILE_TRANSFER_PORT = self.config['ports']['file_transfer']
        protocols.CALL_SIGNALING_PORT = self.config['ports']['call_signaling']
        
        # Сохраняем для восстановления
        self._original_ports = original_ports
    
    def _restore_ports(self):
        """Восстановить оригинальные порты"""
        if hasattr(self, '_original_ports'):
            import back.network.protocols as protocols
            for key, value in self._original_ports.items():
                setattr(protocols, key, value)
    
    def send_message_to(self, target_name: str, message: str) -> bool:
        """Отправить сообщение другому узлу"""
        if not self.messenger or not self.running:
            return False
        
        try:
            # Создаем тестовое сообщение
            test_message = {
                'type': 'SECURE_MESSAGE',
                'chat_id': f'test_{self.name}_{target_name}',
                'encrypted': {'content': message},
                'msg_id': f"test_{int(time.time())}_{self.name}",
                'timestamp': time.time(),
                'from': self.name
            }
            
            # Симуляция доставки через mesh
            success = self._simulate_delivery(target_name, message)
            
            if success:
                self.stats['messages_sent'] += 1
                self.stats['last_activity'] = time.time()
                self.message_log.append({
                    'type': 'sent',
                    'to': target_name,
                    'message': message,
                    'timestamp': time.time(),
                    'success': True
                })
                print(f"📤 {self.name} → {target_name}: {message}")
            else:
                self.stats['errors'] += 1
                self.message_log.append({
                    'type': 'sent',
                    'to': target_name,
                    'message': message,
                    'timestamp': time.time(),
                    'success': False
                })
                print(f"❌ {self.name} ✗ {target_name}: {message}")
            
            return success
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"❌ Ошибка отправки от {self.name}: {e}")
            return False
    
    def _simulate_delivery(self, target_name: str, message: str) -> bool:
        """Симуляция доставки сообщения через mesh"""
        import random
        from test_config import TestConfig
        
        # Симулируем успешность доставки
        success = random.random() < TestConfig.MESSAGE_SUCCESS_RATE
        
        # Логируем попытку доставки
        self.message_log.append({
            'type': 'delivery_attempt',
            'to': target_name,
            'message': message,
            'timestamp': time.time(),
            'simulated_success': success
        })
        
        return success
    
    def receive_message(self, from_name: str, message: str) -> bool:
        """Симулировать получение сообщения"""
        try:
            self.stats['messages_received'] += 1
            self.stats['last_activity'] = time.time()
            
            self.message_log.append({
                'type': 'received',
                'from': from_name,
                'message': message,
                'timestamp': time.time()
            })
            
            print(f"📥 {self.name} ← {from_name}: {message}")
            return True
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"❌ Ошибка получения в {self.name}: {e}")
            return False
    
    def simulate_handshake(self, peer_name: str) -> bool:
        """Симулировать установку хендшейка"""
        import random
        from test_config import TestConfig
        
        success = random.random() < TestConfig.HANDSHAKE_SUCCESS_RATE
        
        if success:
            self.stats['handshakes_completed'] += 1
            self.message_log.append({
                'type': 'handshake',
                'peer': peer_name,
                'timestamp': time.time(),
                'success': True
            })
            print(f"🤝 {self.name} ↔ {peer_name}: хендшейк установлен")
        else:
            self.stats['errors'] += 1
            self.message_log.append({
                'type': 'handshake',
                'peer': peer_name,
                'timestamp': time.time(),
                'success': False
            })
            print(f"❌ {self.name} ✗ {peer_name}: хендшейк не удался")
        
        return success
    
    def get_status(self) -> Dict[str, Any]:
        """Получить статус узла"""
        if not self.messenger:
            return {
                'status': 'stopped',
                'name': self.name,
                'stats': self.stats.copy(),
                'message_log': self.message_log.copy()
            }
        
        try:
            mesh_stats = self.messenger.get_mesh_stats()
            return {
                'status': 'running' if self.running else 'stopped',
                'name': self.name,
                'device_id': self.messenger.device_id,
                'mesh_stats': mesh_stats,
                'custom_stats': self.stats.copy(),
                'message_log': self.message_log.copy(),
                'uptime': time.time() - self.stats['start_time'] if self.stats['start_time'] else 0
            }
        except Exception as e:
            return {
                'status': 'error',
                'name': self.name,
                'error': str(e),
                'stats': self.stats.copy(),
                'message_log': self.message_log.copy()
            }
    
    def reset_stats(self):
        """Сбросить статистику"""
        self.stats = {
            'messages_sent': 0,
            'messages_received': 0,
            'handshakes_completed': 0,
            'errors': 0,
            'start_time': time.time(),
            'last_activity': None
        }
        self.message_log = []
        print(f"📊 Статистика {self.name} сброшена")


class TestNodeManager:
    """Менеджер тестовых узлов"""
    
    def __init__(self):
        self.nodes: Dict[str, TestNode] = {}
        from test_config import TestConfig
        TestConfig.ensure_logs_dir()
    
    def add_node(self, name: str, port_offset: int = 0) -> TestNode:
        """Добавить узел"""
        from test_config import TestConfig
        
        config = TestConfig.get_node_config(name, port_offset)
        node = TestNode(name, config)
        self.nodes[name] = node
        
        print(f"➕ Узел {name} добавлен")
        return node
    
    def remove_node(self, name: str):
        """Удалить узел"""
        if name in self.nodes:
            self.nodes[name].stop()
            del self.nodes[name]
            print(f"➖ Узел {name} удален")
    
    def start_node(self, name: str) -> bool:
        """Запустить узел"""
        if name in self.nodes:
            return self.nodes[name].start()
        return False
    
    def stop_node(self, name: str):
        """Остановить узел"""
        if name in self.nodes:
            self.nodes[name].stop()
    
    def start_all(self) -> Dict[str, bool]:
        """Запустить все узлы"""
        results = {}
        for name in self.nodes:
            results[name] = self.start_node(name)
            time.sleep(0.5)  # Пауза между запусками
        return results
    
    def stop_all(self):
        """Остановить все узлы"""
        for name in self.nodes:
            self.stop_node(name)
    
    def get_node(self, name: str) -> Optional[TestNode]:
        """Получить узел по имени"""
        return self.nodes.get(name)
    
    def get_all_nodes(self) -> List[TestNode]:
        """Получить все узлы"""
        return list(self.nodes.values())
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Получить сводный статус всех узлов"""
        summary = {
            'total_nodes': len(self.nodes),
            'running_nodes': 0,
            'stopped_nodes': 0,
            'error_nodes': 0,
            'nodes': {}
        }
        
        for name, node in self.nodes.items():
            status = node.get_status()
            summary['nodes'][name] = status
            
            if status['status'] == 'running':
                summary['running_nodes'] += 1
            elif status['status'] == 'stopped':
                summary['stopped_nodes'] += 1
            elif status['status'] == 'error':
                summary['error_nodes'] += 1
        
        return summary
    
    def simulate_mesh_communication(self, messages_per_node: int = 2) -> Dict[str, Any]:
        """Симулировать mesh-коммуникацию между узлами"""
        results = {
            'total_messages': 0,
            'successful_deliveries': 0,
            'failed_deliveries': 0,
            'handshakes': 0,
            'successful_handshakes': 0,
            'communication_log': []
        }
        
        node_names = list(self.nodes.keys())
        
        # Установление хендшейков
        print("🤝 Установление хендшейков...")
        for i, sender_name in enumerate(node_names):
            for receiver_name in node_names[i+1:]:
                results['handshakes'] += 1
                if self.nodes[sender_name].simulate_handshake(receiver_name):
                    results['successful_handshakes'] += 1
                time.sleep(0.1)
        
        # Обмен сообщениями
        print("📤 Обмен сообщениями...")
        for sender_name in node_names:
            for receiver_name in node_names:
                if sender_name != receiver_name:
                    for msg_num in range(messages_per_node):
                        message = f"Message {msg_num + 1} from {sender_name}"
                        results['total_messages'] += 1
                        
                        if self.nodes[sender_name].send_message_to(receiver_name, message):
                            results['successful_deliveries'] += 1
                            # Симулируем получение
                            self.nodes[receiver_name].receive_message(sender_name, message)
                        else:
                            results['failed_deliveries'] += 1
                        
                        time.sleep(0.1)
        
        return results
