#!/bin/bash

echo "🐳 Docker Mesh Network Manager"
echo "==============================="
echo ""

# Показываем меню
show_menu() {
    echo "Выберите режим запуска:"
    echo "1) Simple Mesh (3 узла, базовая настройка)"
    echo "2) Advanced Mesh (3 узла, мониторинг, health checks)"
    echo "3) Direct Mesh (прямые образы, без сборки)"
    echo "4) Остановить все контейнеры"
    echo "5) Показать статус"
    echo "6) Тестировать сеть"
    echo "7) Показать логи"
    echo "8) Очистить Docker"
    echo "0) Выход"
    echo ""
}

# Функция для остановки всех контейнеров
stop_all() {
    echo "🛑 Остановка всех контейнеров..."
    docker-compose -f docker-compose-simple.yml down 2>/dev/null
    docker-compose -f docker-compose-advanced.yml down 2>/dev/null
    docker-compose -f docker-compose-direct.yml down 2>/dev/null
    echo "✅ Все контейнеры остановлены"
}

# Функция для показа статуса
show_status() {
    echo "📊 Статус всех контейнеров:"
    echo ""
    
    echo "=== Simple Mesh ==="
    docker-compose -f docker-compose-simple.yml ps 2>/dev/null || echo "Не запущен"
    
    echo ""
    echo "=== Advanced Mesh ==="
    docker-compose -f docker-compose-advanced.yml ps 2>/dev/null || echo "Не запущен"
    
    echo ""
    echo "=== Direct Mesh ==="
    docker-compose -f docker-compose-direct.yml ps 2>/dev/null || echo "Не запущен"
    
    echo ""
    echo "=== Docker контейнеры ==="
    docker ps -a --filter "name=mesh-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}

# Функция для показа логов
show_logs() {
    echo "📝 Выберите контейнер для логов:"
    echo "1) Alice (simple)"
    echo "2) Bob (simple)"
    echo "3) Charlie (simple)"
    echo "4) Alice (advanced)"
    echo "5) Bob (advanced)"
    echo "6) Charlie (advanced)"
    echo "7) Monitor"
    echo "0) Назад"
    echo ""
    read -p "Выбор: " choice
    
    case $choice in
        1) docker logs -f mesh-alice ;;
        2) docker logs -f mesh-bob ;;
        3) docker logs -f mesh-charlie ;;
        4) docker logs -f mesh-alice-advanced ;;
        5) docker logs -f mesh-bob-advanced ;;
        6) docker logs -f mesh-charlie-advanced ;;
        7) docker logs -f mesh-monitor ;;
        0) return ;;
        *) echo "Неверный выбор" ;;
    esac
}

# Функция для очистки Docker
cleanup_docker() {
    echo "🗑️  Очистка Docker..."
    read -p "Это удалит все контейнеры, образы и сети. Продолжить? (y/N): " confirm
    if [[ $confirm == [yY] ]]; then
        stop_all
        docker system prune -f
        docker volume prune -f
        echo "✅ Docker очищен"
    else
        echo "Отменено"
    fi
}

# Основной цикл меню
while true; do
    show_menu
    read -p "Выбор: " choice
    
    case $choice in
        1)
            echo "🚀 Запуск Simple Mesh..."
            stop_all
            ./start-simple.sh
            echo ""
            read -p "Нажмите Enter для продолжения..."
            ;;
        2)
            echo "🚀 Запуск Advanced Mesh..."
            stop_all
            ./start-advanced.sh
            echo ""
            read -p "Нажмите Enter для продолжения..."
            ;;
        3)
            echo "🚀 Запуск Direct Mesh..."
            stop_all
            ./start-direct.sh
            echo ""
            read -p "Нажмите Enter для продолжения..."
            ;;
        4)
            stop_all
            echo ""
            read -p "Нажмите Enter для продолжения..."
            ;;
        5)
            show_status
            echo ""
            read -p "Нажмите Enter для продолжения..."
            ;;
        6)
            ./test-docker-mesh.sh
            echo ""
            read -p "нажмите Enter для продолжения..."
            ;;
        7)
            show_logs
            ;;
        8)
            cleanup_docker
            echo ""
            read -p "нажмите Enter для продолжения..."
            ;;
        0)
            echo "👋 Выход"
            exit 0
            ;;
        *)
            echo "❌ Неверный выбор. Попробуйте снова."
            echo ""
            read -p "нажмите Enter для продолжения..."
            ;;
    esac
done
