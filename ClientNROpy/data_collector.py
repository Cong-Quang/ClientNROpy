# -*- coding: utf-8 -*-
"""
data_collector.py - Module Thu Thập Dữ Liệu Tự Động Cho Game AI (Transformer DeBERTa)
====================================================================================
Nhiệm vụ:
1. Trích xuất trạng thái thời gian thực từ game client (Char, MapInfo, Mob, AutoManager)
   thành chuỗi key-value súc tích dưới 128 tokens qua hàm build_state_text().
2. Ánh xạ các hành động của người chơi / bot thành các nhãn số nguyên (Action ID: 0..4).
3. Cung cấp 2 chế độ ghi:
   - Bắt chước người chơi (Imitation Learning): Chụp snapshot khi người dùng gõ lệnh CLI.
   - Bot tự ghi (Auto Routine Tagging): Chụp snapshot khi logic auto ra quyết định.
4. Cơ chế chống spam (Throttling) và chống frame tĩnh trùng lặp (Deduplication).
5. Luồng ghi đĩa ngầm (AsyncDataWriter) hoàn toàn không chặn luồng socket / CLI của game.
6. Tự động chia 80% Train / 20% Val và lưu ra c:\\data\\MoHinhQuyetDInh\\train_data.json & val_data.json.
"""

import json
import math
import os
import queue
import random
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union


# ==============================================================================
# 1. BẢNG ÁNH XẠ HÀNH ĐỘNG THÀNH NHÃN (ACTION MAPPING)
# ==============================================================================

# Bảng nhãn chuẩn hóa cho mô hình DeBERTa (0 đến num_labels - 1)
ACTION_ATTACK = 0      # Tấn công / Tàn sát quái
ACTION_QUEST = 1       # Làm nhiệm vụ (chính tuyến / bò mộng)
ACTION_HEAL = 2        # Bơm máu / Ăn đậu / Hồi phục
ACTION_RETREAT = 3     # Rút lui / Đổi khu / Né nguy hiểm
ACTION_SKILL = 4       # Tung kỹ năng đặc biệt / Combo skill

NUM_LABELS = 5

ACTION_NAMES: Dict[int, str] = {
    ACTION_ATTACK: "ATTACK",
    ACTION_QUEST: "QUEST",
    ACTION_HEAL: "HEAL",
    ACTION_RETREAT: "RETREAT",
    ACTION_SKILL: "SKILL",
}

ACTION_DESCRIPTIONS: Dict[int, str] = {
    ACTION_ATTACK: "Tấn công / Tàn sát quái vật",
    ACTION_QUEST: "Thực hiện nhiệm vụ",
    ACTION_HEAL: "Bơm máu / Ăn đậu thần hồi phục",
    ACTION_RETREAT: "Rút lui / Đổi khu vực an toàn",
    ACTION_SKILL: "Tung kỹ năng đặc biệt",
}

# Ánh xạ tên lệnh gõ trong CLI sang Action ID
COMMAND_TO_ACTION: Dict[str, int] = {
    # Nhãn 0: Tấn công / Tàn sát
    "ts": ACTION_ATTACK,
    "tansat": ACTION_ATTACK,
    "ak": ACTION_ATTACK,
    "attack": ACTION_ATTACK,
    "danh": ACTION_ATTACK,
    " danhquai": ACTION_ATTACK,

    # Nhãn 1: Làm nhiệm vụ
    "nv": ACTION_QUEST,
    "autonv": ACTION_QUEST,
    "maintask": ACTION_QUEST,
    "nvchinh": ACTION_QUEST,
    "task": ACTION_QUEST,
    "quest": ACTION_QUEST,
    "nhiemvu": ACTION_QUEST,
    "nvbm": ACTION_QUEST,
    "bomong": ACTION_QUEST,

    # Nhãn 2: Bơm máu / Ăn đậu
    "bomhp": ACTION_HEAL,
    "bomki": ACTION_HEAL,
    "useitem": ACTION_HEAL,
    "abf": ACTION_HEAL,
    "dau": ACTION_HEAL,
    "caydau": ACTION_HEAL,
    "harvest": ACTION_HEAL,
    "nhatdau": ACTION_HEAL,
    "eat_pean": ACTION_HEAL,
    "heal": ACTION_HEAL,

    # Nhãn 3: Rút lui / Đổi khu
    "doikhu": ACTION_RETREAT,
    "zone": ACTION_RETREAT,
    "zon": ACTION_RETREAT,
    "zn": ACTION_RETREAT,
    "khu": ACTION_RETREAT,
    "retreat": ACTION_RETREAT,
    "escape": ACTION_RETREAT,

    # Nhãn 4: Kỹ năng đặc biệt
    "skill": ACTION_SKILL,
    "skills": ACTION_SKILL,
    "combo": ACTION_SKILL,
    "chieu": ACTION_SKILL,
}


