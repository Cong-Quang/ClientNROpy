# -*- coding: utf-8 -*-
"""
Mô-đun định dạng và hiển thị thông tin giao diện Console (display.py).

Mục tiêu:
- Giao diện Console gọn, dễ đọc và phù hợp Windows.
- Không emoji, không icon, không ký tự trang trí phức tạp.
- Tách thông tin tổng quan và chi tiết.
- Các hàm hiển thị giữ nguyên API dữ liệu của dự án.
- Có thể tái sử dụng formatter cho Telegram/mobile ở lớp UI phía trên.
"""

from typing import Optional, List, Any

from .char import Char
from .item import Item
from .pet import Pet
from .magic_tree import MagicTree
from .map_info import MapInfo
from .client import ClientNRO
from .game_data import format_big_number, get_item_name, SKILL_NAMES


# ============================================================
# Common UI helpers
# ============================================================

LINE = "=" * 78
LINE_WIDE = "=" * 94
LINE_SHORT = "-" * 78
LINE_BOX = "-" * 60


def _status_text(status: str) -> str:
    """Chuẩn hóa trạng thái thành văn bản, không dùng icon."""
    mapping = {
        "ONLINE": "ONLINE",
        "OFFLINE": "OFFLINE",
        "CONNECTING": "CONNECTING",
        "RECONNECTING": "RECONNECTING",
        "ERROR": "ERROR",
    }
    return mapping.get(status, str(status or "UNKNOWN"))


def _bool_text(value: bool) -> str:
    return "ON" if value else "OFF"


def _safe(value: Any, default: str = "") -> str:
    return default if value is None else str(value)


def _print_title(title: str, width: int = 78) -> None:
    print("\n" + "=" * width)
    print(title.center(width))
    print("=" * width)


def _print_section(title: str, width: int = 60) -> None:
    print("\n" + "-" * width)
    print(title)
    print("-" * width)


def _print_menu(items: List[str], width: int = 60) -> None:
    for item in items:
        print(item)
    print("-" * width)


# ============================================================
# Main dashboard
# ============================================================

def print_banner():
    print(LINE)
    print("DRAGONBOY / NGOC RONG ONLINE - CLIENT SIMULATOR DA TAI KHOAN".center(78))
    print(LINE)


def print_accounts_table(account_manager) -> None:
    """In bang tong hop trang thai cua tat ca tai khoan."""
    accs = account_manager.accounts
    use_proxy = account_manager.proxy_pool.use_proxy
    proxy_count = len(account_manager.proxy_pool.proxies)
    rec_info = (
        f"ON ({int(account_manager.reconnect_delay)}s)"
        if account_manager.auto_reconnect
        else "OFF"
    )

    print("\n" + LINE_WIDE)
    proxy_info = (
        f"ON ({proxy_count} proxy, "
        f"{account_manager.proxy_pool.accounts_per_proxy} acc/proxy)"
        if use_proxy
        else "OFF (Direct)"
    )
    print(
        f"TÀI KHOẢN DASHBOARD ({len(accs)} ACC) | "
        f"PROXY: {proxy_info} | RECONNECT: {rec_info}"
    )
    print(LINE_WIDE)

    if not accs:
        print("Chưa có tài khoản. Kiểm tra accounts.json hoặc dùng 'acc add'.")
        print(LINE_WIDE + "\n")
        return

    header = (
        f"{'ID':<4} | {'TÀI KHOẢN':<14} | {'CHARACTER':<16} | "
        f"{'HP':<15} | {'MAP (ZONE)':<18} | {'STATUS':<14} | {'AUTO':<8}"
    )
    print(header)
    print("-" * len(header))

    import time

    online = 0
    reconnecting = 0
    errors = 0
    offline = 0

    for a in accs:
        acc_id = f"#{a.config.acc_id}"
        username = _safe(a.config.username)[:14]
        cname = _safe(a.char_name)[:16]
        hp = _safe(a.hp_str)[:15]
        map_zone = _safe(a.map_zone_str)[:18]
        auto = _safe(a.auto_status_str)[:8]

        if a.status == "RECONNECTING":
            rem = max(0, int(a.reconnect_timer_end - time.time()))
            status = f"RECONNECT {rem}s" if rem > 0 else "RECONNECT"
            reconnecting += 1
        elif not a.client or not a.client.isConnected():
            if a.status == "CONNECTING":
                status = "CONNECTING"
            elif a.status == "ERROR":
                status = "ERROR"
                errors += 1
            else:
                status = "OFFLINE"
                offline += 1
        elif a.status == "ONLINE":
            status = "ONLINE"
            online += 1
        elif a.status == "CONNECTING":
            status = "CONNECTING"
        elif a.status == "ERROR":
            status = "ERROR"
            errors += 1
        else:
            status = "OFFLINE"
            offline += 1

        row = (
            f"{acc_id:<4} | {username:<14} | {cname:<16} | "
            f"{hp:<15} | {map_zone:<18} | {status:<14} | {auto:<8}"
        )
        print(row)

    print(LINE_WIDE)
    print(
        f"TOTAL: {len(accs)} | ONLINE: {online} | "
        f"RECONNECT: {reconnecting} | ERROR: {errors} | OFFLINE: {offline}"
    )
    print("Gợi ý: 'all <lệnh>' thực thi lệnh trên tất cả tài khoản.")
    print("Gợi ý: 'use <id>' chọn một tài khoản.")
    print()


