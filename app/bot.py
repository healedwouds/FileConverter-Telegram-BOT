"""
FileConverter Bot - Точка входа
Главный модуль для запуска Telegram-бота конвертации файлов
"""

import os
import sys
import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# Импортируем роутеры обработчиков
from app.handlers import start, files, callbacks


def setup_logging() -> None:
    """
    Настройка системы логирования
    Логи выводятся в консоль для сбора Docker-ом
    """
    log_format = (
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Уменьшаем уровень логов для библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)


def get_bot_token() -> str:
    """
    Получает токен бота из переменных окружения
    
    Returns:
        Токен бота
    
    Raises:
        ValueError: Если токен не найден
    """
    token = os.getenv("BOT_TOKEN")
    
    if not token:
        raise ValueError(
            "❌ Токен бота не найден!\n"
            "Установите переменную окружения BOT_TOKEN или "
            "создайте файл .env с токеном."
        )
    
    return token


async def main() -> None:
    """
    Главная функция запуска бота
    Инициализирует бота, диспетчер и запускает polling
    """
    # Настраиваем логирование
    setup_logging()
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 50)
    logger.info("🚀 Запуск FileConverter Bot")
    logger.info("=" * 50)
    
    # Получаем токен бота
    try:
        bot_token = get_bot_token()
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)
    
    # Создаём экземпляр бота с настройками по умолчанию
    bot = Bot(
        token=bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Создаём хранилище для FSM (в памяти)
    storage = MemoryStorage()
    
    # Создаём диспетчер
    dp = Dispatcher(storage=storage)
    
    # Регистрируем роутеры обработчиков
    # Порядок важен: сначала команды, потом файлы, потом callbacks
    dp.include_router(start.router)
    dp.include_router(files.router)
    dp.include_router(callbacks.router)
    
    logger.info("✅ Роутеры обработчиков зарегистрированы")
    
    # Выводим информацию о лимите файлов
    max_file_size = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    logger.info(f"📁 Максимальный размер файла: {max_file_size} МБ")
    
    # Получаем информацию о боте
    try:
        bot_info = await bot.get_me()
        logger.info(f"🤖 Бот: @{bot_info.username} (ID: {bot_info.id})")
    except Exception as e:
        logger.error(f"❌ Ошибка получения информации о боте: {e}")
        sys.exit(1)
    
    logger.info("=" * 50)
    logger.info("✅ Бот успешно запущен и готов к работе!")
    logger.info("=" * 50)
    
    try:
        # Удаляем вебхуки и старые обновления перед запуском
        await bot.delete_webhook(drop_pending_updates=True)
        
        # Запускаем polling (long-polling)
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )
    except Exception as e:
        logger.exception(f"❌ Критическая ошибка: {e}")
    finally:
        logger.info("👋 Бот остановлен")
        await bot.session.close()


if __name__ == "__main__":
    # Запускаем асинхронный цикл
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен пользователем")
