#!/bin/bash

# Запуск мессенджера с разными именами пользователей
# Использование: ./run_messenger.sh [username]

if [ -z "$1" ]; then
    echo "Использование: ./run_messenger.sh <username>"
    echo "Пример: ./run_messenger.sh alice"
    exit 1
fi

export MESSENGER_USERNAME=$1
echo "🚀 Запуск мессенджера с именем: $1"
cd "$(dirname "$0")"
.venv/bin/python back/web.py