# ============================================================
# Nhân vật
# ============================================================

def print_character_overview(char: Char):
    _print_title(f"NHÂN VẬT: {char.cName} (ID: {char.charID})", 60)
    print(f"Sức mạnh:             {char.cPower:,} ({format_big_number(char.cPower)})")
    print(
        f"Tiềm năng:         {char.cTiemNang:,} "
        f"({format_big_number(char.cTiemNang)})"
    )
    print(f"HP:                {char.cHP:,} / {char.cHPFull:,}")
    print(f"KI / MP:           {char.cMP:,} / {char.cMPFull:,}")
    print(f"Vàng:              {char.xu:,} ({format_big_number(char.xu)} Xu)")

    ngoc_str = (
        f" ({format_big_number(char.luong)} Ngoc)"
        if char.luong >= 1000
        else ""
    )
    khoa_str = (
        f" ({format_big_number(char.luongKhoa)} Khoa)"
        if char.luongKhoa >= 1000
        else ""
    )

    print(f"Ngọc:              {char.luong:,}{ngoc_str}")
    print(f"Hồng ngọc:         {char.luongKhoa:,}{khoa_str}")
    print(f"Hệ phái:              {char.nClass}")
    print(f"Tọa độ:           ({char.cx}, {char.cy})")


# ============================================================
# Hành trang
# ============================================================

def _print_item_line(index: int, it: Item, include_id: bool = True) -> None:
    opts = " | ".join(opt.getText() for opt in it.options)
    opt_str = f" [{opts}]" if opts else ""
    item_name = get_item_name(it.template_id, it.info or "")

    id_str = f" | Template: {it.template_id}" if include_id else ""
    quantity = f"x{it.quantity}"

    print(
        f"  [{index:02d}] {item_name} {quantity}"
        f"{id_str}{opt_str}"
    )


def print_inventory(char: Char):
    _print_section(f"HÀNH TRANG - BALO ({len(char.arrItemBag)} ITEMS)")
    if not char.arrItemBag:
        print("  Balo trống.")
    else:
        for i, it in enumerate(char.arrItemBag, start=1):
            _print_item_line(i, it)

    _print_section(f"HÀNH TRANG - RƯƠNG ({len(char.arrItemBox)} ITEMS)")
    if not char.arrItemBox:
        print("  Rương trống.")
    else:
        for i, it in enumerate(char.arrItemBox, start=1):
            _print_item_line(i, it)

    _print_section(f"TRANG BỊ ({len(char.arrItemBody)} ITEMS)")
    if not char.arrItemBody:
        print("  Chưa có trang bị.")
    else:
        for i, it in enumerate(char.arrItemBody, start=1):
            _print_item_line(i, it, include_id=True)


