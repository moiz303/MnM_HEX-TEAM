#!/bin/bash

echo "🐳 Тестирование Docker Mesh Network"
echo "=================================="

# Проверяем, что контейнеры запущены
echo "🔍 Проверка статуса контейнеров..."
if ! docker-compose -f docker-compose-simple.yml ps | grep -q "Up"; then
    echo "❌ Контейнеры не запущены. Запускаем..."
    ./start-simple.sh
    sleep 20
fi

echo ""
echo "🌐 Тестирование доступности узлов..."

# Тестируем HTTP доступность
for port in 8080 8081 8082; do
    node_name=""
    case $port in
        8080) node_name="Alice" ;;
        8081) node_name="Bob" ;;
        8082) node_name="Charlie" ;;
    esac
    
    echo -n "   $node_name (localhost:$port): "
    if curl -s -o /dev/null -w "%{http_code}" http://localhost:$port | grep -q "200"; then
        echo "✅ Доступен"
    else
        echo "❌ Недоступен"
    fi
done

echo ""
echo "📡 Тестирование P2P портов..."

# Проверяем UDP порты для P2P
for port in 37021 37022 37023; do
    echo -n "   UDP порт $port: "
    if lsof -iUDP:$port > /dev/null 2>&1; then
        echo "✅ Открыт"
    else
        echo "⚠️  Не найден (может быть в контейнере)"
    fi
done

echo ""
echo "🔗 Тестирование сетевого взаимодействия..."

# Проверяем сетевые интерфейсы контейнеров
echo "   Сетевые адреса контейнеров:"
for container in mesh-alice mesh-bob mesh-charlie; do
    ip=$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' $container)
    name=$(docker inspect -f '{{.Name}}' $container)
    echo "   $name: $ip"
done

echo ""
echo "📊 Статистика Docker сети:"
docker network inspect mnm_hex-team_mesh-net --format='{{range .Containers}}{{.Name}}: {{.IPv4Address}}{{"\n"}}{{end}}'

echo ""
echo "🧪 Функциональное тестирование..."

# Тест API эндпоинтов
echo "   Тестирование API эндпоинтов:"
for port in 8080 8081 8082; do
    node_name=""
    case $port in
        8080) node_name="Alice" ;;
        8081) node_name="Bob" ;;
        8082) node_name="Charlie" ;;
    esac
    
    echo -n "     $node_name API: "
    response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:$port/api/current_username 2>/dev/null)
    if [ "$response" = "200" ]; then
        echo "✅ Работает"
    else
        echo "❌ Ошибка ($response)"
    fi
done

echo ""
echo "📝 Рекомендации:"
echo "   1. Откройте в браузере:"
echo "      - Alice: http://localhost:8080/login"
echo "      - Bob:   http://localhost:8081/login" 
echo "      - Charlie: http://localhost:8082/login"
echo ""
echo "   2. Войдите в систему для каждого узла"
echo "   3. Проверьте обнаружение пиров в sidebar"
echo "   4. Протестируйте отправку сообщений"
echo "   5. Проверьте mesh визуализацию"
echo ""
echo "   6. Для остановки: docker-compose -f docker-compose-simple.yml down"
echo ""
echo "🎉 Docker Mesh Network готова к тестированию!"
