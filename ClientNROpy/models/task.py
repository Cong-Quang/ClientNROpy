# -*- coding: utf-8 -*-
"""
Mô hình Task mô phỏng Task.cs trong C#.
Lưu trữ thông tin nhiệm vụ chính tuyến của nhân vật.
"""

from typing import List, Optional
import re


def clean_task_name(raw_name: str) -> str:
    """
    Làm sạch tên nhiệm vụ, loại bỏ các banner quảng cáo / nạp tiền / cấp VIP
    của các máy chủ lậu (như ThanhDi.com) để lấy đúng tên nhiệm vụ thật.
    """
    if not raw_name:
        return ""
    lines = [l.strip() for l in raw_name.replace("\r", "").split("\n") if l.strip()]
    if not lines:
        return ""

    # 1. Tìm dòng chứa 'nhiệm vụ' hoặc 'nv:' từ dưới lên
    task_line = next((l for l in reversed(lines) if any(k in l.lower() for k in ["nhiệm vụ", "nv:"])), None)
    if task_line:
        cleaned = re.sub(r"(?i)^.*?(?:nhiệm\s*vụ|nv)[^\:\-]*[:\uFF1A\-]\s*", "", task_line).strip()
        if cleaned:
            return cleaned
        return task_line

    # 2. Nếu không tìm thấy, lọc bỏ các dòng chứa từ khóa quảng cáo phổ biến
    spam_kw = (
        "đăng nhập", "thanhdi", "cấp vip", "coin", "thẻ tháng", "quy lão",
        "___", "---", "===", "nạp", "hn khóa", "st chuẩn", "zalo", "discord", "http"
    )
    filtered = [l for l in lines if not any(w in l.lower() for w in spam_kw)]
    candidate = filtered[-1] if filtered else lines[-1]
    candidate = re.sub(r"(?i)^.*?(?:nhiệm\s*vụ|nv)[^\:\-]*[:\uFF1A\-]\s*", "", candidate).strip()
    return candidate


class Task:
    """
    Thông tin nhiệm vụ chính tuyến (Char.myCharz().taskMaint).
    """

    def __init__(
        self,
        task_id: int = 0,
        index: int = 0,
        name: str = "",
        detail: str = "",
        sub_names: Optional[List[str]] = None,
        counts: Optional[List[int]] = None,
        count: int = 0,
        content_info: Optional[List[str]] = None,
        map_tasks: Optional[List[int]] = None,
        task_types: Optional[List[int]] = None,
    ):
        self.taskId: int = task_id
        self.index: int = index
        self.name: str = name
        self.detail: str = detail
        self.subNames: List[str] = sub_names or []
        self.counts: List[int] = counts or []
        self.count: int = count
        self.contentInfo: List[str] = content_info or []
        self.mapTasks: List[int] = map_tasks or []
        self.taskTypes: List[int] = task_types or []

        # Alias mảng dòng mô tả theo phong cách C#
        self.names: List[str] = [name] if name else []
        self.details: List[str] = [detail] if detail else []

    @property
    def clean_name(self) -> str:
        """Tên nhiệm vụ đã được làm sạch, loại bỏ banner quảng cáo."""
        return clean_task_name(self.name)

    @property
    def current_sub_name(self) -> str:
        """Tên của bước nhiệm vụ phụ hiện tại."""
        if 0 <= self.index < len(self.subNames):
            return self.subNames[self.index]
        return ""

    @property
    def progress_str(self) -> str:
        """Mục tiêu và tiến độ hiện tại (ví dụ: 'Tiêu diệt Xuka (0/5)')."""
        if not (0 <= self.index < len(self.subNames)):
            return ""
        sub = self.subNames[self.index].strip()
        if sub.startswith("-"):
            sub = sub.lstrip("-").strip()

        has_bracket = bool(re.search(r"\(\s*\d+\s*/\s*\d+\s*\)", sub))
        if not has_bracket:
            max_c = self.counts[self.index] if (0 <= self.index < len(self.counts)) else 0
            if max_c > 0:
                cur_c = max(0, self.count) if self.count != -1 else 0
                sub = f"{sub} ({cur_c}/{max_c})" if sub else f"({cur_c}/{max_c})"
        return sub

    @property
    def full_display(self) -> str:
        """Chuỗi hiển thị hoàn chỉnh gồm tên nhiệm vụ và tiến độ hiện tại."""
        c_name = self.clean_name
        prog = self.progress_str
        if c_name and prog:
            return f"{c_name} | Tiến độ: {prog}"
        return c_name or prog or f"Task ID {self.taskId}"

    @property
    def current_map_id(self) -> Optional[int]:
        """ID Map cần đến cho bước hiện tại nếu có."""
        if 0 <= self.index < len(self.mapTasks):
            return self.mapTasks[self.index]
        return None

    def __repr__(self) -> str:
        return (f"<Task ID={self.taskId} Index={self.index} "
                f"Count={self.count} Name='{self.clean_name}'>")
