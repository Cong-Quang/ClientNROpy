# -*- coding: utf-8 -*-
"""
Bộ săn Boss tự động (BossHunter).
Tự động hóa hoàn toàn quy trình săn Boss không cần đồ họa:
- Lắng nghe thông báo Boss xuất hiện từ server
- Lọc theo danh sách Boss cấu hình (whitelist)
- Kiểm tra trạng thái sống/chết (bỏ qua nếu đã bị người khác hạ)
- Kích hoạt Xmap bay tới map của Boss
- Tự động dò qua các khu vực trong map để tìm Boss
- Thấy Boss: Teleport áp sát, khóa tiêu điểm, gửi lệnh đánh liên tục
- Chết: Tự động hồi sinh về thành, Xmap quay lại map và vào lại khu đánh tiếp
- Boss chết: Tự động nhặt vật phẩm rơi quanh khu vực
- Chuyển sang Boss tiếp theo hoặc chờ thông báo mới
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import time
import math
import random
import threading
from typing import Optional, List, Set, Dict, Any, Union, Tuple

from .boss import Boss
from .char import Char
from .xmap.map_data import normalize_str, get_map_name


class BossHunter:
    """
    Máy trạng thái tự động săn Boss (Autonomous Boss Hunter).
    """

    STATE_IDLE = "IDLE"
    STATE_MOVING = "MOVING"
    STATE_SCANNING = "SCANNING"
    STATE_COMBAT = "COMBAT"
    STATE_REVIVING = "REVIVING"
    STATE_LOOTING = "LOOTING"
    STATE_PATROL = "PATROL"

    # Whitelist cấu hình mặc định theo yêu cầu người dùng
    DEFAULT_WHITELIST: List[str] = [
        "Black Goku",
        "Supper Black Goku",
        "Super Black Goku",
        "Zamas",
        "Zamas Kaioshin",
        "Bojack",
        "Đội Bojack",
        "Xên con",
        "Xên bọ hung",
        "Số 4 Recome Namec",
        "Số 3 Recome Namec",
        "Số 2 Recome Namec",
        "Số 1 Recome Namec",
        "Tiểu đội trưởng Ginyu Namec",
        "Mabư",
        "Doraemon",
        "Nobita",
        "Suneo",
        "Chaien",
        "Android 13",
        "Android 14",
        "Android 15",
    ]

    # Danh sách các map Tương Lai tuần tra (Xên bọ hung, Xên con, Black Goku, Zamas...)
    # 102: Nhà Gohan (Tương lai), 92: TP phía đông, 93: TP phía nam, 94: Đảo Balê,
    # 96: Thị trấn Ginder, 97: Thung lũng phía bắc, 98: TP phía bắc, 99: Ngọn núi phía bắc,
    # 100: Rừng nguyên sinh, 103: Võ đài Siêu Bọ Hung
    FUTURE_PATROL_MAPS: List[int] = [102, 92, 93, 94, 96, 97, 98, 99, 100, 103]

    # Danh sách các map Hành tinh Namec tuần tra (Tiểu Đội Sát Thủ Namec: Số 4 -> Tiểu đội trưởng)
    # 7: Làng Mori, 8: Đồi nấm tím, 9: Thị trấn Moori, 10: Thung lũng Namếc, 11: Thung lũng Maima,
    # 12: Vực maima, 13: Đảo Guru, 31: Núi hoa vàng, 32: Núi hoa tím, 33: Nam Guru, 34: Đông Nam Guru, 43: Vách núi Moori
    NAMEC_PATROL_MAPS: List[int] = [7, 8, 9, 10, 11, 12, 13, 31, 32, 33, 34, 43]

    # Núi khỉ đỏ (79) - Nơi xuất hiện TDST Trái Đất (Số 4, Số 3, Số 2, Số 1, Tiểu đội trưởng)
    RED_MONKEY_MAPS: List[int] = [7]

    # Danh sách toàn bộ các map tuần tra khi rảnh rỗi (Mặc định: Tương Lai + Hành tinh Namec + Núi khỉ đỏ)
    DEFAULT_PATROL_MAPS: List[int] = (
        FUTURE_PATROL_MAPS + NAMEC_PATROL_MAPS + RED_MONKEY_MAPS
    )

    def __init__(self, client=None):
        self.client = client

        # Cấu hình tính năng
        self.is_enabled: bool = False                 # Ban đầu chưa kích hoạt, chờ người dùng gõ lệnh 'hunt auto' hoặc 'hunt on'
        self.hunt_all: bool = False                   # Mặc định chỉ săn theo Whitelist
        self.target_bosses: Set[str] = set()          # Danh sách Boss muốn săn (chuỗi chuẩn hoá)
        for t in self.DEFAULT_WHITELIST:
            self.add_target(t)

        self.auto_loot: bool = True                   # Mặc định Tự động nhặt đồ sau khi Boss chết là BẬT
        self.auto_revive: bool = True                 # Mặc định Tự động hồi sinh là BẬT
        self.revive_mode: str = "gem"                 # Mặc định Hồi sinh bằng NGỌC tại chỗ
        self.auto_patrol: bool = True                 # Mặc định Tự động tuần tra khi rảnh rỗi là BẬT
        self.patrol_maps: List[int] = list(self.DEFAULT_PATROL_MAPS)  # Danh sách map đi tuần (ưu tiên Tương Lai trước)
        self.patrol_map_index: int = 0                # Chỉ số map đang tuần tra (bắt đầu từ Tương Lai)
        self.min_scan_zone_delay: float = 0.5         # Thời gian dừng tối thiểu mỗi khu để dò boss (giây)
        self.max_scan_zone_delay: float = 0.7         # Thời gian dừng tối đa mỗi khu để dò boss (giây)
        self.max_zones_scan: int = 30                 # Số khu tối đa sẽ dò trong 1 map

        # Cờ đánh dấu khu đang bị chặn bởi boss hỗ trợ nhiệm vụ
        self._zone_blocked_by_quest: bool = False

        # Trạng thái thực thi
        self.state: str = self.STATE_IDLE
        self.current_boss: Optional[Boss] = None
        self.current_scan_zone: int = 0
        self.scanned_zones: Set[int] = set()
        self.last_state_change: float = time.time()
        self.looting_start_time: float = 0.0
        self.last_attack_time: float = 0.0
        self.last_boss_pos: Optional[Tuple[int, int]] = None
        self.status_message: str = "Đang chờ lệnh hoặc thông báo Boss mới..."

        # Đăng ký lắng nghe sự kiện Boss bị tiêu diệt từ BossManager (ChatVip cmd 93)
        if self.client and hasattr(self.client, "boss_manager"):
            try:
                self.client.boss_manager.on_boss_killed_callbacks.append(self._on_boss_killed_event)
            except Exception:
                pass

        # Đăng ký lắng nghe thông báo chặn khu từ server
        if self.client and hasattr(self.client, "controller"):
            try:
                self.client.controller.on_server_message_callbacks.append(self._on_server_message)
            except Exception:
                pass

        # Quản lý luồng nền
        self._is_running: bool = False
        self._thread: Optional[threading.Thread] = None

        self._start_thread()

    def _start_thread(self) -> None:
        """Khởi động luồng nền quản lý máy trạng thái."""
        if self._thread is None or not self._thread.is_alive():
            self._is_running = True
            self._thread = threading.Thread(target=self._worker_loop, daemon=True, name="BossHunterThread")
            self._thread.start()

    def _log(self, msg: str, is_important: bool = False, is_alert: bool = False) -> None:
        """Ghi log phân loại qua ConsoleLogger với tag tài khoản."""
        self.status_message = msg
        from .logger import logger
        tag = getattr(self.client, "account_id", "BossHunter") if self.client else "BossHunter"
        if is_alert:
            logger.alert(msg, account_tag=tag)
        elif is_important:
            logger.boss(msg, account_tag=tag)
        else:
            logger.auto(msg, account_tag=tag)

    # --------------------------------------------------------------------------
    # ĐIỀU KHIỂN & CẤU HÌNH API
    # --------------------------------------------------------------------------
    def start(self, targets: Optional[List[str]] = None) -> None:
        """Bắt đầu tính năng Auto Săn Boss."""
        if targets:
            self.clear_targets()
            for t in targets:
                self.add_target(t)
        self.is_enabled = True
        self.state = self.STATE_IDLE
        self._log("Đã kích hoạt Auto Săn Boss!")

    def stop(self) -> None:
        """Dừng tính năng Auto Săn Boss."""
        self.is_enabled = False
        self.state = self.STATE_IDLE
        self.current_boss = None
        if self.client and hasattr(self.client, "xmap_stop"):
            self.client.xmap_stop()
        self._log("Đã dừng Auto Săn Boss.")

    def toggle(self) -> bool:
        """Bật / Tắt tính năng Auto Săn Boss."""
        if self.is_enabled:
            self.stop()
        else:
            self.start()
        return self.is_enabled

    def add_target(self, boss_name: str) -> None:
        """Thêm một Boss vào danh sách muốn săn (Whitelist). Hỗ trợ chuẩn hóa và lược bỏ hậu tố xx."""
        clean_name = boss_name.rstrip()
        if clean_name.lower().endswith(" xx"):
            clean_name = clean_name[:-3].strip()
        norm = normalize_str(clean_name)
        if norm:
            self.target_bosses.add(norm)
            self.hunt_all = False

    def remove_target(self, boss_name: str) -> None:
        """Xóa một Boss khỏi danh sách muốn săn."""
        clean_name = boss_name.rstrip()
        if clean_name.lower().endswith(" xx"):
            clean_name = clean_name[:-3].strip()
        norm = normalize_str(clean_name)
        if norm in self.target_bosses:
            self.target_bosses.remove(norm)
        if not self.target_bosses:
            self.hunt_all = True

    def clear_targets(self) -> None:
        """Xóa danh sách cấu hình Boss (chuyển sang săn tất cả)."""
        self.target_bosses.clear()
        self.hunt_all = True

    def get_targets(self) -> List[str]:
        """Lấy danh sách tên boss trong Whitelist."""
        return list(self.target_bosses)

    @property
    def auto_patrol_future(self) -> bool:
        """Hỗ trợ tương thích ngược với thuộc tính cũ."""
        return self.auto_patrol

    @auto_patrol_future.setter
    def auto_patrol_future(self, val: bool) -> None:
        self.auto_patrol = bool(val)

    def set_patrol_mode(self, mode: str) -> None:
        """
        Cấu hình danh mục map tuần tra:
        - 'all': Toàn bộ (Tương Lai + Namec + Núi khỉ đỏ)
        - 'namec' / 'tdst': Chỉ các map Hành tinh Namec và Núi khỉ đỏ (săn TDST)
        - 'future' / 'tl': Chỉ các map Tương Lai
        """
        m = mode.lower().strip()
        if m in ("namec", "namek", "tdst"):
            self.patrol_maps = list(self.NAMEC_PATROL_MAPS) + list(self.RED_MONKEY_MAPS)
        elif m in ("future", "tl", "tuonglai"):
            self.patrol_maps = list(self.FUTURE_PATROL_MAPS)
        else:
            self.patrol_maps = list(self.DEFAULT_PATROL_MAPS)
        self.patrol_map_index = 0

    def set_auto_patrol(self, enabled: bool) -> None:
        """Cấu hình tự động tuần tra các map khi rảnh rỗi."""
        self.auto_patrol = bool(enabled)

    def toggle_auto_patrol(self) -> bool:
        """Bật / Tắt tự động tuần tra."""
        self.auto_patrol = not self.auto_patrol
        return self.auto_patrol

    def set_hunt_all(self, val: bool) -> None:
        """Đặt chế độ săn tất cả hay chỉ theo Whitelist."""
        self.hunt_all = val

    def is_target_boss(self, boss: Boss) -> bool:
        """Kiểm tra Boss có thuộc đối tượng cần săn hay không."""
        if self.hunt_all or not self.target_bosses:
            return True
        norm_b = normalize_str(boss.name)
        return any(t in norm_b or norm_b in t for t in self.target_bosses)

    @property
    def scan_zone_delay(self) -> float:
        """Thời gian chờ đổi khu trung bình (hỗ trợ tương thích ngược)."""
        return (self.min_scan_zone_delay + self.max_scan_zone_delay) / 2.0

    @scan_zone_delay.setter
    def scan_zone_delay(self, val: float) -> None:
        """Thiết lập thời gian chờ đổi khu cố định."""
        self.min_scan_zone_delay = float(val)
        self.max_scan_zone_delay = float(val)

    def set_scan_delay(self, min_val: float, max_val: Optional[float] = None) -> None:
        """Cấu hình khoảng thời gian ngẫu nhiên dừng ở mỗi khu để dò boss (giây)."""
        self.min_scan_zone_delay = max(0.0, float(min_val))
        if max_val is not None:
            self.max_scan_zone_delay = max(self.min_scan_zone_delay, float(max_val))
        else:
            self.max_scan_zone_delay = self.min_scan_zone_delay

    def get_scan_delay(self) -> float:
        """Lấy thời gian chờ ngẫu nhiên giữa các lần đổi khu (mặc định 0.5 - 0.7 giây)."""
        if self.min_scan_zone_delay >= self.max_scan_zone_delay:
            return self.min_scan_zone_delay
        return round(random.uniform(self.min_scan_zone_delay, self.max_scan_zone_delay), 3)

    def tick(self) -> None:
        """Thực hiện một chu kỳ máy trạng thái (dùng cho gọi thủ công hoặc test)."""
        if self.is_enabled:
            self._step()

    # --------------------------------------------------------------------------
    # VÒNG LẶP MÁY TRẠNG THÁI (STATE MACHINE LOOP)
    # --------------------------------------------------------------------------
    def _worker_loop(self) -> None:
        """Vòng lặp chu kỳ xử lý các trạng thái săn Boss."""
        while self._is_running:
            try:
                if self.is_enabled:
                    self._step()
            except Exception as ex:
                if getattr(self.client, "debug", False):
                    self._log(f"Worker error: {ex}", is_alert=True)
            time.sleep(0.15)

    def _on_server_message(self, text: str) -> None:
        """Lắng nghe thông báo từ server (hỗ trợ phát hiện khu bị khóa do có boss hỗ trợ nhiệm vụ)."""
        norm = normalize_str(text)
        if (
            "boss duoc ho tro" in norm
            or "khong the vao luc nay" in norm
            or ("ho tro" in norm and "khu vuc" in norm)
        ):
            self._zone_blocked_by_quest = True

    def _step(self) -> None:
        """Thực thi 1 bước trong máy trạng thái."""
        my_char = self._get_my_char()
        if my_char is None:
            return

        # Kiểm tra nhân vật bị chết thật sự ở bất kỳ trạng thái nào
        is_dead = (my_char.cHPFull > 0 and my_char.cHP <= 0) or getattr(my_char, "statusMe", 1) == 14
        if is_dead:
            if self.auto_revive and self.state != self.STATE_REVIVING:
                self._change_state(self.STATE_REVIVING)

        # 1. Trạng thái HỒI SINH (REVIVING)
        if self.state == self.STATE_REVIVING:
            self._handle_reviving(my_char)
            return

        # 2. Kiểm tra xem Boss hiện tại đã bị người khác tiêu diệt chưa
        if self.current_boss:
            if self.current_boss.is_died:
                if self.state == self.STATE_COMBAT and self.auto_loot:
                    self._change_state(self.STATE_LOOTING)
                    self.looting_start_time = time.time()
                elif self.state != self.STATE_LOOTING:
                    killer_str = f" bởi '{self.current_boss.killer}'" if self.current_boss.killer else ""
                    self.status_message = f"Boss '{self.current_boss.name}' đã bị hạ{killer_str}. Đổi mục tiêu!"
                    self._log(self.status_message, is_important=True)
                    self.current_boss = None
                    self._change_state(self.STATE_IDLE)
                    return

        # 3. Trạng thái CHỜ / CHỌN BOSS (IDLE)
        if self.state == self.STATE_IDLE:
            self._handle_idle()
            return

        # 4. Trạng thái TUẦN TRA MAP TƯƠNG LAI KHI RẢNH RỖI (PATROL)
        if self.state == self.STATE_PATROL:
            self._handle_patrol(my_char)
            return

        # 5. Trạng thái DI CHUYỂN TỚI MAP (MOVING)
        if self.state == self.STATE_MOVING:
            self._handle_moving(my_char)
            return

        # 6. Trạng thái DÒ KHU VỰC TÌM BOSS (SCANNING)
        if self.state == self.STATE_SCANNING:
            self._handle_scanning(my_char)
            return

        # 7. Trạng thái TẤN CÔNG BOSS (COMBAT)
        if self.state == self.STATE_COMBAT:
            self._handle_combat(my_char)
            return

        # 8. Trạng thái NHẶT ĐỒ SAU KHI BOSS CHẾT (LOOTING)
        if self.state == self.STATE_LOOTING:
            self._handle_looting(my_char)
            return

    # --------------------------------------------------------------------------
    # XỬ LÝ TỪNG TRẠNG THÁI
    # --------------------------------------------------------------------------
    def _handle_idle(self) -> None:
        """Tìm và chọn mục tiêu Boss tiếp theo hoặc chuyển sang tuần tra map tương lai khi rảnh rỗi."""
        next_boss = self._select_next_boss()
        if next_boss is not None:
            self.current_boss = next_boss
            self.scanned_zones.clear()
            self.status_message = f"Phát hiện mục tiêu: '{next_boss.name}' tại '{next_boss.map_name}' [{next_boss.map_id}]. Bắt đầu di chuyển!"
            self._log(self.status_message, is_important=True)
            self._change_state(self.STATE_MOVING)
            my_char = self._get_my_char()
            if my_char:
                self._handle_moving(my_char)
        else:
            # Nếu đang rảnh rỗi (chưa có thông báo Boss) và bật tự động tuần tra
            if self.auto_patrol and self.patrol_maps:
                if self.patrol_map_index >= len(self.patrol_maps):
                    self.patrol_map_index = 0
                curr_map = self.patrol_maps[self.patrol_map_index]
                self.status_message = f"Đang rảnh rỗi (chưa có Boss mục tiêu). Bắt đầu tuần tra map {curr_map} ({get_map_name(curr_map)})..."
                self._log(self.status_message)
                self._change_state(self.STATE_PATROL)
            else:
                self.status_message = "Đang chờ Boss xuất hiện hoặc có Boss trong danh sách cấu hình..."

    def _select_next_boss(self) -> Optional[Boss]:
        """Lọc và chọn Boss còn sống phù hợp với cấu hình săn."""
        if not self.client or not hasattr(self.client, "boss_manager"):
            return None

        alive_bosses = self.client.boss_manager.get_alive_bosses()
        for b in reversed(alive_bosses):
            if not b.is_died and b.map_id != -1 and self.is_target_boss(b):
                return b
        return None

    def _handle_moving(self, my_char: Char) -> None:
        """Xử lý di chuyển Xmap tới bản đồ của Boss."""
        if not self.current_boss:
            self._change_state(self.STATE_IDLE)
            return

        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)

        # Đã tới đúng map của Boss
        if curr_map_id == self.current_boss.map_id:
            self.status_message = f"Đã tới map '{self.current_boss.map_name}' [{self.current_boss.map_id}]. Bắt đầu quét khu vực!"
            self._log(self.status_message)
            self._change_state(self.STATE_SCANNING)
            return

        # Chưa tới map -> Kích hoạt Xmap
        if self.client and hasattr(self.client, "xmap"):
            xmap_st = self.client.xmap_status()
            if not xmap_st.get("is_acting", False):
                self.status_message = f"Đang Xmap tới map {self.current_boss.map_id} của Boss '{self.current_boss.name}'..."
                self.client.xmap(self.current_boss.map_id)

    def _handle_scanning(self, my_char: Char) -> None:
        """
        Dò qua từng khu vực trong map để phát hiện Boss theo thuật toán mã giả:
        START
        khu_hien_tai = 0
        tong_so_khu = tổng_số_lượng_khu
        FOR khu = 1 TO tong_so_khu:
            IF khu == khu_hien_tai:
                CONTINUE
            WHILE chưa_đổi_khu_thành_công(khu):
                đổi_khu(khu)
                sleep(0.5)
            khu_hien_tai = khu
            IF nhân_vật_đang_ở_trong_map_hiện_tại == BOSS:
                RETURN
        END FOR
        END
        """
        if not self.current_boss:
            self._change_state(self.STATE_IDLE)
            return

        # khu_hien_tai ban đầu (thường là khu hiện tại của nhân vật khi vừa vào map, mặc định 0)
        khu_hien_tai = getattr(my_char.mapInfo, "zoneID", 0)
        if khu_hien_tai < 0:
            khu_hien_tai = 0

        # Kiểm tra ngay nếu Boss đang ở khu hiện tại
        boss_char = self._find_boss_in_current_map(my_char)
        if boss_char is not None:
            self.current_boss.zone_id = khu_hien_tai
            self.status_message = f"ĐÃ TÌM THẤY BOSS '{self.current_boss.name}' tại Khu {khu_hien_tai}! Bắt đầu chiến đấu!"
            self._log(self.status_message, is_important=True)
            self._change_state(self.STATE_COMBAT)
            return

        # Yêu cầu tải danh sách khu từ server nếu chưa có
        if not my_char.mapInfo.zones:
            if self.client and hasattr(self.client, "service"):
                self.client.service.openUIZone()
                time.sleep(0.5)

        # tong_so_khu = tổng_số_lượng_khu
        if my_char.mapInfo.zones:
            tong_so_khu = len(my_char.mapInfo.zones)
            # Ưu tiên lấy các zoneId thực tế từ server
            zone_ids = [z.zoneId for z in my_char.mapInfo.zones if z.zoneId > 0]
            if not zone_ids:
                zone_ids = list(range(1, tong_so_khu + 1))
        else:
            tong_so_khu = self.max_zones_scan
            zone_ids = list(range(1, tong_so_khu + 1))

        # Nếu Boss có zone_id cụ thể từ thông báo ChatVip (ví dụ khu 10), ưu tiên thử zone đó trước trong danh sách
        if self.current_boss.zone_id != -1 and self.current_boss.zone_id in zone_ids:
            zone_ids = [self.current_boss.zone_id] + [z for z in zone_ids if z != self.current_boss.zone_id]

        # FOR khu = 1 TO tong_so_khu:
        for khu in zone_ids:
            if not self.is_enabled or not self.current_boss or self.current_boss.is_died:
                return

            # IF khu == khu_hien_tai: CONTINUE
            if khu == khu_hien_tai:
                continue

            # WHILE chưa_đổi_khu_thành_công(khu):
            #     đổi_khu(khu)
            #     sleep(0.5)
            retries = 0
            max_retries = 3  # Thử 3 lần giãn cách 1.5s (~4.5s) tuân thủ cooldown 4s của server
            self._zone_blocked_by_quest = False
            while self.is_enabled and getattr(my_char.mapInfo, "zoneID", -1) != khu:
                if not self.current_boss or self.current_boss.is_died:
                    return

                # Nếu nhận thông báo "Khu vực đang có boss được hỗ trợ / Bạn không thể vào lúc này"
                if self._zone_blocked_by_quest:
                    self._log(f"Khu {khu} đang có Boss được hỗ trợ nhiệm vụ. Bỏ qua tạm thời!")
                    self._zone_blocked_by_quest = False
                    break

                self.status_message = f"Đang dò Boss '{self.current_boss.name}': đổi sang Khu {khu} (lần {retries + 1})..."
                if self.client and hasattr(self.client, "change_zone"):
                    self.client.change_zone(khu)
                time.sleep(1.5)
                retries += 1

                if self._zone_blocked_by_quest:
                    self._log(f"Khu {khu} đang có Boss được hỗ trợ nhiệm vụ. Bỏ qua tạm thời!")
                    self._zone_blocked_by_quest = False
                    break

                if retries >= max_retries:
                    self._log(f"Không thể vào Khu {khu} (có thể khu đầy). Chuyển khu tiếp theo.")
                    break

            if getattr(my_char.mapInfo, "zoneID", -1) != khu:
                continue

            # khu_hien_tai = khu
            khu_hien_tai = khu
            self.scanned_zones.add(khu)

            # Chờ 0.1s để server cập nhật danh sách nhân vật/boss trong khu vừa vào
            time.sleep(0.1)

            # IF nhân_vật_đang_ở_trong_map_hiện_tại == BOSS: RETURN
            boss_char = self._find_boss_in_current_map(my_char)
            if boss_char is not None:
                self.current_boss.zone_id = khu
                self.status_message = f"ĐÃ TÌM THẤY BOSS '{self.current_boss.name}' tại Khu {khu}! Bắt đầu chiến đấu!"
                self._log(self.status_message, is_important=True)
                self._change_state(self.STATE_COMBAT)
                return

        # END FOR
        # Đã quét toàn bộ khu mà không thấy Boss -> Boss đã bị hạ hoặc biến mất
        self.status_message = f"Đã quét toàn bộ {tong_so_khu} khu map {self.current_boss.map_id} không thấy Boss '{self.current_boss.name}'. Đánh dấu Boss đã chết!"
        self._log(self.status_message)
        self.current_boss.is_died = True
        self.current_boss = None
        self._change_state(self.STATE_IDLE)

    def _handle_patrol(self, my_char: Char) -> None:
        """
        Tuần tra các map (Tương Lai + Namec + Núi khỉ đỏ) khi đang rảnh rỗi để tìm các boss xuất hiện trước:
        - Nếu có thông báo Boss mới từ server (ChatVip) -> Dừng tuần tra, ưu tiên bay đến Boss đó ngay!
        - Nếu chưa ở map tuần tra hiện tại -> Xmap tới map tuần tra đó.
        - Khi ở trong map tuần tra -> Dò lần lượt từng khu:
            + Nếu phát hiện Boss mục tiêu trong khu -> Chuyển sang STATE_COMBAT đấm Boss!
            + Nếu gặp thông báo 'Khu vực đang có boss được hỗ trợ / Bạn không thể vào lúc này' -> Bỏ qua khu đó tạm thời!
        - Khi đã dò hết các khu trong 1 map -> Di chuyển sang map tiếp theo trong danh sách!
        """
        # 1. Luôn kiểm tra ưu tiên: Có thông báo Boss mục tiêu mới từ server không?
        next_boss = self._select_next_boss()
        if next_boss is not None:
            self.current_boss = next_boss
            self.scanned_zones.clear()
            self.status_message = f"Phát hiện thông báo Boss '{next_boss.name}' tại '{next_boss.map_name}' [{next_boss.map_id}]! Dừng tuần tra, bắt đầu di chuyển!"
            self._log(self.status_message, is_important=True)
            self._change_state(self.STATE_MOVING)
            return

        if not self.patrol_maps:
            self._change_state(self.STATE_IDLE)
            return

        if self.patrol_map_index >= len(self.patrol_maps):
            self.patrol_map_index = 0

        target_map_id = self.patrol_maps[self.patrol_map_index]
        curr_map_id = getattr(my_char.mapInfo, "mapID", -1)

        # 2. Nếu chưa tới map tuần tra hiện tại -> Bắt đầu Xmap
        if curr_map_id != target_map_id:
            if self.client and hasattr(self.client, "xmap"):
                xmap_st = self.client.xmap_status()
                if not xmap_st.get("is_acting", False):
                    self.status_message = f"[Tuần Tra] Đang di chuyển tới map {target_map_id} ({get_map_name(target_map_id)})..."
                    self._log(self.status_message)
                    self.client.xmap(target_map_id)
            return

        # 3. Đã ở đúng map tuần tra -> Bắt đầu dò các khu
        khu_hien_tai = getattr(my_char.mapInfo, "zoneID", -1)

        # Kiểm tra nhanh khu hiện tại xem có boss không
        boss_target, boss_name = self._find_any_target_boss_in_current_map(my_char)
        if boss_target is not None:
            self._engage_patrol_boss(boss_name, target_map_id, khu_hien_tai)
            return

        # Tải danh sách khu nếu cần
        if not my_char.mapInfo.zones:
            if self.client and hasattr(self.client, "service"):
                self.client.service.openUIZone()
                time.sleep(0.5)

        if my_char.mapInfo.zones:
            tong_so_khu = len(my_char.mapInfo.zones)
            zone_ids = [z.zoneId for z in my_char.mapInfo.zones if z.zoneId > 0]
            if not zone_ids:
                zone_ids = list(range(1, tong_so_khu + 1))
        else:
            tong_so_khu = self.max_zones_scan
            zone_ids = list(range(1, tong_so_khu + 1))

        # Dò qua từng khu
        for khu in zone_ids:
            if not self.is_enabled or self.state != self.STATE_PATROL:
                return

            # Kiểm tra xem server có thông báo boss mới chưa
            if self._select_next_boss() is not None:
                self._change_state(self.STATE_IDLE)
                return

            if khu == khu_hien_tai:
                continue

            retries = 0
            max_retries = 3  # Thử 3 lần giãn cách 1.5s (~4.5s) tuân thủ cooldown 4s của server
            self._zone_blocked_by_quest = False
            while self.is_enabled and getattr(my_char.mapInfo, "zoneID", -1) != khu:
                if self._select_next_boss() is not None:
                    self._change_state(self.STATE_IDLE)
                    return

                if self._zone_blocked_by_quest:
                    self._log(f"[Tuần Tra] Khu {khu} có boss được hỗ trợ nhiệm vụ. Bỏ qua tạm thời!")
                    self._zone_blocked_by_quest = False
                    break

                self.status_message = f"[Tuần Tra] Dò map {target_map_id} ({get_map_name(target_map_id)}): đổi sang Khu {khu}..."
                if self.client and hasattr(self.client, "change_zone"):
                    self.client.change_zone(khu)
                time.sleep(1.5)
                retries += 1

                if self._zone_blocked_by_quest:
                    self._log(f"[Tuần Tra] Khu {khu} có boss được hỗ trợ nhiệm vụ. Bỏ qua tạm thời!")
                    self._zone_blocked_by_quest = False
                    break

                if retries >= max_retries:
                    break

            if getattr(my_char.mapInfo, "zoneID", -1) != khu:
                continue

            khu_hien_tai = khu
            time.sleep(0.1)

            # Kiểm tra xem có Boss mục tiêu trong khu này không
            boss_target, boss_name = self._find_any_target_boss_in_current_map(my_char)
            if boss_target is not None:
                self._engage_patrol_boss(boss_name, target_map_id, khu)
                return

        # Đã dò hết các khu trong 1 map mà không thấy Boss -> Di chuyển sang map tiếp theo
        self.patrol_map_index = (self.patrol_map_index + 1) % len(self.patrol_maps)
        next_map = self.patrol_maps[self.patrol_map_index]
        self.status_message = (
            f"[Tuần Tra] Đã dò hết toàn bộ {tong_so_khu} khu tại map {target_map_id} "
            f"({get_map_name(target_map_id)}). Chuyển sang map tiếp theo: {next_map} ({get_map_name(next_map)})!"
        )
        self._log(self.status_message)
        if self.client and hasattr(self.client, "xmap"):
            self.client.xmap(next_map)

    def _find_any_target_boss_in_current_map(self, my_char: Char) -> Tuple[Optional[Any], str]:
        """
        Kiểm tra xem có bất kỳ Boss nào trong Whitelist đang hiện diện trong khu hiện tại không.
        Hỗ trợ tìm cả trong danh sách Char và Mob.
        """
        # 1. Quét danh sách nhân vật (Char)
        for ch in my_char.mapInfo.chars.values():
            if getattr(ch, "cHP", 1) > 0 and not getattr(ch, "isDie", False):
                c_name = getattr(ch, "cName", "")
                norm_c = normalize_str(c_name)
                for target in self.target_bosses:
                    if target in norm_c or norm_c in target:
                        return ch, c_name

        # 2. Quét danh sách quái vật (Mob)
        for m in my_char.mapInfo.mobs.values():
            if getattr(m, "hp", 0) > 0 and getattr(m, "status", 0) not in (0, 1):
                m_name = getattr(m, "name", "")
                if m_name:
                    norm_m = normalize_str(m_name)
                    for target in self.target_bosses:
                        if target in norm_m or norm_m in target:
                            return m, m_name

        return None, ""

    def _engage_patrol_boss(self, boss_name: str, map_id: int, zone_id: int) -> None:
        """Bắt đầu chiến đấu với Boss phát hiện được trong quá trình tuần tra."""
        self.current_boss = Boss(
            name=boss_name,
            map_name=get_map_name(map_id),
            map_id=map_id,
            zone_id=zone_id,
            appear_time=time.time(),
            is_died=False,
        )
        self.status_message = f"ĐÃ TÌM THẤY BOSS '{boss_name}' tại Map {map_id} Khu {zone_id}! Bắt đầu chiến đấu!"
        self._log(self.status_message, is_important=True)
        self._change_state(self.STATE_COMBAT)

    def _find_boss_in_current_map(self, my_char: Char) -> Optional[Any]:
        """Kiểm tra sự hiện diện của nhân vật Boss trong khu hiện tại (Char hoặc Mob)."""
        if not self.current_boss:
            return None
        norm_target = normalize_str(self.current_boss.name)

        # 1. Kiểm tra danh sách người chơi/nhân vật trong map (phần lớn Boss là Char)
        for ch in my_char.mapInfo.chars.values():
            norm_c = normalize_str(getattr(ch, "cName", ""))
            if norm_target in norm_c or norm_c in norm_target:
                if getattr(ch, "cHP", 1) > 0 and not getattr(ch, "isDie", False):
                    return ch

        # 2. Kiểm tra danh sách quái vật trong map (dành cho Boss dạng Mob hoặc siêu quái)
        for m in my_char.mapInfo.mobs.values():
            if getattr(m, "hp", 0) > 0 and getattr(m, "status", 0) not in (0, 1):
                m_name = getattr(m, "name", "")
                if m_name:
                    norm_m = normalize_str(m_name)
                    if norm_target in norm_m or norm_m in norm_target:
                        return m

        return None

    def _attack_boss_like_tansat(self, my_char: Char, boss_target: Any) -> None:
        """
        Tấn công Boss như Tàn Sát (TS) với cơ chế xoay skill theo hành tinh:
        Trái Đất (9, 1, 0), Namek (12, 3, 2), Xayda (13, 5, 4).
        LƯU Ý: CHỈ ĐẤM BOSS (không đánh quái thường, không đánh người khác).
        """
        from .mob import Mob
        # 1. Ưu tiên dùng CombatManager nếu có
        cm = getattr(self.client, "combat_manager", None)
        if cm and hasattr(cm, "_select_and_attack"):
            if isinstance(boss_target, Mob):
                cm._select_and_attack(vMob=[boss_target], vChar=[])
            else:
                cm._select_and_attack(vMob=[], vChar=[boss_target])
            return

        # 2. Fallback xoay skill độc lập theo hành tinh
        gender = getattr(my_char, "cgender", 0)
        try:
            gender = int(gender)
        except Exception:
            gender = 0
        skills_by_gender = {
            0: (9, 1, 0),    # Trái Đất: kaioken, kamejoko, đấm
            1: (12, 3, 2),   # Namek: trứng, masenko, đấm
            2: (13, 5, 4),   # Xayda: hoá hình, atomic, đấm
        }
        candidates = skills_by_gender.get(gender, (0, 2, 4))
        skill_id = getattr(my_char, "skillTemplateId", 0) or candidates[-1]

        if self.client and hasattr(self.client, "service"):
            try:
                self.client.service.selectSkill(skill_id)
                my_char.skillTemplateId = skill_id
            except Exception:
                pass
            if isinstance(boss_target, Mob):
                self.client.service.sendPlayerAttack(vMob=[boss_target], vChar=[])
            else:
                self.client.service.sendPlayerAttack(vMob=[], vChar=[boss_target])

    def _on_boss_killed_event(self, boss: Boss) -> None:
        """Callback tức thời khi nhận thông báo ChatVip server báo Boss bị hạ."""
        if not self.is_enabled or not self.current_boss:
            return
        if normalize_str(self.current_boss.name) == normalize_str(boss.name):
            self.current_boss.is_died = True
            self.current_boss.killer = boss.killer
            if self.state == self.STATE_COMBAT:
                killer_str = f" bởi '{boss.killer}'" if boss.killer else ""
                self._log(f"Server thông báo: Boss '{boss.name}' đã bị tiêu diệt{killer_str}! Bắt đầu nhặt đồ...", is_important=True)
                if self.auto_loot:
                    self._change_state(self.STATE_LOOTING)
                    self.looting_start_time = time.time()
                else:
                    self.current_boss = None
                    self._change_state(self.STATE_IDLE)

    def _is_boss_alive(self, boss_target: Any) -> bool:
        """Kiểm tra xem thực thể Boss còn sống hay đã chết."""
        if boss_target is None:
            return False
        from .mob import Mob
        if isinstance(boss_target, Mob):
            return getattr(boss_target, "hp", 0) > 0 and getattr(boss_target, "status", 0) not in (0, 1)
        # Boss dạng Char: kiểm tra máu, cờ chết và status
        hp = getattr(boss_target, "cHP", 1)
        is_die = getattr(boss_target, "isDie", False)
        status_me = getattr(boss_target, "statusMe", 1)
        return hp > 0 and not is_die and status_me != 14

    def _handle_combat(self, my_char: Char) -> None:
        """
        Chiến đấu tự động với Boss:
        - Đấm như Tàn Sát (TS): xoay skill theo hành tinh, tự dùng đậu thần khi HP/KI thấp, chống chết ảo.
        - CHỈ ĐẤM BOSS: không đánh quái, không đánh người chơi khác.
        - Kiểm tra liên tục xem Boss đã chết chưa (HP <= 0, isDie, statusMe == 14 hoặc biến mất khỏi map).
        """
        if not self.current_boss:
            self._change_state(self.STATE_IDLE)
            return

        boss_target = self._find_boss_in_current_map(my_char)

        # 1. KIỂM TRA BOSS DIE:
        # Nếu Boss không còn trong map hoặc đã bị hạ (HP <= 0 / isDie / statusMe == 14)
        if boss_target is None or not self._is_boss_alive(boss_target):
            self.status_message = f"Boss '{self.current_boss.name}' đã bị tiêu diệt!"
            self._log(self.status_message, is_important=True)
            self.current_boss.is_died = True
            if self.auto_loot:
                self._log("Chuyển sang trạng thái NHẶT ĐỒ BOSS RƠI...", is_important=True)
                self._change_state(self.STATE_LOOTING)
                self.looting_start_time = time.time()
            else:
                self.current_boss = None
                self._change_state(self.STATE_IDLE)
            return

        # 2. Lưu lại toạ độ hiện tại của Boss (để khi Boss chết sẽ tele ngay vào tâm nhặt đồ)
        target_x = getattr(boss_target, "cx", getattr(boss_target, "x", my_char.cx))
        target_y = getattr(boss_target, "cy", getattr(boss_target, "y", my_char.cy))
        self.last_boss_pos = (target_x, target_y)

        # 3. Chống chết ảo và tự động dùng đậu thần duy trì thể lực như TS
        needs_hp = my_char.cHPFull > 0 and (my_char.cHP / my_char.cHPFull) < 0.35
        needs_ki = my_char.cMPFull > 0 and (my_char.cMP / my_char.cMPFull) < 0.35
        if needs_hp or needs_ki:
            if my_char.magicTree.currPeas > 0:
                if self.client and hasattr(self.client, "service"):
                    self.client.service.magicTree(2)

        # 4. Dịch chuyển tức thời áp sát Boss (Teleport)
        if self.client and hasattr(self.client, "teleport"):
            self.client.teleport(target_x, target_y)

        # 5. Khóa tiêu điểm (Focus) duy nhất vào Boss
        from .mob import Mob
        if isinstance(boss_target, Mob):
            my_char.focus_mob(boss_target)
        else:
            my_char.focus_char(boss_target)

        # 6. Tấn công Boss như TS (xoay skill theo hành tinh) nhưng CHỈ ĐẤM BOSS
        now = time.time()
        if now - self.last_attack_time >= 0.12:
            self.last_attack_time = now
            self._attack_boss_like_tansat(my_char, boss_target)

    def _handle_reviving(self, my_char: Char) -> None:
        """Hồi sinh sau khi bị đánh chết (mặc định bằng NGỌC tại chỗ) và tiếp tục săn Boss."""
        # 1. Gửi lệnh hồi sinh
        is_dead = (my_char.cHPFull > 0 and my_char.cHP <= 0) or getattr(my_char, "statusMe", 1) == 14
        if is_dead:
            if self.revive_mode == "gem":
                self.status_message = "Nhân vật đã bị Boss hạ gục! Đang tự động hồi sinh bằng NGỌC tại chỗ..."
                if self.client and hasattr(self.client, "service"):
                    self.client.service.wakeUpFromDead()
            else:
                self.status_message = "Nhân vật đã bị Boss hạ gục! Đang tự động hồi sinh về thành..."
                if self.client and hasattr(self.client, "service"):
                    self.client.service.returnTownFromDead()
            time.sleep(0.5)
            return

        # 2. Đã hồi sinh sống lại
        if my_char.cHP > 0:
            if self.current_boss and not self.current_boss.is_died:
                curr_map_id = getattr(my_char.mapInfo, "mapID", -1)
                curr_zone_id = getattr(my_char.mapInfo, "zoneID", -1)
                if curr_map_id == self.current_boss.map_id and (self.current_boss.zone_id == -1 or curr_zone_id == self.current_boss.zone_id):
                    self.status_message = f"Hồi sinh bằng ngọc thành công tại chỗ! Tiếp tục đánh Boss '{self.current_boss.name}'!"
                    self._log(self.status_message)
                    self._change_state(self.STATE_COMBAT)
                else:
                    self.status_message = f"Hồi sinh thành công! Tự động quay lại map {self.current_boss.map_id} đánh Boss '{self.current_boss.name}' tiếp!"
                    self._log(self.status_message)
                    self._change_state(self.STATE_MOVING)
            else:
                self._change_state(self.STATE_IDLE)

    def _handle_looting(self, my_char: Char) -> None:
        """
        Tự động nhặt toàn bộ vật phẩm rơi dưới đất sau khi Boss chết:
        - Teleport áp sát toạ độ Boss vừa chết
        - Quét toàn bộ vật phẩm rơi trong map (items), ưu tiên nhặt từ gần đến xa
        - Chờ tối thiểu 1.5s để server gửi gói tin item rơi
        - Tiếp tục nhặt đến khi sạch đồ rơi hoặc hết 5.0s timeout
        """
        elapsed = time.time() - self.looting_start_time

        # Bước đệm: Teleport tới toạ độ Boss vừa bị tiêu diệt
        if getattr(self, "last_boss_pos", None):
            bx, by = self.last_boss_pos
            if self.client and hasattr(self.client, "teleport"):
                self.client.teleport(bx, by)

        # Quét danh sách vật phẩm rơi trên đất trong map
        items = list(my_char.mapInfo.items.values())

        # Giai đoạn chờ và nhặt đồ rơi:
        # - Trong 0.5s đầu: chờ server đồng bộ các gói item rơi (tránh thoát nhặt đồ quá sớm)
        # - Nếu có item: tiếp tục teleport nhặt từng món cho đến khi hết (tối đa 2.0s)
        if elapsed < 0.5 or (items and elapsed < 2.0):
            if items:
                # Sắp xếp item gần nhân vật nhất để nhặt tối ưu tốc độ
                items.sort(key=lambda it: self._calc_distance(my_char.cx, my_char.cy, it.x, it.y))
                self.status_message = f"Đang nhặt đồ rơi từ Boss ({len(items)} món trên đất)..."
                for it in items:
                    if not self.is_enabled:
                        return
                    if self.client and hasattr(self.client, "teleport"):
                        self.client.teleport(it.x, it.y)
                    if self.client and hasattr(self.client, "service"):
                        self.client.service.pickItem(it.itemMapID)
                    time.sleep(0.12)
            else:
                self.status_message = "Đang chờ vật phẩm rơi từ Boss xuất hiện trên đất..."
                time.sleep(0.2)
            return

        # Hoàn tất nhặt đồ hoặc hết thời gian chờ
        self.status_message = "Đã hoàn tất nhặt đồ Boss rơi! Chuyển sang mục tiêu Boss tiếp theo."
        self._log(self.status_message)
        self.current_boss = None
        self.last_boss_pos = None
        self._change_state(self.STATE_IDLE)

    @staticmethod
    def _calc_distance(x1: int, y1: int, x2: int, y2: int) -> float:
        """Tính khoảng cách Euclidean giữa 2 toạ độ."""
        return math.hypot(x1 - x2, y1 - y2)

    def _change_state(self, new_state: str) -> None:
        """Thay đổi trạng thái máy."""
        self.state = new_state
        self.last_state_change = time.time()

    def _get_my_char(self) -> Optional[Char]:
        if self.client and hasattr(self.client, "myChar"):
            return self.client.myChar
        return Char.myCharz()

    def get_status(self) -> Dict[str, Any]:
        """Lấy toàn bộ trạng thái hoạt động của Auto Săn Boss."""
        delay_str = f"{self.min_scan_zone_delay:.2f}s - {self.max_scan_zone_delay:.2f}s (Random)" if self.min_scan_zone_delay != self.max_scan_zone_delay else f"{self.min_scan_zone_delay:.2f}s"
        curr_patrol_map = self.patrol_maps[self.patrol_map_index] if self.patrol_maps and self.patrol_map_index < len(self.patrol_maps) else -1
        return {
            "is_enabled": self.is_enabled,
            "state": self.state,
            "status_message": self.status_message,
            "current_boss": self.current_boss.to_dict() if self.current_boss else None,
            "current_boss_name": self.current_boss.name if self.current_boss else None,
            "hunt_all": self.hunt_all,
            "target_bosses": list(self.target_bosses),
            "auto_loot": self.auto_loot,
            "auto_revive": self.auto_revive,
            "revive_mode": self.revive_mode,
            "auto_patrol": self.auto_patrol,
            "auto_patrol_future": self.auto_patrol,
            "patrol_maps_count": len(self.patrol_maps),
            "patrol_map_id": curr_patrol_map,
            "patrol_map_name": get_map_name(curr_patrol_map) if curr_patrol_map != -1 else "",
            "min_scan_zone_delay": self.min_scan_zone_delay,
            "max_scan_zone_delay": self.max_scan_zone_delay,
            "scan_zone_delay_str": delay_str,
            "current_scan_zone": self.current_scan_zone,
            "scanned_zones": list(self.scanned_zones),
            "scanned_zones_count": len(self.scanned_zones),
        }
