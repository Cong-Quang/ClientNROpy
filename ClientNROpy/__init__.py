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
from .auto_manager import AutoManager
from .boss_manager import BossManager
from .boss_hunter import BossHunter
from .auto_quest_bomong import AutoQuest, AutoState, QuestInfo
from .task import Task
from .auto_train_pet import AutoTrainPet, AutoTrainPetMode, AutoTrainPetAttackMode
from .auto_train_new_account import AutoTrainNewAccount

# 4. Service, Controller và Client cấp cao
from .service import Service
from .controller import Controller
from .client import ClientNRO


# 5. Hệ thống Quản trị Đa Tài khoản & Proxy
from .proxy_manager import ProxyConfig, ProxyPool, create_proxy_socket, parse_proxy
from .account_manager import AccountConfig, AccountInstance, AccountManager
from .logger import ConsoleLogger, logger, LogLevel
from .display import print_banner, print_accounts_table, print_cli_help
from .command_handler import execute_client_command, execute_multi_command
from .terminal import interactive_cli

# 6. Hệ thống tìm đường Xmap
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

# 7. Cơ sở dữ liệu trò chơi tập trung (Game Data)
from . import game_data
from .game_data import (
    ITEM_NAMES,
    ITEM_TEMPLATES,
    MOB_NAMES,
    MOB_TEMPLATES,
    NPC_NAMES,
    NPC_TEMPLATES,
    SKILL_NAMES,
    SKILL_TEMPLATES,
    get_item_name,
    get_item_info,
    get_mob_name,
    get_mob_info,
    get_npc_name,
    get_npc_info,
    get_skill_name,
    get_skill_info,
    search_items,
    search_maps,
    search_mobs,
    search_npcs,
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
    "AutoQuest",
    "AutoState",
    "QuestInfo",
    "Task",
    "AutoTrainPet",
    "AutoTrainPetMode",
    "AutoTrainPetAttackMode",
    "AutoTrainNewAccount",
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
    "game_data",
    "ITEM_NAMES",
    "ITEM_TEMPLATES",
    "MOB_NAMES",
    "MOB_TEMPLATES",
    "NPC_NAMES",
    "NPC_TEMPLATES",
    "SKILL_NAMES",
    "SKILL_TEMPLATES",
    "get_item_name",
    "get_item_info",
    "get_mob_name",
    "get_mob_info",
    "get_npc_name",
    "get_npc_info",
    "get_skill_name",
    "get_skill_info",
    "search_items",
    "search_maps",
    "search_mobs",
    "search_npcs",
]

