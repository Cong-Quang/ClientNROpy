# -*- coding: utf-8 -*-
"""
Mô hình Char mô phỏng Char.cs trong C#.
"""

from typing import Optional, List, Any, Tuple
from .pet import Pet
from .magic_tree import MagicTree
from .map_info import MapInfo
from .item import Item
from .task import Task


class Char:
    """
    Thông tin toàn diện về nhân vật:
    - Chỉ số: HP, MP, Sức mạnh, Tiềm năng, Vàng, Ngọc
    - Hành trang balo (arrItemBag), Rương đồ (arrItemBox), Trang bị trên người (arrItemBody)
    - Đệ tử (pet)
    - Cây đậu thần (magicTree)
    - Bản đồ hiện tại (mapInfo)
    """

    def __init__(self):
        self.charID: int = 0
        self.cName: str = ""
        self.ctaskId: int = 0
        self.task_name: str = ""
        self.task: Optional[Task] = None
        self.cgender: int = 0
        self.head: int = 0
        self.body: int = 0
        self.leg: int = 0
        self.bag: int = 0
        self.cPk: int = 0
        self.cTypePk: int = 0
        self.cPower: int = 0
        self.cTiemNang: int = 0
        self.nClass: int = 0
        self.cHPGoc: int = 0
        self.cMPGoc: int = 0
        self.cDamGoc: int = 0
        self.cDefGoc: int = 0
        self.cCriticalGoc: int = 0
        self.cspeed: int = 5
        self.cHP: int = 0
        self.cHPFull: int = 0
        self.cMP: int = 0
        self.cMPFull: int = 0
        self.cDamFull: int = 0
        self.cDefull: int = 0
        self.cCriticalFull: int = 0
        self.xu: int = 0
        self.luong: int = 0
        self.luongKhoa: int = 0
        self.cx: int = 0
        self.cy: int = 0
        self.cdir: int = 1
        self.statusMe: int = 1
        self.canFly: bool = True
        self.skills: List[int] = []

        # Hành trang balo, trang bị và rương đồ
        self.arrItemBody: List[Item] = []
        self.arrItemBag: List[Item] = []
        self.arrItemBox: List[Item] = []

        # Đệ tử & Đậu thần
        self.pet: Pet = Pet()
        self.magicTree: MagicTree = MagicTree()

        # Thông tin Map và Khu vực
        self.mapInfo: MapInfo = MapInfo()

        # Thông tin ngoại hình / trạng thái mở rộng
        self.clevel: int = 0
        self.cFlag: int = 0
        self.isInvisiblez: bool = False
        self.isMonkey: int = 0
        self.isPet: bool = False
        self.isMiniPet: bool = False

        # Tiêu điểm nhắm (Focus) mô phỏng Char.cs trong C#
        self.mobFocus: Optional[Any] = None
        self.charFocus: Optional[Any] = None
        self.itemFocus: Optional[Any] = None
        self.npcFocus: Optional[Any] = None
        self.skillTemplateId: int = 0

    @property
    def is_dead(self) -> bool:
        """Kiểm tra nhân vật có đang trong trạng thái chết hay không."""
        return (self.cHPFull > 0 and self.cHP <= 0) or getattr(self, "statusMe", 1) == 14 or getattr(self, "isDie", False)

    @property
    def taskMaint(self) -> Optional[Task]:
        """Alias tương thích C# cho thông tin nhiệm vụ chính."""
        return self.task

    @property
    def hp_potion(self) -> int:
        """Tổng số hạt đậu thần đang có trong hành trang balo (template_id 13-22 hoặc type 6)."""
        count = 0
        for item in self.arrItemBag:
            if item and (13 <= getattr(item, "template_id", -1) <= 22 or getattr(item, "template_type", -1) == 6):
                count += getattr(item, "quantity", 1)
        return count

    def get_first_pean_item(self) -> Optional[Item]:
        """Lấy vật phẩm đậu thần đầu tiên trong hành trang."""
        for item in self.arrItemBag:
            if item and (13 <= getattr(item, "template_id", -1) <= 22 or getattr(item, "template_type", -1) == 6):
                return item
        return None

    def distance_to(self, x: int, y: int) -> float:
        """Tính khoảng cách Euclidean từ nhân vật tới toạ độ (x, y)."""
        import math
        return math.hypot(self.cx - x, self.cy - y)


    def focus_mob(self, mob: Any) -> None:
        """Nhắm mục tiêu vào quái vật."""
        self.mobFocus = mob
        self.charFocus = None
        self.itemFocus = None
        self.npcFocus = None

    def focus_char(self, target_char: Any) -> None:
        """Nhắm mục tiêu vào người chơi khác."""
        self.charFocus = target_char
        self.mobFocus = None
        self.itemFocus = None
        self.npcFocus = None

    def focus_item(self, item: Any) -> None:
        """Nhắm mục tiêu vào vật phẩm trên đất."""
        self.itemFocus = item
        self.mobFocus = None
        self.charFocus = None
        self.npcFocus = None

    def clear_focus(self) -> None:
        """Hủy toàn bộ mục tiêu đang nhắm."""
        self.mobFocus = None
        self.charFocus = None
        self.itemFocus = None
        self.npcFocus = None

    def get_focused_target(self):
        """Lấy thông tin đối tượng đang focus hiện tại."""
        if self.mobFocus:
            return ("mob", self.mobFocus)
        if self.charFocus:
            return ("char", self.charFocus)
        if self.itemFocus:
            return ("item", self.itemFocus)
        if self.npcFocus:
            return ("npc", self.npcFocus)
        return (None, None)


    _myCharz: Optional["Char"] = None

    @classmethod
    def myCharz(cls) -> "Char":
        """Singleton đối tượng nhân vật chính tương tự Char.myCharz() trong C#."""
        if cls._myCharz is None:
            cls._myCharz = Char()
        return cls._myCharz

    @classmethod
    def myPetz(cls) -> Pet:
        """Singleton đối tượng đệ tử tương tự Char.myPetz() trong C#."""
        return cls.myCharz().pet

    @classmethod
    def clearMyChar(cls) -> None:
        """Reset đối tượng nhân vật khi đăng xuất tương tự GameCanvas.doResetToLoginScr()."""
        cls._myCharz = None

    def __repr__(self) -> str:
        return (f"<Char ID={self.charID} Name='{self.cName}' "
                f"HP={self.cHP:,}/{self.cHPFull:,} Power={self.cPower:,} "
                f"Vàng={self.xu:,} Ngọc={self.luong:,} Balo={len(self.arrItemBag)} món, "
                f"Rương={len(self.arrItemBox)} món>")
