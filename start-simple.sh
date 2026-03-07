#!/bin/bash

echo "🐳 Запуск простой Mesh Network..."

# Создаем директории
mkdir -p logs downloads/uploads

# Останавливаем предыдущие
docker-compose -f docker-compose-simple.yml down 2>/dev/null

# Запускаем
echo "🚀 Запуск 3 узлов..."
docker-compose -f docker-compose-simple.yml up -d

echo ""
echo "✅ Узлы доступны:"
echo "   Alice:   http://localhost:8080"
echo "   Bob:     http://localhost:8081" 
echo "   Charlie: http://localhost:8082"
echo ""
echo "📝 Откройте каждый URL в отдельной вкладке и тестируйте!"
echo "🛑 Остановка: docker-compose -f docker-compose-simple.yml down"
