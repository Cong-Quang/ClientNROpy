# -*- coding: utf-8 -*-
"""
Mô hình Item mô phỏng Item.cs trong C#.
"""

from typing import List
from .item_option import ItemOption


class Item:
    """Vật phẩm trang bị, vật phẩm hành trang balo hoặc rương đồ."""

    def __init__(self, template_id: int = -1, quantity: int = 1,
                 info: str = "", content: str = "", index_ui: int = 0):
        self.template_id: int = template_id
        self.quantity: int = quantity
        self.info: str = info
        self.content: str = content
        self.index_ui: int = index_ui
        self.options: List[ItemOption] = []

    def addOption(self, option_id: int, param: int) -> None:
        self.options.append(ItemOption(option_id, param))

    def __repr__(self) -> str:
        opt_str = ", ".join([opt.getText() for opt in self.options])
        if opt_str:
            return f"<Item ID={self.template_id} x{self.quantity} [{opt_str}]>"
        return f"<Item ID={self.template_id} x{self.quantity}>"
