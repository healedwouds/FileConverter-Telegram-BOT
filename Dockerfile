# FileConverter Bot - Dockerfile
# Образ для запуска Telegram-бота конвертации файлов

# Используем официальный образ Python
FROM python:3.11-slim

# Метаданные образа
LABEL maintainer="FileConverter Bot"
LABEL description="Telegram-бот для конвертации файлов"

# Устанавливаем переменные окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    # FFmpeg для обработки аудио и видео
    ffmpeg \
    # Pandoc для конвертации документов
    pandoc \
    # LaTeX для генерации PDF (минимальная установка)
    texlive-xetex \
    texlive-fonts-recommended \
    texlive-lang-cyrillic \
    # Утилиты
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Создаём рабочую директорию
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем Python-зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY app/ ./app/

# Создаём непривилегированного пользователя для безопасности
RUN useradd --create-home --shell /bin/bash botuser \
    && chown -R botuser:botuser /app

# Переключаемся на непривилегированного пользователя
USER botuser

# Команда запуска бота
CMD ["python", "-m", "app.bot"]
