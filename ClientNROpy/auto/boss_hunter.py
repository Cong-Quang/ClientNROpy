# -*- coding: utf-8 -*-
"""
Compatibility shim for BossHunter.
Toàn bộ logic tự động hóa đã được hợp nhất vào ClientNROpy.auto_manager.AutoManager.
File này giữ lại để đảm bảo tương thích ngược 100% khi import.
"""

from .auto_manager import AutoManager as BossHunter
from ..models.boss import Boss

__all__ = ["BossHunter", "Boss"]
