# -*- coding: utf-8 -*-
"""
Mô hình dữ liệu Boss - Mô phỏng theo Mod/Boss.cs trong Dragonboy C#.
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import time
from typing import Optional, Dict, Any


class Boss:
    """
    Thực thể biểu diễn một Boss trong game.
    Quản lý tên Boss, map xuất hiện, khu vực, thời gian sống,
    trạng thái sống/chết và người chơi tiêu diệt.
    """

    def __init__(
        self,
        name: str = "",
        map_name: str = "",
        map_id: int = -1,
        zone_id: int = -1,
        appear_time: Optional[float] = None,
        is_died: bool = False,
        killer: str = "",
    ):
        self.name: str = name.strip()
        self.map_name: str = map_name.strip()
        self.map_id: int = map_id
        self.zone_id: int = zone_id
        self.appear_time: float = appear_time if appear_time is not None else time.time()
        self.is_died: bool = is_died
        self.killer: str = killer.strip()

    @property
    def time_alive_seconds(self) -> int:
        """Tổng số giây đã trôi qua kể từ khi Boss xuất hiện."""
        elapsed = int(time.time() - self.appear_time)
        return max(0, elapsed)

    def time_alive_str(self) -> str:
        """
        Định dạng thời gian sống theo chuẩn Mod/Boss.cs:
        {hours}h{minutes}m{seconds}s
        Ví dụ: '12s', '3m45s', '1h15m20s'
        """
        secs = self.time_alive_seconds
        hours = secs // 3600
        minutes = (secs % 3600) // 60
        seconds = secs % 60

        result = ""
        if hours > 0:
            result += f"{hours}h"
        if minutes > 0:
            result += f"{minutes}m"
        result += f"{seconds}s"
        return result

    def to_string(
        self,
        use_color: bool = False,
        current_map_id: int = -1,
        current_zone_id: int = -1,
    ) -> str:
        """
        Định dạng chuỗi thông tin Boss tương tự Boss.ToString() trong C#.
        Hỗ trợ định dạng ANSI màu sắc cho terminal nếu use_color=True.
        """
        # Xác định hiển thị map
        if not self.map_name:
            map_str = "chưa biết"
        else:
            map_str = f"{self.map_name} [{self.map_id}]"

        # Trạng thái sống / chết
        if not self.is_died:
            zone_part = f"Khu {self.zone_id} - " if self.zone_id > -1 else ""
            status_str = f"[CÒN SỐNG] {zone_part}{self.time_alive_str()}"
        else:
            if self.killer:
                status_str = f"[ĐÃ CHẾT] Bị {self.killer} tiêu diệt"
            else:
                status_str = "[ĐÃ CHẾT]"

        if not use_color:
            return f"{self.name} - {map_str} - {status_str}"

        # Định dạng màu sắc ANSI
        RESET = "\033[0m"
        if self.is_died:
            GRAY = "\033[90m"
            RED = "\033[91m"
            killer_colored = f"{RED}{self.killer}{GRAY}" if self.killer else ""
            kill_info = f"Bị {killer_colored} tiêu diệt" if self.killer else "Đã chết"
            return f"{RED}[ĐÃ CHẾT]{RESET} {GRAY}{self.name} - {map_str} - {kill_info}{RESET}"

        # Đang còn sống
        is_same_map = current_map_id == self.map_id and self.map_id != -1
        is_same_zone = is_same_map and current_zone_id == self.zone_id and self.zone_id != -1

        YELLOW = "\033[93m"
        CYAN = "\033[96m"
        GREEN = "\033[92m"
        RED = "\033[91m"
        ORANGE = "\033[33m"

        name_color = RED if is_same_zone else (ORANGE if is_same_map else YELLOW)
        map_color = RED if is_same_map else CYAN

        zone_part = ""
        if self.zone_id > -1:
            if is_same_zone:
                zone_part = f"{RED}Khu {self.zone_id}{RESET} - "
            elif is_same_map:
                zone_part = f"{YELLOW}Khu {self.zone_id}{RESET} - "
            else:
                zone_part = f"Khu {YELLOW}{self.zone_id}{RESET} - "

        time_part = f"{GREEN}{self.time_alive_str()}{RESET}"

        return (
            f"{GREEN}[CÒN SỐNG]{RESET} "
            f"{name_color}{self.name}{RESET} - "
            f"{map_color}{map_str}{RESET} - "
            f"{zone_part}{time_part}"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Chuyển đổi thông tin Boss thành dictionary."""
        return {
            "name": self.name,
            "map_name": self.map_name,
            "map_id": self.map_id,
            "zone_id": self.zone_id,
            "appear_time": self.appear_time,
            "time_alive_str": self.time_alive_str(),
            "time_alive_seconds": self.time_alive_seconds,
            "is_died": self.is_died,
            "killer": self.killer,
        }

    def __repr__(self) -> str:
        return f"<Boss {self.to_string()}>"

    def __str__(self) -> str:
        return self.to_string()
