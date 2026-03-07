# 🧪 Тестирование проекта

## 🚀 Быстрый старт

### **Запуск всех тестов:**
```bash
cd tests
python3 run_all_tests.py
```

## 📁 Структура

```
tests/
├── README.md                    # Этот файл
├── run_all_tests.py           # 🌟 Запуск всех тестов
├── integrated/                 # Интегрированные тесты
│   └── integrated_test_suite.py
├── mesh/                       # Mesh-сеть тесты
│   └── mesh_test_suite.py
├── examples/                   # Примеры тестов
│   ├── quick_test.py
│   ├── manual_test.py
│   └── stress_test.py
├── utils/                      # Утилиты
│   ├── test_config.py
│   ├── test_node.py
│   ├── mesh_simulator.py
│   └── report_generator.py
├── logs/                       # JSON логи (.gitignore)
└── reports/                    # Отчеты (.gitignore)
```

## 📊 Что тестируется

### 🌐 **Интегрированные тесты:**
- Mesh-сеть + Шифрование + Передача файлов

### 🌐 **Mesh-сеть:**
- Хендшейки, связность, ретрансляция

### 📝 **Примеры:**
- Быстрый, ручной, нагрузочный тесты

## 🎮 Запуск отдельных тестов

```bash
# Интегрированные тесты
python3 integrated/integrated_test_suite.py --comprehensive

# Только mesh-сеть
python3 mesh/mesh_test_suite.py --quick

# Примеры
python3 examples/quick_test.py
python3 examples/manual_test.py
python3 examples/stress_test.py
```

## 📁 Логи и отчеты

- **Логи:** `tests/logs/*.json`
- **Отчеты:** `tests/reports/*.json`
- Обе папки в `.gitignore`

---

**🌐 Запустите `python3 run_all_tests.py` для полного тестирования проекта!**
