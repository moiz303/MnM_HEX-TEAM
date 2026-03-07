"""
Симулятор mesh-сети для тестирования
"""

import time
import random
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

from test_node import TestNode, TestNodeManager
from test_config import TestConfig

class NodeStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    CONNECTING = "connecting"
    ERROR = "error"

@dataclass
class NetworkEvent:
    """Событие в сети"""
    event_type: str
    source: str
    target: Optional[str]
    data: Dict[str, Any]
    timestamp: float

class MeshSimulator:
    """Симулятор mesh-сети"""
    
    def __init__(self):
        self.node_manager = TestNodeManager()
        self.events: List[NetworkEvent] = []
        self.running = False
        self.simulation_thread = None
        self.network_conditions = {
            'packet_loss': 0.1,      # 10% потеря пакетов
            'latency': 0.1,          # 100ms задержка
            'bandwidth': 1000,       # kbps
            'reliability': 0.95      # 95% надежность
        }
    
    def add_node(self, name: str, port_offset: int = 0) -> TestNode:
        """Добавить узел в сеть"""
        node = self.node_manager.add_node(name, port_offset)
        self._log_event("node_added", name, None, {"port_offset": port_offset})
        return node
    
    def remove_node(self, name: str):
        """Удалить узел из сети"""
        self.node_manager.remove_node(name)
        self._log_event("node_removed", name, None, {})
    
    def start_network(self, node_names: List[str]) -> Dict[str, bool]:
        """Запустить сеть с указанными узлами"""
        print(f"🌐 Запуск mesh-сети с {len(node_names)} узлами...")
        
        # Добавляем узлы
        for i, name in enumerate(node_names):
            self.add_node(name, port_offset=i * 10)
        
        # Запускаем узлы
        results = self.node_manager.start_all()
        
        # Симулируем обнаружение
        self._simulate_discovery()
        
        self.running = True
        
        return results
    
    def stop_network(self):
        """Остановить сеть"""
        print("🛑 Остановка mesh-сети...")
        self.running = False
        self.node_manager.stop_all()
    
    def _simulate_discovery(self):
        """Симулировать обнаружение узлов"""
        print("🔍 Симуляция обнаружения узлов...")
        
        nodes = self.node_manager.get_all_nodes()
        for node in nodes:
            # Каждый узел "обнаруживает" других
            for other_node in nodes:
                if node != other_node:
                    # Симулируем успешное обнаружение
                    if random.random() < self.network_conditions['reliability']:
                        self._log_event("peer_discovered", node.name, other_node.name, {})
                        time.sleep(0.1)
    
    def simulate_handshakes(self) -> Dict[str, Any]:
        """Симулировать установку хендшейков"""
        print("🤝 Симуляция хендшейков...")
        
        nodes = self.node_manager.get_all_nodes()
        results = {
            'total_handshakes': 0,
            'successful_handshakes': 0,
            'failed_handshakes': 0,
            'handshake_details': []
        }
        
        # Каждый узел устанавливает хендшейк с каждым другим
        for i, node in enumerate(nodes):
            for other_node in nodes[i+1:]:
                results['total_handshakes'] += 1
                
                # Симулируем задержку и надежность
                if self._simulate_network_conditions():
                    success = node.simulate_handshake(other_node.name)
                    if success:
                        results['successful_handshakes'] += 1
                        results['handshake_details'].append({
                            'from': node.name,
                            'to': other_node.name,
                            'success': True,
                            'timestamp': time.time()
                        })
                    else:
                        results['failed_handshakes'] += 1
                        results['handshake_details'].append({
                            'from': node.name,
                            'to': other_node.name,
                            'success': False,
                            'timestamp': time.time()
                        })
                else:
                    results['failed_handshakes'] += 1
                
                time.sleep(0.1)
        
        return results
    
    def simulate_message_exchange(self, messages_per_pair: int = 2) -> Dict[str, Any]:
        """Симулировать обмен сообщениями"""
        print(f"📤 Симуляция обмена сообщениями ({messages_per_pair} на пару)...")
        
        nodes = self.node_manager.get_all_nodes()
        results = {
            'total_messages': 0,
            'successful_deliveries': 0,
            'failed_deliveries': 0,
            'average_delivery_time': 0,
            'message_details': []
        }
        
        delivery_times = []
        
        # Обмен сообщениями между всеми парами
        for i, sender in enumerate(nodes):
            for receiver in nodes:
                if sender != receiver:
                    for msg_num in range(messages_per_pair):
                        results['total_messages'] += 1
                        start_time = time.time()
                        
                        message = f"Test message {msg_num + 1} from {sender.name}"
                        
                        # Симулируем сетевые условия
                        if self._simulate_network_conditions():
                            success = sender.send_message_to(receiver.name, message)
                            
                            if success:
                                # Симулируем получение
                                receiver.receive_message(sender.name, message)
                                results['successful_deliveries'] += 1
                                
                                delivery_time = time.time() - start_time
                                delivery_times.append(delivery_time)
                                
                                results['message_details'].append({
                                    'from': sender.name,
                                    'to': receiver.name,
                                    'message': message,
                                    'success': True,
                                    'delivery_time': delivery_time,
                                    'timestamp': time.time()
                                })
                            else:
                                results['failed_deliveries'] += 1
                                results['message_details'].append({
                                    'from': sender.name,
                                    'to': receiver.name,
                                    'message': message,
                                    'success': False,
                                    'delivery_time': None,
                                    'timestamp': time.time()
                                })
                        else:
                            results['failed_deliveries'] += 1
                        
                        time.sleep(0.05)
        
        # Рассчитываем среднее время доставки
        if delivery_times:
            results['average_delivery_time'] = sum(delivery_times) / len(delivery_times)
        
        return results
    
    def simulate_offline_delivery(self) -> Dict[str, Any]:
        """Симулировать офлайн-доставку сообщений"""
        print("📦 Симуляция офлайн-доставки...")
        
        nodes = self.node_manager.get_all_nodes()
        if len(nodes) < 3:
            print("⚠️ Нужно минимум 3 узла для теста офлайн-доставки")
            return {'success': False, 'reason': 'insufficient_nodes'}
        
        sender = nodes[0]
        receiver = nodes[1]
        relay = nodes[2]
        
        results = {
            'messages_queued': 0,
            'messages_delivered': 0,
            'queue_time': 0,
            'success': False
        }
        
        # 1. Останавливаем получателя
        print(f"🛑 Останавливаем {receiver.name}...")
        receiver.stop()
        time.sleep(1)
        
        # 2. Отправляем сообщения офлайн-получателю
        messages = ["Offline message 1", "Offline message 2"]
        for message in messages:
            print(f"📤 {sender.name} → {receiver.name} (офлайн): {message}")
            
            # Симулируем сохранение в очереди ретранслятора
            if random.random() < TestConfig.OFFLINE_DELIVERY_RATE:
                results['messages_queued'] += 1
                self._log_event("message_queued", sender.name, receiver.name, {'message': message})
            else:
                self._log_event("message_lost", sender.name, receiver.name, {'message': message})
        
        queue_start_time = time.time()
        
        # 3. Перезапускаем получателя
        print(f"🚀 Перезапускаем {receiver.name}...")
        receiver.start()
        time.sleep(2)
        
        # 4. Симулируем доставку накопленных сообщений
        for message in messages:
            if random.random() < TestConfig.OFFLINE_DELIVERY_RATE:
                receiver.receive_message(sender.name, message)
                results['messages_delivered'] += 1
                self._log_event("offline_delivered", sender.name, receiver.name, {'message': message})
        
        results['queue_time'] = time.time() - queue_start_time
        results['success'] = results['messages_delivered'] > 0
        
        print(f"📊 Результаты офлайн-доставки: {results['messages_delivered']}/{results['messages_queued']} доставлено")
        
        return results
    
    def simulate_network_stress(self, duration: int = 60, message_rate: int = 10) -> Dict[str, Any]:
        """Симулировать нагрузочное тестирование"""
        print(f"⚡ Нагрузочное тестирование: {duration} сек, {message_rate} сообщений/сек")
        
        nodes = self.node_manager.get_all_nodes()
        results = {
            'duration': duration,
            'target_message_rate': message_rate,
            'actual_messages_sent': 0,
            'actual_messages_delivered': 0,
            'network_errors': 0,
            'average_latency': 0,
            'throughput': 0
        }
        
        start_time = time.time()
        latencies = []
        
        def stress_worker():
            """Рабочий поток для нагрузочного тестирования"""
            while time.time() - start_time < duration:
                for sender in nodes:
                    for receiver in nodes:
                        if sender != receiver and self.running:
                            message_start = time.time()
                            
                            message = f"Stress test message from {sender.name}"
                            success = sender.send_message_to(receiver.name, message)
                            
                            if success:
                                receiver.receive_message(sender.name, message)
                                results['actual_messages_delivered'] += 1
                                latencies.append(time.time() - message_start)
                            else:
                                results['network_errors'] += 1
                            
                            results['actual_messages_sent'] += 1
                
                time.sleep(1.0 / message_rate)
        
        # Запуск рабочего потока
        stress_thread = threading.Thread(target=stress_worker)
        stress_thread.start()
        
        # Ожидание завершения
        stress_thread.join()
        
        # Расчет метрик
        actual_duration = time.time() - start_time
        results['actual_duration'] = actual_duration
        
        if latencies:
            results['average_latency'] = sum(latencies) / len(latencies)
        
        if actual_duration > 0:
            results['throughput'] = results['actual_messages_delivered'] / actual_duration
        
        return results
    
    def _simulate_network_conditions(self) -> bool:
        """Симулировать сетевые условия"""
        # Учитываем потерю пакетов
        if random.random() < self.network_conditions['packet_loss']:
            return False
        
        # Учитываем надежность
        if random.random() > self.network_conditions['reliability']:
            return False
        
        # Симулируем задержку
        time.sleep(self.network_conditions['latency'])
        
        return True
    
    def _log_event(self, event_type: str, source: str, target: Optional[str], data: Dict[str, Any]):
        """Записать событие в лог"""
        event = NetworkEvent(
            event_type=event_type,
            source=source,
            target=target,
            data=data,
            timestamp=time.time()
        )
        self.events.append(event)
        
        # Ограничиваем количество событий
        if len(self.events) > 1000:
            self.events = self.events[-1000:]
    
    def get_network_status(self) -> Dict[str, Any]:
        """Получить статус сети"""
        summary = self.node_manager.get_status_summary()
        
        return {
            'network_running': self.running,
            'node_summary': summary,
            'network_conditions': self.network_conditions.copy(),
            'total_events': len(self.events),
            'recent_events': self.events[-10:] if self.events else []
        }
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Получить метрики производительности"""
        nodes = self.node_manager.get_all_nodes()
        
        total_messages = sum(node.stats['messages_sent'] for node in nodes)
        total_received = sum(node.stats['messages_received'] for node in nodes)
        total_errors = sum(node.stats['errors'] for node in nodes)
        
        return {
            'total_nodes': len(nodes),
            'total_messages_sent': total_messages,
            'total_messages_received': total_received,
            'total_errors': total_errors,
            'success_rate': (total_received / total_messages * 100) if total_messages > 0 else 0,
            'error_rate': (total_errors / total_messages * 100) if total_messages > 0 else 0
        }
    
    def export_events(self) -> List[Dict[str, Any]]:
        """Экспортировать события для анализа"""
        return [
            {
                'type': event.event_type,
                'source': event.source,
                'target': event.target,
                'data': event.data,
                'timestamp': event.timestamp
            }
            for event in self.events
        ]
