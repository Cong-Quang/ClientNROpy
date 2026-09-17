# -*- coding: utf-8 -*-
"""
Compatibility shim for AutoReviveManager.
Toàn bộ logic tự động hồi sinh đã được hợp nhất vào ClientNROpy.auto_manager.AutoManager.
File này giữ lại để đảm bảo tương thích ngược 100% khi import.
"""

from .auto_manager import AutoManager as AutoReviveManager

__all__ = ["AutoReviveManager"]
