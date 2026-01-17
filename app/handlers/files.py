"""
FileConverter Bot - Обработчики входящих файлов
"""

import os
import logging
from pathlib import Path

from aiogram import Router, F, Bot
from aiogram.types import Message, Document, PhotoSize, Audio, Video, Voice, VideoNote
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from app.keyboards.inline import (
    create_format_keyboard, 
    get_file_type,
    get_supported_extensions,
    get_conversion_info
)

# Создаём роутер для обработки файлов
router = Router(name="files")
logger = logging.getLogger(__name__)

# Максимальный размер файла в байтах (по умолчанию 50 МБ)
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024


class FileState(StatesGroup):
    """Состояния для хранения информации о файле"""
    waiting_for_format = State()


async def process_file(
    message: Message,
    file_id: str,
    file_name: str,
    file_size: int,
    state: FSMContext
) -> None:
    """
    Общая функция обработки файла
    
    Args:
        message: Сообщение с файлом
        file_id: ID файла в Telegram
        file_name: Имя файла
        file_size: Размер файла в байтах
        state: Контекст FSM для сохранения состояния
    """
    # Проверяем размер файла
    if file_size > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        file_mb = file_size / (1024 * 1024)
        await message.answer(
            f"❌ <b>Файл слишком большой!</b>\n\n"
            f"📁 Размер вашего файла: <b>{file_mb:.1f} МБ</b>\n"
            f"📏 Максимально допустимый: <b>{max_mb} МБ</b>\n\n"
            f"<i>Пожалуйста, отправьте файл меньшего размера.</i>",
            parse_mode="HTML"
        )
        return
    
    # Получаем расширение файла
    extension = Path(file_name).suffix.lower().lstrip('.') if file_name else ''
    
    # Проверяем поддержку формата
    if not extension or extension not in get_supported_extensions():
        supported = ", ".join(sorted(set(get_supported_extensions())))
        await message.answer(
            f"❌ <b>Неподдерживаемый формат файла!</b>\n\n"
            f"📁 Ваш файл: <code>{file_name or 'без имени'}</code>\n\n"
            f"<b>Поддерживаемые форматы:</b>\n"
            f"<code>{supported}</code>\n\n"
            f"<i>Отправьте файл в одном из поддерживаемых форматов.</i>",
            parse_mode="HTML"
        )
        return
    
    # Получаем информацию о возможных конвертациях
    conversion_info = get_conversion_info(extension)
    if not conversion_info or not conversion_info['available_formats']:
        await message.answer(
            f"ℹ️ <b>Нет доступных форматов для конвертации</b>\n\n"
            f"Файл <code>{file_name}</code> уже в оптимальном формате.",
            parse_mode="HTML"
        )
        return
    
    # Создаём клавиатуру с форматами
    keyboard = create_format_keyboard(extension, file_id)
    if not keyboard:
        await message.answer(
            "❌ Произошла ошибка при создании меню конвертации. Попробуйте ещё раз.",
            parse_mode="HTML"
        )
        return
    
    # Сохраняем информацию о файле в состоянии
    await state.update_data(
        file_id=file_id,
        file_name=file_name,
        file_extension=extension
    )
    await state.set_state(FileState.waiting_for_format)
    
    # Отправляем сообщение с выбором формата
    emoji = conversion_info['emoji']
    formats_text = ", ".join(conversion_info['format_names'].values())
    
    await message.answer(
        f"{emoji} <b>Файл получен!</b>\n\n"
        f"📁 <code>{file_name}</code>\n"
        f"📏 Размер: <b>{file_size / 1024:.1f} КБ</b>\n\n"
        f"<b>Выберите формат для конвертации:</b>",
        reply_markup=keyboard,
        parse_mode="HTML"
    )
    
    logger.info(f"Получен файл: {file_name} ({file_size} байт), расширение: {extension}")


@router.message(F.document)
async def handle_document(message: Message, state: FSMContext) -> None:
    """
    Обработчик документов
    Обрабатывает файлы, отправленные как документы
    """
    document: Document = message.document
    
    await process_file(
        message=message,
        file_id=document.file_id,
        file_name=document.file_name or "document",
        file_size=document.file_size or 0,
        state=state
    )


@router.message(F.photo)
async def handle_photo(message: Message, state: FSMContext) -> None:
    """
    Обработчик фотографий
    Telegram сжимает фото, конвертируем как JPEG
    """
    # Берём фото максимального размера (последнее в списке)
    photo: PhotoSize = message.photo[-1]
    
    await process_file(
        message=message,
        file_id=photo.file_id,
        file_name="photo.jpg",  # Telegram конвертирует фото в JPEG
        file_size=photo.file_size or 0,
        state=state
    )


@router.message(F.audio)
async def handle_audio(message: Message, state: FSMContext) -> None:
    """
    Обработчик аудиофайлов
    """
    audio: Audio = message.audio
    
    # Определяем расширение из MIME-типа или имени файла
    file_name = audio.file_name
    if not file_name:
        mime_ext_map = {
            'audio/mpeg': 'mp3',
            'audio/ogg': 'ogg',
            'audio/wav': 'wav',
            'audio/flac': 'flac',
            'audio/x-wav': 'wav',
        }
        ext = mime_ext_map.get(audio.mime_type, 'mp3')
        file_name = f"audio.{ext}"
    
    await process_file(
        message=message,
        file_id=audio.file_id,
        file_name=file_name,
        file_size=audio.file_size or 0,
        state=state
    )


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext) -> None:
    """
    Обработчик голосовых сообщений
    Telegram отправляет их в формате OGG
    """
    voice: Voice = message.voice
    
    await process_file(
        message=message,
        file_id=voice.file_id,
        file_name="voice.ogg",
        file_size=voice.file_size or 0,
        state=state
    )


@router.message(F.video)
async def handle_video(message: Message, state: FSMContext) -> None:
    """
    Обработчик видеофайлов
    """
    video: Video = message.video
    
    # Определяем расширение
    file_name = video.file_name
    if not file_name:
        mime_ext_map = {
            'video/mp4': 'mp4',
            'video/avi': 'avi',
            'video/quicktime': 'mov',
            'video/x-matroska': 'mkv',
        }
        ext = mime_ext_map.get(video.mime_type, 'mp4')
        file_name = f"video.{ext}"
    
    await process_file(
        message=message,
        file_id=video.file_id,
        file_name=file_name,
        file_size=video.file_size or 0,
        state=state
    )


@router.message(F.video_note)
async def handle_video_note(message: Message, state: FSMContext) -> None:
    """
    Обработчик видеосообщений (кружков)
    """
    video_note: VideoNote = message.video_note
    
    await process_file(
        message=message,
        file_id=video_note.file_id,
        file_name="video_note.mp4",
        file_size=video_note.file_size or 0,
        state=state
    )
