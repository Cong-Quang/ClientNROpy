# -*- coding: utf-8 -*-
"""
Tự động làm nhiệm vụ Bò Mộng hằng ngày (AutoQuest).
Port từ module asyncio (controller.account) sang kiến trúc ClientNROpy hiện tại:
- ClientNRO (myChar / service / xmap_controller / combat_manager / controller)
- Luồng nền threading (giống BossHunter / CombatManager), log bằng print.
Đảm bảo 1 file chỉ chứa đúng 1 class chính (AutoQuest) + Enum/QuestInfo phụ trợ.
"""

import re
import time
import math
import threading
from enum import Enum
from typing import Optional, Tuple, Dict, Any, List

# (map_id, mob_template_id) cho từng tên quái trong nhiệm vụ Bò Mộng.
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
BO_MONG_MAP_ID = 47
BO_MONG_NPC_TEMPLATE_ID = 17
# Khoảng cách tối đa để mở menu NPC (server check ~60px)
NPC_INTERACT_DISTANCE = 60


def is_char_dead(ch) -> bool:
    """Hàm kiểm tra chết duy nhất cho AutoQuest.

    Chết thật khi: đã đồng bộ HP full (cHPFull > 0) mà cHP <= 0,
    hoặc statusMe == 14. Guard cHPFull > 0 để không nhầm lúc chưa
    đồng bộ chỉ số (tránh back về nhà oan).
    """
    if ch is None:
        return False
    try:
        no_hp = getattr(ch, "cHPFull", 0) > 0 and getattr(ch, "cHP", 1) <= 0
        status_dead = getattr(ch, "statusMe", 1) == 14
        return bool(no_hp or status_dead)
    except Exception:
        return False


class AutoState(Enum):
    IDLE = "Đang nghỉ"
    GET_QUEST = "Đi nhận nhiệm vụ"
    NAVIGATE_TO_MAP = "Di chuyển đến map"
    SELECT_ZONE = "Chọn khu vực"
    EXECUTE_QUEST = "Thực hiện nhiệm vụ"
    REPORT_QUEST = "Đi trả nhiệm vụ"


class QuestInfo:
    def __init__(self):
        self.is_valid = False
        self.mob_name = ""
        self.map_name = ""
        self.target_count = 0
        self.initial_count = 0
        self.kill_count = 0
        self.quests_remaining = 0  # Số NV còn lại trong ngày
        self.quests_total = 0      # Tổng số NV trong ngày

    @property
    def current_progress(self):
        return self.initial_count + self.kill_count

    def __str__(self):
        if not self.is_valid:
            return "QuestInfo(Không có nhiệm vụ)"
        return (f"NV: 'Hạ {self.mob_name}', Map: '{self.map_name}', "
                f"Tiến độ: {self.current_progress}/{self.target_count}")


