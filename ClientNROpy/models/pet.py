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


PET_STATUS_NAMES = Pet.STATUS_NAMES

PET_ACTION_MAP = {
    "0": 0, "follow": 0, "dtheo": 0, "theo": 0, "di theo": 0, "đi theo": 0,
    "1": 1, "protect": 1, "baove": 1, "bv": 1, "bao ve": 1, "bảo vệ": 1,
    "2": 2, "attack": 2, "tancong": 2, "tc": 2, "danh": 2, "tan cong": 2, "tấn công": 2,
    "3": 3, "home": 3, "venha": 3, "nha": 3, "ve nha": 3, "về nhà": 3,
    "4": 4, "fuse": 4, "hopthe": 4, "ht": 4, "hop the": 4, "hợp thể": 4,
    "5": 5, "porata": 5, "bongtai": 5, "bt": 5, "bong tai": 5, "bông tai": 5,
}
