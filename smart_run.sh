#!/bin/bash

# Умный запуск мессенджера с проверкой имени
# Использование: ./smart_run.sh [username]

cd "$(dirname "$0")"

# Проверяем, передано ли имя аргументом
if [ ! -z "$1" ]; then
    export MESSENGER_USERNAME="$1"
    echo "🚀 Запуск мессенджера с именем: $1"
    .venv/bin/python back/web.py
    exit 0
fi

# Проверяем переменную окружения
if [ ! -z "$MESSENGER_USERNAME" ]; then
    echo "🚀 Запуск мессенджера с именем из переменной: $MESSENGER_USERNAME"
    .venv/bin/python back/web.py
    exit 0
fi

# Если имени нет, предлагаем варианты
echo "🤔 Имя пользователя не указано!"
echo ""
echo "Выберите вариант:"
echo "1. ./smart_run.sh alice     # Запустить с именем 'alice'"
echo "2. ./smart_run.sh bob       # Запустить с именем 'bob'"
echo "3. export MESSENGER_USERNAME='your_name' && ./smart_run.sh"
echo "4. Или откройте http://127.0.0.1:5000/login для настройки через браузер"
echo ""
echo "⚡ Быстрый запуск с именем по умолчанию:"
echo "   MESSENGER_USERNAME='user1' ./smart_run.sh"
echo ""

# Запускаем с генерированным именем
export MESSENGER_USERNAME="user_$(date +%s)"
echo "🔧 Запуск с авто-генерированным именем: $MESSENGER_USERNAME"
.venv/bin/python back/web.py
