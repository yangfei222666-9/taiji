"""
Self-Improving Loop - Core Module

让 AI Agent 自动进化的完整闭环系统
"""

__version__ = "0.1.0"
__author__ = "Self-Improving Loop Contributors"

from .core import SelfImprovingLoop
from .rollback import AutoRollback
from .threshold import AdaptiveThreshold
from .notifier import TelegramNotifier

__all__ = [
    "SelfImprovingLoop",
    "AutoRollback",
    "AdaptiveThreshold",
    "TelegramNotifier",
]