# ==============================================================================
# 2. HÀM TRÍCH XUẤT TRẠNG THÁI (STATE EXTRACTION)
# ==============================================================================

def build_state_text(client: Any, target: Optional[Any] = None) -> str:
    """
    Trích xuất trạng thái thời gian thực của game client và chuẩn hóa thành
    chuỗi key-value ngắn gọn, nhất quán dưới 128 tokens để mô hình DeBERTa xử lý.

    Ví dụ output:
    "hp:8500, max_hp:10000, mp:600, max_mp:1000, status:alive, mobs_count:3, "
    "target_hp:2000, target_dist:45, skill_1_cd:0.0, skill_2_cd:1.2, map_id:1, zone_id:5, quest_id:2"
    """
    my_char = getattr(client, "myChar", None)
    if not my_char:
        return "hp:0, max_hp:0, mp:0, max_mp:0, status:dead, mobs_count:0, target_hp:0, target_dist:999, skill_1_cd:0.0, skill_2_cd:0.0, map_id:-1, zone_id:-1, quest_id:-1"

    # 1. Chỉ số nhân vật
    hp = int(getattr(my_char, "cHP", 0))
    max_hp = max(1, int(getattr(my_char, "cHPFull", 1)))
    mp = int(getattr(my_char, "cMP", 0))
    max_mp = max(1, int(getattr(my_char, "cMPFull", 1)))

    # Xác định trạng thái sống/chết/choáng
    is_dead = getattr(my_char, "is_dead", False) or hp <= 0 or getattr(my_char, "statusMe", 1) == 14
    is_stunned = getattr(my_char, "statusMe", 1) == 5 or getattr(my_char, "is_stun", False)

    if is_dead:
        status_str = "dead"
    elif is_stunned:
        status_str = "stunned"
    else:
        status_str = "alive"

    # 2. Thông tin Bản đồ & Môi trường
    map_info = getattr(my_char, "mapInfo", None)
    map_id = getattr(map_info, "mapID", -1) if map_info else -1
    zone_id = getattr(map_info, "zoneID", -1) if map_info else -1

    # Nhiệm vụ hiện tại
    quest_id = getattr(my_char, "ctaskId", -1)
    if quest_id == -1 and getattr(my_char, "task", None):
        quest_id = getattr(my_char.task, "taskId", -1)

    # 3. Phân tích Nhiệm vụ chi tiết (quest_type & quest_progress)
    auto_mgr = getattr(client, "auto", None)
    quest_type = "none"
    quest_progress = "0/0"

    # Kiểm tra nhiệm vụ Bò Mộng từ AutoManager
    q_bm = getattr(auto_mgr, "quest_info", None) if auto_mgr else None
    if q_bm and getattr(q_bm, "is_valid", False):
        cur_p = getattr(q_bm, "current_progress", 0)
        tar_c = getattr(q_bm, "target_count", 0)
        quest_progress = f"{cur_p}/{tar_c}"
        if tar_c > 0 and cur_p >= tar_c:
            quest_type = "report"
        else:
            quest_type = "farm"

    # Kiểm tra nhiệm vụ chính tuyến nếu chưa có quest Bò Mộng
    if quest_type == "none" and getattr(my_char, "task", None):
        task = my_char.task
        cur_c = max(0, getattr(task, "count", 0)) if getattr(task, "count", 0) != -1 else 0
        t_idx = getattr(task, "index", 0)
        counts = getattr(task, "counts", [])
        max_c = counts[t_idx] if (0 <= t_idx < len(counts)) else 0
        quest_progress = f"{cur_c}/{max_c}" if max_c > 0 else "0/0"

        if max_c > 0 and cur_c >= max_c:
            quest_type = "report"
        else:
            t_text = f"{getattr(task, 'name', '')} {getattr(task, 'detail', '')} {getattr(task, 'clean_name', '')} {getattr(task, 'current_sub_name', '')}".lower()
            if any(k in t_text for k in ["boss", "kuku", "rambo", "mập đầu đinh", "chill", "fide", "tiểu đội", "xên", "cui", "số 1", "số 2", "số 3", "số 4"]):
                quest_type = "boss"
            elif any(k in t_text for k in ["sức mạnh", "tiềm năng", "power"]):
                quest_type = "power"
            else:
                quest_type = "farm"

    # 4. Quái vật & Boss xung quanh
    mobs_dict = getattr(map_info, "mobs", {}) if map_info else {}
    alive_mobs = []
    has_boss_mob = False
    if isinstance(mobs_dict, dict):
        for m in mobs_dict.values():
            if getattr(m, "hp", 0) > 0 and getattr(m, "status", 0) not in (0, 1):
                alive_mobs.append(m)
                if getattr(m, "isBoss", False):
                    has_boss_mob = True
    elif isinstance(mobs_dict, list):
        for m in mobs_dict:
            if getattr(m, "hp", 0) > 0 and getattr(m, "status", 0) not in (0, 1):
                alive_mobs.append(m)
                if getattr(m, "isBoss", False):
                    has_boss_mob = True
    mobs_count = len(alive_mobs)

    # 5. Người chơi, Boss dạng Char & Đồng đội (team_count, players_count)
    chars_dict = getattr(map_info, "chars", {}) if map_info else {}
    chars_list = list(chars_dict.values()) if isinstance(chars_dict, dict) else (chars_dict if isinstance(chars_dict, list) else [])
    has_boss_char = False
    other_players = []

    for c in chars_list:
        if getattr(c, "charID", 0) == getattr(my_char, "charID", -1):
            continue
        if getattr(c, "isBoss", False) and getattr(c, "cHP", 0) > 0 and getattr(c, "statusMe", 1) != 14:
            has_boss_char = True
        elif not getattr(c, "isPet", False) and not getattr(c, "isMiniPet", False):
            other_players.append(c)

    boss_in_map = 1 if (has_boss_mob or has_boss_char) else 0
    players_count = len(other_players)

    # Tính toán số đồng đội (team_count)
    team_count = 1
    # Đếm các tài khoản cùng hệ thống đang ở cùng khu vực
    acc_mgr = getattr(client, "account_manager", None)
    if acc_mgr and hasattr(acc_mgr, "accounts"):
        for a in acc_mgr.accounts:
            if a.client and a.client != client and getattr(a.client, "isConnected", lambda: False)():
                c_map = getattr(a.client.myChar.mapInfo, "mapID", -2)
                c_zone = getattr(a.client.myChar.mapInfo, "zoneID", -2)
                if c_map == map_id and c_zone == zone_id:
                    team_count += 1
    # Hoặc người chơi có cùng cờ (cFlag)
    my_flag = getattr(my_char, "cFlag", 0)
    if my_flag > 0:
        same_flag_c = sum(1 for c in other_players if getattr(c, "cFlag", 0) == my_flag)
        team_count = max(team_count, 1 + same_flag_c)

    # 6. Mục tiêu cụ thể (target_type: mob | boss | char | npc | item | none)
    target_type = "none"
    target_hp = 0
    target_dist = 999

    cx = getattr(my_char, "cx", 0)
    cy = getattr(my_char, "cy", 0)

    # Ưu tiên 1: Target được truyền trực tiếp vào hàm
    if target is not None:
        t_cls = type(target).__name__.lower()
        if "mob" in t_cls:
            target_type = "boss" if getattr(target, "isBoss", False) else "mob"
            target_hp = int(getattr(target, "hp", 0))
            tx = getattr(target, "x", cx)
            ty = getattr(target, "y", cy)
        elif "char" in t_cls:
            target_type = "boss" if getattr(target, "isBoss", False) else "char"
            target_hp = int(getattr(target, "cHP", 0))
            tx = getattr(target, "cx", cx)
            ty = getattr(target, "cy", cy)
        elif "item" in t_cls:
            target_type = "item"
            tx = getattr(target, "x", cx)
            ty = getattr(target, "y", cy)
        elif isinstance(target, dict):
            target_type = "npc"
            tx = target.get("x", cx)
            ty = target.get("y", cy)
        else:
            target_type = "char"
            tx = getattr(target, "x", cx)
            ty = getattr(target, "y", cy)
        target_dist = int(math.hypot(cx - tx, cy - ty))

    # Ưu tiên 2: Mục tiêu mobFocus / charFocus / npcFocus / itemFocus trong Char
    elif getattr(my_char, "mobFocus", None):
        f_mob = my_char.mobFocus
        target_type = "boss" if getattr(f_mob, "isBoss", False) else "mob"
        target_hp = int(getattr(f_mob, "hp", 0))
        target_dist = int(math.hypot(cx - getattr(f_mob, "x", cx), cy - getattr(f_mob, "y", cy)))

    elif getattr(my_char, "charFocus", None):
        f_char = my_char.charFocus
        target_type = "boss" if getattr(f_char, "isBoss", False) else "char"
        target_hp = int(getattr(f_char, "cHP", 0))
        target_dist = int(math.hypot(cx - getattr(f_char, "cx", cx), cy - getattr(f_char, "cy", cy)))

    elif getattr(my_char, "npcFocus", None):
        f_npc = my_char.npcFocus
        target_type = "npc"
        target_hp = 0
        target_dist = int(math.hypot(cx - getattr(f_npc, "x", cx), cy - getattr(f_npc, "y", cy)))

    elif getattr(my_char, "itemFocus", None):
        f_item = my_char.itemFocus
        target_type = "item"
        target_hp = 0
        target_dist = int(math.hypot(cx - getattr(f_item, "x", cx), cy - getattr(f_item, "y", cy)))

    # Ưu tiên 3: Quái vật gần nhất trong danh sách sống
    elif alive_mobs:
        closest_mob = min(alive_mobs, key=lambda m: math.hypot(cx - getattr(m, "x", cx), cy - getattr(m, "y", cy)))
        target_type = "boss" if getattr(closest_mob, "isBoss", False) else "mob"
        target_hp = int(getattr(closest_mob, "hp", 0))
        target_dist = int(math.hypot(cx - getattr(closest_mob, "x", cx), cy - getattr(closest_mob, "y", cy)))

    # 7. Kỹ năng & Cooldown (làm tròn số nguyên giây để tối ưu token DeBERTa & chống jitter)
    skill_1_cd = 0
    skill_2_cd = 0

    if auto_mgr and hasattr(auto_mgr, "_skill_last_use"):
        now = time.time()
        gender = getattr(my_char, "cgender", 0)
        try:
            gender = int(gender)
        except Exception:
            gender = 0

        skill_pairs = {
            0: (1, 9),    # Trái Đất
            1: (3, 12),   # Namek
            2: (5, 13),   # Xayda
        }
        s1_id, s2_id = skill_pairs.get(gender, (1, 9))

        cd1 = auto_mgr._get_skill_cooldown(s1_id) if hasattr(auto_mgr, "_get_skill_cooldown") else 1.2
        last1 = auto_mgr._skill_last_use.get(s1_id, 0.0)
        rem1 = max(0.0, cd1 - (now - last1))
        skill_1_cd = int(math.ceil(rem1)) if rem1 > 0.05 else 0

        cd2 = auto_mgr._get_skill_cooldown(s2_id) if hasattr(auto_mgr, "_get_skill_cooldown") else 4.0
        last2 = auto_mgr._skill_last_use.get(s2_id, 0.0)
        rem2 = max(0.0, cd2 - (now - last2))
        skill_2_cd = int(math.ceil(rem2)) if rem2 > 0.05 else 0

    # Định dạng chuỗi key-value ngắn gọn chuẩn hóa (< 128 tokens)
    state_str = (
        f"hp:{hp}, max_hp:{max_hp}, mp:{mp}, max_mp:{max_mp}, status:{status_str}, "
        f"map_id:{map_id}, zone_id:{zone_id}, quest_id:{quest_id}, "
        f"quest_type:{quest_type}, quest_progress:{quest_progress}, "
        f"target_type:{target_type}, target_hp:{target_hp}, target_dist:{target_dist}, "
        f"boss_in_map:{boss_in_map}, mobs_count:{mobs_count}, players_count:{players_count}, team_count:{team_count}, "
        f"skill_1_cd:{skill_1_cd}, skill_2_cd:{skill_2_cd}"
    )

    return state_str


