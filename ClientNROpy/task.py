# -*- coding: utf-8 -*-
"""
Mô hình Task mô phỏng Task.cs trong C#.
Lưu trữ thông tin nhiệm vụ chính tuyến của nhân vật.
"""

from typing import List, Optional


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
    def current_sub_name(self) -> str:
        """Tên của bước nhiệm vụ phụ hiện tại."""
        if 0 <= self.index < len(self.subNames):
            return self.subNames[self.index]
        return ""

    @property
    def current_map_id(self) -> Optional[int]:
        """ID Map cần đến cho bước hiện tại nếu có."""
        if 0 <= self.index < len(self.mapTasks):
            return self.mapTasks[self.index]
        return None

    def __repr__(self) -> str:
        return (f"<Task ID={self.taskId} Index={self.index} "
                f"Count={self.count} Name='{self.name}'>")
