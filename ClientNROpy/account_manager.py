# -*- coding: utf-8 -*-
"""
Module wrapper giữ tương thích ngược cho AccountManager.
Toàn bộ logic chính đã được chuyển vào package ClientNROpy/account/.
"""

from .account import (
    AccountConfig,
    AccountInstance,
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
