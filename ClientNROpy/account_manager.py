# -*- coding: utf-8 -*-
"""
Trình quản lý đa tài khoản (AccountManager) cho ClientNROpy.
Quản lý danh sách tài khoản, đọc/ghi file cấu hình accounts.json,
phân bổ proxy tự động từ ProxyPool, điều phối khởi động theo luồng,
và chuyển tiếp lệnh điều khiển tới từng tài khoản hoặc toàn bộ tài khoản cùng lúc.
"""

import os
import json
import time
import threading
from typing import Optional, List, Dict, Any, Tuple, Union, Callable

from .client import ClientNRO
from .proxy_manager import ProxyPool, ProxyConfig, parse_proxy
from .logger import logger
from .char import Char
from .chat_vip import ChatVip


DEFAULT_CONFIG_PATH = "accounts.json"

DEFAULT_SETTINGS = {
    "use_proxy": False,
    "accounts_per_proxy": 4,
    "auto_reconnect": True,
    "reconnect_delay": 10,
    "max_reconnect_attempts": 0,
    "default_server": {
        "host": "51.79.163.109",
        "port": 12457,
        "version": "2.1.4",
    },
}


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
        self.auto_tasks: List[str] = auto_tasks or []
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


class AccountInstance:
    """Đối tượng runtime đại diện cho 1 tài khoản đang hoạt động."""

    def __init__(self, config: AccountConfig, proxy: Optional[ProxyConfig] = None):
        self.config: AccountConfig = config
        self.assigned_proxy: Optional[ProxyConfig] = proxy
        self.client: Optional[ClientNRO] = None
        self.status: str = "OFFLINE"
        self.last_error: Optional[str] = None
        self.login_time: float = 0.0
        self._thread: Optional[threading.Thread] = None
        self.is_manual_stopping: bool = False
        self.reconnect_count: int = 0
        self.reconnect_timer_end: float = 0.0
        self._reconnect_thread: Optional[threading.Thread] = None
        self._reconnect_cancel_event: threading.Event = threading.Event()
        self.saved_auto_tasks: List[str] = list(config.auto_tasks)

    def snapshot_active_autos(self) -> None:
        """Lưu lại các tác vụ auto đang chạy trước khi mất kết nối."""
        if not self.client:
            return
        active = []
        if getattr(self.client.boss_hunter, "is_enabled", False):
            active.append("hunt")
        if getattr(self.client.auto_quest, "is_running", False):
            active.append("nvbm")
        if getattr(self.client.combat_manager, "is_ak", False):
            active.append("ak")
        if getattr(self.client.combat_manager, "is_tansat", False):
            active.append("ts")
        if getattr(self.client.shuttle_manager, "is_running", False):
            active.append("shuttle")
        if getattr(self.client.auto_revive_manager, "is_enabled", False):
            active.append("autohs")
        if active:
            merged = list(set(self.saved_auto_tasks + active))
            self.saved_auto_tasks = merged

    def restore_active_autos(self) -> None:
        """Khôi phục lại các tác vụ auto sau khi kết nối lại thành công."""
        if not self.client:
            return
        tasks = list(self.saved_auto_tasks) if self.saved_auto_tasks else list(self.config.auto_tasks)
        restored = []
        if "hunt" in tasks:
            self.client.start_auto_hunt()
            restored.append("Hunt")
        if "nvbm" in tasks:
            self.client.start_auto_quest()
            restored.append("NVBM")
        if "ak" in tasks:
            self.client.combat_manager.start_ak()
            restored.append("AK")
        if "ts" in tasks:
            self.client.combat_manager.start_tansat()
            restored.append("TS")
        if "autohs" in tasks:
            self.client.auto_revive_manager.enable()
            restored.append("AutoHS")
        if restored:
            from .logger import logger
            logger.system(f"Đã tự động kích hoạt tác vụ: {', '.join(restored)}", account_tag=self.tag)

    @property
    def tag(self) -> str:
        name = self.char_name if self.char_name != "Chưa vào" else self.config.username
        return f"Acc {self.config.acc_id}:{name}"

    @property
    def char_name(self) -> str:
        if self.client and self.client.myChar and self.client.myChar.cName:
            return self.client.myChar.cName
        return "Chưa vào"

    @property
    def hp_str(self) -> str:
        if self.client and self.client.myChar:
            c = self.client.myChar
            if c.cHPFull > 0:
                return f"{c.cHP:,}/{c.cHPFull:,}"
        return "N/A"

    @property
    def power_str(self) -> str:
        if self.client and self.client.myChar:
            return f"{self.client.myChar.cPower:,}"
        return "N/A"

    @property
    def map_zone_str(self) -> str:
        if self.client and self.client.myChar and self.client.myChar.mapInfo:
            m = self.client.myChar.mapInfo
            if m.mapID >= 0:
                return f"Map {m.mapID} (Khu {m.zoneID})"
        return "Chưa rõ"

    @property
    def proxy_str(self) -> str:
        if self.assigned_proxy:
            return self.assigned_proxy.display_str
        return "Trực tiếp"

    @property
    def auto_status_str(self) -> str:
        if not self.client:
            return "N/A"
        active = []
        if getattr(self.client.boss_hunter, "is_enabled", False):
            active.append("Hunt")
        if getattr(self.client.auto_quest, "is_running", False):
            active.append("NVBM")
        if getattr(self.client.combat_manager, "is_ak", False):
            active.append("AK")
        if getattr(self.client.combat_manager, "is_tansat", False):
            active.append("TS")
        if getattr(self.client.shuttle_manager, "is_running", False):
            active.append("Shuttle")
        return ", ".join(active) if active else "None"


