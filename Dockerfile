FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для компиляции
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Копирование зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .

# Создание директорий
RUN mkdir -p /app/logs /app/downloads/uploads

# Открываем порты
EXPOSE 8080

# Переменные окружения
ENV PYTHONPATH=/app
ENV MESSENGER_USERNAME=demo_user

# Запуск приложения
CMD ["python3", "run_server.py"]