# ==============================================================================
# 3. LUỒNG GHI ĐĨA BẤT ĐỒNG BỘ (ASYNC DATA WRITER)
# ==============================================================================

class AsyncDataWriter(threading.Thread):
    """
    Luồng nền ghi file bất đồng bộ.
    Giúp việc lưu trữ tập dữ liệu (JSON) hoàn toàn không chặn (non-blocking)
    luồng xử lý mạng hay vòng lặp game CLI.
    """

    def __init__(self):
        super().__init__(name="DataCollector-AsyncWriter", daemon=True)
        self.queue: queue.Queue = queue.Queue()
        self._running: bool = True
        self.start()

    def submit_task(self, task_func: Any, *args: Any, **kwargs: Any) -> None:
        """Đẩy công việc ghi file vào hàng đợi."""
        self.queue.put((task_func, args, kwargs))

    def run(self) -> None:
        while self._running:
            try:
                item = self.queue.get(timeout=0.5)
                if item is None:
                    break
                task_func, args, kwargs = item
                try:
                    task_func(*args, **kwargs)
                except Exception as ex:
                    print(f"\n[DataCollector] Lỗi khi ghi file bất đồng bộ: {ex}")
                finally:
                    self.queue.task_done()
            except queue.Empty:
                continue

    def stop(self) -> None:
        """Dừng luồng ghi ngầm."""
        self._running = False
        self.queue.put(None)


