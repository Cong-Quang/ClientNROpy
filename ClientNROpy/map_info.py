# -*- coding: utf-8 -*-
"""
Mô hình MapInfo mô phỏng thông tin bản đồ và các thực thể trong C#.
"""

from typing import List, Dict, Any, TYPE_CHECKING
from .waypoint import Waypoint
from .mob import Mob
from .item_map import ItemMap
from .zone_info import ZoneInfo

if TYPE_CHECKING:
    from .char import Char


class MapInfo:
    """Thông tin toàn diện về bản đồ hiện tại và các thực thể xung quanh."""

    def __init__(self):
        self.mapID: int = -1
        self.mapName: str = ""
        self.planetID: int = -1
        self.zoneID: int = -1
        self.typeMap: int = 0
        self.waypoints: List[Waypoint] = []
        self.mobs: Dict[int, Mob] = {}
        self.chars: Dict[int, "Char"] = {}
        self.items: Dict[int, ItemMap] = {}
        self.zones: List[ZoneInfo] = []
        # NPC trong map (phục vụ AutoQuest Bò Mộng): mỗi NPC là dict
        # {status, x, y, template_id, avatar}
        self.npcs: List[Dict[str, Any]] = []

    def clear(self) -> None:
        self.waypoints.clear()
        self.mobs.clear()
        self.chars.clear()
        self.items.clear()
        self.zones.clear()
        self.npcs.clear()

    def find_npc(self, template_id: int) -> Dict[str, Any] | None:
        """Tìm NPC theo template_id (vd: 17 = Bò Mộng)."""
        for npc in self.npcs:
            if npc.get("template_id") == template_id:
                return npc
        return None

    def __repr__(self) -> str:
        return (f"<Map: {self.mapName} (ID: {self.mapID}, Khu: {self.zoneID}) | "
                f"Quái: {len(self.mobs)}, Người chơi: {len(self.chars)}, "
                f"Vật phẩm: {len(self.items)}, NPC: {len(self.npcs)}, Tổng số khu: {len(self.zones)}>")
