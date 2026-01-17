"""
FileConverter Bot - Инлайн-клавиатуры
Модуль для генерации клавиатур с форматами конвертации
"""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


# Маппинг расширений к типам файлов
FILE_TYPE_MAP = {
    # Изображения
    'jpg': 'image', 'jpeg': 'image', 'png': 'image', 
    'webp': 'image', 'bmp': 'image', 'heic': 'image',
    # Документы
    'docx': 'document', 'doc': 'document', 'pdf': 'pdf',
    'txt': 'text', 'rtf': 'document', 'odt': 'document',
    # Таблицы
    'xlsx': 'spreadsheet', 'xls': 'spreadsheet', 'csv': 'spreadsheet',
    # Аудио
    'mp3': 'audio', 'ogg': 'audio', 'wav': 'audio', 
    'flac': 'audio', 'oga': 'audio',
    # Видео
    'mp4': 'video', 'avi': 'video', 'mov': 'video', 'mkv': 'video',
}

# Доступные форматы конвертации для каждого типа
CONVERSION_OPTIONS = {
    'image': {
        'formats': ['jpg', 'png', 'webp', 'bmp', 'pdf'],
        'emoji': '🖼️',
        'names': {
            'jpg': 'JPEG', 'png': 'PNG', 'webp': 'WebP', 
            'bmp': 'BMP', 'pdf': 'PDF'
        }
    },
    'document': {
        'formats': ['pdf', 'txt', 'docx'],
        'emoji': '📄',
        'names': {
            'pdf': 'PDF', 'txt': 'TXT', 'docx': 'DOCX'
        }
    },
    'pdf': {
        'formats': ['txt', 'docx'],
        'emoji': '📑',
        'names': {
            'txt': 'TXT', 'docx': 'DOCX'
        }
    },
    'text': {
        'formats': ['pdf', 'docx'],
        'emoji': '📝',
        'names': {
            'pdf': 'PDF', 'docx': 'DOCX'
        }
    },
    'spreadsheet': {
        'formats': ['csv', 'xlsx'],
        'emoji': '📊',
        'names': {
            'csv': 'CSV', 'xlsx': 'Excel XLSX'
        }
    },
    'audio': {
        'formats': ['mp3', 'ogg', 'wav', 'flac'],
        'emoji': '🎵',
        'names': {
            'mp3': 'MP3', 'ogg': 'OGG', 'wav': 'WAV', 'flac': 'FLAC'
        }
    },
    'video': {
        'formats': ['mp4', 'avi', 'mkv'],
        'emoji': '🎬',
        'names': {
            'mp4': 'MP4', 'avi': 'AVI', 'mkv': 'MKV'
        }
    }
}


def get_file_type(extension: str) -> str | None:
    """
    Определяет тип файла по расширению
    
    Args:
        extension: Расширение файла (без точки, в нижнем регистре)
    
    Returns:
        Тип файла или None если не поддерживается
    """
    return FILE_TYPE_MAP.get(extension.lower())


def get_supported_extensions() -> list[str]:
    """
    Возвращает список всех поддерживаемых расширений
    
    Returns:
        Список поддерживаемых расширений
    """
    return list(FILE_TYPE_MAP.keys())


def create_format_keyboard(
    file_extension: str, 
    file_id: str
) -> InlineKeyboardMarkup | None:
    """
    Создаёт инлайн-клавиатуру с доступными форматами для конвертации
    
    Args:
        file_extension: Расширение исходного файла
        file_id: ID файла в Telegram для callback_data
    
    Returns:
        Инлайн-клавиатура или None если формат не поддерживается
    """
    ext = file_extension.lower().lstrip('.')
    file_type = get_file_type(ext)
    
    if not file_type or file_type not in CONVERSION_OPTIONS:
        return None
    
    options = CONVERSION_OPTIONS[file_type]
    builder = InlineKeyboardBuilder()
    
    # Получаем доступные форматы (исключаем исходный)
    # Также исключаем jpeg если исходный jpg (и наоборот) - это алиасы
    exclude_formats = {ext}
    if ext in ('jpg', 'jpeg'):
        exclude_formats = {'jpg', 'jpeg'}
    
    available_formats = [
        fmt for fmt in options['formats'] 
        if fmt not in exclude_formats
    ]
    
    # Создаём кнопки для каждого формата
    for target_format in available_formats:
        emoji = options['emoji']
        name = options['names'].get(target_format, target_format.upper())
        
        # callback_data формат: cvt:{target_format}
        # file_id хранится в FSM-состоянии
        callback_data = f"cvt:{target_format}"
        
        builder.add(InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=callback_data
        ))
    
    # Добавляем кнопку отмены
    builder.add(InlineKeyboardButton(
        text="❌ Отмена",
        callback_data="cancel"
    ))
    
    # Располагаем кнопки по 2 в ряд, кнопку отмены - отдельно
    builder.adjust(2, 2, 2, 1)
    
    return builder.as_markup()


def get_conversion_info(file_extension: str) -> dict | None:
    """
    Получает информацию о возможных конвертациях для файла
    
    Args:
        file_extension: Расширение файла
    
    Returns:
        Словарь с информацией или None если не поддерживается
    """
    ext = file_extension.lower().lstrip('.')
    file_type = get_file_type(ext)
    
    if not file_type or file_type not in CONVERSION_OPTIONS:
        return None
    
    options = CONVERSION_OPTIONS[file_type]
    available = [fmt for fmt in options['formats'] if fmt != ext]
    
    return {
        'type': file_type,
        'emoji': options['emoji'],
        'available_formats': available,
        'format_names': {fmt: options['names'].get(fmt, fmt.upper()) for fmt in available}
    }