# ============================================================
# Đệ tử
# ============================================================

def print_pet_info(pet: Pet):
    _print_section("ĐỆ TỬ / PET")

    if not pet.havePet:
        print("Chưa có đệ tử.")
        return

    print(f"Tên:               {pet.cName}")
    print(f"Trạng thái:        {pet.statusName}")
    print(f"HP:                {pet.cHP:,} / {pet.cHPFull:,}")
    print(f"KI / MP:           {pet.cMP:,} / {pet.cMPFull:,}")
    print(f"Sức đánh:          {pet.cDamFull:,}")
    print(f"Giáp:              {pet.cDefull:,}")
    print(f"Chí mạng:          {pet.cCriticalFull}%")
    print(f"Sức mạnh:          {pet.cPower:,} ({format_big_number(pet.cPower)})")
    print(
        f"Tiềm năng:         {pet.cTiemNang:,} "
        f"({format_big_number(pet.cTiemNang)})"
    )
    print(f"Stamina:           {pet.cStamina} / {pet.cMaxStamina}")
    print(f"Kỹ năng:           {pet.arrPetSkill}")
    print(f"Equipment:         {len(pet.arrItemBody)} items")

    for i, it in enumerate(pet.arrItemBody, start=1):
        opts = " | ".join(opt.getText() for opt in it.options)
        opt_str = f" [{opts}]" if opts else ""
        print(f"  [{i}] Template: {it.template_id}{opt_str}")


# ============================================================
# Cây đậu thần
# ============================================================

def print_magic_tree(tree: MagicTree):
    _print_section("CÂY ĐẬU THẦN")
    print(f"Tên:               {tree.name}")
    print(f"Cấp độ:              {tree.level}")
    print(f"Số hạt:              {tree.currPeas} / {tree.maxPeas}")
    print(f"Thời gian còn lại:     {tree.seconds} seconds")

    if tree.strInfo:
        print(f"Trạng thái:             {tree.strInfo}")


# ============================================================
# Bản đồ / Khu
# ============================================================

def print_map_and_zones(map_info: MapInfo):
    _print_title(
        f"BẢN ĐỒ: {map_info.mapName} "
        f"(ID: {map_info.mapID}, Hành tinh: {map_info.planetID})",
        78,
    )
    print(f"Khu vực hiện tại:       {map_info.zoneID}")

    if map_info.zones:
        _print_section(f"DANH SÁCH KHU ({len(map_info.zones)})")

        for z in map_info.zones:
            current = " CURRENT" if z.zoneId == map_info.zoneID else ""
            print(
                f"  Zone {z.zoneId:02d}: "
                f"{z.numPlayer:02d}/{z.maxPlayer:02d} players | "
                f"{z.status}{current}"
            )
    else:
        print("Chưa có danh sách khu vực.")

    _print_section(f"NGƯỜI CHƠI TRONG KHU ({len(map_info.chars)})")

    if not map_info.chars:
        print("  Không có người chơi khác.")
    else:
        for pid, c in map_info.chars.items():
            print(
                f"  {c.cName} "
                f"(ID: {pid}) | "
                f"HP: {c.cHP:,}/{c.cHPFull:,} | "
                f"Tọa độ: ({c.cx}, {c.cy})"
            )

    _print_section(f"QUÁI VẬT TRONG KHU ({len(map_info.mobs)})")

    if not map_info.mobs:
        print("  Không có quái vật.")
    else:
        for mid, m in list(map_info.mobs.items())[:10]:
            boss_str = " BOSS" if m.isBoss else ""
            print(
                f"  Mob #{mid}: Template {m.templateId}{boss_str} | "
                f"HP: {m.hp:,}/{m.maxHp:,} | "
                f"Tọa độ: ({m.x}, {m.y})"
            )

        if len(map_info.mobs) > 10:
            print(f"  ... {len(map_info.mobs) - 10} more mobs.")

    if map_info.items:
        _print_section(f"VẬT PHẨM DƯỚI ĐẤT ({len(map_info.items)})")
        for item_id, it in map_info.items.items():
            print(
                f"  Item #{item_id}: Template {it.itemTemplateID} "
                f"at ({it.x}, {it.y})"
            )

    if map_info.waypoints:
        _print_section(f"CỔNG DỊCH CHUYỂN ({len(map_info.waypoints)})")
        for wp in map_info.waypoints:
            print(
                f"  {wp.name}: "
                f"({wp.minX},{wp.minY}) -> ({wp.maxX},{wp.maxY})"
            )