DEFAULT_SETTINGS_PATHS = ["settings.json", "setting.json", "setting.js"]
DEFAULT_ACCOUNTS_PATHS = ["accounts.json", "account.json"]


class AccountManager:
    """Quản lý danh sách các tài khoản và phân bổ mạng."""

    def __init__(self, config_file: str = "accounts.json", settings_file: str = "settings.json"):
        self.config_file: str = config_file
        self.settings_file: str = settings_file
        self.proxy_pool: ProxyPool = ProxyPool(use_proxy=False, accounts_per_proxy=4)
        self.default_server: Dict[str, Any] = dict(DEFAULT_SETTINGS["default_server"])
        self.auto_reconnect: bool = DEFAULT_SETTINGS["auto_reconnect"]
        self.reconnect_delay: float = float(DEFAULT_SETTINGS["reconnect_delay"])
        self.max_reconnect_attempts: int = int(DEFAULT_SETTINGS["max_reconnect_attempts"])

        # Cấu hình Telegram & OpenRouter AI
        self.telegram_config: Dict[str, Any] = {
            "enabled": True,
            "token": "8850708704:AAFg-R7uIx3rZ44jPvHCs8wAAeEssvcO-xo",
            "allowed_chat_ids": [],
            "notify_boss": True,
            "notify_disconnect": True,
            "notify_login": True,
        }
        self.ai_config: Dict[str, Any] = {
            "enabled": True,
            "api_key": "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",
            "model": "openrouter/free",
            "system_prompt": "",
        }
        self.telegram_bot = None

        self.accounts: List[AccountInstance] = []
        self._lock = threading.Lock()
        self._last_server_messages: Dict[str, float] = {}

    def load_settings(self, filepath: Optional[str] = None) -> bool:
        """Đọc cấu hình hệ thống từ settings.json (hoặc setting.json)."""
        target_path = None
        if filepath and os.path.exists(filepath):
            target_path = filepath
        else:
            for p in DEFAULT_SETTINGS_PATHS:
                if os.path.exists(p):
                    target_path = p
                    break

        if not target_path:
            target_path = "settings.json"
            self._create_sample_settings(target_path)

        self.settings_file = target_path
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Cài đặt chung / proxy / reconnect
            gen = data.get("general") or data.get("settings") or {}
            use_proxy = gen.get("use_proxy", False)
            accs_per_proxy = gen.get("accounts_per_proxy", 4)
            self.proxy_pool.set_use_proxy(use_proxy)
            self.proxy_pool.set_accounts_per_proxy(accs_per_proxy)

            self.auto_reconnect = gen.get("auto_reconnect", True)
            self.reconnect_delay = float(gen.get("reconnect_delay", 10))
            self.max_reconnect_attempts = int(gen.get("max_reconnect_attempts", 0))

            srv = gen.get("default_server", {})
            if srv:
                self.default_server.update(srv)

            # Nạp proxies
            self.proxy_pool.clear()
            raw_proxies = data.get("proxies", [])
            for p_str in raw_proxies:
                self.proxy_pool.add_proxy(p_str)

            # Nạp Telegram config
            if "telegram" in data:
                self.telegram_config.update(data["telegram"])

            # Nạp AI config
            if "ai" in data:
                self.ai_config.update(data["ai"])

            rec_str = f"BẬT ({int(self.reconnect_delay)}s)" if self.auto_reconnect else "TẮT"
            tg_str = f"BẬT" if self.telegram_config.get("enabled") else "TẮT"
            logger.system(
                f"Đã nạp cài đặt từ '{target_path}'. "
                f"Proxy: {'BẬT' if use_proxy else 'TẮT'} ({len(self.proxy_pool)} proxy) | "
                f"Auto-Reconnect: {rec_str} | Telegram: {tg_str}."
            )
            return True
        except Exception as ex:
            logger.error(f"Lỗi khi đọc file cài đặt '{target_path}': {ex}")
            return False

    def load_accounts(self, filepath: Optional[str] = None) -> bool:
        """Đọc danh sách tài khoản thuần túy từ accounts.json."""
        target_path = None
        if filepath and os.path.exists(filepath):
            target_path = filepath
        else:
            for p in DEFAULT_ACCOUNTS_PATHS:
                if os.path.exists(p):
                    target_path = p
                    break

        if not target_path:
            target_path = "accounts.json"
            self._create_sample_accounts(target_path)

        self.config_file = target_path
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            raw_accs = []
            if isinstance(data, list):
                raw_accs = data
            elif isinstance(data, dict):
                raw_accs = data.get("accounts", [])
                # Tương thích ngược: nếu file cũ chứa cả settings thì nạp nếu settings chưa nạp
                if "settings" in data and not self.proxy_pool.proxies:
                    old_settings = data.get("settings", {})
                    self.proxy_pool.set_use_proxy(old_settings.get("use_proxy", False))
                    for p in data.get("proxies", []):
                        self.proxy_pool.add_proxy(p)

            with self._lock:
                self.accounts.clear()
                for idx, a_data in enumerate(raw_accs):
                    u = a_data.get("username", "").strip()
                    p = a_data.get("password", "").strip()
                    if not u or not p:
                        continue
                    enabled = a_data.get("enabled", True)
                    custom_proxy = a_data.get("proxy")
                    auto = a_data.get("auto", [])
                    host = a_data.get("host")
                    port = a_data.get("port")
                    ver = a_data.get("version")
                    auto_rec = a_data.get("auto_reconnect", self.auto_reconnect)

                    cfg = AccountConfig(
                        acc_id=idx + 1,
                        username=u,
                        password=p,
                        host=host,
                        port=port,
                        version=ver,
                        proxy=custom_proxy,
                        auto_tasks=auto,
                        enabled=enabled,
                        auto_reconnect=auto_rec,
                    )
                    assigned_proxy = self.proxy_pool.get_proxy_for_account(idx, custom_proxy)
                    self.accounts.append(AccountInstance(cfg, assigned_proxy))

            logger.system(f"Đã nạp {len(self.accounts)} tài khoản từ '{target_path}'.")
            return True
        except Exception as ex:
            logger.error(f"Lỗi khi đọc file tài khoản '{target_path}': {ex}")
            return False

    def load_config(self, filepath: Optional[str] = None) -> bool:
        """Nạp cả cài đặt settings.json và danh sách accounts.json."""
        self.load_settings()
        return self.load_accounts(filepath)

    def _create_sample_settings(self, path: str) -> None:
        """Tạo file settings.json mẫu chứa cấu hình server, proxy, autoreconnect, telegram, ai."""
        sample_data = {
            "_huong_dan": "Cấu hình hệ thống ClientNROpy: proxy, autoreconnect, telegram bot, openrouter ai.",
            "general": {
                "use_proxy": False,
                "accounts_per_proxy": 4,
                "auto_reconnect": True,
                "reconnect_delay": 10,
                "max_reconnect_attempts": 0,
                "default_server": {
                    "host": "51.79.163.109",
                    "port": 12457,
                    "version": "2.1.4",
                },
            },
            "proxies": [
                "socks5://user:pass@1.2.3.4:1080",
                "103.152.112.5:8080:user:pass",
            ],
            "telegram": {
                "enabled": True,
                "token": "8850708704:AAFg-R7uIx3rZ44jPvHCs8wAAeEssvcO-xo",
                "allowed_chat_ids": [],
                "notify_boss": True,
                "notify_disconnect": True,
                "notify_login": True,
            },
            "ai": {
                "enabled": True,
                "api_key": "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",
                "model": "openrouter/free",
                "system_prompt": (
                    "Bạn là trợ lý AI thông minh quản lý và điều khiển tài khoản Ngọc Rồng Online (ClientNRO). "
                    "Hãy trả lời ngắn gọn, thân thiện bằng Tiếng Việt. Bạn được cung cấp trạng thái game thực tế của các tài khoản. "
                    "Nếu người dùng yêu cầu thực hiện hành động trong game, hãy chèn thẻ lệnh [EXEC: <lệnh>] ở cuối câu trả lời. "
                    "Ví dụ: [EXEC: all hunt on] hoặc [EXEC: acc 1 xmap 0]."
                ),
            },
        }
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sample_data, f, indent=2, ensure_ascii=False)
            logger.system(f"Đã tạo file cấu hình cài đặt mẫu: {path}")
        except Exception as ex:
            logger.error(f"Không thể tạo file mẫu '{path}': {ex}")

    def _create_sample_accounts(self, path: str) -> None:
        """Tạo file accounts.json mẫu chỉ chứa danh sách tài khoản."""
        sample_data = [
            {
                "username": "poopooi01",
                "password": "02082003",
                "enabled": True,
                "auto_reconnect": True,
                "proxy": None,
                "auto": ["hunt"],
            },
            {
                "username": "poopooi02",
                "password": "02082003",
                "enabled": True,
                "auto_reconnect": True,
                "proxy": None,
                "auto": ["hunt"],
            },
        ]
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(sample_data, f, indent=2, ensure_ascii=False)
            logger.system(f"Đã tạo file danh sách tài khoản mẫu: {path}")
        except Exception as ex:
            logger.error(f"Không thể tạo file mẫu '{path}': {ex}")

    def add_account_direct(
        self,
        username: str,
        password: str,
        proxy: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        version: Optional[str] = None,
    ) -> AccountInstance:
        """Thêm nhanh một tài khoản từ dòng lệnh mà không bắt buộc dùng file json."""
        with self._lock:
            idx = len(self.accounts)
            cfg = AccountConfig(
                acc_id=idx + 1,
                username=username,
                password=password,
                host=host,
                port=port,
                version=version,
                proxy=proxy,
            )
            assigned_proxy = self.proxy_pool.get_proxy_for_account(idx, proxy)
            inst = AccountInstance(cfg, assigned_proxy)
            self.accounts.append(inst)
            return inst

    def save_accounts_file(self, filepath: Optional[str] = None) -> bool:
        """Lưu danh sách tài khoản hiện tại ra file accounts.json."""
        target_path = filepath or self.config_file or "accounts.json"
        try:
            with self._lock:
                data = []
                for inst in self.accounts:
                    data.append({
                        "username": inst.config.username,
                        "password": inst.config.password,
                        "enabled": inst.config.enabled,
                        "auto_reconnect": inst.config.auto_reconnect,
                        "proxy": inst.config.proxy,
                        "auto": inst.config.auto_tasks or ["hunt"],
                    })
            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.system(f"Đã lưu danh sách {len(data)} tài khoản vào '{target_path}'.")
            return True
        except Exception as ex:
            logger.error(f"Lỗi khi lưu '{target_path}': {ex}")
            return False

    def save_settings_file(self, filepath: Optional[str] = None) -> bool:
        """Lưu cấu hình hệ thống ra settings.json."""
        target_path = filepath or self.settings_file or "settings.json"
        try:
            old_data = {}
            if os.path.exists(target_path):
                try:
                    with open(target_path, "r", encoding="utf-8") as f:
                        old_data = json.load(f)
                except Exception:
                    old_data = {}

            if "general" not in old_data:
                old_data["general"] = {}
            old_data["general"]["use_proxy"] = self.proxy_pool.use_proxy
            old_data["general"]["accounts_per_proxy"] = self.proxy_pool.accounts_per_proxy
            old_data["general"]["auto_reconnect"] = self.auto_reconnect
            old_data["general"]["reconnect_delay"] = self.reconnect_delay
            old_data["general"]["max_reconnect_attempts"] = self.max_reconnect_attempts
            old_data["general"]["default_server"] = self.default_server

            old_data["proxies"] = self.proxy_pool.get_raw_proxies_list()
            old_data["telegram"] = self.telegram_config
            old_data["ai"] = self.ai_config

            with open(target_path, "w", encoding="utf-8") as f:
                json.dump(old_data, f, indent=2, ensure_ascii=False)
            logger.system(f"Đã cập nhật cài đặt vào '{target_path}'.")
            return True
        except Exception as ex:
            logger.error(f"Lỗi khi lưu '{target_path}': {ex}")
            return False

    def add_account_and_save(
        self,
        username: str,
        password: str,
        proxy: Optional[str] = None,
        auto_tasks: Optional[List[str]] = None,
        start_now: bool = True,
    ) -> Tuple[bool, str, Optional[AccountInstance]]:
        """Thêm tài khoản mới, lưu vào accounts.json và tuỳ chọn kết nối ngay."""
        u_clean = username.strip()
        p_clean = password.strip()
        if not u_clean or not p_clean:
            return False, "Username và mật khẩu không được để trống!", None

        with self._lock:
            for a in self.accounts:
                if a.config.username.lower() == u_clean.lower():
                    return False, f"Tài khoản '{u_clean}' đã tồn tại trong danh sách!", None

            idx = len(self.accounts)
            cfg = AccountConfig(
                acc_id=idx + 1,
                username=u_clean,
                password=p_clean,
                proxy=proxy.strip() if proxy else None,
                auto_tasks=auto_tasks if auto_tasks is not None else ["hunt"],
                enabled=True,
                auto_reconnect=self.auto_reconnect,
            )
            assigned_proxy = self.proxy_pool.get_proxy_for_account(idx, cfg.proxy)
            inst = AccountInstance(cfg, assigned_proxy)
            self.accounts.append(inst)

        self.save_accounts_file()

        if start_now:
            t = threading.Thread(target=self.start_account, args=(inst,), daemon=True)
            t.start()

        return True, f"Đã thêm tài khoản '{u_clean}' thành công (Acc #{cfg.acc_id})!", inst

    def remove_account_and_save(self, identifier: Union[int, str]) -> Tuple[bool, str]:
        """Dừng và xoá một tài khoản khỏi danh sách và lưu vào accounts.json."""
        target_inst = self.get_account(identifier)
        if not target_inst:
            return False, f"Không tìm thấy tài khoản '{identifier}'!"

        self.stop_account(target_inst)

        with self._lock:
            if target_inst in self.accounts:
                self.accounts.remove(target_inst)

            for i, a in enumerate(self.accounts):
                a.config.acc_id = i + 1

        self.save_accounts_file()
        return True, f"Đã xoá tài khoản '{target_inst.config.username}' thành công!"

    def edit_account_and_save(
        self,
        identifier: Union[int, str],
        new_password: Optional[str] = None,
        new_proxy: Optional[str] = None,
        enabled: Optional[bool] = None,
    ) -> Tuple[bool, str]:
        """Cập nhật thông tin tài khoản và lưu lại vào accounts.json."""
        target_inst = self.get_account(identifier)
        if not target_inst:
            return False, f"Không tìm thấy tài khoản '{identifier}'!"

        with self._lock:
            if new_password:
                target_inst.config.password = new_password.strip()
            if new_proxy is not None:
                prx_clean = new_proxy.strip()
                if prx_clean.lower() in ("none", "null", "no", "0", "off", "direct"):
                    target_inst.config.proxy = None
                else:
                    target_inst.config.proxy = prx_clean
                target_inst.assigned_proxy = self.proxy_pool.get_proxy_for_account(
                    target_inst.config.acc_id - 1, target_inst.config.proxy
                )
            if enabled is not None:
                target_inst.config.enabled = enabled

        self.save_accounts_file()
        return True, f"Đã cập nhật tài khoản '{target_inst.config.username}' thành công!"

    def add_proxy_and_save(self, proxy_str: str) -> Tuple[bool, str]:
        """Thêm một proxy vào pool và lưu vào settings.json."""
        p_clean = proxy_str.strip()
        if not p_clean:
            return False, "Chuỗi proxy không được để trống!"

        cfg = self.proxy_pool.add_proxy(p_clean)
        if not cfg:
            return False, f"Định dạng proxy không hợp lệ: '{proxy_str}'!"

        self.save_settings_file()
        return True, f"Đã thêm Proxy thành công: {cfg.display_str}"

    def remove_proxy_and_save(self, identifier: Union[int, str]) -> Tuple[bool, str]:
        """Xoá proxy khỏi danh sách và lưu settings.json."""
        ok = self.proxy_pool.remove_proxy(identifier)
        if ok:
            self.save_settings_file()
            return True, f"Đã xoá Proxy '{identifier}' thành công!"
        return False, f"Không tìm thấy Proxy '{identifier}'!"

    def set_use_proxy_and_save(self, enable: bool) -> Tuple[bool, str]:
        """Bật/Tắt chế độ chạy Proxy và lưu settings.json."""
        self.proxy_pool.set_use_proxy(enable)
        self.save_settings_file()
        return True, f"Đã {'BẬT' if enable else 'TẮT'} chế độ Proxy!"

    def get_account(self, identifier: Union[int, str]) -> Optional[AccountInstance]:
        """
        Tìm tài khoản theo STT (1, 2, 3...) hoặc username hoặc tên nhân vật.
        """
        with self._lock:
            if isinstance(identifier, int):
                for a in self.accounts:
                    if a.config.acc_id == identifier:
                        return a
                return None

            s = str(identifier).strip().lower()
            if s.isdigit():
                num = int(s)
                for a in self.accounts:
                    if a.config.acc_id == num:
                        return a
                return None

            # Tìm theo username hoặc char_name
            for a in self.accounts:
                if a.config.username.lower() == s:
                    return a
                if a.char_name and a.char_name.lower() == s:
                    return a
            return None

    def start_account(self, inst: AccountInstance) -> bool:
        """Khởi động và kết nối một tài khoản."""
        if inst.client and inst.client.isConnected():
            logger.warn(f"Tài khoản '{inst.config.username}' đã kết nối trước đó!", account_tag=inst.tag)
            return True

        host = inst.config.host or self.default_server["host"]
        port = inst.config.port or self.default_server["port"]
        ver = inst.config.version or self.default_server["version"]

        proxy_str = inst.assigned_proxy.raw_str if inst.assigned_proxy else None

        inst.is_manual_stopping = False
        inst.status = "CONNECTING"
        tag = f"Acc {inst.config.acc_id}:{inst.config.username}"

        try:
            client = ClientNRO(
                host=host,
                port=port,
                version=ver,
                proxy=proxy_str,
                account_id=tag,
                username=inst.config.username,
            )
            inst.client = client

            # Đăng ký các callback sự kiện
            def _on_char_info(c: Char):
                inst.status = "ONLINE"
                inst.login_time = time.time()
                is_reconnected = inst.reconnect_count > 0
                inst.reconnect_count = 0
                inst.last_error = None
                prefix = "Tự động kết nối lại thành công" if is_reconnected else "Vào game thành công"
                logger.system(
                    f"{prefix}: NV '{c.cName}' (ID {c.charID}, Map {c.mapInfo.mapID})",
                    account_tag=inst.tag,
                )
                # Tự động kích hoạt lại các tác vụ auto đã lưu
                inst.restore_active_autos()
                if self.telegram_bot:
                    self.telegram_bot.notify_login_event(inst.tag, c.cName, c.mapInfo.mapID, is_reconnect=is_reconnected)

            def _on_vip_msg(cv: ChatVip):
                if cv.is_boss:
                    if cv.is_killed:
                        logger.boss(f"Boss '{cv.boss_name}' đã bị hạ bởi '{cv.killer}'!", account_tag=inst.tag)
                    else:
                        z_str = f" khu {cv.zone_id}" if cv.zone_id >= 0 else ""
                        logger.boss(f"Boss '{cv.boss_name}' xuất hiện tại {cv.map_name}{z_str}!", account_tag=inst.tag)
                    if self.telegram_bot:
                        self.telegram_bot.notify_boss_event(cv.boss_name, cv.map_name, cv.zone_id, cv.is_killed, cv.killer)

            def _on_server_msg(text: str):
                now = time.time()
                # Chống spam: lọc bỏ thông báo trùng lặp trong vòng 6 giây
                msg_key = f"{inst.config.acc_id}:{text}"
                last_time = self._last_server_messages.get(msg_key, 0.0)
                if now - last_time < 6.0:
                    logger.debug(f"[SERVER DUP] {text}", account_tag=inst.tag)
                    return
                self._last_server_messages[msg_key] = now

                # Lọc các thông báo hệ thống lặp lại nhiều khi tuần tra khu vực đưa vào debug
                spam_phrases = [
                    "Không thể đổi khu vực lúc này",
                    "Chưa đủ điều kiện để đến",
                    "vui lòng đợi",
                ]
                if any(phrase in text for phrase in spam_phrases):
                    logger.debug(f"[SERVER COOLDOWN] {text}", account_tag=inst.tag)
                if "nhiệm vụ" in text.lower():
                    if inst.client and inst.client.myChar:
                        inst.client.myChar.task_name = text.strip()

                logger.system(f"[SERVER] {text}", account_tag=inst.tag)

            def _on_disconnected():
                if inst.is_manual_stopping:
                    return
                inst.status = "DISCONNECTED"
                # Ghi nhận lại các tác vụ auto đang bật để nối lại sẽ tiếp tục
                inst.snapshot_active_autos()
                if self.telegram_bot:
                    self.telegram_bot.notify_disconnect_event(inst.tag, self.reconnect_delay)

                # Kích hoạt tự động kết nối lại nếu chế độ đang BẬT
                should_reconnect = self.auto_reconnect and getattr(inst.config, "auto_reconnect", True)
                if should_reconnect:
                    self._trigger_auto_reconnect(inst)

            client.on_char_info(_on_char_info)
            client.on_chat_vip(_on_vip_msg)
            client.on_server_message(_on_server_msg)
            client.on_disconnected(_on_disconnected)
            client.on_connection_fail(_on_disconnected)

            client.connect()
            time.sleep(0.3)
            client.login(inst.config.username, inst.config.password, version=ver)
            return True
        except Exception as ex:
            inst.status = "ERROR"
            inst.last_error = str(ex)
            logger.error(f"Khởi động thất bại: {ex}", account_tag=tag)
            # Nếu kết nối thất bại ban đầu và có bật auto-reconnect, thử lại sau delay
            if self.auto_reconnect and getattr(inst.config, "auto_reconnect", True) and not inst.is_manual_stopping:
                self._trigger_auto_reconnect(inst)
            return False

    def _trigger_auto_reconnect(self, inst: AccountInstance) -> None:
        """Kích hoạt luồng đếm ngược và tự động kết nối lại cho tài khoản."""
        with self._lock:
            if inst.is_manual_stopping:
                return
            if inst._reconnect_thread and inst._reconnect_thread.is_alive():
                return
            inst._reconnect_cancel_event.clear()
            inst.status = "RECONNECTING"

        def _reconnect_worker():
            while not inst.is_manual_stopping and not inst._reconnect_cancel_event.is_set():
                inst.reconnect_count += 1
                if self.max_reconnect_attempts > 0 and inst.reconnect_count > self.max_reconnect_attempts:
                    logger.error(
                        f"Đã thử kết nối lại {self.max_reconnect_attempts} lần thất bại. Dừng tự động kết nối!",
                        account_tag=inst.tag,
                    )
                    inst.status = "ERROR"
                    break

                delay = self.reconnect_delay
                inst.reconnect_timer_end = time.time() + delay
                max_str = f"/{self.max_reconnect_attempts}" if self.max_reconnect_attempts > 0 else ""
                logger.warn(
                    f"Mất kết nối! Sẽ tự động kết nối lại sau {int(delay)}s (Lần {inst.reconnect_count}{max_str})...",
                    account_tag=inst.tag,
                )

                # Chờ thời gian giãn cách với khả năng hủy sớm
                if inst._reconnect_cancel_event.wait(timeout=delay):
                    break

                if inst.is_manual_stopping:
                    break

                logger.system(f"Đang tiến hành kết nối lại (Lần {inst.reconnect_count})...", account_tag=inst.tag)
                try:
                    if inst.client:
                        try:
                            inst.client.disconnect()
                        except Exception:
                            pass
                        inst.client = None
                    time.sleep(0.5)

                    ok = self.start_account(inst)
                    if ok:
                        # Chờ tối đa 10s xem nhân vật đã vào map thành công chưa
                        for _ in range(20):
                            if inst.status == "ONLINE":
                                return
                            if inst.status == "DISCONNECTED" or inst.is_manual_stopping or inst._reconnect_cancel_event.is_set():
                                break
                            time.sleep(0.5)
                except Exception as ex:
                    logger.error(f"Lỗi khi thử kết nối lại: {ex}", account_tag=inst.tag)

        t = threading.Thread(target=_reconnect_worker, daemon=True, name=f"AutoReconnect-{inst.config.acc_id}")
        inst._reconnect_thread = t
        t.start()

    def start_all(self, delay: float = 2.0) -> None:
        """
        Khởi động toàn bộ tài khoản có enabled=True.
        Thêm độ trễ giữa các tài khoản để tránh bị máy chủ phát hiện hoặc nghẽn băng thông.
        """
        targets = [a for a in self.accounts if a.config.enabled]
        logger.system(f"Bắt đầu khởi động {len(targets)} tài khoản (giãn cách {delay}s)...")

        def _runner():
            for i, inst in enumerate(targets):
                logger.system(f"-> Khởi động [{i+1}/{len(targets)}]: '{inst.config.username}'...")
                self.start_account(inst)
                if i < len(targets) - 1 and delay > 0:
                    time.sleep(delay)
            logger.system(f"Hoàn tất gửi yêu cầu đăng nhập cho toàn bộ {len(targets)} tài khoản!")

        t = threading.Thread(target=_runner, daemon=True, name="MultiAccStartThread")
        t.start()

    def stop_account(self, inst: AccountInstance) -> None:
        """Dừng một tài khoản an toàn và hủy luồng tự động kết nối lại."""
        inst.is_manual_stopping = True
        inst._reconnect_cancel_event.set()
        inst.reconnect_count = 0
        if inst.client:
            try:
                inst.client.logout()
            except Exception:
                pass
            inst.client = None
        inst.status = "OFFLINE"
        logger.system("Đã dừng tài khoản.", account_tag=inst.tag)

    def stop_all(self) -> None:
        """Dừng tất cả các tài khoản đang chạy."""
        logger.system("Đang dừng toàn bộ tài khoản...")
        with self._lock:
            for inst in self.accounts:
                inst.is_manual_stopping = True
                inst._reconnect_cancel_event.set()
                inst.reconnect_count = 0
                if inst.client:
                    try:
                        inst.client.logout()
                    except Exception:
                        pass
                    inst.client = None
                inst.status = "OFFLINE"
        logger.system("Toàn bộ tài khoản đã được đăng xuất an toàn.")

    def relogin_account(self, inst: AccountInstance) -> None:
        """Đăng nhập lại tài khoản ngay lập tức."""
        inst.is_manual_stopping = False
        inst._reconnect_cancel_event.set()  # Hủy đếm ngược nếu đang chờ reconnect
        if inst.client:
            try:
                inst.client.disconnect()
            except Exception:
                pass
            inst.client = None
        time.sleep(0.5)
        self.start_account(inst)

    def set_auto_reconnect(self, enabled: bool, delay: Optional[float] = None) -> None:
        """Bật / Tắt hoặc điều chỉnh thời gian tự động kết nối lại toàn cục."""
        self.auto_reconnect = enabled
        if delay is not None and delay > 0:
            self.reconnect_delay = delay
        for a in self.accounts:
            a.config.auto_reconnect = enabled
            if not enabled:
                a._reconnect_cancel_event.set()
        status_str = f"BẬT (Chờ {int(self.reconnect_delay)}s)" if enabled else "TẮT"
        logger.system(f"Chế độ Auto-Reconnect: {status_str}")