class AutoQuest:
    """Máy trạng thái auto nhiệm vụ Bò Mộng (chạy luồng nền)."""

    def __init__(self, client=None):
        self.client = client
        self.quest_info = QuestInfo()
        self.current_state = AutoState.IDLE
        self.is_running = False

        # Thống kê
        self.start_time: Optional[float] = None
        self.quests_completed = 0
        self.total_kills = 0

        self._lock = threading.Lock()
        self._worker_started = False
        self._start_worker()

        # Đăng ký callback menu NPC + kill quái (nếu có controller)
        try:
            controller = getattr(self.client, "controller", None)
            if controller is not None:
                if hasattr(controller, "on_npc_menu_callbacks"):
                    controller.on_npc_menu_callbacks.append(self._on_npc_menu)
                if hasattr(controller, "on_mob_killed_callbacks"):
                    controller.on_mob_killed_callbacks.append(self.increment_kill_count)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Vòng đời
    # ------------------------------------------------------------------
    def _tag(self) -> str:
        try:
            return getattr(getattr(self.client, "myChar", None), "cName", "quest") or "quest"
        except Exception:
            return "quest"

    def _start_worker(self) -> None:
        if self._worker_started:
            return
        self._worker_started = True
        t = threading.Thread(target=self._run_loop, daemon=True, name="AutoQuestThread")
        t.start()

    def start(self):
        if self.is_running:
            print(f"[AutoQuest][{self._tag()}] Auto Quest đã chạy rồi.")
            return
        self.is_running = True
        self.start_time = time.time()
        self.quests_completed = 0
        self.total_kills = 0
        print(f"[AutoQuest][{self._tag()}] Bắt đầu Auto Quest Bò Mộng.")
        self._transition_to(AutoState.GET_QUEST)

    def stop(self):
        if not self.is_running:
            self.current_state = AutoState.IDLE
            return
        self.is_running = False
        print(f"[AutoQuest][{self._tag()}] Đã dừng Auto Quest.")
        try:
            cm = getattr(self.client, "combat_manager", None)
            if cm is not None:
                cm.toggle_tansat(False)
        except Exception:
            pass
        try:
            xc = getattr(self.client, "xmap_controller", None)
            if xc is not None and getattr(xc, "is_acting", False):
                xc.stop()
        except Exception:
            pass
        self.current_state = AutoState.IDLE

    def toggle(self) -> bool:
        if self.is_running:
            self.stop()
        else:
            self.start()
        return self.is_running

    def get_stats(self) -> dict:
        elapsed = int(time.time() - self.start_time) if self.start_time else 0
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        if hours > 0:
            time_str = f"{hours}h{minutes:02d}m{seconds:02d}s"
        elif minutes > 0:
            time_str = f"{minutes}m{seconds:02d}s"
        else:
            time_str = f"{seconds}s"
        return {
            "is_running": self.is_running,
            "state": self.current_state.value,
            "quests_completed": self.quests_completed,
            "total_kills": self.total_kills,
            "elapsed_time": elapsed,
            "time_str": time_str,
            "quests_remaining": self.quest_info.quests_remaining,
            "quests_total": self.quest_info.quests_total,
            "quest": str(self.quest_info),
        }

    def get_status(self) -> dict:
        return self.get_stats()

    # ------------------------------------------------------------------
    # Helpers truy cập ClientNRO
    # ------------------------------------------------------------------
    def _my_char(self):
        if self.client is not None and hasattr(self.client, "myChar"):
            return self.client.myChar
        try:
            from .char import Char
            return Char.myCharz()
        except Exception:
            return None

    def _service(self):
        if self.client is not None and hasattr(self.client, "service"):
            return self.client.service
        try:
            from .service import Service
            return Service.gI()
        except Exception:
            return None

    def _map_id(self) -> int:
        ch = self._my_char()
        try:
            return int(ch.mapInfo.mapID)
        except Exception:
            return -1

    def _is_dead(self) -> bool:
        return is_char_dead(self._my_char())

    def _is_dead_confirmed(self, retries: int = 2, delay: float = 0.5) -> bool:
        """Xác nhận chết nhiều lần liên tiếp để chống chết ảo.

        Lần đầu thấy chết -> đợi `delay` rồi đọc lại `retries` lần.
        Chỉ cần 1 lần đọc lại thấy sống là coi như tín hiệu ảo, không hồi sinh.
        """
        if not self._is_dead():
            return False
        for _ in range(retries):
            time.sleep(delay)
            if not self._is_dead():
                print(f"[AutoQuest][{self._tag()}] Tín hiệu chết ảo (đọc lại thấy còn sống). Bỏ qua hồi sinh.")
                return False
        return True

    def _transition_to(self, new_state: AutoState):
        self.current_state = new_state
        print(f"[AutoQuest][{self._tag()}] -> {new_state.value}")

    # ------------------------------------------------------------------
    # Tương tác NPC Bò Mộng
    # ------------------------------------------------------------------
    def _on_npc_menu(self, npc_template_id: int, chat_text: str, options: List[str]):
        try:
            if int(npc_template_id) == BO_MONG_NPC_TEMPLATE_ID:
                self.parse_quest_info(chat_text or "")
        except Exception:
            pass

    def _interact_with_npc_menu(self, npc_template_id: int, menu_options: Optional[List[int]] = None) -> bool:
        """Tele sát NPC (map 47 / NPC 17) rồi mở menu và chọn option (đồng bộ)."""
        try:
            ch = self._my_char()
            svc = self._service()
            if ch is None or svc is None:
                return False
            # 1. Bắt buộc tele lại gần NPC trước khi giao tiếp (server check ~60px)
            try:
                npc = ch.mapInfo.find_npc(npc_template_id) if hasattr(ch.mapInfo, "find_npc") else None
                if npc is not None:
                    dist = math.hypot(npc["x"] - ch.cx, npc["y"] - ch.cy)
                    if dist > NPC_INTERACT_DISTANCE:
                        cm = getattr(self.client, "combat_manager", None)
                        if cm is None:
                            return False
                        # Đứng lệch sang trái NPC 1 chút để không đè lên NPC
                        cm.teleport(int(npc["x"]) - 10, int(npc["y"]))
                        time.sleep(1.0)
                        ch = self._my_char()
                        dist2 = math.hypot(npc["x"] - ch.cx, npc["y"] - ch.cy)
                        if dist2 > NPC_INTERACT_DISTANCE:
                            print(f"[AutoQuest][{self._tag()}] Vẫn đứng xa NPC {npc_template_id} "
                                  f"({dist2:.0f}px > {NPC_INTERACT_DISTANCE}px). Không mở menu.")
                            return False
                else:
                    print(f"[AutoQuest][{self._tag()}] Chưa có tọa độ NPC {npc_template_id} "
                          f"(map {self._map_id()}). Vẫn thử mở menu...")
            except Exception as ex:
                print(f"[AutoQuest][{self._tag()}] Lỗi tele tới NPC {npc_template_id}: {ex}")
                return False
            # 2. Mở menu + chọn options
            svc.openMenu(npc_template_id)
            time.sleep(0.5)
            if menu_options:
                for opt_idx in menu_options:
                    svc.confirmMenu(npc_template_id, int(opt_idx))
                    time.sleep(0.5)
            return True
        except Exception as ex:
            print(f"[AutoQuest][{self._tag()}] Lỗi tương tác NPC {npc_template_id}: {ex}")
            return False

    def refresh_quest_info(self) -> bool:
        if self._map_id() != BO_MONG_MAP_ID:
            print(f"[AutoQuest][{self._tag()}] Đang di chuyển về Bò Mộng để refresh quest...")
            self.go_to_map(BO_MONG_MAP_ID)
            if self._map_id() != BO_MONG_MAP_ID:
                return False
        ok = self._interact_with_npc_menu(BO_MONG_NPC_TEMPLATE_ID, [1])
        if ok:
            print(f"[AutoQuest][{self._tag()}] Đã query NPC refresh quest info.")
        time.sleep(1.0)
        return ok

    # ------------------------------------------------------------------
    # Vòng lặp máy trạng thái
    # ------------------------------------------------------------------
    def _run_loop(self):
        while True:
            try:
                if self.is_running:
                    self.update()
            except Exception as ex:
                print(f"[AutoQuest][{self._tag()}] Lỗi trong vòng lặp: {ex}")
                try:
                    self.stop()
                except Exception:
                    pass
            time.sleep(0.2)

    def update(self):
        if self._is_dead_confirmed():
            print(f"[AutoQuest][{self._tag()}] Nhân vật đã chết (xác nhận). Hồi sinh về nhà...")
            try:
                cm = getattr(self.client, "combat_manager", None)
                if cm is not None:
                    cm.toggle_tansat(False)
            except Exception:
                pass
            try:
                self._service().returnTownFromDead()
            except Exception:
                pass
            time.sleep(1.0)
            for _ in range(10):
                if not self._is_dead():
                    break
                time.sleep(1.0)
            if self._is_dead():
                return
            print(f"[AutoQuest][{self._tag()}] Đã hồi sinh. Quay lại làm nhiệm vụ...")
            self._transition_to(AutoState.NAVIGATE_TO_MAP)
            return
        handler = {
            AutoState.IDLE: self._handle_idle,
            AutoState.GET_QUEST: self._handle_get_quest,
            AutoState.NAVIGATE_TO_MAP: self._handle_navigate_to_map,
            AutoState.SELECT_ZONE: self._handle_select_zone,
            AutoState.EXECUTE_QUEST: self._handle_execute_quest,
            AutoState.REPORT_QUEST: self._handle_report_quest,
        }.get(self.current_state)
        if handler:
            handler()

    def _handle_idle(self):
        time.sleep(0.2)

    def _handle_get_quest(self):
        with self._lock:
            self.quest_info = QuestInfo()
        if self._map_id() != BO_MONG_MAP_ID:
            self.go_to_map(BO_MONG_MAP_ID)
            return
        print(f"[AutoQuest][{self._tag()}] Nhận nhiệm vụ hàng ngày (Siêu khó)...")
        self._interact_with_npc_menu(BO_MONG_NPC_TEMPLATE_ID, [1, 4])
        time.sleep(2.0)
        if self.quest_info.is_valid:
            self._transition_to(AutoState.NAVIGATE_TO_MAP)
        else:
            print(f"[AutoQuest][{self._tag()}] Không nhận được thông tin NV mới. Thử lại sau 5s.")
            time.sleep(5.0)

    def _handle_navigate_to_map(self):
        if not self.quest_info.is_valid:
            self._transition_to(AutoState.GET_QUEST)
            return
        map_id, _ = self.get_quest_target_ids()
        if map_id == -1:
            print(f"[AutoQuest][{self._tag()}] Không tìm thấy map cho NV '{self.quest_info.mob_name}'. Dừng.")
            self.stop()
            return
        if not self._can_access_map(map_id):
            print(f"[AutoQuest][{self._tag()}] Không thể vào map {map_id}. Huỷ NV và nhận NV mới.")
            self._cancel_and_get_new_quest()
            return
        if self._map_id() != map_id:
            self.go_to_map(map_id)
        else:
            self._transition_to(AutoState.SELECT_ZONE)

    def _handle_select_zone(self):
        if self._map_id() == BO_MONG_MAP_ID:
            self._transition_to(AutoState.EXECUTE_QUEST)
            return
        print(f"[AutoQuest][{self._tag()}] Đang tìm khu vực tối ưu...")
        try:
            self._service().openUIZone()
        except Exception:
            pass
        time.sleep(1.5)
        ch = self._my_char()
        zones = list(getattr(ch.mapInfo, "zones", []) or []) if ch else []
        if not zones:
            print(f"[AutoQuest][{self._tag()}] Không lấy được danh sách khu. Bỏ qua chọn zone.")
            self._transition_to(AutoState.EXECUTE_QUEST)
            return
        current_zone = ch.mapInfo.zoneID
        best_zone = None
        for z in zones:
            zid = getattr(z, "zoneId", -1)
            num_p = getattr(z, "numPlayer", 0)
            max_p = getattr(z, "maxPlayer", 0)
            if zid != current_zone and (max_p <= 0 or num_p < max_p):
                best_zone = zid
                break
        if best_zone is not None:
            print(f"[AutoQuest][{self._tag()}] Chuyển sang khu vực {best_zone}...")
            try:
                self._service().requestChangeZone(int(best_zone))
            except Exception:
                pass
            time.sleep(2.0)
        else:
            print(f"[AutoQuest][{self._tag()}] Không tìm thấy zone phù hợp.")
        self._transition_to(AutoState.EXECUTE_QUEST)

    def _handle_execute_quest(self):
        if self.quest_info.is_valid and self.quest_info.current_progress >= self.quest_info.target_count:
            print(f"[AutoQuest][{self._tag()}] Đã đủ mục tiêu "
                  f"({self.quest_info.current_progress}/{self.quest_info.target_count}). Trả NV...")
            try:
                getattr(self.client, "combat_manager", None).toggle_tansat(False)
            except Exception:
                pass
            self._transition_to(AutoState.REPORT_QUEST)
            return
        _, mob_template_id = self.get_quest_target_ids()
        cm = getattr(self.client, "combat_manager", None)
        if mob_template_id != -1 and cm is not None:
            try:
                # Quest Bò Mộng lọc theo loại quái (template), không lọc theo mobId
                if int(mob_template_id) not in set(cm.target_mob_types or set()) or cm.target_mob_ids:
                    cm.target_mob_types.clear()
                    cm.target_mob_ids.clear()
                    cm.target_mob_types.add(int(mob_template_id))
                    print(f"[AutoQuest][{self._tag()}] Set target loại quái = {{{mob_template_id}}} ({self.quest_info.mob_name})")
            except Exception:
                pass
            if not cm.is_tansat:
                print(f"[AutoQuest][{self._tag()}] Farm: {self.quest_info.mob_name} "
                      f"({self.quest_info.current_progress}/{self.quest_info.target_count})")
                cm.toggle_tansat(True, mode="mob")

    def _handle_report_quest(self):
        try:
            getattr(self.client, "combat_manager", None).toggle_tansat(False)
        except Exception:
            pass
        if self._map_id() != BO_MONG_MAP_ID:
            self.go_to_map(BO_MONG_MAP_ID)
            return
        print(f"[AutoQuest][{self._tag()}] Trả NV (local: "
              f"{self.quest_info.current_progress}/{self.quest_info.target_count}).")
        old_mob = self.quest_info.mob_name
        # 1. Trả NV: [1] Nhiệm vụ hằng ngày -> [0] Trả nhiệm vụ
        self._interact_with_npc_menu(BO_MONG_NPC_TEMPLATE_ID, [1, 0])
        time.sleep(2.0)
        # 2. Server báo chưa đủ -> farm tiếp
        if self.quest_info.is_valid and self.quest_info.mob_name == old_mob:
            if self.quest_info.initial_count < self.quest_info.target_count:
                print(f"[AutoQuest][{self._tag()}] Server: chưa đủ "
                      f"({self.quest_info.initial_count}/{self.quest_info.target_count}). Farm tiếp!")
                self._transition_to(AutoState.NAVIGATE_TO_MAP)
                return
        # 3. Trả xong -> nhận NV mới [1] -> [4] Siêu khó
        print(f"[AutoQuest][{self._tag()}] Trả NV thành công! Nhận NV mới...")
        self.quests_completed += 1
        with self._lock:
            self.quest_info = QuestInfo()
        self._interact_with_npc_menu(BO_MONG_NPC_TEMPLATE_ID, [1, 4])
        time.sleep(2.0)
        if self.quest_info.is_valid:
            map_id, _ = self.get_quest_target_ids()
            if map_id != -1 and not self._can_access_map(map_id):
                print(f"[AutoQuest][{self._tag()}] NV mới cần map {map_id} không vào được. Huỷ...")
                self._cancel_and_get_new_quest()
                return
            print(f"[AutoQuest][{self._tag()}] NV mới: {self.quest_info.mob_name} (xong: {self.quests_completed})")
            self._transition_to(AutoState.NAVIGATE_TO_MAP)
        else:
            print(f"[AutoQuest][{self._tag()}] Không nhận được NV mới. Thử lại...")
            self._transition_to(AutoState.GET_QUEST)

    # ------------------------------------------------------------------
    # Parse + đếm kill
    # ------------------------------------------------------------------
    def parse_quest_info(self, menu_text: str):
        lower_text = (menu_text or "").lower()
        print(f"[AutoQuest][{self._tag()}] parse quest raw: {repr((menu_text or '')[:300])}...")
        if "hết nhiệm vụ cho hôm nay" in lower_text:
            print(f"[AutoQuest][{self._tag()}] Hết NV hôm nay. Dừng.")
            self.stop()
            return
        match_remaining = re.search(r"số nhiệm vụ còn lại của hôm nay\s+(\d+)/(\d+)", lower_text)
        if match_remaining:
            remaining = int(match_remaining.group(1))
            total = int(match_remaining.group(2))
            print(f"[AutoQuest][{self._tag()}] NV còn lại: {remaining}/{total}")
            self.quest_info.quests_remaining = remaining
            self.quest_info.quests_total = total
            if remaining <= 0:
                print(f"[AutoQuest][{self._tag()}] Hết NV trong ngày. Dừng.")
                self.stop()
                return
        if "nhiệm vụ của bạn" not in lower_text:
            return
        quest = QuestInfo()
        quest.quests_remaining = self.quest_info.quests_remaining
        quest.quests_total = self.quest_info.quests_total
        match_task = re.search(r"nhiệm vụ của bạn\s+tiêu diệt\s+\d+\s+([^\n]+)", lower_text)
        if match_task:
            quest.is_valid = True
            quest.mob_name = match_task.group(1).strip()
            print(f"[AutoQuest][{self._tag()}] mob_name: '{quest.mob_name}'")
        else:
            print(f"[AutoQuest][{self._tag()}] Không parse được mô tả NV.")
            return
        match_location = re.search(r"địa điểm nhiệm vụ\s+([^\n]+)", lower_text)
        if match_location:
            quest.map_name = match_location.group(1).strip()
        match_progress = re.search(r"tiến độ nhiệm vụ\s+(\d+)/(\d+)", lower_text)
        if match_progress:
            quest.initial_count = int(match_progress.group(1))
            quest.target_count = int(match_progress.group(2))
        quest.kill_count = 0
        with self._lock:
            # Giữ số NV còn lại mới nhất nếu menu này không có
            if quest.quests_total == 0:
                quest.quests_remaining = self.quest_info.quests_remaining
                quest.quests_total = self.quest_info.quests_total
            self.quest_info = quest
        print(f"[AutoQuest][{self._tag()}] NV cập nhật: {self.quest_info}")

    def increment_kill_count(self, mob_template_id: int):
        _, quest_mob_id = self.get_quest_target_ids()
        if not self.is_running:
            return
        if not self.quest_info.is_valid:
            return
        if self.current_state != AutoState.EXECUTE_QUEST:
            return
        if int(mob_template_id) != int(quest_mob_id):
            return
        with self._lock:
            self.quest_info.kill_count += 1
            self.total_kills += 1
            prog = self.quest_info.current_progress
            target = self.quest_info.target_count
        print(f"[AutoQuest][{self._tag()}] Diệt {self.quest_info.mob_name} ({prog}/{target})")
        if prog >= target:
            print(f"[AutoQuest][{self._tag()}] Đủ mục tiêu! Dừng farm...")
            try:
                getattr(self.client, "combat_manager", None).toggle_tansat(False)
            except Exception:
                pass

    def get_quest_target_ids(self) -> Tuple[int, int]:
        """Trả về (map_id, mob_template_id) cho NV hiện tại."""
        if not self.quest_info or not self.quest_info.mob_name:
            return -1, -1
        target = self.quest_info.mob_name.lower().strip()
        for name, ids in MOB_LOCATION_DATA.items():
            if name.lower() == target:
                return ids
        for name, ids in MOB_LOCATION_DATA.items():
            if target in name.lower():
                print(f"[AutoQuest][{self._tag()}] Khớp một phần '{name}' với '{target}'")
                return ids
        print(f"[AutoQuest][{self._tag()}] Không có dữ liệu cho quái: '{self.quest_info.mob_name}'")
        return -1, -1

    def _can_access_map(self, map_id: int) -> bool:
        try:
            xc = getattr(self.client, "xmap_controller", None)
            ch = self._my_char()
            if xc is None or ch is None:
                return True
            way = xc.find_path(int(ch.mapInfo.mapID), int(map_id), use_capsule=False)
            return way is not None
        except Exception:
            return True

    def _cancel_and_get_new_quest(self):
        print(f"[AutoQuest][{self._tag()}] Huỷ NV không thể hoàn thành...")
        if self._map_id() != BO_MONG_MAP_ID:
            self.go_to_map(BO_MONG_MAP_ID)
            if self._map_id() != BO_MONG_MAP_ID:
                return
        # Huỷ NV: [1] -> [1]
        self._interact_with_npc_menu(BO_MONG_NPC_TEMPLATE_ID, [1, 1])
        time.sleep(0.5)
        with self._lock:
            keep_remain = self.quest_info.quests_remaining
            keep_total = self.quest_info.quests_total
            self.quest_info = QuestInfo()
            self.quest_info.quests_remaining = keep_remain
            self.quest_info.quests_total = keep_total
        # Nhận NV mới: [1] -> [4]
        self._interact_with_npc_menu(BO_MONG_NPC_TEMPLATE_ID, [1, 4])
        time.sleep(2.0)
        if self.quest_info.is_valid:
            map_id, _ = self.get_quest_target_ids()
            if map_id != -1 and not self._can_access_map(map_id):
                print(f"[AutoQuest][{self._tag()}] NV mới vẫn không vào được map {map_id}. Huỷ tiếp...")
                self._cancel_and_get_new_quest()
                return
            print(f"[AutoQuest][{self._tag()}] NV mới: {self.quest_info.mob_name}")
            self._transition_to(AutoState.NAVIGATE_TO_MAP)
        else:
            self._transition_to(AutoState.GET_QUEST)

    def go_to_map(self, map_id: int):
        if self._map_id() == map_id:
            return
        print(f"[AutoQuest][{self._tag()}] Xmap đến map {map_id}...")
        xc = getattr(self.client, "xmap_controller", None)
        if xc is None:
            return
        try:
            xc.start(int(map_id))
        except Exception as ex:
            print(f"[AutoQuest][{self._tag()}] Xmap lỗi: {ex}")
            return
        start = time.time()
        while getattr(xc, "is_acting", False):
            if not self.is_running:
                try:
                    xc.stop()
                except Exception:
                    pass
                return
            if time.time() - start > 120:
                print(f"[AutoQuest][{self._tag()}] Xmap timeout map {map_id}.")
                try:
                    xc.stop()
                except Exception:
                    pass
                break
            time.sleep(0.5)
        if self._map_id() != map_id:
            print(f"[AutoQuest][{self._tag()}] Chưa tới map {map_id} (đang ở {self._map_id()}). Vòng sau thử lại.")
        else:
            print(f"[AutoQuest][{self._tag()}] Đã tới map {map_id}.")
