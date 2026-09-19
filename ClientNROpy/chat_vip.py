# -*- coding: utf-8 -*-
"""
Mô hình ChatVip - Tin nhắn VIP, thông báo hệ thống và chat thế giới (cmd 93).
Mô phỏng Assets.src.e.ChatVip.cs trong Dragonboy C#.
Toàn bộ logic bóc tách, theo dõi và quản lý Boss đã được tách riêng vào boss.py và boss_manager.py.
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import time
from typing import Optional, Any


class ChatVip:
    """
    Thông tin tin nhắn ChatVip nhận được từ server (cmd 93).
    Mô phỏng Assets.src.e.ChatVip trong bản mod Dragonboy.
    """

    def __init__(
        self,
        text: str = "",
        width: int = 0,
        x: int = 0,
        timestamp: Optional[float] = None,
        boss: Optional[Any] = None,
    ):
        self.text: str = text.strip()
        self.chat: str = self.text  # Thuộc tính tương thích ChatVip.chat trong C#
        self.width: int = width
        self.x: int = x
        self.timestamp: float = timestamp if timestamp is not None else time.time()
        self.boss = boss

    # --------------------------------------------------------------------------
    # Các thuộc tính tiện ích ủy quyền từ thực thể Boss (nếu là thông báo Boss)
    # --------------------------------------------------------------------------
    @property
    def is_boss(self) -> bool:
        """Kiểm tra tin nhắn này có phải thông báo về Boss hay không."""
        return self.boss is not None

    @property
    def is_killed(self) -> bool:
        """Kiểm tra Boss có phải vừa bị tiêu diệt hay không."""
        return self.boss.is_died if self.boss else False

    @property
    def boss_name(self) -> str:
        """Tên của Boss."""
        return self.boss.name if self.boss else ""

    @property
    def map_name(self) -> str:
        """Tên map nơi Boss xuất hiện."""
        return self.boss.map_name if self.boss else ""

    @property
    def map_id(self) -> int:
        """Mã ID bản đồ nơi Boss xuất hiện."""
        return self.boss.map_id if self.boss else -1

    @property
    def zone_id(self) -> int:
        """Khu vực của Boss (-1 nếu chưa rõ)."""
        return self.boss.zone_id if self.boss else -1

    @property
    def killer(self) -> str:
        """Tên người chơi tiêu diệt Boss."""
        return self.boss.killer if self.boss else ""

    @classmethod
    def parse(cls, raw_text: str) -> "ChatVip":
        """
        Bóc tách gói tin ChatVip nhận được từ server.
        Tự động ủy quyền nhận diện Boss sang BossManager.
        """
        cleaned = raw_text.strip()
        display_text = cleaned[1:].strip() if cleaned.startswith("!") else cleaned

        # Ủy quyền cho BossManager bóc tách thông tin Boss (bọc try-except phòng thủ)
        boss = None
        try:
            from .boss_manager import BossManager
            boss = BossManager.parse_boss_announcement(cleaned)
        except Exception:
            boss = None

        return cls(text=display_text, boss=boss)

    def __repr__(self) -> str:
        if self.is_boss:
            if self.is_killed:
                return f"<ChatVip [BOSS DIED] '{self.boss_name}' hạ bởi '{self.killer}'>"
            zone_str = f" Khu {self.zone_id}" if self.zone_id >= 0 else ""
            map_str = f" tại '{self.map_name}'" if self.map_name else ""
            return f"<ChatVip [BOSS SPAWN] '{self.boss_name}'{map_str}{zone_str}>"
        return f"<ChatVip '{self.text}'>"