# ============================================================
# Boss
# ============================================================

def print_boss_list(client: ClientNRO, filter_mode: str = "all"):
    all_bosses = client.get_bosses()
    alive_count = sum(1 for b in all_bosses if not b.is_died)
    dead_count = sum(1 for b in all_bosses if b.is_died)

    if filter_mode == "alive":
        display_bosses = [b for b in all_bosses if not b.is_died]
        title = "BOSS ĐANG SỐNG"
    elif filter_mode == "dead":
        display_bosses = [b for b in all_bosses if b.is_died]
        title = "BOSS ĐÃ CHẾT"
    else:
        display_bosses = all_bosses
        title = "TẤT CẢ BOSS"

    _print_title(
        f"{title} ({len(display_bosses)} BOSSES)",
        78,
    )
    print(f"CÒN SỐNG: {alive_count} | ĐÃ CHẾT: {dead_count}")
    print("-" * 78)

    if not display_bosses:
        print("Không có Boss phù hợp với bộ lọc.")
        print("=" * 78)
        return

    curr_map_id = (
        getattr(client.myChar.mapInfo, "mapID", -1)
        if client.myChar and client.myChar.mapInfo
        else -1
    )
    curr_zone_id = (
        getattr(client.myChar.mapInfo, "zoneID", -1)
        if client.myChar and client.myChar.mapInfo
        else -1
    )

    for b in display_bosses:
        try:
            stt = all_bosses.index(b) + 1
        except ValueError:
            stt = 0

        boss_str = b.to_string(
            use_color=True,
            current_map_id=curr_map_id,
            current_zone_id=curr_zone_id,
        )
        print(f"  [{stt:02d}] {boss_str}")

    print("=" * 78)


# ============================================================
# Auto hunt
# ============================================================

def print_hunt_status(client: ClientNRO):
    st = client.get_hunt_status()

    _print_title("TỰ ĐỘNG SĂN BOSS", 78)

    print(f"Trạng thái:              {_bool_text(st['is_enabled'])}")
    print(f"Trạng thái FSM:           {st['state']}")
    print(f"Thông báo:             {st['status_message']}")
    print(
        "Chế độ săn:           "
        f"{'TẤT CẢ BOSS' if st['hunt_all'] else 'WHITELIST'}"
    )

    targets_str = (
        ", ".join(st["target_bosses"])
        if st["target_bosses"]
        else "TẤT CẢ BOSS"
    )
    print(f"Danh sách Boss:           {targets_str}")

    combo_sids = st.get("combo_skills", [])
    combo_str = (
        " -> ".join(
            f"{s} ({SKILL_NAMES.get(s, 'Skill')})"
            for s in combo_sids
        )
        if combo_sids
        else "Default by planet"
    )
    print(f"Combo kỹ năng:         {combo_str}")

    coop_scanners = st.get("cooperative_scanners", 0)
    print(f"Tài khoản phối hợp:{coop_scanners}")

    print(f"Boss đã tiêu diệt:          {st.get('boss_kill_count', 0)}")
    print(
        f"Vật phẩm nhặt từ Boss:    "
        f"{st.get('boss_looted_items_count', 0)}"
    )

    looted_hist = st.get("boss_looted_items_history", [])
    if looted_hist:
        _print_section("LỊCH SỬ NHẶT ĐỒ BOSS")
        for item in looted_hist[-5:]:
            print(
                f"  {item.get('time', '')}: "
                f"{item.get('item_name', '')} | "
                f"Boss: {item.get('boss_name', '')} | "
                f"Map: {item.get('map_name', '')}"
            )

    print(f"Tự nhặt đồ:           {_bool_text(st['auto_loot'])}")
    print(f"Tự hồi sinh:         {_bool_text(st['auto_revive'])}")
    print(
        f"Tự động tuần tra:         "
        f"{_bool_text(st.get('auto_patrol', True))}"
    )

    if st["current_boss"]:
        b = st["current_boss"]
        z_str = (
            f"Zone {b.get('zone_id')}"
            if b.get("zone_id", -1) >= 0
            else "Unknown zone"
        )
        print(
            f"Boss hiện tại:        {b.get('name')} | "
            f"Map: {b.get('map_name')} ({b.get('map_id')}) | "
            f"{z_str}"
        )

    print("=" * 78)


