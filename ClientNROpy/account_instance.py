# -*- coding: utf-8 -*-
"""
Module wrapper giữ tương thích ngược cho AccountInstance.
Toàn bộ logic chính đã được chuyển vào ClientNROpy/account/instance.py.
"""

from .account.instance import AccountInstance

__all__ = ["AccountInstance"]
