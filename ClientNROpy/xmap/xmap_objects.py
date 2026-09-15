# -*- coding: utf-8 -*-
"""
Định nghĩa các đối tượng và kiểu dữ liệu cho Xmap,
mô phỏng XmapObjects.cs trong Dragonboy C#.
"""

from enum import IntEnum
from typing import List, Optional


class TypeMapNext(IntEnum):
    """Phân loại hình thức chuyển map kế tiếp."""
    NONE = -1
    AutoWaypoint = 0   # Cổng dịch chuyển bản đồ tự động
    NpcMenu = 1        # Menu tương tác NPC (Trạm tàu vũ trụ, Tương lai, v.v.)
    NpcPanel = 2       # Bảng chọn map NPC
    Position = 3       # Nhảy tọa độ đặc biệt (Thần điện -> Tháp Karin, Tháp Karin -> Chân tháp)
    Capsule = 4        # Dùng Capsule bay thẳng tới map


class MapNext:
    """Đại diện cho 1 bước chuyển tiếp giữa hai map liền kề trên đồ thị."""

    def __init__(self, map_start: int, to: int, type: TypeMapNext, info: Optional[List[int]] = None):
        self.map_start: int = map_start
        self.to: int = to
        self.type: TypeMapNext = type
        self.info: List[int] = info if info is not None else []

    def __repr__(self) -> str:
        return f"<MapNext {self.map_start} -> {self.to} ({self.type.name}, info={self.info})>"


class GroupMap:
    """Đại diện cho nhóm các bản đồ thuộc cùng hành tinh hoặc phân khu."""

    def __init__(self, names: List[str], maps: List[int]):
        self.names: List[str] = names
        self.maps: List[int] = maps

    @property
    def primary_name(self) -> str:
        return self.names[0] if self.names else "Unknown"

    def __repr__(self) -> str:
        return f"<GroupMap '{self.primary_name}' maps={self.maps}>"
