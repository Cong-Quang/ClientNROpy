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


# ==============================================================================
# BẢNG TRA CỨU TÊN VẬT PHẨM, KỸ NĂNG VÀ TRANG BỊ CHUẨN NRO
# ==============================================================================
COMMON_ITEM_NAMES: Dict[int, str] = {
    0: "Áo Vải Thô (Trái Đất)",
    1: "Quần Vải Thô (Trái Đất)",
    2: "Giày Vải Thô (Trái Đất)",
    3: "Áo Sợi Len (Namếc)",
    4: "Quần Sợi Len (Namếc)",
    5: "Giày Sợi Len (Namếc)",
    6: "Áo Giáp Sắt (Xayda)",
    7: "Quần Giáp Sắt (Xayda)",
    8: "Giày Giáp Sắt (Xayda)",
    12: "Rada Cấp 1",
    13: "Đậu thần Cấp 1",
    14: "Đậu thần Cấp 2",
    15: "Đậu thần Cấp 3",
    16: "Đậu thần Cấp 4",
    17: "Đậu thần Cấp 5",
    18: "Đậu thần Cấp 6",
    19: "Đậu thần Cấp 7",
    20: "Đậu thần Cấp 8",
    60: "Đậu thần Cấp 9",
    61: "Đậu thần Cấp 10",
    77: "Cờ Caro",
    193: "Capsule Bay Thường",
    194: "Capsule Đặc Biệt (VIP)",
    211: "Nho Tím",
    212: "Nho Xanh",
    380: "Bổ Huyết",
    381: "Bổ Khí",
    382: "Giáp Xên",
    383: "Cuồng Nộ",
    384: "Ẩn Danh",
    385: "Bổ Huyết 2",
    441: "Ngọc Rồng 1 Sao",
    442: "Ngọc Rồng 2 Sao",
    443: "Ngọc Rồng 3 Sao",
    444: "Ngọc Rồng 4 Sao",
    445: "Ngọc Rồng 5 Sao",
    446: "Ngọc Rồng 6 Sao",
    447: "Ngọc Rồng 7 Sao",
    457: "Thỏi Vàng (500Tr Vàng)",
    521: "Bình Nước Phép",
    534: "Nước Mía",
    535: "Trà Đào",
    536: "Bánh Bao",
    568: "Hộp Quà May Mắn",
    569: "Kẹo Giáng Sinh",
    921: "Bông Tai Porata Cấp 2",
    922: "Mảnh Vỡ Bông Tai",
    1152: "Đá Nâng Cấp",
    1153: "Đá May Mắn",
}

SKILL_NAMES: Dict[int, str] = {
    0: "Đấm Dragon (Trái Đất)",
    1: "Kamejoko",
    6: "Thái Dương Hạ San",
    9: "Quả Cầu Kênh Khi",
    10: "Dịch Chuyển Tức Thời",
    19: "Thôi Miên",
    20: "Tự Phát Nổ",
    22: "Khiên Năng Lượng (TĐ)",
    2: "Đấm Demon (Namếc)",
    3: "Masenko",
    7: "Trị Thương",
    8: "Tái Tạo Năng Lượng",
    11: "Biến Sôcôla",
    12: "Đẻ Trứng",
    14: "Laser",
    4: "Đấm Galic (Xayda)",
    5: "Antomic",
    13: "Biến Khỉ (Hóa Khỉ)",
    17: "Trói Tự Động",
    18: "Huýt Sáo",
    21: "Khiên Năng Lượng (XD)",
}

BODY_SLOT_NAMES: Dict[int, str] = {
    0: "Áo",
    1: "Quần",
    2: "Găng tay",
    3: "Giày",
    4: "Rada",
    5: "Cải trang",
    6: "Giáp luyện tập",
    7: "Phụ kiện",
    8: "Linh thú",
    9: "Bông tai Porata",
    10: "Chân mệnh",
}


def format_big_number(val: int) -> str:
    """Định dạng số lớn theo phong cách người chơi NRO (Tỷ, Triệu, k)."""
    if val >= 1_000_000_000:
        return f"{val / 1_000_000_000:.1f} Tỷ"
    if val >= 1_000_000:
        return f"{val / 1_000_000:.1f} Tr"
    if val >= 1_000:
        return f"{val / 1_000:.1f}k"
    return str(val)


