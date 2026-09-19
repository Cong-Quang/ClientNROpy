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

# 1. Giao thức mạng, I/O gói tin và Session (Network Package)
from .network import (
    myReader,
    myWriter,
    Message,
    ISession,
    IMessageHandler,
    Sender,
    MessageCollector,
    Session_ME,
    ProxyConfig,
    ProxyPool,
    create_proxy_socket,
    parse_proxy,
)

# 2. Các mô hình thực thể và thế giới Game (Models Package)
from .models import (
    ItemOption,
    OPTION_TEMPLATES,
    Item,
    PlayerData,
    Pet,
    MagicTree,
    Waypoint,
    Mob,
    ItemMap,
    ZoneInfo,
    MapInfo,
    Char,
    ChatVip,
    Boss,
    Task,
)

# 3. Hệ thống Tự động hóa và Săn Boss (Auto Package)
from .auto import (
    AutoManager,
    BossManager,
    BossHunter,
    CombatManager,
    AutoReviveManager,
    AutoUseItemManager,
    AutoQuest,
    AutoState,
    QuestInfo,
    AutoTrainPet,
    AutoTrainPetMode,
    AutoTrainPetAttackMode,
    AutoTrainNewAccount,
)

# 4. Service, Controller và Client cấp cao
from .service import Service
from .controller import Controller
from .client import ClientNRO

# 5. Hệ thống Quản trị Đa Tài khoản (Account Package)
from .account import AccountConfig, AccountInstance, AccountManager
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
    "AutoReviveManager",
    "AutoUseItemManager",
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
    "AccountConfig",
    "AccountInstance",
    "AccountManager",
    "ProxyConfig",
    "ProxyPool",
]

