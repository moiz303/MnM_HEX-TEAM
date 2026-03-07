"""
Генератор отчетов о тестировании mesh-сети (исправленная версия)
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass

@dataclass
class TestResult:
    """Результат теста"""
    test_name: str
    success_rate: float
    duration: float
    details: Dict[str, Any]
    timestamp: float
    status: str  # 'passed', 'failed', 'warning'

class ReportGenerator:
    """Генератор отчетов о тестировании"""
    
    def __init__(self):
        self.test_results: List[TestResult] = []
        self.test_session_id = f"session_{int(time.time())}"
        self.start_time = time.time()
        
    def add_test_result(self, test_name: str, success_rate: float, duration: float, 
                       details: Dict[str, Any], status: str = None):
        """Добавить результат теста"""
        if status is None:
            status = self._determine_status(success_rate)
        
        result = TestResult(
            test_name=test_name,
            success_rate=success_rate,
            duration=duration,
            details=details,
            timestamp=time.time(),
            status=status
        )
        
        self.test_results.append(result)
        return result
    
    def _determine_status(self, success_rate: float) -> str:
        """Определить статус по成功率"""
        from test_config import TestConfig
        
        if success_rate >= TestConfig.QUALITY_THRESHOLDS['excellent']:
            return 'passed'
        elif success_rate >= TestConfig.QUALITY_THRESHOLDS['good']:
            return 'warning'
        else:
            return 'failed'
    
    def generate_summary(self) -> Dict[str, Any]:
        """Сгенерировать сводку результатов"""
        if not self.test_results:
            return {'status': 'no_results'}
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if r.status == 'passed')
        warning_tests = sum(1 for r in self.test_results if r.status == 'warning')
        failed_tests = sum(1 for r in self.test_results if r.status == 'failed')
        
        average_success_rate = sum(r.success_rate for r in self.test_results) / total_tests
        total_duration = sum(r.duration for r in self.test_results)
        
        overall_status = 'passed'
        if failed_tests > 0:
            overall_status = 'failed'
        elif warning_tests > 0:
            overall_status = 'warning'
        
        return {
            'session_id': self.test_session_id,
            'start_time': self.start_time,
            'end_time': time.time(),
            'total_duration': time.time() - self.start_time,
            'total_tests': total_tests,
            'passed_tests': passed_tests,
            'warning_tests': warning_tests,
            'failed_tests': failed_tests,
            'average_success_rate': average_success_rate,
            'total_test_duration': total_duration,
            'overall_status': overall_status,
            'test_results': [
                {
                    'name': r.test_name,
                    'success_rate': r.success_rate,
                    'duration': r.duration,
                    'status': r.status,
                    'timestamp': r.timestamp
                }
                for r in self.test_results
            ]
        }
    
    def generate_detailed_report(self) -> Dict[str, Any]:
        """Сгенерировать детальный отчет"""
        summary = self.generate_summary()
        
        detailed_results = []
        for result in self.test_results:
            detailed_result = {
                'test_name': result.test_name,
                'success_rate': result.success_rate,
                'duration': result.duration,
                'status': result.status,
                'timestamp': result.timestamp,
                'details': result.details,
                'recommendations': self._generate_recommendations(result)
            }
            detailed_results.append(detailed_result)
        
        summary['detailed_results'] = detailed_results
        summary['recommendations'] = self._generate_overall_recommendations()
        
        return summary
    
    def _generate_recommendations(self, result: TestResult) -> List[str]:
        """Сгенерировать рекомендации для теста"""
        recommendations = []
        
        if result.status == 'failed':
            recommendations.append("Критические проблемы обнаружены. Требуется немедленное внимание.")
            
            if result.test_name == 'connectivity':
                recommendations.append("Проверьте сетевые настройки и порты.")
                recommendations.append("Убедитесь, что файрвол блокирует соединения.")
            elif result.test_name == 'offline_delivery':
                recommendations.append("Проверьте работу очередей сообщений.")
                recommendations.append("Увеличьте время ожидания доставки.")
            elif result.test_name == 'handshakes':
                recommendations.append("Проверьте криптографические компоненты.")
                recommendations.append("Синхронизируйте время между узлами.")
        
        elif result.status == 'warning':
            recommendations.append("Обнаружены проблемы, требующие внимания.")
            
            if result.success_rate < 80:
                recommendations.append("Рассмотрите оптимизацию конфигурации сети.")
                recommendations.append("Проверьте нагрузку на ретрансляторы.")
        
        elif result.status == 'passed':
            if result.success_rate < 95:
                recommendations.append("Отличный результат, но есть возможности для улучшения.")
        
        return recommendations
    
    def _generate_overall_recommendations(self) -> List[str]:
        """Сгенерировать общие рекомендации"""
        recommendations = []
        
        if not self.test_results:
            return ["Нет результатов для анализа."]
        
        avg_success = sum(r.success_rate for r in self.test_results) / len(self.test_results)
        
        if avg_success >= 90:
            recommendations.append("Отличная работа! Mesh-сеть функционирует идеально.")
            recommendations.append("Система готова к производственному использованию.")
        elif avg_success >= 75:
            recommendations.append("Хороший результат. Рекомендуется дополнительная оптимизация.")
            recommendations.append("Проверьте настройки сети и увеличьте время ожидания.")
        elif avg_success >= 50:
            recommendations.append("Требуется улучшение конфигурации.")
            recommendations.append("Рассмотрите увеличение ресурсов и оптимизацию алгоритмов.")
        else:
            recommendations.append("Критические проблемы требуют немедленного решения.")
            recommendations.append("Проверьте все компоненты системы и сетевую инфраструктуру.")
        
        return recommendations
    
    def export_json(self, filename: str = None) -> str:
        """Экспортировать отчет в JSON"""
        if filename is None:
            filename = f"test_report_{self.test_session_id}.json"
        
        # Сохраняем в папку reports
        reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'reports')
        os.makedirs(reports_dir, exist_ok=True)
        
        filepath = os.path.join(reports_dir, filename)
        
        report = self.generate_detailed_report()
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        return filepath
    
    def print_summary(self):
        """Вывести сводку в консоль"""
        summary = self.generate_summary()
        
        print("\n" + "="*60)
        print("🧪 MESH NETWORK TEST REPORT")
        print("="*60)
        print(f"Session ID: {summary['session_id']}")
        print(f"Duration: {summary['total_duration']:.1f}s")
        print(f"Overall Status: {summary['overall_status'].upper()}")
        print(f"Average Success Rate: {summary['average_success_rate']:.1f}%")
        print(f"Tests: {summary['passed_tests']} passed, {summary['warning_tests']} warnings, {summary['failed_tests']} failed")
        print("="*60)
        
        for result in summary['test_results']:
            status_icon = "✅" if result['status'] == 'passed' else "⚠️" if result['status'] == 'warning' else "❌"
            print(f"{status_icon} {result['name']}: {result['success_rate']:.1f}% ({result['duration']:.1f}s)")
        
        print("="*60)
        
        # Рекомендации
        recommendations = self._generate_overall_recommendations()
        if recommendations:
            print("\n💡 Recommendations:")
            for i, rec in enumerate(recommendations, 1):
                print(f"  {i}. {rec}")
        
        print("="*60)
