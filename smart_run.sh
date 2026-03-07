#!/bin/bash

# Запуск мессенджера
cd "$(dirname "$0")"

# Генерируем уникальное имя
export MESSENGER_USERNAME="user_$(date +%s)"
echo "🚀 Запуск мессенджера"
echo "🌐 Откройте: http://127.0.0.1:5000/login"
echo "� Имя пользователя будет задано на сайте"
.venv/bin/python back/web.py
