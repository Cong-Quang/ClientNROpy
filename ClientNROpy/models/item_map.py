# -*- coding: utf-8 -*-
"""
Mô hình ItemMap mô phỏng ItemMap.cs trong C#.
"""


class ItemMap:
    """Vật phẩm rơi trên mặt đất trong bản đồ."""

    def __init__(
        self,
        itemMapID: int = 0,
        itemTemplateID: int = 0,
        x: int = 0,
        y: int = 0,
        playerId: int = -1,
        **kwargs,
    ):
        self.itemMapID: int = itemMapID
        self.itemTemplateID: int = kwargs.get("template_id", itemTemplateID)
        self.x: int = x
        self.y: int = y
        self.playerId: int = kwargs.get("playerID", playerId)

    @property
    def template_id(self) -> int:
        """Thuộc tính alias cho itemTemplateID."""
        return self.itemTemplateID

    @template_id.setter
    def template_id(self, val: int) -> None:
        self.itemTemplateID = val

    def __repr__(self) -> str:
        return f"<ItemMap ID={self.itemMapID} Template={self.itemTemplateID} Pos=({self.x},{self.y})>"
