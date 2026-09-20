# -*- coding: utf-8 -*-
"""
Đối tượng runtime AccountInstance đại diện cho 1 tài khoản đang hoạt động.
Quản lý trạng thái kết nối, luồng, auto task snapshot & restore,
cùng các thông số hiển thị nhân vật và vị trí runtime.
"""

import threading
from typing import Optional, List, Dict, Any, Union

from .config import AccountConfig
from ..proxy_manager import ProxyConfig
from ..client import ClientNRO
from ..game_data import format_big_number
from ..logger import logger


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

        # Lưu trữ trạng thái tác vụ auto và khu vực/bản đồ để khôi phục khi reconnect hoặc mất mạng đột ngột
        self.saved_auto_tasks: List[str] = [t for t in (config.auto_tasks or []) if t and t.strip()]
        self.saved_auto_state: Dict[str, Any] = {}
        self.last_zone_id: int = -1
        self.last_map_id: int = -1
        self.saved_zone_id: int = -1
        self.saved_map_id: int = -1
        self.last_commands: List[str] = []

    def snapshot_active_autos(self) -> None:
        """
        Lưu lại toàn bộ các tác vụ auto đang chạy, thông số cấu hình và vị trí map/zone.
        Cập nhật liên tục để ngay cả khi ngắt kết nối đột ngột vẫn giữ nguyên vẹn dữ liệu.
        """
        if not self.client:
            return

        try:
            # Ghi nhận Map và Zone hiện tại
            if self.client.myChar and self.client.myChar.mapInfo:
                curr_z = getattr(self.client.myChar.mapInfo, "zoneID", -1)
                curr_m = getattr(self.client.myChar.mapInfo, "mapID", -1)
                if curr_z >= 0:
                    self.last_zone_id = curr_z
                    self.saved_zone_id = curr_z
                if curr_m >= 0:
                    self.last_map_id = curr_m
                    self.saved_map_id = curr_m

            auto = getattr(self.client, "auto", None)
            if not auto:
                return

            state: Dict[str, Any] = {}
            active_tasks: List[str] = []

            # 1. Tự đánh (AK)
            if getattr(auto, "is_ak", False):
                active_tasks.append("ak")
                state["ak"] = True

            # 2. Tàn sát (TS)
            if getattr(auto, "is_tansat", False):
                active_tasks.append("ts")
                state["ts"] = {
                    "mode": getattr(auto, "tansat_mode", "mob"),
                    "target_mob_ids": list(getattr(auto, "target_mob_ids", set())),
                    "target_mob_types": list(getattr(auto, "target_mob_types", set())),
                    "avoid_super_mob": getattr(auto, "avoid_super_mob", True),
                    "skill_id": getattr(auto, "tansat_skill_id", None),
                    "combo_skills": list(getattr(auto, "combat_combo_skills", [])) if getattr(auto, "combat_combo_skills", None) else None,
                }

            # 3. Săn Boss (Hunt)
            if getattr(auto, "is_boss_hunter_enabled", False):
                active_tasks.append("hunt")
                state["hunt"] = {
                    "hunt_all": getattr(auto, "hunt_all", False),
                    "target_bosses": list(getattr(auto, "target_bosses", set())),
                    "auto_loot": getattr(auto, "auto_loot_boss", True),
                    "auto_patrol": getattr(auto, "auto_patrol", False),
                    "combo_skills": list(getattr(auto, "combat_combo_skills", [])) if getattr(auto, "combat_combo_skills", None) else None,
                }

            # 4. Úp đệ tử (TrainPet)
            if hasattr(auto, "train_pet") and (getattr(auto.train_pet, "is_enabled", False) or getattr(auto.train_pet, "is_running", False)):
                active_tasks.append("trainpet")
                state["trainpet"] = {
                    "mode": auto.train_pet.mode.name.lower(),
                    "attack_mode": auto.train_pet.attack_mode.name.lower(),
                }

            # 5. Úp tân thủ / sơ sinh (TrainNewAcc)
            if hasattr(auto, "train_new_acc") and (getattr(auto.train_new_acc, "is_enabled", False) or getattr(auto.train_new_acc, "is_running", False)):
                active_tasks.append("trainacc")
                state["trainacc"] = True

            # 6. Nhiệm vụ bò mộng (NVBM)
            if getattr(auto, "is_quest_enabled", False):
                active_tasks.append("nvbm")
                state["nvbm"] = True

            # 7. Tự nhặt đồ & Dùng đậu & Né siêu quái
            state["anhat"] = getattr(auto, "auto_pick", True)
            state["cnn"] = getattr(auto, "pick_gem_only", False)
            state["abf"] = getattr(auto, "auto_pean", True)
            state["pean_threshold"] = getattr(auto, "pean_threshold", 0.3)
            state["nsq"] = getattr(auto, "avoid_super_mob", True)

            # 8. Tự hồi sinh (AutoHS)
            if getattr(auto, "auto_revive", False):
                active_tasks.append("autohs")
                state["autohs"] = {
                    "mode": getattr(auto, "revive_mode", "gem"),
                }

            # 9. Tự dùng Item định kỳ (UseItem)
            if getattr(auto, "auto_use_item_enabled", False):
                active_tasks.append("useitem")
                state["useitem"] = {
                    "item_id": getattr(auto, "auto_use_item_id", None),
                    "interval": getattr(auto, "auto_use_interval_minutes", 10.0),
                }

            # 10. Shuttle (Chạy 2 map)
            if getattr(auto, "is_shuttle_enabled", False):
                active_tasks.append("shuttle")
                state["shuttle"] = {
                    "map_a": getattr(auto, "shuttle_map_a", None),
                    "map_b": getattr(auto, "shuttle_map_b", None),
                    "rounds": getattr(auto, "shuttle_rounds", 0),
                }

            # 11. Nhiệm vụ chính tuyến (NV)
            if getattr(auto, "is_main_task_enabled", False):
                active_tasks.append("nv")
                state["nv"] = {
                    "combo_skills": list(getattr(auto, "combat_combo_skills", [])) if getattr(auto, "combat_combo_skills", None) else None,
                }

            self.saved_auto_state = state
            self.saved_auto_tasks = active_tasks
        except Exception:
            pass

    def restore_active_autos(self) -> None:
        """Khôi phục lại đầy đủ toàn bộ tác vụ, thông số cấu hình và lệnh auto sau khi kết nối lại thành công."""
        if not self.client:
            return

        state = getattr(self, "saved_auto_state", {})
        tasks = list(self.saved_auto_tasks) if getattr(self, "saved_auto_tasks", None) is not None else [t for t in self.config.auto_tasks if t and t.strip()]
        auto = getattr(self.client, "auto", None)
        if not auto:
            return

        restored: List[str] = []

        try:
            # Phục hồi cài đặt sinh tồn & nhặt đồ
            if "anhat" in state:
                auto.auto_pick = state["anhat"]
            if "cnn" in state:
                auto.pick_gem_only = state["cnn"]
            if "abf" in state:
                auto.auto_pean = state["abf"]
            if "pean_threshold" in state:
                auto.pean_threshold = state["pean_threshold"]
            if "nsq" in state:
                auto.avoid_super_mob = state["nsq"]

            # 1. Tự đánh (AK)
            if "ak" in tasks or state.get("ak"):
                auto.start_ak()
                restored.append("AK")

            # 2. Tàn sát (TS)
            if "ts" in tasks or "ts" in state:
                ts_cfg = state.get("ts", {})
                mode = ts_cfg.get("mode", "mob")
                if ts_cfg.get("avoid_super_mob") is not None:
                    auto.avoid_super_mob = ts_cfg["avoid_super_mob"]
                if ts_cfg.get("target_mob_ids"):
                    auto.target_mob_ids = set(ts_cfg["target_mob_ids"])
                if ts_cfg.get("target_mob_types"):
                    auto.target_mob_types = set(ts_cfg["target_mob_types"])
                if ts_cfg.get("combo_skills"):
                    auto.combat_combo_skills = list(ts_cfg["combo_skills"])
                auto.start_tansat(mode=mode)
                restored.append(f"TS({mode})")

            # 3. Săn Boss (Hunt)
            if "hunt" in tasks or "hunt" in state:
                h_cfg = state.get("hunt", {})
                if h_cfg.get("target_bosses"):
                    auto.target_bosses = set(h_cfg["target_bosses"])
                if h_cfg.get("hunt_all") is not None:
                    auto.hunt_all = h_cfg["hunt_all"]
                if h_cfg.get("auto_loot") is not None:
                    auto.auto_loot_boss = h_cfg["auto_loot"]
                if h_cfg.get("auto_patrol") is not None:
                    auto.auto_patrol = h_cfg["auto_patrol"]
                if h_cfg.get("combo_skills"):
                    auto.combat_combo_skills = list(h_cfg["combo_skills"])
                self.client.start_auto_hunt()
                restored.append("Hunt")

            # 4. Úp đệ tử (TrainPet)
            if "trainpet" in tasks or "trainpet" in state:
                tp_cfg = state.get("trainpet", {})
                mode_str = tp_cfg.get("mode", "normal")
                atk_str = tp_cfg.get("attack_mode", "mob")
                auto.start_train_pet(mode_str)
                auto.set_train_pet_attack_mode(atk_str)
                restored.append(f"TrainPet({mode_str})")

            # 5. Úp tân thủ / sơ sinh (TrainNewAcc)
            if "trainacc" in tasks or state.get("trainacc"):
                auto.start_train_new_account()
                restored.append("TrainAcc")

            # 6. Nhiệm vụ bò mộng (NVBM)
            if "nvbm" in tasks or state.get("nvbm"):
                self.client.start_auto_quest()
                restored.append("NVBM")

            # 7. Tự hồi sinh (AutoHS)
            if "autohs" in tasks or "autohs" in state:
                hs_cfg = state.get("autohs", {})
                rev_mode = hs_cfg.get("mode", "gem")
                self.client.set_auto_revive_mode(rev_mode)
                self.client.auto_revive_manager.enable()
                restored.append(f"AutoHS({rev_mode})")

            # 8. Tự dùng Item (UseItem)
            if "useitem" in tasks or "useitem" in state:
                ui_cfg = state.get("useitem", {})
                item_id = ui_cfg.get("item_id")
                interval = ui_cfg.get("interval", 10.0)
                if item_id is not None:
                    self.client.start_auto_use_item(item_id, interval)
                    restored.append(f"UseItem({item_id})")

            # 9. Shuttle
            if "shuttle" in tasks or "shuttle" in state:
                st_cfg = state.get("shuttle", {})
                map_a = st_cfg.get("map_a")
                map_b = st_cfg.get("map_b")
                rounds = st_cfg.get("rounds", 0)
                if map_a is not None and map_b is not None:
                    self.client.start_shuttle(map_a, map_b, rounds)
                    restored.append(f"Shuttle({map_a}<->{map_b})")

            # 10. Nhiệm vụ chính tuyến (NV)
            if "nv" in tasks or "nv" in state:
                nv_cfg = state.get("nv", {}) if isinstance(state.get("nv"), dict) else {}
                if nv_cfg.get("combo_skills"):
                    auto.combat_combo_skills = list(nv_cfg["combo_skills"])
                self.client.start_auto_main_task()
                restored.append("NV")

            if restored:
                logger.system(f"Đã tự động khôi phục các lệnh/tác vụ: {', '.join(restored)}", account_tag=self.tag)
        except Exception as ex:
            logger.error(f"Lỗi khi khôi phục tác vụ auto: {ex}", account_tag=self.tag)

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
            p = getattr(self.client.myChar, "cPower", 0)
            if p >= 1_000:
                return f"{p:,} ({format_big_number(p)})"
            return f"{p:,}"
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
            if isinstance(self.assigned_proxy, str):
                return self.assigned_proxy
            return getattr(self.assigned_proxy, "display_str", str(self.assigned_proxy))
        return "Trực tiếp"

    @property
    def auto_status_str(self) -> str:
        if not self.client:
            return "N/A"
        active = []
        auto = getattr(self.client, "auto", None)
        if not auto:
            return "None"
        if getattr(auto, "is_boss_hunter_enabled", False):
            active.append("Hunt")
        if getattr(auto, "is_quest_enabled", False):
            active.append("NVBM")
        if getattr(auto, "is_ak", False):
            active.append("AK")
        if getattr(auto, "is_tansat", False):
            mode = getattr(auto, "tansat_mode", "mob")
            active.append(f"TS({mode})")
        if hasattr(auto, "train_pet") and (getattr(auto.train_pet, "is_enabled", False) or getattr(auto.train_pet, "is_running", False)):
            active.append(f"Pet({auto.train_pet.mode.name.lower()})")
        if hasattr(auto, "train_new_acc") and (getattr(auto.train_new_acc, "is_enabled", False) or getattr(auto.train_new_acc, "is_running", False)):
            active.append("NewAcc")
        if getattr(auto, "is_shuttle_enabled", False):
            active.append("Shuttle")
        if getattr(auto, "auto_use_item_enabled", False):
            active.append(f"Item({auto.auto_use_item_id})")
        if getattr(auto, "auto_revive", False):
            active.append("HS")
        if getattr(auto, "pick_gem_only", False):
            active.append("CNN")
        elif getattr(auto, "auto_pick", False):
            active.append("Nhặt")
        return ", ".join(active) if active else "None"

    def refresh_info(self) -> None:
        """Gửi yêu cầu đồng bộ chỉ số mới nhất từ máy chủ cho tài khoản này."""
        if self.client and hasattr(self.client, "refresh_char_info"):
            self.client.refresh_char_info()
