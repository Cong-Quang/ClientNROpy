# -*- coding: utf-8 -*-
"""
Hệ thống Console Logger trung tâm cho ClientNROpy.
Cung cấp khả năng lọc kênh log, gán tiền tố tài khoản [Acc X: Tên],
ngăn chặn spam console (mặc định ẩn chat map và raw network),
hỗ trợ bật/tắt toàn cục hoặc theo từng danh mục.
"""

import os
import sys
import time
import threading
from typing import Optional, Dict, Any


class LogLevel:
    DEBUG = 10
    INFO = 20
    WARN = 30
    ERROR = 40
    SILENT = 50

    @classmethod
    def from_str(cls, s: str) -> int:
        s = s.strip().upper()
        if s in ("DEBUG", "DBG"):
            return cls.DEBUG
        if s in ("INFO", "INF"):
            return cls.INFO
        if s in ("WARN", "WARNING"):
            return cls.WARN
        if s in ("ERROR", "ERR"):
            return cls.ERROR
        if s in ("SILENT", "MUTE", "OFF", "NONE"):
            return cls.SILENT
        return cls.INFO


class ConsoleLogger:
    """Quản lý in ấn và lọc log ra màn hình console mượt mà, không giật màn hình."""

    def __init__(self):
        self.muted: bool = False
        self.level: int = LogLevel.INFO
        self._lock = threading.Lock()
        self._current_prompt: str = ""
        self._ansi_supported: bool = self._init_ansi()
        self._recent_logs: Dict[str, float] = {}

        # Cấu hình bật/tắt từng kênh thông tin
        # Mặc định: Ẩn chat map và raw packet để màn hình luôn sạch
        self.channels: Dict[str, bool] = {
            "boss": True,      # Thông báo Boss xuất hiện / bị hạ
            "system": True,    # Kết nối, đăng nhập, nạp dữ liệu, đổi khu
            "alert": True,     # Cảnh báo chết, kẹt, hết đậu
            "auto": False,     # Tiến độ săn Boss, tuần tra, di chuyển Xmap (MẶC ĐỊNH TẮT để console sạch sẽ)
            "chat": False,     # Chat map của người chơi khác (MẶC ĐỊNH TẮT)
            "network": False,  # Debug gói tin, linkDefault, server waiting (MẶC ĐỊNH TẮT)
        }

    def _init_ansi(self) -> bool:
        """Kích hoạt hỗ trợ ANSI / VT100 trên Windows terminal để xóa dòng và redraw mượt mà."""
        if sys.platform != "win32":
            return True
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            hOut = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_ulong()
            if kernel32.GetConsoleMode(hOut, ctypes.byref(mode)):
                kernel32.SetConsoleMode(hOut, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                return True
        except Exception:
            pass
        return os.environ.get("TERM") is not None or "WT_SESSION" in os.environ

    def set_prompt(self, prompt: str) -> None:
        """Đăng ký nhãn prompt hiện tại của bàn phím để khi có log nền, không làm gãy prompt."""
        with self._lock:
            self._current_prompt = prompt

    def clear_prompt(self) -> None:
        """Hủy đăng ký prompt khi kết thúc lệnh hoặc thoát nhập liệu."""
        with self._lock:
            self._current_prompt = ""

    def set_muted(self, muted: bool) -> None:
        """Bật/tắt toàn bộ log nền."""
        self.muted = muted

    def set_level(self, level: int) -> None:
        self.level = level

    def set_channel(self, channel: str, enabled: bool) -> bool:
        ch = channel.lower().strip()
        if ch in self.channels:
            self.channels[ch] = enabled
            return True
        return False

    def is_channel_enabled(self, channel: str) -> bool:
        if self.muted:
            return False
        ch = channel.lower().strip()
        return self.channels.get(ch, True)

    def log(
        self,
        msg: str,
        channel: str = "system",
        level: int = LogLevel.INFO,
        account_tag: Optional[str] = None,
    ) -> None:
        """Ghi log có kiểm tra bộ lọc kênh, chống spam trùng lặp và giữ ổn định prompt."""
        if self.muted or level < self.level:
            return

        ch = channel.lower().strip()
        if not self.channels.get(ch, True):
            return

        # Bộ lọc flood: Chống lặp đúng 1 nội dung trong vòng 3 giây
        now_ts = time.time()
        cache_key = f"{account_tag}:{ch}:{msg}"
        last_ts = self._recent_logs.get(cache_key, 0.0)
        if now_ts - last_ts < 3.0:
            return
        self._recent_logs[cache_key] = now_ts
        if len(self._recent_logs) > 300:
            self._recent_logs = {k: v for k, v in self._recent_logs.items() if now_ts - v < 15.0}

        now_str = time.strftime("%H:%M:%S")
        tag_str = f"[{account_tag}] " if account_tag else ""
        ch_str = f"[{ch.upper()}] " if ch != "system" else ""

        line = f"[{now_str}] {tag_str}{ch_str}{msg}"

        with self._lock:
            try:
                if self._current_prompt:
                    # Nếu người dùng đang ở dòng lệnh:
                    # Xóa dòng prompt, in log hoàn chỉnh, sau đó vẽ lại prompt ngay bên dưới
                    if self._ansi_supported:
                        sys.stdout.write(f"\r\x1b[2K{line}\n{self._current_prompt}")
                    else:
                        pad = " " * max(len(self._current_prompt), 30)
                        sys.stdout.write(f"\r{pad}\r{line}\n{self._current_prompt}")
                    sys.stdout.flush()
                else:
                    print(line, flush=True)
            except Exception:
                pass

    def boss(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="boss", level=LogLevel.INFO, account_tag=account_tag)

    def system(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="system", level=LogLevel.INFO, account_tag=account_tag)

    def alert(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="alert", level=LogLevel.WARN, account_tag=account_tag)

    def auto(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="auto", level=LogLevel.INFO, account_tag=account_tag)

    def chat(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="chat", level=LogLevel.INFO, account_tag=account_tag)

    def warn(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="system", level=LogLevel.WARN, account_tag=account_tag)

    def error(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="system", level=LogLevel.ERROR, account_tag=account_tag)

    def debug(self, msg: str, account_tag: Optional[str] = None) -> None:
        self.log(msg, channel="network", level=LogLevel.DEBUG, account_tag=account_tag)


# Singleton logger toàn cục
logger = ConsoleLogger()
