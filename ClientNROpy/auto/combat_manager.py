# -*- coding: utf-8 -*-
"""
Compatibility shim for CombatManager.
Toàn bộ logic chiến đấu, AK, Tàn Sát đã được hợp nhất vào ClientNROpy.auto_manager.AutoManager.
File này giữ lại để đảm bảo tương thích ngược 100% khi import.
"""

from .auto_manager import AutoManager as CombatManager

__all__ = ["CombatManager"]
