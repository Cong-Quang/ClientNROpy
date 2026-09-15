# -*- coding: utf-8 -*-
"""
Mô hình ChatVip - Tin nhắn VIP, thông báo Boss và chat thế giới (cmd 93).
Mô phỏng Assets.src.e.ChatVip.cs và Mod.Boss.cs trong C#.
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import re
import time
from typing import Optional, List


class ChatVip:
    """
    Thông tin tin nhắn ChatVip / Thông báo Boss từ máy chủ (cmd 93).
    Tự động phân tích các mẫu thông báo Boss xuất hiện và Boss bị tiêu diệt:
    - 'BOSS [Tên Boss] vừa xuất hiện tại [Bản đồ] khu vực [Khu]'
    - '[Người chơi] : Đã tiêu diệt được [Tên Boss] mọi người đều ngưỡng mộ.'
    """

    # Các từ khóa thông báo boss xuất hiện (Mod/Boss.cs)
    STR_APPEARED = [" vừa xuất hiện tại ", " appear at ", " muncul di "]
    STR_ZONE = [" khu vực ", " zone ", " zona "]

    # Các từ khóa thông báo boss bị hạ gục (Mod/Boss.cs)
    STR_KILLED = [
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

    def __init__(
        self,
        text: str = "",
        is_boss: bool = False,
        boss_name: str = "",
        map_name: str = "",
        zone_id: int = -1,
        is_killed: bool = False,
        killer: str = "",
    ):
        self.text: str = text
        self.is_boss: bool = is_boss
        self.boss_name: str = boss_name
        self.map_name: str = map_name
        self.zone_id: int = zone_id
        self.is_killed: bool = is_killed
        self.killer: str = killer
        self.timestamp: float = time.time()

    @classmethod
    def parse(cls, raw_text: str) -> "ChatVip":
        """Phân tích chuỗi tin nhắn ChatVip nhận được từ server."""
        cleaned = raw_text.strip()
        # Nếu bắt đầu bằng dấu '!' (tin nhắn hiệu ứng pháo hoa)
        if cleaned.startswith("!"):
            cleaned = cleaned[1:].strip()

        obj = cls(text=cleaned)

        # 1. Kiểm tra Boss bị tiêu diệt
        if any(k in cleaned for k in cls.STR_KILLED):
            obj.is_boss = True
            obj.is_killed = True
            # Mẫu chuẩn: "TênPlayer : Đã tiêu diệt được TênBoss mọi người đều ngưỡng mộ."
            match_kill = re.search(r"^(.*?)\s*:\s*(?:Đã tiêu diệt được|defeated|mengalahkan)\s*(.*?)(?:\s+mọi người.*|\.|$)", cleaned, re.IGNORECASE)
            if match_kill:
                obj.killer = match_kill.group(1).strip()
                b_name = match_kill.group(2).strip()
                if b_name.upper().startswith("BOSS "):
                    b_name = b_name[5:].strip()
                obj.boss_name = b_name
            return obj

        # 2. Kiểm tra Boss xuất hiện
        is_appear = any(app in cleaned for app in cls.STR_APPEARED) or cleaned.upper().startswith("BOSS ")
        if is_appear:
            obj.is_boss = True
            obj.is_killed = False
            # Mẫu chuẩn: "BOSS [Tên Boss] vừa xuất hiện tại [Tên Map] khu vực [Khu]"
            pattern = r"(?:BOSS\s+)?(.*?)\s+(?:vừa xuất hiện tại|appear at|muncul di)\s+(.*?)(?:\s+(?:khu vực|zone|zona)\s+(\d+))?$"
            match_app = re.search(pattern, cleaned, re.IGNORECASE)
            if match_app:
                obj.boss_name = match_app.group(1).strip()
                obj.map_name = match_app.group(2).strip()
                if match_app.group(3):
                    try:
                        obj.zone_id = int(match_app.group(3))
                    except ValueError:
                        obj.zone_id = -1
            else:
                # Nếu không khớp regex đầy đủ nhưng bắt đầu bằng BOSS
                if cleaned.upper().startswith("BOSS "):
                    obj.boss_name = cleaned[5:].strip()

        return obj

    def __repr__(self) -> str:
        if self.is_boss:
            if self.is_killed:
                return f"<ChatVip [BOSS DIED] '{self.boss_name}' hạ bởi '{self.killer}'>"
            zone_str = f" Khu {self.zone_id}" if self.zone_id >= 0 else ""
            map_str = f" tại '{self.map_name}'" if self.map_name else ""
            return f"<ChatVip [BOSS SPAWN] '{self.boss_name}'{map_str}{zone_str}>"
        return f"<ChatVip '{self.text}'>"
