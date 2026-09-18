# -*- coding: utf-8 -*-
"""
Module Tự Động Hóa Hợp Nhất (Unified Automation Engine - auto_manager.py).
Tập hợp và chuẩn hóa toàn bộ các tính năng tự động trong game thành 1 file duy nhất:
1. Hệ thống Tiêu điểm (Focus) & Dịch chuyển tức thời (Teleport)
2. Tự động đánh (Auto Attack - AK) & Tàn sát (Slaughter - TS quái, PK người chơi)
3. Xoay vòng kỹ năng theo hành tinh (Trái Đất, Namek, Xayda)
4. Tự động Hồi sinh thông minh (Auto Revive - bằng ngọc tại chỗ hoặc về thành)
5. Tự động dùng đậu thần (Auto Pean) bảo vệ HP/KI
6. Tự động nhặt đồ dưới đất (Auto Pick / Loot Item)
7. Quản lý Boss & Bóc tách ChatVip (Boss Manager)
8. Máy trạng thái Săn Boss tự động & Đi tuần (Autonomous Boss Hunter & Patrol)
9. Auto nhiệm vụ Bò Mộng hằng ngày (Daily Quest Bo Mong)
10. Auto Shuttle di chuyển qua lại giữa 2 map
11. Auto dùng vật phẩm theo chu kỳ phút (Auto Use Item)

Vận hành trên 1 Worker Thread DUY NHẤT cho mỗi Client theo thứ tự ưu tiên,
tránh xung đột race condition, giảm tối đa tải CPU/RAM khi chạy đa tài khoản.
"""

import math
import random
import re
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union

from .boss import Boss
from .char import Char
from .item import Item
from .item_map import ItemMap
from .mob import Mob
from .waypoint import Waypoint
from .xmap.map_data import MAP_NAMES, get_map_name, normalize_str, resolve_map_id
from .auto_train_pet import AutoTrainPet, AutoTrainPetMode, AutoTrainPetAttackMode
from .auto_train_new_account import AutoTrainNewAccount
from .game_data import get_item_name, format_big_number, SKILL_NAMES


# ==============================================================================
# DỮ LIỆU CẤU HÌNH CHO NHIỆM VỤ BÒ MỘNG
# ==============================================================================
BO_MONG_MAP_ID: int = 47
BO_MONG_NPC_TEMPLATE_ID: int = 17
NPC_INTERACT_DISTANCE: int = 60

MOB_LOCATION_DATA: Dict[str, Tuple[int, int]] = {
    "mộc nhân": (14, 0), "khủng long": (1, 1), "lợn lòi": (8, 2), "quỷ đất": (15, 3),
    "khủng long mẹ": (2, 4), "lợn lòi mẹ": (9, 5), "quỷ đất mẹ": (16, 6),
    "thằn lằn bay": (3, 7), "phi long": (11, 8), "quỷ bay": (17, 9), "thằn lằn mẹ": (4, 10),
    "phi long mẹ": (12, 11), "quỷ bay mẹ": (18, 12), "ốc mượn hồn": (29, 13),
    "ốc sên": (33, 14), "heo xayda mẹ": (37, 15), "heo rừng": (28, 16),
    "heo da xanh": (32, 17), "heo xayda": (36, 18), "heo rừng mẹ": (6, 19),
    "heo xanh mẹ": (10, 20), "alien": (19, 21), "bulon": (30, 22), "ukulele": (34, 23),
    "quỷ mập": (38, 24), "tambourine": (6, 25), "drum": (10, 26), "akkuman": (19, 27),
    "không tặc": (29, 31), "quỷ đầu to": (33, 32), "quỷ địa ngục": (37, 33),
    "nappa": (68, 39), "soldier": (70, 40), "appule": (71, 41), "raspberry": (71, 42),
    "thằn lằn xanh": (72, 43), "quỷ đầu nhọn": (64, 44), "quỷ đầu vàng": (63, 45),
    "quỷ da tím": (66, 46), "quỷ già": (67, 47), "cá sấu": (73, 48),
    "dơi da xanh": (67, 49), "quỷ chim": (81, 50), "lính đầu trọc": (74, 51),
    "lính tai dài": (76, 52), "lính vũ trụ": (77, 53), "khỉ lông đen": (82, 54),
    "khỉ giáp sắt": (83, 55), "khỉ lông đỏ": (79, 56), "khỉ lông vàng": (80, 57),
    "xên con cấp 1": (92, 58), "xên con cấp 2": (93, 59), "xên con cấp 3": (94, 60),
    "xên con cấp 4": (96, 61), "xên con cấp 5": (97, 62), "xên con cấp 6": (98, 63),
    "xên con cấp 7": (99, 64), "xên con cấp 8": (100, 65), "tai tím": (106, 66),
    "abo": (107, 67), "kado": (109, 68), "da xanh": (110, 69),
    "ếch mặt đỏ": (166, 86), "jinai": (166, 87),
    "khỉ lông xanh": (155, 78), "taburine đỏ": (155, 79),
}


class QuestInfo:
    """Mô hình dữ liệu lưu tiến trình nhiệm vụ Bò Mộng."""

    def __init__(self):
        self.is_valid: bool = False
        self.mob_name: str = ""
        self.map_name: str = ""
        self.target_count: int = 0
        self.initial_count: int = 0
        self.kill_count: int = 0
        self.quests_remaining: int = 0
        self.quests_total: int = 0

    @property
    def current_progress(self) -> int:
        return self.initial_count + self.kill_count

    def __str__(self) -> str:
        if not self.is_valid:
            return "QuestInfo(Không có nhiệm vụ)"
        return f"NV: 'Hạ {self.mob_name}', Map: '{self.map_name}', Tiến độ: {self.current_progress}/{self.target_count}"


class AutoQuestState(Enum):
    IDLE = "Đang nghỉ"
    GET_QUEST = "Đi nhận nhiệm vụ"
    NAVIGATE_TO_MAP = "Di chuyển đến map"
    SELECT_ZONE = "Chọn khu vực"
    EXECUTE_QUEST = "Thực hiện nhiệm vụ"
    REPORT_QUEST = "Đi trả nhiệm vụ"


# ==============================================================================
# BỘ ĐIỀU PHỐI SĂN BOSS & CHIA KHU ĐA TÀI KHOẢN (SHARED HUNT COORDINATOR)
# ==============================================================================
class SharedHuntCoordinator:
    """
    Bộ điều phối săn Boss và chia việc dò khu vực giữa nhiều tài khoản.
    Đảm bảo:
    1. Không có 2 acc quét trùng 1 khu cùng lúc (chia việc thông minh).
    2. Khi 1 acc phát hiện Boss trong khu X:
       - Cập nhật vị trí Boss (map_id, zone_id, pos).
       - Thông báo cho toàn bộ các acc còn lại cùng bay vào khu X để tập hợp pem Boss và nhặt đồ.
    3. Khi Boss chết:
       - Toàn bộ các acc chuyển sang trạng thái nhặt đồ (looting) rồi tìm mục tiêu mới.
    """
    _lock = threading.RLock()
    _managers: Set[Any] = set()
    _zone_claims: Dict[int, Dict[int, Dict[str, Any]]] = {}  # map_id -> zone_id -> info
    _active_bosses: Dict[str, Dict[str, Any]] = {}          # norm_boss_name -> info

    @classmethod
    def register(cls, manager: Any) -> None:
        with cls._lock:
            cls._managers.add(manager)

    @classmethod
    def unregister(cls, manager: Any) -> None:
        with cls._lock:
            cls._managers.discard(manager)

    @classmethod
    def claim_next_zone(
        cls,
        acc_tag: str,
        map_id: int,
        available_zones: List[int],
        exclude_zones: Optional[Set[int]] = None,
        current_zone: int = -1,
    ) -> Optional[int]:
        """Tìm và giữ chỗ (claim) khu tiếp theo chưa có ai quét, tránh trùng lặp giữa các acc."""
        with cls._lock:
            now = time.time()
            if map_id not in cls._zone_claims:
                cls._zone_claims[map_id] = {}

            claims = cls._zone_claims[map_id]
            excluded = exclude_zones or set()

            valid_zones = [z for z in available_zones if z != current_zone and z not in excluded]
            if not valid_zones:
                return None

            free_zones = []
            for z in valid_zones:
                c = claims.get(z)
                if not c:
                    free_zones.append((z, 0.0))
                elif c.get("claimed_by") == acc_tag:
                    free_zones.append((z, c.get("last_scanned_time", 0.0)))
                elif (now - c.get("claim_time", 0.0)) >= 12.0:
                    free_zones.append((z, c.get("last_scanned_time", 0.0)))

            if not free_zones:
                return None

            free_zones.sort(key=lambda item: item[1])
            acc_offset = abs(hash(acc_tag)) % max(1, len(free_zones))
            best_zone = free_zones[acc_offset % len(free_zones)][0]

            claims[best_zone] = {
                "claimed_by": acc_tag,
                "claim_time": now,
                "last_scanned_time": claims.get(best_zone, {}).get("last_scanned_time", 0.0),
            }
            return best_zone

    @classmethod
    def release_zone(cls, acc_tag: str, map_id: int, zone_id: int, scanned: bool = True) -> None:
        """Giải phóng khu và cập nhật thời điểm đã quét xong."""
        with cls._lock:
            now = time.time()
            if map_id in cls._zone_claims and zone_id in cls._zone_claims[map_id]:
                c = cls._zone_claims[map_id][zone_id]
                if scanned:
                    c["last_scanned_time"] = now
                if c.get("claimed_by") == acc_tag:
                    c["claimed_by"] = ""
                    c["claim_time"] = 0.0

    @classmethod
    def report_boss_found(
        cls,
        reporter_mgr: Any,
        boss: Boss,
        map_id: int,
        zone_id: int,
        pos: Tuple[int, int],
    ) -> None:
        """Báo cáo đã tìm thấy Boss để toàn bộ các acc cùng bay vào khu pem Boss."""
        with cls._lock:
            now = time.time()
            b_norm = normalize_str(boss.name)
            cls._active_bosses[b_norm] = {
                "name": boss.name,
                "map_id": map_id,
                "zone_id": zone_id,
                "pos": pos,
                "found_by": reporter_mgr._tag(),
                "found_time": now,
                "is_died": False,
            }
            for mgr in list(cls._managers):
                if mgr is not reporter_mgr:
                    try:
                        mgr.notify_boss_spotted(boss, map_id, zone_id, pos, reporter_tag=reporter_mgr._tag())
                    except Exception:
                        pass

    @classmethod
    def report_boss_died(
        cls,
        reporter_mgr: Any,
        boss_name: str,
        map_id: int,
        zone_id: int,
    ) -> None:
        """Báo cáo Boss đã chết để toàn bộ các acc cùng chuyển sang trạng thái nhặt đồ."""
        with cls._lock:
            b_norm = normalize_str(boss_name)
            if b_norm in cls._active_bosses:
                cls._active_bosses[b_norm]["is_died"] = True
            for mgr in list(cls._managers):
                if mgr is not reporter_mgr:
                    try:
                        mgr.notify_boss_killed(boss_name, map_id, zone_id, reporter_tag=reporter_mgr._tag())
                    except Exception:
                        pass

    @classmethod
    def get_active_boss(cls, boss_name: str) -> Optional[Dict[str, Any]]:
        """Lấy thông tin vị trí Boss đang còn sống nếu đã có acc tìm thấy gần đây."""
        with cls._lock:
            b_norm = normalize_str(boss_name)
            info = cls._active_bosses.get(b_norm)
            if info and not info.get("is_died", False):
                if (time.time() - info.get("found_time", 0.0)) < 90.0:
                    return info
            return None

    @classmethod
    def clear_boss(cls, boss_name: str) -> None:
        with cls._lock:
            b_norm = normalize_str(boss_name)
            cls._active_bosses.pop(b_norm, None)

    @classmethod
    def get_active_scanners_count(cls, map_id: int) -> int:
        with cls._lock:
            now = time.time()
            claims = cls._zone_claims.get(map_id, {})
            scanners = set()
            for z, data in claims.items():
                if data.get("claimed_by") and (now - data.get("claim_time", 0.0)) < 12.0:
                    scanners.add(data.get("claimed_by"))
            return len(scanners)