# ============================================================
# Quest
# ============================================================

def print_quest_status(client: ClientNRO):
    st = client.get_quest_status()

    _print_title("TỰ ĐỘNG NHIỆM VỤ BÒ MỘNG", 78)

    print(f"Trạng thái:              {_bool_text(st['is_running'])}")
    print(f"State:               {st['state']}")
    print(f"Nhiệm vụ hiện tại:       {st['quest']}")
    print(f"Nhiệm vụ đã hoàn thành:    {st['quests_completed']}")
    print(f"Tổng số quái đã diệt:         {st['total_kills']}")
    print(f"Thời gian chạy:             {st['time_str']}")

    print("=" * 78)


# ============================================================
# Shuttle
# ============================================================

def print_shuttle_status(client: ClientNRO):
    st = client.get_shuttle_status()

    _print_title("SHUTTLE - TUYẾN HAI BẢN ĐỒ", 78)

    print(f"Trạng thái:              {_bool_text(st['is_running'])}")
    print(f"Tuyến:               {st['map_a']} <-> {st['map_b']}")
    print(f"Số lượt đã đi:      {st['legs_done']}")
    print(f"Thông báo:             {st['status_message']}")

    print("=" * 78)


# ============================================================
# Main interactive menu
# ============================================================

def print_main_menu(account_manager=None):
    """Menu Console tong quan, toi uu cho man hinh PC."""
    print()
    print("=" * 60)
    print("TRUNG TÂM ĐIỀU KHIỂN NRO".center(60))
    print("=" * 60)

    print()
    print("TÀI KHOẢNS")
    print("  1. Bảng tài khoản")
    print("  2. Chọn tài khoản")
    print("  3. Điều khiển tất cả tài khoản")
    print("  4. Kết nối / Đăng xuất")
    print("  5. Kết nối lại")
    print("  6. Proxy")

    print()
    print("AUTO")
    print("  7. Săn Boss")
    print("  8. Nhiệm vụ Bò Mộng")
    print("  9. Luyện đệ tử")
    print(" 10. Quái / PK")
    print(" 11. Tự động nhặt đồ")
    print(" 12. Tự động hồi sinh")
    print(" 13. Tự động hồi HP / KI")
    print(" 14. Tự động tuần tra")

    print()
    print("GAME")
    print(" 15. Boss")
    print(" 16. Bản đồ / Khu")
    print(" 17. Hành trang")
    print(" 18. Nhân vật")
    print(" 19. Đệ tử")
    print(" 20. Cây đậu thần")

    print()
    print("HỆ THỐNG")
    print(" 21. Telegram")
    print(" 22. Kết nối lại settings")
    print(" 23. Nhật ký")
    print(" 24. Cài đặt")
    print("  0. Thoát")

    print("-" * 60)

    if account_manager is not None:
        accs = account_manager.accounts
        online = 0
        for a in accs:
            try:
                if a.client and a.client.isConnected() and a.status == "ONLINE":
                    online += 1
            except Exception:
                pass

        print(
            f"Tài khoản: {len(accs)} | "
            f"Trực tuyến: {online} | "
            f"Tự động kết nối lại: "
            f"{_bool_text(account_manager.auto_reconnect)}"
        )

    print("-" * 60)
    print("Lựa chọn: ", end="")


