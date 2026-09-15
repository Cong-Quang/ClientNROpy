# -*- coding: utf-8 -*-
"""
Mô hình ItemMap mô phỏng ItemMap.cs trong C#.
"""


class ItemMap:
    """Vật phẩm rơi trên mặt đất trong bản đồ."""

    def __init__(self, itemMapID: int = 0, itemTemplateID: int = 0,
                 x: int = 0, y: int = 0, playerId: int = -1):
        self.itemMapID: int = itemMapID
        self.itemTemplateID: int = itemTemplateID
        self.x: int = x
        self.y: int = y
        self.playerId: int = playerId

    def __repr__(self) -> str:
        return f"<ItemMap ID={self.itemMapID} Template={self.itemTemplateID} Pos=({self.x},{self.y})>"
