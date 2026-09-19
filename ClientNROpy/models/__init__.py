# -*- coding: utf-8 -*-
"""
Package models cho ClientNROpy.
Chứa toàn bộ các mô hình thực thể trong thế giới game Dragonboy/NRO:
Nhân vật (Char), Đệ tử (Pet), Quái (Mob), Boss, Vật phẩm (Item/ItemOption),
Bản đồ (MapInfo/ZoneInfo/Waypoint), Đậu thần (MagicTree), Nhiệm vụ (Task), ChatVip.
"""

from .char import Char
from .pet import Pet
from .mob import Mob
from .boss import Boss
from .item import Item
from .item_option import ItemOption, OPTION_TEMPLATES
from .item_map import ItemMap
from .magic_tree import MagicTree
from .map_info import MapInfo
from .zone_info import ZoneInfo
from .player_data import PlayerData
from .waypoint import Waypoint
from .task import Task, clean_task_name
from .chat_vip import ChatVip

__all__ = [
    "Char",
    "Pet",
    "Mob",
    "Boss",
    "Item",
    "ItemOption",
    "OPTION_TEMPLATES",
    "ItemMap",
    "MagicTree",
    "MapInfo",
    "ZoneInfo",
    "PlayerData",
    "Waypoint",
    "Task",
    "clean_task_name",
    "ChatVip",
]
