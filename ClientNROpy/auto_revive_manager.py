# -*- coding: utf-8 -*-
"""
Bộ quản lý tự động hồi sinh nhân vật (Auto Revive Manager).
Mặc định kích hoạt tự động hồi sinh tại chỗ bằng ngọc (cmd -16) ngay khi nhân vật bị hạ gục.
Cung cấp khả năng chuyển đổi linh hoạt giữa hồi sinh bằng ngọc và hồi sinh về thành.
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import time
import threading
from typing import Optional, Dict, Any


class AutoReviveManager:
    """Tự động phát hiện khi nhân vật chết và gửi lệnh hồi sinh (mặc định bằng ngọc)."""

    MODE_GEM: str = "gem"    # Hồi sinh tại chỗ bằng 1 ngọc (cmd -16)
    MODE_TOWN: str = "town"  # Hồi sinh về nhà / làng miễn phí (cmd -15)

    def __init__(self, client=None):
        self.client = client
        # Yêu cầu: Mặc định tính năng Auto Hồi Sinh là BẬT
        self.is_enabled: bool = True
        self.mode: str = self.MODE_GEM  # Mặc định là hồi sinh bằng ngọc
        self.delay_before_revive: float = 0.5  # Chờ 0.5s sau khi chết để trạng thái ổn định
        self.cooldown_seconds: float = 2.0     # Khoảng cách tối thiểu giữa 2 lần gửi lệnh hồi sinh
        self.revive_count: int = 0
        self.last_revive_time: float = 0.0

        # Quản lý luồng nền
        self._is_stopped: bool = False
        self._thread: Optional[threading.Thread] = None
        self._start_thread()

    def _start_thread(self) -> None:
        """Khởi động luồng nền giám sát trạng thái sống / chết của nhân vật."""
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="AutoReviveThread",
            )
            self._thread.start()

    def _log(self, msg: str, is_alert: bool = False) -> None:
        from .logger import logger
        tag = getattr(self.client, "account_id", "AutoRevive") if self.client else "AutoRevive"
        if is_alert:
            logger.alert(msg, account_tag=tag)
        else:
            logger.auto(msg, account_tag=tag)

    def enable(self) -> None:
        """Bật tính năng Auto Hồi Sinh."""
        self.is_enabled = True
        mode_str = "bằng Ngọc tại chỗ (cmd -16)" if self.mode == self.MODE_GEM else "về Thành (cmd -15)"
        self._log(f"[AutoRevive] Auto Hồi Sinh: BẬT [{mode_str}]!")

    def disable(self) -> None:
        """Tắt tính năng Auto Hồi Sinh."""
        self.is_enabled = False
        self._log(f"[AutoRevive] Auto Hồi Sinh: TẮT!")

    def toggle(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt tính năng Auto Hồi Sinh."""
        if enable is not None:
            self.is_enabled = enable
        else:
            self.is_enabled = not self.is_enabled

        if self.is_enabled:
            mode_str = "bằng Ngọc tại chỗ" if self.mode == self.MODE_GEM else "về Thành"
            self._log(f"[AutoRevive] Auto Hồi Sinh: BẬT [{mode_str}]!")
        else:
            self._log("[AutoRevive] Auto Hồi Sinh: TẮT!")
        return self.is_enabled

    def set_mode(self, mode: str) -> bool:
        """
        Cài đặt phương thức hồi sinh:
        :param mode: 'gem' (ngọc tại chỗ) hoặc 'town' (về nhà/làng).
        """
        m = mode.lower().strip()
        if m in ("gem", "ngoc", "place", "here", "1"):
            self.mode = self.MODE_GEM
            self._log("[AutoRevive] Đã chuyển chế độ: Hồi sinh bằng Ngọc tại chỗ (cmd -16)!")
            return True
        elif m in ("town", "ve", "thanh", "nha", "home", "0"):
            self.mode = self.MODE_TOWN
            self._log("[AutoRevive] Đã chuyển chế độ: Hồi sinh về Thành / Nhà (cmd -15)!")
            return True
        return False

    def is_char_dead(self) -> bool:
        """Kiểm tra nhân vật có đang trong trạng thái chết hay không."""
        if not self.client or not hasattr(self.client, "myChar") or not self.client.myChar:
            return False
        c = self.client.myChar
        is_hp_zero = (c.cHPFull > 0 and c.cHP <= 0)
        is_die_flag = getattr(c, "isDie", False)
        is_status_die = (getattr(c, "statusMe", 1) == 14)
        return is_hp_zero or is_die_flag or is_status_die

    def revive(self) -> None:
        """Thực hiện lệnh gửi hồi sinh lên server."""
        if not self.client or not hasattr(self.client, "service"):
            return

        self.revive_count += 1
        self.last_revive_time = time.time()

        if self.mode == self.MODE_GEM:
            self._log(
                f"[AutoRevive] Nhân vật đã bị hạ gục! "
                f"Tự động hồi sinh tại chỗ bằng 1 Ngọc (cmd -16) [lần #{self.revive_count}]...",
                is_alert=True,
            )
            self.client.service.wakeUpFromDead()
        else:
            self._log(
                f"[AutoRevive] Nhân vật đã bị hạ gục! "
                f"Tự động hồi sinh về Thành (cmd -15) [lần #{self.revive_count}]...",
                is_alert=True,
            )
            self.client.service.returnTownFromDead()

    def _worker_loop(self) -> None:
        """Vòng lặp kiểm tra trạng thái nhân vật liên tục."""
        while not self._is_stopped:
            try:
                if self.is_enabled:
                    # Chỉ kiểm tra khi client đã kết nối vào game
                    if self.client and hasattr(self.client, "isConnected") and self.client.isConnected():
                        if self.is_char_dead():
                            now = time.time()
                            # Tránh spam gói tin hồi sinh liên tục
                            if (now - self.last_revive_time) >= self.cooldown_seconds:
                                # Chờ nhẹ để server đồng bộ trạng thái
                                if self.delay_before_revive > 0:
                                    time.sleep(self.delay_before_revive)
                                if self.is_char_dead():
                                    self._execute_revive()

                time.sleep(0.3)
            except Exception:
                time.sleep(1.0)

    def get_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái Auto Hồi Sinh."""
        mode_str = "Ngọc tại chỗ (1 ngọc)" if self.mode == self.MODE_GEM else "Về thành / Làng (miễn phí)"
        return {
            "is_enabled": self.is_enabled,
            "mode": self.mode,
            "mode_str": mode_str,
            "revive_count": self.revive_count,
            "is_currently_dead": self.is_char_dead(),
        }
