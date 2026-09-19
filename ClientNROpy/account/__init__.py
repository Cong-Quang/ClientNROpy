# -*- coding: utf-8 -*-
"""
Package quản lý tài khoản game (Account) cho ClientNROpy.
Gom nhóm các thành phần cấu hình (AccountConfig), runtime (AccountInstance)
và quản trị đa tài khoản (AccountManager) vào một thư mục chuyên biệt.
"""

from .config import AccountConfig
from .instance import AccountInstance
from .manager import (
    AccountManager,
    DEFAULT_CONFIG_PATH,
    DEFAULT_SETTINGS,
    DEFAULT_SETTINGS_PATHS,
    DEFAULT_ACCOUNTS_PATHS,
)

__all__ = [
    "AccountConfig",
    "AccountInstance",
    "AccountManager",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_SETTINGS",
    "DEFAULT_SETTINGS_PATHS",
    "DEFAULT_ACCOUNTS_PATHS",
]