def get_item_display_name(template_id: int, fallback_info: str = "") -> str:
    """Lấy tên hiển thị trực quan của vật phẩm."""
    if template_id in COMMON_ITEM_NAMES:
        return COMMON_ITEM_NAMES[template_id]
    if fallback_info and fallback_info.strip():
        return fallback_info.strip()
    return f"Vật phẩm #{template_id}"


def get_skill_display_name(skill_id: int) -> str:
    """Lấy tên kỹ năng hiển thị."""
    return SKILL_NAMES.get(skill_id, f"Chiêu #{skill_id}")


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

        # Ngữ cảnh tài khoản đang chọn điều khiển cho từng người chat (None = ALL)
        self.selected_targets: Dict[Union[int, str], Optional[int]] = {}

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
        """Bàn phím gọn: chọn acc (kèm trạng thái ON/OFF) + vài lệnh nhanh."""
        selected = self.selected_targets.get(chat_id) if chat_id else None

        # Hàng 1: ngữ cảnh ALL (dấu [>] = đang chọn)
        all_marker = "[>]" if selected is None else "[ ]"
        keyboard = [[{"text": f"{all_marker} Tất cả [ALL]"}]]

        # Các hàng chọn acc: mỗi hàng 2 nút, hiển thị [ON]/[OFF] + tên
        if self.account_manager and self.account_manager.accounts:
            row = []
            for a in self.account_manager.accounts:
                cname = a.char_name if a.char_name != "Chưa vào" else a.config.username
                online = bool(a.client and a.client.isConnected())
                state = "[ON]" if online else "[OFF]"
                is_sel = (selected == a.config.acc_id or selected == str(a.config.acc_id))
                prefix = "> " if is_sel else ""
                row.append({"text": f"{prefix}{state} Acc #{a.config.acc_id}: {cname}"})
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
            if row:
                keyboard.append(row)

        # Hàng lệnh tra cứu
        keyboard.append([
            {"text": "/status"},
            {"text": "/goto"},
            {"text": "/info"},
            {"text": "/help"},
        ])

        # Hàng lệnh train cơ bản (tự áp dụng vào acc đang chọn)
        keyboard.append([
            {"text": "/ts on"},
            {"text": "/ts off"},
            {"text": "/zone min"},
            {"text": "/harvest"},
        ])

        return {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "is_persistent": True,
        }

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
        alive_str = "[x] ĐÃ CHẾT" if is_dead else "[=] CÒN SỐNG"

        hp_pct = round((char.cHP / max(1, char.cHPFull)) * 100, 1)
        mp_pct = round((char.cMP / max(1, char.cMPFull)) * 100, 1)

        map_id = char.mapInfo.mapID if char.mapInfo else -1
        map_name = char.mapInfo.mapName if char.mapInfo and char.mapInfo.mapName else f"Map {map_id}"
        zone_id = char.mapInfo.zoneID if char.mapInfo else -1
        planet_names = {0: "Trái Đất", 1: "Namếc", 2: "Xayda", 3: "Hành tinh khác"}
        map_planet = planet_names.get(char.mapInfo.planetID, "Không rõ") if char.mapInfo else "Không rõ"

        # Nhiệm vụ
        task_str = getattr(char, "task_name", "") or f"Nhiệm vụ Task ID: {char.ctaskId}"

        # Kỹ năng
        skills_str = ", ".join([get_skill_display_name(sk) for sk in char.skills]) if char.skills else "Chưa có kỹ năng đặc biệt"

        lines = [
            f"= *THÔNG TIN CHI TIẾT TÀI KHOẢN [{inst.tag}]*",
            f"=============================",
            f"> *1. THÔNG TIN BẢN THÂN (CHARACTER):*",
            f"> Tên nhân vật:    *{char.cName}* (ID: `{char.charID}`)",
            f"> Hành tinh:       *{gender_str}* | Lớp: `{class_str}`",
            f"> Trạng thái:      *{alive_str}* | Kết nối: *{inst.status}*",
            f"> HP (Máu):        *{char.cHP:,} / {char.cHPFull:,}* ({hp_pct}%)",
            f"> KI / MP (Nội lực): *{char.cMP:,} / {char.cMPFull:,}* ({mp_pct}%)",
            f"> Sức mạnh:        *{char.cPower:,}* ({format_big_number(char.cPower)})",
            f"> Tiềm năng:       *{char.cTiemNang:,}* ({format_big_number(char.cTiemNang)})",
            f"> Sức đánh (Dam):  *{char.cDamFull:,}* (Gốc: `{char.cDamGoc:,}`)",
            f"> Giáp (Def):      *{char.cDefull:,}* (Gốc: `{char.cDefGoc:,}`)",
            f"> Chí mạng (Crit): *{char.cCriticalFull}%* (Gốc: `{char.cCriticalGoc}%`)",
            f"> Tốc độ chạy:     *{char.cspeed}*",
            f"> Tài sản tiền tệ:",
            f"  ↳ = Vàng (Xu): *{char.xu:,}* ({format_big_number(char.xu)} Xu)",
            f"  ↳ = Ngọc xanh: *{char.luong:,}* Lượng",
            f"  ↳ = Ngọc hồng: *{char.luongKhoa:,}* Lượng khóa",
            f"> Nhiệm vụ:        *{task_str}*",
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
            lines.append(f"> HP (Máu đệ):     *{pet.cHP:,} / {pet.cHPFull:,}* ({pet_hp_pct}%)")
            lines.append(f"> KI / MP:         *{pet.cMP:,} / {pet.cMPFull:,}* ({pet_mp_pct}%)")
            lines.append(f"> Sức đánh:        *{pet.cDamFull:,}* | Giáp: *{pet.cDefull:,}* | Chí mạng: *{pet.cCriticalFull}%*")
            lines.append(f"> Sức mạnh:        *{pet.cPower:,}* ({format_big_number(pet.cPower)}) | Tiềm năng: *{format_big_number(pet.cTiemNang)}*")
            lines.append(f"> Thể lực:         *{pet.cStamina} / {pet.cMaxStamina}* ({pet_sta_pct}%)")
            lines.append(f"> Kỹ năng đệ:      `{pet_skills}`")
            lines.append(f"> Trang bị đệ:     *{len(pet.arrItemBody)}* món trang bị")
        else:
            lines.append("> Hiện tại nhân vật chưa có đệ tử.")

        # 3. Bản đồ & Khu vực (Zone)
        lines.append(f"\n= *3. BẢN ĐỒ & KHU VỰC (ZONE):*")
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

        # 4. Cây đậu thần
        lines.append(f"\n= *4. CÂY ĐẬU THẦN (MAGIC TREE):*")
        tree = char.magicTree
        if tree:
            sec_str = f"Chín sau {tree.seconds}s ({int(tree.seconds/60)} phút)" if tree.seconds > 0 else "Đậu đã chín đầy đủ!"
            pea_pct = round((tree.currPeas / max(1, tree.maxPeas)) * 100, 1)
            lines.append(f"> Cây đậu Cấp {tree.level}: *{tree.currPeas} / {tree.maxPeas}* hạt ({pea_pct}%)")
            lines.append(f"> Tình trạng:      *{sec_str}* (Gõ `/harvest` để thu hoạch)")
        else:
            lines.append("> Chưa có dữ liệu cây đậu.")

        # 5. Hành trang Balo
        bag = char.arrItemBag
        lines.append(f"\n= *5. HÀNH TRANG BALO ({len(bag)} món):*")
        if not bag:
            lines.append("> (Balo hiện đang trống)")
        else:
            show_count = min(12, len(bag))
            for idx in range(show_count):
                it = bag[idx]
                it_name = get_item_display_name(it.template_id, it.info)
                opts = " | ".join([opt.getText() for opt in it.options[:2]])
                opt_str = f" [{opts}]" if opts else ""
                lines.append(f"`{idx+1:02d}.` *{it_name}* x{it.quantity} (ID: `{it.template_id}`){opt_str}")
            if len(bag) > show_count:
                lines.append(f"... và *{len(bag) - show_count}* món khác. Gõ `/bag #{inst.config.acc_id}` để xem toàn bộ!")

        # 6. Trang bị đang mặc (Body)
        body = char.arrItemBody
        lines.append(f"\n= *6. TRANG BỊ ĐANG MẶC ({len(body)} món):*")
        if not body:
            lines.append("> (Chưa mặc trang bị)")
        else:
            for idx, it in enumerate(body):
                slot_title = BODY_SLOT_NAMES.get(idx, f"Món {idx+1}")
                it_name = get_item_display_name(it.template_id, it.info)
                opts = " | ".join([opt.getText() for opt in it.options[:3]])
                opt_str = f"\n   ↳ _{opts}_" if opts else ""
                lines.append(f"> [{slot_title}] *{it_name}* (ID: `{it.template_id}`){opt_str}")

        # 7. Rương đồ tóm tắt
        box = char.arrItemBox
        lines.append(f"\n= *7. RƯƠNG ĐỒ ({len(box)} món):*")
        lines.append(f"> Đang chứa *{len(box)}* vật phẩm trong rương đồ. Gõ `/box #{inst.config.acc_id}` để xem chi tiết.")

        # 8. Cấu hình Auto & Hệ thống
        lines.append(f"\n= *8. CẤU HÌNH AUTO & HỆ THỐNG:*")
        cbm = client.combat_manager
        bh = client.boss_hunter
        rec_str = f"BẬT ({int(self.account_manager.reconnect_delay)}s)" if (self.account_manager and self.account_manager.auto_reconnect) else "TẮT"
        lines.append(f"> Auto Săn Boss:   {'[=] BẬT' if bh.is_hunting else '[ ] TẮT'}")
        lines.append(f"> Tự Đánh (AK):    {'[=] BẬT' if cbm.is_ak else '[ ] TẮT'}")
        lines.append(f"> Tàn Sát (TS):    {'[=] BẬT' if cbm.is_tansat else '[ ] TẮT'} (Chế độ: `{cbm.tansat_mode}`)")
        lines.append(f"> Tự Nhặt Đồ:      {'[=] BẬT' if cbm.auto_pick else '[ ] TẮT'}{' (Chỉ ngọc)' if cbm.pick_gem_only else ''}")
        lines.append(f"> Né Siêu Quái:    {'[=] BẬT' if cbm.avoid_super_mob else '[ ] TẮT'}")
        lines.append(f"> Tự Ăn Đậu (ABF): {'[=] BẬT' if cbm.auto_pean else '[ ] TẮT'} (khi < {int(cbm.pean_threshold*100)}%)")
        lines.append(f"> Tự Hồi Sinh:     {'[=] BẬT' if client.auto_revive_manager.is_enabled else '[ ] TẮT'} (Mode: `{client.auto_revive_manager.mode}`)")
        lines.append(f"> Auto NV Bò Mộng: {'[=] BẬT' if client.auto_quest_manager.is_running else '[ ] TẮT'}")
        lines.append(f"> Auto-Reconnect:  *{rec_str}* | Proxy: *{inst.proxy_str}*")

        lines.append(f"=============================")
        lines.append(f"> *Lệnh nhanh:* `/pet follow|attack|fuse` > `/harvest` > `/bag` > `/box` > `/map` > `/xmap 0`")

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
            opt_str = f"\n   ↳ *Chỉ số:* _{opts}_" if opts else ""
            desc_str = f"\n   ↳ *Ghi chú:* {it.content}" if (it.content and it.content != it_name) else ""
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
            opt_str = f"\n   ↳ *Chỉ số:* _{opts}_" if opts else ""
            desc_str = f"\n   ↳ *Ghi chú:* {it.content}" if (it.content and it.content != it_name) else ""
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
            f"> HP (Máu):        *{pet.cHP:,} / {pet.cHPFull:,}* ({pet_hp_pct}%)",
            f"> KI / MP:         *{pet.cMP:,} / {pet.cMPFull:,}* ({pet_mp_pct}%)",
            f"> Sức đánh:        *{pet.cDamFull:,}*",
            f"> Giáp:            *{pet.cDefull:,}*",
            f"> Chí mạng:        *{pet.cCriticalFull}%*",
            f"> Sức mạnh:        *{pet.cPower:,}* ({format_big_number(pet.cPower)})",
            f"> Tiềm năng:       *{pet.cTiemNang:,}* ({format_big_number(pet.cTiemNang)})",
            f"> Thể lực:         *{pet.cStamina} / {pet.cMaxStamina}* ({pet_sta_pct}%)",
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
                task_desc = getattr(char, "task_name", "") or f"Task ID {char.ctaskId}"
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
                cbm = a.client.combat_manager
                bh = a.client.boss_hunter
                autos = []
                if bh.is_hunting: autos.append("Săn Boss")
                if cbm.is_ak: autos.append("Tự Đánh")
                if cbm.is_tansat: autos.append(f"Tàn Sát ({cbm.tansat_mode})")
                if cbm.auto_pick: autos.append("Tự Nhặt")
                if cbm.auto_pean: autos.append("Tự Dùng Đậu")
                if a.client.auto_revive_manager.is_enabled: autos.append("Tự Hồi Sinh")
                if a.client.auto_quest_manager.is_running: autos.append("Auto Bò Mộng")
                parts.append(f"Auto đang bật: {', '.join(autos) if autos else 'Không'}")

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
                self.send_message(chat_id, "[x] Bạn không có quyền điều khiển bot này.", with_keyboard=False)
                return

        # Đưa vào danh sách active để nhận broadcast
        with self._lock:
            self.active_chat_ids.add(chat_id)

        # ----------------------------------------------------------------------
        # A. Xử lý các nút bấm chuyển ngữ cảnh tài khoản (ReplyKeyboardMarkup)
        # ----------------------------------------------------------------------
        # Nút "[>] Tất cả [ALL]" (chọn ngữ cảnh ALL)
        if "tất cả [all]" in text.lower() or "tất cả (all)" in text.lower():
            self.selected_targets[chat_id] = None
            self.send_message(
                chat_id,
                "= Đã chuyển ngữ cảnh sang: *TOÀN BỘ TÀI KHOẢN [ALL]*!\n"
                "Mọi lệnh tiếp theo (`/info`, `/goto`, `/hunt`, `/harvest`...) sẽ áp dụng cho tất cả tài khoản.",
                reply_markup=self.get_main_keyboard(chat_id)
            )
            return

        # Nút "[ON] Acc #1: tên" (chọn 1 acc, có thể kèm dấu ">" khi đang chọn)
        acc_match = re.search(r"acc\s*#(\d+)", text, re.IGNORECASE)
        if acc_match and "acc #" in text.lower():
            acc_id = int(acc_match.group(1))
            inst = self.account_manager.get_account(str(acc_id)) if self.account_manager else None
            if not inst:
                self.send_message(chat_id, f"[x] Không tìm thấy Acc #{acc_id}. Gõ `/status` để xem danh sách.")
                return
            cname = inst.char_name if inst.char_name != "Chưa vào" else inst.config.username
            online = "ONLINE" if (inst.client and inst.client.isConnected()) else "OFFLINE"
            self.selected_targets[chat_id] = acc_id
            self.send_message(
                chat_id,
                f"> Đã chọn tài khoản: *Acc #{acc_id} ({cname})* [{online}]\n"
                f"Các lệnh (`/info`, `/goto`, `/ts`, `/zone`...) tiếp theo sẽ áp dụng riêng cho tài khoản này.",
                reply_markup=self.get_main_keyboard(chat_id)
            )
            return

        # ----------------------------------------------------------------------
        # B. Các lệnh menu & hướng dẫn cơ bản
        # ----------------------------------------------------------------------
        if text.lower() in ("/start", "/help", "help", "trogiup", "/menu", "/keyboard", "/phim"):
            self._send_help_message(chat_id)
            return

        if text.lower() in ("/reset", "reset"):
            self.selected_targets[chat_id] = None
            self.send_message(chat_id, "> Đã cài lại ngữ cảnh về mặc định: *TOÀN BỘ TÀI KHOẢN [ALL]*.")
            return

        # ----------------------------------------------------------------------
        # C. Bảng tổng hợp trạng thái
        # ----------------------------------------------------------------------
        if text.lower() in ("/status", "status", "/st", "st", "list", "/list"):
            self._send_status_message(chat_id)
            return

        parts = text.split()
        first_token = parts[0].lower().lstrip("/")

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
        # G. QUẢN LÝ TÀI KHOẢN & PROXY (CRUD) — vd: /adduser poopooi03 02082003
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
                    "Cú pháp: `/addproxy <proxy>`\nVd: `/addproxy socks5://u:p@1.2.3.4:1080`"
                )
                return
            ok, msg = self.account_manager.add_proxy_and_save(sub_args[0])
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
                lines.append("  (chưa có proxy nào — thêm bằng `/addproxy`)")
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
            "nvbm", "nhiemvu", "quest", "bomong", "useitem", "shuttle", "dual",
            "tele", "tp", "focus", "chat", "reconnect", "autoreconnect", "rec",
            "telegram", "tg", "bot", "log", "mute", "cls", "clear", "exit", "quit"
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
    def _send_help_message(self, chat_id: Union[int, str]) -> None:
        selected = self.selected_targets.get(chat_id)
        sel_text = f"Acc #{selected}" if selected else "TOÀN BỘ TÀI KHOẢN [ALL]"

        help_text = (
            "= *CLIENT NRO PY - TELEGRAM BOT*\n"
            f"> *Ngữ cảnh đang chọn:* `{sel_text}`\n"
            "==============================\n"
            "> *NÚT BẤM:* bấm acc để chọn riêng, `[>] Tất cả [ALL]` để về tất cả.\n"
            "> Lệnh `/goto`, `/ts on`... tự chạy trên acc đang chọn.\n\n"
            "= *1. DI CHUYỂN & TREO FARM:*\n"
            "> `/goto <map> [min|khu] [ts|ak|hunt]` : tới map + đổi khu + bật auto\n"
            "> Vd: `/goto 112 min ts` (map 112, khu vắng nhất, bật tansat)\n"
            "> `/xmap <id|tên>` / `/xmap stop` : di chuyển / dừng\n"
            "> `/zone <khu>` hoặc `/zone min` : đổi khu / sang khu vắng nhất\n"
            "> `/ts [on|off]` : tàn sát quái | `/ak [on|off]` : tự đánh\n"
            "> `/harvest` : thu hoạch đậu thần\n\n"
            "= *2. XEM THÔNG TIN:*\n"
            "> `/status` : bảng trạng thái các acc\n"
            "> `/info [id|all]` : chi tiết 100% (HP, đệ, zone, balo, rương, đậu)\n"
            "> `/bag` / `/box` / `/pet` / `/map` / `/combat [id|all]`\n\n"
            "= *3. SĂN BOSS:*\n"
            "> `/hunt on` / `/hunt off` : bật/tắt Auto Săn Boss\n"
            "> `/boss go <tên|stt>` : bay tới Boss | `/boss alive` : Boss đang sống\n"
            "> `/nvbm [on|off]` : Auto NV Bò Mộng | `/autohs [on|off]` : tự hồi sinh\n\n"
            "= *4. QUẢN LÝ TÀI KHOẢN & PROXY:*\n"
            "> `/adduser <user> <pass> [proxy]` (vd: `/adduser poopooi03 02082003`)\n"
            "> `/deluser <user|id>` : xóa acc | `/setpass <user|id> <mk_moi>` : đổi mk\n"
            "> `/addproxy <proxy>` / `/delproxy <stt>` / `/listproxy` : quản lý proxy\n"
            "> `/setproxy <user|id> <proxy|off>` : gán proxy riêng cho acc\n"
            "> (tin nhắn chứa mật khẩu sẽ tự xóa sau khi xử lý)\n\n"
            "= *5. ĐIỀU KHIỂN & ÚP ĐỆ TỬ:*\n"
            "> `/pet follow|protect|attack|home|fuse|porata` (hoặc `0-5`)\n"
            "> `/trainpet [normal|avoid|kaioken|off]` : Auto Úp đệ tử thông minh\n"
            "> `/trainacc [on|off]` : Auto làm nhiệm vụ tân thủ sơ sinh (NV 0 -> 11)\n\n"
            "= *6. ĐA TÀI KHOẢN & HỆ THỐNG:*\n"
            "> `/acc <id> <lệnh>` : lệnh cho 1 acc (vd: `/acc 1 goto 112 min ts`, gõ tắt `/1 goto 112 min ts`)\n"
            "> `/all <lệnh>` : lệnh cho toàn bộ acc (vd: `/all hunt on`)\n"
            "> `/reconnect now` : kết nối lại ngay | `/chat <nội dung>` : chat vào game\n"
            "> `/notify <boss|login|dis> <on|off>` : bật/tắt thông báo tự động\n\n"
            "= *7. TRỢ LÝ AI (nhắn tiếng Việt tự nhiên):*\n"
            "> _'cho poopooi02 ra map 112 khu vắng rồi tansat'_\n"
            "> _'hentaiz còn bao nhiêu hp?'_ | _'bật săn boss lên'_\n"
            "> AI tự dịch thành lệnh và thực thi. Cần bật `ai.enabled` + API key trong `settings.json`."
        )
        self.send_message(chat_id, help_text)

    def _send_status_message(self, chat_id: Union[int, str]) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Hiện tại chưa có tài khoản nào được nạp.")
            return

        accs = self.account_manager.accounts
        lines = [
            "= *BẢNG TỔNG HỢP TRẠNG THÁI TÀI KHOẢN*",
            f"Tổng số: *{len(accs)} acc* | Auto-Reconnect: *{'BẬT' if self.account_manager.auto_reconnect else 'TẮT'}*",
            "==============================",
        ]
        for a in accs:
            st_icon = "=" if a.status == "ONLINE" else (">" if a.status in ("CONNECTING", "RECONNECTING") else ":")
            cname = a.char_name if a.char_name != "Chưa vào" else a.config.username
            hp = a.hp_str
            mz = a.map_zone_str
            auto = a.auto_status_str
            status_text = a.status
            if a.status == "RECONNECTING":
                rem = max(0, int(a.reconnect_timer_end - time.time()))
                status_text = f"Nối lại ({rem}s)"

            lines.append(f"{st_icon} *Acc #{a.config.acc_id}*: `{cname}`")
            lines.append(f"   > HP: `{hp}` | {mz}")
            lines.append(f"   > Trạng thái: *{status_text}* | Auto: `{auto}`")

        lines.append("==============================")
        lines.append("> Bấm chọn nút tài khoản bên dưới hoặc gõ `/info 1` để xem chi tiết.")
        self.send_message(chat_id, "\n".join(lines))

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

        if target_arg and target_arg.lower() in ("all", "tatca", "*"):
            for a in accs:
                info_text = self.format_char_full_info(a)
                self.send_message(chat_id, info_text)
            return

        if target_arg:
            inst = self._resolve_account(target_arg)
            if inst:
                self.send_message(chat_id, self.format_char_full_info(inst))
            else:
                self.send_message(chat_id, f"[x] Không tìm thấy tài khoản '{target_arg}'. Gõ `/status` để xem danh sách.")
            return

        # Nếu không truyền tham số:
        if len(accs) == 1:
            self.send_message(chat_id, self.format_char_full_info(accs[0]))
        else:
            self.send_message(chat_id, self.format_char_full_info(accs[0]))
            opts = [f"`/info {a.config.acc_id}`" for a in accs]
            prompt = f"\n> Đang quản lý {len(accs)} tài khoản. Bạn có thể nhấn nút tài khoản bên dưới hoặc gõ: " + ", ".join(opts) + " hoặc `/info all` để xem toàn bộ!"
            self.send_message(chat_id, prompt)

    def _send_bag_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        if target_arg and target_arg.lower() in ("all", "tatca", "*"):
            for a in self.account_manager.accounts:
                self.send_message(chat_id, self.format_char_bag_info(a))
            return
        inst = self._resolve_account(target_arg)
        if inst:
            self.send_message(chat_id, self.format_char_bag_info(inst))
        else:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản.")

    def _send_box_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return
        if target_arg and target_arg.lower() in ("all", "tatca", "*"):
            for a in self.account_manager.accounts:
                self.send_message(chat_id, self.format_char_box_info(a))
            return
        inst = self._resolve_account(target_arg)
        if inst:
            self.send_message(chat_id, self.format_char_box_info(inst))
        else:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản.")

    def _send_pet_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None, action_arg: Optional[str] = None) -> None:
        if not self.account_manager or not self.account_manager.accounts:
            self.send_message(chat_id, "[!] Chưa có tài khoản nào được nạp.")
            return

        action_map = {
            "0": 0, "follow": 0, "dtheo": 0, "theo": 0,
            "1": 1, "protect": 1, "baove": 1, "bv": 1,
            "2": 2, "attack": 2, "tancong": 2, "tc": 2, "danh": 2,
            "3": 3, "home": 3, "venha": 3, "nha": 3,
            "4": 4, "fuse": 4, "hopthe": 4, "ht": 4,
            "5": 5, "porata": 5, "bongtai": 5,
        }

        # Nếu tham số thứ nhất là hành động (ví dụ /pet attack hoặc /pet fuse)
        if target_arg and target_arg.lower() in action_map:
            act_code = action_map[target_arg.lower()]
            connected = [a for a in self.account_manager.accounts if a.client and a.client.isConnected()]
            if not connected:
                self.send_message(chat_id, "[!] Không có tài khoản nào đang Online để đổi trạng thái đệ.")
                return
            for a in connected:
                a.client.change_pet_status(act_code)
            st_names = {0: "Đi theo", 1: "Bảo vệ", 2: "Tấn công", 3: "Về nhà", 4: "Hợp thể", 5: "Hợp thể Porata"}
            self.send_message(chat_id, f"[=] Đã chuyển trạng thái đệ tử sang: *{st_names.get(act_code)}* cho {len(connected)} tài khoản!")
            return

        # Nếu có target_arg và action_arg (ví dụ /pet 1 attack)
        if action_arg and action_arg.lower() in action_map:
            act_code = action_map[action_arg.lower()]
            st_names = {0: "Đi theo", 1: "Bảo vệ", 2: "Tấn công", 3: "Về nhà", 4: "Hợp thể", 5: "Hợp thể Porata"}
            if target_arg.lower() in ("all", "tatca", "*"):
                connected = [a for a in self.account_manager.accounts if a.client and a.client.isConnected()]
                for a in connected:
                    a.client.change_pet_status(act_code)
                self.send_message(chat_id, f"[=] Đã chuyển trạng thái đệ tử sang: *{st_names.get(act_code)}* cho TOÀN BỘ tài khoản!")
                return
            inst = self._resolve_account(target_arg)
            if inst and inst.client:
                inst.client.change_pet_status(act_code)
                self.send_message(chat_id, f"[=] [{inst.tag}] Đã chuyển trạng thái đệ tử sang: *{st_names.get(act_code)}*!")
                return
            else:
                self.send_message(chat_id, f"[x] Không tìm thấy tài khoản '{target_arg}'.")
                return

        # Nếu chỉ xem thông tin đệ tử (/pet hoặc /pet 1 hoặc /pet all)
        if target_arg and target_arg.lower() in ("all", "tatca", "*"):
            for a in self.account_manager.accounts:
                self.send_message(chat_id, self.format_char_pet_info(a))
            return

        inst = self._resolve_account(target_arg)
        if inst:
            self.send_message(chat_id, self.format_char_pet_info(inst))
        else:
            self.send_message(chat_id, f"[x] Không tìm thấy tài khoản.")

    def _send_tree_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        inst = self._resolve_account(target_arg)
        if not inst or not inst.client or not inst.client.myChar:
            self.send_message(chat_id, "[!] Tài khoản chưa vào map.")
            return
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
        inst = self._resolve_account(target_arg)
        if inst:
            self.send_message(chat_id, self.format_char_map_info(inst))
        else:
            self.send_message(chat_id, "[x] Không tìm thấy tài khoản.")

    def _send_combat_message(self, chat_id: Union[int, str], target_arg: Optional[str] = None) -> None:
        inst = self._resolve_account(target_arg)
        if inst:
            self.send_message(chat_id, self.format_char_combat_info(inst))
        else:
            self.send_message(chat_id, "[x] Không tìm thấy tài khoản.")

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
