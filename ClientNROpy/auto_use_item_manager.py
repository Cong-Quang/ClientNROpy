# -*- coding: utf-8 -*-
"""
Bộ quản lý tự động sử dụng vật phẩm theo chu kỳ thời gian (Auto Use Item Manager).
Cho phép tự động dùng một item nhiều lần trong khoảng thời gian nhất định (tính bằng phút).
Nếu hết item hoặc không tìm thấy trong balo, hệ thống sẽ cảnh báo ra console.
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import time
import threading
from typing import Optional, Dict, Any, Tuple


class AutoUseItemManager:
    """Quản lý việc tự động sử dụng một vật phẩm trong hành trang balo theo chu kỳ thời gian."""

    def __init__(self, client=None):
        self.client = client
        self.item_template_id: Optional[int] = None
        self.interval_minutes: float = 10.0
        self.is_enabled: bool = False
        self.use_count: int = 0
        self.last_use_time: float = 0.0
        self.last_alert_time: float = 0.0

        # Quản lý luồng nền
        self._is_stopped: bool = False
        self._thread: Optional[threading.Thread] = None
        self._start_thread()

    def _start_thread(self) -> None:
        """Khởi động luồng nền kiểm tra chu kỳ dùng item."""
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(
                target=self._worker_loop,
                daemon=True,
                name="AutoUseItemThread",
            )
            self._thread.start()

    def start_auto(self, item_id: int, interval_minutes: float) -> Tuple[bool, str]:
        """
        Bắt đầu tự động sử dụng item theo chu kỳ.
        :param item_id: Template ID của vật phẩm cần dùng.
        :param interval_minutes: Chu kỳ sử dụng tính bằng phút (có thể là số thực, vd 0.5 = 30s).
        """
        if item_id <= 0:
            return False, "Template ID của vật phẩm phải là số nguyên dương!"

        if interval_minutes <= 0:
            return False, "Thời gian chu kỳ phải lớn hơn 0 phút!"

        self.item_template_id = item_id
        self.interval_minutes = interval_minutes
        self.is_enabled = True
        self.use_count = 0
        self.last_use_time = 0.0  # Đặt về 0 để sử dụng ngay lập tức lần đầu
        self.last_alert_time = 0.0

        # Kiểm tra trước xem có item trong balo không
        item_in_bag = self._find_item_in_bag(item_id)
        if item_in_bag is None:
            print(f"[!] [AutoUseItem] CẢNH BÁO: Hiện không tìm thấy vật phẩm Template ID {item_id} trong hành trang Balo!")
            return True, (
                f"Đã bật Auto dùng item ID {item_id} mỗi {interval_minutes:g} phút "
                f"(Lưu ý: Chưa thấy có item trong balo, hệ thống sẽ tự động dùng khi có)!"
            )

        return True, (
            f"Đã kích hoạt Auto dùng item ID {item_id} mỗi {interval_minutes:g} phút "
            f"(Hiện có x{item_in_bag.quantity} trong Balo)!"
        )

    def stop(self) -> Tuple[bool, str]:
        """Dừng tính năng tự động dùng item."""
        if not self.is_enabled:
            return False, "Auto dùng item hiện đang tắt!"
        self.is_enabled = False
        msg = f"Đã dừng Auto dùng item ID {self.item_template_id} (Tổng cộng đã dùng {self.use_count} lần)."
        return True, msg

    def toggle(self, item_id: Optional[int] = None, interval_minutes: Optional[float] = None) -> Tuple[bool, str]:
        """Bật / Tắt tính năng tự động dùng item."""
        if self.is_enabled:
            return self.stop()
        if item_id is not None and interval_minutes is not None:
            return self.start_auto(item_id, interval_minutes)
        if self.item_template_id is not None:
            return self.start_auto(self.item_template_id, self.interval_minutes)
        return False, "Chưa thiết lập item ID và thời gian! Cú pháp: useitem <id> <phút>"

    def _find_item_in_bag(self, item_id: int):
        """Tìm vật phẩm theo template_id trong arrItemBag của myChar."""
        if not self.client or not hasattr(self.client, "myChar") or not self.client.myChar:
            return None
        bag = getattr(self.client.myChar, "arrItemBag", [])
        for it in bag:
            if it is not None and getattr(it, "template_id", -1) == item_id:
                return it
        return None

    def execute_now(self) -> Tuple[bool, str]:
        """Cưỡng chế sử dụng item ngay lập tức một lần."""
        if self.item_template_id is None:
            return False, "Chưa chỉ định Template ID của vật phẩm!"

        item = self._find_item_in_bag(self.item_template_id)
        if item is None:
            msg = f"[!] [AutoUseItem] Không tìm thấy vật phẩm Template ID {self.item_template_id} trong hành trang Balo hoặc đã hết!"
            print(msg)
            return False, msg

        if not self.client or not hasattr(self.client, "service"):
            return False, "Client chưa sẵn sàng gửi gói tin (service không tồn tại)!"

        # Gửi gói tin useItem (type=0, where=1: Balo, index_ui, template_id)
        self.client.service.useItem(0, 1, item.index_ui, item.template_id)
        self.use_count += 1
        self.last_use_time = time.time()
        msg = (
            f"[*] [AutoUseItem] Đã sử dụng item ID {self.item_template_id} "
            f"(Số lượng còn: x{item.quantity}, slot {item.index_ui}). Lần dùng: #{self.use_count}."
        )
        print(msg)
        return True, msg

    def _worker_loop(self) -> None:
        """Vòng lặp chạy nền kiểm tra thời gian dùng item."""
        while not self._is_stopped:
            try:
                if self.is_enabled and self.item_template_id is not None:
                    # Kiểm tra kết nối client
                    if self.client and hasattr(self.client, "isConnected") and self.client.isConnected():
                        now = time.time()
                        interval_sec = self.interval_minutes * 60.0

                        # Dùng ngay lần đầu hoặc khi đã hết thời gian chu kỳ
                        if self.last_use_time == 0.0 or (now - self.last_use_time) >= interval_sec:
                            item = self._find_item_in_bag(self.item_template_id)
                            if item is not None:
                                self.client.service.useItem(0, 1, item.index_ui, item.template_id)
                                self.use_count += 1
                                self.last_use_time = now
                                print(
                                    f"[*] [AutoUseItem] Đã sử dụng item ID {self.item_template_id} "
                                    f"(Số lượng còn: x{item.quantity}, slot {item.index_ui}). "
                                    f"Lần dùng: #{self.use_count}. Lần tiếp theo sau {self.interval_minutes:g} phút."
                                )
                            else:
                                # Nếu hết hoặc không có trong balo -> thông báo cảnh báo ra console
                                if (now - self.last_alert_time) >= 15.0:  # Không spam liên tục mỗi giây
                                    print(
                                        f"[!] [AutoUseItem] CẢNH BÁO: Không tìm thấy vật phẩm Template ID "
                                        f"{self.item_template_id} trong hành trang Balo hoặc đã hết số lượng!"
                                    )
                                    self.last_alert_time = now

                time.sleep(1.0)
            except Exception as ex:
                time.sleep(2.0)

    def get_status(self) -> Dict[str, Any]:
        """Lấy thông tin trạng thái hiện tại."""
        remaining_seconds = 0.0
        if self.is_enabled and self.last_use_time > 0.0:
            elapsed = time.time() - self.last_use_time
            remaining_seconds = max(0.0, (self.interval_minutes * 60.0) - elapsed)

        item = self._find_item_in_bag(self.item_template_id) if self.item_template_id else None
        item_qty = getattr(item, "quantity", 0) if item else 0

        return {
            "is_enabled": self.is_enabled,
            "item_template_id": self.item_template_id,
            "interval_minutes": self.interval_minutes,
            "use_count": self.use_count,
            "has_item_in_bag": item is not None,
            "quantity_in_bag": item_qty,
            "remaining_seconds": remaining_seconds,
            "remaining_time_str": f"{int(remaining_seconds // 60)}m{int(remaining_seconds % 60)}s" if remaining_seconds > 0 else "Ngay bây giờ",
        }
