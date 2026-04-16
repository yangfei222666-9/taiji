"""
AIOS Storage Module
异步存储管理（aiosqlite + aiosql）
"""

try:
    from .storage_manager import (
        StorageManager,
        get_storage_manager,
        close_storage_manager,
    )
except ImportError:
    StorageManager = None
    get_storage_manager = None
    close_storage_manager = None

__all__ = [
    'StorageManager',
    'get_storage_manager',
    'close_storage_manager',
]
