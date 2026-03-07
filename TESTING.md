# 🧪 Тестирование системы передачи файлов

## 📋 Обзор тестов

Система включает несколько уровней тестирования для проверки функциональности передачи файлов.

## 🚀 Быстрый старт

### 1. Запуск базовых тестов
```bash
python3 test_file_transfer.py
```
Проверяет:
- ✅ Импорт всех модулей
- ✅ Инициализацию FileTransferManager
- ✅ Валидацию файлов
- ✅ Чанкинг файлов
- ✅ Веб-сервер

### 2. Запуск интеграционных тестов
```bash
python3 test_integration.py
```
Проверяет:
- ✅ Симуляцию передачи между пирами
- ✅ Шифрование/дешифрование
- ✅ Обработку ошибок

### 3. Запуск реального сервера
```bash
python3 run_server.py
```
Запускает веб-интерфейс на http://localhost:5000

## 🔍 Детальное тестирование

### Unit тесты (test_file_transfer.py)

**Backend Imports:**
- Проверяет что все модули импортируются без ошибок
- Включает FileTransferManager, протоколы, криптографию

**File Transfer Manager:**
- Создает mock объекты для криптографии и соединений
- Проверяет успешную инициализацию менеджера

**File Validation:**
- Создает тестовый файл 1MB
- Проверяет валидацию пути и размера
- Удаляет временный файл

**File Chunking:**
- Создает файл 1MB (64 чанка по 16KB)
- Проверяет правильность разбиения на чанки
- Валидирует размеры всех чанков

**Web Server:**
- Проверяет что Flask приложение запускается
- Тестирует базовые эндпоинты

### Интеграционные тесты (test_integration.py)

**Mock Peer Simulation:**
- Создает два mock пира с разными ID
- Симулирует полную передачу файла
- Проверяет отправку file_offer и file_chunk сообщений
- Валидирует обработку на принимающей стороне

**Encryption Flow:**
- Тестирует XOR шифрование (для тестов)
- Проверяет что зашифрованные данные != исходным
- Проверяет успешное дешифрование

**Error Handling:**
- Проверяет обработку несуществующих файлов
- Тестирует валидацию размера файла
- Проверяет обработку ошибок шифрования

## 🌐 Ручное тестирование через веб-интерфейс

### Запуск сервера
```bash
python3 run_server.py
```

### Шаги для тестирования
1. **Откройте браузер** → http://localhost:5000
2. **Проверьте интерфейс** → должен загрузиться фронтенд
3. **Протестируйте загрузку файла:**
   - Нажмите "Attach File"
   - Выберите файл (до 100MB)
   - Отправьте сообщение (можно самому себе)
4. **Следите за прогрессом:**
   - Откройте консоль разработчика (F12)
   - Ищите логи `[file_transfer]`
   - Проверьте прогресс-бар

### API эндпоинты для тестирования

**Инициализация загрузки:**
```bash
curl -X POST http://localhost:5000/api/upload/init \
  -H "Content-Type: application/json" \
  -d '{"filename": "test.txt", "size": 1024}'
```

**Загрузка чанка:**
```bash
curl -X POST http://localhost:5000/api/upload/chunk \
  -F "upload_id=YOUR_UPLOAD_ID" \
  -F "chunk_index=0" \
  -F "chunk=@test.txt"
```

**Завершение загрузки:**
```bash
curl -X POST http://localhost:5000/api/upload/complete \
  -H "Content-Type: application/json" \
  -d '{"upload_id": "YOUR_UPLOAD_ID"}'
```

## 🔧 Диагностика проблем

### Проверка логов
```bash
# Запуск с детальными логами
python3 run_server.py 2>&1 | tee server.log
```

### Проверка файлов
```bash
# Проверка загруженных файлов
ls -la downloads/uploads/
ls -la downloads/uploads/tmp/
```

### Проверка портов
```bash
# Проверка что порт 5000 свободен
lsof -i :5000
```

## ⚠️ Известные ограничения

1. **Mock криптография** в тестах использует XOR (реальная использует AES)
2. **Тестирование пиров** эмулируется без реальной сети
3. **Веб-интерфейс** требует наличия фронтенда в `frontend/`

## 📊 Ожидаемые результаты

### Успешное прохождение тестов:
```
🚀 Starting File Transfer System Tests
✅ Backend Imports: PASSED
✅ File Transfer Manager: PASSED
✅ File Validation: PASSED
✅ File Chunking: PASSED
✅ Web Server: PASSED
📊 Test Results: 5/5 tests passed
🎉 All tests passed! System is ready for use.
```

### Успешные интеграционные тесты:
```
🚀 Starting Integration Tests
✅ Mock Peer Simulation: PASSED
✅ Encryption Flow: PASSED
✅ Error Handling: PASSED
📊 Integration Test Results: 3/3 tests passed
🎉 All integration tests passed!
```

## 🚨 Если тесты не проходят

1. **Проверьте зависимости:**
   ```bash
   python3 -c "import flask; print('Flask OK')"
   python3 -c "import flask_cors; print('Flask-CORS OK')"
   ```

2. **Проверьте права доступа:**
   ```bash
   mkdir -p downloads/uploads
   chmod 755 downloads/uploads
   ```

3. **Проверьте импорты:**
   ```bash
   python3 -c "from back.network.file_transfer import FileTransferManager; print('Import OK')"
   ```

## 🎯 Ручная проверка функциональности

После запуска сервера проверьте:

1. **Базовая функциональность:**
   - [ ] Загрузка файла до 100MB
   - [ ] Прогресс-бар показывает корректный прогресс
   - [ ] Файл сохраняется в `downloads/uploads/`

2. **Обработка ошибок:**
   - [ ] Слишком большой файл (>100MB) отклоняется
   - [ ] Пустой файл обрабатывается корректно
   - [ ] Прерывание загрузки работает

3. **Безопасность:**
   - [ ] Файлы шифруются перед передачей
   - [ ] Валидация типов файлов работает
   - [ ] Path traversal предотвращается

Система готова к использованию после прохождения всех тестов! 🚀
