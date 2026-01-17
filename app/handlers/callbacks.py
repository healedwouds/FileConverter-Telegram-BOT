"""
FileConverter Bot - Обработчики callback-кнопок
Модуль для обработки выбора формата конвертации
"""

import os
import tempfile
import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, FSInputFile
from aiogram.fsm.context import FSMContext

from app.handlers.files import FileState
from app.utils.converter_logic import (
    convert_file, 
    save_file_from_bytes,
    cleanup_files,
    ConversionError
)
from app.keyboards.inline import get_file_type

# Создаём роутер для callback-кнопок
router = Router(name="callbacks")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "cancel")
async def handle_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик кнопки отмены
    Очищает состояние и удаляет сообщение с кнопками
    """
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Конвертация отменена</b>\n\n"
        "<i>Отправьте новый файл, чтобы начать снова.</i>",
        parse_mode="HTML"
    )
    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("cvt:"))
async def handle_conversion(
    callback: CallbackQuery, 
    bot: Bot,
    state: FSMContext
) -> None:
    """
    Обработчик выбора формата конвертации
    Скачивает файл, конвертирует и отправляет результат
    
    Формат callback_data: cvt:{target_format}
    file_id хранится в FSM-состоянии
    """
    await callback.answer("⏳ Начинаю конвертацию...")
    
    # Парсим callback_data - получаем только целевой формат
    parts = callback.data.split(":")
    if len(parts) != 2:
        await callback.message.edit_text(
            "❌ Ошибка: некорректные данные. Попробуйте отправить файл снова.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    _, target_format = parts
    
    # Получаем данные из состояния (включая file_id)
    data = await state.get_data()
    file_id = data.get("file_id", "")
    file_name = data.get("file_name", "file")
    source_extension = data.get("file_extension", "")
    
    if not source_extension or not file_id:
        await callback.message.edit_text(
            "❌ Ошибка: информация о файле потеряна. Отправьте файл снова.",
            parse_mode="HTML"
        )
        await state.clear()
        return
    
    # Обновляем сообщение - показываем статус загрузки
    status_message = await callback.message.edit_text(
        "⏳ <b>Обработка файла...</b>\n\n"
        "📥 Загружаю файл с серверов Telegram...",
        parse_mode="HTML"
    )
    
    # Создаём временные файлы
    temp_dir = tempfile.gettempdir()
    input_path = os.path.join(temp_dir, f"input_{callback.from_user.id}_{file_id[:8]}.{source_extension}")
    output_filename = Path(file_name).stem + f".{target_format}"
    output_path = os.path.join(temp_dir, f"output_{callback.from_user.id}_{file_id[:8]}.{target_format}")
    
    try:
        # Скачиваем файл
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        
        # Сохраняем во временный файл
        await save_file_from_bytes(file_bytes.read(), input_path)
        
        # Обновляем статус - конвертация
        file_type = get_file_type(source_extension)
        if file_type == 'video':
            status_text = "🎬 Конвертирую видео... Это может занять некоторое время."
        elif file_type == 'audio':
            status_text = "🎵 Конвертирую аудио..."
        elif file_type == 'image':
            status_text = "🖼️ Конвертирую изображение..."
        elif file_type in ('document', 'pdf', 'text'):
            status_text = "📄 Конвертирую документ..."
        elif file_type == 'spreadsheet':
            status_text = "📊 Конвертирую таблицу..."
        else:
            status_text = "⚙️ Конвертирую файл..."
        
        await status_message.edit_text(
            f"⏳ <b>Обработка файла...</b>\n\n{status_text}",
            parse_mode="HTML"
        )
        
        # Конвертируем файл
        await convert_file(
            input_path=input_path,
            output_path=output_path,
            source_format=source_extension,
            target_format=target_format
        )
        
        # Проверяем, что выходной файл создан
        if not os.path.exists(output_path):
            raise ConversionError("Выходной файл не был создан")
        
        # Обновляем статус - отправка
        await status_message.edit_text(
            "⏳ <b>Обработка файла...</b>\n\n"
            "📤 Загружаю результат...",
            parse_mode="HTML"
        )
        
        # Отправляем результат
        result_file = FSInputFile(output_path, filename=output_filename)
        
        await callback.message.answer_document(
            document=result_file,
            caption=(
                f"✅ <b>Конвертация завершена!</b>\n\n"
                f"📁 <code>{file_name}</code> → <code>{output_filename}</code>"
            ),
            parse_mode="HTML"
        )
        
        # Обновляем статусное сообщение
        await status_message.edit_text(
            "✅ <b>Готово!</b>\n\n"
            f"📁 <code>{file_name}</code> → <code>{output_filename}</code>\n\n"
            "<i>Отправьте ещё файл для конвертации.</i>",
            parse_mode="HTML"
        )
        
        logger.info(
            f"Успешная конвертация: {file_name} ({source_extension}) -> {target_format} "
            f"для пользователя {callback.from_user.id}"
        )
        
    except ConversionError as e:
        logger.error(f"Ошибка конвертации: {e}")
        await status_message.edit_text(
            f"❌ <b>Ошибка конвертации</b>\n\n"
            f"<i>{str(e)}</i>\n\n"
            "Попробуйте отправить другой файл или выбрать другой формат.",
            parse_mode="HTML"
        )
    
    except Exception as e:
        logger.exception(f"Неожиданная ошибка при конвертации: {e}")
        await status_message.edit_text(
            "❌ <b>Произошла непредвиденная ошибка</b>\n\n"
            "Пожалуйста, попробуйте позже или отправьте другой файл.",
            parse_mode="HTML"
        )
    
    finally:
        # Очищаем состояние и временные файлы
        await state.clear()
        await cleanup_files(input_path, output_path)


@router.callback_query()
async def handle_unknown_callback(callback: CallbackQuery) -> None:
    """
    Обработчик неизвестных callback-запросов
    """
    await callback.answer(
        "⚠️ Эта кнопка устарела. Отправьте файл заново.",
        show_alert=True
    )
    logger.warning(f"Неизвестный callback: {callback.data}")
