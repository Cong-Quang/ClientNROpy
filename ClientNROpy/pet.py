# -*- coding: utf-8 -*-
"""
Mô hình Pet mô phỏng Pet / Đệ tử trong C#.
"""

from typing import List
from .item import Item


class Pet:
    """Thông tin Pet / Đệ tử của nhân vật (Char.myPetz)."""

    STATUS_NAMES = {
        0: "Đi theo",
        1: "Bảo vệ",
        2: "Tấn công",
        3: "Về nhà",
        4: "Hợp thể",
        5: "Hợp thể Porata",
    }

    def __init__(self):
        self.havePet: bool = False
        self.head: int = 0
        self.cName: str = ""
        self.currStrLevel: str = ""
        self.cHP: int = 0
        self.cHPFull: int = 0
        self.cMP: int = 0
        self.cMPFull: int = 0
        self.cDamFull: int = 0
        self.cDefull: int = 0
        self.cCriticalFull: int = 0
        self.cPower: int = 0
        self.cTiemNang: int = 0
        self.petStatus: int = 0
        self.cStamina: int = 0
        self.cMaxStamina: int = 0
        self.arrItemBody: List[Item] = []
        self.arrPetSkill: List[int] = []

    @property
    def statusName(self) -> str:
        return self.STATUS_NAMES.get(self.petStatus, f"Trạng thái {self.petStatus}")

    def __repr__(self) -> str:
        if not self.havePet:
            return "<Pet: Chưa có đệ tử>"
        return (f"<Pet Name='{self.cName}' Status='{self.statusName}' "
                f"HP={self.cHP:,}/{self.cHPFull:,} Dam={self.cDamFull:,} Power={self.cPower:,}>")
