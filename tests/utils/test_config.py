"""
Конфигурация тестов mesh-сети
"""

import os
import socket
from typing import List, Dict, Any

class TestConfig:
    """Конфигурация для тестирования mesh-сети"""
    
    # Базовые настройки
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    BACKEND_DIR = os.path.join(BASE_DIR, 'back')
    LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
    
    # Настройки узлов
    DEFAULT_NODES = ['Alice', 'Bob', 'Charlie']
    FULL_TEST_NODES = ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve']
    STRESS_TEST_NODES = [f'Node{i}' for i in range(1, 11)]
    
    # Порты (смещение для изоляции от основного сервера)
    BASE_BROADCAST_PORT = 39020  # Изменено с 38020
    BASE_MESSAGE_PORT = 39021    # Изменено с 38021
    BASE_DHT_PORT = 39022        # Изменено с 38022
    BASE_FILE_TRANSFER_PORT = 39023  # Изменено с 38023
    BASE_CALL_SIGNALING_PORT = 39024  # Изменено с 38024
    WEB_PORT = 8081
    
    # Таймауты
    NODE_STARTUP_TIMEOUT = 10  # секунд
    HANDSHAKE_TIMEOUT = 30     # секунд
    MESSAGE_TIMEOUT = 5        # секунд
    TEST_TIMEOUT = 300         # секунд (5 минут)
    
    # Параметры тестов
    QUICK_TEST_MESSAGES = 2    # сообщений на узел
    FULL_TEST_MESSAGES = 5     # сообщений на узел
    STRESS_TEST_MESSAGES = 20  # сообщений на узел
    
    # Пороги качества
    QUALITY_THRESHOLDS = {
        'excellent': 85.0,  # %
        'good': 70.0,       # %
        'acceptable': 50.0, # %
        'poor': 0.0         # %
    }
    
    # Симуляция
    MESSAGE_SUCCESS_RATE = 0.9    # 90% успешность доставки
    HANDSHAKE_SUCCESS_RATE = 0.95  # 95% успешность хендшейков
    OFFLINE_DELIVERY_RATE = 0.85  # 85% успешность офлайн-доставки
    
    @classmethod
    def get_free_ports(cls, count: int = 5, start_port: int = None) -> List[int]:
        """Получить свободные порты"""
        if start_port is None:
            start_port = cls.BASE_MESSAGE_PORT + 100
        
        free_ports = []
        for i in range(count):
            port = start_port + i
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    free_ports.append(port)
            except OSError:
                continue
        
        return free_ports[:count]
    
    @classmethod
    def get_node_config(cls, node_name: str, port_offset: int = 0) -> Dict[str, Any]:
        """Получить конфигурацию для узла"""
        return {
            'name': node_name,
            'ports': {
                'broadcast': cls.BASE_BROADCAST_PORT + port_offset,
                'message': cls.BASE_MESSAGE_PORT + port_offset,
                'dht': cls.BASE_DHT_PORT + port_offset,
                'file_transfer': cls.BASE_FILE_TRANSFER_PORT + port_offset,
                'call_signaling': cls.BASE_CALL_SIGNALING_PORT + port_offset,
            },
            'log_file': os.path.join(cls.LOGS_DIR, f"{node_name.lower()}.log"),
            'db_file': os.path.join(cls.LOGS_DIR, f"{node_name.lower()}.db"),
        }
    
    @classmethod
    def ensure_logs_dir(cls):
        """Создать директорию для логов"""
        os.makedirs(cls.LOGS_DIR, exist_ok=True)
    
    @classmethod
    def cleanup_logs(cls):
        """Очистить старые логи"""
        import glob
        import shutil
        
        if os.path.exists(cls.LOGS_DIR):
            # Удалить старые логи (>7 дней)
            import time
            current_time = time.time()
            
            for log_file in glob.glob(os.path.join(cls.LOGS_DIR, "*.log")):
                if current_time - os.path.getmtime(log_file) > 7 * 24 * 3600:
                    os.remove(log_file)
            
            # Удалить старые базы данных
            for db_file in glob.glob(os.path.join(cls.LOGS_DIR, "*.db")):
                if current_time - os.path.getmtime(db_file) > 7 * 24 * 3600:
                    os.remove(db_file)
