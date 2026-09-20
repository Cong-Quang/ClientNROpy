# -*- coding: utf-8 -*-
"""
Module tích hợp Telegram Bot & Trợ Lý AI OpenRouter (telegram_bot.py).
Hỗ trợ:
1. Điều khiển 100% tính năng trò chơi từ xa qua Telegram Bot (@nroPy_Bot)
2. Bàn phím nút bấm tùy chỉnh (ReplyKeyboardMarkup) trực tiếp dưới khung chat:
   - Nút chọn từng tài khoản đang hoạt động (Acc #1, Acc #2...) hoặc Tất cả [ALL]
   - Nút tra cứu nhanh (/status, /info, /bag, /pet, /map, /harvest...)
   - Nút hành động nhanh (/hunt on, /hunt off, /xmap 0, /reconnect...)
3. Lệnh /info chi tiết 100%: Bản thân, HP, MP, Sức mạnh, Tiềm năng, Sức đánh, Giáp, Crit,
   Tài sản (Vàng, Ngọc), Đệ tử, Bản đồ, Zone, Tọa độ, Cây đậu thần, Balo, Rương đồ, Trang bị, Auto
4. Cơ chế chống trùng lặp thông báo Boss (Deduplication) khi chạy nhiều tài khoản cùng lúc
5. Trợ lý AI OpenRouter (model: openrouter/free) với đầy đủ ngữ cảnh thời gian thực (real-time context)
   mỗi khi người dùng đặt câu hỏi và ghi nhớ lịch sử hội thoại nhiều lượt (chat memory)
6. Tự động chuyển đổi ý định người dùng thành lệnh [EXEC: <lệnh>] để điều khiển game
7. Hoạt động thuần túy trên thư viện chuẩn Python (urllib.request), không yêu cầu cài thư viện ngoài.
"""

import os
import sys
import json
import time
import re
import threading
import urllib.request
import urllib.error
from typing import Optional, List, Dict, Any, Set, Union

from .logger import logger
from .char import Char
from .item import Item
from .pet import PET_ACTION_MAP, PET_STATUS_NAMES
from .game_data import (
    COMMON_ITEM_NAMES,
    ITEM_NAMES,
    SKILL_NAMES,
    BODY_SLOT_NAMES,
    ITEM_TYPE_NAMES,
    GENDER_NAMES,
    format_big_number,
    format_compact_number,
    get_item_display_name,
    get_skill_display_name,
    get_item_name,
    get_item_info,
    get_item_type_name,
    get_gender_name,
    format_item_details,
    get_map_name,
    get_mob_name,
    get_npc_name,
    search_items,
)