# ==============================================================================
# 4. LỚP ĐIỀU PHỐI CHÍNH (DataCollector)
# ==============================================================================

class DataCollector:
    """
    Hệ thống thu thập dữ liệu quyết định thời gian thực cho game NRO.
    Tạo ra tập dữ liệu train_data.json và val_data.json phục vụ huấn luyện Transformer.
    """

    _default_instance: Optional["DataCollector"] = None

    def __init__(
        self,
        client: Optional[Any] = None,
        output_dir: str = r"c:\data\MoHinhQuyetDInh",
        min_interval: float = 0.33,  # Giới hạn tối đa ~3 mẫu/giây (Throttling)
    ):
        self.client: Optional[Any] = client
        self.output_dir: str = output_dir
        self.min_interval: float = min_interval

        self.is_recording: bool = False
        self.samples: List[Dict[str, Any]] = []

        # Cơ chế chống spam / Chống trùng lặp (Throttling & Deduplication)
        self.last_record_time: float = 0.0
        self.last_state_text: str = ""
        self.last_label: int = -1

        # Đếm số lượng mẫu theo từng nhãn
        self.label_counts: Dict[int, int] = {i: 0 for i in range(NUM_LABELS)}

        # Khóa an toàn đồng bộ luồng
        self.lock = threading.Lock()

        # Luồng ghi file ngầm
        self.writer = AsyncDataWriter()

    # --------------------------------------------------------------------------
    # Bật / Tắt / Trạng thái thu thập
    # --------------------------------------------------------------------------
    def start_recording(self) -> bool:
        """Bật chế độ ghi nhận dữ liệu."""
        with self.lock:
            self.is_recording = True
        return True

    def stop_recording(self) -> bool:
        """Tạm dừng chế độ ghi nhận dữ liệu."""
        with self.lock:
            self.is_recording = False
        return True

    def toggle_recording(self) -> bool:
        """Chuyển đổi trạng thái bật/tắt ghi dữ liệu."""
        with self.lock:
            self.is_recording = not self.is_recording
            return self.is_recording

    def clear(self) -> None:
        """Xóa toàn bộ các mẫu đang lưu trong bộ nhớ tạm."""
        with self.lock:
            self.samples.clear()
            self.last_state_text = ""
            self.last_label = -1
            self.label_counts = {i: 0 for i in range(NUM_LABELS)}

    def get_stats(self) -> Dict[str, Any]:
        """Lấy thống kê số lượng mẫu đã thu thập."""
        with self.lock:
            total = len(self.samples)
            counts = dict(self.label_counts)
            recording = self.is_recording
        return {
            "is_recording": recording,
            "total_samples": total,
            "label_counts": counts,
            "output_dir": self.output_dir,
        }

    # --------------------------------------------------------------------------
    # Ghi nhận mẫu (Record Sample) với Throttling & Deduplication
    # --------------------------------------------------------------------------
    def record_sample(
        self,
        client: Optional[Any] = None,
        action: Union[int, str] = 0,
        target: Optional[Any] = None,
        force: bool = False,
    ) -> bool:
        """
        Ghi nhận một mẫu (state, action).
        Áp dụng kiểm tra:
        1. Đang bật ghi hay không.
        2. Throttling: khoảng cách giữa 2 lần ghi >= min_interval (trừ khi force=True).
        3. Deduplication: bỏ qua nếu state và action giống hệt mẫu trước đó.
        """
        if not self.is_recording and not force:
            return False

        # Xác định Action ID số nguyên
        if isinstance(action, str):
            clean_act = action.strip().lower()
            if clean_act.startswith("/"):
                clean_act = clean_act[1:].strip()
            # Tách từ đầu tiên nếu là câu lệnh đầy đủ (vd: "ts on" -> "ts")
            act_word = clean_act.split()[0] if clean_act else ""
            if act_word in COMMAND_TO_ACTION:
                label = COMMAND_TO_ACTION[act_word]
            elif act_word.isdigit():
                label = int(act_word)
            else:
                return False
        else:
            label = int(action)

        if label < 0 or label >= NUM_LABELS:
            return False

        target_client = client or self.client
        if not target_client:
            return False

        now = time.time()

        with self.lock:
            # 1. Throttling: giới hạn tần suất ghi
            if not force and (now - self.last_record_time) < self.min_interval:
                return False

            # 2. State Extraction
            state_text = build_state_text(target_client, target=target)

            # 3. Deduplication: chống trùng lặp frame tĩnh
            if not force and state_text == self.last_state_text and label == self.last_label:
                return False

            # Ghi nhận mẫu hợp lệ
            sample = {
                "text": state_text,
                "label": label,
            }
            self.samples.append(sample)

            # Cập nhật trạng thái kiểm tra
            self.last_record_time = now
            self.last_state_text = state_text
            self.last_label = label
            self.label_counts[label] = self.label_counts.get(label, 0) + 1

        return True

    # --------------------------------------------------------------------------
    # Lưu trữ tập dữ liệu (Save Dataset) & Chia Train / Validation (80/20)
    # --------------------------------------------------------------------------
    def save_dataset(
        self,
        train_ratio: float = 0.8,
        output_dir: Optional[str] = None,
        async_save: bool = True,
    ) -> Tuple[int, int]:
        """
        Chia dữ liệu thành 80% Train và 20% Validation, sau đó lưu ra file JSON.
        - train_data.json
        - val_data.json
        Trả về (số mẫu train, số mẫu validation).
        """
        out_dir = output_dir or self.output_dir

        with self.lock:
            if not self.samples:
                print(f"[DataCollector] Chưa có mẫu dữ liệu nào để lưu.")
                return 0, 0

            # Tạo bản sao và xáo trộn ngẫu nhiên
            all_samples = list(self.samples)

        random.shuffle(all_samples)

        # Tính toán điểm cắt chia 80% Train / 20% Val
        total_count = len(all_samples)
        train_count = int(total_count * train_ratio)
        val_count = total_count - train_count

        train_data = all_samples[:train_count]
        val_data = all_samples[train_count:]

        train_path = os.path.join(out_dir, "train_data.json")
        val_path = os.path.join(out_dir, "val_data.json")

        def _do_save():
            try:
                os.makedirs(out_dir, exist_ok=True)

                with open(train_path, "w", encoding="utf-8") as f:
                    json.dump(train_data, f, ensure_ascii=False, indent=2)

                with open(val_path, "w", encoding="utf-8") as f:
                    json.dump(val_data, f, ensure_ascii=False, indent=2)

                print(
                    f"\n[DataCollector] ĐÃ LƯU DỮ LIỆU THÀNH CÔNG!\n"
                    f"  - Thư mục lưu trữ: {out_dir}\n"
                    f"  - Tập Train ({int(train_ratio * 100)}%): {len(train_data)} mẫu -> '{train_path}'\n"
                    f"  - Tập Val ({int((1 - train_ratio) * 100)}%):   {len(val_data)} mẫu -> '{val_path}'\n"
                )
            except Exception as ex:
                print(f"\n[DataCollector] Lỗi khi ghi tập dữ liệu ra đĩa: {ex}")

        if async_save:
            self.writer.submit_task(_do_save)
        else:
            _do_save()

        return len(train_data), len(val_data)


# ==============================================================================
# 5. SINGLETON & HELPER TIỆN ÍCH
# ==============================================================================

_GLOBAL_COLLECTOR: Optional[DataCollector] = None


def get_data_collector(client: Optional[Any] = None) -> DataCollector:
    """Lấy hoặc khởi tạo instance DataCollector toàn cục."""
    global _GLOBAL_COLLECTOR
    if _GLOBAL_COLLECTOR is None:
        _GLOBAL_COLLECTOR = DataCollector(client=client)
    elif client is not None and _GLOBAL_COLLECTOR.client is None:
        _GLOBAL_COLLECTOR.client = client
    return _GLOBAL_COLLECTOR
