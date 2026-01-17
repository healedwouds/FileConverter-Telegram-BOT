"""
FileConverter Bot - Логика конвертации файлов
Модуль содержит функции для конвертации различных типов файлов
"""

import os
import io
import asyncio
import logging
from pathlib import Path
from typing import BinaryIO

import aiofiles
from PIL import Image
import pillow_heif
import ffmpeg
from pydub import AudioSegment
import pypandoc
import pandas as pd

# Регистрируем поддержку HEIC
pillow_heif.register_heif_opener()

logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Исключение при ошибке конвертации"""
    pass


async def run_in_executor(func, *args, **kwargs):
    """
    Запускает синхронную функцию в отдельном потоке
    
    Args:
        func: Функция для выполнения
        *args: Позиционные аргументы
        **kwargs: Именованные аргументы
    
    Returns:
        Результат выполнения функции
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, 
        lambda: func(*args, **kwargs)
    )


async def convert_image(
    input_path: str, 
    output_path: str, 
    target_format: str
) -> str:
    """
    Конвертирует изображение в указанный формат
    
    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения результата
        target_format: Целевой формат (jpg, png, webp, bmp, pdf)
    
    Returns:
        Путь к сконвертированному файлу
    
    Raises:
        ConversionError: При ошибке конвертации
    """
    try:
        def _convert():
            with Image.open(input_path) as img:
                # Конвертируем в RGB если нужно (для JPEG и PDF)
                if target_format.lower() in ('jpg', 'jpeg', 'pdf'):
                    if img.mode in ('RGBA', 'P', 'LA'):
                        # Создаём белый фон для прозрачности
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if img.mode == 'P':
                            img = img.convert('RGBA')
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        img = background
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                
                # Маппинг форматов для Pillow
                format_map = {
                    'jpg': 'JPEG',
                    'jpeg': 'JPEG',
                    'png': 'PNG',
                    'webp': 'WEBP',
                    'bmp': 'BMP',
                    'pdf': 'PDF'
                }
                
                pil_format = format_map.get(target_format.lower(), target_format.upper())
                
                # Сохраняем с оптимальным качеством
                save_kwargs = {}
                if pil_format == 'JPEG':
                    save_kwargs = {'quality': 95, 'optimize': True}
                elif pil_format == 'PNG':
                    save_kwargs = {'optimize': True}
                elif pil_format == 'WEBP':
                    save_kwargs = {'quality': 90}
                
                img.save(output_path, format=pil_format, **save_kwargs)
                return output_path
        
        result = await run_in_executor(_convert)
        logger.info(f"Изображение сконвертировано: {input_path} -> {output_path}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка конвертации изображения: {e}")
        raise ConversionError(f"Не удалось конвертировать изображение: {e}")


async def convert_audio(
    input_path: str, 
    output_path: str, 
    target_format: str
) -> str:
    """
    Конвертирует аудиофайл в указанный формат
    
    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения результата
        target_format: Целевой формат (mp3, ogg, wav, flac)
    
    Returns:
        Путь к сконвертированному файлу
    
    Raises:
        ConversionError: При ошибке конвертации
    """
    try:
        def _convert():
            # Определяем формат входного файла
            input_ext = Path(input_path).suffix.lower().lstrip('.')
            
            # Загружаем аудио
            audio = AudioSegment.from_file(input_path, format=input_ext)
            
            # Параметры экспорта для разных форматов
            export_kwargs = {}
            if target_format == 'mp3':
                export_kwargs = {'format': 'mp3', 'bitrate': '320k'}
            elif target_format == 'ogg':
                export_kwargs = {'format': 'ogg', 'codec': 'libvorbis'}
            elif target_format == 'wav':
                export_kwargs = {'format': 'wav'}
            elif target_format == 'flac':
                export_kwargs = {'format': 'flac'}
            else:
                export_kwargs = {'format': target_format}
            
            audio.export(output_path, **export_kwargs)
            return output_path
        
        result = await run_in_executor(_convert)
        logger.info(f"Аудио сконвертировано: {input_path} -> {output_path}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка конвертации аудио: {e}")
        raise ConversionError(f"Не удалось конвертировать аудио: {e}")


async def convert_video(
    input_path: str, 
    output_path: str, 
    target_format: str
) -> str:
    """
    Конвертирует видеофайл в указанный формат
    
    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения результата
        target_format: Целевой формат (mp4, avi, mkv)
    
    Returns:
        Путь к сконвертированному файлу
    
    Raises:
        ConversionError: При ошибке конвертации
    """
    try:
        def _convert():
            # Настройки кодеков для разных форматов
            codec_settings = {
                'mp4': {'vcodec': 'libx264', 'acodec': 'aac'},
                'avi': {'vcodec': 'mpeg4', 'acodec': 'mp3'},
                'mkv': {'vcodec': 'libx264', 'acodec': 'aac'},
            }
            
            settings = codec_settings.get(target_format, {'vcodec': 'copy', 'acodec': 'copy'})
            
            # Запускаем конвертацию через ffmpeg
            stream = ffmpeg.input(input_path)
            stream = ffmpeg.output(
                stream, 
                output_path,
                vcodec=settings['vcodec'],
                acodec=settings['acodec'],
                **{'y': None}  # Перезаписывать без вопросов
            )
            
            ffmpeg.run(stream, capture_stdout=True, capture_stderr=True)
            return output_path
        
        result = await run_in_executor(_convert)
        logger.info(f"Видео сконвертировано: {input_path} -> {output_path}")
        return result
        
    except ffmpeg.Error as e:
        logger.error(f"Ошибка ffmpeg: {e.stderr.decode() if e.stderr else str(e)}")
        raise ConversionError(f"Не удалось конвертировать видео: ошибка ffmpeg")
    except Exception as e:
        logger.error(f"Ошибка конвертации видео: {e}")
        raise ConversionError(f"Не удалось конвертировать видео: {e}")


