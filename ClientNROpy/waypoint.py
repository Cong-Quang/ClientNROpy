# -*- coding: utf-8 -*-
"""
Mô hình Waypoint mô phỏng Waypoint.cs trong C#.
"""


class Waypoint:
    """Cổng dịch chuyển / Waypoint qua map khác."""

    def __init__(self, minX: int, minY: int, maxX: int, maxY: int,
                 isEnter: bool, isOffline: bool, name: str):
        self.minX: int = minX
        self.minY: int = minY
        self.maxX: int = maxX
        self.maxY: int = maxY
        self.isEnter: bool = isEnter
        self.isOffline: bool = isOffline
        self.name: str = name

    def __repr__(self) -> str:
        return f"<Waypoint '{self.name}' Pos=({self.minX},{self.minY})-({self.maxX},{self.maxY})>"
