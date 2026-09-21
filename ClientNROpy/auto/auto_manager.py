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

from ..models.boss import Boss
from ..models.char import Char
from ..models.item import Item
from ..models.item_map import ItemMap
from ..models.mob import Mob
from ..models.waypoint import Waypoint
from ..xmap.map_data import MAP_NAMES, get_map_name, normalize_str, resolve_map_id
from .auto_train_pet import AutoTrainPet, AutoTrainPetMode, AutoTrainPetAttackMode
from .auto_train_new_account import AutoTrainNewAccount
from ..game_data import get_item_name, format_big_number, SKILL_NAMES, MOB_NAMES


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
        self.mob_template_id: int = -1
        self.map_name: str = ""
        self.map_id: int = -1
        self.target_count: int = 0
        self.initial_count: int = 0
        self.kill_count: int = 0
        self.quests_remaining: int = 0
        self.quests_total: int = 0

    @property
    def current_progress(self) -> int:
        return self.initial_count + self.kill_count

    def reset(self) -> None:
        self.is_valid = False
        self.mob_name = ""
        self.mob_template_id = -1
        self.map_name = ""
        self.map_id = -1
        self.target_count = 0
        self.initial_count = 0
        self.kill_count = 0

    def __str__(self) -> str:
        if not self.is_valid:
            return "Chưa có nhiệm vụ"
        pct = int(self.current_progress * 100 / max(1, self.target_count))
        m_info = f"tại {self.map_name}" if self.map_name else ""
        return f"Hạ {self.mob_name} {m_info} ({self.current_progress}/{self.target_count} - {pct}%)"


class AutoQuestState(Enum):
    IDLE = "Đang nghỉ"
    GET_QUEST = "Đi nhận nhiệm vụ"
    NAVIGATE_TO_MAP = "Di chuyển đến map"
    SELECT_ZONE = "Chọn khu vực"
    EXECUTE_QUEST = "Thực hiện nhiệm vụ"
    REPORT_QUEST = "Đi trả nhiệm vụ"


AutoState = AutoQuestState


# ==============================================================================
# DỮ LIỆU CẤU HÌNH NPC BÁO CÁO NHIỆM VỤ CHÍNH TUYẾN
# ==============================================================================
# {tên_nhận_diện: (npc_template_id, map_id, tên_hiển_thị)}
KNOWN_REPORT_NPCS: Dict[str, Tuple[int, int, str]] = {
    "cui": (12, 19, "Cui"),                               # Cui - Thành phố Vegeta
    "vua vegeta": (15, 19, "Vua Vegeta"),                 # Vua Vegeta - Thành phố Vegeta
    "quy lão": (13, 5, "Quy Lão Kame"),                   # Quy Lão Kame - Đảo Kame
    "kame": (13, 5, "Quy Lão Kame"),
    "trưởng lão": (14, 7, "Trưởng lão Guru"),             # Trưởng Lão Guru - Nhà Trưởng Lão
    "guru": (14, 7, "Trưởng lão Guru"),
    "thần mèo": (18, 46, "Thần mèo Karin"),               # Thần Mèo Karin - Tháp Karin
    "karin": (18, 46, "Thần mèo Karin"),
    "thần vũ trụ": (20, 48, "Thần Vũ Trụ"),               # Thần Vũ Trụ - Thánh địa Kaio
    "kaio": (20, 48, "Thần Vũ Trụ"),
    "thượng đế": (19, 45, "Thượng Đế"),                   # Thượng Đế - Điện Thượng Đế
    "bò mộng": (17, 47, "Bò Mộng"),                       # Bò Mộng - Rừng Karin
    "bà hạt mít": (21, 5, "Bà Hạt Mít"),                  # Bà Hạt Mít - Đảo Kame
    "bunma": (7, 0, "Bunma"),                             # Bunma - Làng Aru
    "dende": (8, 7, "Dende"),                             # Dende - Làng Mori
    "appule": (9, 8, "Appule"),                           # Appule - Làng Kakarot
    "dr. brief": (10, 0, "Dr. Brief"),                    # Dr. Brief - Làng Aru
    "dr brief": (10, 0, "Dr. Brief"),
    "gôhan": (0, 21, "Ông Gôhan"),                        # Ông Gôhan - Nhà Gôhan
    "moori": (2, 22, "Ông Moori"),                        # Ông Moori - Nhà Moori
    "paragus": (1, 23, "Ông Paragus"),                    # Ông Paragus - Nhà Paragus
}


class MainTaskState(Enum):
    IDLE = "Đang nghỉ"
    NAVIGATE_TO_FARM = "Di chuyển đến bãi quái"
    FARMING = "Đang đánh quái nhiệm vụ"
    FARMING_POWER = "Đang farm quái úp sức mạnh"
    WAITING_BOSS = "Đang chờ thông báo Boss"
    HUNTING_BOSS = "Đang săn Boss nhiệm vụ"
    NAVIGATE_TO_REPORT = "Di chuyển đến NPC báo cáo"
    REPORTING = "Đang báo cáo nhiệm vụ"


