# -*- coding: utf-8 -*-
"""
Compatibility shim for AutoQuest.
Toàn bộ logic làm nhiệm vụ Bò Mộng đã được hợp nhất vào ClientNROpy.auto_manager.AutoManager.
File này giữ lại để đảm bảo tương thích ngược 100% khi import.
"""

from .auto_manager import (
    AutoManager as AutoQuest,
    AutoQuestState as AutoState,
    QuestInfo,
    MOB_LOCATION_DATA,
    BO_MONG_MAP_ID,
    BO_MONG_NPC_TEMPLATE_ID,
)

__all__ = [
    "AutoQuest",
    "AutoState",
    "QuestInfo",
    "MOB_LOCATION_DATA",
    "BO_MONG_MAP_ID",
    "BO_MONG_NPC_TEMPLATE_ID",
]
