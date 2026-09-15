# -*- coding: utf-8 -*-
"""
Mô hình MagicTree mô phỏng MagicTree.cs trong C#.
"""


class MagicTree:
    """Thông tin Cây Đậu Thần (MagicTree) tại nhà."""

    def __init__(self):
        self.id: int = 0
        self.name: str = "Đậu thần"
        self.x: int = 0
        self.y: int = 0
        self.level: int = 1
        self.currPeas: int = 0
        self.maxPeas: int = 0
        self.strInfo: str = ""
        self.seconds: int = 0
        self.isUpdate: bool = False

    def __repr__(self) -> str:
        return (f"<MagicTree Cấp={self.level} Đậu={self.currPeas}/{self.maxPeas} "
                f"Thời gian chín={self.seconds}s>")