class MainTaskInfo:
    """Mô hình dữ liệu lưu thông tin chuỗi nhiệm vụ chính tuyến."""

    def __init__(self):
        self.is_valid: bool = False
        self.task_id: int = 0
        self.task_index: int = 0
        self.task_name: str = ""
        self.sub_name: str = ""
        self.mob_name: str = ""
        self.mob_template_id: int = -1
        self.farm_map_id: int = -1
        self.farm_map_name: str = ""
        self.target_count: int = 0
        self.current_count: int = 0
        self.is_power_task: bool = False
        self.target_power: int = 0
        self.is_boss_task: bool = False
        self.boss_name: str = ""
        self.boss_spawn_maps: List[int] = []
        self.is_report_step: bool = False
        self.report_npc_id: int = -1
        self.report_map_id: int = -1
        self.report_npc_name: str = ""
        self.report_map_name: str = ""

    def reset(self) -> None:
        self.is_valid = False
        self.task_id = 0
        self.task_index = 0
        self.task_name = ""
        self.sub_name = ""
        self.mob_name = ""
        self.mob_template_id = -1
        self.farm_map_id = -1
        self.farm_map_name = ""
        self.target_count = 0
        self.current_count = 0
        self.is_power_task = False
        self.target_power = 0
        self.is_boss_task = False
        self.boss_name = ""
        self.boss_spawn_maps = []
        self.is_report_step = False
        self.report_npc_id = -1
        self.report_map_id = -1
        self.report_npc_name = ""
        self.report_map_name = ""

    def __str__(self) -> str:
        if not self.is_valid:
            return "Chưa có nhiệm vụ phù hợp"
        if self.is_report_step:
            return f"[{self.task_name}] -> Báo cáo: Gặp {self.report_npc_name} tại {self.report_map_name} (Map {self.report_map_id})"
        if self.is_boss_task:
            loc_str = f" tại {self.farm_map_name}" if self.farm_map_name else ""
            return f"[{self.task_name}] -> Săn Boss '{self.boss_name}'{loc_str} (chờ thông báo)"
        if self.is_power_task:
            tar_sm = format_big_number(self.target_power)
            if 0 < self.target_count < 1000:
                prog = f"({self.current_count}/{self.target_count})"
            else:
                curr_sm = format_big_number(self.current_count)
                pct = int(self.current_count * 100 / max(1, self.target_power))
                prog = f"({curr_sm}/{tar_sm} - {pct}%)"
            return f"[{self.task_name}] -> Úp đạt {tar_sm} sức mạnh tại {self.farm_map_name} {prog}"
        pct = int(self.current_count * 100 / max(1, self.target_count))
        return f"[{self.task_name}] -> Tiêu diệt {self.mob_name} tại {self.farm_map_name} ({self.current_count}/{self.target_count} - {pct}%)"



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
    _farming_claims: Dict[int, Dict[int, Dict[str, Any]]] = {}  # map_id -> zone_id -> {"claimed_by": acc_tag, "last_heartbeat": float}

    @classmethod
    def get_claimed_farming_zones(cls, map_id: int, exclude_acc: str = "") -> Set[int]:
        """Lấy danh sách các khu đang có đồng đội farm quái tại map_id (trong vòng 15s gần đây)."""
        with cls._lock:
            now = time.time()
            claims = cls._farming_claims.get(map_id, {})
            occupied = set()
            for z, data in claims.items():
                claimed_by = data.get("claimed_by", "")
                if claimed_by and claimed_by != exclude_acc:
                    if (now - data.get("last_heartbeat", 0.0)) < 15.0:
                        occupied.add(z)
            return occupied

    @classmethod
    def get_farming_zone_for_acc(cls, acc_tag: str, map_id: int) -> Optional[int]:
        """Lấy khu vực mà acc_tag đang giữ để farm quái tại map_id."""
        with cls._lock:
            now = time.time()
            claims = cls._farming_claims.get(map_id, {})
            for z, data in claims.items():
                if data.get("claimed_by") == acc_tag:
                    if (now - data.get("last_heartbeat", 0.0)) < 15.0:
                        return z
            return None

    @classmethod
    def claim_farming_zone(cls, acc_tag: str, map_id: int, zone_id: int) -> None:
        """Đăng ký giữ khu farm quái/sức mạnh cho tài khoản."""
        with cls._lock:
            now = time.time()
            if map_id not in cls._farming_claims:
                cls._farming_claims[map_id] = {}
            for m_id, z_dict in list(cls._farming_claims.items()):
                for z, d in list(z_dict.items()):
                    if d.get("claimed_by") == acc_tag and (m_id != map_id or z != zone_id):
                        d["claimed_by"] = ""
                        d["last_heartbeat"] = 0.0

            cls._farming_claims[map_id][zone_id] = {
                "claimed_by": acc_tag,
                "last_heartbeat": now,
            }

    @classmethod
    def release_farming_zone(cls, acc_tag: str, map_id: Optional[int] = None) -> None:
        """Giải phóng khu farm khi chuyển map hoặc hoàn thành nhiệm vụ."""
        with cls._lock:
            for m_id, z_dict in list(cls._farming_claims.items()):
                if map_id is None or m_id == map_id:
                    for z, d in list(z_dict.items()):
                        if d.get("claimed_by") == acc_tag:
                            d["claimed_by"] = ""
                            d["last_heartbeat"] = 0.0

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
            if map_id not in cls._zone_claims:
                cls._zone_claims[map_id] = {}
            if zone_id not in cls._zone_claims[map_id]:
                cls._zone_claims[map_id][zone_id] = {
                    "claimed_by": "",
                    "claim_time": 0.0,
                    "last_scanned_time": 0.0,
                }
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

    @classmethod
    def are_all_zones_scanned(cls, map_id: int, zone_ids: List[int], max_age: float = 60.0) -> bool:
        """Kiểm tra xem toàn bộ các khu trong map đã được quét xong gần đây chưa."""
        with cls._lock:
            now = time.time()
            claims = cls._zone_claims.get(map_id, {})
            for z in zone_ids:
                c = claims.get(z)
                if not c:
                    return False
                if (now - c.get("last_scanned_time", 0.0)) > max_age:
                    return False
            return True


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
        0: (1, 9, 0),    # Trái Đất: kamejoko, kaioken, đấm
        1: (3, 12, 17, 2),   # Namek: masenko, trứng, đấm
        2: (5, 13, 4),   # Xayda: atomic, hoá hình, đấm
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

    # Khóa và bộ nhớ Boss dùng chung giữa các instance
    _lock: threading.RLock = threading.RLock()
    _active_bosses: Dict[str, Dict[str, Any]] = {}

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
        self.combat_attack_delay: float = 0.1       # Tốc độ kiểm tra và ra đòn 100ms chuẩn C# Mod NRO

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
        self.bh_waiting_zone: int = -1
        self.bh_zone_change_time: float = 0.0
        self.last_teleport_item_time: float = 0.0

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
        self.last_quest_xmap_time: float = 0.0

        # ----------------------------------------------------------------------
        # 5.1. Chuỗi Nhiệm Vụ Mới / Nhiệm Vụ Chính Tuyến (AutoMainTask FSM)
        # ----------------------------------------------------------------------
        self.is_main_task_enabled: bool = False
        self.main_task_info: MainTaskInfo = MainTaskInfo()
        self.main_task_state: MainTaskState = MainTaskState.IDLE
        self.last_main_task_xmap_time: float = 0.0
        self.last_main_task_report_time: float = 0.0
        self._last_farming_zone_change_time: float = 0.0
        self.main_task_status_message: str = "Đã dừng"

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
        if hasattr(self, "account_tag") and self.account_tag:
            return self.account_tag
        if self.client:
            return getattr(self.client, "account_tag", None) or getattr(self.client, "account_id", "Client") or "Client"
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
            from ..logger import logger
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
        if hasattr(ctrl, "on_task_callbacks"):
            ctrl.on_task_callbacks.append(self._on_task_event)

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

        # Hỗ trợ máy chủ gửi thông báo Boss qua Server Message (cmd -25, 94)
        if any(w in norm for w in ("xuat hien tai", "appear at", "tieu diet", "danh bai")):
            self.handle_chat_vip(text)

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
                combined = (chat_text or "")
                if options:
                    combined += "\n" + "\n".join(options)
                self._parse_quest_info(combined)
        except Exception:
            pass

    def _on_task_event(self, task: Any) -> None:
        """Lắng nghe khi nhận nhiệm vụ mới hoặc cập nhật tiến độ nhiệm vụ từ server."""
        if self.is_main_task_enabled:
            my_char = self._get_my_char()
            if my_char:
                self._parse_main_task_info(my_char)

    def _on_mob_killed_event(self, mob_template_id: int) -> None:
        self._increment_quest_kill_count(mob_template_id)
        if self.is_main_task_enabled and self.main_task_info and self.main_task_info.is_valid:
            if self.main_task_info.mob_template_id == mob_template_id or mob_template_id == -1:
                self.main_task_info.current_count += 1
                if self.main_task_info.current_count >= self.main_task_info.target_count:
                    self._log_auto(f"Đã hoàn thành mục tiêu ({self.main_task_info.current_count}/{self.main_task_info.target_count} {self.main_task_info.mob_name})! Chuẩn bị đi báo cáo...", is_important=True)
                    self.main_task_info.is_report_step = True
                    self.main_task_state = MainTaskState.NAVIGATE_TO_REPORT

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
                        # ƯU TIÊN 3: TÁC VỤ ĐỊNH KỲ (DÙNG ITEM BALO & ĐỒNG BỘ INFO)
                        # ------------------------------------------------------
                        if self.auto_use_item_enabled:
                            self._step_auto_use_item()

                        # Đồng bộ thông tin nhân vật (cPower, pet info) định kỳ 15s một lần
                        now_sync = time.time()
                        if (now_sync - getattr(self, "_last_char_info_sync_time", 0.0)) >= 15.0:
                            self._last_char_info_sync_time = now_sync
                            if self.client and hasattr(self.client, "refresh_char_info"):
                                self.client.refresh_char_info()

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

                        # 4.5. Chuỗi Nhiệm Vụ Mới / Nhiệm Vụ Chính Tuyến (AutoMainTask FSM)
                        elif self.is_main_task_enabled:
                            self._step_main_task(my_char)

                        # 4.6. Shuttle chuyển qua lại 2 map
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
            # Hook Auto Routine Tagging: Bơm máu / Ăn đậu (Label 2)
            collector = getattr(self.client, "data_collector", None)
            if collector and collector.is_recording:
                collector.record_sample(self.client, 2)

            svc = self._service()
            if not svc:
                return

            # 1. Ưu tiên ăn hạt đậu thần đang có sẵn trong hành trang Balo
            pean = my_char.get_first_pean_item() if hasattr(my_char, "get_first_pean_item") else None
            if pean is not None:
                svc.useItem(0, 1, -1, pean.template_id)
                time.sleep(0.2)
                return

            # 2. Nếu trong balo hết đậu nhưng đang ở nhà và cây đậu có đậu chín
            if my_char.magicTree and getattr(my_char.magicTree, "currPeas", 0) > 0:
                curr_map = getattr(my_char.mapInfo, "mapID", -1)
                # Map nhà: 21 (Trái đất), 22 (Namếc), 23 (Xayda)
                if curr_map in (21, 22, 23):
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
        """Cài đặt bộ skill xoay vòng để pem boss / tàn sát / làm nhiệm vụ (loại trừ QCKK, Makankosappo, Tự sát)."""
        clean_ids = [int(s) for s in skill_ids if int(s) not in self.FORBIDDEN_COMBAT_SKILLS]
        if not clean_ids:
            return False, "Danh sách skill không hợp lệ (không chứa skill cấm QCKK/Makankosappo/Tự sát)!"
        self.combat_combo_skills = clean_ids
        self._combo_skill_idx = 0
        self._skill_last_use.clear()
        my_char = self._get_my_char()
        if my_char:
            my_char.skillTemplateId = None
        names = [f"{sid} ({SKILL_NAMES.get(sid, 'Skill')})" for sid in clean_ids]
        msg = f"Đã cài đặt combo {len(clean_ids)} skill: {' -> '.join(names)}"
        self._log_auto(msg, is_important=True)
        return True, msg

    def _get_skill_cooldown(self, skill_id: int) -> float:
        """Thời gian hồi chiêu (cooldown) chuẩn theo từng kỹ năng trong NRO."""
        if skill_id in (1, 3, 5):          # Chưởng Kamejoko / Masenko / Antomic
            return 1.2
        elif skill_id in (9, 17, 25):      # Kaioken, Liên hoàn, Cađíc liên hoàn
            return 4.0
        elif skill_id in (12, 13):         # Đẻ trứng, Biến hình khỉ
            return 25.0
        elif skill_id in (6, 8, 19, 21):   # Thái Dương Hạ San, TTNL, Khiên, Huýt sáo
            return 10.0
        return 0.0                         # Đấm cơ bản (0, 2, 4) cooldown = 0s

    def _get_tansat_skill_ids(self) -> tuple:
        my_char = self._get_my_char()
        gender = getattr(my_char, "cgender", 0) if my_char else 0
        try:
            gender = int(gender)
        except Exception:
            gender = 0
        return self.TANSAT_SKILLS_BY_GENDER.get(gender, (1, 9, 0))

    def _select_combat_skill_rotation(self, my_char: Char) -> int:
        """
        Xoay vòng combo skill (chưởng -> buff -> đấm) liên tục cho tàn sát, đánh quái nhiệm vụ và săn boss (mô phỏng Mod C#).
        Kiểm tra cooldown theo thời gian thực (độ chính xác 0.001s). Nếu skill hết cooldown thì dùng ngay và xoay con trỏ,
        nếu chưa hết cooldown thì xoay tiếp sang skill kế tiếp trong combo.
        """
        gender = getattr(my_char, "cgender", 0) if my_char else 0
        try:
            gender = int(gender)
        except Exception:
            gender = 0

        basic_punch = {0: 0, 1: 2, 2: 4}.get(gender, 0)

        # 1. Xác định danh sách candidate
        if self.combat_combo_skills:
            # Người dùng đã chủ động chọn combo -> Tin tưởng 100%
            candidate_list = [s for s in self.combat_combo_skills if s not in self.FORBIDDEN_COMBAT_SKILLS]
        else:
            # Mặc định theo hệ phái (Trái Đất: 1, 9, 0; Namek: 3, 12, 2; Xayda: 5, 13, 4)
            candidate_list = list(self.TANSAT_SKILLS_BY_GENDER.get(gender, (1, 9, 0)))

        if not candidate_list:
            candidate_list = [basic_punch]

        now = time.time()
        num_candidates = len(candidate_list)
        for offset in range(num_candidates):
            idx = (self._combo_skill_idx + offset) % num_candidates
            s_id = candidate_list[idx]

            # Bỏ qua skill cấm nếu lọt vào
            if s_id in self.FORBIDDEN_COMBAT_SKILLS:
                continue

            # Kiểm tra Biến hình (13): nếu đã hoá khỉ rồi thì xoay tiếp
            if s_id == 13 and getattr(my_char, "isMonkey", 0) > 0:
                continue

            # Kiểm tra năng lượng KI/MP: nếu cMP <= 15 và không phải chiêu đấm cơ bản (0, 2, 4) -> xoay tiếp
            if s_id not in (0, 2, 4) and getattr(my_char, "cMP", 100) < 15:
                continue

            cd = self._get_skill_cooldown(s_id)
            last_used = self._skill_last_use.get(s_id, 0.0)

            # Kiểm tra cooldown thời gian thực (~0.001s)
            if (now - last_used) >= cd:
                # Đủ điều kiện: dùng skill này và xoay sang skill kế tiếp cho lần kiểm tra sau
                self._combo_skill_idx = (idx + 1) % num_candidates
                self._skill_last_use[s_id] = now
                return s_id
            # Chưa hết cooldown -> tự động xoay tiếp sang offset kế tiếp trong vòng lặp!

        # Fallback về chiêu đấm cơ bản trong lúc chờ các chiêu khác hồi
        self._skill_last_use[basic_punch] = now
        return basic_punch

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

        # Hook Auto Routine Tagging: Tấn công quái (Label 0) hoặc Tung skill combo (Label 4)
        collector = getattr(self.client, "data_collector", None)
        if collector and collector.is_recording:
            act_id = 4 if (skill_id is not None and skill_id not in (0, 2, 4)) else 0
            t_obj = vMob[0] if vMob else (vChar[0] if vChar else None)
            collector.record_sample(self.client, act_id, target=t_obj)

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
        attack_delay = getattr(self, "combat_attack_delay", 0.1)
        if (now - self.last_attack_time) >= attack_delay:
            self.last_attack_time = now
            self.attack_target(target)

    def _step_tansat(self, my_char: Char) -> None:
        """Thực thi một chu kỳ tàn sát quái / người chơi."""
        # 1. Nhặt đồ trước nếu có
        if self.auto_pick and self._step_loot_ground_items(my_char):
            return

        attack_delay = getattr(self, "combat_attack_delay", 0.1)

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
            if not candidate_mobs and (self.target_mob_types or self.target_mob_ids):
                # Fallback: Nếu bộ lọc quái (theo template hoặc mob ID) không có con nào trong map hiện tại,
                # tự động fallback đánh các quái thông thường có sẵn để nhân vật không bị đứng đơ một chỗ
                candidate_mobs = [
                    m for m in mobs
                    if getattr(m, "status", 0) not in (0, 1) and getattr(m, "hp", 0) > 0
                    and (not self.avoid_super_mob or not getattr(m, "isBoss", False))
                ]

            if candidate_mobs:
                target_mob = min(candidate_mobs, key=lambda m: my_char.distance_to(m.x, m.y))
                my_char.focus_mob(target_mob)
                self.teleport(target_mob.x, target_mob.y)
                now = time.time()
                if (now - self.last_attack_time) >= attack_delay:
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
                if (now - self.last_attack_time) >= attack_delay:
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

        if norm_map in ("me cung chet choc", "me cung", "me cung chet", "vuc chet"):
            return 67
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

        def _clean_res(k: str, b: str) -> Tuple[str, str]:
            b_clean = b.strip()
            if b_clean.upper().startswith("BOSS "):
                b_clean = b_clean[5:].strip()
            return k.strip(), b_clean.rstrip(".!").strip()

        m1 = re.search(r"BOSS\s+(.+?)\s+vừa\s+bị\s+(.+?)\s+tiêu\s+diệt", text, re.IGNORECASE)
        if m1:
            return _clean_res(m1.group(2), m1.group(1))
        m2 = re.search(r"(.+?)\s+vừa\s+bị\s+tiêu\s+diệt\s+bởi\s+(.+)", text, re.IGNORECASE)
        if m2:
            return _clean_res(m2.group(2), m2.group(1))
        m3 = re.search(r"(.+?)\s+đã\s+bị\s+(.+?)\s+tiêu\s+diệt", text, re.IGNORECASE)
        if m3:
            return _clean_res(m3.group(2), m3.group(1))
        m4 = re.search(r"(.+?)\s+đã\s+tiêu\s+diệt\s+được\s+(.+)", text, re.IGNORECASE)
        if m4:
            return _clean_res(m4.group(1), m4.group(2))
        m5 = re.search(r"(.+?)\s+đã\s+tiêu\s+diệt\s+(.+)", text, re.IGNORECASE)
        if m5:
            return _clean_res(m5.group(1), m5.group(2))
        m6 = re.search(r"(?:BOSS\s+)?(.+?)\s+(?:đã|vừa)\s+bị\s+tiêu\s+diệt", text, re.IGNORECASE)
        if m6:
            return _clean_res("", m6.group(1))
        return None

    @classmethod
    def parse_boss_announcement(cls, raw_text: str) -> Optional[Boss]:
        """
        Bóc tách thông báo Boss xuất hiện hoặc bị tiêu diệt từ tin nhắn ChatVip (cmd 93)
        hoặc Server Message (cmd -25, 94). Trả về đối tượng Boss nếu nhận diện được.
        """
        if not raw_text:
            return None

        # 1. Làm sạch chuỗi
        text = str(raw_text).strip()
        while text.startswith("!"):
            text = text[1:].strip()
        # Loại bỏ các tag màu như |0|, |1|, ... |7|
        text = re.sub(r"\|[0-9]\|", "", text).strip()
        # Loại bỏ tag tiền tố như [Thông báo], [Server], v.v.
        text = re.sub(r"^\[.*?\]\s*", "", text).strip()

        # 2. Kiểm tra Boss bị tiêu diệt
        killed_info = cls._extract_killed_info(text)
        if killed_info:
            killer, boss_name = killed_info
            b_norm = normalize_str(boss_name)
            boss = Boss(name=boss_name, map_name="", is_died=True, killer=killer)
            with cls._lock:
                if b_norm in cls._active_bosses:
                    cls._active_bosses[b_norm]["is_died"] = True
                    cls._active_bosses[b_norm]["killer"] = killer
            return boss

        # 3. Kiểm tra Boss xuất hiện bằng Regex linh hoạt
        m_app = re.search(
            r"(?:BOSS\s+)?(.+?)\s+(?:vừa\s+xuất\s+hiện\s+tại|vua\s+xuat\s+hien\s+tai|xuất\s+hiện\s+tại|xuat\s+hien\s+tai|appear\s+at|muncul\s+di)\s+(.+?)(?:\s+(?:khu\s+vực|khu\s+vuc|khu|zone|zona)\s+(\d+))?(?:\s*[\.!]|$)",
            text,
            re.IGNORECASE,
        )
        if m_app:
            boss_name = m_app.group(1).strip()
            if boss_name.upper().startswith("BOSS "):
                boss_name = boss_name[5:].strip()
            map_name = m_app.group(2).strip().rstrip(".!").strip()
            zone_id = int(m_app.group(3)) if m_app.group(3) else -1
            map_id = cls.resolve_boss_map_id(boss_name, map_name)

            boss = Boss(name=boss_name, map_name=map_name, map_id=map_id, zone_id=zone_id, is_died=False)
            b_norm = normalize_str(boss_name)
            with cls._lock:
                cls._active_bosses[b_norm] = {
                    "name": boss_name,
                    "map_id": map_id,
                    "map_name": map_name,
                    "zone_id": zone_id,
                    "is_died": False,
                    "found_time": time.time(),
                }
            return boss

        # 4. Fallback từ khóa truyền thống
        is_appear = any(app in text for app in cls.STR_BOSS_APPEARED[1:4]) or text.startswith(cls.STR_BOSS_APPEARED[0])
        if is_appear:
            temp_text = text
            for k in cls.STR_BOSS_APPEARED:
                temp_text = temp_text.replace(k, "|")
            parts = temp_text.split("|")
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                boss_name = parts[0]
                if boss_name.upper() == "BOSS" and len(parts) >= 3:
                    boss_name = parts[1]
                    map_name = parts[2]
                    zone_id = int(parts[3]) if len(parts) >= 4 and parts[3].isdigit() else -1
                else:
                    map_name = parts[1]
                    zone_id = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else -1
                if boss_name.upper().startswith("BOSS "):
                    boss_name = boss_name[5:].strip()
                map_id = cls.resolve_boss_map_id(boss_name, map_name)
                boss = Boss(name=boss_name, map_name=map_name, map_id=map_id, zone_id=zone_id, is_died=False)
                b_norm = normalize_str(boss_name)
                with cls._lock:
                    cls._active_bosses[b_norm] = {
                        "name": boss_name,
                        "map_id": map_id,
                        "map_name": map_name,
                        "zone_id": zone_id,
                        "is_died": False,
                        "found_time": time.time(),
                    }
                return boss

        return None

    def handle_chat_vip(self, chat_vip_text: str) -> Optional[Boss]:
        """
        Tiếp nhận và xử lý gói tin ChatVip hoặc thông báo hệ thống liên quan tới Boss.
        Lưu vào danh sách lịch sử Boss và kích hoạt các callback sự kiện.
        """
        boss = self.parse_boss_announcement(chat_vip_text)
        if not boss:
            return None

        with self._lock:
            if boss.is_died:
                existing = None
                norm_bname = normalize_str(boss.name)
                for b in reversed(self.list_bosses):
                    if (b.name == boss.name or normalize_str(b.name) == norm_bname) and not b.killer:
                        existing = b
                        break
                if existing:
                    existing.is_died = True
                    existing.killer = boss.killer
                    boss = existing
                else:
                    self.list_bosses.append(boss)

                self._trim_bosses()
                for cb in self.on_boss_killed_callbacks:
                    try:
                        cb(boss)
                    except Exception:
                        pass
            else:
                # Đánh dấu các bản ghi cũ của cùng tên boss này là đã chết (vì Boss không thể xuất hiện ở 2 nơi cùng lúc)
                norm_bname = normalize_str(boss.name)
                for b in self.list_bosses:
                    if not b.is_died and (normalize_str(b.name) == norm_bname or norm_bname in normalize_str(b.name)):
                        b.is_died = True

                self.list_bosses.append(boss)
                self._trim_bosses()
                for cb in self.on_boss_appeared_callbacks:
                    try:
                        cb(boss)
                    except Exception:
                        pass

        return boss

    def _trim_bosses(self) -> None:
        while len(self.list_bosses) > 100:
            self.list_bosses.pop(0)

    def update_boss_status(self, current_map_id: int, current_zone_id: int, chars_in_map: Optional[Dict[int, Any]] = None) -> None:
        chars_list = list(chars_in_map.values()) if chars_in_map else []
        if not chars_list:
            return

        for boss in self.list_bosses:
            if boss.is_died:
                continue

            if boss.map_id == current_map_id and current_map_id != -1:
                found_char = None
                norm_b = normalize_str(boss.name)
                for ch in chars_list:
                    ch_name = getattr(ch, "cName", "")
                    norm_c = normalize_str(ch_name)
                    if norm_c == norm_b or (len(norm_b) >= 3 and norm_b in norm_c):
                        found_char = ch
                        break

                if found_char is not None:
                    if boss.zone_id == -1:
                        boss.zone_id = current_zone_id
                    # Chỉ đánh dấu Boss chết khi thực sự có trạng thái chết (statusMe == 14 hoặc isDie)
                    # KHÔNG dựa vào cHP <= 0 vì khi Boss mới xuất hiện / đang nói chuyện server gửi cHP = 0 (chưa lên máu đỏ)
                    if getattr(found_char, "statusMe", 1) == 14 or getattr(found_char, "isDie", False):
                        boss.is_died = True
                        for cb in self.on_boss_killed_callbacks:
                            try:
                                cb(boss)
                            except Exception:
                                pass

    def get_all_bosses(self) -> List[Boss]:
        return list(self.list_bosses)

    def get_alive_bosses(self) -> List[Boss]:
        now = time.time()
        alive = []
        for b in self.list_bosses:
            if b.is_died:
                continue
            # Boss xuất hiện quá 5 phút mà chưa xác định được khu vực (zone_id == -1) -> Coi như đã chết
            if (now - b.appear_time) > 300 and b.zone_id == -1:
                b.is_died = True
                continue
            alive.append(b)
        return alive

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
        self.is_quest_enabled = False
        self.is_shuttle_enabled = False
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
                now = time.time()
                self.boss_death_time = now
                self.looting_start_time = now
                self.pick_item_attempts = 0
                self.last_pick_item_time = 0.0
            elif self.bh_state != self.STATE_BH_LOOTING:
                killer_str = f" bởi '{self.current_boss.killer}'" if self.current_boss.killer else ""
                self._log_auto(f"Boss '{self.current_boss.name}' đã bị hạ{killer_str}. Đổi mục tiêu!", is_important=True)
                self.current_boss = None
                self._reset_boss_fight_tracking()
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
            self.bh_waiting_zone = -1
            self.bh_status_message = f"Phát hiện mục tiêu: '{next_boss.name}' tại '{next_boss.map_name}' [{next_boss.map_id}]. Bắt đầu di chuyển!"
            self._log_auto(self.bh_status_message, is_important=True)
            self.bh_state = self.STATE_BH_MOVING
            self._handle_bh_moving(my_char)
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
                self.bh_waiting_zone = -1
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
                if not xst.get("is_acting", False) and not xst.get("is_running", False):
                    self.client.xmap(target_map)
            return

        # Đang ở map tuần tra -> tạo boss ảo tạm để quét các khu tìm boss xuất hiện trước
        virtual_boss = Boss(name="Boss Tuần Tra", map_name=get_map_name(curr_map), map_id=curr_map)
        self.current_boss = virtual_boss
        self.bh_waiting_zone = -1
        self.bh_state = self.STATE_BH_SCANNING

    def _handle_bh_moving(self, my_char: Char) -> None:
        if not self.current_boss:
            self.bh_state = self.STATE_BH_IDLE
            return

        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)
        if curr_map_id == self.current_boss.map_id:
            self.bh_status_message = f"Đã tới map '{self.current_boss.map_name}'. Bắt đầu quét khu!"
            self.bh_waiting_zone = -1
            self.bh_state = self.STATE_BH_SCANNING
            self._handle_bh_scanning(my_char)
            return

        if self.client and hasattr(self.client, "xmap"):
            xst = self.client.xmap_status()
            if not xst.get("is_acting", False) and not xst.get("is_running", False):
                self.client.xmap(self.current_boss.map_id)

    def _find_boss_in_current_map(self, my_char: Char) -> Optional[Any]:
        """
        Tìm Boss trong map hiện tại.
        Áp dụng chuẩn C# Mod NRO (AutoFarmBossNappa):
        - Nhận diện theo tên Boss (StartsWith / Contains).
        - Khi Boss mới xuất hiện hoặc đang nói chuyện, cHP = 0 và chưa lên máu đỏ (ví dụ: Kuku [0 / 5000000]).
          Vẫn nhận diện để bot ở lại khu chờ boss nói xong lên máu đỏ để pem!
        - Chỉ bỏ qua khi thực thể là pet/minipet, hoặc statusMe == 14 (đã chết nằm đất), hoặc isDie == True.
        """
        if not self.current_boss:
            return None
        norm_target = normalize_str(self.current_boss.name)
        is_patrol = (self.current_boss.name == "Boss Tuần Tra") or self.hunt_all

        # 1. Quét trong người chơi / boss dạng Char
        for ch in list(my_char.mapInfo.chars.values()):
            if ch is None or ch.charID == my_char.charID:
                continue

            # Bỏ qua pet và minipet
            if getattr(ch, "isPet", False) or getattr(ch, "isMiniPet", False):
                continue

            # Chỉ bỏ qua nếu thực sự là xác chết nằm đất (statusMe == 14 hoặc isDie)
            if getattr(ch, "statusMe", 1) == 14 or getattr(ch, "isDie", False):
                continue

            c_name = getattr(ch, "cName", "")
            if not c_name or c_name.startswith("$") or c_name.startswith("#"):
                continue

            is_pk_boss = (getattr(ch, "cTypePk", 0) == 5)
            is_neg_id = (getattr(ch, "charID", 0) < 0)

            # Làm sạch mã màu (\c0, |1|) và tiền tố [BOSS] nếu có
            clean_c = re.sub(r"\\[cC]\d+|\|\d+\||\[.*?\]", "", c_name).strip()
            norm_c = normalize_str(clean_c)
            norm_raw = normalize_str(c_name)

            if is_patrol:
                if is_pk_boss or is_neg_id:
                    return ch
                continue

            # 1. Nếu mang cTypePk == 5 hoặc charID âm -> chắc chắn là Boss/thực thể đặc biệt:
            if is_pk_boss or is_neg_id:
                if (norm_target in norm_c) or (norm_c in norm_target) or (norm_target in norm_raw):
                    return ch
                if norm_c.startswith(norm_target) or norm_raw.startswith(norm_target):
                    return ch
                target_words = norm_target.split()
                if target_words and any(w in norm_c or w in norm_raw for w in target_words if len(w) >= 3):
                    return ch

            # 2. Nếu cTypePk != 5 và charID >= 0 (ví dụ Boss lúc đang nói chuyện chưa bật cTypePk=5):
            # Tên phải khớp chính xác hoặc bắt đầu bằng tên boss + khoảng trắng (VD: "Kuku", "Kuku 1", "\c2Kuku")
            if (
                norm_c == norm_target
                or norm_raw == norm_target
                or norm_c.startswith(norm_target + " ")
                or norm_raw.startswith(norm_target + " ")
            ):
                return ch

        # 2. Quét trong quái (boss dạng Mob như Hirudegarn, Heo Rừng...)
        for m in list(my_char.mapInfo.mobs.values()):
            if m is None or getattr(m, "hp", 0) <= 0 or getattr(m, "status", 0) in (0, 1):
                continue

            # Lấy tên Mob chuẩn từ MOB_NAMES qua templateId
            m_template_id = getattr(m, "templateId", -1)
            raw_mob_name = MOB_NAMES.get(m_template_id, "")
            norm_m = normalize_str(raw_mob_name)
            is_mob_boss = getattr(m, "isBoss", False)

            if is_patrol:
                if is_mob_boss:
                    return m
                if norm_m and self.target_bosses and any(t == norm_m or (len(t) >= 3 and t in norm_m) for t in self.target_bosses):
                    return m
            else:
                if norm_m:
                    if norm_m == norm_target or (len(norm_target) >= 3 and norm_target in norm_m):
                        return m
                if is_mob_boss and norm_m and (norm_m == norm_target or norm_target in norm_m):
                    return m

        return None

    def _handle_bh_scanning(self, my_char: Char) -> None:
        """
        Dò tìm Boss theo thứ tự từ khu 0 đến hết khu trong map.
        Nếu đổi khu chưa thành công thì chờ 0.5s rồi thử lại liên tục cho tới khi thành công.
        Khi vào khu, ở lại 1.5s (MAP_LOAD_DELAY_MS trong C#) để server nạp đầy đủ gói tin nhân vật/boss trong khu rồi mới quét.
        """
        if not self.current_boss:
            self.bh_state = self.STATE_BH_IDLE
            return

        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)
        curr_zone_id = getattr(my_char.mapInfo, "zoneID", -1)
        now = time.time()

        # 1. Tự động gửi yêu cầu lấy danh sách khu vực thực tế từ server nếu chưa có
        zones = getattr(my_char.mapInfo, "zones", [])
        if not zones:
            last_req = getattr(self, "_last_bh_zones_request_time", 0.0)
            if (now - last_req) >= 4.0:
                self._last_bh_zones_request_time = now
                if self.client and hasattr(self.client, "request_zones"):
                    self.client.request_zones()

        # Xác định danh sách các khu từ 0 đến hết khu trong map
        if zones:
            available_zones = sorted([z.zoneId for z in zones if z.zoneId >= 0])
        else:
            # Nếu chưa tải được danh sách từ server, quét tạm thời từ khu 0 đến 14
            available_zones = list(range(0, 15))

        if not available_zones:
            available_zones = [0]

        # 2. Ưu tiên nếu đồng đội đã tìm thấy Boss ở khu cụ thể hoặc Boss có sẵn khu từ ChatVip
        active_boss = SharedHuntCoordinator.get_active_boss(self.current_boss.name)
        team_zone = -1
        if active_boss and active_boss.get("map_id") == curr_map_id and not active_boss.get("is_died", False):
            team_zone = active_boss.get("zone_id", -1)
        if team_zone < 0 and self.current_boss.zone_id >= 0:
            team_zone = self.current_boss.zone_id

        # 3. Xác định khu vực mục tiêu cần đến (target_zone)
        if team_zone >= 0:
            target_zone = team_zone
        else:
            # Ưu tiên quét ngay khu hiện tại trước nếu chưa quét (tránh vừa vào map đã nhảy khu khác)
            if curr_zone_id >= 0 and curr_zone_id in available_zones and curr_zone_id not in self.scanned_zones:
                target_zone = curr_zone_id
            else:
                # Quét tuần tự kết hợp chia khu thông minh giữa các acc đồng đội (không quét trùng khu)
                unscanned = [z for z in available_zones if z not in self.scanned_zones]
                if not unscanned:
                    # Đã quét sạch toàn bộ các khu trong map mà không tìm thấy Boss -> Boss đã bị tiêu diệt hoặc đã biến mất!
                    b_name = self.current_boss.name
                    m_name = self.current_boss.map_name or get_map_name(curr_map_id)
                    self._log_auto(
                        f"[~] Đã quét sạch {len(available_zones)} khu (0 -> {available_zones[-1]}) tại {m_name} không thấy Boss '{b_name}'. Xác nhận Boss đã bị tiêu diệt hoặc biến mất!",
                        is_important=True,
                    )
                    self.current_boss.is_died = True
                    norm_b = normalize_str(b_name)
                    for b in self.list_bosses:
                        if not b.is_died and (norm_b in normalize_str(b.name) or normalize_str(b.name) in norm_b):
                            if b.map_id in (-1, curr_map_id):
                                b.is_died = True
                    SharedHuntCoordinator.report_boss_died(self, b_name, curr_map_id, -1)
                    SharedHuntCoordinator.clear_boss(b_name)

                    self.current_boss = None
                    self.scanned_zones.clear()
                    self._reset_boss_fight_tracking()
                    self.bh_state = self.STATE_BH_IDLE
                    self.bh_status_message = f"Boss '{b_name}' đã biến mất khỏi {m_name}. Đang chờ thông báo Boss mới..."
                    return

                claimed = SharedHuntCoordinator.claim_next_zone(
                    self._tag(), curr_map_id, available_zones, exclude_zones=self.scanned_zones, current_zone=curr_zone_id
                )
                target_zone = claimed if claimed is not None else unscanned[0]

        # 4. Kiểm tra xem đã vào đúng khu target_zone chưa
        if curr_zone_id == target_zone:
            # ĐÃ VÀO KHU THÀNH CÔNG!
            self._zone_retry_count = 0

            # Ghi nhận thời điểm bắt đầu vào khu này
            if getattr(self, "_current_settled_zone", -1) != curr_zone_id:
                self._current_settled_zone = curr_zone_id
                self._zone_settled_time = now

            # Chia sẻ tầm nhìn: Quét toàn bộ Boss có trong khu và báo cáo cho đồng đội
            self._scan_and_share_vision_bosses(my_char, curr_map_id, curr_zone_id)

            # Quét kiểm tra xem Boss mục tiêu của bản thân có trong khu hiện tại không
            found = self._find_boss_in_current_map(my_char)
            if found is not None:
                self.current_boss.zone_id = curr_zone_id
                if hasattr(found, "cName"):
                    self.current_boss.name = found.cName
                target_x = getattr(found, "cx", getattr(found, "x", my_char.cx))
                target_y = getattr(found, "cy", getattr(found, "y", my_char.cy))
                self.last_boss_pos = (target_x, target_y)
                self._log_auto(f"[+] PHÁT HIỆN BOSS '{self.current_boss.name}' tại Khu {curr_zone_id}! Bắt đầu theo dõi và pem!", is_important=True)
                SharedHuntCoordinator.report_boss_found(self, self.current_boss, curr_map_id, curr_zone_id, (target_x, target_y))
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_COMBAT
                return

            # Cần ở lại trong khu ít nhất 1.5s (MAP_LOAD_DELAY_MS trong AutoFarmBossNappa) để server nạp đủ gói tin PLAYER_IN_MAP
            if (now - getattr(self, "_zone_settled_time", 0.0)) < 1.5:
                return

            # Nếu sau 1.5s vẫn không có Boss trong khu này: Đánh dấu đã quét xong
            self.scanned_zones.add(target_zone)
            SharedHuntCoordinator.release_zone(self._tag(), curr_map_id, target_zone, scanned=True)

            # Chuyển ngay sang khu tiếp theo trong danh sách
            next_unscanned = [z for z in available_zones if z not in self.scanned_zones]
            if next_unscanned:
                next_z = next_unscanned[0]
                if self.client and hasattr(self.client, "change_zone"):
                    self.client.change_zone(next_z)
                    self.last_zone_retry_time = now
                    self._current_settled_zone = -1
                    self.bh_status_message = f"Đang quét Khu {next_z:02d} (đã quét {len(self.scanned_zones)}/{len(available_zones)} khu)..."
            else:
                # Đã quét xong khu cuối cùng trong map và không thấy Boss
                b_name = self.current_boss.name
                m_name = self.current_boss.map_name or get_map_name(curr_map_id)
                self._log_auto(
                    f"[~] Đã quét sạch {len(available_zones)} khu (0 -> {available_zones[-1]}) tại {m_name} không thấy Boss '{b_name}'. Xác nhận Boss đã bị tiêu diệt hoặc biến mất!",
                    is_important=True,
                )
                self.current_boss.is_died = True
                norm_b = normalize_str(b_name)
                for b in self.list_bosses:
                    if not b.is_died and (norm_b in normalize_str(b.name) or normalize_str(b.name) in norm_b):
                        if b.map_id in (-1, curr_map_id):
                            b.is_died = True
                SharedHuntCoordinator.report_boss_died(self, b_name, curr_map_id, -1)
                SharedHuntCoordinator.clear_boss(b_name)

                self.current_boss = None
                self.scanned_zones.clear()
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_IDLE
                self.bh_status_message = f"Boss '{b_name}' đã biến mất khỏi {m_name}. Đang chờ thông báo Boss mới..."
            return

        # 5. CHƯA VÀO ĐƯỢC KHU (curr_zone_id != target_zone):
        self._current_settled_zone = -1
        if (now - getattr(self, "last_zone_retry_time", 0.0)) >= 0.5:
            self.last_zone_retry_time = now
            self._zone_retry_count = getattr(self, "_zone_retry_count", 0) + 1
            if self._zone_retry_count >= 4:
                # Thử đổi vào khu target_zone quá 4 lần (2s) không được -> có thể khu bị đầy
                self._log_auto(f"[~] Khu {target_zone:02d} không vào được (khu đầy hoặc lỗi kết nối). Bỏ qua và chuyển sang khu tiếp theo!")
                self.scanned_zones.add(target_zone)
                SharedHuntCoordinator.release_zone(self._tag(), curr_map_id, target_zone, scanned=True)
                self._zone_retry_count = 0
                return

            if self.client and hasattr(self.client, "change_zone"):
                self.client.change_zone(target_zone)
                self.bh_status_message = f"Đang đổi sang Khu {target_zone:02d} (thử lại lần {self._zone_retry_count}/4)..."

    def _handle_bh_combat(self, my_char: Char) -> None:
        """Đấm Boss liên tục bằng combo 3 skill và giám sát HP boss (phát hiện boss ảo/kẹt/đang nói chuyện)."""
        if not self.current_boss:
            self.bh_state = self.STATE_BH_IDLE
            return

        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)
        curr_zone_id = getattr(my_char.mapInfo, "zoneID", -1)
        now = time.time()

        # 1. Đảm bảo ở đúng khu vực của Boss
        if self.current_boss.zone_id >= 0 and curr_zone_id != self.current_boss.zone_id:
            if self.client and hasattr(self.client, "change_zone"):
                self.client.change_zone(self.current_boss.zone_id)
                self.bh_waiting_zone = self.current_boss.zone_id
                self.bh_zone_change_time = now
                return

        boss_target = self._find_boss_in_current_map(my_char)

        # 2. Kiểm tra nếu Boss đã chết hoặc biến mất
        is_dead = False
        if boss_target is None:
            # Kiểm tra xem có xác boss nằm trong map (statusMe == 14 hoặc isDie) không
            dead_boss_in_map = False
            for ch in list(my_char.mapInfo.chars.values()):
                if ch and (getattr(ch, "statusMe", 1) == 14 or getattr(ch, "isDie", False)):
                    c_name = getattr(ch, "cName", "")
                    clean_c = re.sub(r"\\[cC]\d+|\|\d+\||\[.*?\]", "", c_name).strip()
                    norm_c = normalize_str(clean_c)
                    norm_target = normalize_str(self.current_boss.name)
                    if (norm_target in norm_c) or (norm_c in norm_target):
                        dead_boss_in_map = True
                        break

            if dead_boss_in_map:
                is_dead = True
            else:
                # Nếu tạm thời mất dấu Boss (boss bay đi xa hoặc nhân vật bị văng ra), thử teleport lại vị trí cũ
                if self.last_boss_pos and my_char.distance_to(self.last_boss_pos[0], self.last_boss_pos[1]) > 50:
                    self.teleport(self.last_boss_pos[0], self.last_boss_pos[1])

                # Chỉ kết luận boss đã chết hoặc biến mất sau ít nhất 5.0 giây liên tục không tìm thấy
                # VÀ trước đó đã thấy Boss còn sống (boss_entry_time > 0)
                if self.boss_entry_time > 0 and (now - self.last_boss_hp_check_time) > 5.0:
                    is_dead = True
        else:
            # Chỉ kết luận Boss chết nếu:
            # - Có cờ chết (statusMe == 14 hoặc isDie)
            # - Hoặc trước đó đã thấy Boss có máu đỏ (last_boss_hp > 0 hoặc boss_damaged) và hiện tại cHP <= 0
            if getattr(boss_target, "statusMe", 1) == 14 or getattr(boss_target, "isDie", False):
                is_dead = True
            elif (self.boss_damaged or (self.last_boss_hp > 0)) and getattr(boss_target, "cHP", 1) <= 0:
                is_dead = True
            # LƯU Ý: Nếu Boss mới xuất hiện hoặc đang nói chuyện (cHP = 0, chưa lên máu đỏ),
            # tuyệt đối không đánh dấu is_dead = True!

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

        # 3. Khởi tạo theo dõi biến động HP & phát hiện Boss ảo / kẹt / đang nói chuyện
        if self.boss_entry_time == 0.0:
            self.boss_entry_time = now
            self.last_boss_hp = getattr(boss_target, "cHP", -1)
            self.last_boss_hp_check_time = now
            self.boss_damaged = False
            self.consecutive_no_damage_count = 0

        current_hp = getattr(boss_target, "cHP", 0)

        # 4. Teleport áp sát & Focus Boss
        target_x = getattr(boss_target, "cx", getattr(boss_target, "x", my_char.cx))
        target_y = getattr(boss_target, "cy", getattr(boss_target, "y", my_char.cy))
        self.last_boss_pos = (target_x, target_y)

        if my_char.distance_to(target_x, target_y) > 40:
            self.teleport(target_x, target_y)

        if isinstance(boss_target, Mob):
            my_char.focus_mob(boss_target)
        else:
            my_char.focus_char(boss_target)

        # 5. Xử lý trường hợp Boss đang nói chuyện (cHP <= 0, chưa lên máu đỏ):
        if current_hp <= 0 and not self.boss_damaged and self.last_boss_hp <= 0:
            elapsed = now - self.boss_entry_time
            self.bh_status_message = f"Boss '{self.current_boss.name}' đang nói chuyện ({elapsed:.1f}s, chờ lên máu đỏ)..."

            # Nếu quá 15s mà Boss vẫn không lên máu đỏ -> Boss ảo hoặc kẹt hội thoại
            if elapsed >= 15.0:
                self._log_auto(f"[!] Boss '{self.current_boss.name}' không lên máu đỏ sau 15s (kẹt hội thoại/boss ảo). Bỏ qua khu {curr_zone_id}!", is_alert=True)
                SharedHuntCoordinator.release_zone(self._tag(), curr_map_id, curr_zone_id, scanned=True)
                self.scanned_zones.add(curr_zone_id)
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_SCANNING
                return

            # Đang nói chuyện: đứng cạnh chờ, không spam chiêu
            return

        # 6. Boss đã lên máu đỏ (current_hp > 0): Theo dõi biến động HP (C# AutoFarmBossNappa)
        if self.last_boss_hp <= 0:
            self.last_boss_hp = current_hp
            self.last_boss_hp_check_time = now
            self._log_auto(f"[+] Boss '{self.current_boss.name}' đã lên máu đỏ ({format_big_number(current_hp)} HP)! Bắt đầu tấn công!", is_important=True)

        if (now - self.last_boss_hp_check_time) >= self.HP_CHECK_INTERVAL_S:
            self.last_boss_hp_check_time = now
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

        # 7. Focus & Tấn công liên tục bằng combo 3 skill xoay vòng
        attack_delay = getattr(self, "combat_attack_delay", 0.1)
        if (now - self.last_attack_time) >= attack_delay:
            self.last_attack_time = now
            self.attack_target(boss_target)

    def _handle_bh_looting(self, my_char: Char) -> None:
        """Nhặt vật phẩm rơi từ Boss theo cơ chế Mod C# (chờ 2s, lọc đồ, retry 5 lần)."""
        now = time.time()
        start_t = self.boss_death_time if self.boss_death_time > 0 else self.looting_start_time
        elapsed = now - start_t

        # Duy trì vị trí boss chết (giới hạn tần suất teleport tránh spam lên trời)
        if self.last_boss_pos:
            bx, by = self.last_boss_pos
            if my_char.distance_to(bx, by) > 50 and (now - self.last_teleport_item_time) >= 0.5:
                self.last_teleport_item_time = now
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
        if my_char.distance_to(target_item.x, target_item.y) > 30:
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

    def _scan_and_share_vision_bosses(self, my_char: Char, curr_map_id: int, curr_zone_id: int) -> None:
        """
        Chia sẻ tầm nhìn (Shared Vision) cho toàn đội:
        Quét toàn bộ các Boss đang có mặt trong khu hiện tại (kể cả Boss của acc khác).
        Nếu phát hiện Boss mà đồng đội đang cần (ví dụ: Số 4, Số 3, Tiểu Đội Trưởng...):
        - Tự động báo cáo lên SharedHuntCoordinator kèm toạ độ và khu.
        - Giúp các acc khác lập tức bay tới khu này để pem mà không cần tự đi dò.
        - Bản thân KHÔNG đánh Boss nếu không nằm trong danh sách mục tiêu của mình (nhường Boss cho đồng đội).
        """
        for ch in list(my_char.mapInfo.chars.values()):
            if ch is None or ch.charID == my_char.charID:
                continue
            if getattr(ch, "isPet", False) or getattr(ch, "isMiniPet", False):
                continue
            if getattr(ch, "statusMe", 1) == 14 or getattr(ch, "isDie", False):
                continue

            c_name = getattr(ch, "cName", "")
            if not c_name or c_name.startswith("$") or c_name.startswith("#"):
                continue

            is_pk_boss = (getattr(ch, "cTypePk", 0) == 5)
            is_neg_id = (getattr(ch, "charID", 0) < 0)
            if not (is_pk_boss or is_neg_id):
                continue

            clean_c = re.sub(r"\\[cC]\d+|\|\d+\||\[.*?\]", "", c_name).strip()
            if not clean_c:
                continue

            target_x = getattr(ch, "cx", getattr(ch, "x", my_char.cx))
            target_y = getattr(ch, "cy", getattr(ch, "y", my_char.cy))
            b_obj = Boss(
                name=clean_c,
                map_id=curr_map_id,
                zone_id=curr_zone_id,
                map_name=get_map_name(curr_map_id),
            )
            SharedHuntCoordinator.report_boss_found(self, b_obj, curr_map_id, curr_zone_id, (target_x, target_y))

    def notify_boss_spotted(self, boss: Boss, map_id: int, zone_id: int, pos: Tuple[int, int], reporter_tag: str = "") -> None:
        """Được gọi bởi SharedHuntCoordinator khi 1 acc đồng đội phát hiện boss."""
        if not self.is_boss_hunter_enabled and not self.is_main_task_enabled:
            return
        if not self.is_target_boss(boss):
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
                    self.bh_waiting_zone = zone_id
                    self.bh_zone_change_time = time.time()
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
        if (not self.is_boss_hunter_enabled and not self.is_main_task_enabled) or not self.current_boss:
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
        self.is_boss_hunter_enabled = False
        self.is_shuttle_enabled = False
        self.is_tansat = False
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
        """
        Bóc tách thông tin nhiệm vụ Bò Mộng từ menu hội thoại hoặc thông báo.
        Tự động nhận diện tên quái, map_id, số lượng cần diệt và tiến độ.
        """
        lower_text = (menu_text or "").lower()
        if not lower_text:
            return

        # 1. Kiểm tra nếu đã hết nhiệm vụ hôm nay
        if any(x in lower_text for x in ("hết nhiệm vụ", "het nhiem vu", "hoàn thành hết", "mai quay lại")):
            self._log_auto("Đã hoàn thành hết số nhiệm vụ Bò Mộng hôm nay!")
            self.stop_auto_quest()
            return

        # 2. Bóc tách số nhiệm vụ còn lại hôm nay (vd: "Số nhiệm vụ còn lại: 9/10")
        m_rem = re.search(r"(?:còn lại|hôm nay|con lai|hom nay)[\s:]+(\d+)\s*/\s*(\d+)", lower_text)
        if m_rem:
            self.quest_info.quests_remaining = int(m_rem.group(1))
            self.quest_info.quests_total = int(m_rem.group(2))
            if self.quest_info.quests_remaining <= 0:
                self._log_auto("Đã hết lượt nhiệm vụ hôm nay!")
                self.stop_auto_quest()
                return

        # 3. Nhận diện quái vật mục tiêu từ MOB_LOCATION_DATA (sắp xếp dài trước để khớp chính xác)
        matched_mob = None
        sorted_mobs = sorted(MOB_LOCATION_DATA.keys(), key=lambda k: len(k), reverse=True)
        for mob in sorted_mobs:
            if mob in lower_text:
                matched_mob = mob
                break

        # Fallback regex nếu không trực tiếp chứa tên quái khớp chính xác
        if not matched_mob:
            m_task = re.search(r"(?:tiêu diệt|hạ|giết|danh|diet)\s+(\d+)?\s*([a-zA-Zà-ỹÀ-Ỹ\s]+?)(?:\s+tại|\s+ở|\s*[\.!]|\s*tiến độ|$)", lower_text)
            if m_task and m_task.group(2):
                candidate = m_task.group(2).strip()
                for mob in sorted_mobs:
                    if mob in candidate or candidate in mob:
                        matched_mob = mob
                        break

        if matched_mob:
            loc = MOB_LOCATION_DATA[matched_mob]
            target_map, template_id = loc
            self.quest_info.is_valid = True
            self.quest_info.mob_name = matched_mob
            self.quest_info.mob_template_id = template_id
            self.quest_info.map_id = target_map
            self.quest_info.map_name = get_map_name(target_map)

        # 4. Bóc tách tiến độ và số lượng cần diệt
        m_prog = re.search(r"(?:tiến độ|tiến độ nhiệm vụ|đã diệt|tien do)[\s:]*(\d+)\s*/\s*(\d+)", lower_text)
        if m_prog:
            self.quest_info.initial_count = int(m_prog.group(1))
            self.quest_info.target_count = int(m_prog.group(2))
            self.quest_info.kill_count = 0
        else:
            m_target = re.search(r"(?:tiêu diệt|hạ|giết|diet)\s+(\d+)", lower_text)
            if m_target:
                self.quest_info.target_count = int(m_target.group(1))
                self.quest_info.initial_count = 0
                self.quest_info.kill_count = 0

        if self.quest_info.is_valid and self.quest_info.target_count > 0:
            self._log_auto(f"Nhận diện NV: Hạ {self.quest_info.target_count} {self.quest_info.mob_name} tại {self.quest_info.map_name} [{self.quest_info.map_id}] (Tiến độ: {self.quest_info.current_progress}/{self.quest_info.target_count})")

    def _increment_quest_kill_count(self, mob_template_id: int) -> None:
        if not self.is_quest_enabled or not self.quest_info.is_valid:
            return

        target_template = getattr(self.quest_info, "mob_template_id", -1)
        target_name = (self.quest_info.mob_name or "").lower().strip()
        loc = MOB_LOCATION_DATA.get(target_name)
        expected_id = target_template if target_template != -1 else (loc[1] if loc else -1)

        if expected_id == mob_template_id or mob_template_id == -1:
            self.quest_info.kill_count += 1
            self.quest_total_kills += 1
            if self.quest_info.current_progress >= self.quest_info.target_count:
                self.quest_state = AutoQuestState.REPORT_QUEST
                self._log_auto(f"Đã hoàn thành mục tiêu ({self.quest_info.current_progress}/{self.quest_info.target_count} {self.quest_info.mob_name})! Đang quay về trả nhiệm vụ...")

    def _step_auto_quest(self, my_char: Char) -> None:
        """Thực thi một bước trong máy trạng thái Bò Mộng."""
        # Hook Auto Routine Tagging: Làm nhiệm vụ (Label 1)
        collector = getattr(self.client, "data_collector", None)
        if collector and collector.is_recording:
            collector.record_sample(self.client, 1)

        curr_map = getattr(my_char.mapInfo, "mapID", -1)

        # Kiểm tra nếu Xmap đang di chuyển thì đợi, tuyệt đối không spam xmap liên tục
        xst = self.client.xmap_status() if (self.client and hasattr(self.client, "xmap_status")) else {}
        is_xmap_busy = xst.get("is_acting", False) or xst.get("is_running", False)

        now = time.time()

        # 1. Trả nhiệm vụ
        if self.quest_state == AutoQuestState.REPORT_QUEST or (
            self.quest_info.is_valid and self.quest_info.current_progress >= self.quest_info.target_count
        ):
            self.quest_state = AutoQuestState.REPORT_QUEST
            if curr_map != BO_MONG_MAP_ID:
                if not is_xmap_busy and self.client and hasattr(self.client, "xmap"):
                    if (now - self.last_quest_xmap_time) >= 3.0:
                        self.last_quest_xmap_time = now
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
                    self.quests_completed += 1
                    self._log_auto(f"Đã trả nhiệm vụ Bò Mộng thành công! (Tổng hoàn thành: {self.quests_completed})")
                    # Reset quest_info để sẵn sàng nhận nhiệm vụ mới
                    self.quest_info.reset()
                    self.quest_state = AutoQuestState.GET_QUEST
            return

        # 2. Nhận nhiệm vụ
        if self.quest_state == AutoQuestState.GET_QUEST:
            if curr_map != BO_MONG_MAP_ID:
                if not is_xmap_busy and self.client and hasattr(self.client, "xmap"):
                    if (now - self.last_quest_xmap_time) >= 3.0:
                        self.last_quest_xmap_time = now
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
                    time.sleep(0.8)
                    if self.quest_info.is_valid:
                        self.quest_state = AutoQuestState.NAVIGATE_TO_MAP
            return

        # 3. Di chuyển đến map nhiệm vụ
        if self.quest_state == AutoQuestState.NAVIGATE_TO_MAP:
            target_map = getattr(self.quest_info, "map_id", -1)
            if target_map == -1:
                target = self.quest_info.mob_name.lower().strip()
                loc = MOB_LOCATION_DATA.get(target)
                if loc:
                    target_map = loc[0]
                    self.quest_info.map_id = target_map
                    self.quest_info.map_name = get_map_name(target_map)
                else:
                    return

            if curr_map != target_map:
                if not is_xmap_busy and self.client and hasattr(self.client, "xmap"):
                    if (now - self.last_quest_xmap_time) >= 3.0:
                        self.last_quest_xmap_time = now
                        self.client.xmap(target_map)
            else:
                self.quest_state = AutoQuestState.EXECUTE_QUEST
            return

        # 4. Thực hiện đánh quái nhiệm vụ
        if self.quest_state == AutoQuestState.EXECUTE_QUEST:
            expected_template = getattr(self.quest_info, "mob_template_id", -1)
            if expected_template == -1:
                target = self.quest_info.mob_name.lower().strip()
                loc = MOB_LOCATION_DATA.get(target)
                if loc:
                    expected_template = loc[1]
                    self.quest_info.mob_template_id = expected_template
                else:
                    return

            target_mob = my_char.mapInfo.find_mob(expected_template, from_x=my_char.cx, from_y=my_char.cy)
            if target_mob:
                my_char.focus_mob(target_mob)
                self.teleport(target_mob.x, target_mob.y)
                if (now - self.last_attack_time) >= 0.12:
                    self.last_attack_time = now
                    self.attack_target(target_mob)

    # ==========================================================================
    # 6. AUTO CHUỖI NHIỆM VỤ MỚI / NHIỆM VỤ CHÍNH TUYẾN (MAIN TASK FSM)
    # ==========================================================================
    def start_auto_main_task(self) -> Tuple[bool, str]:
        """Bật Auto làm chuỗi nhiệm vụ chính tuyến."""
        with self._lock:
            self.is_main_task_enabled = True
            self.auto_revive = True  # Tự động bật Auto Hồi Sinh khi làm nhiệm vụ
            self.main_task_state = MainTaskState.IDLE
            self.main_task_status_message = "Đang khởi động"
            my_char = self._get_my_char()
            task_str = ""
            if my_char:
                info = self._parse_main_task_info(my_char)
                if info and info.is_valid:
                    task_str = f" | {info}"
            msg = f"Auto Nhiệm Vụ: BẬT{task_str} | AutoHS: [ON]"
            return True, msg

    def stop_auto_main_task(self) -> Tuple[bool, str]:
        """Tắt Auto làm chuỗi nhiệm vụ chính tuyến."""
        with self._lock:
            self.is_main_task_enabled = False
            self.main_task_state = MainTaskState.IDLE
            self.main_task_status_message = "Đã dừng"
            SharedHuntCoordinator.release_farming_zone(self._tag())
            return True, "Auto Nhiệm Vụ: TẮT!"

    def toggle_auto_main_task(self, enable: Optional[bool] = None) -> bool:
        """Chuyển đổi trạng thái bật/tắt Auto Nhiệm Vụ Chính Tuyến."""
        if enable is not None:
            if enable:
                self.start_auto_main_task()
            else:
                self.stop_auto_main_task()
        else:
            if self.is_main_task_enabled:
                self.stop_auto_main_task()
            else:
                self.start_auto_main_task()
        return self.is_main_task_enabled

    def get_main_task_status(self) -> Dict[str, Any]:
        """Lấy thông tin tiến độ nhiệm vụ chính tuyến."""
        my_char = self._get_my_char()
        info_str = "Chưa có thông tin"
        map_id = -1
        map_name = "Chưa rõ"
        zone_id = -1
        if my_char:
            info = self._parse_main_task_info(my_char)
            if info:
                info_str = str(info)
            if hasattr(my_char, "mapInfo") and my_char.mapInfo:
                map_id = getattr(my_char.mapInfo, "mapID", -1)
                map_name = getattr(my_char.mapInfo, "mapName", "") or get_map_name(map_id)
                zone_id = getattr(my_char.mapInfo, "zoneID", -1)

        gender = getattr(my_char, "cgender", 0) if my_char else 0
        try:
            gender = int(gender)
        except Exception:
            gender = 0
        combo_sids = self.combat_combo_skills or list(self.TANSAT_SKILLS_BY_GENDER.get(gender, (1, 9, 0)))
        combo_names = [f"{s} ({SKILL_NAMES.get(s, 'Skill')})" for s in combo_sids]
        combo_str = " -> ".join(combo_names)

        fsm_state_str = self.main_task_state.value
        if self.main_task_state == MainTaskState.HUNTING_BOSS:
            if self.bh_state == self.STATE_BH_MOVING:
                fsm_state_str = "Đang di chuyển tới map Boss"
            elif self.bh_state == self.STATE_BH_SCANNING:
                fsm_state_str = "Đang quét các khu tìm Boss"
            elif self.bh_state == self.STATE_BH_COMBAT:
                fsm_state_str = "Đang chiến đấu với Boss"
            elif self.bh_state == self.STATE_BH_LOOTING:
                fsm_state_str = "Đang nhặt đồ Boss rơi"
            else:
                fsm_state_str = "Đang săn Boss nhiệm vụ"

        status_msg = self.main_task_status_message
        if self.main_task_state == MainTaskState.HUNTING_BOSS and self.bh_status_message:
            status_msg = self.bh_status_message

        return {
            "is_enabled": self.is_main_task_enabled,
            "auto_revive": self.auto_revive,
            "revive_mode": self.revive_mode,
            "state": fsm_state_str,
            "status_message": status_msg,
            "task_display": info_str,
            "current_map_id": map_id,
            "current_map_name": map_name,
            "current_zone_id": zone_id,
            "combo_skills": combo_sids,
            "combo_display": combo_str,
            "info": self.main_task_info.__dict__ if self.main_task_info else {},
        }

    def _resolve_report_npc(
        self,
        my_char: Char,
        task: Any,
        mob_name: str,
        farm_map: int,
    ) -> Tuple[int, int, str]:
        """
        Xác định NPC và Map để trả nhiệm vụ.
        Ưu tiên:
        1. Tên NPC / Map được nhắc cụ thể trong mô tả nhiệm vụ (vd: Cui, Thành phố Vegeta).
        2. Nếu farm quái ở các map Fide/Cold/Nappa (map 68-83) -> Báo cho Cui (Map 19, NPC 12).
        3. mapTasks của task nếu server có gửi mapID.
        4. Sư phụ tân thủ theo phái nếu ở map sơ sinh.
        """
        sub_names = getattr(task, "subNames", [])
        task_index = getattr(task, "index", 0)
        current_sub = sub_names[task_index] if (0 <= task_index < len(sub_names)) else ""
        detail = getattr(task, "detail", "")
        content_info = getattr(task, "contentInfo", [])
        content_str = " ".join(content_info) if content_info else ""
        full_text = f"{current_sub} {detail} {content_str}".lower()
        norm_text = normalize_str(full_text)

        # 1. So khớp tên NPC từ KNOWN_REPORT_NPCS
        sorted_npcs = sorted(KNOWN_REPORT_NPCS.keys(), key=lambda k: len(k), reverse=True)
        for k in sorted_npcs:
            if k in full_text or normalize_str(k) in norm_text:
                npc_id, def_map, display_name = KNOWN_REPORT_NPCS[k]
                if "thanh pho vegeta" in norm_text or "vegeta" in norm_text:
                    return npc_id, 19, display_name
                return npc_id, def_map, display_name

        # 2. Nếu trong text có "thành phố vegeta", "vegeta" hoặc "tiểu đội sát thủ" -> Báo cho Cui (Map 19, NPC 12)
        if any(k in norm_text for k in ("vegeta", "tp vegeta", "thanh pho vegeta", "tieu doi sat thu", "sat thu")):
            return 12, 19, "Cui"

        # 3. Theo khu vực farm quái:
        # Các map từ 68 đến 83 là khu vực Fide/Nappa -> Báo cho Cui ở Thành phố Vegeta (Map 19, NPC 12)
        if farm_map in (68, 69, 70, 71, 72, 73, 74, 76, 77, 79, 80, 81, 82, 83) or mob_name in (
            "nappa", "soldier", "appule", "raspberry", "thằn lằn xanh", "quỷ đầu nhọn",
            "quỷ đầu vàng", "quỷ da tím", "quỷ già", "cá sấu", "dơi da xanh", "quỷ chim",
            "lính đầu trọc", "lính tai dài", "lính vũ trụ", "khỉ lông đen", "khỉ giáp sắt",
            "khỉ lông đỏ", "khỉ lông vàng"
        ):
            return 12, 19, "Cui"

        # Các map Xên (92 - 100) -> Báo cho Quy Lão (Map 5, NPC 13) hoặc Vua Vegeta
        if 92 <= farm_map <= 100 or "xên con" in mob_name:
            return 13, 5, "Quy Lão Kame"

        # 4. Kiểm tra mapTasks từ server
        map_tasks = getattr(task, "mapTasks", [])
        if 0 <= task_index < len(map_tasks) and map_tasks[task_index] > 0:
            srv_map = map_tasks[task_index]
            if srv_map == 19:
                return 12, 19, "Cui"
            return 12, srv_map, "NPC Nhiệm Vụ"

        # 5. Mặc định theo hành tinh / Sư phụ
        cgender = getattr(my_char, "cgender", 0)
        home_map = cgender + 21
        sp_id = 0 if cgender == 0 else (2 if cgender == 1 else 1)
        sp_names = {0: "Ông Gôhan", 1: "Ông Paragus", 2: "Ông Moori"}
        return sp_id, home_map, sp_names.get(cgender, "Sư Phụ")

    @classmethod
    def _parse_target_power(cls, text: str) -> int:
        """
        Bóc tách mốc sức mạnh mục tiêu từ văn bản nhiệm vụ.
        Ví dụ:
        '- Đạt 600 tr sức mạnh' -> 600_000_000
        '- Đạt 1.5 tỷ sức mạnh' -> 1_500_000_000
        '- Đạt 16 triệu sức mạnh' -> 16_000_000
        '- Đạt 40tr sức mạnh' -> 40_000_000
        '- Đạt 20.000.000 sức mạnh' -> 20_000_000
        '- Sức mạnh đạt 600 tr' -> 600_000_000
        """
        if not text:
            return 0
        norm = normalize_str(text.lower())
        if not any(k in norm for k in ("suc manh", "sm")):
            return 0

        patterns = [
            r"(?:dat|can|len)\s+([\d\.,]+)\s*(tr|trieu|ty|k|nghin|m|b)?\s*(?:suc manh|sm)",
            r"(?:suc manh|sm)\s*(?:dat|can|len|:)?\s*([\d\.,]+)\s*(tr|trieu|ty|k|nghin|m|b)?",
        ]

        for pat in patterns:
            m = re.search(pat, norm)
            if m:
                val_str = m.group(1).strip()
                unit = m.group(2).strip() if m.group(2) else ""
                if unit:
                    clean_val = val_str.replace(",", ".")
                    try:
                        val = float(clean_val)
                        if unit in ("ty", "b"):
                            return int(val * 1_000_000_000)
                        elif unit in ("tr", "trieu", "m"):
                            return int(val * 1_000_000)
                        elif unit in ("k", "nghin"):
                            return int(val * 1_000)
                    except ValueError:
                        pass
                else:
                    clean_num = val_str.replace(".", "").replace(",", "")
                    if clean_num.isdigit():
                        num = int(clean_num)
                        if num >= 1000:
                            return num
        return 0

    def _parse_main_task_info(self, my_char: Char) -> Optional[MainTaskInfo]:
        """
        Bóc tách thông tin nhiệm vụ chính tuyến từ my_char.task.
        Đối chiếu tên quái trong MOB_LOCATION_DATA và xác định NPC báo cáo.
        """
        task = getattr(my_char, "task", None)
        if not task:
            self.main_task_info.reset()
            return None

        clean_name = getattr(task, "clean_name", "") or getattr(task, "name", "")
        task_id = getattr(task, "taskId", getattr(my_char, "ctaskId", 0))
        task_index = getattr(task, "index", 0)

        sub_names = getattr(task, "subNames", [])
        current_sub = ""
        if 0 <= task_index < len(sub_names):
            current_sub = sub_names[task_index]
        elif sub_names:
            current_sub = sub_names[0]

        detail = getattr(task, "detail", "")
        content_info = getattr(task, "contentInfo", [])
        content_str = " ".join(content_info) if content_info else ""

        full_text = f"{current_sub} {detail} {clean_name} {content_str}".strip()
        lower_text = full_text.lower()
        norm_text = normalize_str(lower_text)

        info = self.main_task_info
        info.task_id = task_id
        info.task_index = task_index
        info.task_name = clean_name
        info.sub_name = current_sub

        # 0. Kiểm tra nhiệm vụ có chữ "đạt ... sức mạnh" trong bước hiện tại (current_sub)
        # Chỉ kiểm tra current_sub (bước hiện tại), KHÔNG kiểm tra detail (mô tả chung)
        # vì detail có thể chứa chữ "Đạt 50 triệu sức mạnh" của toàn bộ chuỗi nhiệm vụ
        norm_sub = normalize_str(current_sub.lower())
        target_power = self._parse_target_power(current_sub)
        is_power_phrase = (target_power > 0) or bool(
            re.search(r"dat.*?(?:suc manh|sm)", norm_sub)
            or re.search(r"(?:suc manh|sm).*?dat", norm_sub)
        )
        if not current_sub and not is_power_phrase:
            norm_full = normalize_str(full_text.lower())
            target_power = self._parse_target_power(full_text)
            is_power_phrase = (target_power > 0) or bool(
                re.search(r"dat.*?(?:suc manh|sm)", norm_full)
                or re.search(r"(?:suc manh|sm).*?dat", norm_full)
            )

        if is_power_phrase:
            c_power = getattr(my_char, "cPower", 0)
            info.is_power_task = True
            info.target_power = target_power if target_power > 0 else 600_000_000
            info.farm_map_id = 122  # Map 122 (Ngũ Hành Sơn) theo chỉ định người dùng
            info.farm_map_name = get_map_name(122)
            info.mob_name = "quái Ngũ Hành Sơn"
            info.is_valid = True

            # Kiểm tra tiến độ đếm từ server (vd: 0/1)
            target_count = 0
            current_count = 0
            counts = getattr(task, "counts", [])
            if 0 <= task_index < len(counts) and counts[task_index] > 0:
                target_count = counts[task_index]
            task_count = getattr(task, "count", -1)
            if task_count != -1:
                current_count = max(0, task_count)

            # Trích xuất từ regex tiến độ dạng (0/1) nếu có
            m_prog = re.search(r"\((\d+)\s*/\s*(\d+)\)", current_sub) or re.search(r"\((\d+)\s*/\s*(\d+)\)", full_text)
            if m_prog:
                c_curr = int(m_prog.group(1))
                c_tar = int(m_prog.group(2))
                if target_count == 0:
                    target_count = c_tar
                if task_count == -1:
                    current_count = c_curr

            # Cơ chế game: Phải đấm quái 1 cái để nhận +xxx sức mạnh thì server mới cập nhật nhiệm vụ (0/1 -> 1/1).
            # Mặc định target_count tối thiểu là 1 nếu server chưa hoàn thành.
            if target_count == 0:
                target_count = 1

            info.target_count = target_count
            info.current_count = current_count

            # Chỉ hoàn thành khi server đã xác nhận đủ (current_count >= target_count)
            # VÀ sức mạnh >= target_power (nếu xác định được mốc sức mạnh)
            is_completed = (current_count >= target_count)
            if target_power > 0:
                is_completed = is_completed and (c_power >= target_power)

            info.is_report_step = is_completed

            # Xác định NPC & Map cần báo cáo
            npc_id, report_map, npc_name = self._resolve_report_npc(my_char, task, "", info.farm_map_id)
            info.report_npc_id = npc_id
            info.report_map_id = report_map
            info.report_npc_name = npc_name
            info.report_map_name = get_map_name(report_map)
            return info

        # 1. Tìm quái trong MOB_LOCATION_DATA (ưu tiên sub-task hiện tại trước)
        matched_mob = None
        sorted_mobs = sorted(MOB_LOCATION_DATA.keys(), key=lambda k: len(k), reverse=True)
        lower_sub = current_sub.lower()
        norm_sub = normalize_str(lower_sub)

        for mob in sorted_mobs:
            if mob in lower_sub or normalize_str(mob) in norm_sub:
                matched_mob = mob
                break

        # Nếu sub-task không nhắc tới quái thường, kiểm tra xem có phải Boss không trước khi quét detail
        if not matched_mob:
            boss_cand, _, _ = self._resolve_task_boss(current_sub, full_text, task, task_index)
            if not boss_cand:
                for mob in sorted_mobs:
                    if mob in lower_text or normalize_str(mob) in norm_text:
                        matched_mob = mob
                        break

        # 2. Bóc tách số lượng cần diệt & số lượng hiện tại
        target_count = 0
        current_count = 0

        counts = getattr(task, "counts", [])
        if 0 <= task_index < len(counts) and counts[task_index] > 0:
            target_count = counts[task_index]

        task_count = getattr(task, "count", -1)
        if task_count != -1:
            current_count = max(0, task_count)

        # Trích xuất từ regex tiến độ dạng (42/100)
        m_prog = re.search(r"\((\d+)\s*/\s*(\d+)\)", current_sub) or re.search(r"\((\d+)\s*/\s*(\d+)\)", full_text)
        if m_prog:
            c_curr = int(m_prog.group(1))
            c_tar = int(m_prog.group(2))
            if target_count == 0:
                target_count = c_tar
            if task_count == -1:
                current_count = c_curr

        if target_count == 0:
            m_tar = re.search(r"(?:tiêu diệt|hạ|giết|danh|diet)\s+(\d+)", lower_text)
            if m_tar:
                target_count = int(m_tar.group(1))
            else:
                target_count = 1

        info.target_count = target_count
        info.current_count = current_count

        # 3. Xác định xem là bước Đánh Quái hay Báo Cáo
        is_completed_farming = (target_count > 0 and current_count >= target_count)
        is_explicit_report_text = any(w in lower_text for w in (
            "báo cáo", "bao cao", "gặp", "gap", "nói chuyện", "noi chuyen",
            "trả nhiệm vụ", "tra nhiem vu", "đến gặp", "ve gap", "trở về"
        )) and not (matched_mob and not is_completed_farming)

        if matched_mob:
            loc = MOB_LOCATION_DATA[matched_mob]
            info.mob_name = matched_mob
            info.farm_map_id = loc[0]
            info.mob_template_id = loc[1]
            info.farm_map_name = get_map_name(loc[0])
            info.is_valid = True

            if is_completed_farming:
                info.is_report_step = True
            else:
                info.is_report_step = False
        else:
            # Kiểm tra xem có phải nhiệm vụ tiêu diệt BOSS hay không
            # Ví dụ: "- Tiêu diệt Poc", "- Tiêu diệt Pic", "- Tiêu diệt Kuku", "- Tiêu diệt Mập đầu đinh"
            boss_name, wait_map_id, wait_map_name = self._resolve_task_boss(current_sub, full_text, task, task_index)
            if boss_name:
                info.is_boss_task = True
                info.boss_name = boss_name
                norm_b = normalize_str(boss_name)
                if "kuku" in norm_b:
                    info.boss_spawn_maps = [68, 69, 70, 71, 72]
                elif "map dau dinh" in norm_b:
                    info.boss_spawn_maps = [64, 65, 66, 67]
                elif "rambo" in norm_b:
                    info.boss_spawn_maps = [73, 74, 75, 76, 77]
                elif any(k in norm_b for k in ("so 4", "so 3", "so 2", "so 1", "tieu doi truong", "ginyu")):
                    info.boss_spawn_maps = [81, 82, 83]
                else:
                    info.boss_spawn_maps = [wait_map_id] if wait_map_id > 0 else []
                info.farm_map_id = wait_map_id
                info.farm_map_name = wait_map_name or ("Điểm săn Boss" if wait_map_id > 0 else "Chờ thông báo Boss")
                info.is_valid = True

                if is_completed_farming:
                    info.is_report_step = True
                else:
                    info.is_report_step = False
            elif is_explicit_report_text or is_completed_farming:
                info.is_report_step = True
                info.is_valid = True
            else:
                info.is_valid = False
                return None

        # 4. Xác định NPC & Map cần báo cáo
        npc_id, report_map, npc_name = self._resolve_report_npc(my_char, task, matched_mob or info.boss_name or "", info.farm_map_id)
        info.report_npc_id = npc_id
        info.report_map_id = report_map
        info.report_npc_name = npc_name
        info.report_map_name = get_map_name(report_map)

        return info

    @classmethod
    def _resolve_task_boss(
        cls,
        sub_name: str,
        full_text: str,
        task: Optional[Any] = None,
        task_index: int = 0,
    ) -> Tuple[Optional[str], int, str]:
        """
        Nhận diện mục tiêu Boss từ văn bản nhiệm vụ một cách hoàn toàn động.
        KHÔNG sử dụng cấu hình cứng (không bịa thông tin map).
        Cơ chế:
        1. Bóc tách tên mục tiêu từ sub_name (vd: "- Tiêu diệt Poc" -> "Poc").
        2. Nếu tên mục tiêu không thuộc danh mục quái thường (MOB_LOCATION_DATA), đó là Boss nhiệm vụ.
        3. Điểm chờ (nếu có): Lấy từ mapTasks của server hoặc map được nhắc đến trong mô tả nhiệm vụ.
           (Nếu không có, wait_map_id = -1, bot sẽ đứng chờ thông báo ChatVip để biết chính xác map Boss xuất hiện).
        """
        m_boss = re.search(
            r"(?:tiêu diệt|tieu diet|hạ|ha|giết|giet|đánh bại|danh bai|diet)\s+(?:boss\s+)?(?:bọn\s+|tên\s+|con\s+)?([a-zA-Z0-9à-ỹÀ-Ỹ\s]+?)(?:\s*\(\s*\d+\s*/\s*\d+\s*\)|\s+(?:tại|ở)\s+.*|$)",
            sub_name,
            re.IGNORECASE,
        )
        if not m_boss:
            return None, -1, ""

        candidate = m_boss.group(1).strip()
        if not candidate or candidate.isdigit():
            return None, -1, ""

        norm_cand = normalize_str(candidate.lower())
        # Nếu trùng tên quái thường trong MOB_LOCATION_DATA hoặc quái xên con farm theo số lượng lớn -> không phải boss đơn lẻ
        if any(norm_cand == normalize_str(k) for k in MOB_LOCATION_DATA.keys()):
            return None, -1, ""
        if norm_cand.startswith(("xen con", "xên con")):
            return None, -1, ""

        boss_name = candidate.strip().title()

        # Xác định điểm chờ săn (nếu server hoặc mô tả nhiệm vụ có cung cấp)
        wait_map_id = -1
        wait_map_name = ""

        # Ưu tiên các map chờ săn cố định nổi tiếng của nhóm Boss Nappa
        norm_b = normalize_str(boss_name)
        if "kuku" in norm_b:
            wait_map_id = 68
            wait_map_name = get_map_name(68)
        elif "map dau dinh" in norm_b:
            wait_map_id = 64
            wait_map_name = get_map_name(64)
        elif "rambo" in norm_b:
            wait_map_id = 73
            wait_map_name = get_map_name(73)
        elif any(k in norm_b for k in ("so 4", "so 3", "so 2", "so 1", "tieu doi truong", "ginyu")):
            wait_map_id = 81
            wait_map_name = get_map_name(81)

        # 1. Kiểm tra mapTasks từ server nếu chưa xác định
        if wait_map_id <= 0 and task:
            map_tasks = getattr(task, "mapTasks", [])
            if 0 <= task_index < len(map_tasks) and map_tasks[task_index] > 0:
                wait_map_id = map_tasks[task_index]
                wait_map_name = get_map_name(wait_map_id)

        # 2. Nếu chưa có, đối chiếu trực tiếp với danh mục MAP_NAMES của game
        if wait_map_id <= 0:
            norm_full = normalize_str(full_text)
            for mid, mname in MAP_NAMES.items():
                if len(mname) >= 6 and normalize_str(mname) in norm_full:
                    wait_map_id = mid
                    wait_map_name = mname
                    break

        return boss_name, wait_map_id, wait_map_name

    def _step_main_task(self, my_char: Char) -> None:
        """Thực thi một chu kỳ làm nhiệm vụ chính tuyến."""
        # Hook Auto Routine Tagging: Làm nhiệm vụ (Label 1)
        collector = getattr(self.client, "data_collector", None)
        if collector and collector.is_recording:
            collector.record_sample(self.client, 1)

        now = time.time()
        info = self._parse_main_task_info(my_char)
        if not info or not info.is_valid:
            self.main_task_status_message = "Không có nhiệm vụ phù hợp trong dữ liệu hoặc chưa nhận diện được mục tiêu."
            return

        xst = self.client.xmap_status() if (self.client and hasattr(self.client, "xmap_status")) else {}
        is_xmap_busy = xst.get("is_acting", False) or xst.get("is_running", False)

        if info.is_report_step:
            self.main_task_state = MainTaskState.NAVIGATE_TO_REPORT
            self._handle_main_task_reporting(my_char, is_xmap_busy, now)
        elif info.is_power_task:
            self.main_task_state = MainTaskState.FARMING_POWER
            self._handle_main_task_power_farm(my_char, is_xmap_busy, now)
        elif info.is_boss_task:
            self.main_task_state = MainTaskState.WAITING_BOSS
            self._handle_main_task_boss_hunt(my_char, is_xmap_busy, now)
        else:
            self.main_task_state = MainTaskState.FARMING
            self._handle_main_task_farming(my_char, is_xmap_busy, now)

    def _handle_main_task_boss_hunt(self, my_char: Char, is_xmap_busy: bool, now: float) -> None:
        """
        Xử lý nhiệm vụ tiêu diệt Boss:
        1. Đăng ký Boss vào mục tiêu săn để nhận diện thông báo Chat VIP.
        2. Nếu phát hiện Boss đã xuất hiện (qua Chat VIP hoặc đồng đội báo):
           - Lập tức chuyển sang Boss Hunter để tới map, quét khu và pem Boss.
        3. Nếu chưa có thông báo:
           - Tự động di chuyển tới điểm săn tiềm năng (ví dụ: Thành phố phía Bắc) để chờ và quét boss tại chỗ.
        """
        info = self.main_task_info
        b_name = info.boss_name
        norm_b = normalize_str(b_name)

        # 1. Đảm bảo tên Boss nằm trong mục tiêu săn và chỉ tập trung vào Boss này
        self.target_bosses = {norm_b}
        self.hunt_all = False

        # 2. Nếu Boss hiện tại không khớp với Boss nhiệm vụ hiện tại (ví dụ vừa giết Kuku xong và chuyển sang Mập đầu đinh)
        if self.current_boss:
            curr_b_norm = normalize_str(self.current_boss.name)
            if not ((norm_b in curr_b_norm) or (curr_b_norm in norm_b)):
                self.current_boss = None
                self._reset_boss_fight_tracking()
                self.bh_state = self.STATE_BH_IDLE

        # 3. Kiểm tra xem Boss mục tiêu có đang sống và đã xuất hiện ở map nào không
        active_target_boss = None
        # Ưu tiên kiểm tra SharedHuntCoordinator
        coord_boss = SharedHuntCoordinator.get_active_boss(b_name)
        if coord_boss and not coord_boss.get("is_died", False) and coord_boss.get("map_id", -1) != -1:
            active_target_boss = Boss(
                name=coord_boss.get("name", b_name),
                map_id=coord_boss.get("map_id", -1),
                zone_id=coord_boss.get("zone_id", -1),
                map_name=get_map_name(coord_boss.get("map_id", -1)),
            )

        # Nếu coordinator chưa có, kiểm tra danh sách list_bosses nhận từ Chat VIP
        if not active_target_boss:
            for b in reversed(self.get_alive_bosses()):
                norm_curr_b = normalize_str(b.name)
                is_match = (norm_b in norm_curr_b) or (norm_curr_b in norm_b)
                if is_match and not b.is_died:
                    # Nếu map_id chưa giải được (-1), thử phân giải lại
                    if b.map_id == -1 and b.map_name:
                        b.map_id = self.resolve_boss_map_id(b.name, b.map_name)
                    if b.map_id != -1:
                        active_target_boss = b
                        break

        # Nếu phát hiện Boss đã xuất hiện:
        if active_target_boss is not None:
            self.main_task_state = MainTaskState.HUNTING_BOSS
            need_reset = (
                not self.current_boss
                or self.current_boss.name != active_target_boss.name
                or self.current_boss.map_id != active_target_boss.map_id
                or self.bh_state == self.STATE_BH_IDLE
            )
            if need_reset:
                self.current_boss = active_target_boss
                self.scanned_zones.clear()
                self.bh_waiting_zone = -1
                self.bh_state = self.STATE_BH_MOVING
                z_desc = f"[Khu {active_target_boss.zone_id:02d}]" if active_target_boss.zone_id >= 0 else "(đang dò khu...)"
                self.main_task_status_message = f"Phát hiện Boss '{active_target_boss.name}' tại {active_target_boss.map_name} {z_desc}. Bắt đầu săn!"

            self._step_boss_hunter(my_char)

            if self.bh_state != self.STATE_BH_IDLE and self.bh_status_message:
                self.main_task_status_message = self.bh_status_message
            return

        # 3. Nếu đang trong trận combat với Boss hiện tại:
        if self.current_boss and not self.current_boss.is_died:
            self.main_task_state = MainTaskState.HUNTING_BOSS
            self.main_task_status_message = f"Đang chiến đấu tiêu diệt Boss '{self.current_boss.name}' tại {self.current_boss.map_name}!"
            self._step_boss_hunter(my_char)
            if self.bh_state != self.STATE_BH_IDLE and self.bh_status_message:
                self.main_task_status_message = self.bh_status_message
            return

        # 4. Chưa có thông báo Boss: Di chuyển tới điểm săn boss tiềm năng để chờ
        curr_map = getattr(my_char.mapInfo, "mapID", -1)
        target_wait_map = info.boss_spawn_maps[0] if info.boss_spawn_maps else info.farm_map_id

        if target_wait_map > 0 and curr_map != target_wait_map:
            wait_map_name = get_map_name(target_wait_map)
            self.main_task_status_message = f"Chờ thông báo Boss '{b_name}'. Đang tới điểm săn {wait_map_name} [Map {target_wait_map}]..."
            if not is_xmap_busy and self.client and hasattr(self.client, "xmap"):
                if (now - self.last_main_task_xmap_time) >= 3.0:
                    self.last_main_task_xmap_time = now
                    self.client.xmap(target_wait_map)
            return

        # 5. Đã có mặt tại điểm săn: Quét kiểm tra xem Boss có đang ở map hiện tại không
        found_in_map = self._find_boss_in_current_map(my_char)
        if found_in_map is not None:
            curr_zone = getattr(my_char.mapInfo, "zoneID", -1)
            target_x = getattr(found_in_map, "cx", getattr(found_in_map, "x", my_char.cx))
            target_y = getattr(found_in_map, "cy", getattr(found_in_map, "y", my_char.cy))
            self.current_boss = Boss(
                name=getattr(found_in_map, "cName", b_name),
                map_id=curr_map,
                zone_id=curr_zone,
                map_name=get_map_name(curr_map),
            )
            self.last_boss_pos = (target_x, target_y)
            self._log_auto(f"[+] Bắt gặp Boss '{self.current_boss.name}' tại điểm săn {get_map_name(curr_map)} Khu {curr_zone}! Bắt đầu pem!", is_important=True)
            self._reset_boss_fight_tracking()
            self.bh_state = self.STATE_BH_COMBAT
            self._step_boss_hunter(my_char)
            return

        # Đang chờ tại điểm săn: Điều phối chia mỗi acc 1 khu để mở rộng tầm nhìn radar
        if target_wait_map > 0 and curr_map == target_wait_map:
            if self._coordinate_farming_zone(my_char, target_wait_map, now):
                return

        loc_name = get_map_name(curr_map) if curr_map > 0 else "điểm săn"
        curr_z = getattr(my_char.mapInfo, "zoneID", 0)
        self.main_task_status_message = f"Đang có mặt tại {loc_name} [Khu {curr_z:02d}]. Chờ thông báo Boss '{b_name}' xuất hiện..."

    def _coordinate_farming_zone(self, my_char: Char, map_id: int, now: float) -> bool:
        """
        Điều phối chia khu thông minh giữa các acc đồng đội khi cùng farm quái trong 1 map.
        - Tránh hoàn toàn việc 2 acc ở cùng 1 khu tranh quái nhiệm vụ.
        - Tự động đổi sang khu khác (ưu tiên khu vắng người) nếu khu hiện tại đã có đồng đội farm.
        Trả về True nếu đang trong quá trình đổi khu (cần chờ), False nếu đã ở đúng khu của mình.
        """
        curr_zone = getattr(my_char.mapInfo, "zoneID", -1)
        if curr_zone < 0:
            return True  # Chưa tải xong thông tin khu

        acc_tag = self._tag()
        my_claimed_zone = SharedHuntCoordinator.get_farming_zone_for_acc(acc_tag, map_id)

        # Nếu đã ở đúng khu mình đã claim trước đó -> chỉ cần cập nhật heartbeat
        if my_claimed_zone is not None and curr_zone == my_claimed_zone:
            SharedHuntCoordinator.claim_farming_zone(acc_tag, map_id, curr_zone)
            return False

        # Kiểm tra xem khu hiện tại có đang bị đồng đội khác chiếm không
        occupied_zones = SharedHuntCoordinator.get_claimed_farming_zones(map_id, exclude_acc=acc_tag)

        if curr_zone in occupied_zones:
            # Khu hiện tại đã có đồng đội đang farm!
            last_change = getattr(self, "_last_farming_zone_change_time", 0.0)
            if (now - last_change) < 2.5:
                return True  # Chờ giãn cách đổi khu

            self._last_farming_zone_change_time = now

            # Lấy danh sách khu vực có sẵn trong map
            zones = getattr(my_char.mapInfo, "zones", [])
            if zones:
                available_zones = [z.zoneId for z in zones if z.zoneId >= 0]
            else:
                available_zones = list(range(0, 15))
                if self.client and hasattr(self.client, "request_zones"):
                    self.client.request_zones()

            # Lọc các khu chưa có đồng đội nào chiếm và khác khu hiện tại
            candidate_zones = [z for z in available_zones if z not in occupied_zones and z != curr_zone]
            if not candidate_zones:
                candidate_zones = [z for z in available_zones if z != curr_zone]

            if not candidate_zones:
                # Không còn khu nào khác, chấp nhận ở lại khu hiện tại
                SharedHuntCoordinator.claim_farming_zone(acc_tag, map_id, curr_zone)
                return False

            # Ưu tiên khu ít người chơi nhất nếu có thông tin ZoneInfo
            target_zone = candidate_zones[0]
            if zones:
                valid_objs = [z for z in zones if z.zoneId in candidate_zones]
                if valid_objs:
                    valid_objs.sort(key=lambda z: getattr(z, "numPlayer", 0))
                    target_zone = valid_objs[0].zoneId

            # Giữ chỗ khu mới ngay để các acc khác không chọn trùng
            SharedHuntCoordinator.claim_farming_zone(acc_tag, map_id, target_zone)

            self._log_auto(
                f"[TASK] Khu {curr_zone:02d} đã có đồng đội đang farm quái! Đang chuyển sang Khu {target_zone:02d} để chia khu...",
                is_important=True,
            )
            if self.client and hasattr(self.client, "change_zone"):
                self.client.change_zone(target_zone)
            return True

        # Khu hiện tại hoàn toàn trống (chưa có đồng đội nào farm) -> Claim ngay!
        SharedHuntCoordinator.claim_farming_zone(acc_tag, map_id, curr_zone)
        return False

    def _handle_main_task_farming(self, my_char: Char, is_xmap_busy: bool, now: float) -> None:
        """Xử lý di chuyển đến map và đánh quái nhiệm vụ."""
        info = self.main_task_info
        curr_map = getattr(my_char.mapInfo, "mapID", -1)

        # 1. Nếu chưa tới map farm -> di chuyển bằng Xmap
        if curr_map != info.farm_map_id:
            SharedHuntCoordinator.release_farming_zone(self._tag(), curr_map)
            self.main_task_status_message = f"Đang di chuyển đến {info.farm_map_name} [Map {info.farm_map_id}] để đánh {info.mob_name}..."
            if not is_xmap_busy and self.client and hasattr(self.client, "xmap"):
                if (now - self.last_main_task_xmap_time) >= 3.0:
                    self.last_main_task_xmap_time = now
                    self.client.xmap(info.farm_map_id)
            return

        # 2. Đang ở map farm: Điều phối chia khu thông minh giữa các acc đồng đội (tránh tranh quái)
        if self._coordinate_farming_zone(my_char, info.farm_map_id, now):
            return

        # 3. Đang ở đúng khu của mình: Tìm quái mục tiêu
        curr_z = getattr(my_char.mapInfo, "zoneID", 0)
        self.main_task_status_message = f"Đang tiêu diệt {info.mob_name} ({info.current_count}/{info.target_count}) tại {info.farm_map_name} [Khu {curr_z:02d}]"
        target_mob = my_char.mapInfo.find_mob(info.mob_template_id, from_x=my_char.cx, from_y=my_char.cy)
        if not target_mob:
            target_mob = my_char.mapInfo.find_mob(info.mob_name, from_x=my_char.cx, from_y=my_char.cy)

        if target_mob:
            my_char.focus_mob(target_mob)
            self.teleport(target_mob.x, target_mob.y)
            attack_delay = getattr(self, "combat_attack_delay", 0.1)
            if (now - self.last_attack_time) >= attack_delay:
                self.last_attack_time = now
                self.attack_target(target_mob)

        # Nhặt vật phẩm rơi
        if self.auto_pick:
            self._step_loot_ground_items(my_char)

    def _handle_main_task_power_farm(self, my_char: Char, is_xmap_busy: bool, now: float) -> None:
        """
        Xử lý nhiệm vụ đạt mốc sức mạnh (ví dụ: '- Đạt 600 tr sức mạnh'):
        1. Kiểm tra sức mạnh hiện tại (cPower). Nếu đã đạt -> chuyển sang bước Báo Cáo.
        2. Nếu chưa đạt:
           - Di chuyển ra Map 122 (Ngũ Hành Sơn) theo chỉ định của người dùng.
           - Tại Map 122, tìm quái gần nhất và tấn công liên tục để up sức mạnh.
           - Nhặt vật phẩm rơi nếu bật auto_pick.
        """
        info = self.main_task_info
        curr_power = getattr(my_char, "cPower", 0)
        target_power = info.target_power

        # 1. Đã hoàn thành tiến độ (cả số lượng server đếm và mốc sức mạnh) -> chuyển sang báo cáo
        if info.is_report_step:
            self.main_task_state = MainTaskState.NAVIGATE_TO_REPORT
            self._log_auto(
                f"[TASK] Đã hoàn thành nhiệm vụ sức mạnh ({format_big_number(curr_power)}/{format_big_number(target_power)})! Bắt đầu đi báo cáo nhiệm vụ...",
                is_important=True,
            )
            self._handle_main_task_reporting(my_char, is_xmap_busy, now)
            return

        curr_map = getattr(my_char.mapInfo, "mapID", -1)
        target_farm_map = 122

        # 2. Chưa tới Map 122 -> di chuyển bằng Xmap
        if curr_map != target_farm_map:
            SharedHuntCoordinator.release_farming_zone(self._tag(), curr_map)
            pct_str = f"({info.current_count}/{info.target_count})" if info.target_count < 1000 else f"({format_big_number(curr_power)}/{format_big_number(target_power)})"
            self.main_task_status_message = (
                f"Nhiệm vụ sức mạnh {pct_str}: Đang di chuyển ra Map 122 ({get_map_name(122)}) để farm quái..."
            )
            if not is_xmap_busy and self.client and hasattr(self.client, "xmap"):
                if (now - self.last_main_task_xmap_time) >= 3.0:
                    self.last_main_task_xmap_time = now
                    self.client.xmap(target_farm_map)
            return

        # 3. Đang ở Map 122: Điều phối chia khu thông minh giữa các acc đồng đội (tránh tranh quái)
        if self._coordinate_farming_zone(my_char, target_farm_map, now):
            return

        # 4. Đang ở đúng khu của mình -> Tàn sát (tansat) quái để nhận +xxx sức mạnh cập nhật nhiệm vụ
        pct_str = f"({info.current_count}/{info.target_count})" if info.target_count < 1000 else f"({format_big_number(curr_power)}/{format_big_number(target_power)})"
        curr_z = getattr(my_char.mapInfo, "zoneID", 0)
        self.main_task_status_message = (
            f"Đang tàn sát quái tại Map 122 [Ngũ Hành Sơn] [Khu {curr_z:02d}] - Tiến độ: {pct_str} (SM: {format_big_number(curr_power)})"
        )

        # 4.1 Nhặt vật phẩm rơi nếu có
        if self.auto_pick and self._step_loot_ground_items(my_char):
            return

        # 4.2 Tìm quái còn sống trong map (ưu tiên gần nhất)
        mobs = list(my_char.mapInfo.mobs.values())
        candidate_mobs = [
            m for m in mobs
            if getattr(m, "status", 0) not in (0, 1) and getattr(m, "hp", 0) > 0
            and (not self.avoid_super_mob or not getattr(m, "isBoss", False))
        ]

        if candidate_mobs:
            target_mob = min(candidate_mobs, key=lambda m: my_char.distance_to(m.x, m.y))
            my_char.focus_mob(target_mob)
            self.teleport(target_mob.x, target_mob.y)
            attack_delay = getattr(self, "combat_attack_delay", 0.1)
            if (now - self.last_attack_time) >= attack_delay:
                self.last_attack_time = now
                self.attack_target(target_mob)
        else:
            self.main_task_status_message = (
                f"Đang chờ quái hồi sinh tại Map 122 [Ngũ Hành Sơn]... - Tiến độ: {pct_str}"
            )

    def _handle_main_task_reporting(self, my_char: Char, is_xmap_busy: bool, now: float) -> None:
        """Xử lý di chuyển đến map của NPC và giao tiếp để trả nhiệm vụ."""
        info = self.main_task_info
        curr_map = getattr(my_char.mapInfo, "mapID", -1)

        # 1. Di chuyển đến map NPC báo cáo
        if curr_map != info.report_map_id:
            SharedHuntCoordinator.release_farming_zone(self._tag())
            self.main_task_status_message = f"Đang di chuyển tới {info.report_map_name} [Map {info.report_map_id}] để báo cáo cho {info.report_npc_name}..."
            if not is_xmap_busy and self.client and hasattr(self.client, "xmap"):
                if (now - self.last_main_task_xmap_time) >= 3.0:
                    self.last_main_task_xmap_time = now
                    self.client.xmap(info.report_map_id)
            return

        # 2. Đang ở map NPC: Tìm NPC và mở menu báo cáo
        self.main_task_status_message = f"Đang gặp {info.report_npc_name} tại {info.report_map_name} để báo cáo nhiệm vụ..."
        npc = my_char.mapInfo.find_npc(info.report_npc_id)
        if npc:
            npc_x = int(npc.get("x", 0))
            npc_y = int(npc.get("y", 0))
            self.teleport(npc_x - 15, npc_y)
            svc = self._service()
            if svc and (now - self.last_main_task_report_time) >= 2.0:
                self.last_main_task_report_time = now
                self.main_task_state = MainTaskState.REPORTING
                svc.openMenu(info.report_npc_id)
                time.sleep(0.4)
                svc.confirmMenu(info.report_npc_id, 0)
                self._log_auto(f"Đã báo cáo nhiệm vụ [{info.task_name}] cho {info.report_npc_name} tại {info.report_map_name}! Đang chờ nhiệm vụ tiếp theo...", is_important=True)
                SharedHuntCoordinator.release_farming_zone(self._tag())
                info.reset()

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
        my_char = self._get_my_char()
        gender = getattr(my_char, "cgender", 0) if my_char else 0
        try:
            gender = int(gender)
        except Exception:
            gender = 0
        combo_sids = self.combat_combo_skills or list(self.TANSAT_SKILLS_BY_GENDER.get(gender, (1, 9, 0)))
        combo_names = [f"{s} ({SKILL_NAMES.get(s, 'Skill')})" for s in combo_sids]
        combo_str = " -> ".join(combo_names)

        return {
            "is_ak": self.is_ak,
            "is_tansat": self.is_tansat,
            "tansat_mode": self.tansat_mode,
            "avoid_super_mob": self.avoid_super_mob,
            "auto_pick": self.auto_pick,
            "pick_gem_only": self.pick_gem_only,
            "auto_pean": self.auto_pean,
            "auto_revive": self.auto_revive,
            "combo_skills": combo_sids,
            "combo_display": combo_str,
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
    def auto_attack_enabled(self) -> bool:
        """Alias cho is_ak."""
        return self.is_ak

    @property
    def auto_pickup(self) -> bool:
        """Alias cho auto_pick."""
        return self.auto_pick

    @property
    def auto_train_pet_enabled(self) -> bool:
        """Alias cho train_pet.is_enabled."""
        return bool(getattr(self, "train_pet", None) and getattr(self.train_pet, "is_enabled", False))

    @property
    def auto_train_enabled(self) -> bool:
        """Alias cho train_new_acc.is_enabled."""
        return bool(getattr(self, "train_new_acc", None) and getattr(self.train_new_acc, "is_enabled", False))

    @property
    def is_enabled(self) -> bool:
        """Kiểm tra xem có bất kỳ tính năng tự động nào đang bật hay không."""
        return (
            self.is_boss_hunter_enabled
            or self.auto_revive
            or self.is_quest_enabled
            or self.is_main_task_enabled
            or self.is_ak
            or self.is_tansat
            or self.is_shuttle_enabled
            or self.auto_train_pet_enabled
            or self.auto_train_enabled
            or self.auto_pick
            or self.auto_pean
            or self.auto_use_item_enabled
        )

    @property
    def is_revive_enabled(self) -> bool:
        """Alias cho AutoReviveManager.is_enabled."""
        return self.auto_revive

    def clear(self) -> None:
        """Xóa toàn bộ lịch sử boss đã lưu (khắc phục lỗi khi gọi client.boss_manager.clear())."""
        with self._lock:
            self.list_bosses.clear()

    def clear_bosses(self) -> None:
        """Bí danh của clear()."""
        self.clear()

    def get_active_summary_list(self) -> List[str]:
        """Trả về danh sách tên các module auto đang hoạt động."""
        active = []
        if self.is_boss_hunter_enabled:
            active.append("Săn Boss")
        if self.is_ak:
            active.append("Tự Đánh")
        if getattr(self, "is_tansat", False):
            mode_str = f" ({self.tansat_mode})" if getattr(self, "tansat_mode", None) else ""
            active.append(f"Tàn Sát{mode_str}")
        if self.auto_pick:
            active.append("Tự Nhặt")
        if self.auto_pean:
            active.append("Tự Dùng Đậu")
        if self.auto_revive:
            active.append("Tự Hồi Sinh")
        if self.is_quest_enabled:
            active.append("Auto Bò Mộng")
        if self.is_main_task_enabled:
            active.append("Auto NV Chính Tuyến")
        if self.is_shuttle_enabled:
            active.append("Auto Đi Lại")
        if self.auto_train_pet_enabled:
            active.append("Úp Đệ")
        if self.auto_train_enabled:
            active.append("NV Tân Thủ")
        if self.auto_use_item_enabled:
            active.append("Dùng Vật Phẩm")
        return active

    def get_active_summary_str(self) -> str:
        """Trả về chuỗi tổng hợp các tính năng auto đang hoạt động."""
        active = self.get_active_summary_list()
        return ", ".join(active) if active else "Không"

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

    def set_mode(self, mode: str) -> bool:
        """Alias cho AutoReviveManager.set_mode()."""
        return self.set_auto_revive_mode(mode)

    def start_auto(self, item_id: int, interval_minutes: float) -> Tuple[bool, str]:
        """Alias cho AutoUseItemManager.start_auto."""
        return self.start_auto_use_item(item_id, interval_minutes)

    def start(self, *args, **kwargs) -> Any:
        """Đa hình hỗ trợ gọi start() cũ."""
        if args and isinstance(args[0], (list, set)):
            return self.start_auto_hunt(targets=list(args[0]))
        if len(args) >= 2 and isinstance(args[0], int) and isinstance(args[1], int):
            return self.start_shuttle(args[0], args[1], args[2] if len(args) > 2 else 0)
        if kwargs.get("quest") or kwargs.get("nvbm"):
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
        if m_lower in ("pet", "mypet", "detu", "attack_my_pet"):
            atk_mode = AutoTrainPetAttackMode.ATTACK_MY_PET
        elif m_lower in ("me", "myself", "banthan", "attack_myself"):
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
