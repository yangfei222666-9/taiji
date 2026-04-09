"""
AIOS Storage Module
异步存储管理（aiosqlite + aiosql）
"""

from .storage_manager import (
    StorageManager,
    get_storage_manager,
    close_storage_manager
)

__all__ = [
    'StorageManager',
    'get_storage_manager',
    'close_storage_manager'
]
