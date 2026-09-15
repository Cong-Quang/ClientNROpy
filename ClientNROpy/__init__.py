# -*- coding: utf-8 -*-
"""
Package ClientNROpy - Môi trường mạng giả lập không đồ hoạ (Headless Client)
dành cho game Dragonboy / Ngọc Rồng Online.
Tuân thủ nguyên tắc thiết kế OOP: Mỗi file chứa đúng 1 class.
"""

import sys

# Đảm bảo console Windows hỗ trợ in Unicode tiếng Việt
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# 1. Các lớp I/O và gói tin
from .reader import myReader
from .writer import myWriter
from .message import Message

# 2. Các interfaces và luồng mạng
from .isession import ISession
from .imessage_handler import IMessageHandler
from .sender import Sender
from .message_collector import MessageCollector
from .session import Session_ME

# 3. Các mô hình thực thể (Models) - mỗi file 1 class
from .item_option import ItemOption, OPTION_TEMPLATES
from .item import Item
from .player_data import PlayerData
from .pet import Pet
from .magic_tree import MagicTree
from .waypoint import Waypoint
from .mob import Mob
from .item_map import ItemMap
from .zone_info import ZoneInfo
from .map_info import MapInfo
from .char import Char
from .chat_vip import ChatVip
from .boss import Boss
from .boss_manager import BossManager
from .boss_hunter import BossHunter
from .combat_manager import CombatManager

# 4. Service, Controller và Client cấp cao
from .service import Service
from .controller import Controller
from .client import ClientNRO


# 5. Hệ thống tìm đường Xmap
from .xmap import (
    XmapController,
    XmapData,
    XmapAlgorithm,
    XmapExecutor,
    MapNext,
    TypeMapNext,
    GroupMap,
    MAP_NAMES,
    get_map_name,
    resolve_map_id,
)

__all__ = [
    "myReader",
    "myWriter",
    "Message",
    "ISession",
    "IMessageHandler",
    "Sender",
    "MessageCollector",
    "Session_ME",
    "ItemOption",
    "OPTION_TEMPLATES",
    "Item",
    "PlayerData",
    "Pet",
    "MagicTree",
    "Waypoint",
    "Mob",
    "ItemMap",
    "ZoneInfo",
    "MapInfo",
    "Char",
    "ChatVip",
    "Boss",
    "BossManager",
    "BossHunter",
    "CombatManager",
    "Service",
    "Controller",
    "ClientNRO",
    "XmapController",
    "XmapData",
    "XmapAlgorithm",
    "XmapExecutor",
    "MapNext",
    "TypeMapNext",
    "GroupMap",
    "MAP_NAMES",
    "get_map_name",
    "resolve_map_id",
]

