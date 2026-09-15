# -*- coding: utf-8 -*-
"""
Bộ quản lý Boss - Mô phỏng theo Mod/Boss.cs trong Dragonboy C#.
Quản lý danh sách Boss, bóc tách thông báo ChatVip (cmd 93),
tự động cập nhật trạng thái sống/chết và điều khiển Xmap đến Boss.
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import re
import time
from typing import Optional, List, Tuple, Union, Callable, Dict, Any

from .boss import Boss
from .xmap.map_data import MAP_NAMES, resolve_map_id, normalize_str


class BossManager:
    """
    Quản lý danh sách Boss xuất hiện và bị tiêu diệt trong game.
    Tích hợp với Xmap để tự động di chuyển đến map và đổi khu vực của Boss.
    """

    MAX_BOSS: int = 100

    STR_BOSS_APPEARED: List[str] = [
        "BOSS ",
        " vừa xuất hiện tại ",
        " appear at ",
        " muncul di ",
        " khu vực ",
        " zone ",
        " zona ",
    ]

    STR_BOSS_KILLED: List[str] = [
        " mọi người đều ngưỡng mộ.",
        " everyone admired.",
        " semua orang mengagumi.",
        " đã đánh bại và nhận được cải trang thành ",
        " killed and receive disguise of ",
        " membunuh Dan menerima disguise ",
        ": Đã tiêu diệt được ",
        ": defeated ",
        ": mengalahkan ",
    ]

    def __init__(self, client=None):
        self.client = client
        self.list_bosses: List[Boss] = []
        self.is_enabled: bool = True
        self.pending_zone_id: int = -1
        self.pending_boss_name: str = ""

        # Callbacks sự kiện
        self.on_boss_appeared_callbacks: List[Callable[[Boss], None]] = []
        self.on_boss_killed_callbacks: List[Callable[[Boss], None]] = []
        self.on_boss_updated_callbacks: List[Callable[[Boss], None]] = []

        # Đăng ký hook nếu có client
        if self.client:
            self._setup_client_hooks()

    def _setup_client_hooks(self) -> None:
        """Đăng ký lắng nghe sự kiện từ client và controller."""
        if hasattr(self.client, "controller"):
            self.client.controller.on_chat_vip_callbacks.append(self.handle_chat_vip_obj)
            self.client.controller.on_map_info_callbacks.append(self.on_map_changed)

        if hasattr(self.client, "xmap_controller"):
            self.client.xmap_controller.on_finish_callbacks.append(self._on_xmap_finished)

    @classmethod
    def resolve_boss_map_id(cls, boss_name: str, map_name: str) -> int:
        """
        Quy tắc xác định mapId đặc biệt mô phỏng chính xác Boss.GetMapId trong Mod/Boss.cs.
        - 'Vách núi Aru' -> 42 (Vách núi đen)
        - 'Vách núi Moori' -> 43 (Vách núi Namếc)
        - 'Trạm tàu vũ trụ':
            - Tiểu đội sát thủ ('Số ', 'Tiểu đội') -> 25 (Namếc)
            - Bojack team ('Bojack', 'Bujin', 'Bido', 'Zangya') -> 24 (Trái Đất)
        - Các map khác: tra cứu trong bảng MAP_NAMES hoặc resolve_map_id.
        """
        raw_map = map_name.strip()
        norm_map = normalize_str(raw_map)
        b_name = boss_name.strip()

        # 1. Vách núi Aru -> 42
        if norm_map == "vach nui aru":
            return 42

        # 2. Vách núi Moori -> 43
        if norm_map in ("vach nui moori", "vach nui mori"):
            return 43

        # 3. Trạm tàu vũ trụ
        if norm_map in ("tram tau vu tru", "tram tau"):
            # Tiểu đội sát thủ (Số 1, Số 2, Số 3, Số 4, Tiểu đội trưởng...)
            if b_name.startswith("Số ") or b_name.startswith("Tiểu đội") or "ginyu" in b_name.lower():
                return 25
            # Bojack team
            if any(k in b_name for k in ["Bojack", "Bujin", "Bido", "Zangya"]):
                return 24
            # Mặc định trạm tàu Trái Đất
            return 24

        # 4. Tra cứu thông thường
        # Tra cứu chính xác theo tên
        for mid, name in MAP_NAMES.items():
            if name.lower() == raw_map.lower():
                return mid

        # Tra cứu chuẩn hóa
        for mid, name in MAP_NAMES.items():
            if normalize_str(name) == norm_map:
                return mid

        resolved = resolve_map_id(raw_map)
        return resolved if resolved is not None else -1

    @classmethod
    def parse_boss_announcement(cls, chat_vip_text: str) -> Optional[Boss]:
        """
        Bóc tách chuỗi ChatVip để kiểm tra xem có phải thông báo Boss hay không.
        Trả về thực thể Boss tương ứng nếu đúng, hoặc None nếu là chat thông thường.
        """
        text = chat_vip_text.strip()
        if text.startswith("!"):
            text = text[1:].strip()

        # 1. Kiểm tra Boss bị tiêu diệt
        if any(k in text for k in cls.STR_BOSS_KILLED):
            temp_text = text
            for k in cls.STR_BOSS_KILLED:
                temp_text = temp_text.replace(k, "|")
            parts = temp_text.split("|")
            if len(parts) >= 2:
                killer = parts[0].strip()
                boss_name = parts[1].strip()
                if boss_name.upper().startswith("BOSS "):
                    boss_name = boss_name[5:].strip()
                return Boss(name=boss_name, map_name="", is_died=True, killer=killer)

        # 2. Kiểm tra Boss xuất hiện
        is_appear = any(app in text for app in cls.STR_BOSS_APPEARED[1:4]) or text.startswith(cls.STR_BOSS_APPEARED[0])
        if is_appear:
            temp_text = text
            for k in cls.STR_BOSS_APPEARED:
                temp_text = temp_text.replace(k, "|")
            parts = temp_text.split("|")
            if len(parts) >= 3:
                boss_name = parts[1].strip()
                map_name = parts[2].strip()
                zone_id = -1
                if len(parts) >= 4 and parts[3].strip().isdigit():
                    zone_id = int(parts[3].strip())
                map_id = cls.resolve_boss_map_id(boss_name, map_name)
                return Boss(
                    name=boss_name,
                    map_name=map_name,
                    map_id=map_id,
                    zone_id=zone_id,
                    is_died=False,
                )

        return None

    def handle_chat_vip_obj(self, chat_vip) -> None:
        """Nhận sự kiện ChatVip đối tượng từ Controller."""
        raw_text = getattr(chat_vip, "text", "")
        if raw_text:
            self.handle_chat_vip(raw_text)

    def handle_chat_vip(self, chat_vip_text: str) -> Optional[Boss]:
        """
        Bóc tách chuỗi ChatVip từ server tương tự Mod.Boss.AddBoss(string chatVip).
        Hỗ trợ cả thông báo Boss xuất hiện và Boss bị tiêu diệt.
        """
        text = chat_vip_text.strip()
        if text.startswith("!"):
            text = text[1:].strip()

        # 1. Kiểm tra Boss bị tiêu diệt
        if any(k in text for k in self.STR_BOSS_KILLED):
            temp_text = text
            for k in self.STR_BOSS_KILLED:
                temp_text = temp_text.replace(k, "|")
            parts = temp_text.split("|")
            if len(parts) >= 2:
                killer = parts[0].strip()
                boss_name = parts[1].strip()
                if boss_name.upper().startswith("BOSS "):
                    boss_name = boss_name[5:].strip()

                boss = None
                # Tìm Boss gần nhất trong danh sách (Last)
                for b in reversed(self.list_bosses):
                    # Ngoại lệ map 79, 82, 83 với Tiểu đội sát thủ
                    if b.map_id in (79, 82, 83):
                        if re.search(
                            r"(Tiểu đội trưởng|(Captain|Kapten) Ginyu|Số [1-4]|Jeice|Burter|Recoome|Guldo)",
                            b.name,
                            re.IGNORECASE,
                        ):
                            continue
                    if b.name == boss_name and not b.killer:
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
            # Kết quả sau khi split:
            # parts[0] = '' (trước 'BOSS ')
            # parts[1] = boss_name
            # parts[2] = map_name
            # parts[3] = zone_id (nếu có)
            if len(parts) >= 3:
                boss_name = parts[1].strip()
                map_name = parts[2].strip()
                zone_id = -1
                if len(parts) >= 4 and parts[3].strip().isdigit():
                    zone_id = int(parts[3].strip())

                map_id = self.resolve_boss_map_id(boss_name, map_name)

                boss = None
                # Tìm boss chưa có map hoặc đang chờ
                for b in reversed(self.list_bosses):
                    if map_id in (79, 82, 83):
                        if re.search(
                            r"(Tiểu đội trưởng|(Captain|Kapten) Ginyu|Số [1-4]|Jeice|Burter|Recoome|Guldo)",
                            boss_name,
                            re.IGNORECASE,
                        ):
                            continue
                    if (not b.map_name) and b.name == boss_name:
                        boss = b
                        break

                if boss is None:
                    boss = Boss(
                        name=boss_name,
                        map_name=map_name,
                        map_id=map_id,
                        zone_id=zone_id,
                        appear_time=time.time(),
                        is_died=False,
                    )
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
        """Giữ tối đa MAX_BOSS trong danh sách."""
        while len(self.list_bosses) > self.MAX_BOSS:
            self.list_bosses.pop(0)

    def on_map_changed(self, map_info) -> None:
        """Kích hoạt khi thông tin map hiện tại được cập nhật."""
        self.update_boss_status(map_info.mapID, map_info.zoneID, map_info.chars)

        # Nếu đang trong tiến trình đến Boss và đã vào đúng map
        if self.pending_zone_id != -1 and map_info.mapID != -1:
            # Kiểm tra xem có cần đổi khu vực không
            if map_info.zoneID != self.pending_zone_id:
                if self.client:
                    print(f"[*] Đã tới map của Boss! Đang tự động đổi sang Khu {self.pending_zone_id}...")
                    self.client.change_zone(self.pending_zone_id)
            self.pending_zone_id = -1
            self.pending_boss_name = ""

    def _on_xmap_finished(self, success: bool, message: str) -> None:
        """Callback khi tiến trình Xmap kết thúc."""
        if success and self.pending_zone_id != -1 and self.client:
            curr_zone = getattr(self.client.myChar.mapInfo, "zoneID", -1)
            if curr_zone != self.pending_zone_id:
                print(f"[*] Xmap hoàn tất! Tự động đổi sang Khu {self.pending_zone_id}...")
                self.client.change_zone(self.pending_zone_id)
            self.pending_zone_id = -1
            self.pending_boss_name = ""

    def update_boss_status(
        self,
        current_map_id: int,
        current_zone_id: int,
        chars_in_map: Optional[Dict[int, Any]] = None,
    ) -> None:
        """
        Cập nhật trạng thái sống/chết của các Boss trong danh sách theo thực tế map hiện tại.
        Mô phỏng hàm Update() trong Mod/Boss.cs.
        """
        chars_list = list(chars_in_map.values()) if chars_in_map else []

        for boss in self.list_bosses:
            if boss.is_died:
                continue

            if boss.map_id == current_map_id and current_map_id != -1:
                # Tìm Boss trong danh sách nhân vật
                found_char = None
                for ch in chars_list:
                    ch_name = getattr(ch, "cName", "")
                    if ch_name == boss.name:
                        found_char = ch
                        break

                if found_char is not None:
                    # Nếu chưa biết khu vực thì cập nhật khu vực hiện tại
                    if boss.zone_id == -1:
                        boss.zone_id = current_zone_id

                    # Nếu nhân vật đã chết
                    is_die = getattr(found_char, "isDie", False)
                    hp = getattr(found_char, "cHP", 1)
                    if is_die or hp == 0:
                        boss.is_died = True
                else:
                    # Nếu đang ở đúng khu vực của Boss mà không thấy Boss -> Boss đã chết
                    if boss.zone_id == current_zone_id and boss.zone_id != -1:
                        boss.is_died = True

    def get_alive_bosses(self) -> List[Boss]:
        """Lấy danh sách các Boss đang còn sống."""
        return [b for b in self.list_bosses if not b.is_died]

    def get_all_bosses(self) -> List[Boss]:
        """Lấy toàn bộ danh sách Boss (bao gồm cả đã chết)."""
        return list(self.list_bosses)

    def find_boss(self, query: Union[int, str]) -> Optional[Boss]:
        """
        Tìm kiếm Boss theo:
        - Số thứ tự (index 1-based trong danh sách boss sống hoặc danh sách đầy đủ)
        - Tên Boss (chuỗi tiếng Việt có hoặc không dấu)
        """
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

        # Nếu là số nguyên dưới dạng chuỗi
        if raw.isdigit():
            idx = int(raw)
            alive = self.get_alive_bosses()
            if 1 <= idx <= len(alive):
                return alive[idx - 1]
            if 1 <= idx <= len(self.list_bosses):
                return self.list_bosses[idx - 1]
            return None

        norm_q = normalize_str(raw)
        # 1. Tìm trong boss còn sống trước
        for b in reversed(self.get_alive_bosses()):
            if norm_q in normalize_str(b.name):
                return b

        # 2. Tìm trong toàn bộ danh sách
        for b in reversed(self.list_bosses):
            if norm_q in normalize_str(b.name):
                return b

        return None

    def go_to_boss(self, target: Union[int, str]) -> Tuple[bool, str]:
        """
        Kích hoạt tự động di chuyển đến Boss bằng Xmap và tự đổi sang khu vực của Boss.
        Mô phỏng thao tác Click vào dòng Boss trong Mod/Boss.cs.
        """
        boss = self.find_boss(target)
        if boss is None:
            return False, f"Không tìm thấy Boss phù hợp với yêu cầu '{target}'!"

        if boss.is_died:
            reason = f"bị {boss.killer} tiêu diệt" if boss.killer else "đã chết"
            return False, f"Boss '{boss.name}' đã {reason}!"

        if boss.map_id == -1:
            return False, f"Boss '{boss.name}' chưa xác định được bản đồ (map='{boss.map_name}')!"

        curr_map_id = -1
        curr_zone_id = -1
        if self.client and hasattr(self.client, "myChar"):
            curr_map_id = getattr(self.client.myChar.mapInfo, "mapID", -1)
            curr_zone_id = getattr(self.client.myChar.mapInfo, "zoneID", -1)

        # 1. Nếu đang ở khác bản đồ -> Bắt đầu Xmap
        if curr_map_id != boss.map_id:
            if not self.client or not hasattr(self.client, "xmap"):
                return False, f"Client chưa sẵn sàng tính năng Xmap để đi tới map {boss.map_id}!"

            self.pending_zone_id = boss.zone_id
            self.pending_boss_name = boss.name

            zone_desc = f" khu {boss.zone_id}" if boss.zone_id != -1 else ""
            print(f"[*] Bắt đầu Xmap di chuyển tới Boss '{boss.name}' tại '{boss.map_name}' [{boss.map_id}]{zone_desc}...")
            ok = self.client.xmap(boss.map_id)
            if not ok:
                self.pending_zone_id = -1
                return False, f"Không thể bắt đầu Xmap tới map {boss.map_id}!"
            return True, f"Đang Xmap tới '{boss.map_name}' [{boss.map_id}] (Boss: {boss.name})..."

        # 2. Nếu đã ở cùng bản đồ
        if boss.zone_id != -1 and curr_zone_id != boss.zone_id:
            if self.client and hasattr(self.client, "change_zone"):
                print(f"[*] Đang ở map '{boss.map_name}'. Đổi sang Khu {boss.zone_id} của Boss '{boss.name}'...")
                self.client.change_zone(boss.zone_id)
                return True, f"Đã gửi yêu cầu đổi sang Khu {boss.zone_id} của Boss '{boss.name}'!"

        return True, f"Bạn đã có mặt tại map '{boss.map_name}' khu {curr_zone_id} cùng Boss '{boss.name}'!"

    def clear(self) -> None:
        """Xóa toàn bộ lịch sử Boss."""
        self.list_bosses.clear()
        self.pending_zone_id = -1
        self.pending_boss_name = ""

    def __len__(self) -> int:
        return len(self.list_bosses)
