# -*- coding: utf-8 -*-
"""
Mô hình MapInfo mô phỏng thông tin bản đồ và các thực thể trong C#.
"""

from typing import List, Dict, Any, TYPE_CHECKING, Optional, Union
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

    def find_npc(self, template_id: int) -> Optional[Dict[str, Any]]:
        """Tìm NPC theo template_id (vd: 17 = Bò Mộng)."""
        for npc in self.npcs:
            if npc.get("template_id") == template_id:
                return npc
        return None

    def find_mob(self, query: Optional[Union[int, str]] = None, from_x: Optional[int] = None, from_y: Optional[int] = None) -> Optional[Mob]:
        """Tìm quái vật trong map theo mobId, templateId, tên hoặc khoảng cách gần nhất."""
        import math
        alive_mobs = [m for m in self.mobs.values() if getattr(m, "status", 0) not in (0, 1) and getattr(m, "hp", 0) > 0]
        if not alive_mobs:
            return None

        if query is None or str(query).strip() == "":
            if from_x is not None and from_y is not None:
                return min(alive_mobs, key=lambda m: math.hypot(from_x - m.x, from_y - m.y))
            return alive_mobs[0]

        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            val = int(query)
            for m in alive_mobs:
                if m.mobId == val or m.templateId == val:
                    return m
            return None

        q_str = str(query).lower()
        for m in alive_mobs:
            t_name = getattr(m, "template_name", "")
            if q_str in t_name.lower():
                return m
        return alive_mobs[0]

    def find_char(self, query: Optional[Union[int, str]] = None, exclude_char_id: Optional[int] = None, from_x: Optional[int] = None, from_y: Optional[int] = None) -> Optional["Char"]:
        """Tìm người chơi trong map theo charID, tên hoặc khoảng cách gần nhất."""
        import math
        candidates = [c for c in self.chars.values() if exclude_char_id is None or c.charID != exclude_char_id]
        if not candidates:
            return None

        if query is None or str(query).strip() == "":
            if from_x is not None and from_y is not None:
                return min(candidates, key=lambda c: math.hypot(from_x - c.cx, from_y - c.cy))
            return candidates[0]

        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            val = int(query)
            for c in candidates:
                if c.charID == val:
                    return c
            return None

        q_str = str(query).lower()
        for c in candidates:
            if q_str in c.cName.lower():
                return c
        return None

    def find_item(self, query: Optional[Union[int, str]] = None, from_x: Optional[int] = None, from_y: Optional[int] = None) -> Optional[ItemMap]:
        """Tìm vật phẩm rơi dưới đất theo itemMapID, template_id hoặc khoảng cách gần nhất."""
        import math
        items = list(self.items.values())
        if not items:
            return None

        if query is None or str(query).strip() == "":
            if from_x is not None and from_y is not None:
                return min(items, key=lambda it: math.hypot(from_x - it.x, from_y - it.y))
            return items[0]

        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            val = int(query)
            for it in items:
                if it.itemMapID == val or it.template_id == val:
                    return it
            return None
        return None

    def get_least_populated_zone(self) -> Optional[int]:
        """Lấy zoneId có ít người chơi nhất và chưa đầy."""
        if not self.zones:
            return None
        valid = [z for z in self.zones if getattr(z, "numPlayer", 0) < getattr(z, "maxPlayer", 15)]
        target_list = valid if valid else list(self.zones)
        target_list.sort(key=lambda z: getattr(z, "numPlayer", 0))
        return getattr(target_list[0], "zoneId", None) if target_list else None


    def __repr__(self) -> str:
        npc_ids = [npc.get("template_id") for npc in self.npcs]
        return (f"<Map: {self.mapName} (ID: {self.mapID}, Khu: {self.zoneID}) | "
                f"Quái: {len(self.mobs)}, Người chơi: {len(self.chars)}, "
                f"Vật phẩm: {len(self.items)}, NPC: {len(self.npcs)} {npc_ids}, Tổng số khu: {len(self.zones)}>")
