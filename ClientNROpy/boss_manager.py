# -*- coding: utf-8 -*-
"""
Compatibility shim for BossManager.
Toàn bộ logic theo dõi và bóc tách Boss đã được hợp nhất vào ClientNROpy.auto_manager.AutoManager.
File này giữ lại để đảm bảo tương thích ngược 100% khi import.
"""

from .auto_manager import AutoManager as BossManager
from .boss import Boss

__all__ = ["BossManager", "Boss"]
