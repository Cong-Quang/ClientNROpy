# -*- coding: utf-8 -*-
"""
Mô hình Mob mô phỏng Mob.cs trong C#.
"""


class Mob:
    """Quái vật xuất hiện trong bản đồ."""

    def __init__(self, mobId: int = 0, templateId: int = 0, hp: int = 0,
                 maxHp: int = 0, x: int = 0, y: int = 0, status: int = 0, isBoss: bool = False):
        self.mobId: int = mobId
        self.templateId: int = templateId
        self.hp: int = hp
        self.maxHp: int = maxHp
        self.x: int = x
        self.y: int = y
        self.status: int = status
        self.isBoss: bool = isBoss

    def __repr__(self) -> str:
        return f"<Mob ID={self.mobId} Type={self.templateId} HP={self.hp:,}/{self.maxHp:,} Pos=({self.x},{self.y})>"
