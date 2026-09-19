# -*- coding: utf-8 -*-
# Wrapper tương thích ngược chuyển tiếp sang auto/boss_manager.py
from .auto.boss_manager import BossManager
from .models.boss import Boss

__all__ = ["BossManager", "Boss"]
