# -*- coding: utf-8 -*-
"""
Package auto cho ClientNROpy.
Chứa toàn bộ hệ thống tự động hóa trò chơi:
AutoManager (Tàn sát mob, Tự đánh AK, Săn Boss, Tự dùng Item, Làm nhiệm vụ Bò Mộng, Tự hồi sinh),
AutoTrainPet (Úp đệ tử), AutoTrainNewAccount (Úp sơ sinh/tân thủ).
"""

from .auto_manager import AutoManager
from .auto_quest_bomong import AutoQuest, AutoState, QuestInfo
from .auto_revive_manager import AutoReviveManager
from .auto_use_item_manager import AutoUseItemManager
from .auto_train_pet import AutoTrainPet, AutoTrainPetMode, AutoTrainPetAttackMode
from .auto_train_new_account import AutoTrainNewAccount
from .boss_hunter import BossHunter
from .boss_manager import BossManager
from .combat_manager import CombatManager

__all__ = [
    "AutoManager",
    "AutoQuest",
    "AutoState",
    "QuestInfo",
    "AutoReviveManager",
    "AutoUseItemManager",
    "AutoTrainPet",
    "AutoTrainPetMode",
    "AutoTrainPetAttackMode",
    "AutoTrainNewAccount",
    "BossHunter",
    "BossManager",
    "CombatManager",
]
