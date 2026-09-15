# -*- coding: utf-8 -*-
"""
Mô hình PlayerData mô phỏng PlayerData.cs trong C#.
"""


class PlayerData:
    """Thông tin nhân vật trong màn hình chọn nhân vật (ChooseCharScr)."""

    def __init__(self, playerID: int = 0, name: str = "", head: int = 0,
                 body: int = 0, leg: int = 0, ppoint: int = 0):
        self.playerID: int = playerID
        self.name: str = name
        self.head: int = head
        self.body: int = body
        self.leg: int = leg
        self.ppoint: int = ppoint

    def __repr__(self) -> str:
        return f"<PlayerData ID={self.playerID} Name='{self.name}' Power={self.ppoint:,}>"