class TelegramAIBot:
    """Quản lý Telegram Bot và kết nối AI OpenRouter."""

    def __init__(
        self,
        token: str,
        account_manager=None,
        allowed_chat_ids: Optional[List[Union[int, str]]] = None,
        notify_boss: bool = False,
        notify_disconnect: bool = True,
        notify_login: bool = True,
        ai_enabled: bool = True,
        ai_api_key: str = "",
        ai_model: str = "openrouter/free",
        ai_system_prompt: Optional[str] = None,
    ):
        self.token: str = token.strip()
        self.account_manager = account_manager
        self.allowed_chat_ids: Set[Union[int, str]] = set(allowed_chat_ids or [])
        self.active_chat_ids: Set[Union[int, str]] = set(allowed_chat_ids or [])

        # Ngữ cảnh tài khoản đang chọn điều khiển cho từng người chat.
        # None = tất cả tài khoản.
        self.selected_targets: Dict[Union[int, str], Optional[int]] = {}

        # Trạng thái giao diện nút bấm theo từng người chat.
        # Mục đích: tách màn hình chọn tài khoản khỏi màn hình điều khiển.
        self._menu_modes: Dict[Union[int, str], str] = {}

        # Bộ lọc chống trùng lặp thông báo Boss giữa nhiều tài khoản
        self._recent_boss_events: Dict[str, float] = {}

        # Bộ nhớ lịch sử hội thoại cho AI OpenRouter
        self._chat_histories: Dict[Union[int, str], List[Dict[str, str]]] = {}

        self.notify_boss: bool = notify_boss
        self.notify_disconnect: bool = notify_disconnect
        self.notify_login: bool = notify_login

        self.ai_enabled: bool = ai_enabled
        self.ai_api_key: str = ai_api_key.strip()
        self.ai_model: str = ai_model or "openrouter/free"
        self.ai_system_prompt: str = ai_system_prompt or (
            "Bạn là trợ lý AI thông minh quản lý và điều khiển tài khoản Ngọc Rồng Online (ClientNRO). "
            "Hãy trả lời ngắn gọn, thân thiện và hữu ích bằng Tiếng Việt. "
            "Bạn được cung cấp toàn bộ trạng thái chi tiết của các tài khoản (HP, MP, Đệ tử, Balo, Vị trí, Auto, Boss đang xuất hiện) "
            "theo thời gian thực mỗi khi người dùng hỏi. "
            "Nếu người dùng yêu cầu thực hiện hành động (như di chuyển, săn boss, đổi khu, hồi sinh, đánh quái, nhặt đồ, đổi trạng thái đệ...), "
            "hãy đính kèm thẻ lệnh [EXEC: <lệnh>] ở cuối câu trả lời để hệ thống tự động thực thi. "
            "Ví dụ: 'Đang chuyển hentaiz về nhà [EXEC: acc 1 xmap 0]' hoặc 'Đã bật săn boss [EXEC: all hunt on]'."
        )

        self._running: bool = False
        self._thread: Optional[threading.Thread] = None
        self._last_update_id: int = 0
        # Sức khỏe vòng polling nhận lệnh (để chẩn đoán khi bot gửi được mà không trả lời)
        self._last_poll_ok: float = 0.0
        self._last_poll_error: str = ""
        self._poll_updates: int = 0
        # Mạng NAT thường cắt kết nối treo lâu: giữ long-poll ngắn (10s),
        # thất bại liên tiếp sẽ tự hạ về short-poll (timeout=0).
        self._poll_hold: int = 10
        self._poll_fail_streak: int = 0
        self._lock = threading.Lock()

    # --------------------------------------------------------------------------
    # Bàn phím nút bấm tùy chỉnh (ReplyKeyboardMarkup)
    # --------------------------------------------------------------------------
    def get_main_keyboard(self, chat_id: Optional[Union[int, str]] = None) -> Dict[str, Any]:
        """Tạo bàn phím điều khiển theo từng màn hình, ưu tiên thao tác bằng tiếng Việt."""
        mode = self._menu_modes.get(chat_id, "main") if chat_id else "main"
        selected = self.selected_targets.get(chat_id) if chat_id else None

        def menu(rows: List[List[str]]) -> Dict[str, Any]:
            return {
                "keyboard": [[{"text": text} for text in row] for row in rows],
                "resize_keyboard": True,
                "is_persistent": True,
                "one_time_keyboard": False,
            }

        if mode == "accounts":
            rows: List[List[str]] = [["Tất cả tài khoản"]]
            acc_row: List[str] = []
            if self.account_manager and self.account_manager.accounts:
                for a in self.account_manager.accounts:
                    cname = a.char_name if a.char_name != "Chưa vào" else a.config.username
                    online = bool(a.client and a.client.isConnected())
                    state = "Đang online" if online else "Ngoại tuyến"
                    label = f"Tài khoản {a.config.acc_id}: {state}"
                    if cname:
                        label += f" - {cname[:24]}"
                    acc_row.append(label)
                    if len(acc_row) == 2:
                        rows.append(acc_row)
                        acc_row = []
                if acc_row:
                    rows.append(acc_row)
            rows.extend([
                ["Đăng nhập tất cả", "Đăng xuất tất cả"],
                ["Quay lại"],
            ])
            return menu(rows)

        if mode == "info":
            return menu([
                ["Tổng quan", "Thông tin chi tiết"],
                ["Balo", "Rương đồ"],
                ["Đệ tử", "Bản đồ"],
                ["Khu vực", "Chiến đấu"],
                ["Cây đậu", "Quay lại"],
            ])

        if mode == "control":
            return menu([
                ["Bật auto nhiệm vụ", "Tắt auto nhiệm vụ"],
                ["Trạng thái nhiệm vụ", "Thu hoạch đậu"],
                ["Bật tàn sát", "Tắt tàn sát"],
                ["Bật tự đánh", "Tắt tự đánh"],
                ["Bật săn Boss", "Tắt săn Boss"],
                ["Bật tự nhặt đồ", "Tắt tự hồi sinh"],
                ["Đăng nhập", "Đăng xuất"],
                ["Quay lại"],
            ])

        if mode == "boss":
            return menu([
                ["Xem Boss hiện tại", "Bật săn Boss"],
                ["Tắt săn Boss", "Đi tới Boss"],
                ["Trạng thái nhiệm vụ", "Quay lại"],
            ])

        if mode == "help":
            return menu([
                ["Tài khoản", "Trạng thái"],
                ["Điều khiển", "Thông tin"],
                ["Săn Boss", "Trợ lý AI"],
                ["Hướng dẫn", "Về menu chính"],
            ])

        # Màn hình chính chỉ chứa nhóm chức năng, không nhồi toàn bộ lệnh vào một chỗ.
        target_name = "Tất cả tài khoản" if selected is None else f"Tài khoản {selected}"
        return menu([
            ["Tài khoản", "Trạng thái"],
            ["Điều khiển", "Thông tin"],
            ["Săn Boss", "Đăng nhập"],
            ["Trợ lý AI", "Hướng dẫn"],
            [target_name],
        ])

    def _set_menu_mode(self, chat_id: Union[int, str], mode: str, send_menu: bool = True) -> None:
        """Chuyển màn hình điều khiển và cập nhật bàn phím Telegram."""
        self._menu_modes[chat_id] = mode
        if send_menu:
            title_map = {
                "main": "Menu chính",
                "accounts": "Chọn tài khoản",
                "info": "Thông tin",
                "control": "Điều khiển",
                "boss": "Săn Boss",
                "help": "Hướng dẫn",
            }
            title = title_map.get(mode, "Menu chính")
            selected = self.selected_targets.get(chat_id)
            target = "Tất cả tài khoản" if selected is None else f"Tài khoản {selected}"
            self.send_message(
                chat_id,
                f"*{title}*\nPhạm vi hiện tại: *{target}*",
                reply_markup=self.get_main_keyboard(chat_id),
            )

    def _handle_menu_button(self, chat_id: Union[int, str], text: str) -> bool:
        """Xử lý các nút giao diện tiếng Việt; trả về True nếu đã xử lý."""
        raw = (text or "").strip()
        lower = raw.lower()
        mode = self._menu_modes.get(chat_id, "main")

        # Nút chung.
        if lower in ("quay lại", "về menu chính", "menu chính"):
            self._set_menu_mode(chat_id, "main", send_menu=True)
            return True

        if lower == "tài khoản":
            self._set_menu_mode(chat_id, "accounts", send_menu=True)
            return True

        if lower == "trạng thái":
            self._send_status_message(chat_id)
            self._set_menu_mode(chat_id, "main", send_menu=False)
            self.send_message(chat_id, "Bạn có thể tiếp tục chọn chức năng bên dưới.", reply_markup=self.get_main_keyboard(chat_id))
            return True

        if lower == "điều khiển":
            self._set_menu_mode(chat_id, "control", send_menu=True)
            return True

        if lower == "thông tin":
            self._set_menu_mode(chat_id, "info", send_menu=True)
            return True

        if lower == "săn boss":
            self._set_menu_mode(chat_id, "boss", send_menu=True)
            return True

        if lower == "trợ lý ai":
            self.send_message(
                chat_id,
                "Nhập yêu cầu bằng tiếng Việt tự nhiên. Ví dụ:\n"
                "`Cho tài khoản 1 tới map 112, vào khu vắng và bật tàn sát`.\n\n"
                "Bạn cũng có thể dùng `/ai <nội dung>`.",
                reply_markup=self.get_main_keyboard(chat_id),
            )
            return True

        if lower in ("hướng dẫn",):
            self._send_help_message(chat_id)
            self._set_menu_mode(chat_id, "main", send_menu=False)
            self.send_message(chat_id, "Bạn có thể tiếp tục chọn chức năng bên dưới.", reply_markup=self.get_main_keyboard(chat_id))
            return True

        if lower in ("về menu chính",):
            self._set_menu_mode(chat_id, "main", send_menu=True)
            return True

        # Nút chọn tài khoản.
        if lower == "tất cả tài khoản" and mode == "accounts":
            self.selected_targets[chat_id] = None
            self._set_menu_mode(chat_id, "main", send_menu=False)
            self.send_message(chat_id, "Đã chọn phạm vi: *Tất cả tài khoản*.", reply_markup=self.get_main_keyboard(chat_id))
            return True

        m = re.match(r"^tài khoản\s+(\d+):", raw, re.IGNORECASE)
        if m and mode == "accounts":
            acc_id = int(m.group(1))
            inst = self.account_manager.get_account(str(acc_id)) if self.account_manager else None
            if not inst:
                self.send_message(chat_id, f"Không tìm thấy tài khoản {acc_id}.", reply_markup=self.get_main_keyboard(chat_id))
                return True
            self.selected_targets[chat_id] = acc_id
            if inst:
                inst.refresh_info()
            cname = inst.char_name if inst.char_name != "Chưa vào" else inst.config.username
            online = bool(inst.client and inst.client.isConnected())
            state = "Đang online" if online else "Ngoại tuyến"
            self._set_menu_mode(chat_id, "main", send_menu=False)
            self.send_message(
                chat_id,
                f"Đã chọn *Tài khoản {acc_id}*.\n"
                f"Nhân vật: *{cname}*\n"
                f"Trạng thái: *{state}*\n\n"
                "Các lệnh từ menu tiếp theo sẽ áp dụng cho tài khoản này.",
                reply_markup=self.get_main_keyboard(chat_id),
            )
            return True

        # Menu thông tin: Sử dụng trực tiếp các hàm định dạng Telegram đẹp mắt, hỗ trợ tất cả tài khoản
        if mode == "info":
            curr_target = str(self.selected_targets.get(chat_id)) if self.selected_targets.get(chat_id) else None
            if lower == "tổng quan":
                self._send_status_message(chat_id)
                return True
            if lower == "thông tin chi tiết":
                self._send_info_message(chat_id, curr_target)
                return True
            if lower == "balo":
                self._send_bag_message(chat_id, curr_target)
                return True
            if lower == "rương đồ":
                self._send_box_message(chat_id, curr_target)
                return True
            if lower == "đệ tử":
                self._send_pet_message(chat_id, curr_target)
                return True
            if lower == "bản đồ":
                self._send_map_message(chat_id, curr_target)
                return True
            if lower == "khu vực":
                self._send_zone_message(chat_id, curr_target)
                return True
            if lower == "chiến đấu":
                self._send_combat_message(chat_id, curr_target)
                return True
            if lower == "cây đậu":
                self._send_tree_message(chat_id, curr_target)
                return True

        # Menu điều khiển.
        control_commands = {
            "bật tàn sát": "ts on",
            "tắt tàn sát": "ts off",
            "bật tự đánh": "ak on",
            "tắt tự đánh": "ak off",
            "bật săn boss": "hunt on",
            "tắt săn boss": "hunt off",
            "bật tự nhặt đồ": "anhat on",
            "tắt tự nhặt đồ": "anhat off",
            "bật tự hồi sinh": "autohs on",
            "tắt tự hồi sinh": "autohs off",
            "bật auto nhiệm vụ": "nv on",
            "tắt auto nhiệm vụ": "nv off",
            "trạng thái nhiệm vụ": "nv status",
            "thu hoạch đậu": "harvest",
        }
        if mode == "control" and lower in control_commands:
            self._execute_ui_command(chat_id, control_commands[lower])
            return True

        # Menu Boss dùng lệnh cũ để không ảnh hưởng backend.
        if mode == "boss":
            if lower == "xem boss hiện tại":
                self._send_boss_message(chat_id, str(self.selected_targets[chat_id]) if self.selected_targets.get(chat_id) else None, [])
                return True
            if lower == "bật săn boss":
                self._execute_ui_command(chat_id, "hunt on")
                return True
            if lower == "tắt săn boss":
                self._execute_ui_command(chat_id, "hunt off")
                return True
            if lower == "đi tới boss":
                self.send_message(chat_id, "Nhập tên Boss theo cú pháp: `/boss go <tên boss>`", reply_markup=self.get_main_keyboard(chat_id))
                return True

        # Đăng nhập / đăng xuất từ menu hoặc nút bấm bất kỳ chế độ nào.
        if lower in ("đăng nhập tất cả", "dang nhap tat ca", "login all"):
            self._handle_login_cmd(chat_id, "all")
            return True
        if lower in ("đăng xuất tất cả", "dang xuat tat ca", "logout all"):
            self._handle_logout_cmd(chat_id, "all")
            return True

        if lower in ("đăng nhập", "dang nhap") and mode in ("main", "control", "accounts"):
            self._handle_login_cmd(chat_id)
            return True
        if lower in ("đăng xuất", "dang xuat") and mode in ("main", "control", "accounts"):
            self._handle_logout_cmd(chat_id)
            return True

        # Nút tài khoản hiện tại ở menu chính.
        selected = self.selected_targets.get(chat_id)
        if selected is None and lower == "tất cả tài khoản":
            self._set_menu_mode(chat_id, "accounts", send_menu=True)
            return True
        if selected is not None and lower == f"tài khoản {selected}":
            self._set_menu_mode(chat_id, "accounts", send_menu=True)
            return True

        return False

    def _execute_ui_command(self, chat_id: Union[int, str], command: str) -> None:
        """Thực thi một lệnh từ giao diện nút bấm và đưa người dùng về menu phù hợp."""
        self._execute_direct_command(chat_id, command)
        self._set_menu_mode(chat_id, "main", send_menu=False)
        self.send_message(chat_id, "Bạn có thể tiếp tục thao tác bằng menu bên dưới.", reply_markup=self.get_main_keyboard(chat_id))

    # --------------------------------------------------------------------------
    # Các hàm gọi Telegram HTTP API thuần urllib
    # --------------------------------------------------------------------------
    def _api_call(self, method: str, payload: Optional[Dict[str, Any]] = None, timeout: int = 30) -> Optional[Dict[str, Any]]:
        """Gửi yêu cầu HTTP POST tới Telegram Bot API."""
        url = f"https://api.telegram.org/bot{self.token}/{method}"
        data = json.dumps(payload or {}).encode("utf-8") if payload is not None else None
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "ClientNROpy-TelegramBot/1.0",
        }
        try:
            req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                res_bytes = resp.read()
                return json.loads(res_bytes.decode("utf-8"))
        except urllib.error.HTTPError as he:
            err_msg = he.read().decode("utf-8", errors="replace")
            logger.debug(f"[Telegram API Error] {method} HTTP {he.code}: {err_msg}")
            return {"ok": False, "error_code": he.code, "description": err_msg[:300]}
        except Exception as ex:
            logger.debug(f"[Telegram API Error] {method}: {ex}")
            return None

    def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        parse_mode: Optional[str] = "Markdown",
        reply_markup: Optional[Dict[str, Any]] = None,
        with_keyboard: bool = True,
    ) -> bool:
        """Gửi tin nhắn văn bản tới chat_id (tự động đính kèm bàn phím nút bấm chọn acc và lệnh nhanh)."""
        if not text:
            return False

        # Tự động gán bàn phím nút bấm mặc định nếu không chỉ định riêng
        if reply_markup is None and with_keyboard:
            reply_markup = self.get_main_keyboard(chat_id)

        # Chia nhỏ thông minh theo từng dòng để tránh gãy cấu trúc Markdown
        chunks = []
        if len(text) <= 3800:
            chunks.append(text)
        else:
            cur_lines = []
            cur_len = 0
            for line in text.split("\n"):
                line_len = len(line) + 1
                if cur_len + line_len > 3800 and cur_lines:
                    chunks.append("\n".join(cur_lines))
                    cur_lines = [line]
                    cur_len = line_len
                else:
                    cur_lines.append(line)
                    cur_len += line_len
            if cur_lines:
                chunks.append("\n".join(cur_lines))

        success = True
        for i, chunk in enumerate(chunks):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode
            # Chỉ gửi reply_markup ở chunk cuối cùng
            if i == len(chunks) - 1 and reply_markup:
                payload["reply_markup"] = reply_markup

            res = self._api_call("sendMessage", payload, timeout=15)
            if not res or not res.get("ok"):
                # Thử lại không có parse_mode nếu gặp lỗi Markdown entity
                if parse_mode:
                    payload.pop("parse_mode", None)
                    res = self._api_call("sendMessage", payload, timeout=15)
                if not res or not res.get("ok"):
                    success = False
        return success

    def broadcast_message(self, text: str, parse_mode: Optional[str] = "Markdown") -> None:
        """Gửi thông báo tới toàn bộ các chat_id đang hoạt động."""
        with self._lock:
            targets = list(self.active_chat_ids)
        for cid in targets:
            try:
                self.send_message(cid, text, parse_mode=parse_mode, with_keyboard=False)
            except Exception:
                pass

    # --------------------------------------------------------------------------
    # Định dạng chi tiết thông tin nhân vật cho Telegram
    # --------------------------------------------------------------------------
    def format_char_full_info(self, inst) -> str:
        """Tạo báo cáo chi tiết toàn diện 100% mọi thông tin nhân vật, đệ tử, balo, rương, đậu, map, auto."""
        client = inst.client
        if not client or not client.isConnected() or not client.myChar:
            return f"[!] *[{inst.tag}]*: Tài khoản hiện đang OFFLINE hoặc chưa vào bản đồ."

        char = client.myChar
        gender_names = {0: "Trái Đất", 1: "Namếc", 2: "Xayda"}
        gender_str = gender_names.get(char.cgender, "Chưa rõ")
        class_names = {0: "Chiến binh Trái Đất", 1: "Chiến binh Namếc", 2: "Chiến binh Xayda"}
        class_str = class_names.get(char.nClass, f"Hệ phái {char.nClass}")

        # Tình trạng sinh tử
        is_dead = (char.statusMe == 14) or (char.cHP <= 0 and char.cHPFull > 0)
        alive_str = "[!] ĐÃ CHẾT" if is_dead else "[=] CÒN SỐNG"

        hp_pct = round((char.cHP / max(1, char.cHPFull)) * 100, 1)
        mp_pct = round((char.cMP / max(1, char.cMPFull)) * 100, 1)

        map_id = char.mapInfo.mapID if char.mapInfo else -1
        map_name = char.mapInfo.mapName if char.mapInfo and char.mapInfo.mapName else f"Map {map_id}"
        zone_id = char.mapInfo.zoneID if char.mapInfo else -1
        planet_names = {0: "Trái Đất", 1: "Namếc", 2: "Xayda", 3: "Hành tinh khác"}
        map_planet = planet_names.get(char.mapInfo.planetID, "Không rõ") if char.mapInfo else "Không rõ"

        # Nhiệm vụ
        task = getattr(char, "task", None)
        task_name = ""
        task_prog = ""
        if task:
            task_name = getattr(task, "clean_name", "")
            task_prog = getattr(task, "progress_str", "")
        if not task_name:
            raw_task = getattr(char, "task_name", "")
            from .task import clean_task_name
            task_name = clean_task_name(raw_task) if raw_task else ""
        if not task_name and getattr(char, "ctaskId", 0):
            task_name = f"Task ID {char.ctaskId}"

        if task_name and task_prog:
            task_display = f"*{task_name}* | Tiến độ: *{task_prog}*"
        elif task_name:
            task_display = f"*{task_name}*"
        elif task_prog:
            task_display = f"*{task_prog}*"
        else:
            task_display = "*Chưa có*"

        # Kỹ năng
        skills_str = ", ".join([get_skill_display_name(sk) for sk in char.skills]) if char.skills else "Chưa có kỹ năng đặc biệt"

        lines = [
            f"= *THÔNG TIN CHI TIẾT TÀI KHOẢN [{inst.tag} - SM: {inst.power_str}]*",
            f"=============================",
            f"> *1. THÔNG TIN BẢN THÂN (CHARACTER):*",
            f"> Tên nhân vật:    *{char.cName}* (ID: `{char.charID}`) | Sức mạnh: *{inst.power_str}*",
            f"> Hành tinh:       *{gender_str}* | Lớp: `{class_str}`",
            f"> Trạng thái:      *{alive_str}* | Kết nối: *{inst.status}*",
            f"> = *TÀI SẢN TIỀN TỆ:*",
            f"  > Vàng (Xu):       *{format_compact_number(char.xu)} Xu* ({char.xu:,} Xu)",
            f"  > Ngọc xanh:       *{format_compact_number(char.luong)} Ngọc*",
            f"  > Hồng ngọc:       *{format_compact_number(char.luongKhoa)} Ngọc khóa*",
            f"> = *CHỈ SỐ CHIẾN ĐẤU:*",
            f"  > HP (Máu):        *{format_compact_number(char.cHP)} / {format_compact_number(char.cHPFull)}* ({hp_pct}%)",
            f"  > KI / MP (Nội lực): *{format_compact_number(char.cMP)} / {format_compact_number(char.cMPFull)}* ({mp_pct}%)",
            f"  > Sức mạnh:        *{char.cPower:,} ({format_big_number(char.cPower)})*",
            f"  > Tiềm năng:       *{char.cTiemNang:,} ({format_big_number(char.cTiemNang)})*",
            f"  > Sức đánh (Dam):  *{format_compact_number(char.cDamFull)}* (Gốc: `{format_compact_number(char.cDamGoc)}`)",
            f"  > Giáp (Def):      *{format_compact_number(char.cDefull)}* (Gốc: `{format_compact_number(char.cDefGoc)}`)",
            f"  > Chí mạng (Crit): *{char.cCriticalFull}%* (Gốc: `{char.cCriticalGoc}%`)",
            f"  > Tốc độ chạy:     *{char.cspeed}*",
            f"> Nhiệm vụ:        {task_display}",
            f"> Chiêu thức ({len(char.skills)}): `{skills_str}`",
        ]

        # 2. Đệ tử (Pet)
        lines.append(f"\n= *2. ĐỆ TỬ / PET:*")
        pet = char.pet
        if pet and pet.havePet:
            p_name = pet.cName if pet.cName else "Đệ tử"
            pet_hp_pct = round((pet.cHP / max(1, pet.cHPFull)) * 100, 1)
            pet_mp_pct = round((pet.cMP / max(1, pet.cMPFull)) * 100, 1)
            pet_sta_pct = round((pet.cStamina / max(1, pet.cMaxStamina)) * 100, 1) if pet.cMaxStamina > 0 else 0
            pet_skills = ", ".join([get_skill_display_name(sk) for sk in pet.arrPetSkill]) if pet.arrPetSkill else "Chưa mở kỹ năng"

            lines.append(f"> Tên đệ tử:       *{p_name}* (Trạng thái: *{pet.statusName}*)")
            lines.append(f"> HP (Máu đệ):     *{format_compact_number(pet.cHP)} / {format_compact_number(pet.cHPFull)}* ({pet_hp_pct}%)")
            lines.append(f"> KI / MP:         *{format_compact_number(pet.cMP)} / {format_compact_number(pet.cMPFull)}* ({pet_mp_pct}%)")
            lines.append(f"> Sức đánh:        *{format_compact_number(pet.cDamFull)}* | Giáp: *{format_compact_number(pet.cDefull)}* | Chí mạng: *{pet.cCriticalFull}%*")
            lines.append(f"> Sức mạnh:        *{pet.cPower:,} ({format_big_number(pet.cPower)})* | Tiềm năng: *{pet.cTiemNang:,} ({format_big_number(pet.cTiemNang)})*")
            lines.append(f"> Thể lực:         *{format_compact_number(pet.cStamina)} / {format_compact_number(pet.cMaxStamina)}* ({pet_sta_pct}%)")
            lines.append(f"> Kỹ năng đệ:      `{pet_skills}`")
            lines.append(f"> Trang bị đệ:     *{len(pet.arrItemBody)}* món trang bị")
        else:
            lines.append("> Hiện tại nhân vật chưa có đệ tử.")

        # 3. Bản đồ & Khu vực (Zone)
        lines.append(f"\n= *3. BẢN ĐỒ & VỊ TRÍ:*")
        num_players = len(char.mapInfo.chars) if char.mapInfo and char.mapInfo.chars else 0
        zone_player_str = ""
        if char.mapInfo and char.mapInfo.zones:
            for z in char.mapInfo.zones:
                if z.zoneId == zone_id:
                    zone_player_str = f" ({z.numPlayer}/{z.maxPlayer} người)"
                    break
        lines.append(f"> Bản đồ:          *{map_name}* (ID: `{map_id}`, Hành tinh: *{map_planet}*)")
        lines.append(f"> Khu vực (Zone):  *Khu {zone_id:02d}*{zone_player_str}")
        lines.append(f"> Tọa độ nhân vật: X: `{char.cx}`, Y: `{char.cy}`")
        if char.mapInfo and char.mapInfo.chars:
            c_sample = [f"`{c.cName}`" for c in list(char.mapInfo.chars.values())[:6]]
            lines.append(f"> Người trong khu: {', '.join(c_sample)} (tổng {num_players} người)")
        else:
            lines.append(f"> Người trong khu: Không có người chơi khác.")

        # Cây đậu thần
        tree = char.magicTree
        if tree:
            sec_str = f"Chín sau {tree.seconds}s ({int(tree.seconds/60)} phút)" if tree.seconds > 0 else "Đậu đã chín đầy đủ!"
            pea_pct = round((tree.currPeas / max(1, tree.maxPeas)) * 100, 1)
            lines.append(f"> Cây đậu Cấp {tree.level}: *{tree.currPeas} / {tree.maxPeas}* hạt ({pea_pct}%) - {sec_str}")

        # 4. Hành trang & Rương đồ (Tóm tắt gọn gàng - KHÔNG in chi tiết từng món để tránh dài dòng)
        bag = char.arrItemBag
        box = char.arrItemBox
        lines.append(f"\n= *4. HÀNH TRANG & RƯƠNG ĐỒ:*")
        lines.append(f"> Balo:    *{len(bag)}* món (Dùng `/item <id|tên>` để kiểm tra đồ hoặc `/bag` để xem)")
        lines.append(f"> Rương:   *{len(box)}* món (Dùng `/box` để xem chi tiết)")

        # 5. Tiến độ Săn Boss (Hiển thị nổi bật nếu đang bật hunt hoặc đã diệt boss)
        bh = getattr(client, "boss_hunter", None)
        is_hunting = getattr(bh, "is_hunting", False) if bh else False
        kills = getattr(bh, "boss_kill_count", 0) if bh else 0
        loots = getattr(bh, "boss_looted_items_count", 0) if bh else 0

        if is_hunting or kills > 0 or loots > 0:
            lines.append(f"\n= *5. TIẾN ĐỘ SĂN BOSS:*")
            state_names = {
                "IDLE": "[=] Đang chờ thông báo Boss mới" if is_hunting else "[ ] Đã dừng săn",
                "MOVING": "[>] Đang di chuyển tới map Boss",
                "SEARCHING": "[*] Đang tìm kiếm & quét khu vực",
                "COMBAT": "[!] Đang chiến đấu tiêu diệt Boss",
                "LOOTING": "[+] Đang nhặt đồ rơi",
            }
            curr_state = getattr(bh, "bh_state", "IDLE")
            state_desc = state_names.get(curr_state, curr_state)
            lines.append(f"> Trạng thái săn:   *{state_desc}*")

            # Mục tiêu hiện tại
            curr_b = getattr(bh, "current_boss", None)
            if curr_b:
                b_map = curr_b.map_name or get_map_name(curr_b.map_id)
                z_txt = f" (Khu {curr_b.zone_id:02d})" if getattr(curr_b, "zone_id", -1) >= 0 else " (Đang tìm khu)"
                lines.append(f"> Mục tiêu hiện tại: *{curr_b.name}* tại *{b_map}*{z_txt}")
            else:
                lines.append(f"> Mục tiêu hiện tại: Chưa có (Đang quét khu hoặc chờ Boss)")

            status_msg = getattr(bh, "bh_status_message", "") or "Đang hoạt động"
            lines.append(f"> Đang làm gì:      _{status_msg}_")
            lines.append(f"> Boss đã tiêu diệt: *{kills}* con")
            lines.append(f"> Đồ farm được:     *{loots}* vật phẩm")

            # Combo 3 Skill Pem
            combo_sids = getattr(bh, "combat_combo_skills", None) or (getattr(bh, "_get_tansat_skill_ids", lambda: (0, 2, 4))() if hasattr(bh, "_get_tansat_skill_ids") else (0, 2, 4))
            combo_names = [f"{s} ({get_skill_display_name(s)})" for s in combo_sids]
            lines.append(f"> Combo Skill Pem:  *{' -> '.join(combo_names)}*")

            # Lịch sử tiêu diệt gần nhất
            b_history = getattr(bh, "boss_kill_history", [])
            if b_history:
                lines.append(f"> Boss hạ gần đây:")
                for h in b_history[-3:]:
                    lines.append(f"  *{h['name']}* tại {h.get('map_name', '')} ({h.get('time', '')})")

            # Chiến lợi phẩm nhặt từ Boss gần nhất
            looted_items = getattr(bh, "boss_looted_items_history", [])
            if looted_items:
                lines.append(f"> Đồ nhặt từ Boss gần đây:")
                for it in looted_items[-3:]:
                    lines.append(f"  {it.get('time', '')}: *{it.get('item_name', '')}* ({it.get('boss_name', '')})")

        # 6. Cấu hình Auto & Hệ thống
        lines.append(f"\n= *6. CẤU HÌNH AUTO & HỆ THỐNG:*")
        cbm = getattr(client, "combat_manager", None)
        rec_str = f"BẬT ({int(self.account_manager.reconnect_delay)}s)" if (self.account_manager and self.account_manager.auto_reconnect) else "TẮT"
        arm = getattr(client, "auto_revive_manager", None)
        aqm = getattr(client, "auto_quest_manager", None)

        is_ak = getattr(cbm, "is_ak", False) if cbm else False
        is_ts = getattr(cbm, "is_tansat", False) if cbm else False
        ts_mode = getattr(cbm, "tansat_mode", "mob") if cbm else "mob"
        auto_pick = getattr(cbm, "auto_pick", False) if cbm else False
        pick_gem = getattr(cbm, "pick_gem_only", False) if cbm else False
        avoid_mob = getattr(cbm, "avoid_super_mob", False) if cbm else False
        auto_pean = getattr(cbm, "auto_pean", False) if cbm else False
        pean_pct = int(getattr(cbm, "pean_threshold", 0.3) * 100) if cbm else 30
        arm_on = getattr(arm, "is_enabled", False) if arm else False
        arm_mode = getattr(arm, "mode", "gem") if arm else "gem"
        aqm_on = getattr(aqm, "is_running", False) if aqm else False

        lines.append(f"> Săn Boss (Hunt): {'[=] BẬT' if is_hunting else '[ ] TẮT'}")
        lines.append(f"> Tự Đánh (AK):    {'[=] BẬT' if is_ak else '[ ] TẮT'}")
        lines.append(f"> Tàn Sát (TS):    {'[=] BẬT' if is_ts else '[ ] TẮT'} (Chế độ: `{ts_mode}`)")
        lines.append(f"> Tự Nhặt Đồ:      {'[=] BẬT' if auto_pick else '[ ] TẮT'}{' (Chỉ ngọc)' if pick_gem else ''}")
        lines.append(f"> Né Siêu Quái:    {'[=] BẬT' if avoid_mob else '[ ] TẮT'}")
        lines.append(f"> Tự Ăn Đậu (ABF): {'[=] BẬT' if auto_pean else '[ ] TẮT'} (khi < {pean_pct}%)")
        lines.append(f"> Tự Hồi Sinh:     {'[=] BẬT' if arm_on else '[ ] TẮT'} (Mode: `{arm_mode}`)")
        lines.append(f"> Auto NV Bò Mộng: {'[=] BẬT' if aqm_on else '[ ] TẮT'}")
        lines.append(f"> Auto-Reconnect:  *{rec_str}* | Proxy: *{inst.proxy_str}*")

        lines.append(f"=============================")
        lines.append(f"> *Lệnh nhanh:* `/item 14` > `/map` > `/zone min` > `/hunt on` > `/ts on` > `/harvest`")

        return "\n".join(lines)

    def format_char_bag_info(self, inst) -> str:
        """Định dạng toàn bộ 100% vật phẩm trong balo."""
        client = inst.client
        if not client or not client.isConnected() or not client.myChar:
            return f"[!] *[{inst.tag}]*: Tài khoản chưa vào map."
        char = client.myChar
        bag = char.arrItemBag
        lines = [
            f"= *HÀNH TRANG BALO [{inst.tag}]* (Tổng cộng: *{len(bag)} món*)",
            f"=============================",
        ]
        if not bag:
            lines.append("Balo hiện đang trống.")
            return "\n".join(lines)

        for i, it in enumerate(bag):
            it_name = get_item_display_name(it.template_id, it.info)
            opts = " | ".join([opt.getText() for opt in it.options])
            opt_str = f"\n   | *Chỉ số:* _{opts}_" if opts else ""
            desc_str = f"\n   | *Ghi chú:* {it.content}" if (it.content and it.content != it_name) else ""
            lines.append(f"`{i+1:02d}.` = *{it_name}* x{it.quantity} (ID: `{it.template_id}`){opt_str}{desc_str}")
        return "\n".join(lines)

    def format_char_box_info(self, inst) -> str:
        """Định dạng toàn bộ 100% vật phẩm trong rương đồ."""
        client = inst.client
        if not client or not client.isConnected() or not client.myChar:
            return f"[!] *[{inst.tag}]*: Tài khoản chưa vào map."
        char = client.myChar
        box = char.arrItemBox
        lines = [
            f"= *RƯƠNG ĐỒ [{inst.tag}]* (Tổng cộng: *{len(box)} món*)",
            f"=============================",
        ]
        if not box:
            lines.append("Rương đồ hiện đang trống.")
            return "\n".join(lines)

        for i, it in enumerate(box):
            it_name = get_item_display_name(it.template_id, it.info)
            opts = " | ".join([opt.getText() for opt in it.options])
            opt_str = f"\n   | *Chỉ số:* _{opts}_" if opts else ""
            desc_str = f"\n   | *Ghi chú:* {it.content}" if (it.content and it.content != it_name) else ""
            lines.append(f"`{i+1:02d}.` = *{it_name}* x{it.quantity} (ID: `{it.template_id}`){opt_str}{desc_str}")
        return "\n".join(lines)

    def format_char_pet_info(self, inst) -> str:
        """Định dạng chi tiết toàn bộ về đệ tử."""
        client = inst.client
        if not client or not client.isConnected() or not client.myChar:
            return f"[!] *[{inst.tag}]*: Tài khoản chưa vào map."
        pet = client.myChar.pet
        if not pet or not pet.havePet:
            return f"= *[{inst.tag}]*: Nhân vật chưa có đệ tử."

        pet_hp_pct = round((pet.cHP / max(1, pet.cHPFull)) * 100, 1)
        pet_mp_pct = round((pet.cMP / max(1, pet.cMPFull)) * 100, 1)
        pet_sta_pct = round((pet.cStamina / max(1, pet.cMaxStamina)) * 100, 1) if pet.cMaxStamina > 0 else 0
        pet_skills = ", ".join([get_skill_display_name(sk) for sk in pet.arrPetSkill]) if pet.arrPetSkill else "Chưa có kỹ năng"

        lines = [
            f"= *THÔNG TIN CHI TIẾT ĐỆ TỬ / PET [{inst.tag}]*",
            f"=============================",
            f"> Tên đệ tử:       *{pet.cName}*",
            f"> Trạng thái:      *{pet.statusName}* (Code: `{pet.petStatus}`)",
            f"> HP (Máu):        *{format_compact_number(pet.cHP)} / {format_compact_number(pet.cHPFull)}* ({pet_hp_pct}%)",
            f"> KI / MP:         *{format_compact_number(pet.cMP)} / {format_compact_number(pet.cMPFull)}* ({pet_mp_pct}%)",
            f"> Sức đánh:        *{format_compact_number(pet.cDamFull)}*",
            f"> Giáp:            *{format_compact_number(pet.cDefull)}*",
            f"> Chí mạng:        *{pet.cCriticalFull}%*",
            f"> Sức mạnh:        *{format_compact_number(pet.cPower)}*",
            f"> Tiềm năng:       *{format_compact_number(pet.cTiemNang)}*",
            f"> Thể lực:         *{format_compact_number(pet.cStamina)} / {format_compact_number(pet.cMaxStamina)}* ({pet_sta_pct}%)",
            f"> Kỹ năng đã học:  `{pet_skills}`",
            f"> Trang bị đệ tử:  *{len(pet.arrItemBody)}* món trang bị",
        ]
        if pet.arrItemBody:
            lines.append(f"\n= *Chi tiết trang bị đệ:*")
            for idx, it in enumerate(pet.arrItemBody):
                slot_title = BODY_SLOT_NAMES.get(idx, f"Món {idx+1}")
                it_name = get_item_display_name(it.template_id, it.info)
                opts = " | ".join([opt.getText() for opt in it.options])
                opt_str = f" - _{opts}_" if opts else ""
                lines.append(f"`{idx+1}.` [{slot_title}] *{it_name}*{opt_str}")

        lines.append(f"=============================")
        lines.append(f"> *Đổi trạng thái đệ tử:*")
        lines.append(f"> `/pet follow` : Đệ tử Đi theo")
        lines.append(f"> `/pet protect` : Đệ tử Bảo vệ")
        lines.append(f"> `/pet attack` : Đệ tử Tấn công")
        lines.append(f"> `/pet home` : Đệ tử Về nhà")
        lines.append(f"> `/pet fuse` : Hợp thể thường")
        lines.append(f"> `/pet porata` : Hợp thể bông tai Porata")
        return "\n".join(lines)

    def format_char_map_info(self, inst) -> str:
        """Định dạng thông tin bản đồ, khu vực và người chơi trong khu."""
        client = inst.client
        if not client or not client.isConnected() or not client.myChar:
            return f"[!] *[{inst.tag}]*: Tài khoản chưa vào map."
        m = client.myChar.mapInfo
        planet_names = {0: "Trái Đất", 1: "Namếc", 2: "Xayda", 3: "Hành tinh khác"}
        planet_str = planet_names.get(m.planetID, f"Hành tinh {m.planetID}")
        lines = [
            f"= *BẢN ĐỒ & KHU VỰC [{inst.tag}]*",
            f"=============================",
            f"> Bản đồ: *{m.mapName}* (ID: `{m.mapID}`, {planet_str})",
            f"> Khu vực hiện tại: *Khu {m.zoneID:02d}*",
            f"> Tọa độ nhân vật: `({client.myChar.cx}, {client.myChar.cy})`",
        ]
        if m.zones:
            lines.append(f"\n= *Danh sách khu vực ({len(m.zones)} khu):*")
            z_strs = []
            for z in m.zones:
                curr = "=" if z.zoneId == m.zoneID else ""
                z_strs.append(f"K{z.zoneId:02d}:{z.numPlayer}/{z.maxPlayer}{curr}")
            lines.append(" | ".join(z_strs[:15]))
            if len(m.zones) > 15:
                lines.append(" | ".join(z_strs[15:30]))
        if m.chars:
            lines.append(f"\n> *Người chơi cùng khu ({len(m.chars)} người):*")
            c_list = [f"`{c.cName}` (HP: {c.cHP:,})" for c in list(m.chars.values())[:8]]
            lines.append(", ".join(c_list))
        return "\n".join(lines)

    def format_char_combat_info(self, inst) -> str:
        """Định dạng cấu hình chiến đấu và luyện tập."""
        client = inst.client
        if not client or not client.isConnected():
            return f"[!] *[{inst.tag}]*: Tài khoản chưa online."
        st = client.combat_status()
        cbm = client.combat_manager
        lines = [
            f"= *CẤU HÌNH CHIẾN ĐẤU & LUYỆN TẬP [{inst.tag}]*",
            f"=============================",
            f"> Tự động đánh (AK):     {'[=] BẬT [ON]' if st['is_ak'] else '[ ] TẮT [OFF]'}",
            f"> Tàn sát quái (TS):     {'[=] BẬT [ON]' if st['is_tansat'] else '[ ] TẮT [OFF]'} (Chế độ: `{st['tansat_mode']}`)",
            f"> Tự động nhặt đồ:       {'[=] BẬT [ON]' if st['auto_pick'] else '[ ] TẮT [OFF]'}",
            f"> Chỉ nhặt ngọc:         {'[=] BẬT [ON]' if st['pick_gem_only'] else '[ ] TẮT [OFF]'}",
            f"> Né siêu quái (NSQ):    {'[=] BẬT [ON]' if cbm.avoid_super_mob else '[ ] TẮT [OFF]'}",
            f"> Tự dùng đậu (ABF):     {'[=] BẬT [ON]' if st['auto_pean'] else '[ ] TẮT [OFF]'} (Khi HP/KI < {int(cbm.pean_threshold*100)}%)",
            f"> Tự hồi sinh (AutoHS):  {'[=] BẬT [ON]' if client.auto_revive_manager.is_enabled else '[ ] TẮT [OFF]'} (Mode: `{client.auto_revive_manager.mode}`)",
            f"> Auto NV Bò Mộng:       {'[=] BẬT [ON]' if client.auto_quest_manager.is_running else '[ ] TẮT [OFF]'}",
            f"=============================",
            f"> *Lệnh thao tác:* `/ak on|off` > `/ts on|off` > `/anhat` > `/cnn` > `/nsq` > `/abf 50` > `/autohs on|off`",
        ]
        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # Gọi AI OpenRouter API thuần urllib với Real-time Context & Memory
    # --------------------------------------------------------------------------
    def query_openrouter_ai(self, user_prompt: str, chat_id: Optional[Union[int, str]] = None) -> str:
        """Gửi câu hỏi và toàn bộ ngữ cảnh game chi tiết thời gian thực tới OpenRouter AI."""
        if not self.ai_api_key:
            return "Trợ lý AI chưa được cấu hình API Key OpenRouter trong settings.json."

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.ai_api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/ClientNROpy",
            "X-Title": "ClientNROpy Assistant",
            "User-Agent": "ClientNROpy/1.0",
        }

        # Xây dựng ngữ cảnh chi tiết toàn diện theo thời gian thực (real-time)
        game_status_summary = self._build_game_state_summary(chat_id)

        full_system_prompt = (
            f"{self.ai_system_prompt}\n\n"
            f"=== THÔNG TIN TÀI KHOẢN GAME HIỆN TẠI (THỜI GIAN THỰC) ===\n"
            f"{game_status_summary}\n\n"
            f"=== DANH SÁCH LỆNH GAME CÓ THỂ ĐIỀU KHIỂN ===\n"
            f"- all hunt on / all hunt off : Bật/Tắt Auto Săn Boss cho toàn bộ acc\n"
            f"- all xmap <map_id> : Di chuyển toàn bộ acc đến map (vd: all xmap 0)\n"
            f"- acc <id> xmap <map_id> : Cho acc cụ thể di chuyển map (vd: acc 1 xmap 0 là về nhà)\n"
            f"- acc <id> goto <map> [min|khu] [ts|ak|hunt] : Tới map + đổi khu + bật auto (vd: acc 2 goto 112 min ts)\n"
            f"- acc <username> ... : Có thể dùng username thay id (vd: acc poopooi02 goto 112 min ts)\n"
            f"- acc <id> zone <khu|min> : Đổi khu cho acc (vd: acc 1 zone 5, acc 1 zone min là khu vắng nhất)\n"
            f"- acc <id> hunt on / off : Bật/tắt săn boss riêng 1 acc\n"
            f"- acc <id> autohs on / off : Bật/tắt tự hồi sinh\n"
            f"- acc <id> ak on / off : Bật/tắt tự đánh mục tiêu\n"
            f"- acc <id> ts on / off : Bật/tắt tàn sát quái\n"
            f"- anhat : Bật/tắt tự nhặt đồ\n"
            f"- reconnect now : Kết nối lại toàn bộ tài khoản ngay\n"
            f"- harvest : Thu hoạch đậu thần\n"
            f"- all pet <follow|protect|attack|home|fuse|porata> : Đổi trạng thái đệ tử\n"
            f"LƯU Ý: Nếu người dùng muốn thực hiện hành động, hãy giải thích ngắn gọn và chèn thẻ [EXEC: <lệnh>] ở cuối câu."
        )

        system_msg = {"role": "system", "content": full_system_prompt}
        recent_history = self._chat_histories.get(chat_id, [])[-8:] if chat_id else []
        messages = [system_msg] + recent_history + [{"role": "user", "content": user_prompt}]

        payload = {
            "model": self.ai_model,
            "messages": messages,
            "max_tokens": 800,
        }

        try:
            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=25) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                choices = data.get("choices", [])
                if choices:
                    msg_obj = choices[0].get("message", {})
                    content = msg_obj.get("content")
                    if content and content.strip():
                        reply_text = content.strip()
                    else:
                        reasoning = msg_obj.get("reasoning")
                        reply_text = reasoning.strip() if reasoning else "AI không trả lời được câu hỏi này."

                    # Lưu hội thoại vào memory
                    if chat_id:
                        if chat_id not in self._chat_histories:
                            self._chat_histories[chat_id] = []
                        self._chat_histories[chat_id].append({"role": "user", "content": user_prompt})
                        clean_ai = re.sub(r"\[EXEC:\s*(.+?)\]", "", reply_text).strip()
                        self._chat_histories[chat_id].append({"role": "assistant", "content": clean_ai})
                        if len(self._chat_histories[chat_id]) > 16:
                            self._chat_histories[chat_id] = self._chat_histories[chat_id][-16:]

                    return reply_text

                return "AI không trả lời được câu hỏi này. Vui lòng thử lại."
        except urllib.error.HTTPError as he:
            err_content = he.read().decode("utf-8", errors="replace")
            logger.debug(f"[OpenRouter HTTP Error] {he.code}: {err_content}")
            return f"Lỗi gọi AI OpenRouter (HTTP {he.code}): {err_content[:200]}"
        except Exception as ex:
            logger.debug(f"[OpenRouter Error] {ex}")
            return f"Lỗi kết nối AI: {ex}"

    def _build_game_state_summary(self, chat_id: Optional[Union[int, str]] = None) -> str:
        """Tạo chuỗi tóm tắt trạng thái chi tiết thời gian thực của các tài khoản game cho AI."""
        if not self.account_manager or not self.account_manager.accounts:
            return "Chưa có tài khoản nào được nạp."

        selected = self.selected_targets.get(chat_id) if chat_id else None
        now_str = time.strftime("%H:%M:%S ngày %d/%m/%Y")

        lines = [
            f"Thời gian hiện tại: {now_str}",
        ]
        if selected is None:
            lines.append("Người dùng đang chọn ngữ cảnh: [TOÀN BỘ TÀI KHOẢN (ALL)]")
        else:
            target_inst = self._resolve_account(str(selected))
            target_name = target_inst.char_name if target_inst else f"Acc #{selected}"
            lines.append(f"Người dùng đang chọn điều khiển riêng tài khoản: [Acc #{selected}: {target_name}]")

        lines.append("\n--- CHI TIẾT TỪNG TÀI KHOẢN ---")
        for a in self.account_manager.accounts:
            st = a.status
            cname = a.char_name
            hp = a.hp_str
            mz = a.map_zone_str
            auto = a.auto_status_str
            char = a.client.myChar if a.client else None

            parts = [f"Acc #{a.config.acc_id} (user: '{a.config.username}') - NV: '{cname}'"]
            parts.append(f"Trạng thái: {st}")
            parts.append(f"HP: {hp}")
            if char:
                hp_pct = round((char.cHP / max(1, char.cHPFull)) * 100, 1)
                mp_pct = round((char.cMP / max(1, char.cMPFull)) * 100, 1)
                parts.append(f"HP%: {hp_pct}%")
                parts.append(f"MP: {char.cMP:,}/{char.cMPFull:,} ({mp_pct}%)")
                parts.append(f"Sức mạnh: {char.cPower:,} ({format_big_number(char.cPower)})")
                parts.append(f"Tiềm năng: {char.cTiemNang:,} ({format_big_number(char.cTiemNang)})")
                parts.append(f"Sức đánh: {char.cDamFull:,} (Gốc: {char.cDamGoc:,})")
                parts.append(f"Giáp: {char.cDefull:,} | Crit: {char.cCriticalFull}%")
                parts.append(f"Vàng: {char.xu:,} xu ({format_big_number(char.xu)} Xu)")
                parts.append(f"Ngọc: {char.luong:,} xanh, {char.luongKhoa:,} hồng")
                parts.append(f"Vị trí: {mz} (tọa độ X={char.cx}, Y={char.cy})")
                task = getattr(char, "task", None)
                if task:
                    task_desc = task.full_display
                else:
                    raw_task = getattr(char, "task_name", "")
                    from .task import clean_task_name
                    c_name = clean_task_name(raw_task) if raw_task else ""
                    task_desc = c_name or f"Task ID {char.ctaskId}"
                parts.append(f"Nhiệm vụ: {task_desc}")

                # Chi tiết balo
                bag = char.arrItemBag
                parts.append(f"Balo: {len(bag)} món")
                if bag:
                    top_items = [f"{get_item_display_name(it.template_id, it.info)} x{it.quantity}" for it in bag[:6]]
                    parts.append(f"Vật phẩm trong balo: {', '.join(top_items)}")

                # Chi tiết đệ tử
                if char.pet and char.pet.havePet:
                    p = char.pet
                    p_hp_pct = round((p.cHP / max(1, p.cHPFull)) * 100, 1)
                    parts.append(f"Đệ tử: '{p.cName}' (HP: {p.cHP:,}/{p.cHPFull:,} [{p_hp_pct}%], Dam: {p.cDamFull:,}, Trạng thái: {p.statusName})")
                    if p.arrPetSkill:
                        p_skills = [get_skill_display_name(sk) for sk in p.arrPetSkill]
                        parts.append(f"Chiêu đệ tử: {', '.join(p_skills)}")
                else:
                    parts.append("Đệ tử: Chưa có")

                # Chi tiết cây đậu thần
                if char.magicTree:
                    t = char.magicTree
                    sec_info = f"chín sau {t.seconds}s" if t.seconds > 0 else "đậu đã chín đầy đủ"
                    parts.append(f"Cây đậu: Cấp {t.level} ({t.currPeas}/{t.maxPeas} hạt, {sec_info})")

            # Cấu hình auto
            if a.client:
                auto_str = a.client.auto.get_active_summary_str()
                parts.append(f"Auto đang bật: {auto_str}")

            lines.append("> " + " | ".join(parts))

        # Thông tin Boss đang xuất hiện hoặc theo dõi
        lines.append("\n--- THÔNG TIN BOSS HIỆN TẠI ---")
        boss_tracked = []
        for a in self.account_manager.accounts:
            if a.client and hasattr(a.client, "boss_manager"):
                alive = a.client.boss_manager.get_alive_bosses()
                for b in alive[:5]:
                    b_str = f"{b.get('name')} (tại {b.get('map_name')})"
                    if b_str not in boss_tracked:
                        boss_tracked.append(b_str)
        if boss_tracked:
            lines.append(f"Boss đang xuất hiện: {', '.join(boss_tracked)}")
        else:
            lines.append("Hiện tại chưa ghi nhận Boss nào đang xuất hiện.")

        return "\n".join(lines)

    # --------------------------------------------------------------------------
    # Xử lý tin nhắn và phân tích lệnh
    # --------------------------------------------------------------------------
    def _try_delete_message(self, chat_id: Union[int, str], message_id: Any) -> None:
        """Xóa tin nhắn người dùng (dùng sau lệnh chứa mật khẩu). Thất bại thì bỏ qua."""
        if not message_id:
            return
        try:
            self._api_call("deleteMessage", {"chat_id": chat_id, "message_id": message_id}, timeout=10)
        except Exception:
            pass

    def _handle_incoming_message(self, message: Dict[str, Any]) -> None:
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = (message.get("text") or "").strip()
        msg_id = message.get("message_id")

        if not chat_id or not text:
            return

        # Kiểm tra danh sách allowed_chat_ids (nếu cấu hình rỗng thì cho phép tất cả)
        if self.allowed_chat_ids:
            if chat_id not in self.allowed_chat_ids and str(chat_id) not in self.allowed_chat_ids:
                self.send_message(chat_id, "[!] Bạn không có quyền điều khiển bot này.", with_keyboard=False)
                return

        # Đưa vào danh sách active để nhận broadcast
        with self._lock:
            self.active_chat_ids.add(chat_id)

        # ----------------------------------------------------------------------
        # A. Xử lý giao diện nút bấm tiếng Việt.
        # Ưu tiên nút bấm trước khi phân tích cú pháp lệnh CLI.
        # ----------------------------------------------------------------------
        if self._handle_menu_button(chat_id, text):
            return

        # ----------------------------------------------------------------------
        # A2. Tương thích ngược với các nút kiểu cũ nếu còn trong client Telegram.
        # ----------------------------------------------------------------------
        # Nút "Đang thực hiện: Tất cả [ALL]" (chọn ngữ cảnh ALL)
        if "tất cả [all]" in text.lower() or "tất cả (all)" in text.lower():
            self.selected_targets[chat_id] = None
            self.send_message(
                chat_id,
                "= Đã chuyển ngữ cảnh sang: *TOÀN BỘ TÀI KHOẢN [ALL]*!\n"
                "Mọi lệnh tiếp theo (`/info`, `/goto`, `/hunt`, `/harvest`...) sẽ áp dụng cho tất cả tài khoản.",
                reply_markup=self.get_main_keyboard(chat_id)
            )
            return

        # Nút "Đang bật Acc #1: tên" (chọn 1 acc, có thể kèm dấu ">" khi đang chọn)
        acc_match = re.search(r"acc\s*#(\d+)", text, re.IGNORECASE)
        if acc_match and "acc #" in text.lower():
            acc_id = int(acc_match.group(1))
            inst = self.account_manager.get_account(str(acc_id)) if self.account_manager else None
            if not inst:
                self.send_message(chat_id, f"[x] Không tìm thấy Acc #{acc_id}. Gõ `/status` để xem danh sách.")
                return
            cname = inst.char_name if inst.char_name != "Chưa vào" else inst.config.username
            online = bool(inst.client and inst.client.isConnected())
            self.selected_targets[chat_id] = acc_id

            if not online:
                card = (
                    f"> *ĐÃ CHỌN TÀI KHOẢN: Acc #{acc_id} ({cname})* Ngoại tuyến\n"
                    f"=============================\n"
                    f"[!] Tài khoản hiện đang ngắt kết nối.\n"
                    f"> Gõ `/login` để kết nối vào game ngay!"
                )
            else:
                char = inst.client.myChar if inst.client else None
                if char:
                    hp_pct = round((char.cHP / max(1, char.cHPFull)) * 100, 1)
                    mp_pct = round((char.cMP / max(1, char.cMPFull)) * 100, 1)
                    gender_str = GENDER_NAMES.get(char.cgender, "Chưa rõ")
                    map_name = char.mapInfo.mapName if (char.mapInfo and char.mapInfo.mapName) else "Chưa rõ"
                    zone_id = char.mapInfo.zoneID if char.mapInfo else -1

                    auto_str = inst.client.auto.get_active_summary_str()
                    if auto_str == "Không":
                        auto_str = "Không bật"

                    card = (
                        f"> *ĐÃ CHỌN TÀI KHOẢN: Acc #{acc_id} ({cname})* Đang online\n"
                        f"=============================\n"
                        f"> Nhân vật:       *{cname}* ({gender_str}) | SM: *{inst.power_str}*\n"
                        f"> HP:             *{format_compact_number(char.cHP)} / {format_compact_number(char.cHPFull)}* ({hp_pct}%) | KI: *{format_compact_number(char.cMP)}* ({mp_pct}%)\n"
                        f"> Vị trí:         *{map_name}* (Khu {zone_id:02d}) | X: `{char.cx}`, Y: `{char.cy}`\n"
                        f"> Tiền tệ:        *{format_compact_number(char.xu)} Xu* | *{format_compact_number(char.luong)}* Ngọc\n"
                        f"> Auto hiện tại:  *{auto_str}*\n"
                        f"=============================\n"
                        f"> *Lệnh nhanh:* `/info` > `/zone min` > `/ts on` > `/harvest` > `/item 14`"
                    )
                else:
                    card = (
                        f"> *ĐÃ CHỌN TÀI KHOẢN: Acc #{acc_id} ({cname})* Đang online\n"
                        f"=============================\n"
                        f"> Đang đồng bộ dữ liệu nhân vật...\n"
                        f"> *Lệnh nhanh:* `/info` > `/status` > `/map`"
                    )
            self.send_message(chat_id, card, reply_markup=self.get_main_keyboard(chat_id))
            return

        # ----------------------------------------------------------------------
        # B. Các lệnh menu & hướng dẫn cơ bản
        # ----------------------------------------------------------------------
        if text.lower() == "/start":
            self._send_welcome_message(chat_id)
            return

        if text.lower() in ("/help", "help", "trogiup", "/menu", "/keyboard", "/phim"):
            self._send_help_message(chat_id)
            return

        if text.lower() in ("/reset", "reset"):
            self.selected_targets[chat_id] = None
            self.send_message(chat_id, "> Đã cài lại ngữ cảnh về mặc định: *TOÀN BỘ TÀI KHOẢN [ALL]*.")
            return

        # ----------------------------------------------------------------------
        # C. Bảng tổng hợp trạng thái
        # ----------------------------------------------------------------------
        if text.lower() in ("/status", "status", "/st", "st", "/stt", "stt", "list", "/list"):
            self._send_status_message(chat_id)
            return

        parts = text.split()
        first_token = parts[0].lower().lstrip("/")

        # Tự động chuẩn hóa các alias lệnh viết tắt phổ biến
        cmd_aliases = {
            "st": "status",
            "stt": "status",
            "inf": "info",
            "thongtin": "info",
            "itm": "item",
            "timitem": "item",
            "checkitem": "item",
            "finditem": "item",
            "zn": "zone",
            "zon": "zone",
            "khu": "zone",
            "mp": "map",
            "bando": "map",
            "dau": "harvest",
            "nhatdau": "harvest",
            "thuhoach": "harvest",
            "caydau": "tree",
            "tp": "trainpet",
            "upde": "trainpet",
            "ta": "trainacc",
            "nvts": "trainacc",
            "autonv": "nv",
            "maintask": "nv",
            "nvchinh": "nv",
            "hp": "help",
            "trogiup": "help",
            "conn": "login",
            "dangnhap": "login",
            "dis": "logout",
            "dangxuat": "logout",
            "thoat": "logout",
        }
        if first_token in cmd_aliases:
            first_token = cmd_aliases[first_token]

        sub_args = parts[1:]

        # Lấy tài khoản đang chọn cho chat này nếu có
        curr_selected = self.selected_targets.get(chat_id)

        # ----------------------------------------------------------------------
        # D. Hỗ trợ cú pháp tắt /1 <lệnh> hoặc #1 <lệnh> (vd: /1 info, /1 xmap 0)
        # ----------------------------------------------------------------------
        clean_first = first_token.lstrip("#")
        if clean_first.isdigit() and sub_args:
            target_acc_id = clean_first
            sub_cmd = sub_args[0].lower().lstrip("/")
            sub_sub_args = sub_args[1:]
            if sub_cmd in ("info", "thongtin"):
                self._send_info_message(chat_id, target_acc_id)
                return
            if sub_cmd in ("bag", "balo", "tui"):
                self._send_bag_message(chat_id, target_acc_id)
                return
            if sub_cmd in ("box", "ruong"):
                self._send_box_message(chat_id, target_acc_id)
                return
            if sub_cmd in ("pet", "detu"):
                act = sub_sub_args[0] if sub_sub_args else None
                self._send_pet_message(chat_id, target_acc_id, act)
                return
            if sub_cmd in ("tree", "dau", "caydau"):
                self._send_tree_message(chat_id, target_acc_id)
                return
            if sub_cmd in ("combat", "chiendau"):
                self._send_combat_message(chat_id, target_acc_id)
                return
            if sub_cmd in ("map", "khu"):
                self._send_map_message(chat_id, target_acc_id)
                return
            if sub_cmd in ("item", "timitem", "checkitem"):
                self._send_item_search_message(chat_id, " ".join(sub_sub_args), target_acc_id)
                return
            if sub_cmd in ("zone", "khu"):
                self._send_zone_message(chat_id, target_acc_id, sub_sub_args)
                return
            if sub_cmd in ("autohs", "hs", "autors", "hoisinh", "revive"):
                self._send_autohs_message(chat_id, target_acc_id, sub_sub_args)
                return
            if sub_cmd in ("login", "start", "dangnhap"):
                self._handle_login_cmd(chat_id, target_acc_id)
                return
            if sub_cmd in ("logout", "stop", "dangxuat"):
                self._handle_logout_cmd(chat_id, target_acc_id)
                return
            # Ngược lại là lệnh CLI trực tiếp cho acc đó (vd: /1 xmap 0, /1 zone 3)
            self._execute_direct_command(chat_id, f"acc {target_acc_id} " + " ".join(sub_args))
            return

        # ----------------------------------------------------------------------
        # E. LỆNH /info ĐẶC BIỆT (Hiển thị chi tiết 100% mọi thông tin)
        # ----------------------------------------------------------------------
        if first_token in ("info", "thongtin"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._send_info_message(chat_id, target_arg)
            return

        # ----------------------------------------------------------------------
        # E2. LỆNH /item (Tra cứu vật phẩm trong Balo)
        # ----------------------------------------------------------------------
        if first_token in ("item", "timitem", "checkitem", "finditem"):
            if not sub_args:
                self._send_item_search_message(chat_id, "", None)
                return
            # Nếu tham số cuối là ID acc hoặc 'all'
            if len(sub_args) > 1 and (sub_args[-1].lower() in ("all", "tatca", "*") or sub_args[-1].isdigit()):
                t_arg = sub_args[-1]
                q_arg = " ".join(sub_args[:-1])
            else:
                t_arg = str(curr_selected) if curr_selected else None
                q_arg = " ".join(sub_args)
            self._send_item_search_message(chat_id, q_arg, t_arg)
            return

        # ----------------------------------------------------------------------
        # E3. LỆNH /login VÀ /logout (Đăng nhập và Đăng xuất an toàn)
        # ----------------------------------------------------------------------
        if first_token in ("login", "dangnhap", "startacc", "connect"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._handle_login_cmd(chat_id, target_arg)
            return

        if first_token in ("logout", "dangxuat", "stopacc", "disconnect", "dis"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._handle_logout_cmd(chat_id, target_arg)
            return

        # ----------------------------------------------------------------------
        # E4. LỆNH /zone, /autohs VÀ /boss
        # ----------------------------------------------------------------------
        if first_token in ("zone", "khu"):
            target_arg = str(curr_selected) if curr_selected else None
            self._send_zone_message(chat_id, target_arg, sub_args)
            return

        if first_token in ("autohs", "hs", "autors", "hoisinh", "revive"):
            target_arg = str(curr_selected) if curr_selected else None
            self._send_autohs_message(chat_id, target_arg, sub_args)
            return

        if first_token in ("boss",):
            # Nếu là lệnh bay tới boss: /boss go <tên>
            if sub_args and sub_args[0].lower() in ("go", "goto", "den", "bay", "tele"):
                cleaned_cmd = f"boss {' '.join(sub_args)}"
                if curr_selected:
                    cleaned_cmd = f"acc {curr_selected} {cleaned_cmd}"
                self._execute_direct_command(chat_id, cleaned_cmd)
                return
            target_arg = str(curr_selected) if curr_selected else None
            self._send_boss_message(chat_id, target_arg, sub_args)
            return

        # ----------------------------------------------------------------------
        # F. Lệnh /bag, /box, /pet, /tree, /harvest, /map, /combat
        # ----------------------------------------------------------------------
        if first_token in ("bag", "balo", "tui"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._send_bag_message(chat_id, target_arg)
            return

        if first_token in ("box", "ruong"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._send_box_message(chat_id, target_arg)
            return

        if first_token in ("pet", "detu"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            action_arg = sub_args[1] if len(sub_args) > 1 else None
            self._send_pet_message(chat_id, target_arg, action_arg)
            return

        if first_token in ("tree", "dau", "caydau"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._send_tree_message(chat_id, target_arg)
            return

        if first_token in ("harvest", "thuhoach", "nhatdau"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._send_harvest_message(chat_id, target_arg)
            return

        if first_token in ("map", "khu"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._send_map_message(chat_id, target_arg)
            return

        if first_token in ("combat", "chiendau"):
            target_arg = sub_args[0] if sub_args else (str(curr_selected) if curr_selected else None)
            self._send_combat_message(chat_id, target_arg)
            return

        # ----------------------------------------------------------------------
        # F2. Lệnh /nvbm, /bomong, /quest (Nhiệm vụ Bò Mộng hằng ngày)
        # ----------------------------------------------------------------------
        if first_token in ("nvbm", "nhiemvu", "quest", "bomong"):
            target_arg = str(curr_selected) if curr_selected else None
            self._send_nvbm_message(chat_id, target_arg, sub_args)
            return

        # ----------------------------------------------------------------------
        # G. QUẢN LÝ TÀI KHOẢN & PROXY (CRUD) - vd: /adduser poopooi03 02082003
        # ----------------------------------------------------------------------
        if first_token in ("adduser", "addacc", "themacc"):
            if len(sub_args) < 2:
                self.send_message(chat_id, "Cú pháp: `/adduser <user> <pass> [proxy]`\nVd: `/adduser poopooi03 02082003`")
                return
            prx = sub_args[2] if len(sub_args) > 2 else None
            ok, msg, _inst = self.account_manager.add_account_and_save(
                sub_args[0], sub_args[1], proxy=prx, start_now=True
            )
            self._try_delete_message(chat_id, msg_id)
            self.send_message(chat_id, f"{'[=]' if ok else '[x]'} {msg}")
            return

        if first_token in ("deluser", "delacc", "xoaacc"):
            if not sub_args:
                self.send_message(chat_id, "Cú pháp: `/deluser <user|id>`\nVd: `/deluser poopooi03` hoặc `/deluser 2`")
                return
            ok, msg = self.account_manager.remove_account_and_save(sub_args[0])
            self.send_message(chat_id, f"{'[=]' if ok else '[x]'} {msg}")
            return

        if first_token in ("setpass", "doimk", "doipass"):
            if len(sub_args) < 2:
                self.send_message(chat_id, "Cú pháp: `/setpass <user|id> <mat_khau_moi>`")
                return
            ok, msg = self.account_manager.edit_account_and_save(sub_args[0], new_password=sub_args[1])
            self._try_delete_message(chat_id, msg_id)
            self.send_message(chat_id, f"{'[=]' if ok else '[x]'} {msg}")
            return

        if first_token in ("setproxy", "ganproxy"):
            if len(sub_args) < 2:
                self.send_message(
                    chat_id,
                    "Cú pháp: `/setproxy <user|id> <proxy|off>`\n"
                    "Vd: `/setproxy 1 socks5://u:p@1.2.3.4:1080` (`off` = chạy trực tiếp)"
                )
                return
            ok, msg = self.account_manager.edit_account_and_save(sub_args[0], new_proxy=sub_args[1])
            self._try_delete_message(chat_id, msg_id)
            self.send_message(chat_id, f"{'[=]' if ok else '[x]'} {msg}")
            return

        if first_token in ("addproxy", "themproxy"):
            if not sub_args:
                self.send_message(
                    chat_id,
                    "Cú pháp: `/addproxy <proxy>`\n"
                    "Vd 1: `/addproxy 31.59.20.176:6754:quangproxyx:QuangProxy`\n"
                    "Vd 2: `/addproxy http://quangproxyx:QuangProxy@31.59.20.176:6754/`\n"
                    "Vd 3: `/addproxy 31.59.20.176 6754 quangproxyx QuangProxy`"
                )
                return
            proxy_input = " ".join(sub_args).strip()
            ok, msg = self.account_manager.add_proxy_and_save(proxy_input)
            self._try_delete_message(chat_id, msg_id)
            self.send_message(chat_id, f"{'[=]' if ok else '[x]'} {msg}")
            return

        if first_token in ("delproxy", "xoaproxy"):
            if not sub_args:
                self.send_message(chat_id, "Cú pháp: `/delproxy <stt|proxy>`")
                return
            ok, msg = self.account_manager.remove_proxy_and_save(sub_args[0])
            self.send_message(chat_id, f"{'[=]' if ok else '[x]'} {msg}")
            return

        if first_token in ("listproxy", "proxylist", "dsproxy"):
            pool = self.account_manager.proxy_pool
            lines = [f"= *DANH SÁCH PROXY* (chế độ: *{'BẬT' if pool.use_proxy else 'TẮT'}*, {len(pool)} proxy)"]
            for i, p in enumerate(pool.proxies):
                lines.append(f"  [{i+1}] `{p.display_str}` (đang gán: {p.active_accounts_count} acc)")
            if not pool.proxies:
                lines.append("  (chưa có proxy nào - thêm bằng `/addproxy`)")
            self.send_message(chat_id, "\n".join(lines))
            return

        # ----------------------------------------------------------------------
        # G2. Bật/Tắt thông báo tự động (boss / vào game / mất mạng)
        # ----------------------------------------------------------------------
        if first_token in ("notify", "thongbao", "tb"):
            if not sub_args:
                st = self.account_manager.get_notify_status()
                self.send_message(
                    chat_id,
                    f"= *THÔNG BÁO TỰ ĐỘNG HIỆN TẠI:*\n> {st}\n"
                    "Cú pháp: `/notify <boss|login|dis> <on|off>`\n"
                    "Vd: `/notify boss off` (chỉ xem boss khi gõ `/boss`)",
                )
                return
            if len(sub_args) < 2:
                self.send_message(chat_id, "Cú pháp: `/notify <boss|login|dis> <on|off>`")
                return
            kind = sub_args[0].lower()
            val = sub_args[1].lower()
            if val in ("on", "1", "bat", "enable"):
                ok, msg = self.account_manager.set_notify_and_save(kind, True)
            elif val in ("off", "0", "tat", "disable"):
                ok, msg = self.account_manager.set_notify_and_save(kind, False)
            else:
                self.send_message(chat_id, "Cú pháp: `/notify <boss|login|dis> <on|off>`")
                return
            self.send_message(chat_id, f"{'[=]' if ok else '[x]'} {msg}")
            return

        # ----------------------------------------------------------------------
        # H. Toàn bộ các lệnh điều khiển CLI trực tiếp
        # ----------------------------------------------------------------------
        direct_commands = {
            "all", "acc", "use", "select", "hunt", "autohunt", "huntauto", "boss",
            "xmap", "goto", "zone", "ak", "ts", "tansat",
            "anhat", "cnn", "nsq", "abf",
            "autohs", "autors", "auto_revive", "hs", "revive", "hoisinh", "wake",
            "useitem", "shuttle", "dual",
            "tele", "tp", "focus", "chat", "reconnect", "autoreconnect", "rec",
            "telegram", "tg", "bot", "log", "mute", "cls", "clear", "exit", "quit",
            "trainpet", "upde", "autode", "petauto",
            "trainacc", "newacc", "autonewacc", "nvts",
            "nv", "autonv", "maintask", "nvchinh", "task", "nhiemvu", "quest",
            "harvest", "dau", "thuhoach", "pet", "detu",
            "bag", "balo", "box", "ruong", "login", "logout"
        }

        if (text.startswith("/") and not text.startswith("/ai")) or (first_token in direct_commands):
            cleaned_cmd = text.lstrip("/")
            # Nếu người dùng đang chọn 1 acc cụ thể và gõ lệnh hành động chung (vd: xmap 0, zone 5, hunt on)
            # Tự động gán tiền tố acc <id> nếu lệnh chưa có acc hoặc all
            parts_clean = cleaned_cmd.split()
            if curr_selected and parts_clean and parts_clean[0].lower() not in ("acc", "all", "reconnect", "telegram", "tg", "help"):
                cleaned_cmd = f"acc {curr_selected} {cleaned_cmd}"
            self._execute_direct_command(chat_id, cleaned_cmd)
            return

        # ----------------------------------------------------------------------
        # I. Nếu là câu hỏi tự nhiên hoặc lệnh /ai -> Gửi tới AI OpenRouter
        # ----------------------------------------------------------------------
        user_query = text
        if user_query.lower().startswith("/ai "):
            user_query = user_query[4:].strip()

        self._handle_ai_query(chat_id, user_query)

    # --------------------------------------------------------------------------
    # Các hàm phản hồi thông điệp
    # --------------------------------------------------------------------------
    def _send_welcome_message(self, chat_id: Union[int, str]) -> None:
        """Màn hình chào mừng tập trung vào hành động người dùng cần làm ngay."""
        acc_count = len(self.account_manager.accounts) if (self.account_manager and self.account_manager.accounts) else 0
        online_count = sum(1 for a in self.account_manager.accounts if a.client and a.client.isConnected()) if acc_count > 0 else 0
        rec_status = "Đang bật" if (self.account_manager and self.account_manager.auto_reconnect) else "Đang tắt"
        ai_status = f"Đang bật ({self.ai_model})" if (self.ai_enabled and self.ai_api_key) else "Đang tắt"

        self._menu_modes[chat_id] = "main"
        welcome_text = (
            "*CLIENT NRO PY*\n"
            "Trung tâm điều khiển tài khoản qua Telegram\n\n"
            f"Tài khoản: *{online_count}/{acc_count}* đang online\n"
            f"Tự kết nối lại: *{rec_status}*\n"
            f"Trợ lý AI: *{ai_status}*\n\n"
            "Bắt đầu bằng cách chọn *Tài khoản* để xác định phạm vi điều khiển. "
            "Sau đó dùng *Điều khiển*, *Thông tin* hoặc *Săn Boss*.\n\n"
            "Bạn vẫn có thể dùng toàn bộ lệnh cũ, ví dụ `/status`, `/info`, `/goto 112 min ts`."
        )
        self.send_message(chat_id, welcome_text, reply_markup=self.get_main_keyboard(chat_id))

    def _send_help_message(self, chat_id: Union[int, str]) -> None:
        selected = self.selected_targets.get(chat_id)
        sel_text = "Tất cả tài khoản" if selected is None else f"Tài khoản {selected}"

        from .display import get_telegram_help_text
        help_text = get_telegram_help_text(sel_text)
        self.send_message(chat_id, help_text, reply_markup=self.get_main_keyboard(chat_id))

    def _send_status_message(self, chat_id: Union[int, str]) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "Hiện tại chưa có tài khoản nào được nạp.", reply_markup=self.get_main_keyboard(chat_id))
            return

        # Kích hoạt đồng bộ chỉ số mới nhất từ server cho các tài khoản đang online
        if hasattr(self.account_manager, "refresh_all_accounts_info"):
            self.account_manager.refresh_all_accounts_info()
            time.sleep(0.35)

        accs = self.account_manager.accounts
        curr_selected = self.selected_targets.get(chat_id)
        scope_str = f"Tài khoản {curr_selected}" if curr_selected else "Tất cả tài khoản"
        lines = [
            "*TRẠNG THÁI TÀI KHOẢN*",
            f"Phạm vi: *{scope_str}*",
            f"Tổng số: *{len(accs)}* tài khoản",
            f"Tự kết nối lại: *{'Đang bật' if self.account_manager.auto_reconnect else 'Đang tắt'}*",
            "",
        ]

        total_boss_kills = 0
        total_boss_loots = 0
        recent_boss_kills = []

        for a in accs:
            cname = a.char_name if a.char_name != "Chưa vào" else a.config.username
            power = a.power_str
            mz = a.map_zone_str
            auto = a.auto_status_str
            status_text = a.status
            if a.status == "ONLINE":
                status_text = "Đang online"
            elif a.status == "CONNECTING":
                status_text = "Đang kết nối"
            elif a.status == "RECONNECTING":
                rem = max(0, int(a.reconnect_timer_end - time.time()))
                status_text = f"Đang kết nối lại, còn {rem} giây"
            elif a.status == "OFFLINE":
                status_text = "Ngoại tuyến"

            is_sel = (curr_selected is not None and str(a.config.acc_id) == str(curr_selected))
            sel_tag = " <Đang chọn>" if is_sel else ""
            lines.append(f"*Tài khoản {a.config.acc_id}: {cname}*{sel_tag}")
            lines.append(f"Trạng thái: *{status_text}* | Sức mạnh: `{power}`")
            lines.append(f"Vị trí: {mz}")
            lines.append(f"Tự động hóa: {auto}")

            if a.client:
                bh = a.client.boss_hunter
                kills = getattr(bh, "boss_kill_count", 0)
                loots = getattr(bh, "boss_looted_items_count", 0)
                is_hunt = getattr(bh, "is_hunting", False)
                total_boss_kills += kills
                total_boss_loots += loots

                if kills > 0 or loots > 0 or is_hunt:
                    hunt_text = "Đang bật" if is_hunt else "Đang tắt"
                    lines.append(f"Săn Boss: {hunt_text} | Đã hạ {kills} Boss | Nhặt {loots} vật phẩm")

                hist = getattr(bh, "boss_kill_history", [])
                for h in hist:
                    recent_boss_kills.append({**h, "acc_tag": a.tag})

        if total_boss_kills > 0 or total_boss_loots > 0:
            lines.append(f"*Tổng săn Boss:* Hạ {total_boss_kills} Boss | Nhặt {total_boss_loots} vật phẩm")

        if recent_boss_kills:
            last_k = recent_boss_kills[-1]
            lines.append(
                f"Boss gần nhất: *{last_k['name']}* | Tài khoản {last_k['acc_tag']} | "
                f"{last_k.get('map_name', 'Chưa rõ')} | {last_k.get('time', '')}"
            )

        lines.append("")
        lines.append("Chọn *Tài khoản* bên dưới để chuyển phạm vi, hoặc dùng `/info 1` để xem chi tiết tài khoản 1.")
        self.send_message(chat_id, "\n".join(lines), reply_markup=self.get_main_keyboard(chat_id))

    def _resolve_account(self, token: Optional[str]):
        """Tìm tài khoản theo STT (#1, 1), username hoặc tên nhân vật."""
        if not self.account_manager or not self.account_manager.accounts:
            return None
        if not token:
            return self.account_manager.accounts[0]
        token_clean = token.lstrip("#").strip()
        return self.account_manager.get_account(token_clean)

    def _send_info_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        """Xử lý lệnh /info: Hiển thị đầy đủ thông tin nhân vật, đệ tử, balo, rương, đậu thần, map, auto."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        accs = self.account_manager.accounts
        curr_selected = self.selected_targets.get(chat_id)

        # 1. Nếu người dùng chỉ định tài khoản cụ thể (khác all)
        if target_arg and target_arg.lower() not in ("all", "tatca", "*"):
            inst = self._resolve_account(target_arg)
            if inst:
                inst.refresh_info()
                time.sleep(0.35)
                self.send_message(chat_id, self.format_char_full_info(inst))
            else:
                self.send_message(chat_id, f"[x] Không tìm thấy tài khoản '{target_arg}'. Gõ `/status` để xem danh sách.")
            return

        # 2. Nếu đang chọn 1 tài khoản cụ thể trong menu (và không có target_arg == 'all')
        if curr_selected is not None and not (target_arg and target_arg.lower() in ("all", "tatca", "*")):
            inst = self._resolve_account(str(curr_selected))
            if inst:
                inst.refresh_info()
                time.sleep(0.35)
                self.send_message(chat_id, self.format_char_full_info(inst))
                return

        # 3. Ngữ cảnh Tất cả tài khoản (ALL) hoặc target_arg == 'all'
        # Gửi yêu cầu làm mới dữ liệu cho toàn bộ tài khoản
        if hasattr(self.account_manager, "refresh_all_accounts_info"):
            self.account_manager.refresh_all_accounts_info()
            time.sleep(0.4)

        # Gửi thông tin từng tài khoản (mỗi tài khoản 1 tin nhắn riêng biệt)
        for a in accs:
            self.send_message(chat_id, self.format_char_full_info(a))
            time.sleep(0.1)

    def _send_bag_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        accs = self.account_manager.accounts
        curr_selected = self.selected_targets.get(chat_id)
        is_all = (target_arg and target_arg.lower() in ("all", "tatca", "*")) or (not target_arg and curr_selected is None)
        if is_all:
            for a in accs:
                self.send_message(chat_id, self.format_char_bag_info(a))
                time.sleep(0.05)
            return
        inst = self._resolve_account(target_arg if target_arg else str(curr_selected))
        if inst:
            self.send_message(chat_id, self.format_char_bag_info(inst))
        else:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản.")

    def _send_box_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        accs = self.account_manager.accounts
        curr_selected = self.selected_targets.get(chat_id)
        is_all = (target_arg and target_arg.lower() in ("all", "tatca", "*")) or (not target_arg and curr_selected is None)
        if is_all:
            for a in accs:
                self.send_message(chat_id, self.format_char_box_info(a))
                time.sleep(0.05)
            return
        inst = self._resolve_account(target_arg if target_arg else str(curr_selected))
        if inst:
            self.send_message(chat_id, self.format_char_box_info(inst))
        else:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản.")

    def _send_pet_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None, action_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        # Nếu tham số thứ nhất là hành động (ví dụ /pet attack hoặc /pet fuse)
        if target_arg and target_arg.lower() in PET_ACTION_MAP:
            act_code = PET_ACTION_MAP[target_arg.lower()]
            connected = [a for a in self.account_manager.accounts if a.client and a.client.isConnected()]
            if not connected:
                self.send_message(chat_id, "[!] Không có tài khoản nào đang Online để đổi trạng thái đệ.")
                return
            for a in connected:
                a.client.change_pet_status(act_code)
            self.send_message(chat_id, f"[=] Đã chuyển trạng thái đệ tử sang: *{PET_STATUS_NAMES.get(act_code)}* cho {len(connected)} tài khoản!")
            return

        # Nếu có target_arg và action_arg (ví dụ /pet 1 attack)
        if action_arg and action_arg.lower() in PET_ACTION_MAP:
            act_code = PET_ACTION_MAP[action_arg.lower()]
            st_name = PET_STATUS_NAMES.get(act_code, "Đã đổi")
            if target_arg.lower() in ("all", "tatca", "*"):
                connected = [a for a in self.account_manager.accounts if a.client and a.client.isConnected()]
                for a in connected:
                    a.client.change_pet_status(act_code)
                self.send_message(chat_id, f"[=] Đã chuyển trạng thái đệ tử sang: *{st_name}* cho TOÀN BỘ tài khoản!")
                return
            inst = self._resolve_account(target_arg)
            if inst and inst.client:
                inst.client.change_pet_status(act_code)
                self.send_message(chat_id, f"[=] [{inst.tag}] Đã chuyển trạng thái đệ tử sang: *{st_name}*!")
                return
            else:
                self.send_message(chat_id, f"[x] Không tìm thấy tài khoản '{target_arg}'.")
                return

        # Nếu chỉ xem thông tin đệ tử (/pet hoặc /pet 1 hoặc /pet all)
        curr_selected = self.selected_targets.get(chat_id)
        is_all = (target_arg and target_arg.lower() in ("all", "tatca", "*")) or (not target_arg and curr_selected is None)
        if is_all:
            for a in self.account_manager.accounts:
                self.send_message(chat_id, self.format_char_pet_info(a))
                time.sleep(0.05)
            return

        inst = self._resolve_account(target_arg if target_arg else str(curr_selected))
        if inst:
            self.send_message(chat_id, self.format_char_pet_info(inst))
        else:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản.")

    def _send_tree_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        curr_selected = self.selected_targets.get(chat_id)
        is_all = (target_arg and target_arg.lower() in ("all", "tatca", "*")) or (not target_arg and curr_selected is None)
        targets = self.account_manager.accounts if is_all else [self._resolve_account(target_arg if target_arg else str(curr_selected))]
        for inst in targets:
            if not inst or not inst.client or not inst.client.myChar:
                self.send_message(chat_id, f"[!] [{inst.tag if inst else '?'}] Tài khoản chưa vào map.")
                continue
            tree = inst.client.myChar.magicTree
            sec_str = f"Chín sau {tree.seconds}s ({int(tree.seconds/60)} phút)" if tree.seconds > 0 else "Đậu đã chín đầy đủ!"
            msg = (
                f"= *CÂY ĐẬU THẦN [{inst.tag}]*\n"
                f"=============================\n"
                f"> Cấp độ: *Cấp {tree.level}*\n"
                f"> Số lượng đậu: *{tree.currPeas} / {tree.maxPeas}* hạt\n"
                f"> Tình trạng: *{sec_str}*\n\n"
                f"> Gõ `/harvest` để thu hoạch đậu ngay!"
            )
            self.send_message(chat_id, msg)
            time.sleep(0.05)

    def _send_harvest_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        targets = [self._resolve_account(target_arg)] if (target_arg and target_arg.lower() not in ("all", "tatca", "*")) else self.account_manager.accounts
        count = 0
        for a in targets:
            if a and a.client and a.client.isConnected():
                a.client.request_magic_tree(action=2)
                count += 1
        self.send_message(chat_id, f"= Đã gửi yêu cầu thu hoạch đậu thần cho {count} tài khoản!")

    def _send_map_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        curr_selected = self.selected_targets.get(chat_id)
        is_all = (target_arg and target_arg.lower() in ("all", "tatca", "*")) or (not target_arg and curr_selected is None)
        if is_all:
            for a in self.account_manager.accounts:
                self.send_message(chat_id, self.format_char_map_info(a))
                time.sleep(0.05)
            return
        inst = self._resolve_account(target_arg if target_arg else str(curr_selected))
        if inst:
            self.send_message(chat_id, self.format_char_map_info(inst))
        else:
            self.send_message(chat_id, "[x] Không tìm thấy tài khoản.")

    def _send_combat_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        curr_selected = self.selected_targets.get(chat_id)
        is_all = (target_arg and target_arg.lower() in ("all", "tatca", "*")) or (not target_arg and curr_selected is None)
        if is_all:
            for a in self.account_manager.accounts:
                self.send_message(chat_id, self.format_char_combat_info(a))
                time.sleep(0.05)
            return
        inst = self._resolve_account(target_arg if target_arg else str(curr_selected))
        if inst:
            self.send_message(chat_id, self.format_char_combat_info(inst))
        else:
            self.send_message(chat_id, "[x] Không tìm thấy tài khoản.")

    def _send_item_search_message(self, chat_id: Union[int, str], query: str, target_arg: Optional[str] = None) -> None:
        """Xử lý tra cứu vật phẩm trong balo: tìm theo ID hoặc tên."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        query_clean = query.strip()
        if not query_clean:
            self.send_message(
                chat_id,
                "= *TRA CỨU VẬT PHẨM TRONG BALO*\n"
                "=============================\n"
                "> Cú pháp: `/item <id|tên> [id|all]`\n"
                "> _Ví dụ:_ `/item 14` (kiểm tra có item 14 không, đang có bao nhiêu)\n"
                "> _Ví dụ:_ `/item đậu` hoặc `/item 14 all`"
            )
            return

        is_query_numeric = query_clean.isdigit()
        target_template_id = int(query_clean) if is_query_numeric else -1

        # Xác định đối tượng tài khoản cần tìm
        curr_selected = self.selected_targets.get(chat_id)
        if target_arg and target_arg.lower() in ("all", "tatca", "*"):
            targets = self.account_manager.accounts
            is_multi = True
        elif target_arg:
            inst = self._resolve_account(target_arg)
            targets = [inst] if inst else []
            is_multi = False
        elif curr_selected:
            inst = self._resolve_account(str(curr_selected))
            targets = [inst] if inst else []
            is_multi = False
        else:
            # Ngữ cảnh ALL
            targets = self.account_manager.accounts
            is_multi = True

        if not targets:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản '{target_arg}'.")
            return

        if not is_multi:
            # Tra cứu trên 1 tài khoản
            inst = targets[0]
            if not inst.client or not inst.client.isConnected() or not inst.client.myChar:
                self.send_message(chat_id, f"[!] [{inst.tag}] Tài khoản hiện chưa Online hoặc chưa vào map.")
                return

            bag = inst.client.myChar.arrItemBag
            matched_items = []
            for slot_idx, it in enumerate(bag):
                match = False
                if is_query_numeric and it.template_id == target_template_id:
                    match = True
                elif not is_query_numeric:
                    it_name = get_item_display_name(it.template_id, it.info)
                    if query_clean.lower() in it_name.lower():
                        match = True
                if match:
                    matched_items.append((slot_idx, it))

            if not matched_items:
                self.send_message(
                    chat_id,
                    f"= *KẾT QUẢ TÌM VẬT PHẨM [{inst.tag}]*\n"
                    f"=============================\n"
                    f"[x] *Không tìm thấy* vật phẩm `{query_clean}` trong balo!\n"
                    f"> Balo hiện đang có *{len(bag)}* món khác. Gõ `/bag` để xem toàn bộ."
                )
                return

            # Gom nhóm và hiển thị
            total_qty = sum(it.quantity for _, it in matched_items)
            first_it = matched_items[0][1]
            first_name = get_item_display_name(first_it.template_id, first_it.info)

            lines = [
                f"= *KẾT QUẢ TÌM VẬT PHẨM [{inst.tag}]*",
                f"=============================",
                f"> Vật phẩm: *{first_name}* (ID: `{first_it.template_id}`)",
            ]

            # Bổ sung thông tin chi tiết từ game_data
            item_meta = get_item_info(first_it.template_id)
            if item_meta:
                t_name = get_item_type_name(item_meta.get("type", -1))
                g_name = get_gender_name(item_meta.get("gender", 3))
                lines.append(f"> Phân loại: *{t_name}* | Hành tinh: *{g_name}*")
                sub_meta = []
                lvl = item_meta.get("level", 0)
                if lvl > 0:
                    sub_meta.append(f"Cấp độ: *{lvl}*")
                req_sm = item_meta.get("req", 0)
                if req_sm > 0:
                    sub_meta.append(f"Yêu cầu SM: *{format_big_number(req_sm)}*")
                if sub_meta:
                    lines.append(f"> " + " | ".join(sub_meta))
                desc = item_meta.get("desc", "").strip()
                if desc and desc != "...":
                    lines.append(f"> Mô tả: _{desc}_")

            lines.append(f"> Tổng số lượng trong balo: *x{total_qty:,}*")
            lines.append(f"> Vị trí ô chứa ({len(matched_items)} ô):")
            for slot_idx, it in matched_items:
                opts = " | ".join([opt.getText() for opt in it.options[:2]])
                opt_str = f" _{opts}_" if opts else ""
                lines.append(f"  Ô {slot_idx+1:02d}: x{it.quantity}{opt_str}")

            if first_it.options:
                all_opts = " | ".join([opt.getText() for opt in first_it.options])
                lines.append(f"> Chỉ số/Thuộc tính: _{all_opts}_")

            self.send_message(chat_id, "\n".join(lines))
            return

        # Tra cứu trên toàn bộ tài khoản (ALL)
        lines = [
            f"= *TỔNG HỢP VẬT PHẨM TRÊN TOÀN ĐỘI*",
            f"> Từ khóa tìm kiếm: `{query_clean}`",
        ]
        if is_query_numeric:
            meta_header = format_item_details(target_template_id)
            if meta_header:
                lines.append(f"> Thông tin: _{meta_header}_")

        lines.append("=============================")
        grand_total = 0
        item_sample_name = ""
        item_sample_id = None

        for inst in targets:
            if not inst.client or not inst.client.isConnected() or not inst.client.myChar:
                lines.append(f"[-] *[{inst.tag}]*: (OFFLINE)")
                continue

            bag = inst.client.myChar.arrItemBag
            matched = []
            for slot_idx, it in enumerate(bag):
                match = False
                if is_query_numeric and it.template_id == target_template_id:
                    match = True
                elif not is_query_numeric:
                    it_name = get_item_display_name(it.template_id, it.info)
                    if query_clean.lower() in it_name.lower():
                        match = True
                if match:
                    matched.append((slot_idx, it))

            if matched:
                acc_total = sum(it.quantity for _, it in matched)
                grand_total += acc_total
                if not item_sample_name:
                    item_sample_name = get_item_display_name(matched[0][1].template_id, matched[0][1].info)
                    item_sample_id = matched[0][1].template_id
                slots_str = ", ".join([f"Ô {s+1:02d} (x{it.quantity})" for s, it in matched])
                lines.append(f"> *[{inst.tag}]*: Có *x{acc_total:,}* ({slots_str})")
            else:
                lines.append(f"> *[{inst.tag}]*: [Không có]")

        lines.append("=============================")
        if grand_total > 0:
            name_str = f" *{item_sample_name}*" if item_sample_name else ""
            lines.append(f"> *TỔNG CỘNG TOÀN ĐỘI:*{name_str} *x{grand_total:,}* vật phẩm!")
            if not is_query_numeric and item_sample_id is not None:
                meta_footer = format_item_details(item_sample_id)
                if meta_footer:
                    lines.append(f"> Chi tiết vật phẩm: _{meta_footer}_")
        else:
            lines.append(f"[!] Không tài khoản nào có vật phẩm `{query_clean}` trong balo.")

        self.send_message(chat_id, "\n".join(lines))

    def _send_zone_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None, sub_args: Optional[List[str]] = None) -> None:
        """Xử lý lệnh /zone: Xem danh sách khu vực, đổi khu riêng lẻ hoặc tản khu vắng toàn đội."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        is_all = (target_arg is None) or (target_arg.lower() in ("all", "tatca", "*"))
        args_clean = [a.lower() for a in (sub_args or [])]
        if any(a in ("all", "tatca", "*") for a in args_clean):
            is_all = True
            args_clean = [a for a in args_clean if a not in ("all", "tatca", "*")]

        action = args_clean[0] if args_clean else None

        # ----------------------------------------------------------------------
        # TRƯỜNG HỢP 1: TẢN KHU VẮNG CHO TOÀN BỘ TÀI KHOẢN (ALL /zone min)
        # ----------------------------------------------------------------------
        if is_all and action in ("min", "least", "itnguoi", "vang", "empty", "auto"):
            connected = [
                a for a in self.account_manager.accounts
                if a.client and a.client.isConnected() and a.client.myChar and a.client.myChar.mapInfo
            ]
            if not connected:
                self.send_message(chat_id, "[!] Không có tài khoản nào đang online và trong map để đổi khu.")
                return

            results = self.account_manager.disperse_zones_min(connected)
            lines = [
                "= *PHÂN TÁN KHU VẮNG TOÀN ĐỘI (/zone min)*",
                f"> Số tài khoản: *{len(results)}* | Cơ chế: *Không đụng nhau, giữ nguyên nếu đã ở khu min*",
                "=============================",
            ]
            for r in results:
                a = r["account"]
                f_z = r["from_zone"]
                t_z = r["to_zone"]
                m_name = r.get("map_name", "")
                c_name = getattr(a, "char_name", "") or "NV"
                if r["stayed"]:
                    lines.append(f"> *[{a.tag}]* ({c_name}): Đang ở *Khu {t_z:02d}* ({m_name}) -> Đã là khu ít người nhất, giữ nguyên")
                else:
                    lines.append(f"> *[{a.tag}]* ({c_name}): Khu {f_z:02d} -> *Khu {t_z:02d}* ({m_name}) -> Tản vào khu vắng")

            lines.append("=============================")
            lines.append("> *Thành công:* Toàn bộ tài khoản đã được tản đều ra các khu vắng, không đụng nhau!")
            self.send_message(chat_id, "\n".join(lines))
            return

        # ----------------------------------------------------------------------
        # TRƯỜNG HỢP 2: ĐỔI SANG CÙNG 1 SỐ KHU CHO TẤT CẢ (ALL /zone <số>)
        # ----------------------------------------------------------------------
        if is_all and action and action.isdigit():
            target_zid = int(action)
            connected = [
                a for a in self.account_manager.accounts
                if a.client and a.client.isConnected() and a.client.myChar and a.client.myChar.mapInfo
            ]
            if not connected:
                self.send_message(chat_id, "[!] Không có tài khoản nào đang online để đổi khu.")
                return
            for a in connected:
                a.client.change_zone(target_zid)
                a.last_zone_id = target_zid
                a.snapshot_active_autos()
                time.sleep(0.08)
            self.send_message(chat_id, f"[=] Đã gửi yêu cầu đổi sang *Khu {target_zid:02d}* cho toàn bộ {len(connected)} tài khoản!")
            return

        # ----------------------------------------------------------------------
        # TRƯỜNG HỢP 3: XEM DANH SÁCH KHU VỰC HOẶC ĐỔI KHU TRÊN 1 ACC
        # ----------------------------------------------------------------------
        if not action:
            # Hiển thị danh sách khu vực
            if is_all:
                connected = [
                    a for a in self.account_manager.accounts
                    if a.client and a.client.isConnected() and a.client.myChar and a.client.myChar.mapInfo
                ]
                if not connected:
                    self.send_message(chat_id, "[!] Không có tài khoản nào đang online và trong map.")
                    return

                maps_dict: Dict[int, List[Any]] = {}
                for a in connected:
                    mid = a.client.myChar.mapInfo.mapID
                    maps_dict.setdefault(mid, []).append(a)

                for mid, accs_in_map in maps_dict.items():
                    rep = accs_in_map[0]
                    rep.client.request_zones()
                    time.sleep(0.3)
                    m = rep.client.myChar.mapInfo

                    # Vị trí các tài khoản trong map này
                    zone_occupants: Dict[int, List[str]] = {}
                    for a in accs_in_map:
                        c_name = a.char_name if a.char_name and a.char_name != "Chưa vào" else a.config.username
                        zid = getattr(a.client.myChar.mapInfo, "zoneID", -1)
                        if zid >= 0:
                            zone_occupants.setdefault(zid, []).append(c_name)

                    acc_status_list = []
                    for a in accs_in_map:
                        c_name = a.char_name if a.char_name and a.char_name != "Chưa vào" else a.config.username
                        zid = getattr(a.client.myChar.mapInfo, "zoneID", 0)
                        acc_status_list.append(f"> *[{a.tag}]* {c_name}: *Khu {zid:02d}*")

                    lines = [
                        f"= *DANH SÁCH KHU VỰC* (Bản đồ: *{m.mapName}* - ID: `{m.mapID}`)",
                        f"> Vị trí các tài khoản ({len(accs_in_map)} acc):",
                        "\n".join(acc_status_list),
                        "=============================",
                    ]

                    if m.zones:
                        z_parts = []
                        for z in m.zones:
                            occupants = zone_occupants.get(z.zoneId, [])
                            occ_mark = f" <{', '.join(occupants)}>" if occupants else ""
                            density = " Đầy" if z.numPlayer >= z.maxPlayer else (" Vắng" if z.numPlayer <= 2 else "")
                            z_parts.append(f"*K{z.zoneId:02d}:* {z.numPlayer}/{z.maxPlayer}{density}{occ_mark}")

                        for i in range(0, len(z_parts), 3):
                            lines.append(" | ".join(z_parts[i:i+3]))
                    else:
                        lines.append("Chưa tải được danh sách khu. Vui lòng thử lại sau 1s.")

                    lines.append("=============================")
                    lines.append("> *Thao tác:* Gõ `/zone <số>` để đổi khu, hoặc `/zone min` để vào khu vắng nhất.")
                    self.send_message(chat_id, "\n".join(lines))
                    time.sleep(0.05)
                return

            # Chỉ xem 1 tài khoản cụ thể
            inst = self._resolve_account(target_arg)
            if not inst or not inst.client or not inst.client.isConnected() or not inst.client.myChar:
                self.send_message(chat_id, "[!] Tài khoản chưa online hoặc chưa vào map.")
                return

            inst.client.request_zones()
            time.sleep(0.3)
            m = inst.client.myChar.mapInfo
            c_name = inst.char_name if inst.char_name and inst.char_name != "Chưa vào" else inst.config.username

            zone_occupants = {}
            for a in self.account_manager.accounts:
                if a.client and a.client.isConnected() and a.client.myChar and a.client.myChar.mapInfo:
                    if a.client.myChar.mapInfo.mapID == m.mapID:
                        name = a.char_name if a.char_name and a.char_name != "Chưa vào" else a.config.username
                        zid = getattr(a.client.myChar.mapInfo, "zoneID", -1)
                        if zid >= 0:
                            zone_occupants.setdefault(zid, []).append(name)

            lines = [
                f"= *DANH SÁCH KHU VỰC [{inst.tag}]*",
                f"> Bản đồ: *{m.mapName}* (ID: `{m.mapID}`)",
                f"> Nhân vật: *{c_name}* (Khu hiện tại: *Khu {m.zoneID:02d}*)",
                "=============================",
            ]
            if m.zones:
                z_parts = []
                for z in m.zones:
                    occupants = zone_occupants.get(z.zoneId, [])
                    occ_mark = f" <{', '.join(occupants)}>" if occupants else ""
                    density = " Đầy" if z.numPlayer >= z.maxPlayer else (" Vắng" if z.numPlayer <= 2 else "")
                    z_parts.append(f"*K{z.zoneId:02d}:* {z.numPlayer}/{z.maxPlayer}{density}{occ_mark}")

                for i in range(0, len(z_parts), 3):
                    lines.append(" | ".join(z_parts[i:i+3]))
            else:
                lines.append("Chưa tải được danh sách khu. Vui lòng thử lại sau 1s.")

            lines.append("=============================")
            lines.append("> *Thao tác:* Gõ `/zone <số>` để đổi khu, hoặc `/zone min` để vào khu vắng nhất.")
            self.send_message(chat_id, "\n".join(lines))
            return

        # Nếu có action (min hoặc đổi sang số khu cụ thể) trên 1 tài khoản
        inst = self._resolve_account(target_arg)
        if not inst or not inst.client or not inst.client.isConnected() or not inst.client.myChar:
            self.send_message(chat_id, "[!] Tài khoản chưa online hoặc chưa vào map.")
            return

        if action in ("min", "least", "itnguoi", "vang", "empty", "auto"):
            curr_zid = getattr(inst.client.myChar.mapInfo, "zoneID", -1)
            zid = inst.client.change_to_least_populated_zone()
            if zid is not None:
                if zid == curr_zid:
                    self.send_message(chat_id, f"[=] [{inst.tag}] Đang ở *Khu {zid:02d}* (đã là khu ít người nhất, giữ nguyên không đổi)!")
                else:
                    inst.last_zone_id = zid
                    inst.snapshot_active_autos()
                    self.send_message(chat_id, f"[=] [{inst.tag}] Đã chuyển sang *Khu {zid:02d}* (khu vắng nhất)!")
            else:
                self.send_message(chat_id, f"[!] [{inst.tag}] Đã ở khu vắng nhất hoặc không lấy được danh sách.")
            return
        elif action and action.isdigit():
            zid = int(action)
            inst.client.change_zone(zid)
            inst.last_zone_id = zid
            inst.snapshot_active_autos()
            self.send_message(chat_id, f"[=] [{inst.tag}] Đã gửi yêu cầu đổi sang *Khu {zid:02d}*!")
            return

    def _send_autohs_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None, sub_args: Optional[List[str]] = None) -> None:
        """Xử lý lệnh /autohs và /hs: Bật/tắt tự hồi sinh, cài đặt chế độ ngọc/về thành."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        is_all = (target_arg is None) or (target_arg.lower() in ("all", "tatca", "*"))
        args_clean = [a.lower() for a in (sub_args or [])]
        if any(a in ("all", "tatca", "*") for a in args_clean):
            is_all = True
            args_clean = [a for a in args_clean if a not in ("all", "tatca", "*")]

        action = args_clean[0] if args_clean else ""

        if is_all:
            targets = [a for a in self.account_manager.accounts if a.client and a.client.isConnected()]
            if not targets:
                self.send_message(chat_id, "[!] Không có tài khoản nào đang online để điều khiển Tự Hồi Sinh.")
                return

            if action in ("on", "start", "1", "true", "bat"):
                mode = None
                if len(args_clean) > 1 and args_clean[1] in ("gem", "ngoc"):
                    mode = "gem"
                elif len(args_clean) > 1 and args_clean[1] in ("town", "ve", "thanh", "nha"):
                    mode = "town"

                for a in targets:
                    if mode:
                        a.client.set_auto_revive_mode(mode)
                    a.client.auto_revive_manager.enable()
                    a.snapshot_active_autos()
                mode_str = f" ({mode})" if mode else ""
                self.send_message(chat_id, f"[=] Đã BẬT Tự Động Hồi Sinh{mode_str} cho TOÀN BỘ {len(targets)} tài khoản!")
                return

            elif action in ("off", "stop", "0", "false", "tat"):
                for a in targets:
                    a.client.auto_revive_manager.disable()
                    a.snapshot_active_autos()
                self.send_message(chat_id, f"[x] Đã TẮT Tự Động Hồi Sinh cho TOÀN BỘ {len(targets)} tài khoản!")
                return

            elif action in ("gem", "ngoc", "place", "here"):
                for a in targets:
                    a.client.set_auto_revive_mode("gem")
                    a.client.auto_revive_manager.enable()
                    a.snapshot_active_autos()
                self.send_message(chat_id, f"[=] Đã cài đặt chế độ Hồi Sinh BẰNG NGỌC TẠI CHỖ (và bật AutoHS) cho TOÀN BỘ {len(targets)} tài khoản!")
                return

            elif action in ("town", "ve", "thanh", "nha", "home"):
                for a in targets:
                    a.client.set_auto_revive_mode("town")
                    a.client.auto_revive_manager.enable()
                    a.snapshot_active_autos()
                self.send_message(chat_id, f"[=] Đã cài đặt chế độ Hồi Sinh VỀ THÀNH (và bật AutoHS) cho TOÀN BỘ {len(targets)} tài khoản!")
                return

            # Nếu không có tham số hoặc gõ status: hiển thị bảng trạng thái toàn đội
            lines = [
                "= *TRẠNG THÁI TỰ ĐỘNG HỒI SINH (TOÀN ĐỘI)*",
                "=============================",
            ]
            for a in targets:
                st = a.client.get_auto_revive_status()
                st_icon = "[ON]" if st["is_enabled"] else "[OFF]"
                lines.append(f"> *[{a.tag}]*: `{st_icon}` Chế độ: *{st['mode_str']}* (Đã HS: {st['revive_count']} lần)")
            lines.append("=============================")
            lines.append("> *Lệnh:* `/autohs on` | `/autohs off` | `/autohs ngoc` | `/autohs ve`")
            self.send_message(chat_id, "\n".join(lines))
            return

        # Cho 1 tài khoản cụ thể
        inst = self._resolve_account(target_arg)
        if not inst or not inst.client or not inst.client.isConnected():
            self.send_message(chat_id, "[!] Tài khoản chưa kết nối online.")
            return

        if action in ("on", "start", "1", "true", "bat"):
            if len(args_clean) > 1 and args_clean[1] in ("gem", "ngoc"):
                inst.client.set_auto_revive_mode("gem")
            elif len(args_clean) > 1 and args_clean[1] in ("town", "ve", "thanh", "nha"):
                inst.client.set_auto_revive_mode("town")
            inst.client.auto_revive_manager.enable()
            inst.snapshot_active_autos()
            st = inst.client.get_auto_revive_status()
            self.send_message(chat_id, f"[=] [{inst.tag}] Đã BẬT Tự Động Hồi Sinh (Chế độ: *{st['mode_str']}*)!")
            return

        elif action in ("off", "stop", "0", "false", "tat"):
            inst.client.auto_revive_manager.disable()
            inst.snapshot_active_autos()
            self.send_message(chat_id, f"[x] [{inst.tag}] Đã TẮT Tự Động Hồi Sinh!")
            return

        elif action in ("gem", "ngoc", "place", "here"):
            inst.client.set_auto_revive_mode("gem")
            inst.client.auto_revive_manager.enable()
            inst.snapshot_active_autos()
            self.send_message(chat_id, f"[=] [{inst.tag}] Đã chuyển sang chế độ Hồi Sinh BẰNG NGỌC TẠI CHỖ (và bật AutoHS)!")
            return

        elif action in ("town", "ve", "thanh", "nha", "home"):
            inst.client.set_auto_revive_mode("town")
            inst.client.auto_revive_manager.enable()
            inst.snapshot_active_autos()
            self.send_message(chat_id, f"[=] [{inst.tag}] Đã chuyển sang chế độ Hồi Sinh VỀ THÀNH (và bật AutoHS)!")
            return

        elif not action:
            # Toggle
            new_state = inst.client.toggle_auto_revive()
            inst.snapshot_active_autos()
            st = inst.client.get_auto_revive_status()
            self.send_message(
                chat_id,
                f"[{inst.tag}] Đã {'BẬT [ON]' if new_state else 'TẮT [OFF]'} Tự Hồi Sinh (Chế độ: *{st['mode_str']}*)!"
            )
            return

        # Hiển thị trạng thái chi tiết
        st = inst.client.get_auto_revive_status()
        lines = [
            f"= *CẤU HÌNH TỰ ĐỘNG HỒI SINH [{inst.tag}]*",
            f"=============================",
            f"> Trạng thái:     {'[=] ĐANG BẬT [ON]' if st['is_enabled'] else '[ ] ĐÃ TẮT [OFF]'}",
            f"> Chế độ:         *{st['mode_str']}*",
            f"> Đã hồi sinh:    *{st['revive_count']}* lần",
            f"> Tình trạng NV:  {'ĐÃ CHẾT' if st['is_currently_dead'] else 'CÒN SỐNG'}",
            f"=============================",
            f"> *Lệnh:* `/autohs on` | `/autohs off` | `/autohs ngoc` | `/autohs ve`",
        ]
        self.send_message(chat_id, "\n".join(lines))

    def _send_boss_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None, sub_args: Optional[List[str]] = None) -> None:
        """Xử lý lệnh /boss: Hiển thị Boss đang sống + Thống kê Boss bị tiêu diệt và đồ farm của từng acc."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        accs = self.account_manager.accounts
        lines = [
            "= *BẢNG THEO DÕI & THỐNG KÊ SĂN BOSS*",
            "=============================",
        ]

        # 1. Boss đang xuất hiện & vừa bị hạ gần đây
        recent_bosses = []
        for a in accs:
            if a.client and hasattr(a.client, "boss_manager"):
                for b in reversed(a.client.boss_manager.get_all_bosses()):
                    b_key = f"{b.get('name')}:{b.get('map_name')}"
                    if not any(f"{x.get('name')}:{x.get('map_name')}" == b_key for x in recent_bosses):
                        recent_bosses.append(b)

        lines.append("= *1. BOSS ĐANG XUẤT HIỆN:*")
        if recent_bosses:
            for i, b in enumerate(recent_bosses[:10]):
                z_str = f" (Khu {b.get('zone_id')})" if b.get('zone_id', -1) >= 0 else ""
                m_str = f" tại *{b.get('map_name')}*" if b.get('map_name') else ""
                is_died = b.get("is_died", False)
                killer = (b.get("killer") or "").strip()
                if is_died:
                    st_text = f"[{killer}]" if killer else "[Đã chết]"
                else:
                    st_text = "[Còn sống]"
                lines.append(f"  `{i+1:02d}.` *{b.get('name')}*{m_str}{z_str} {st_text}")
        else:
            lines.append("  (Hiện chưa có Boss nào được phát hiện)")

        # 2. Bảng thành tích săn boss của từng acc
        lines.append("\n= *2. THÀNH TÍCH SĂN BOSS TỪNG TÀI KHOẢN:*")
        total_kills = 0
        total_loots = 0
        all_histories = []

        for a in accs:
            bh = a.client.boss_hunter if a.client else None
            kills = getattr(bh, "boss_kill_count", 0) if bh else 0
            loots = getattr(bh, "boss_looted_items_count", 0) if bh else 0
            hunting_str = "[=] Đang săn" if (bh and getattr(bh, "is_hunting", False)) else "[ ] Tắt"
            total_kills += kills
            total_loots += loots

            lines.append(f"> *Acc #{a.config.acc_id}* ({a.char_name}): Diệt *{kills}* Boss | Farm *{loots}* đồ [{hunting_str}]")

            if bh and hasattr(bh, "boss_kill_history"):
                for h in bh.boss_kill_history:
                    all_histories.append({**h, "acc_tag": a.tag})

        lines.append(f"> *Toàn đội:* Đã hạ *{total_kills}* Boss | Thu hoạch *{total_loots}* vật phẩm!")

        # 3. Lịch sử hạ boss gần đây
        if all_histories:
            lines.append("\n= *3. LỊCH SỬ HẠ BOSS GẦN ĐÂY:*")
            for h in all_histories[-5:]:
                lines.append(f"  [{h['acc_tag']}] Tiêu diệt *{h['name']}* tại {h.get('map_name', 'Chưa rõ')} ({h.get('time', '')})")

        lines.append("=============================")
        lines.append("> *Lệnh:* `/hunt on` | `/hunt off` | `/boss go <tên boss>`")
        self.send_message(chat_id, "\n".join(lines))

    def _send_nvbm_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None, sub_args: Optional[List[str]] = None) -> None:
        """Xử lý lệnh /nvbm: Bật/Tắt và hiển thị trạng thái làm Nhiệm vụ Bò Mộng hằng ngày."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Hệ thống chưa có tài khoản nào được nạp.")
            return

        accs = self.account_manager.accounts
        curr_selected = self.selected_targets.get(chat_id)

        # 1. Xác định danh sách account mục tiêu
        target_accs = []
        if target_arg:
            inst = self._resolve_account(target_arg)
            if inst:
                target_accs = [inst]
        elif curr_selected:
            inst = self._resolve_account(str(curr_selected))
            if inst:
                target_accs = [inst]

        if not target_accs:
            target_accs = accs

        # 2. Xử lý hành động on/off nếu có
        subs = [a.lower().strip() for a in (sub_args or [])]
        if any(x in ("on", "start", "1") for x in subs):
            for a in target_accs:
                if a.client:
                    a.client.start_auto_quest()
            target_name = f"Acc #{target_accs[0].config.acc_id} ({target_accs[0].char_name})" if len(target_accs) == 1 else "Toàn bộ tài khoản"
            self.send_message(chat_id, f"[=] *[NV BÒ MỘNG]* Đã BẬT tự động làm nhiệm vụ cho *{target_name}*!")
            return

        if any(x in ("off", "stop", "0") for x in subs):
            for a in target_accs:
                if a.client:
                    a.client.stop_auto_quest()
            target_name = f"Acc #{target_accs[0].config.acc_id} ({target_accs[0].char_name})" if len(target_accs) == 1 else "Toàn bộ tài khoản"
            self.send_message(chat_id, f"[=] *[NV BÒ MỘNG]* Đã TẮT tự động làm nhiệm vụ cho *{target_name}*!")
            return

        # 3. Hiển thị bảng trạng thái NVBM trực quan
        lines = [
            "[i] *TỰ ĐỘNG NHIỆM VỤ BÒ MỘNG*",
            "=============================",
        ]

        for a in target_accs:
            c = a.client
            st = c.get_quest_status() if c else {}
            is_running = st.get("is_running", False)
            state_desc = st.get("state", "Đang nghỉ")
            q_desc = st.get("quest", "Chưa có")
            quests_done = st.get("quests_completed", 0)
            total_kills = st.get("total_kills", 0)
            time_str = st.get("time_str", "0m00s")
            status_tag = "[Bật]" if is_running else "[Tắt]"

            lines.append(f"> *Acc #{a.config.acc_id}* ({a.char_name}): {status_tag}")
            lines.append(f"  = *Trạng thái:* {state_desc}")
            lines.append(f"  = *Nhiệm vụ:* {q_desc}")
            lines.append(f"  = *Đã hoàn thành:* {quests_done} NV | *Đã diệt:* {total_kills} quái")
            lines.append(f"  = *Thời gian chạy:* {time_str}")
            lines.append("")

        if lines and lines[-1] == "":
            lines.pop()

        lines.append("=============================")
        lines.append("[i]*Lệnh:* `/nvbm on` | `/nvbm off` | `/nvbm status`")
        self.send_message(chat_id, "\n".join(lines))

    def _handle_login_cmd(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        """Xử lý lệnh /login: Đăng nhập cho acc đang chọn hoặc toàn bộ acc."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        curr_selected = self.selected_targets.get(chat_id)
        if target_arg and target_arg.lower() in ("all", "tatca", "*"):
            self.account_manager.start_all(delay=1.5)
            self.send_message(
                chat_id,
                f"[=] *[ĐĂNG NHẬP]* Đang gửi yêu cầu kết nối lại cho TOÀN BỘ ({len(self.account_manager.accounts)}) tài khoản...",
                reply_markup=self.get_main_keyboard(chat_id)
            )
            return

        if target_arg:
            inst = self._resolve_account(target_arg)
        elif curr_selected:
            inst = self._resolve_account(str(curr_selected))
        else:
            # Ngữ cảnh ALL -> start all
            self.account_manager.start_all(delay=1.5)
            self.send_message(
                chat_id,
                f"[=] *[ĐĂNG NHẬP]* Đang gửi yêu cầu kết nối lại cho TOÀN BỘ ({len(self.account_manager.accounts)}) tài khoản...",
                reply_markup=self.get_main_keyboard(chat_id)
            )
            return

        if not inst:
            self.send_message(chat_id, f"[!] Không tìm thấy tài khoản '{target_arg}'.")
            return

        if inst.client and inst.client.isConnected():
            self.send_message(chat_id, f"[i] [{inst.tag}] Tài khoản đã đang ONLINE!")
            return

        inst.is_manual_stopping = False
        ok = self.account_manager.start_account(inst)
        st_text = "Thành công" if ok else "Đang kết nối..."
        self.send_message(
            chat_id,
            f"[=] *[ĐĂNG NHẬP]* Đang kết nối tài khoản *{inst.tag}* ({st_text})...",
            reply_markup=self.get_main_keyboard(chat_id)
        )

    def _handle_logout_cmd(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        """Xử lý lệnh /logout: Đăng xuất an toàn và ngắt kết nối cho acc đang chọn hoặc toàn bộ acc."""
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        curr_selected = self.selected_targets.get(chat_id)
        if target_arg and target_arg.lower() in ("all", "tatca", "*"):
            self.account_manager.stop_all()
            self.send_message(
                chat_id,
                f"[=] *[ĐĂNG XUẤT THÀNH CÔNG]* Đã ngắt kết nối an toàn TOÀN BỘ ({len(self.account_manager.accounts)}) tài khoản (đã dừng auto-reconnect).",
                reply_markup=self.get_main_keyboard(chat_id)
            )
            return

        if target_arg:
            inst = self._resolve_account(target_arg)
        elif curr_selected:
            inst = self._resolve_account(str(curr_selected))
        else:
            # Ngữ cảnh ALL -> stop all
            self.account_manager.stop_all()
            self.send_message(
                chat_id,
                f"[=] *[ĐĂNG XUẤT THÀNH CÔNG]* Đã ngắt kết nối an toàn TOÀN BỘ ({len(self.account_manager.accounts)}) tài khoản (đã dừng auto-reconnect).",
                reply_markup=self.get_main_keyboard(chat_id)
            )
            return

        if not inst:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản '{target_arg}'.")
            return

        self.account_manager.stop_account(inst)
        self.send_message(
            chat_id,
            f"[=] *[ĐĂNG XUẤT THÀNH CÔNG]* Đã ngắt kết nối an toàn cho *{inst.tag}* (đã dừng auto-reconnect)!",
            reply_markup=self.get_main_keyboard(chat_id)
        )

    def _execute_direct_command(self, chat_id: Union[int, str], cmd_line: str) -> None:
        """Thực thi lệnh CLI thông qua command_handler và phản hồi kết quả."""
        if not self.account_manager:
            self.send_message(chat_id, "[!] Hệ thống quản lý tài khoản chưa sẵn sàng.")
            return

        # Hỗ trợ cú pháp tắt /1 <lệnh> -> acc 1 <lệnh>
        parts = cmd_line.split()
        if parts:
            first = parts[0].lstrip("#")
            if first.isdigit() and len(parts) > 1:
                cmd_line = f"acc {first} " + " ".join(parts[1:])

        from .command_handler import execute_multi_command
        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        try:
            execute_multi_command(self.account_manager, None, cmd_line)
            raw_output = buffer.getvalue().strip()
            # Xóa mã escape màu ANSI
            output = re.sub(r'\x1b\[[0-9;]*[mK]', '', raw_output).strip()
        except Exception as ex:
            output = f"Lỗi khi thực thi lệnh '{cmd_line}': {ex}"
        finally:
            sys.stdout = old_stdout

        if not output:
            output = f"[=] Đã thực thi lệnh: `{cmd_line}`"

        self.send_message(chat_id, output)

    def _handle_ai_query(self, chat_id: Union[int, str], query: str) -> None:
        """Xử lý câu hỏi tự nhiên bằng AI OpenRouter."""
        if not self.ai_enabled or not self.ai_api_key:
            self.send_message(
                chat_id,
                f"[i] Trợ lý AI chưa được kích hoạt. Hãy dùng các nút bên dưới hoặc cấu hình API Key OpenRouter trong `settings.json`."
            )
            return

        # Báo bot đang xử lý
        self._api_call("sendChatAction", {"chat_id": chat_id, "action": "typing"})

        ai_reply = self.query_openrouter_ai(query, chat_id=chat_id)

        # Kiểm tra xem AI có sinh thẻ lệnh [EXEC: <lệnh>] không
        exec_matches = re.findall(r"\[EXEC:\s*(.+?)\]", ai_reply, re.IGNORECASE)
        clean_reply = re.sub(r"\[EXEC:\s*(.+?)\]", "", ai_reply).strip()

        exec_results = []
        if exec_matches and self.account_manager:
            from .command_handler import execute_multi_command
            for cmd in exec_matches:
                cmd = cmd.strip()
                try:
                    execute_multi_command(self.account_manager, None, cmd)
                    exec_results.append(f"> Đã thực thi: `{cmd}`")
                except Exception as ex:
                    exec_results.append(f"[x] Lỗi thực thi `{cmd}`: {ex}")

        final_msg = clean_reply
        if exec_results:
            final_msg += "\n\n" + "\n".join(exec_results)

        self.send_message(chat_id, final_msg)

    # --------------------------------------------------------------------------
    # Các hàm gửi thông báo sự kiện (Notifications)
    # --------------------------------------------------------------------------
    def notify_boss_event(self, boss_name: str, map_name: str, zone_id: int, is_killed: bool, killer: str = "") -> None:
        """Gửi thông báo Boss xuất hiện hoặc bị hạ tới Telegram (chống trùng lặp giữa nhiều tài khoản)."""
        if not self.notify_boss:
            return

        now = time.time()
        # Chống trùng lặp thông báo Boss giữa các tài khoản cùng nhận được trong vòng 15 giây
        event_key = f"{boss_name.strip().lower()}:{map_name.strip().lower()}:{is_killed}"
        with self._lock:
            last_time = self._recent_boss_events.get(event_key, 0.0)
            if now - last_time < 15.0:
                # Đã gửi thông báo từ tài khoản khác trong vòng 15 giây -> Bỏ qua
                return
            self._recent_boss_events[event_key] = now
            # Dọn dẹp cache
            self._recent_boss_events = {k: v for k, v in self._recent_boss_events.items() if now - v < 60.0}

        if is_killed:
            killer_str = f" bởi *{killer}*" if killer else ""
            msg = f"= *[BOSS BỊ TIÊU DIỆT]*\nBoss *{boss_name}* đã bị tiêu diệt{killer_str}!"
        else:
            z_str = f" (Khu {zone_id})" if zone_id >= 0 else ""
            msg = f"= *[BOSS XUẤT HIỆN]*\nBoss *{boss_name}* đã xuất hiện tại *{map_name}*{z_str}!"
        self.broadcast_message(msg)

    def notify_disconnect_event(self, account_tag: str, delay_sec: float = 10.0) -> None:
        """Gửi thông báo tài khoản bị rớt mạng."""
        if not self.notify_disconnect:
            return
        msg = f"[!] *[MẤT KẾT NỐI]*\n[{account_tag}] Mất kết nối tới máy chủ!\nSẽ tự động kết nối lại sau {int(delay_sec)}s..."
        self.broadcast_message(msg)

    def notify_login_event(self, account_tag: str, char_name: str, map_id: int, is_reconnect: bool = False) -> None:
        """Gửi thông báo đăng nhập hoặc kết nối lại thành công."""
        if not self.notify_login:
            return
        action = "Tự động kết nối lại thành công" if is_reconnect else "Vào game thành công"
        msg = f"[=] *[{action.upper()}]*\n[{account_tag}] Nhân vật: *{char_name}* | Map: `{map_id}`"
        self.broadcast_message(msg)

    # --------------------------------------------------------------------------
    # Vòng lặp Long Polling
    # --------------------------------------------------------------------------
    def _poll_worker(self) -> None:
        logger.system(f"Telegram Bot (@nroPy_Bot) đã khởi động! Đang lắng nghe tin nhắn...")
        while self._running:
            # Mạng NAT siết chặt có thể cắt kết nối treo lâu: thất bại liên tiếp
            # thì tự hạ về short-poll (timeout=0, hỏi nhanh từng giây) để vẫn nhận lệnh.
            eff_hold = 0 if self._poll_fail_streak >= 3 else self._poll_hold
            try:
                payload = {
                    "offset": self._last_update_id + 1,
                    "timeout": eff_hold,
                }
                res = self._api_call("getUpdates", payload, timeout=eff_hold + 15)
                if res and res.get("ok"):
                    self._poll_fail_streak = 0
                    self._last_poll_ok = time.time()
                    self._last_poll_error = ""
                    updates = res.get("result", [])
                    for update in updates:
                        up_id = update.get("update_id", 0)
                        if up_id > self._last_update_id:
                            self._last_update_id = up_id
                        msg = update.get("message") or update.get("channel_post")
                        if msg:
                            try:
                                self._handle_incoming_message(msg)
                            except Exception as ex_msg:
                                logger.error(f"[Telegram] Lỗi xử lý tin nhắn: {ex_msg}")
                            self._poll_updates += 1
                    if eff_hold == 0:
                        time.sleep(1.0)  # short-poll: nghỉ 1s tránh spam API
                else:
                    self._poll_fail_streak += 1
                    err_code = (res or {}).get("error_code")
                    desc = (res or {}).get("description") or "mất mạng/timeout"
                    new_err = f"HTTP {err_code}: {desc}" if err_code else f"getUpdates thất bại ({desc})"
                    if new_err != self._last_poll_error:
                        self._last_poll_error = new_err
                        if err_code == 409:
                            logger.error("[Telegram] 409 CONFLICT: có nơi khác đang lấy tin nhắn (2 bot cùng token hoặc webhook đang bật). VPS này sẽ KHÔNG nhận được lệnh!")
                        else:
                            logger.warn(f"[Telegram] Polling lỗi: {new_err}. Đang thử lại...")
                    time.sleep(10.0 if err_code == 409 else 2.0)
            except Exception as ex:
                self._poll_fail_streak += 1
                if self._last_poll_error != str(ex):
                    self._last_poll_error = str(ex)
                    logger.warn(f"[Telegram Polling Exception] {ex}")
                time.sleep(2.0)

    def start(self) -> None:
        """Khởi động Telegram Bot trong background thread."""
        if not self.token:
            logger.warn("Telegram Bot chưa được cấu hình token trong settings.json!")
            return
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_worker, daemon=True, name="TelegramBotThread")
        self._thread.start()

    def stop(self) -> None:
        """Dừng Telegram Bot."""
        self._running = False
