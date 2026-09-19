# -*- coding: utf-8 -*-
"""
Cấu hình tài khoản (AccountConfig) cho ClientNROpy.
Đại diện cho thông tin cấu hình đọc từ file accounts.json / settings.
"""

from typing import Optional, List, Dict, Any


class AccountConfig:
    """Cấu hình cho một tài khoản game."""

    def __init__(
        self,
        acc_id: int,
        username: str,
        password: str,
        host: Optional[str] = None,
        port: Optional[int] = None,
        version: Optional[str] = None,
        proxy: Optional[str] = None,
        auto_tasks: Optional[List[str]] = None,
        enabled: bool = True,
        auto_reconnect: bool = True,
    ):
        self.acc_id: int = acc_id
        self.username: str = username
        self.password: str = password
        self.host: Optional[str] = host
        self.port: Optional[int] = port
        self.version: Optional[str] = version
        self.proxy: Optional[str] = proxy
        self.auto_tasks: List[str] = [t for t in (auto_tasks or []) if t and t.strip()]
        self.enabled: bool = enabled
        self.auto_reconnect: bool = auto_reconnect

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "username": self.username,
            "password": self.password,
            "enabled": self.enabled,
            "auto_reconnect": self.auto_reconnect,
        }
        if self.proxy:
            d["proxy"] = self.proxy
        if self.auto_tasks:
            d["auto"] = self.auto_tasks
        if self.host:
            d["host"] = self.host
        if self.port:
            d["port"] = self.port
        if self.version:
            d["version"] = self.version
        return d
