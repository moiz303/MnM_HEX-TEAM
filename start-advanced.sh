#!/bin/bash

echo "🚀 Запуск Advanced Docker Mesh Network"
echo "====================================="

# Создаем необходимые директории
mkdir -p logs/{alice,bob,charlie} downloads/{alice,bob,charlie} uploads

# Останавливаем предыдущие контейнеры
echo "🛑 Остановка предыдущих контейнеров..."
docker-compose -f docker-compose-advanced.yml down 2>/dev/null

# Удаляем старые образы для пересборки
echo "🗑️  Очистка старых образов..."
docker-compose -f docker-compose-advanced.yml down --rmi all 2>/dev/null

# Собираем и запускаем
echo "🔨 Сборка образов..."
docker-compose -f docker-compose-advanced.yml build --no-cache

echo "🚀 Запуск контейнеров..."
docker-compose -f docker-compose-advanced.yml up -d

echo ""
echo "⏳ Ожидание запуска сервисов..."
sleep 30

# Проверяем статус
echo ""
echo "📊 Статус контейнеров:"
docker-compose -f docker-compose-advanced.yml ps

echo ""
echo "🔍 Проверка здоровья сервисов..."
for service in alice bob charlie; do
    container="mesh-$service-advanced"
    health=$(docker inspect $container --format='{{.State.Health.Status}}' 2>/dev/null || echo "starting")
    status=$(docker inspect $container --format='{{.State.Status}}' 2>/dev/null || echo "unknown")
    
    case $health in
        "healthy")
            echo "✅ $service: $status ($health)"
            ;;
        "unhealthy")
            echo "❌ $service: $status ($health)"
            ;;
        "starting"|"none")
            echo "⏳ $service: $status ($health)"
            ;;
        *)
            echo "❓ $service: $status ($health)"
            ;;
    esac
done

echo ""
echo "🌐 Доступные узлы:"
echo "   Alice:   http://localhost:8080/login"
echo "   Bob:     http://localhost:8081/login" 
echo "   Charlie: http://localhost:8082/login"
echo ""
echo "📊 Мониторинг:"
echo "   Логи: tail -f logs/monitor.log"
echo "   Статус: docker-compose -f docker-compose-advanced.yml ps"
echo ""
echo "🧪 Тестирование:"
echo "   Запустите: ./test-docker-mesh.sh"
echo ""
echo "🛑 Остановка: docker-compose -f docker-compose-advanced.yml down"
echo ""
echo "🎉 Advanced Mesh Network запущена!"