async def convert_document(
    input_path: str, 
    output_path: str, 
    target_format: str
) -> str:
    """
    Конвертирует документ в указанный формат через Pandoc
    
    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения результата
        target_format: Целевой формат (pdf, txt, docx)
    
    Returns:
        Путь к сконвертированному файлу
    
    Raises:
        ConversionError: При ошибке конвертации
    """
    try:
        def _convert():
            # Маппинг форматов для Pandoc
            pandoc_format_map = {
                'docx': 'docx',
                'doc': 'doc',
                'pdf': 'pdf',
                'txt': 'plain',
                'rtf': 'rtf',
                'odt': 'odt',
            }
            
            input_ext = Path(input_path).suffix.lower().lstrip('.')
            input_format = pandoc_format_map.get(input_ext, input_ext)
            output_format = pandoc_format_map.get(target_format, target_format)
            
            # Для PDF нужен дополнительный параметр
            extra_args = []
            if target_format == 'pdf':
                extra_args = ['--pdf-engine=xelatex']
            
            pypandoc.convert_file(
                input_path,
                output_format,
                outputfile=output_path,
                extra_args=extra_args if extra_args else None
            )
            return output_path
        
        result = await run_in_executor(_convert)
        logger.info(f"Документ сконвертирован: {input_path} -> {output_path}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка конвертации документа: {e}")
        raise ConversionError(f"Не удалось конвертировать документ: {e}")


async def convert_spreadsheet(
    input_path: str, 
    output_path: str, 
    target_format: str
) -> str:
    """
    Конвертирует таблицу (Excel/CSV) в указанный формат
    
    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения результата
        target_format: Целевой формат (csv, xlsx)
    
    Returns:
        Путь к сконвертированному файлу
    
    Raises:
        ConversionError: При ошибке конвертации
    """
    try:
        def _convert():
            input_ext = Path(input_path).suffix.lower().lstrip('.')
            
            # Читаем входной файл
            if input_ext in ('xlsx', 'xls'):
                df = pd.read_excel(input_path)
            elif input_ext == 'csv':
                # Пробуем разные кодировки
                for encoding in ['utf-8', 'cp1251', 'latin-1']:
                    try:
                        df = pd.read_csv(input_path, encoding=encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    df = pd.read_csv(input_path, encoding='utf-8', errors='ignore')
            else:
                raise ConversionError(f"Неподдерживаемый формат таблицы: {input_ext}")
            
            # Сохраняем в целевой формат
            if target_format == 'csv':
                df.to_csv(output_path, index=False, encoding='utf-8')
            elif target_format == 'xlsx':
                df.to_excel(output_path, index=False, engine='openpyxl')
            else:
                raise ConversionError(f"Неподдерживаемый целевой формат: {target_format}")
            
            return output_path
        
        result = await run_in_executor(_convert)
        logger.info(f"Таблица сконвертирована: {input_path} -> {output_path}")
        return result
        
    except Exception as e:
        logger.error(f"Ошибка конвертации таблицы: {e}")
        raise ConversionError(f"Не удалось конвертировать таблицу: {e}")


async def convert_file(
    input_path: str, 
    output_path: str, 
    source_format: str,
    target_format: str
) -> str:
    """
    Универсальная функция конвертации файла
    Определяет тип файла и вызывает соответствующий конвертер
    
    Args:
        input_path: Путь к исходному файлу
        output_path: Путь для сохранения результата
        source_format: Исходный формат файла
        target_format: Целевой формат
    
    Returns:
        Путь к сконвертированному файлу
    
    Raises:
        ConversionError: При ошибке конвертации
    """
    from app.keyboards.inline import get_file_type
    
    file_type = get_file_type(source_format)
    
    if file_type == 'image':
        return await convert_image(input_path, output_path, target_format)
    elif file_type == 'audio':
        return await convert_audio(input_path, output_path, target_format)
    elif file_type == 'video':
        return await convert_video(input_path, output_path, target_format)
    elif file_type in ('document', 'pdf', 'text'):
        return await convert_document(input_path, output_path, target_format)
    elif file_type == 'spreadsheet':
        return await convert_spreadsheet(input_path, output_path, target_format)
    else:
        raise ConversionError(f"Неподдерживаемый тип файла: {source_format}")


async def save_file_from_bytes(data: bytes, path: str) -> str:
    """
    Сохраняет байты в файл асинхронно
    
    Args:
        data: Данные для сохранения
        path: Путь к файлу
    
    Returns:
        Путь к сохранённому файлу
    """
    async with aiofiles.open(path, 'wb') as f:
        await f.write(data)
    return path


async def read_file_bytes(path: str) -> bytes:
    """
    Читает файл асинхронно
    
    Args:
        path: Путь к файлу
    
    Returns:
        Содержимое файла
    """
    async with aiofiles.open(path, 'rb') as f:
        return await f.read()


async def cleanup_files(*paths: str) -> None:
    """
    Удаляет временные файлы
    
    Args:
        *paths: Пути к файлам для удаления
    """
    for path in paths:
        try:
            if os.path.exists(path):
                os.remove(path)
                logger.debug(f"Удалён временный файл: {path}")
        except Exception as e:
            logger.warning(f"Не удалось удалить файл {path}: {e}")