# ============================================================
# ============================================================
# Cấu hình danh mục lệnh tập trung (Single Source of Truth)
# Dùng chung cho CLI Terminal và Telegram Bot để dễ cập nhật
# Không sử dụng emoji hay icon
# ============================================================

COMMAND_HELP_GROUPS = [
    {
        "category": "TÀI KHOẢN & PHẠM VI",
        "commands": [
            {
                "tg": "/status",
                "cli": "status / stt / ls",
                "desc": "Xem bảng tổng hợp trạng thái tài khoản",
            },
            {
                "tg": "/use <id|all>",
                "cli": "use <id|all>",
                "desc": "Chọn tài khoản thao tác (hoặc /1, /2...)",
            },
            {
                "tg": "/all <lệnh>",
                "cli": "all <command>",
                "desc": "Thực thi lệnh trên tất cả tài khoản",
            },
            {
                "tg": "/acc <id> <lệnh>",
                "cli": "acc <id> <command>",
                "desc": "Thực thi lệnh trên một tài khoản",
            },
            {
                "tg": "/login [id|all]",
                "cli": "login / connect [id|all]",
                "desc": "Kết nối tài khoản vào game",
            },
            {
                "tg": "/logout [id|all]",
                "cli": "logout / dis [id|all]",
                "desc": "Đăng xuất an toàn (dừng reconnect)",
            },
            {
                "tg": "/adduser <tk> <mk> [prx]",
                "cli": "acc add <user> <pass> [proxy]",
                "desc": "Thêm tài khoản mới và kết nối ngay",
            },
            {
                "tg": "/deluser <tk|id>",
                "cli": "acc del <user|id>",
                "desc": "Xóa tài khoản khỏi danh sách",
            },
            {
                "tg": "/setpass <tk|id> <mk_mới>",
                "cli": "acc edit <user|id> <pass_mới>",
                "desc": "Đổi mật khẩu cho tài khoản",
            },
        ],
    },
    {
        "category": "PROXY & THÔNG BÁO",
        "commands": [
            {
                "tg": "/setproxy <tk|id> <prx|off>",
                "cli": "acc edit <id> <pass> <proxy>",
                "desc": "Gán hoặc gỡ proxy cho tài khoản",
            },
            {
                "tg": "/addproxy <proxy>",
                "cli": "proxy add <proxy>",
                "desc": "Thêm proxy mới vào danh sách",
            },
            {
                "tg": "/delproxy <stt|prx>",
                "cli": "proxy del <stt|proxy>",
                "desc": "Xóa proxy khỏi danh sách",
            },
            {
                "tg": "/listproxy",
                "cli": "proxy list / ls",
                "desc": "Xem danh sách proxy đang có",
            },
            {
                "tg": "/notify [on|off]",
                "cli": "notify [on|off]",
                "desc": "Bật / tắt thông báo tự động (Boss, Server)",
            },
        ],
    },
    {
        "category": "BẢN ĐỒ & KHU VỰC",
        "commands": [
            {
                "tg": "/map",
                "cli": "map",
                "desc": "Xem bản đồ, quái, NPC, người chơi và item",
            },
            {
                "tg": "/zone [khu]",
                "cli": "zone [khu|min]",
                "desc": "Xem danh sách khu hoặc đổi khu",
            },
            {
                "tg": "/zone min",
                "cli": "zone min / all zone min",
                "desc": "Tản đều toàn đội vào các khu vắng nhất",
            },
            {
                "tg": "/xmap <id|tên>",
                "cli": "xmap <id|ten>",
                "desc": "Tự động di chuyển tới bản đồ",
            },
            {
                "tg": "/xmap stop",
                "cli": "xmap stop",
                "desc": "Dừng tự động di chuyển Xmap",
            },
            {
                "tg": "/goto <m> min ts",
                "cli": "goto <map> [min|khu] [ts]",
                "desc": "Combo: tới map -> chọn khu vắng -> bật tàn sát",
            },
        ],
    },
    {
        "category": "CHIẾN ĐẤU & TỰ ĐỘNG",
        "commands": [
            {
                "tg": "/hunt [on|off]",
                "cli": "hunt on / off / status",
                "desc": "Bật, tắt hoặc xem Auto Săn Boss",
            },
            {
                "tg": "/boss [alive|go]",
                "cli": "boss / boss alive / boss go",
                "desc": "Xem Boss xuất hiện hoặc bay tới Boss",
            },
            {
                "tg": "/ts [on|off|mob|pk]",
                "cli": "ts / tansat [on|off|mob|pk]",
                "desc": "Bật / tắt tàn sát quái hoặc PK",
            },
            {
                "tg": "/ak [on|off]",
                "cli": "ak [on|off]",
                "desc": "Tự động đánh mục tiêu đang focus",
            },
            {
                "tg": "/autohs [on|off|ngoc|ve]",
                "cli": "autohs [on|off|ngoc|ve]",
                "desc": "Tự động hồi sinh (ngọc tại chỗ hoặc về thành)",
            },
            {
                "tg": "/anhat",
                "cli": "anhat",
                "desc": "Bật / tắt tự động nhặt vật phẩm rơi",
            },
            {
                "tg": "/cnn",
                "cli": "cnn",
                "desc": "Bật / tắt chế độ chỉ nhặt ngọc",
            },
            {
                "tg": "/nsq",
                "cli": "nsq",
                "desc": "Bật / tắt né siêu quái bảo vệ acc",
            },
            {
                "tg": "/abf [hp%]",
                "cli": "abf [hp%]",
                "desc": "Tự dùng đậu khi HP/KI dưới ngưỡng",
            },
        ],
    },
    {
        "category": "VẬT PHẨM & NHÂN VẬT",
        "commands": [
            {
                "tg": "/info",
                "cli": "info / thongtin",
                "desc": "Xem thông tin chi tiết nhân vật",
            },
            {
                "tg": "/bag",
                "cli": "bag",
                "desc": "Xem hành trang balo",
            },
            {
                "tg": "/box",
                "cli": "box",
                "desc": "Xem rương đồ",
            },
            {
                "tg": "/combat",
                "cli": "combat / chiendau",
                "desc": "Xem thống kê và chỉ số chiến đấu",
            },
            {
                "tg": "/tree",
                "cli": "harvest / dau",
                "desc": "Xem cây đậu và thu hoạch đậu thần",
            },
            {
                "tg": "/item <id|tên>",
                "cli": "item <id|ten> [all]",
                "desc": "Kiểm tra / tìm kiếm vật phẩm trong túi và rương",
            },
        ],
    },
    {
        "category": "ĐỆ TỬ & NHIỆM VỤ",
        "commands": [
            {
                "tg": "/pet",
                "cli": "pet",
                "desc": "Xem thông tin chi tiết đệ tử",
            },
            {
                "tg": "/pet <0-5|lệnh>",
                "cli": "pet <0-5|action>",
                "desc": "Ra lệnh đệ tử (theo sau, bảo vệ, đánh, về...)",
            },
            {
                "tg": "/trainpet [mode]",
                "cli": "trainpet [normal|avoid|off]",
                "desc": "Tự động luyện đệ tử (normal/avoid)",
            },
            {
                "tg": "/trainacc [on|off]",
                "cli": "trainacc [on|off]",
                "desc": "Tự động chuỗi nhiệm vụ tân thủ 0-11",
            },
            {
                "tg": "/nvbm [on|off]",
                "cli": "auto nvbm [on|off]",
                "desc": "Tự động làm nhiệm vụ Bò Mộng",
            },
        ],
    },
    {
        "category": "HỆ THỐNG",
        "commands": [
            {
                "tg": "/reconnect [chế độ]",
                "cli": "reconnect [on|off|delay|now]",
                "desc": "Cấu hình tự động kết nối lại khi mất mạng",
            },
            {
                "tg": "/quiet",
                "cli": "quiet / log off / log on",
                "desc": "Điều khiển nhật ký nền",
            },
            {
                "tg": "/cls",
                "cli": "cls / clear",
                "desc": "Xóa màn hình Console",
            },
            {
                "tg": "/help",
                "cli": "help / ?",
                "desc": "Xem bảng hướng dẫn lệnh",
            },
            {
                "tg": "/exit",
                "cli": "exit / quit",
                "desc": "Đăng xuất và thoát",
            },
        ],
    },
]


