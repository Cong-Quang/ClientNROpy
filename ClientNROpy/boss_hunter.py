# -*- coding: utf-8 -*-
# Wrapper tương thích ngược chuyển tiếp sang auto/boss_hunter.py
from .auto.boss_hunter import BossHunter
from .models.boss import Boss

__all__ = ["BossHunter", "Boss"]
