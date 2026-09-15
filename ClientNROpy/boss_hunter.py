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
import threading
from typing import Optional, List, Set, Dict, Any, Union

from .boss import Boss
from .char import Char
from .xmap.map_data import normalize_str


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

    def __init__(self, client=None):
        self.client = client

        # Cấu hình tính năng
        self.is_enabled: bool = False
        self.hunt_all: bool = True                    # Săn tất cả các Boss
        self.target_bosses: Set[str] = set()          # Danh sách Boss muốn săn (chuỗi chuẩn hoá)
        self.auto_loot: bool = True                   # Tự động nhặt đồ sau khi Boss chết
        self.auto_revive: bool = True                 # Tự động hồi sinh và quay lại đánh tiếp
        self.scan_zone_delay: float = 0.35            # Thời gian dừng ở mỗi khu để dò boss (giây)
        self.max_zones_scan: int = 30                 # Số khu tối đa sẽ dò trong 1 map

        # Trạng thái thực thi
        self.state: str = self.STATE_IDLE
        self.current_boss: Optional[Boss] = None
        self.current_scan_zone: int = 0
        self.scanned_zones: Set[int] = set()
        self.last_state_change: float = time.time()
        self.looting_start_time: float = 0.0
        self.last_attack_time: float = 0.0
        self.status_message: str = "Đang chờ lệnh hoặc thông báo Boss mới..."

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
        self.status_message = "Đã kích hoạt Auto Săn Boss!"
        print(f"[*] {self.status_message}")

    def stop(self) -> None:
        """Dừng tính năng Auto Săn Boss."""
        self.is_enabled = False
        self.state = self.STATE_IDLE
        self.current_boss = None
        self.status_message = "Đã dừng Auto Săn Boss."
        if self.client and hasattr(self.client, "xmap_stop"):
            self.client.xmap_stop()
        print(f"[*] {self.status_message}")

    def toggle(self) -> bool:
        """Bật / Tắt tính năng Auto Săn Boss."""
        if self.is_enabled:
            self.stop()
        else:
            self.start()
        return self.is_enabled

    def add_target(self, boss_name: str) -> None:
        """Thêm một Boss vào danh sách muốn săn."""
        norm = normalize_str(boss_name)
        if norm:
            self.target_bosses.add(norm)
            self.hunt_all = False

    def remove_target(self, boss_name: str) -> None:
        """Xóa một Boss khỏi danh sách muốn săn."""
        norm = normalize_str(boss_name)
        if norm in self.target_bosses:
            self.target_bosses.remove(norm)
        if not self.target_bosses:
            self.hunt_all = True

    def clear_targets(self) -> None:
        """Xóa danh sách cấu hình Boss (chuyển sang săn tất cả)."""
        self.target_bosses.clear()
        self.hunt_all = True

    def is_target_boss(self, boss: Boss) -> bool:
        """Kiểm tra Boss có thuộc đối tượng cần săn hay không."""
        if self.hunt_all or not self.target_bosses:
            return True
        norm_b = normalize_str(boss.name)
        return any(t in norm_b or norm_b in t for t in self.target_bosses)

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
                    print(f"[BossHunter] worker error: {ex}")
            time.sleep(0.15)

    def _step(self) -> None:
        """Thực thi 1 bước trong máy trạng thái."""
        my_char = self._get_my_char()
        if my_char is None:
            return

        # Kiểm tra nhân vật bị chết ở bất kỳ trạng thái nào
        if my_char.cHP <= 0 or getattr(my_char, "statusMe", 1) == 14:
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
                    print(f"[*] {self.status_message}")
                    self.current_boss = None
                    self._change_state(self.STATE_IDLE)
                    return

        # 3. Trạng thái CHỜ / CHỌN BOSS (IDLE)
        if self.state == self.STATE_IDLE:
            self._handle_idle()
            return

        # 4. Trạng thái DI CHUYỂN TỚI MAP (MOVING)
        if self.state == self.STATE_MOVING:
            self._handle_moving(my_char)
            return

        # 5. Trạng thái DÒ KHU VỰC TÌM BOSS (SCANNING)
        if self.state == self.STATE_SCANNING:
            self._handle_scanning(my_char)
            return

        # 6. Trạng thái TẤN CÔNG BOSS (COMBAT)
        if self.state == self.STATE_COMBAT:
            self._handle_combat(my_char)
            return

        # 7. Trạng thái NHẶT ĐỒ SAU KHI BOSS CHẾT (LOOTING)
        if self.state == self.STATE_LOOTING:
            self._handle_looting(my_char)
            return

    # --------------------------------------------------------------------------
    # XỬ LÝ TỪNG TRẠNG THÁI
    # --------------------------------------------------------------------------
    def _handle_idle(self) -> None:
        """Tìm và chọn mục tiêu Boss tiếp theo."""
        next_boss = self._select_next_boss()
        if next_boss is not None:
            self.current_boss = next_boss
            self.scanned_zones.clear()
            self.status_message = f"Phát hiện mục tiêu: '{next_boss.name}' tại '{next_boss.map_name}' [{next_boss.map_id}]. Bắt đầu di chuyển!"
            print(f"[*] {self.status_message}")
            self._change_state(self.STATE_MOVING)
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
            print(f"[*] {self.status_message}")
            self._change_state(self.STATE_SCANNING)
            return

        # Chưa tới map -> Kích hoạt Xmap
        if self.client and hasattr(self.client, "xmap"):
            xmap_st = self.client.xmap_status()
            if not xmap_st.get("is_acting", False):
                self.status_message = f"Đang Xmap tới map {self.current_boss.map_id} của Boss '{self.current_boss.name}'..."
                self.client.xmap(self.current_boss.map_id)

    def _handle_scanning(self, my_char: Char) -> None:
        """Dò qua từng khu vực để phát hiện Boss."""
        if not self.current_boss:
            self._change_state(self.STATE_IDLE)
            return

        # 1. Quét xem Boss có trong khu vực hiện tại hay không
        boss_char = self._find_boss_in_current_map(my_char)
        if boss_char is not None:
            curr_zone = getattr(my_char.mapInfo, "zoneID", -1)
            self.current_boss.zone_id = curr_zone
            self.status_message = f"ĐÃ TÌM THẤY BOSS '{self.current_boss.name}' tại Khu {curr_zone}! Bắt đầu chiến đấu!"
            print(f"[!] >>> {self.status_message}")
            self._change_state(self.STATE_COMBAT)
            return

        # 2. Nếu Boss có zone_id đã biết và chưa thử zone đó -> Thử zone đó trước
        if self.current_boss.zone_id != -1 and self.current_boss.zone_id not in self.scanned_zones:
            target_zone = self.current_boss.zone_id
            self.scanned_zones.add(target_zone)
            self.status_message = f"Đang vào Khu {target_zone} theo thông báo Boss..."
            if self.client and hasattr(self.client, "change_zone"):
                self.client.change_zone(target_zone)
            time.sleep(self.scan_zone_delay)
            return

        # 3. Lấy danh sách khu vực trong map
        available_zones = []
        if my_char.mapInfo.zones:
            available_zones = [z.zoneId for z in my_char.mapInfo.zones]
        else:
            available_zones = list(range(self.max_zones_scan))

        # Tìm khu tiếp theo chưa quét
        unscanned = [z for z in available_zones if z not in self.scanned_zones]
        if not unscanned:
            # Đã quét toàn bộ khu trong map mà không thấy Boss -> Boss đã bị hạ hoặc biến mất
            self.status_message = f"Đã quét toàn bộ khu map {self.current_boss.map_id} không thấy Boss '{self.current_boss.name}'. Đánh dấu Boss đã chết!"
            print(f"[*] {self.status_message}")
            self.current_boss.is_died = True
            self.current_boss = None
            self._change_state(self.STATE_IDLE)
            return

        next_zone = unscanned[0]
        self.scanned_zones.add(next_zone)
        self.status_message = f"Đang dò Boss tại Khu {next_zone} (Đã kiểm tra {len(self.scanned_zones)} khu)..."
        if self.client and hasattr(self.client, "change_zone"):
            self.client.change_zone(next_zone)
        time.sleep(self.scan_zone_delay)

    def _find_boss_in_current_map(self, my_char: Char) -> Optional[Char]:
        """Kiểm tra sự hiện diện của nhân vật Boss trong khu hiện tại."""
        if not self.current_boss:
            return None
        norm_target = normalize_str(self.current_boss.name)

        # Kiểm tra danh sách người chơi/nhân vật trong map
        for ch in my_char.mapInfo.chars.values():
            norm_c = normalize_str(getattr(ch, "cName", ""))
            if norm_target in norm_c or norm_c in norm_target:
                if getattr(ch, "cHP", 1) > 0 and not getattr(ch, "isDie", False):
                    return ch

        return None

    def _handle_combat(self, my_char: Char) -> None:
        """Chiến đấu tự động với Boss: Teleport áp sát, khóa tiêu điểm, gửi lệnh đánh."""
        if not self.current_boss:
            self._change_state(self.STATE_IDLE)
            return

        boss_char = self._find_boss_in_current_map(my_char)

        # Nếu không còn thấy Boss trong map
        if boss_char is None:
            self.status_message = f"Boss '{self.current_boss.name}' đã bị tiêu diệt hoặc rời khỏi khu!"
            print(f"[*] {self.status_message}")
            self.current_boss.is_died = True
            if self.auto_loot:
                self._change_state(self.STATE_LOOTING)
                self.looting_start_time = time.time()
            else:
                self.current_boss = None
                self._change_state(self.STATE_IDLE)
            return

        # 1. Teleport tức thời áp sát Boss
        if self.client and hasattr(self.client, "teleport"):
            self.client.teleport(boss_char.cx, boss_char.cy)

        # 2. Khóa tiêu điểm vào Boss
        my_char.focus_char(boss_char)

        # 3. Gửi lệnh tấn công Boss
        now = time.time()
        if now - self.last_attack_time >= 0.12:
            self.last_attack_time = now
            if self.client and hasattr(self.client, "service"):
                self.client.service.sendPlayerAttack(vMob=[], vChar=[boss_char])

        # 4. Tự động dùng đậu thần duy trì thể lực khi đánh Boss
        if my_char.cHPFull > 0 and (my_char.cHP / my_char.cHPFull) < 0.35:
            if my_char.magicTree.currPeas > 0:
                if self.client and hasattr(self.client, "service"):
                    self.client.service.magicTree(2)

    def _handle_reviving(self, my_char: Char) -> None:
        """Hồi sinh sau khi bị đánh chết và tự động quay lại map Boss."""
        # 1. Gửi lệnh hồi sinh về thành
        if my_char.cHP <= 0 or getattr(my_char, "statusMe", 1) == 14:
            self.status_message = "Nhân vật đã bị Boss hạ gục! Đang tự động hồi sinh về thành..."
            if self.client and hasattr(self.client, "service"):
                self.client.service.returnTownFromDead()
            time.sleep(1.0)
            return

        # 2. Đã hồi sinh sống lại
        if my_char.cHP > 0:
            if self.current_boss and not self.current_boss.is_died:
                self.status_message = f"Hồi sinh thành công! Tự động quay lại map {self.current_boss.map_id} đánh Boss '{self.current_boss.name}' tiếp!"
                print(f"[*] {self.status_message}")
                self._change_state(self.STATE_MOVING)
            else:
                self._change_state(self.STATE_IDLE)

    def _handle_looting(self, my_char: Char) -> None:
        """Tự động nhặt các vật phẩm rơi dưới đất sau khi Boss chết."""
        elapsed = time.time() - self.looting_start_time

        # Quét vật phẩm trong map
        items = list(my_char.mapInfo.items.values())
        if items and elapsed < 2.5:
            self.status_message = f"Đang nhặt đồ rơi từ Boss ({len(items)} vật phẩm)..."
            for it in items:
                if self.client and hasattr(self.client, "teleport"):
                    self.client.teleport(it.x, it.y)
                if self.client and hasattr(self.client, "service"):
                    self.client.service.pickItem(it.itemMapID)
                time.sleep(0.12)
            return

        # Hoàn tất nhặt đồ hoặc hết thời gian chờ
        self.status_message = "Đã nhặt xong đồ rơi! Chuyển sang mục tiêu Boss tiếp theo."
        print(f"[*] {self.status_message}")
        self.current_boss = None
        self._change_state(self.STATE_IDLE)

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
            "scanned_zones_count": len(self.scanned_zones),
        }
