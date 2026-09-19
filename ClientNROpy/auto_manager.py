# -*- coding: utf-8 -*-
# Wrapper tương thích ngược chuyển tiếp sang auto/auto_manager.py
from .auto.auto_manager import (
    AutoManager,
    QuestInfo,
    AutoQuestState,
    MOB_LOCATION_DATA,
    BO_MONG_MAP_ID,
    BO_MONG_NPC_TEMPLATE_ID,
    NPC_INTERACT_DISTANCE,
)

AutoState = AutoQuestState

__all__ = [
    "AutoManager",
    "QuestInfo",
    "AutoQuestState",
    "AutoState",
    "MOB_LOCATION_DATA",
    "BO_MONG_MAP_ID",
    "BO_MONG_NPC_TEMPLATE_ID",
    "NPC_INTERACT_DISTANCE",
]