def print_cli_help():
    """Hiển thị trợ giúp dòng lệnh theo nhóm từ COMMAND_HELP_GROUPS (không dùng emoji/icon)."""
    _print_title("TRỢ GIÚP DÒNG LỆNH - CLIENT NRO PY", 78)

    for idx, g in enumerate(COMMAND_HELP_GROUPS):
        cat_name = g["category"]
        if idx == 0:
            print(cat_name)
        else:
            _print_section(cat_name)

        for cmd in g["commands"]:
            print(f"  {cmd['cli']}")
            print(f"      {cmd['desc']}")

    print("=" * 78)


def get_telegram_help_text(selected_scope_text: str = "Tất cả tài khoản") -> str:
    """
    Tạo nội dung hướng dẫn sử dụng dạng lưới có cấu trúc hoàn chỉnh cho Telegram Bot.
    Sử dụng chung nguồn dữ liệu COMMAND_HELP_GROUPS để đồng bộ với CLI.
    Không sử dụng emoji hay icon theo đúng quy chuẩn.
    """
    lines = [
        "= HƯỚNG DẪN SỬ DỤNG LỆNH & ĐIỀU KHIỂN =",
        f"Phạm vi hiện tại: *{selected_scope_text}*",
        "",
        "*1. Thao tác nhanh bằng nút bấm:*",
        "- *Tài khoản*: Chọn 1 tài khoản cụ thể hoặc Tất cả tài khoản",
        "- *Thông tin*: Xem chỉ số, Balo, Rương, Đệ tử, Bản đồ, Combat",
        "- *Điều khiển*: Bật/tắt Tàn sát, Hồi sinh, Đậu thần, Nhặt đồ...",
        "- *Săn Boss*: Theo dõi Boss sống, Bật/tắt săn Boss, Whitelist",
        "- *Trợ lý AI*: Nhập yêu cầu bằng tiếng Việt tự nhiên",
        "",
        "*2. Bảng lệnh tra cứu chi tiết (Dạng lưới):*",
        "=============================",
    ]

    for g in COMMAND_HELP_GROUPS:
        lines.append(f"[{g['category']}]")
        for cmd in g["commands"]:
            lines.append(f"- `{cmd['tg']}` : {cmd['desc']}")
        lines.append("")

    lines.append("=============================")
    lines.append("*3. Trợ lý AI (Tiếng Việt tự nhiên):*")
    lines.append("Bạn có thể gõ yêu cầu tự do, ví dụ:")
    lines.append("- Cho tài khoản 1 tới map 112 khu vắng và bật tàn sát")
    lines.append("- Tất cả tài khoản tản ra khu min và săn boss")
    lines.append("- Kiểm tra đệ tử của tài khoản 2")

    return "\n".join(lines)