# -*- coding: utf-8 -*-
"""
Mô hình ZoneInfo mô phỏng thông tin khu vực (Zone) trong C#.
"""


class ZoneInfo:
    """Thông tin một khu vực trong bản đồ (Zone)."""

    def __init__(self, zoneId: int = 0, numPlayer: int = 0, maxPlayer: int = 0, pts: int = 0):
        self.zoneId: int = zoneId
        self.numPlayer: int = numPlayer
        self.maxPlayer: int = maxPlayer
        self.pts: int = pts

    @property
    def status(self) -> str:
        if self.numPlayer >= self.maxPlayer:
            return "Đầy"
        if self.numPlayer >= self.maxPlayer * 0.7:
            return "Đông"
        return "Vắng"

    def __repr__(self) -> str:
        return f"<Khu {self.zoneId}: {self.numPlayer}/{self.maxPlayer} ({self.status})>"
