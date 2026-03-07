#!/bin/bash

echo "🐳 Запуск Mesh Network (прямые образы)..."

# Останавливаем предыдущие
docker-compose -f docker-compose-direct.yml down 2>/dev/null

# Запускаем
echo "🚀 Запуск 3 узлов..."
docker-compose -f docker-compose-direct.yml up -d

# Ждем запуска
echo "⏳ Ожидание запуска контейнеров..."
sleep 10

# Проверяем статус
echo ""
echo "✅ Статус контейнеров:"
docker-compose -f docker-compose-direct.yml ps

echo ""
echo "🌐 Доступные узлы:"
echo "   Alice:   http://localhost:8080"
echo "   Bob:     http://localhost:8081" 
echo "   Charlie: http://localhost:8082"
echo ""
echo "📝 Инструкция:"
echo "   1. Откройте каждый URL в отдельной вкладке"
echo "   2. Войдите в систему (имена уже установлены)"
echo "   3. Тестируйте чаты и визуализацию"
echo ""
echo "🛑 Остановка: docker-compose -f docker-compose-direct.yml down"
