#!/bin/bash

echo "🐳 Запуск Mesh Network в Docker..."
echo "=================================="

# Проверяем наличие Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен. Установите Docker:"
    echo "   macOS: brew install docker"
    echo "   Ubuntu: sudo apt install docker.io"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose не установлен. Установите Docker Compose:"
    echo "   macOS: brew install docker-compose"
    echo "   Ubuntu: sudo apt install docker-compose"
    exit 1
fi

# Создаем директории
mkdir -p logs downloads/uploads

# Останавливаем предыдущие контейнеры
echo "🛑 Остановка предыдущих контейнеров..."
docker-compose down --remove-orphans 2>/dev/null

# Собираем образы
echo "🔨 Сборка Docker образов..."
docker-compose build --no-cache

# Запускаем контейнеры
echo "🚀 Запуск контейнеров..."
docker-compose up -d

# Показываем статус
echo ""
echo "✅ Контейнеры запущены:"
echo "=================================="
docker-compose ps

echo ""
echo "🌐 Доступные узлы:"
echo "   Alice:   http://localhost:8080"
echo "   Bob:     http://localhost:8081" 
echo "   Charlie: http://localhost:8082"
echo "   Diana:   http://localhost:8083"
echo ""
echo "📝 Инструкция:"
echo "   1. Откройте каждый узел в отдельной вкладке"
echo "   2. Войдите в систему (имя уже установлено)"
echo "   3. Проверьте список пиров в каждом узле"
echo "   4. Отправляйте сообщения между узлами"
echo "   5. Проверьте визуализатор сети"
echo ""
echo "🛑 Остановка: docker-compose down"
echo "📊 Логи: docker-compose logs -f [alice|bob|charlie|diana]"
echo "=================================="
