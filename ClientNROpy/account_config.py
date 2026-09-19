# -*- coding: utf-8 -*-
"""
Module wrapper giữ tương thích ngược cho AccountConfig.
Toàn bộ logic chính đã được chuyển vào ClientNROpy/account/config.py.
"""

from .account.config import AccountConfig

__all__ = ["AccountConfig"]