# ==============================================================================
# CLASS TRUNG TÂM: AUTOMANAGER (UNIFIED AUTO ENGINE)
# ==============================================================================
class AutoManager:
    """
    Class điều phối toàn diện mọi tác vụ tự động hóa trong ClientNROpy.
    """

    # --- Hằng số Boss Hunter & Tuần tra ---
    STATE_BH_IDLE = "IDLE"
    STATE_BH_MOVING = "MOVING"
    STATE_BH_SCANNING = "SCANNING"
    STATE_BH_COMBAT = "COMBAT"
    STATE_BH_REVIVING = "REVIVING"
    STATE_BH_LOOTING = "LOOTING"
    STATE_BH_PATROL = "PATROL"

    DEFAULT_WHITELIST: List[str] = [
        "Black Goku", "Supper Black Goku", "Super Black Goku", "Zamas", "Zamas Kaioshin",
        "Bojack", "Đội Bojack", "Xên con", "Xên bọ hung",
        "Số 4 Recome Namec", "Số 3 Recome Namec", "Số 2 Recome Namec", "Số 1 Recome Namec",
        "Tiểu đội trưởng Ginyu Namec", "Mabư", "Doraemon", "Nobita", "Suneo", "Chaien",
        "Android 13", "Android 14", "Android 15",
    ]

    FUTURE_PATROL_MAPS: List[int] = [102, 92, 93, 94, 96, 97, 98, 99, 100, 103]
    NAMEC_PATROL_MAPS: List[int] = [7, 8, 9, 10, 11, 12, 13, 31, 32, 33, 34, 43]
    RED_MONKEY_MAPS: List[int] = [79]
    DEFAULT_PATROL_MAPS: List[int] = FUTURE_PATROL_MAPS + NAMEC_PATROL_MAPS + RED_MONKEY_MAPS

    # --- Hằng số Nhặt đồ & Kỹ năng ---
    DEFAULT_BLOCKED_ITEMS: Set[int] = {225, 353, 354, 355, 356, 357, 358, 359, 360, 362}

    TANSAT_SKILLS_BY_GENDER: Dict[int, tuple] = {
        0: (9, 1, 0),    # Trái Đất: kaioken, kamejoko, đấm
        1: (12, 3, 2),   # Namek: trứng, masenko, đấm
        2: (13, 5, 4),   # Xayda: hoá hình, atomic, đấm
    }

    # Hằng số Săn Boss & Giám sát HP & Nhặt đồ (C# AutoFarmBossNappa)
    BOSS_NO_DAMAGE_TIMEOUT_S: float = 10.0
    HP_CHECK_INTERVAL_S: float = 2.0
    MAX_CONSECUTIVE_NO_DAMAGE: int = 5
    MAX_CONSECUTIVE_NO_DAMAGE_IN_FIGHT: int = 3
    WAIT_AFTER_BOSS_DEATH_S: float = 2.0
    PICK_ITEM_DELAY_S: float = 0.8
    MAX_PICK_ATTEMPTS: int = 5
    GANG_THIEN_SU_ITEM_ID: int = 1070
    FORBIDDEN_COMBAT_SKILLS: Set[int] = {10, 11, 14}  # Tuyệt đối không dùng QCKK (10), Makankosappo (11), Tự sát (14)

    # Bóc tách thông báo Boss ChatVip
    STR_BOSS_APPEARED: List[str] = [
        "BOSS ", " vừa xuất hiện tại ", " appear at ", " muncul di ", " khu vực ", " zone ", " zona ",
    ]
    STR_BOSS_KILLED: List[str] = [
        " mọi người đều ngưỡng mộ.", " everyone admired.", " semua orang mengagumi.",
        " đã đánh bại và nhận được cải trang thành ", " killed and receive disguise of ",
        " membunuh Dan menerima disguise ", ": Đã tiêu diệt được ", ": defeated ", ": mengalahkan ",
    ]

    def __init__(self, client=None):
        self.client = client
        self._lock = threading.RLock()

        # ----------------------------------------------------------------------
        # 1. Trạng thái Hồi sinh & Ăn đậu & Nhặt đồ
        # ----------------------------------------------------------------------
        self.auto_revive: bool = True               # Mặc định tự động hồi sinh là BẬT
        self.revive_mode: str = "gem"               # "gem" (ngọc tại chỗ cmd -16) hoặc "town" (về làng cmd -15)
        self.revive_count: int = 0
        self.last_revive_time: float = 0.0
        self.revive_cooldown: float = 2.0

        self.auto_pean: bool = True                 # Tự động dùng đậu bảo vệ HP/KI
        self.pean_threshold: float = 0.3            # Dưới 30% HP/KI thì ăn đậu

        self.auto_pick: bool = True                 # Tự động nhặt đồ rơi
        self.pick_gem_only: bool = False
        self.blocked_items: Set[int] = set(self.DEFAULT_BLOCKED_ITEMS)

        # ----------------------------------------------------------------------
        # 2. Trạng thái Tự đánh (AK) & Tàn sát (TS)
        # ----------------------------------------------------------------------
        self.is_ak: bool = False
        self.is_tansat: bool = False
        self.tansat_mode: str = "mob"               # "mob", "player", "all"
        self.target_mob_ids: Set[int] = set()
        self.target_mob_types: Set[int] = set()
        self.avoid_super_mob: bool = True
        self.target_char_names: Set[str] = set()
        self.target_char_ids: Set[int] = set()
        self.tansat_skill_id: Optional[int] = None
        self.combat_combo_skills: Optional[List[int]] = None
        self._combo_skill_idx: int = 0
        self._skill_last_use: Dict[int, float] = {}
        self.last_attack_time: float = 0.0

        # ----------------------------------------------------------------------
        # 3. Quản lý Boss & Danh sách Boss (Mod/Boss.cs)
        # ----------------------------------------------------------------------
        self.list_bosses: List[Boss] = []
        self.pending_zone_id: int = -1
        self.pending_boss_name: str = ""
        self.on_boss_appeared_callbacks: List[Callable[[Boss], None]] = []
        self.on_boss_killed_callbacks: List[Callable[[Boss], None]] = []
        self.on_boss_updated_callbacks: List[Callable[[Boss], None]] = []

        # ----------------------------------------------------------------------
        # 4. Máy trạng thái Săn Boss Tự Động (BossHunter FSM)
        # ----------------------------------------------------------------------
        self.is_boss_hunter_enabled: bool = False
        self.hunt_all: bool = False
        self.target_bosses: Set[str] = set()
        for t in self.DEFAULT_WHITELIST:
            self.add_hunt_target(t)

        self.auto_loot_boss: bool = True
        self.auto_patrol: bool = True
        self.patrol_maps: List[int] = list(self.DEFAULT_PATROL_MAPS)
        self.patrol_map_index: int = 0
        self.min_scan_zone_delay: float = 0.5
        self.max_scan_zone_delay: float = 0.7
        self.max_zones_scan: int = 30
        self._zone_blocked_by_quest: bool = False

        self.bh_state: str = self.STATE_BH_IDLE
        self.current_boss: Optional[Boss] = None
        self.scanned_zones: Set[int] = set()
        self.last_boss_pos: Optional[Tuple[int, int]] = None
        self.looting_start_time: float = 0.0
        self.bh_status_message: str = "Đang chờ lệnh hoặc thông báo Boss mới..."

        # Thống kê săn boss và đồ loot
        self.boss_kill_count: int = 0
        self.boss_looted_items_count: int = 0
        self.boss_kill_history: List[Dict[str, Any]] = []

        # Giám sát HP Boss & Phát hiện Boss ảo/kẹt (C# AutoFarmBossNappa)
        self.boss_entry_time: float = 0.0
        self.boss_damaged: bool = False
        self.last_boss_hp: int = -1
        self.last_boss_hp_check_time: float = 0.0
        self.consecutive_no_damage_count: int = 0

        # Nhặt đồ Boss rơi (C# AutoFarmBossNappa)
        self.boss_death_time: float = 0.0
        self.pick_item_attempts: int = 0
        self.last_pick_item_time: float = 0.0
        self.boss_looted_items_history: List[Dict[str, Any]] = []

        # Đăng ký với bộ điều phối săn Boss đa tài khoản
        SharedHuntCoordinator.register(self)

        # ----------------------------------------------------------------------
        # 5. Nhiệm vụ Bò Mộng hằng ngày (AutoQuest FSM)
        # ----------------------------------------------------------------------
        self.is_quest_enabled: bool = False
        self.quest_info: QuestInfo = QuestInfo()
        self.quest_state: AutoQuestState = AutoQuestState.IDLE
        self.quest_start_time: Optional[float] = None
        self.quests_completed: int = 0
        self.quest_total_kills: int = 0

        # ----------------------------------------------------------------------
        # 6. Auto Shuttle (Đi lại 2 map)
        # ----------------------------------------------------------------------
        self.is_shuttle_enabled: bool = False
        self.shuttle_map_a: Optional[int] = None
        self.shuttle_map_b: Optional[int] = None
        self.shuttle_rounds: int = 0
        self.shuttle_legs_done: int = 0
        self.shuttle_target: Optional[int] = None
        self.shuttle_status_message: str = "Đã dừng"

        # ----------------------------------------------------------------------
        # 7. Auto Dùng Item Định Kỳ (Auto Use Item)
        # ----------------------------------------------------------------------
        self.auto_use_item_enabled: bool = False
        self.auto_use_item_id: Optional[int] = None
        self.auto_use_interval_minutes: float = 10.0
        self.auto_use_count: int = 0
        self.auto_use_last_time: float = 0.0
        self.auto_use_last_alert: float = 0.0

        # ----------------------------------------------------------------------
        # 8. Auto Úp Đệ Tử (AutoTrainPet) & Auto Tân Thủ (AutoTrainNewAccount)
        # ----------------------------------------------------------------------
        self.train_pet: AutoTrainPet = AutoTrainPet(self.client)
        self.train_new_acc: AutoTrainNewAccount = AutoTrainNewAccount(self.client)

        # ----------------------------------------------------------------------
        # 9. Đăng ký Callbacks với Controller
        # ----------------------------------------------------------------------
        self._register_controller_callbacks()

        # ----------------------------------------------------------------------
        # 9. Khởi động 1 Worker Thread DUY NHẤT
        # ----------------------------------------------------------------------
        self._is_worker_running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
        self._start_worker()

    def _tag(self) -> str:
        """Lấy nhãn nhận diện tài khoản cho log."""
        if self.client:
            return getattr(self.client, "account_id", "Client") or "Client"
        return "Client"

    def _get_my_char(self) -> Optional[Char]:
        """Lấy đối tượng nhân vật an toàn."""
        if self.client and hasattr(self.client, "myChar") and self.client.myChar:
            return self.client.myChar
        return Char.myCharz()

    def _service(self):
        """Lấy đối tượng service an toàn."""
        if self.client and hasattr(self.client, "service"):
            return self.client.service
        return None

    def _log_auto(self, msg: str, is_important: bool = False, is_alert: bool = False) -> None:
        """Ghi log qua logger chuẩn."""
        try:
            from .logger import logger
            tag = self._tag()
            if is_alert:
                logger.alert(msg, account_tag=tag)
            elif is_important:
                logger.boss(msg, account_tag=tag)
            else:
                logger.auto(msg, account_tag=tag)
        except Exception:
            print(f"[{self._tag()}] {msg}")

    # ==========================================================================
    # ĐĂNG KÝ HOOKS VÀ SỰ KIỆN TỪ CONTROLLER
    # ==========================================================================
    def _register_controller_callbacks(self) -> None:
        """Đăng ký lắng nghe sự kiện từ Controller."""
        if not self.client or not hasattr(self.client, "controller"):
            return

        ctrl = self.client.controller
        if hasattr(ctrl, "on_chat_vip_callbacks"):
            ctrl.on_chat_vip_callbacks.append(self._on_chat_vip_event)
        if hasattr(ctrl, "on_map_info_callbacks"):
            ctrl.on_map_info_callbacks.append(self._on_map_info_event)
        if hasattr(ctrl, "on_char_info_callbacks"):
            ctrl.on_char_info_callbacks.append(self._on_char_info_event)
        if hasattr(ctrl, "on_char_in_map_callbacks"):
            ctrl.on_char_in_map_callbacks.append(self._on_char_info_event)
        if hasattr(ctrl, "on_server_message_callbacks"):
            ctrl.on_server_message_callbacks.append(self._on_server_message_event)
        if hasattr(ctrl, "on_npc_menu_callbacks"):
            ctrl.on_npc_menu_callbacks.append(self._on_npc_menu_event)
        if hasattr(ctrl, "on_mob_killed_callbacks"):
            ctrl.on_mob_killed_callbacks.append(self._on_mob_killed_event)

        if hasattr(self.client, "xmap_controller"):
            self.client.xmap_controller.on_finish_callbacks.append(self._on_xmap_finished)

    def _on_chat_vip_event(self, chat_vip) -> None:
        text = getattr(chat_vip, "text", "")
        if text:
            self.handle_chat_vip(text)

    def _on_map_info_event(self, map_info) -> None:
        self.update_boss_status(map_info.mapID, map_info.zoneID, map_info.chars)
        if self.pending_zone_id != -1 and map_info.mapID != -1:
            if map_info.zoneID != self.pending_zone_id and self.client:
                self.client.change_zone(self.pending_zone_id)
            self.pending_zone_id = -1
            self.pending_boss_name = ""

    def _on_char_info_event(self, char) -> None:
        my_char = self._get_my_char()
        if my_char and my_char.mapInfo:
            self.update_boss_status(my_char.mapInfo.mapID, my_char.mapInfo.zoneID, my_char.mapInfo.chars)

    def _on_server_message_event(self, text: str) -> None:
        norm = normalize_str(text)
        if (
            "boss duoc ho tro" in norm
            or "khong the vao luc nay" in norm
            or ("ho tro" in norm and "khu vuc" in norm)
        ):
            self._zone_blocked_by_quest = True

    def _on_xmap_finished(self, success: bool, msg: str) -> None:
        if success and self.pending_zone_id != -1:
            my_char = self._get_my_char()
            if my_char and my_char.mapInfo:
                curr_zone = getattr(my_char.mapInfo, "zoneID", -1)
                if curr_zone != self.pending_zone_id and self.client:
                    self.client.change_zone(self.pending_zone_id)
            self.pending_zone_id = -1
            self.pending_boss_name = ""

    def _on_npc_menu_event(self, npc_template_id: int, chat_text: str, options: List[str]) -> None:
        try:
            if int(npc_template_id) == BO_MONG_NPC_TEMPLATE_ID:
                self._parse_quest_info(chat_text or "")
        except Exception:
            pass

    def _on_mob_killed_event(self, mob_template_id: int) -> None:
        self._increment_quest_kill_count(mob_template_id)

    # ==========================================================================
    # WORKER THREAD DUY NHẤT & VÒNG LẶP CHÍNH (MASTER WORKER LOOP)
    # ==========================================================================
    def _start_worker(self) -> None:
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._is_worker_running = True
            self._worker_thread = threading.Thread(
                target=self._master_loop,
                daemon=True,
                name=f"UnifiedAutoWorker-{self._tag()}",
            )
            self._worker_thread.start()

    def _master_loop(self) -> None:
        """
        Vòng lặp tổng hợp duy nhất cho toàn bộ các chế độ tự động.
        Thực thi mỗi chu kỳ ~0.12 - 0.15s.
        """
        while self._is_worker_running:
            try:
                # Chỉ xử lý khi client đã kết nối vào game
                if self.client and hasattr(self.client, "isConnected") and self.client.isConnected():
                    my_char = self._get_my_char()
                    if my_char:
                        # ------------------------------------------------------
                        # ƯU TIÊN 1: KIỂM TRA SỐNG CÒN & TỰ ĐỘNG HỒI SINH
                        # ------------------------------------------------------
                        if my_char.is_dead:
                            if self.auto_revive:
                                self._step_auto_revive(my_char)
                            time.sleep(0.3)
                            continue

                        # ------------------------------------------------------
                        # ƯU TIÊN 2: BẢO VỆ SINH MỆNH (TỰ DÙNG ĐẬU THẦN)
                        # ------------------------------------------------------
                        if self.auto_pean:
                            self._step_auto_pean(my_char)

                        # ------------------------------------------------------
                        # ƯU TIÊN 3: TÁC VỤ ĐỊNH KỲ (DÙNG ITEM BALO)
                        # ------------------------------------------------------
                        if self.auto_use_item_enabled:
                            self._step_auto_use_item()

                        # ------------------------------------------------------
                        # ƯU TIÊN 4: ĐIỀU PHỐI TÁC VỤ CHÍNH (THEO THỨ TỰ ƯU TIÊN)
                        # ------------------------------------------------------
                        # 4.1. Auto Tân Thủ (Làm chuỗi nhiệm vụ sơ sinh NV 0 -> NV 11)
                        if self.train_new_acc and self.train_new_acc.is_enabled:
                            handled = self.train_new_acc.step()
                            if handled:
                                time.sleep(0.12)
                                continue

                        # 4.2. Auto Úp Đệ Tử (AutoTrainPet)
                        if self.train_pet and self.train_pet.is_enabled:
                            handled = self.train_pet.step()
                            if handled:
                                time.sleep(0.12)
                                continue

                        # 4.3. Săn Boss (BossHunter FSM)
                        if self.is_boss_hunter_enabled:
                            self._step_boss_hunter(my_char)

                        # 4.4. Nhiệm Vụ Bò Mộng (AutoQuest FSM)
                        elif self.is_quest_enabled:
                            self._step_auto_quest(my_char)

                        # 4.5. Shuttle chuyển qua lại 2 map
                        elif self.is_shuttle_enabled:
                            self._step_shuttle(my_char)

                        # 4.6. Tàn Sát quái / người chơi (Slaughter) hoặc Tự Đánh (AK)
                        elif self.is_tansat or self.is_ak:
                            if self.is_ak:
                                self._step_ak(my_char)
                            if self.is_tansat:
                                self._step_tansat(my_char)

                        # 4.7. Tự nhặt vật phẩm rơi tự do khi không bận
                        elif self.auto_pick:
                            self._step_loot_ground_items(my_char)

            except Exception as ex:
                if getattr(self.client, "debug", False):
                    self._log_auto(f"Master loop error: {ex}", is_alert=True)

            time.sleep(0.12)

    # ==========================================================================
    # 1. HỆ THỐNG TIÊU ĐIỂM (FOCUS) & DỊCH CHUYỂN (TELEPORT)
    # ==========================================================================
    def focus(self, target_type: str = "", query: Optional[Union[int, str]] = None) -> Tuple[bool, str]:
        """Nhắm tiêu điểm (Focus) vào quái, người chơi hoặc vật phẩm dưới đất."""
        my_char = self._get_my_char()
        if my_char is None:
            return False, "Chưa đồng bộ nhân vật!"

        t_type = target_type.lower().strip()
        if not t_type:
            kind, target = my_char.get_focused_target()
            if kind is None:
                return True, "Hiện chưa focus vào đối tượng nào."
            if kind == "mob":
                return True, f"Đang focus Quái: ID={target.mobId}, Template={target.templateId}, HP={target.hp:,}/{target.maxHp:,} tại ({target.x},{target.y})"
            if kind == "char":
                return True, f"Đang focus Người chơi: '{target.cName}' (ID={target.charID}), HP={target.cHP:,}/{target.cHPFull:,} tại ({target.cx},{target.cy})"
            if kind == "item":
                return True, f"Đang focus Vật phẩm: MapID={target.itemMapID}, TemplateID={target.template_id} tại ({target.x},{target.y})"
            return True, f"Đang focus {kind}: {target}"

        if t_type in ("clear", "none", "unfocus", "defocus"):
            my_char.clear_focus()
            return True, "Đã hủy bỏ toàn bộ tiêu điểm focus."

        if t_type in ("mob", "quai", "m"):
            mob = my_char.mapInfo.find_mob(query, from_x=my_char.cx, from_y=my_char.cy)
            if mob is None:
                return False, f"Không tìm thấy quái phù hợp trong map với '{query}'!"
            my_char.focus_mob(mob)
            return True, f"Đã focus Quái ID {mob.mobId} (Template {mob.templateId}, HP: {mob.hp:,}/{mob.maxHp:,}) tại ({mob.x},{mob.y})!"

        if t_type in ("char", "player", "nguoi", "c", "p"):
            ch = my_char.mapInfo.find_char(query, exclude_char_id=my_char.charID, from_x=my_char.cx, from_y=my_char.cy)
            if ch is None:
                return False, f"Không tìm thấy người chơi phù hợp trong map với '{query}'!"
            my_char.focus_char(ch)
            return True, f"Đã focus Người chơi '{ch.cName}' (ID: {ch.charID}, HP: {ch.cHP:,}/{ch.cHPFull:,}) tại ({ch.cx},{ch.cy})!"

        if t_type in ("item", "vatpham", "vp", "i"):
            it = my_char.mapInfo.find_item(query, from_x=my_char.cx, from_y=my_char.cy)
            if it is None:
                return False, f"Không tìm thấy vật phẩm phù hợp trong map với '{query}'!"
            my_char.focus_item(it)
            return True, f"Đã focus Vật phẩm ID {it.itemMapID} (Template {it.template_id}) tại ({it.x},{it.y})!"

        return False, f"Loại mục tiêu không hợp lệ: '{target_type}'. Hỗ trợ: mob, char, item, clear."

    def teleport(self, x: int, y: int) -> bool:
        """Dịch chuyển tức thời đến toạ độ (x, y) không cần đồ họa."""
        my_char = self._get_my_char()
        svc = self._service()
        if my_char is None or svc is None:
            return False

        my_char.cx = x
        my_char.cy = y
        try:
            svc.charMove(x, y, flying=False)
            return True
        except Exception:
            return False

    def teleport_to(self, target: Any) -> Tuple[bool, str]:
        """Dịch chuyển tức thời tới đối tượng."""
        my_char = self._get_my_char()
        if my_char is None:
            return False, "Chưa đồng bộ nhân vật!"

        if isinstance(target, Mob):
            self.teleport(target.x, target.y)
            return True, f"Đã teleport tới Quái #{target.mobId} tại ({target.x}, {target.y})!"
        if isinstance(target, Char):
            self.teleport(target.cx, target.cy)
            return True, f"Đã teleport tới '{target.cName}' tại ({target.cx}, {target.cy})!"
        if isinstance(target, ItemMap):
            self.teleport(target.x, target.y)
            return True, f"Đã teleport tới Vật phẩm #{target.itemMapID} tại ({target.x}, {target.y})!"
        if isinstance(target, Waypoint):
            mid_x = (target.minX + target.maxX) // 2
            mid_y = (target.minY + target.maxY) // 2
            self.teleport(mid_x, mid_y)
            return True, f"Đã teleport tới Cổng '{target.name}' tại ({mid_x}, {mid_y})!"

        return False, f"Đối tượng teleport không hỗ trợ: {type(target)}"

    # ==========================================================================
    # 2. HỒI SINH (AUTO REVIVE) & ĂN ĐẬU (AUTO PEAN)
    # ==========================================================================
    def toggle_auto_revive(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt tính năng tự động hồi sinh."""
        if enable is not None:
            self.auto_revive = enable
        else:
            self.auto_revive = not self.auto_revive
        mode_str = "bằng Ngọc tại chỗ" if self.revive_mode == "gem" else "về Thành"
        st = "BẬT" if self.auto_revive else "TẮT"
        self._log_auto(f"Auto Hồi Sinh: {st} [{mode_str}]!")
        return self.auto_revive

    def set_auto_revive_mode(self, mode: str) -> bool:
        """Cài đặt chế độ hồi sinh ('gem' hoặc 'town')."""
        m = mode.lower().strip()
        if m in ("gem", "ngoc", "place", "here", "1"):
            self.revive_mode = "gem"
            self._log_auto("Đã chuyển chế độ: Hồi sinh bằng Ngọc tại chỗ (cmd -16)!")
            return True
        elif m in ("town", "ve", "thanh", "nha", "home", "0"):
            self.revive_mode = "town"
            self._log_auto("Đã chuyển chế độ: Hồi sinh về Thành / Nhà (cmd -15)!")
            return True
        return False

    def revive(self, at_place: bool = False) -> Tuple[bool, str]:
        """Gửi lệnh hồi sinh thủ công hoặc tự động."""
        svc = self._service()
        if not svc:
            return False, "Service chưa sẵn sàng!"
        self.revive_count += 1
        self.last_revive_time = time.time()
        if at_place or self.revive_mode == "gem":
            svc.wakeUpFromDead()
            return True, "Đã gửi lệnh hồi sinh tại chỗ bằng 1 ngọc (cmd -16)!"
        else:
            svc.returnTownFromDead()
            return True, "Đã gửi lệnh hồi sinh về thành / nhà (cmd -15)!"

    def _step_auto_revive(self, my_char: Char) -> None:
        """Xử lý hồi sinh tự động khi nhân vật chết thật sự."""
        now = time.time()
        if (now - self.last_revive_time) < self.revive_cooldown:
            return

        # Xác nhận chống chết ảo
        time.sleep(0.2)
        if not my_char.is_dead:
            return

        self.revive(at_place=(self.revive_mode == "gem"))
        mode_str = "Ngọc tại chỗ" if self.revive_mode == "gem" else "Về Thành"
        self._log_auto(
            f"Nhân vật bị hạ gục! Tự động hồi sinh [{mode_str}] [lần #{self.revive_count}]...",
            is_alert=True,
        )

    def _step_auto_pean(self, my_char: Char) -> None:
        """Tự động ăn đậu thần khi HP hoặc KI xuống thấp hơn ngưỡng."""
        if my_char.cHPFull <= 0 or my_char.cMPFull <= 0:
            return

        hp_ratio = my_char.cHP / max(1, my_char.cHPFull)
        ki_ratio = my_char.cMP / max(1, my_char.cMPFull)

        if hp_ratio <= self.pean_threshold or ki_ratio <= self.pean_threshold:
            if my_char.magicTree and my_char.magicTree.currPeas > 0:
                svc = self._service()
                if svc:
                    svc.magicTree(2)
                    time.sleep(0.2)

    # ==========================================================================
    # 3. TỰ ĐÁNH (AK) & TÀN SÁT (TS) & QUẢN LÝ KỸ NĂNG
    # ==========================================================================
    def start_ak(self) -> bool:
        """Bật chế độ tự động đánh (AK)."""
        self.is_ak = True
        self._log_auto("Tự Động Đánh (AK): BẬT!")
        return True

    def stop_ak(self) -> bool:
        """Tắt chế độ tự động đánh (AK)."""
        self.is_ak = False
        self._log_auto("Tự Động Đánh (AK): TẮT!")
        return False

    def toggle_ak(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt chế độ tự đánh mục tiêu đang focus."""
        if enable is not None:
            self.is_ak = enable
        else:
            self.is_ak = not self.is_ak
        self._log_auto(f"Tự Động Đánh (AK): {'BẬT' if self.is_ak else 'TẮT'}!")
        return self.is_ak

    def start_tansat(self, mode: str = "mob") -> bool:
        """Bật chế độ tàn sát tự động."""
        self.is_tansat = True
        if mode:
            self.tansat_mode = mode.lower()
        self._log_auto(f"Tàn Sát (Slaughter): BẬT [{self.tansat_mode}]!")
        return True

    def stop_tansat(self) -> bool:
        """Tắt chế độ tàn sát tự động."""
        self.is_tansat = False
        self._log_auto("Tàn Sát (Slaughter): TẮT!")
        return False

    def toggle_tansat(self, enable: Optional[bool] = None, mode: str = "mob") -> bool:
        """Bật / Tắt chế độ tàn sát tự động."""
        if enable is not None:
            self.is_tansat = enable
        else:
            self.is_tansat = not self.is_tansat
        if mode:
            self.tansat_mode = mode.lower()
        self._log_auto(f"Tàn Sát (Slaughter): {'BẬT' if self.is_tansat else 'TẮT'} [{self.tansat_mode}]!")
        return self.is_tansat

    def add_mob_target(self, mob_id: int) -> None:
        if mob_id in self.target_mob_ids:
            self.target_mob_ids.remove(mob_id)
        else:
            self.target_mob_ids.add(mob_id)

    def add_mob_type_target(self, template_id: int) -> None:
        if template_id in self.target_mob_types:
            self.target_mob_types.remove(template_id)
        else:
            self.target_mob_types.add(template_id)

    def clear_mob_targets(self) -> None:
        self.target_mob_ids.clear()
        self.target_mob_types.clear()

    def _reset_boss_fight_tracking(self) -> None:
        """Đặt lại toàn bộ dữ liệu theo dõi trận đánh Boss."""
        self.boss_entry_time = 0.0
        self.boss_damaged = False
        self.last_boss_hp = -1
        self.last_boss_hp_check_time = 0.0
        self.consecutive_no_damage_count = 0

    def set_combo_skills(self, skill_ids: List[int]) -> Tuple[bool, str]:
        """Cài đặt bộ 3 skill xoay vòng để pem boss / tàn sát (loại trừ QCKK, Makankosappo, Tự sát)."""
        clean_ids = [int(s) for s in skill_ids if int(s) not in self.FORBIDDEN_COMBAT_SKILLS]
        if not clean_ids:
            return False, "Danh sách skill không hợp lệ (không chứa skill cấm QCKK/Makankosappo/Tự sát)!"
        self.combat_combo_skills = clean_ids
        names = [f"{sid} ({SKILL_NAMES.get(sid, 'Skill')})" for sid in clean_ids]
        return True, f"Đã cài đặt combo 3 skill: {' -> '.join(names)}"

    def _get_tansat_skill_ids(self) -> tuple:
        my_char = self._get_my_char()
        gender = getattr(my_char, "cgender", 0) if my_char else 0
        try:
            gender = int(gender)
        except Exception:
            gender = 0
        return self.TANSAT_SKILLS_BY_GENDER.get(gender, (0, 2, 4))

    def _select_combat_skill_rotation(self, my_char: Char) -> int:
        """
        Xoay vòng combo 3 skill cho 1 boss liên tục đến khi boss chết.
        Tự động loại bỏ các skill bị cấm: Quả cầu kênh khi (10), Makankosappo (11), Tự sát (14).
        """
        if self.combat_combo_skills:
            candidate_list = [s for s in self.combat_combo_skills if s not in self.FORBIDDEN_COMBAT_SKILLS]
        else:
            gender = getattr(my_char, "cgender", 0) if my_char else 0
            try:
                gender = int(gender)
            except Exception:
                gender = 0
            candidate_list = list(self.TANSAT_SKILLS_BY_GENDER.get(gender, (0, 2, 4)))

        if not candidate_list:
            candidate_list = [0]

        now = time.time()
        num_candidates = len(candidate_list)
        for offset in range(num_candidates):
            idx = (self._combo_skill_idx + offset) % num_candidates
            s_id = candidate_list[idx]

            # Bỏ qua skill cấm nếu lọt vào
            if s_id in self.FORBIDDEN_COMBAT_SKILLS:
                continue

            # Kiểm tra Biến hình (13): nếu đã hoá khỉ rồi thì không cần hoá lại
            if s_id == 13 and getattr(my_char, "isMonkey", 0) > 0:
                continue

            # Kiểm tra năng lượng KI/MP: nếu cMP <= 15 và không phải chiêu đấm cơ bản (0, 2, 4)
            if s_id not in (0, 2, 4) and getattr(my_char, "cMP", 100) < 15:
                continue

            # Cooldown theo loại skill:
            cd = 0.0
            if s_id in (1, 3, 5):      # Chưởng Kamejoko / Masenko / Antomic
                cd = 1.2
            elif s_id in (9, 17, 25):  # Kaioken, Liên hoàn, Cađíc liên hoàn
                cd = 4.0
            elif s_id in (12, 13):     # Đẻ trứng, Biến hình
                cd = 25.0

            last_used = self._skill_last_use.get(s_id, 0.0)
            if (now - last_used) >= cd:
                self._combo_skill_idx = (idx + 1) % num_candidates
                return s_id

        # Fallback về chiêu đấm cơ bản (luôn sẵn sàng 0s CD)
        return candidate_list[-1]

    def _pick_attack_skill(self) -> Optional[int]:
        if self.tansat_skill_id is not None:
            return self.tansat_skill_id
        my_char = self._get_my_char()
        if not my_char:
            return 0
        return self._select_combat_skill_rotation(my_char)

    def attack_target(self, target: Any = None) -> bool:
        """Tấn công mục tiêu (hoặc mục tiêu đang focus) với xoay skill combo."""
        my_char = self._get_my_char()
        svc = self._service()
        if not my_char or not svc:
            return False

        if target is None:
            kind, focus_t = my_char.get_focused_target()
            if kind == "mob":
                vMob = [focus_t]
                vChar = []
            elif kind == "char":
                vMob = []
                vChar = [focus_t]
            else:
                return False
        elif isinstance(target, Mob):
            vMob = [target]
            vChar = []
        elif isinstance(target, Char):
            vMob = []
            vChar = [target]
        else:
            return False

        skill_id = self._pick_attack_skill()
        if skill_id is not None:
            try:
                if getattr(my_char, "skillTemplateId", None) != skill_id:
                    svc.selectSkill(skill_id)
                    my_char.skillTemplateId = skill_id
            except Exception:
                pass
            self._skill_last_use[skill_id] = time.time()

        try:
            svc.sendPlayerAttack(vMob=vMob, vChar=vChar)
            return True
        except Exception:
            return False

    def _step_ak(self, my_char: Char) -> None:
        """Thực thi một chu kỳ tự đánh mục tiêu đang focus."""
        kind, target = my_char.get_focused_target()
        if not target:
            return

        target_x = getattr(target, "x", getattr(target, "cx", my_char.cx))
        target_y = getattr(target, "y", getattr(target, "cy", my_char.cy))

        if my_char.distance_to(target_x, target_y) > 60:
            self.teleport(target_x, target_y)

        now = time.time()
        if (now - self.last_attack_time) >= 0.12:
            self.last_attack_time = now
            self.attack_target(target)

    def _step_tansat(self, my_char: Char) -> None:
        """Thực thi một chu kỳ tàn sát quái / người chơi."""
        # 1. Nhặt đồ trước nếu có
        if self.auto_pick and self._step_loot_ground_items(my_char):
            return

        # 2. Tàn sát Quái
        if self.tansat_mode in ("mob", "all"):
            mobs = list(my_char.mapInfo.mobs.values())
            candidate_mobs = [
                m for m in mobs
                if getattr(m, "status", 0) not in (0, 1) and getattr(m, "hp", 0) > 0
                and (not self.avoid_super_mob or not getattr(m, "isBoss", False))
                and (not self.target_mob_ids or m.mobId in self.target_mob_ids)
                and (not self.target_mob_types or m.templateId in self.target_mob_types)
            ]
            if candidate_mobs:
                target_mob = min(candidate_mobs, key=lambda m: my_char.distance_to(m.x, m.y))
                my_char.focus_mob(target_mob)
                self.teleport(target_mob.x, target_mob.y)
                now = time.time()
                if (now - self.last_attack_time) >= 0.12:
                    self.last_attack_time = now
                    self.attack_target(target_mob)
                return

        # 3. Tàn sát Người chơi (Auto PK)
        if self.tansat_mode in ("player", "char", "pk", "all"):
            chars = list(my_char.mapInfo.chars.values())
            candidate_chars = [
                c for c in chars
                if c.charID != my_char.charID and not c.is_dead
                and (not self.target_char_names or c.cName in self.target_char_names)
                and (not self.target_char_ids or c.charID in self.target_char_ids)
            ]
            if candidate_chars:
                target_char = min(candidate_chars, key=lambda c: my_char.distance_to(c.cx, c.cy))
                my_char.focus_char(target_char)
                self.teleport(target_char.cx, target_char.cy)
                now = time.time()
                if (now - self.last_attack_time) >= 0.12:
                    self.last_attack_time = now
                    self.attack_target(target_char)
                return

    def _step_loot_ground_items(self, my_char: Char) -> bool:
        """Nhặt các vật phẩm rơi dưới đất."""
        items = list(my_char.mapInfo.items.values())
        if not items:
            return False

        valid_items = [
            it for it in items
            if it.itemMapID not in self.blocked_items
            and (not self.pick_gem_only or it.template_id in (77, 861, 862))
        ]
        if not valid_items:
            return False

        nearest = min(valid_items, key=lambda it: my_char.distance_to(it.x, it.y))
        self.teleport(nearest.x, nearest.y)
        svc = self._service()
        if svc:
            svc.pickItem(nearest.itemMapID)
            time.sleep(0.1)
        return True

    # ==========================================================================
    # 4. QUẢN LÝ BOSS & BÓC TÁCH CHATVIP (MOD/BOSS.CS)
    # ==========================================================================
    @classmethod
    def resolve_boss_map_id(cls, boss_name: str, map_name: str) -> int:
        raw_map = map_name.strip()
        norm_map = normalize_str(raw_map)
        b_name = boss_name.strip()

        if norm_map == "vach nui aru":
            return 42
        if norm_map in ("vach nui moori", "vach nui mori"):
            return 43
        if norm_map in ("tram tau vu tru", "tram tau"):
            if b_name.startswith("Số ") or b_name.startswith("Tiểu đội") or "ginyu" in b_name.lower():
                return 25
            if any(k in b_name for k in ["Bojack", "Bujin", "Bido", "Zangya"]):
                return 24
            return 24

        for mid, name in MAP_NAMES.items():
            if name.lower() == raw_map.lower():
                return mid
        for mid, name in MAP_NAMES.items():
            if normalize_str(name) == norm_map:
                return mid
        resolved = resolve_map_id(raw_map)
        return resolved if resolved is not None else -1

    @classmethod
    def _extract_killed_info(cls, text: str) -> Optional[Tuple[str, str]]:
        for k in cls.STR_BOSS_KILLED:
            if k in text:
                temp_text = text
                for sk in cls.STR_BOSS_KILLED:
                    temp_text = temp_text.replace(sk, "|")
                parts = temp_text.split("|")
                if len(parts) >= 2 and parts[0].strip() and parts[1].strip():
                    killer = parts[0].strip()
                    boss_name = parts[1].strip()
                    if boss_name.upper().startswith("BOSS "):
                        boss_name = boss_name[5:].strip()
                    return killer, boss_name

        m1 = re.search(r"BOSS\s+(.+?)\s+vừa\s+bị\s+(.+?)\s+tiêu\s+diệt", text, re.IGNORECASE)
        if m1:
            return m1.group(2).strip(), m1.group(1).strip()
        m2 = re.search(r"(.+?)\s+vừa\s+bị\s+tiêu\s+diệt\s+bởi\s+(.+)", text, re.IGNORECASE)
        if m2:
            return m2.group(2).strip(), m2.group(1).strip()
        m3 = re.search(r"(.+?)\s+đã\s+bị\s+(.+?)\s+tiêu\s+diệt", text, re.IGNORECASE)
        if m3:
            return m3.group(2).strip(), m3.group(1).strip()
        m4 = re.search(r"(.+?)\s+đã\s+tiêu\s+diệt\s+được\s+(.+)", text, re.IGNORECASE)
        if m4:
            return m4.group(1).strip(), m4.group(2).strip()
        m5 = re.search(r"(.+?)\s+đã\s+tiêu\s+diệt\s+(.+)", text, re.IGNORECASE)
        if m5:
            return m5.group(1).strip(), m5.group(2).strip()
        m6 = re.search(r"(?:BOSS\s+)?(.+?)\s+(?:đã|vừa)\s+bị\s+tiêu\s+diệt", text, re.IGNORECASE)
        if m6:
            return "", m6.group(1).strip()
        return None

    def handle_chat_vip(self, chat_vip_text: str) -> Optional[Boss]:
        text = chat_vip_text.strip()
        if text.startswith("!"):
            text = text[1:].strip()

        # 1. Kiểm tra Boss bị tiêu diệt
        killed_info = self._extract_killed_info(text)
        if killed_info:
            killer, boss_name = killed_info
            boss = None
            norm_bname = normalize_str(boss_name)
            for b in reversed(self.list_bosses):
                if (b.name == boss_name or normalize_str(b.name) == norm_bname) and not b.killer:
                    boss = b
                    break

            if boss is None:
                boss = Boss(name=boss_name, map_name="", is_died=True, killer=killer)
                self.list_bosses.append(boss)
            else:
                boss.is_died = True
                boss.killer = killer

            self._trim_bosses()
            for cb in self.on_boss_killed_callbacks:
                try:
                    cb(boss)
                except Exception:
                    pass
            return boss

        # 2. Kiểm tra Boss xuất hiện
        is_appear = any(app in text for app in self.STR_BOSS_APPEARED[1:4]) or text.startswith(self.STR_BOSS_APPEARED[0])
        if is_appear:
            temp_text = text
            for k in self.STR_BOSS_APPEARED:
                temp_text = temp_text.replace(k, "|")
            parts = temp_text.split("|")
            if len(parts) >= 3:
                boss_name = parts[1].strip()
                map_name = parts[2].strip()
                zone_id = -1
                if len(parts) >= 4 and parts[3].strip().isdigit():
                    zone_id = int(parts[3].strip())
                map_id = self.resolve_boss_map_id(boss_name, map_name)

                boss = None
                for b in reversed(self.list_bosses):
                    if b.name == boss_name and not b.is_died and b.map_id == -1:
                        boss = b
                        break

                if boss is None:
                    boss = Boss(name=boss_name, map_name=map_name, map_id=map_id, zone_id=zone_id, is_died=False)
                    self.list_bosses.append(boss)
                else:
                    boss.map_name = map_name
                    boss.map_id = map_id
                    boss.zone_id = zone_id
                    boss.appear_time = time.time()
                    boss.is_died = False

                self._trim_bosses()
                for cb in self.on_boss_appeared_callbacks:
                    try:
                        cb(boss)
                    except Exception:
                        pass
                return boss

        return None

    def _trim_bosses(self) -> None:
        while len(self.list_bosses) > 100:
            self.list_bosses.pop(0)

    def update_boss_status(self, current_map_id: int, current_zone_id: int, chars_in_map: Optional[Dict[int, Any]] = None) -> None:
        chars_list = list(chars_in_map.values()) if chars_in_map else []
        has_chars = len(chars_list) > 0

        for boss in self.list_bosses:
            if boss.is_died:
                continue

            if boss.map_id == current_map_id and current_map_id != -1:
                found_char = None
                norm_b = normalize_str(boss.name)
                for ch in chars_list:
                    ch_name = getattr(ch, "cName", "")
                    norm_c = normalize_str(ch_name)
                    if norm_c == norm_b or norm_b in norm_c or norm_c in norm_b:
                        found_char = ch
                        break

                if found_char is not None:
                    if boss.zone_id == -1:
                        boss.zone_id = current_zone_id
                    if getattr(found_char, "is_dead", False) or getattr(found_char, "isDie", False):
                        boss.is_died = True
                        for cb in self.on_boss_killed_callbacks:
                            try:
                                cb(boss)
                            except Exception:
                                pass
                else:
                    if has_chars and boss.zone_id == current_zone_id and boss.zone_id != -1:
                        boss.is_died = True
                        for cb in self.on_boss_killed_callbacks:
                            try:
                                cb(boss)
                            except Exception:
                                pass

    def get_all_bosses(self) -> List[Boss]:
        return list(self.list_bosses)

    def get_alive_bosses(self) -> List[Boss]:
        return [b for b in self.list_bosses if not b.is_died]

    def find_boss(self, query: Union[int, str]) -> Optional[Boss]:
        if isinstance(query, int):
            alive = self.get_alive_bosses()
            if 1 <= query <= len(alive):
                return alive[query - 1]
            if 1 <= query <= len(self.list_bosses):
                return self.list_bosses[query - 1]
            return None

        raw = str(query).strip()
        if not raw:
            return None
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(self.list_bosses):
                return self.list_bosses[idx - 1]
            return None

        norm_q = normalize_str(raw)
        for b in reversed(self.get_alive_bosses()):
            if norm_q in normalize_str(b.name):
                return b
        for b in reversed(self.list_bosses):
            if norm_q in normalize_str(b.name):
                return b
        return None

    def go_to_boss(self, target: Union[int, str]) -> Tuple[bool, str]:
        boss = self.find_boss(target)
        if boss is None:
            return False, f"Không tìm thấy Boss phù hợp với yêu cầu '{target}'!"
        if boss.is_died:
            reason = f"bị {boss.killer} tiêu diệt" if boss.killer else "đã chết"
            return False, f"Boss '{boss.name}' đã {reason}!"
        if boss.map_id == -1:
            return False, f"Boss '{boss.name}' chưa xác định được bản đồ!"

        my_char = self._get_my_char()
        curr_map_id = getattr(my_char.mapInfo, "mapID", -1) if my_char else -1
        curr_zone_id = getattr(my_char.mapInfo, "zoneID", -1) if my_char else -1

        if curr_map_id != boss.map_id:
            if not self.client or not hasattr(self.client, "xmap"):
                return False, "Chưa sẵn sàng Xmap!"
            self.pending_zone_id = boss.zone_id
            self.pending_boss_name = boss.name
            self.client.xmap(boss.map_id)
            return True, f"Đang Xmap tới '{boss.map_name}' [{boss.map_id}] (Boss: {boss.name})..."

        if boss.zone_id != -1 and curr_zone_id != boss.zone_id:
            if self.client and hasattr(self.client, "change_zone"):
                self.client.change_zone(boss.zone_id)
                return True, f"Đã gửi yêu cầu đổi sang Khu {boss.zone_id} của Boss '{boss.name}'!"

        return True, f"Bạn đã có mặt tại map '{boss.map_name}' khu {curr_zone_id} cùng Boss '{boss.name}'!"

    # ==========================================================================
    # 5. MÁY TRẠNG THÁI SĂN BOSS TỰ ĐỘNG (AUTONOMOUS BOSS HUNTER)
    # ==========================================================================
    def start_auto_hunt(self, targets: Optional[List[str]] = None) -> None:
        """Kích hoạt máy trạng thái tự động săn Boss."""
        if targets:
            self.clear_hunt_targets()
            for t in targets:
                self.add_hunt_target(t)
        self.is_boss_hunter_enabled = True
        self.bh_state = self.STATE_BH_IDLE
        self._log_auto("Đã kích hoạt Auto Săn Boss!")

    def stop_auto_hunt(self) -> None:
        """Dừng tự động săn Boss."""
        self.is_boss_hunter_enabled = False
        self.bh_state = self.STATE_BH_IDLE
        self.current_boss = None
        if self.client and hasattr(self.client, "xmap_stop"):
            self.client.xmap_stop()
        self._log_auto("Đã dừng Auto Săn Boss.")

    def toggle_auto_hunt(self) -> bool:
        if self.is_boss_hunter_enabled:
            self.stop_auto_hunt()
        else:
            self.start_auto_hunt()
        return self.is_boss_hunter_enabled

    @property
    def is_hunting(self) -> bool:
        """Thuộc tính tương thích ngược cho telegram_bot."""
        return self.is_boss_hunter_enabled

    def add_hunt_target(self, boss_name: str) -> None:
        clean = boss_name.rstrip()
        if clean.lower().endswith(" xx"):
            clean = clean[:-3].strip()
        norm = normalize_str(clean)
        if norm:
            self.target_bosses.add(norm)
            self.hunt_all = False

    def remove_hunt_target(self, boss_name: str) -> None:
        clean = boss_name.rstrip()
        if clean.lower().endswith(" xx"):
            clean = clean[:-3].strip()
        norm = normalize_str(clean)
        if norm in self.target_bosses:
            self.target_bosses.remove(norm)
        if not self.target_bosses:
            self.hunt_all = True

    def clear_hunt_targets(self) -> None:
        self.target_bosses.clear()
        self.hunt_all = True

    def is_target_boss(self, boss: Boss) -> bool:
        if self.hunt_all or not self.target_bosses:
            return True
        norm_b = normalize_str(boss.name)
        return any(t in norm_b or norm_b in t for t in self.target_bosses)

    def set_hunt_all(self, val: bool) -> None:
        self.hunt_all = bool(val)

    @property
    def auto_loot(self) -> bool:
        return self.auto_loot_boss

    @auto_loot.setter
    def auto_loot(self, val: bool) -> None:
        self.auto_loot_boss = bool(val)

    def set_patrol_mode(self, mode: str) -> None:
        m = mode.lower().strip()
        if m in ("namec", "namek", "tdst"):
            self.patrol_maps = list(self.NAMEC_PATROL_MAPS) + list(self.RED_MONKEY_MAPS)
        elif m in ("future", "tl", "tuonglai"):
            self.patrol_maps = list(self.FUTURE_PATROL_MAPS)
        else:
            self.patrol_maps = list(self.DEFAULT_PATROL_MAPS)
        self.patrol_map_index = 0

    def toggle_auto_patrol(self) -> bool:
        self.auto_patrol = not self.auto_patrol
        return self.auto_patrol

    def _step_boss_hunter(self, my_char: Char) -> None:
        """Thực thi một bước trong máy trạng thái săn Boss."""
        # 1. Kiểm tra Boss hiện tại có bị người khác hạ chưa
        if self.current_boss and self.current_boss.is_died:
            if self.bh_state == self.STATE_BH_COMBAT and self.auto_loot_boss:
                self.bh_state = self.STATE_BH_LOOTING
                self.looting_start_time = time.time()
            elif self.bh_state != self.STATE_BH_LOOTING:
                killer_str = f" bởi '{self.current_boss.killer}'" if self.current_boss.killer else ""
                self._log_auto(f"Boss '{self.current_boss.name}' đã bị hạ{killer_str}. Đổi mục tiêu!", is_important=True)
                self.current_boss = None
                self.bh_state = self.STATE_BH_IDLE
                return

        # 2. Xử lý theo từng State
        if self.bh_state == self.STATE_BH_IDLE:
            self._handle_bh_idle(my_char)
        elif self.bh_state == self.STATE_BH_PATROL:
            self._handle_bh_patrol(my_char)
        elif self.bh_state == self.STATE_BH_MOVING:
            self._handle_bh_moving(my_char)
        elif self.bh_state == self.STATE_BH_SCANNING:
            self._handle_bh_scanning(my_char)
        elif self.bh_state == self.STATE_BH_COMBAT:
            self._handle_bh_combat(my_char)
        elif self.bh_state == self.STATE_BH_LOOTING:
            self._handle_bh_looting(my_char)

    def _handle_bh_idle(self, my_char: Char) -> None:
        next_boss = None
        for b in reversed(self.get_alive_bosses()):
            if not b.is_died and b.map_id != -1 and self.is_target_boss(b):
                next_boss = b
                break

        if next_boss is not None:
            self.current_boss = next_boss
            self.scanned_zones.clear()
            self.bh_status_message = f"Phát hiện mục tiêu: '{next_boss.name}' tại '{next_boss.map_name}' [{next_boss.map_id}]. Bắt đầu di chuyển!"
            self._log_auto(self.bh_status_message, is_important=True)
            self.bh_state = self.STATE_BH_MOVING
        else:
            if self.auto_patrol and self.patrol_maps:
                if self.patrol_map_index >= len(self.patrol_maps):
                    self.patrol_map_index = 0
                curr_map = self.patrol_maps[self.patrol_map_index]
                self.bh_status_message = f"Đang rảnh rỗi. Bắt đầu tuần tra map {curr_map} ({get_map_name(curr_map)})..."
                self.bh_state = self.STATE_BH_PATROL
            else:
                self.bh_status_message = "Đang chờ Boss xuất hiện..."

    def _handle_bh_patrol(self, my_char: Char) -> None:
        # Ưu tiên nếu có thông báo Boss mới
        for b in reversed(self.get_alive_bosses()):
            if not b.is_died and b.map_id != -1 and self.is_target_boss(b):
                self.current_boss = b
                self.scanned_zones.clear()
                self._log_auto(f"Thông báo Boss '{b.name}'! Dừng tuần tra, bắt đầu di chuyển!", is_important=True)
                self.bh_state = self.STATE_BH_MOVING
                return

        if not self.patrol_maps:
            self.bh_state = self.STATE_BH_IDLE
            return

        if self.patrol_map_index >= len(self.patrol_maps):
            self.patrol_map_index = 0

        target_map = self.patrol_maps[self.patrol_map_index]
        curr_map = getattr(my_char.mapInfo, "mapID", -1)

        if curr_map != target_map:
            if self.client and hasattr(self.client, "xmap"):
                xst = self.client.xmap_status()
                if not xst.get("is_acting", False):
                    self.client.xmap(target_map)
            return

        # Đang ở map tuần tra -> tạo boss ảo tạm để quét các khu tìm boss xuất hiện trước
        virtual_boss = Boss(name="Boss Tuần Tra", map_name=get_map_name(curr_map), map_id=curr_map)
        self.current_boss = virtual_boss
        self.bh_state = self.STATE_BH_SCANNING

    def _handle_bh_moving(self, my_char: Char) -> None:
        if not self.current_boss:
            self.bh_state = self.STATE_BH_IDLE
            return

        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)
        if curr_map_id == self.current_boss.map_id:
            self.bh_status_message = f"Đã tới map '{self.current_boss.map_name}'. Bắt đầu quét khu!"
            self.bh_state = self.STATE_BH_SCANNING
            return

        if self.client and hasattr(self.client, "xmap"):
            xst = self.client.xmap_status()
            if not xst.get("is_acting", False):
                self.client.xmap(self.current_boss.map_id)

    def _find_boss_in_current_map(self, my_char: Char) -> Optional[Any]:
        if not self.current_boss:
            return None
        norm_target = normalize_str(self.current_boss.name)

        # 1. Quét trong người chơi (boss dạng Char)
        for ch in my_char.mapInfo.chars.values():
            if ch.charID != my_char.charID and not ch.is_dead:
                norm_c = normalize_str(ch.cName)
                if self.current_boss.name == "Boss Tuần Tra":
                    if any(t in norm_c for t in self.target_bosses):
                        return ch
                elif norm_c == norm_target or norm_target in norm_c or norm_c in norm_target:
                    return ch

        # 2. Quét trong quái (boss dạng Mob)
        for m in my_char.mapInfo.mobs.values():
            if getattr(m, "hp", 0) > 0 and getattr(m, "status", 0) not in (0, 1):
                norm_m = normalize_str(getattr(m, "template_name", ""))
                if self.current_boss.name == "Boss Tuần Tra":
                    if getattr(m, "isBoss", False) or any(t in norm_m for t in self.target_bosses):
                        return m
                elif norm_m == norm_target or norm_target in norm_m or norm_m in norm_target:
                    return m
        return None

    def _handle_bh_scanning(self, my_char: Char) -> None:
        if not self.current_boss:
            self.bh_state = self.STATE_BH_IDLE
            return

        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)
        curr_zone_id = getattr(my_char.mapInfo, "zoneID", -1)

        # 1. Kiểm tra xem đã có đồng đội tìm thấy Boss này ở map hiện tại chưa
        active_boss = SharedHuntCoordinator.get_active_boss(self.current_boss.name)
        if active_boss and active_boss.get("map_id") == curr_map_id and not active_boss.get("is_died", False):
            target_zone = active_boss.get("zone_id", -1)
            if target_zone >= 0:
                self.current_boss.zone_id = target_zone
                if curr_zone_id != target_zone:
                    self._log_auto(f"[~] Đồng đội đã tìm thấy Boss '{self.current_boss.name}' ở Khu {target_zone}! Chuyển khu tới pem...", is_important=True)
                    if self.client and hasattr(self.client, "change_zone"):
                        self.client.change_zone(target_zone)
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_COMBAT
                return

        # 2. Kiểm tra ngay nếu Boss có ở khu hiện tại
        found = self._find_boss_in_current_map(my_char)
        if found is not None:
            self.current_boss.zone_id = curr_zone_id
            if hasattr(found, "cName"):
                self.current_boss.name = found.cName
            target_x = getattr(found, "cx", getattr(found, "x", my_char.cx))
            target_y = getattr(found, "cy", getattr(found, "y", my_char.cy))
            self.last_boss_pos = (target_x, target_y)
            self._log_auto(f"[+] PHÁT HIỆN BOSS '{self.current_boss.name}' tại Khu {curr_zone_id}! Báo toàn đội cùng pem!", is_important=True)
            SharedHuntCoordinator.report_boss_found(self, self.current_boss, curr_map_id, curr_zone_id, (target_x, target_y))
            self._reset_boss_fight_tracking()
            self.bh_state = self.STATE_BH_COMBAT
            return

        # 3. Chia việc dò khu thông minh với SharedHuntCoordinator
        zones = my_char.mapInfo.zones
        zone_ids = [z.zoneId for z in zones if z.zoneId > 0] if zones else list(range(1, 25))

        # Claim khu tiếp theo chưa có acc nào quét
        next_zone = SharedHuntCoordinator.claim_next_zone(
            self._tag(),
            curr_map_id,
            zone_ids,
            exclude_zones=self.scanned_zones,
            current_zone=curr_zone_id,
        )

        if next_zone is not None:
            self.scanned_zones.add(next_zone)
            if self.client and hasattr(self.client, "change_zone"):
                self.client.change_zone(next_zone)
                delay = random.uniform(self.min_scan_zone_delay, self.max_scan_zone_delay)
                time.sleep(delay)

            # Cập nhật trạng thái đã quét xong
            SharedHuntCoordinator.release_zone(self._tag(), curr_map_id, next_zone, scanned=True)

            # Kiểm tra xem boss có ở khu mới này không
            found = self._find_boss_in_current_map(my_char)
            if found is not None:
                self.current_boss.zone_id = next_zone
                if hasattr(found, "cName"):
                    self.current_boss.name = found.cName
                target_x = getattr(found, "cx", getattr(found, "x", my_char.cx))
                target_y = getattr(found, "cy", getattr(found, "y", my_char.cy))
                self.last_boss_pos = (target_x, target_y)
                self._log_auto(f"[+] PHÁT HIỆN BOSS '{self.current_boss.name}' tại Khu {next_zone}! Báo toàn đội cùng pem!", is_important=True)
                SharedHuntCoordinator.report_boss_found(self, self.current_boss, curr_map_id, next_zone, (target_x, target_y))
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_COMBAT
                return
        else:
            # Đã quét hết toàn bộ khu ở map này mà không thấy Boss
            if self.current_boss.name == "Boss Tuần Tra":
                self.patrol_map_index += 1
                self.bh_state = self.STATE_BH_PATROL
            else:
                self._log_auto(f"Đã quét hết các khu không thấy Boss '{self.current_boss.name}'. Đánh dấu Boss đã chết!")
                self.current_boss.is_died = True
                SharedHuntCoordinator.clear_boss(self.current_boss.name)
                self.current_boss = None
                self.bh_state = self.STATE_BH_IDLE

    def _handle_bh_combat(self, my_char: Char) -> None:
        """Đấm Boss liên tục bằng combo 3 skill và giám sát HP boss (phát hiện boss ảo/kẹt)."""
        if not self.current_boss:
            self.bh_state = self.STATE_BH_IDLE
            return

        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)
        curr_zone_id = getattr(my_char.mapInfo, "zoneID", -1)

        # 1. Đảm bảo ở đúng khu vực của Boss
        if self.current_boss.zone_id >= 0 and curr_zone_id != self.current_boss.zone_id:
            if self.client and hasattr(self.client, "change_zone"):
                self.client.change_zone(self.current_boss.zone_id)
                time.sleep(0.3)
                return

        boss_target = self._find_boss_in_current_map(my_char)
        now = time.time()

        # 2. Kiểm tra nếu Boss đã chết hoặc biến mất
        is_dead = False
        if boss_target is None:
            if self.boss_entry_time > 0 and (now - self.boss_entry_time) > 2.5:
                is_dead = True
        elif getattr(boss_target, "is_dead", False) or getattr(boss_target, "isDie", False) or getattr(boss_target, "cHP", 1) <= 0:
            is_dead = True

        if is_dead:
            self.current_boss.is_died = True
            self.boss_kill_count += 1
            b_map_name = self.current_boss.map_name or get_map_name(curr_map_id)
            self.boss_kill_history.append({
                "name": self.current_boss.name,
                "map_name": b_map_name,
                "time": time.strftime("%H:%M:%S"),
            })
            if len(self.boss_kill_history) > 30:
                self.boss_kill_history = self.boss_kill_history[-30:]

            # Thông báo cho toàn đội biết Boss đã chết
            SharedHuntCoordinator.report_boss_died(self, self.current_boss.name, curr_map_id, curr_zone_id)

            if self.auto_loot_boss:
                self._log_auto(f"[=] Boss '{self.current_boss.name}' đã bị tiêu diệt! Chờ 2s rồi nhặt đồ rơi...", is_important=True)
                self.bh_state = self.STATE_BH_LOOTING
                self.boss_death_time = now
                self.looting_start_time = now
                self.pick_item_attempts = 0
                self.last_pick_item_time = 0.0
            else:
                self.current_boss = None
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_IDLE
            return

        # 3. Theo dõi biến động HP & phát hiện Boss ảo / Boss kẹt (C# AutoFarmBossNappa)
        if self.boss_entry_time == 0.0:
            self.boss_entry_time = now
            self.last_boss_hp = getattr(boss_target, "cHP", -1)
            self.last_boss_hp_check_time = now
            self.boss_damaged = False
            self.consecutive_no_damage_count = 0

        current_hp = getattr(boss_target, "cHP", 0)
        if (now - self.last_boss_hp_check_time) >= self.HP_CHECK_INTERVAL_S:
            self.last_boss_hp_check_time = now
            if self.last_boss_hp != -1:
                if current_hp < self.last_boss_hp:
                    self.boss_damaged = True
                    self.consecutive_no_damage_count = 0
                    self.last_boss_hp = current_hp
                    self.bh_status_message = f"Đang pem Boss '{self.current_boss.name}' (HP: {format_big_number(current_hp)})"
                elif current_hp == self.last_boss_hp:
                    self.consecutive_no_damage_count += 1
                    self.bh_status_message = f"Pem Boss '{self.current_boss.name}' - HP không đổi lần {self.consecutive_no_damage_count} (HP: {format_big_number(current_hp)})"

                    # Kiểm tra Boss ảo: chưa từng mất máu sau 10s hoặc 5 lần kiểm tra
                    if not self.boss_damaged and ((now - self.boss_entry_time) >= self.BOSS_NO_DAMAGE_TIMEOUT_S or self.consecutive_no_damage_count >= self.MAX_CONSECUTIVE_NO_DAMAGE):
                        self._log_auto(f"[!] Boss '{self.current_boss.name}' là Boss ảo hoặc không thể đánh (10s không giảm HP). Bỏ qua khu {curr_zone_id}!", is_alert=True)
                        SharedHuntCoordinator.release_zone(self._tag(), curr_map_id, curr_zone_id, scanned=True)
                        self.scanned_zones.add(curr_zone_id)
                        self._reset_boss_fight_tracking()
                        self.bh_state = self.STATE_BH_SCANNING
                        return

                    # Kiểm tra Boss kẹt: đang đánh mà kẹt máu 3 lần kiểm tra liên tiếp
                    if self.boss_damaged and self.consecutive_no_damage_count >= self.MAX_CONSECUTIVE_NO_DAMAGE_IN_FIGHT:
                        self._log_auto(f"[!] Boss '{self.current_boss.name}' bị kẹt / bất tử trong khi đánh. Bỏ qua khu {curr_zone_id}!", is_alert=True)
                        SharedHuntCoordinator.release_zone(self._tag(), curr_map_id, curr_zone_id, scanned=True)
                        self.scanned_zones.add(curr_zone_id)
                        self._reset_boss_fight_tracking()
                        self.bh_state = self.STATE_BH_SCANNING
                        return
                else:
                    self.last_boss_hp = current_hp
                    self.consecutive_no_damage_count = 0
            else:
                self.last_boss_hp = current_hp

        target_x = getattr(boss_target, "cx", getattr(boss_target, "x", my_char.cx))
        target_y = getattr(boss_target, "cy", getattr(boss_target, "y", my_char.cy))
        self.last_boss_pos = (target_x, target_y)

        # 4. Teleport áp sát
        if my_char.distance_to(target_x, target_y) > 40:
            self.teleport(target_x, target_y)

        # 5. Focus & Tấn công liên tục bằng combo 3 skill xoay vòng
        if (now - self.last_attack_time) >= 0.12:
            self.last_attack_time = now
            if isinstance(boss_target, Mob):
                my_char.focus_mob(boss_target)
            else:
                my_char.focus_char(boss_target)
            self.attack_target(boss_target)

    def _handle_bh_looting(self, my_char: Char) -> None:
        """Nhặt vật phẩm rơi từ Boss theo cơ chế Mod C# (chờ 2s, lọc đồ, retry 5 lần)."""
        now = time.time()
        elapsed = now - self.boss_death_time

        # Duy trì vị trí boss chết
        if self.last_boss_pos:
            bx, by = self.last_boss_pos
            if my_char.distance_to(bx, by) > 50:
                self.teleport(bx, by)

        # 1. Chờ 2 giây sau khi boss chết để server drop đồ xuống mặt đất
        if elapsed < self.WAIT_AFTER_BOSS_DEATH_S:
            remaining_ms = int((self.WAIT_AFTER_BOSS_DEATH_S - elapsed) * 1000)
            self.bh_status_message = f"Chờ server drop vật phẩm ({remaining_ms}ms)..."
            return

        # 2. Lấy danh sách item dưới đất
        all_items = list(my_char.mapInfo.items.values())
        if not all_items:
            if elapsed >= 3.5 or self.pick_item_attempts > 0:
                self._log_auto(f"[=] Kết thúc nhặt đồ Boss. Tổng chiến lợi phẩm: {self.boss_looted_items_count} món.", is_important=True)
                self.current_boss = None
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_IDLE
            return

        # Lọc vật phẩm giá trị từ Boss
        eligible_items = []
        for it in all_items:
            if it.itemMapID in self.blocked_items:
                continue
            # Đồ của mình
            if getattr(it, "playerId", -1) == my_char.charID:
                eligible_items.append(it)
            # Găng thiên sứ (1070) và mảnh thiên sứ/thần linh (1066 - 1073)
            elif it.template_id == self.GANG_THIEN_SU_ITEM_ID or (1066 <= it.template_id <= 1073):
                eligible_items.append(it)
            # Ngọc (77, 861, 862), Ngọc Rồng (14 - 20), Sao pha lê (441 - 447), Vàng (188 - 190)
            elif it.template_id in (77, 861, 862) or (14 <= it.template_id <= 20) or (441 <= it.template_id <= 447) or (188 <= it.template_id <= 190):
                eligible_items.append(it)
            # Đồ rơi tự do không chủ sở hữu
            elif getattr(it, "playerId", -1) in (-1, 0) and not self.pick_gem_only:
                eligible_items.append(it)

        if not eligible_items:
            if elapsed >= 3.5 or self.pick_item_attempts > 0:
                self._log_auto("[=] Không còn vật phẩm giá trị từ Boss trong khu.", is_important=True)
                self.current_boss = None
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_IDLE
            return

        # 3. Giãn cách nhặt: 800ms
        if (now - self.last_pick_item_time) < self.PICK_ITEM_DELAY_S:
            self.bh_status_message = f"Đang nhặt đồ Boss ({self.pick_item_attempts}/{self.MAX_PICK_ATTEMPTS})..."
            return

        # 4. Chọn item gần nhất và teleport tới nhặt
        target_item = min(eligible_items, key=lambda it: my_char.distance_to(it.x, it.y))
        self.teleport(target_item.x, target_item.y)

        svc = self._service()
        if svc:
            svc.pickItem(target_item.itemMapID)

        self.last_pick_item_time = now
        self.pick_item_attempts += 1
        self.boss_looted_items_count += 1

        it_name = get_item_name(target_item.template_id) or f"Item #{target_item.template_id}"
        b_name = self.current_boss.name if self.current_boss else "Boss"
        m_name = self.current_boss.map_name if self.current_boss else get_map_name(getattr(my_char.mapInfo, "mapID", -1))

        self.boss_looted_items_history.append({
            "item_name": it_name,
            "template_id": target_item.template_id,
            "boss_name": b_name,
            "map_name": m_name,
            "time": time.strftime("%H:%M:%S"),
        })
        if len(self.boss_looted_items_history) > 30:
            self.boss_looted_items_history = self.boss_looted_items_history[-30:]

        self._log_auto(f"[+] Đã nhặt: {it_name} rơi từ Boss '{b_name}' (lần {self.pick_item_attempts}/{self.MAX_PICK_ATTEMPTS})!", is_important=True)

        if self.pick_item_attempts >= self.MAX_PICK_ATTEMPTS:
            self._log_auto(f"[=] Đã nhặt đủ {self.MAX_PICK_ATTEMPTS} lần quy định, hoàn tất nhặt đồ!", is_important=True)
            self.current_boss = None
            self._reset_boss_fight_tracking()
            self.bh_state = self.STATE_BH_IDLE

    def notify_boss_spotted(self, boss: Boss, map_id: int, zone_id: int, pos: Tuple[int, int], reporter_tag: str = "") -> None:
        """Được gọi bởi SharedHuntCoordinator khi 1 acc đồng đội phát hiện boss."""
        if not self.is_boss_hunter_enabled:
            return
        if not self.is_target_boss(boss) and self.current_boss and self.current_boss.name != boss.name:
            return

        my_char = self._get_my_char()
        curr_map = getattr(my_char.mapInfo, "mapID", -1) if my_char and my_char.mapInfo else -1

        self.current_boss = boss
        self.current_boss.map_id = map_id
        self.current_boss.zone_id = zone_id
        self.last_boss_pos = pos

        tag_str = f"[{reporter_tag}] " if reporter_tag else ""
        if curr_map == map_id:
            curr_zone = getattr(my_char.mapInfo, "zoneID", -1) if my_char and my_char.mapInfo else -1
            if curr_zone != zone_id:
                self._log_auto(f"[~] Đồng đội {tag_str}phát hiện Boss '{boss.name}' ở Khu {zone_id}! Đang chuyển khu tới hỗ trợ pem...", is_important=True)
                if self.client and hasattr(self.client, "change_zone"):
                    self.client.change_zone(zone_id)
            else:
                self._log_auto(f"[~] Đã ở cùng Khu {zone_id} với Boss '{boss.name}'! Tập hợp pem Boss!", is_important=True)
            self._reset_boss_fight_tracking()
            self.bh_state = self.STATE_BH_COMBAT
        else:
            self._log_auto(f"[~] Đồng đội {tag_str}phát hiện Boss '{boss.name}' tại map {map_id} ({boss.map_name}) khu {zone_id}! Di chuyển tới chi viện!", is_important=True)
            self.bh_state = self.STATE_BH_MOVING
            if self.client and hasattr(self.client, "xmap"):
                self.client.xmap(map_id)

    def notify_boss_killed(self, boss_name: str, map_id: int, zone_id: int, reporter_tag: str = "") -> None:
        """Được gọi bởi SharedHuntCoordinator khi Boss đã bị tiêu diệt."""
        if not self.is_boss_hunter_enabled or not self.current_boss:
            return
        norm_curr = normalize_str(self.current_boss.name)
        norm_target = normalize_str(boss_name)
        if norm_curr == norm_target or norm_target in norm_curr or norm_curr in norm_target:
            self.current_boss.is_died = True
            self.boss_kill_count += 1
            b_map_name = self.current_boss.map_name or get_map_name(map_id)
            self.boss_kill_history.append({
                "name": self.current_boss.name,
                "map_name": b_map_name,
                "time": time.strftime("%H:%M:%S"),
            })
            if len(self.boss_kill_history) > 30:
                self.boss_kill_history = self.boss_kill_history[-30:]

            if self.auto_loot_boss:
                self._log_auto(f"[=] Boss '{self.current_boss.name}' đã bị hạ! Chờ 2s rồi nhặt đồ rơi...", is_important=True)
                self.bh_state = self.STATE_BH_LOOTING
                now = time.time()
                self.boss_death_time = now
                self.looting_start_time = now
                self.pick_item_attempts = 0
                self.last_pick_item_time = 0.0
            else:
                self.current_boss = None
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_IDLE

    # ==========================================================================
    # 6. NHIỆM VỤ BÒ MỘNG HẰNG NGÀY (AUTO QUEST BO MONG)
    # ==========================================================================
    def start_auto_quest(self) -> None:
        self.is_quest_enabled = True
        self.quest_start_time = time.time()
        self.quests_completed = 0
        self.quest_total_kills = 0
        self.quest_state = AutoQuestState.GET_QUEST
        self._log_auto("Bắt đầu Auto Nhiệm vụ Bò Mộng hằng ngày!")

    def stop_auto_quest(self) -> None:
        self.is_quest_enabled = False
        self.quest_state = AutoQuestState.IDLE
        self._log_auto("Đã dừng Auto Nhiệm vụ Bò Mộng.")

    def toggle_auto_quest(self) -> bool:
        if self.is_quest_enabled:
            self.stop_auto_quest()
        else:
            self.start_auto_quest()
        return self.is_quest_enabled

    def _parse_quest_info(self, menu_text: str) -> None:
        lower_text = (menu_text or "").lower()
        if "hết nhiệm vụ cho hôm nay" in lower_text:
            self._log_auto("Đã hết nhiệm vụ hôm nay. Hoàn tất!")
            self.stop_auto_quest()
            return

        m_rem = re.search(r"số nhiệm vụ còn lại của hôm nay\s+(\d+)/(\d+)", lower_text)
        if m_rem:
            self.quest_info.quests_remaining = int(m_rem.group(1))
            self.quest_info.quests_total = int(m_rem.group(2))
            if self.quest_info.quests_remaining <= 0:
                self.stop_auto_quest()
                return

        m_task = re.search(r"nhiệm vụ của bạn\s+tiêu diệt\s+\d+\s+([^\n]+)", lower_text)
        if m_task:
            self.quest_info.is_valid = True
            self.quest_info.mob_name = m_task.group(1).strip()

        m_prog = re.search(r"tiến độ nhiệm vụ\s+(\d+)/(\d+)", lower_text)
        if m_prog:
            self.quest_info.initial_count = int(m_prog.group(1))
            self.quest_info.target_count = int(m_prog.group(2))
            self.quest_info.kill_count = 0

    def _increment_quest_kill_count(self, mob_template_id: int) -> None:
        if not self.is_quest_enabled or not self.quest_info.is_valid:
            return
        target = self.quest_info.mob_name.lower().strip()
        expected_ids = MOB_LOCATION_DATA.get(target)
        if expected_ids and expected_ids[1] == mob_template_id:
            self.quest_info.kill_count += 1
            self.quest_total_kills += 1

    def _step_auto_quest(self, my_char: Char) -> None:
        """Thực thi một bước trong máy trạng thái Bò Mộng."""
        curr_map = getattr(my_char.mapInfo, "mapID", -1)

        # 1. Trả nhiệm vụ
        if self.quest_state == AutoQuestState.REPORT_QUEST or (
            self.quest_info.is_valid and self.quest_info.current_progress >= self.quest_info.target_count
        ):
            if curr_map != BO_MONG_MAP_ID:
                if self.client and hasattr(self.client, "xmap"):
                    self.client.xmap(BO_MONG_MAP_ID)
                return
            npc = my_char.mapInfo.find_npc(BO_MONG_NPC_TEMPLATE_ID)
            if npc:
                self.teleport(int(npc["x"]) - 15, int(npc["y"]))
                svc = self._service()
                if svc:
                    svc.openMenu(BO_MONG_NPC_TEMPLATE_ID)
                    time.sleep(0.4)
                    svc.confirmMenu(BO_MONG_NPC_TEMPLATE_ID, 1)
                    self.quests_completed += 1
                    self.quest_state = AutoQuestState.GET_QUEST
            return

        # 2. Nhận nhiệm vụ
        if self.quest_state == AutoQuestState.GET_QUEST:
            if curr_map != BO_MONG_MAP_ID:
                if self.client and hasattr(self.client, "xmap"):
                    self.client.xmap(BO_MONG_MAP_ID)
                return
            npc = my_char.mapInfo.find_npc(BO_MONG_NPC_TEMPLATE_ID)
            if npc:
                self.teleport(int(npc["x"]) - 15, int(npc["y"]))
                svc = self._service()
                if svc:
                    svc.openMenu(BO_MONG_NPC_TEMPLATE_ID)
                    time.sleep(0.4)
                    svc.confirmMenu(BO_MONG_NPC_TEMPLATE_ID, 1)
                    time.sleep(0.4)
                    svc.confirmMenu(BO_MONG_NPC_TEMPLATE_ID, 4)
                    time.sleep(1.0)
                    if self.quest_info.is_valid:
                        self.quest_state = AutoQuestState.NAVIGATE_TO_MAP
            return

        # 3. Di chuyển đến map nhiệm vụ
        if self.quest_state == AutoQuestState.NAVIGATE_TO_MAP:
            target = self.quest_info.mob_name.lower().strip()
            loc = MOB_LOCATION_DATA.get(target)
            if not loc:
                return
            target_map, _ = loc
            if curr_map != target_map:
                if self.client and hasattr(self.client, "xmap"):
                    self.client.xmap(target_map)
            else:
                self.quest_state = AutoQuestState.EXECUTE_QUEST
            return

        # 4. Thực hiện đánh quái nhiệm vụ
        if self.quest_state == AutoQuestState.EXECUTE_QUEST:
            target = self.quest_info.mob_name.lower().strip()
            loc = MOB_LOCATION_DATA.get(target)
            if not loc:
                return
            _, expected_template = loc
            target_mob = my_char.mapInfo.find_mob(expected_template, from_x=my_char.cx, from_y=my_char.cy)
            if target_mob:
                my_char.focus_mob(target_mob)
                self.teleport(target_mob.x, target_mob.y)
                now = time.time()
                if (now - self.last_attack_time) >= 0.12:
                    self.last_attack_time = now
                    self.attack_target(target_mob)

    # ==========================================================================
    # 7. AUTO SHUTTLE (DI CHUYỂN QUA LẠI 2 MAP)
    # ==========================================================================
    def start_shuttle(self, map_a: int, map_b: int, rounds: int = 0) -> bool:
        if map_a == map_b:
            return False
        with self._lock:
            self.shuttle_map_a = map_a
            self.shuttle_map_b = map_b
            self.shuttle_rounds = rounds
            self.shuttle_legs_done = 0
            self.is_shuttle_enabled = True
            self.shuttle_status_message = "Đang khởi động"
            self._log_auto(f"Bắt đầu Shuttle: Map {map_a} <-> Map {map_b} ({rounds} lượt)!")
            return True

    def stop_shuttle(self) -> None:
        with self._lock:
            self.is_shuttle_enabled = False
            self.shuttle_status_message = "Đã dừng"
            self._log_auto("Đã dừng Shuttle.")

    def _step_shuttle(self, my_char: Char) -> None:
        curr_map = getattr(my_char.mapInfo, "mapID", -1)
        if self.shuttle_target is None:
            self.shuttle_target = self.shuttle_map_b if curr_map == self.shuttle_map_a else self.shuttle_map_a

        if curr_map == self.shuttle_target:
            self.shuttle_legs_done += 1
            if self.shuttle_rounds > 0 and self.shuttle_legs_done >= self.shuttle_rounds:
                self.stop_shuttle()
                return
            # Đổi sang map đích tiếp theo
            self.shuttle_target = self.shuttle_map_b if self.shuttle_target == self.shuttle_map_a else self.shuttle_map_a
            time.sleep(1.0)

        if self.client and hasattr(self.client, "xmap"):
            xst = self.client.xmap_status()
            if not xst.get("is_acting", False):
                self.client.xmap(self.shuttle_target)

    # ==========================================================================
    # 8. AUTO DÙNG ITEM ĐỊNH KỲ (AUTO USE ITEM)
    # ==========================================================================
    def start_auto_use_item(self, item_id: int, interval_minutes: float) -> Tuple[bool, str]:
        if item_id <= 0:
            return False, "Template ID của vật phẩm phải lớn hơn 0!"
        if interval_minutes <= 0:
            return False, "Khoảng thời gian phải lớn hơn 0 phút!"

        self.auto_use_item_id = item_id
        self.auto_use_interval_minutes = interval_minutes
        self.auto_use_item_enabled = True
        self.auto_use_count = 0
        self.auto_use_last_time = 0.0
        self._log_auto(f"Bật Auto dùng Item ID {item_id} mỗi {interval_minutes:g} phút!")
        return True, f"Đã kích hoạt Auto dùng item ID {item_id} mỗi {interval_minutes:g} phút!"

    def stop_auto_use_item(self) -> Tuple[bool, str]:
        if not self.auto_use_item_enabled:
            return False, "Auto dùng item hiện đang tắt!"
        self.auto_use_item_enabled = False
        msg = f"Đã dừng Auto dùng item ID {self.auto_use_item_id} (đã dùng {self.auto_use_count} lần)."
        self._log_auto(msg)
        return True, msg

    def _find_item_in_bag(self, item_id: int) -> Optional[Item]:
        my_char = self._get_my_char()
        if not my_char or not my_char.arrItemBag:
            return None
        for it in my_char.arrItemBag:
            if it is not None and getattr(it, "template_id", -1) == item_id:
                return it
        return None

    def _step_auto_use_item(self) -> None:
        if not self.auto_use_item_id:
            return
        now = time.time()
        interval_sec = self.auto_use_interval_minutes * 60.0

        if self.auto_use_last_time == 0.0 or (now - self.auto_use_last_time) >= interval_sec:
            item = self._find_item_in_bag(self.auto_use_item_id)
            if item is not None:
                svc = self._service()
                if svc:
                    svc.useItem(0, 1, item.index_ui, item.template_id)
                    self.auto_use_count += 1
                    self.auto_use_last_time = now
                    self._log_auto(f"Đã sử dụng item ID {self.auto_use_item_id} (slot {item.index_ui}). Lần dùng: #{self.auto_use_count}.")
            else:
                if (now - self.auto_use_last_alert) >= 20.0:
                    self._log_auto(f"CẢNH BÁO: Không tìm thấy item ID {self.auto_use_item_id} trong balo!", is_alert=True)
                    self.auto_use_last_alert = now

    # ==========================================================================
    # CÁC HÀM GET_STATUS & TƯƠNG THÍCH NGƯỢC (BACKWARD COMPATIBILITY)
    # ==========================================================================
    def get_combat_status(self) -> Dict[str, Any]:
        return {
            "is_ak": self.is_ak,
            "is_tansat": self.is_tansat,
            "tansat_mode": self.tansat_mode,
            "avoid_super_mob": self.avoid_super_mob,
            "auto_pick": self.auto_pick,
            "pick_gem_only": self.pick_gem_only,
            "auto_pean": self.auto_pean,
            "auto_revive": self.auto_revive,
        }

    def get_hunt_status(self) -> Dict[str, Any]:
        curr_patrol = self.patrol_maps[self.patrol_map_index] if self.patrol_maps and self.patrol_map_index < len(self.patrol_maps) else -1
        my_char = self._get_my_char()
        gender = getattr(my_char, "cgender", 0) if my_char else 0
        try:
            gender = int(gender)
        except Exception:
            gender = 0
        current_combo = self.combat_combo_skills or list(self.TANSAT_SKILLS_BY_GENDER.get(gender, (0, 2, 4)))
        curr_map = getattr(my_char.mapInfo, "mapID", -1) if my_char and my_char.mapInfo else -1
        coop_scanners = SharedHuntCoordinator.get_active_scanners_count(curr_map)

        return {
            "is_enabled": self.is_boss_hunter_enabled,
            "state": self.bh_state,
            "status_message": self.bh_status_message,
            "current_boss": self.current_boss.to_dict() if self.current_boss else None,
            "hunt_all": self.hunt_all,
            "target_bosses": list(self.target_bosses),
            "auto_loot": self.auto_loot_boss,
            "auto_revive": self.auto_revive,
            "auto_patrol": self.auto_patrol,
            "patrol_map_id": curr_patrol,
            "patrol_map_name": get_map_name(curr_patrol) if curr_patrol != -1 else "",
            "boss_kill_count": self.boss_kill_count,
            "boss_looted_items_count": self.boss_looted_items_count,
            "boss_looted_items_history": list(self.boss_looted_items_history[-5:]),
            "combo_skills": current_combo,
            "cooperative_scanners": coop_scanners,
        }

    def get_quest_status(self) -> Dict[str, Any]:
        elapsed = int(time.time() - self.quest_start_time) if self.quest_start_time else 0
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return {
            "is_running": self.is_quest_enabled,
            "state": self.quest_state.value,
            "quests_completed": self.quests_completed,
            "total_kills": self.quest_total_kills,
            "time_str": f"{h}h{m:02d}m{s:02d}s" if h > 0 else f"{m}m{s:02d}s",
            "quest": str(self.quest_info),
        }

    def get_shuttle_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_shuttle_enabled,
            "map_a": f"{get_map_name(self.shuttle_map_a)} ({self.shuttle_map_a})" if self.shuttle_map_a is not None else "?",
            "map_b": f"{get_map_name(self.shuttle_map_b)} ({self.shuttle_map_b})" if self.shuttle_map_b is not None else "?",
            "legs_done": self.shuttle_legs_done,
            "rounds": self.shuttle_rounds,
            "status_message": self.shuttle_status_message,
        }

    def get_auto_revive_status(self) -> Dict[str, Any]:
        my_char = self._get_my_char()
        return {
            "is_enabled": self.auto_revive,
            "mode": self.revive_mode,
            "mode_str": "Ngọc tại chỗ" if self.revive_mode == "gem" else "Về Thành",
            "revive_count": self.revive_count,
            "is_currently_dead": my_char.is_dead if my_char else False,
        }

    def get_auto_use_item_status(self) -> Dict[str, Any]:
        remaining = 0.0
        if self.auto_use_item_enabled and self.auto_use_last_time > 0.0:
            elapsed = time.time() - self.auto_use_last_time
            remaining = max(0.0, (self.auto_use_interval_minutes * 60.0) - elapsed)
        item = self._find_item_in_bag(self.auto_use_item_id) if self.auto_use_item_id else None
        return {
            "is_enabled": self.auto_use_item_enabled,
            "item_template_id": self.auto_use_item_id,
            "interval_minutes": self.auto_use_interval_minutes,
            "use_count": self.auto_use_count,
            "has_item_in_bag": item is not None,
            "remaining_seconds": remaining,
        }

    # Hỗ trợ tương thích ngược với các tên gọi thuộc tính cũ
    @property
    def is_running(self) -> bool:
        """Alias cho AutoQuest."""
        return self.is_quest_enabled

    @property
    def is_enabled(self) -> bool:
        """Alias cho BossHunter."""
        return self.is_boss_hunter_enabled

    @property
    def mode(self) -> str:
        """Alias cho AutoReviveManager.mode."""
        return self.revive_mode

    @property
    def is_hunting(self) -> bool:
        """Alias cho BossHunter.is_hunting."""
        return self.is_boss_hunter_enabled

    def enable(self) -> None:
        """Alias cho AutoReviveManager.enable()."""
        self.auto_revive = True

    def disable(self) -> None:
        """Alias cho AutoReviveManager.disable()."""
        self.auto_revive = False

    def toggle(self, enable: Optional[bool] = None) -> bool:
        """Alias cho AutoReviveManager.toggle()."""
        return self.toggle_auto_revive(enable)

    def start_auto(self, item_id: int, interval_minutes: float) -> Tuple[bool, str]:
        """Alias cho AutoUseItemManager.start_auto."""
        return self.start_auto_use_item(item_id, interval_minutes)

    def start(self, *args, **kwargs) -> Any:
        """Đa hình hỗ trợ gọi start() cũ."""
        if args and isinstance(args[0], (list, set)):
            return self.start_auto_hunt(targets=list(args[0]))
        if len(args) >= 2 and isinstance(args[0], int) and isinstance(args[1], int):
            return self.start_shuttle(args[0], args[1], args[2] if len(args) > 2 else 0)
        if self.is_quest_enabled or kwargs.get("quest"):
            return self.start_auto_quest()
        return self.start_auto_hunt()

    def stop(self) -> Any:
        """Đa hình hỗ trợ gọi stop() cũ."""
        self.stop_auto_hunt()
        self.stop_auto_quest()
        self.stop_shuttle()
        self.is_ak = False
        self.is_tansat = False

    def get_status(self) -> Dict[str, Any]:
        """Trả về status tổng hợp."""
        return {
            "combat": self.get_combat_status(),
            "hunt": self.get_hunt_status(),
            "quest": self.get_quest_status(),
            "shuttle": self.get_shuttle_status(),
            "revive": self.get_auto_revive_status(),
            "use_item": self.get_auto_use_item_status(),
            "train_pet": {
                "enabled": self.train_pet.is_enabled,
                "mode": self.train_pet.mode.name,
                "attack_mode": self.train_pet.attack_mode.name,
            },
            "train_new_acc": {
                "enabled": self.train_new_acc.is_enabled,
            },
        }

    def start_train_pet(self, mode: str = "normal") -> Tuple[bool, str]:
        """Bật Auto Úp Đệ Tử ('normal', 'avoid', 'kaioken')."""
        mode_lower = mode.lower().strip()
        pet_mode = AutoTrainPetMode.NORMAL
        if mode_lower in ("avoid", "avoid_super", "avoid_super_mob", "ne", "nesieuquai"):
            pet_mode = AutoTrainPetMode.AVOID_SUPER_MOB
        elif mode_lower in ("kaioken", "kaio", "kk"):
            pet_mode = AutoTrainPetMode.KAIOKEN
        elif mode_lower in ("off", "stop", "tat", "disable"):
            self.train_pet.set_mode(AutoTrainPetMode.DISABLED)
            return True, "Đã tắt Auto Úp Đệ Tử."

        self.train_pet.set_mode(pet_mode)
        return True, f"Đã bật Auto Úp Đệ Tử chế độ '{pet_mode.name}'."

    def stop_train_pet(self) -> Tuple[bool, str]:
        """Tắt Auto Úp Đệ Tử."""
        self.train_pet.set_mode(AutoTrainPetMode.DISABLED)
        return True, "Đã tắt Auto Úp Đệ Tử."

    def set_train_pet_attack_mode(self, mode: str = "mob") -> Tuple[bool, str]:
        """Cài đặt chế độ đánh khi đệ kêu lười ('mob', 'pet', 'me')."""
        m_lower = mode.lower().strip()
        atk_mode = AutoTrainPetAttackMode.ATTACK_CLOSEST_MOB
        if m_lower in ("pet", "mypet", "detu"):
            atk_mode = AutoTrainPetAttackMode.ATTACK_MY_PET
        elif m_lower in ("me", "myself", "banthan"):
            atk_mode = AutoTrainPetAttackMode.ATTACK_MYSELF

        self.train_pet.set_attack_mode(atk_mode)
        return True, f"Đã đổi chế độ đánh khi đệ lười thành '{atk_mode.name}'."

    def start_train_new_account(self) -> Tuple[bool, str]:
        """Bật Auto Làm Nhiệm Vụ Tân Thủ (NV 0 -> NV 11)."""
        self.train_new_acc.set_state(True)
        return True, "Đã bật Auto Tân Thủ (Làm nhiệm vụ sơ sinh 0 -> 11)."

    def stop_train_new_account(self) -> Tuple[bool, str]:
        """Tắt Auto Làm Nhiệm Vụ Tân Thủ."""
        self.train_new_acc.set_state(False)
        return True, "Đã tắt Auto Tân Thủ."
