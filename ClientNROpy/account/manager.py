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
from typing import Optional, List, Dict, Any, Tuple, Union, Callable, Set

from .config import AccountConfig
from .instance import AccountInstance
from ..client import ClientNRO
from ..proxy_manager import ProxyPool, ProxyConfig, parse_proxy
from ..logger import logger
from ..char import Char
from ..chat_vip import ChatVip
from ..player_data import PlayerData
from ..map_info import MapInfo

__all__ = [
    "AccountConfig",
    "AccountInstance",
    "AccountManager",
    "DEFAULT_CONFIG_PATH",
    "DEFAULT_SETTINGS",
    "DEFAULT_SETTINGS_PATHS",
    "DEFAULT_ACCOUNTS_PATHS",
]


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


DEFAULT_SETTINGS_PATHS = ["settings.json", "setting.json", "setting.js"]
DEFAULT_ACCOUNTS_PATHS = ["accounts.json", "account.json"]


class AccountManager:
    """Quản lý danh sách các tài khoản và phân bổ mạng."""

    def refresh_all_accounts_info(self) -> None:
        """Gửi yêu cầu đồng bộ chỉ số mới nhất cho tất cả tài khoản đang online."""
        for a in self.accounts:
            try:
                if a.client and hasattr(a.client, "isConnected") and a.client.isConnected():
                    a.refresh_info()
            except Exception:
                pass

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
                "notify_boss": False,
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
            "notify_boss": False,
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
                "auto": [],
            },
            {
                "username": "poopooi02",
                "password": "02082003",
                "enabled": True,
                "auto_reconnect": True,
                "proxy": None,
                "auto": [],
            },
            {
                "username": "poopooi03",
                "password": "02082003",
                "enabled": True,
                "auto_reconnect": True,
                "proxy": None,
                "auto": [],
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
                auto_tasks=[],
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
                        "auto": [t for t in (inst.config.auto_tasks or []) if t and t.strip()],
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
            clean_auto = [t for t in auto_tasks if t and t.strip()] if auto_tasks is not None else []
            cfg = AccountConfig(
                acc_id=idx + 1,
                username=u_clean,
                password=p_clean,
                proxy=proxy.strip() if proxy else None,
                auto_tasks=clean_auto,
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

    NOTIFY_KEYS = {
        "boss": ("notify_boss", "Boss xuất hiện/bị diệt"),
        "login": ("notify_login", "Vào game / kết nối lại"),
        "dis": ("notify_disconnect", "Mất kết nối"),
        "disconnect": ("notify_disconnect", "Mất kết nối"),
        "matmang": ("notify_disconnect", "Mất kết nối"),
    }

    def set_notify_and_save(self, kind: str, enable: bool) -> Tuple[bool, str]:
        """Bật/Tắt 1 loại thông báo Telegram, áp dụng ngay và lưu settings.json."""
        found = self.NOTIFY_KEYS.get(kind.strip().lower())
        if not found:
            return False, f"Loại thông báo không hợp lệ: '{kind}'! Dùng: boss | login | dis"
        key, label = found
        self.telegram_config[key] = enable
        bot = getattr(self, "telegram_bot", None)
        if bot is not None:
            setattr(bot, key, enable)
        self.save_settings_file()
        return True, f"Đã {'BẬT' if enable else 'TẮT'} thông báo: {label}!"

    def get_notify_status(self) -> str:
        """Chuỗi trạng thái các loại thông báo Telegram."""
        seen = []
        for key, label in [("notify_boss", "Boss"), ("notify_login", "Vào game"), ("notify_disconnect", "Mất mạng")]:
            st = "BẬT" if self.telegram_config.get(key, False) else "TẮT"
            seen.append(f"{label}: {st}")
        return " | ".join(seen)

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
            def _on_login_ok(players: List[PlayerData]):
                if players:
                    logger.system(f"Tự động chọn nhân vật '{players[0].name}'...", account_tag=inst.tag)
                    client.selectChar(players[0].name)

            def _on_map_info(m: MapInfo):
                # Theo dõi Map và Zone liên tục theo thời gian thực phòng khi mất mạng đột ngột
                if m.zoneID >= 0:
                    inst.last_zone_id = m.zoneID
                if m.mapID >= 0:
                    inst.last_map_id = m.mapID
                inst.snapshot_active_autos()

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

                # Tự động quay lại khu cũ nếu có
                target_zone = inst.saved_zone_id if inst.saved_zone_id >= 0 else inst.last_zone_id
                target_map = inst.saved_map_id if inst.saved_map_id >= 0 else inst.last_map_id

                if target_zone >= 0:
                    def _restore_zone_worker():
                        # Trễ 0.5s theo yêu cầu người dùng để client hoàn tất bắt tay và nạp map
                        time.sleep(0.5)
                        if not inst.client or not inst.client.isConnected() or inst.status != "ONLINE":
                            return
                        curr_z = getattr(inst.client.myChar.mapInfo, "zoneID", -1)
                        curr_m = getattr(inst.client.myChar.mapInfo, "mapID", -1)
                        if (target_map < 0 or curr_m == target_map) and target_zone >= 0 and curr_z != target_zone:
                            logger.system(f"Đang tự động chuyển về khu cũ: Khu {target_zone} (từ Khu {curr_z})...", account_tag=inst.tag)
                            inst.client.change_zone(target_zone)
                            time.sleep(0.8)
                            new_z = getattr(inst.client.myChar.mapInfo, "zoneID", -1)
                            if new_z == target_zone:
                                logger.system(f"Đã quay lại khu cũ thành công: Khu {target_zone}!", account_tag=inst.tag)
                            elif new_z >= 0 and new_z != target_zone:
                                inst.client.change_zone(target_zone)

                    threading.Thread(target=_restore_zone_worker, daemon=True, name=f"RestoreZone-{inst.config.acc_id}").start()

                # Tự động kích hoạt lại toàn bộ các tác vụ auto đã lưu
                inst.restore_active_autos()

                if c.mapInfo and c.mapInfo.zoneID >= 0:
                    inst.last_zone_id = c.mapInfo.zoneID
                if c.mapInfo and c.mapInfo.mapID >= 0:
                    inst.last_map_id = c.mapInfo.mapID

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
                    return

                if "nhiệm vụ" in text.lower():
                    if inst.client and inst.client.myChar:
                        from ..models.task import clean_task_name
                        cleaned_task = clean_task_name(text.strip())
                        if not inst.client.myChar.task and cleaned_task:
                            inst.client.myChar.task_name = cleaned_task
                    logger.debug(f"[SERVER TASK] {text}", account_tag=inst.tag)
                    return

                logger.system(f"[SERVER] {text}", account_tag=inst.tag)

            def _on_disconnected():
                if inst.is_manual_stopping:
                    return
                inst.status = "DISCONNECTED"
                # Ghi nhận lại toàn diện các tác vụ auto đang bật và vị trí trước khi luồng reconnect dọn dẹp client
                inst.snapshot_active_autos()
                if inst.saved_zone_id < 0 and inst.last_zone_id >= 0:
                    inst.saved_zone_id = inst.last_zone_id
                if inst.saved_map_id < 0 and inst.last_map_id >= 0:
                    inst.saved_map_id = inst.last_map_id

                if self.telegram_bot:
                    self.telegram_bot.notify_disconnect_event(inst.tag, self.reconnect_delay)

                # Kích hoạt tự động kết nối lại nếu chế độ đang BẬT
                should_reconnect = self.auto_reconnect and getattr(inst.config, "auto_reconnect", True)
                if should_reconnect:
                    self._trigger_auto_reconnect(inst)

            client.on_login_ok(_on_login_ok)
            client.on_map_info(_on_map_info)
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
            inst.snapshot_active_autos()
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

    def disperse_zones_min(self, targets: Optional[List[AccountInstance]] = None) -> List[Dict[str, Any]]:
        """
        Phân tán toàn bộ tài khoản sang các khu ít người chơi nhất (khu min) sao cho:
        1. Tất cả tài khoản tản ra đều, không đụng khu nhau (mỗi acc 1 khu riêng biệt nếu còn khu trống).
        2. Nếu một tài khoản đang đứng ở khu đã là khu min (hoặc bằng min) và chưa bị acc khác trong đội chiếm,
           thì giữ nguyên vị trí, không đổi đi đâu hết.
        3. Phân nhóm theo từng map riêng biệt nếu các acc đang ở các map khác nhau.
        Trả về danh sách kết quả chi tiết từng tài khoản.
        """
        if targets is None:
            targets = [
                a for a in self.accounts
                if a.client and a.client.isConnected() and a.client.myChar and a.client.myChar.mapInfo
            ]
        else:
            targets = [
                a for a in targets
                if a.client and a.client.isConnected() and a.client.myChar and a.client.myChar.mapInfo
            ]

        if not targets:
            return []

        # Phân nhóm tài khoản theo mapID
        map_groups: Dict[int, List[AccountInstance]] = {}
        for a in targets:
            mid = getattr(a.client.myChar.mapInfo, "mapID", -1)
            map_groups.setdefault(mid, []).append(a)

        results: List[Dict[str, Any]] = []

        for mid, acc_list in map_groups.items():
            if not acc_list:
                continue

            # Dùng tài khoản đầu tiên trong map để lấy danh sách khu
            first_client = acc_list[0].client
            first_client.request_zones()
            time.sleep(0.35)
            zones = getattr(first_client.myChar.mapInfo, "zones", [])
            if not zones:
                time.sleep(0.25)
                zones = getattr(first_client.myChar.mapInfo, "zones", [])

            if not zones:
                # Nếu không đọc được danh sách khu, fallback cho từng acc gọi hàm cá nhân
                for a in acc_list:
                    curr_z = getattr(a.client.myChar.mapInfo, "zoneID", -1)
                    zid = a.client.change_to_least_populated_zone()
                    results.append({
                        "account": a,
                        "map_id": mid,
                        "map_name": getattr(a.client.myChar.mapInfo, "mapName", ""),
                        "from_zone": curr_z,
                        "to_zone": zid if zid is not None else curr_z,
                        "changed": (zid is not None and zid != curr_z),
                        "stayed": (zid == curr_z),
                    })
                continue

            # Lọc các khu còn chỗ
            valid_zones = [z for z in zones if getattr(z, "numPlayer", 0) < getattr(z, "maxPlayer", 15)]
            if not valid_zones:
                valid_zones = list(zones)

            min_players = min(getattr(z, "numPlayer", 0) for z in valid_zones)

            # Khởi tạo bảng đếm người chơi theo khu
            # zone_occupancy: zid -> số người hiện tại (bao gồm các acc đã được xếp)
            zone_occupancy: Dict[int, int] = {
                getattr(z, "zoneId", 0): getattr(z, "numPlayer", 0) for z in valid_zones
            }
            claimed_zones: Set[int] = set()
            assigned: Dict[AccountInstance, int] = {}
            unassigned: List[AccountInstance] = []

            # BƯỚC 1: Ưu tiên tài khoản đang đứng ở khu ĐÃ LÀ MIN ZONE
            # Nếu khu đang đứng có số người <= min_players và chưa bị acc nào trước đó chiếm -> Giữ nguyên!
            for a in acc_list:
                curr_z = getattr(a.client.myChar.mapInfo, "zoneID", -1)
                curr_obj = next((z for z in valid_zones if getattr(z, "zoneId", -1) == curr_z), None)
                if (
                    curr_obj is not None
                    and getattr(curr_obj, "numPlayer", 0) <= min_players
                    and curr_z not in claimed_zones
                ):
                    assigned[a] = curr_z
                    claimed_zones.add(curr_z)
                    zone_occupancy[curr_z] = zone_occupancy.get(curr_z, 0) + 1
                else:
                    unassigned.append(a)

            # BƯỚC 2: Phân tán các tài khoản còn lại vào các khu vắng khác để KHÔNG ĐỤNG NHAU
            for a in unassigned:
                # Ứng viên ưu tiên: các khu chưa bị acc trong đội chiếm
                unclaimed_cands = [z for z in valid_zones if getattr(z, "zoneId", 0) not in claimed_zones]
                if unclaimed_cands:
                    # Sắp xếp theo số người chơi tăng dần
                    unclaimed_cands.sort(key=lambda z: (zone_occupancy.get(getattr(z, "zoneId", 0), 0), getattr(z, "zoneId", 0)))
                    chosen_z = getattr(unclaimed_cands[0], "zoneId", 0)
                else:
                    # Nếu số acc nhiều hơn số khu, chọn khu có ít người nhất hiện tại
                    all_cands = list(valid_zones)
                    all_cands.sort(key=lambda z: (zone_occupancy.get(getattr(z, "zoneId", 0), 0), getattr(z, "zoneId", 0)))
                    chosen_z = getattr(all_cands[0], "zoneId", 0)

                assigned[a] = chosen_z
                claimed_zones.add(chosen_z)
                zone_occupancy[chosen_z] = zone_occupancy.get(chosen_z, 0) + 1

            # BƯỚC 3: Thực thi chuyển khu cho các tài khoản cần chuyển
            for a in acc_list:
                curr_z = getattr(a.client.myChar.mapInfo, "zoneID", -1)
                target_z = assigned.get(a, curr_z)
                changed = False
                if target_z != curr_z and target_z >= 0:
                    a.client.change_zone(target_z)
                    a.last_zone_id = target_z
                    a.snapshot_active_autos()
                    changed = True
                    time.sleep(0.1)  # Giảm nghẽn mạng giữa các request

                results.append({
                    "account": a,
                    "map_id": mid,
                    "map_name": getattr(a.client.myChar.mapInfo, "mapName", ""),
                    "from_zone": curr_z,
                    "to_zone": target_z,
                    "changed": changed,
                    "stayed": not changed,
                })

        return results
