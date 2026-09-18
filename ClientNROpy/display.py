# -*- coding: utf-8 -*-
"""
Module định dạng và hiển thị thông tin giao diện Console (display.py).
Bao gồm các bảng thông tin trực quan:
- Bảng tổng hợp trạng thái đa tài khoản (print_accounts_table)
- Thông tin nhân vật, hành trang balo, rương, trang bị
- Đệ tử, cây đậu thần, bản đồ, danh sách khu
- Lịch sử Boss, bảng trạng thái Auto Săn Boss, NV Bò Mộng, Shuttle
- Trợ giúp dòng lệnh (print_cli_help)
"""

from typing import Optional, List, Any
from .char import Char
from .item import Item
from .pet import Pet
from .magic_tree import MagicTree
from .map_info import MapInfo
from .client import ClientNRO
from .game_data import format_big_number, get_item_name, SKILL_NAMES


def print_banner():
    print("=" * 78)
    print("      DRAGONBOY / NGOC RONG ONLINE - CLIENT SIMULATOR ĐA TÀI KHOẢN     ")
    print("=" * 78)


def print_accounts_table(account_manager) -> None:
    """In bảng tổng hợp trạng thái của tất cả các tài khoản đang quản lý."""
    accs = account_manager.accounts
    use_proxy = account_manager.proxy_pool.use_proxy
    proxy_count = len(account_manager.proxy_pool.proxies)
    rec_info = f"BẬT ({int(account_manager.reconnect_delay)}s)" if account_manager.auto_reconnect else "TẮT"

    print("\n" + "=" * 94)
    proxy_info = f"BẬT ({proxy_count} proxy, {account_manager.proxy_pool.accounts_per_proxy} acc/proxy)" if use_proxy else "TẮT (Trực tiếp)"
    print(f"       BẢNG THEO DÕI ĐA TÀI KHOẢN ({len(accs)} ACC) | PROXY: {proxy_info} | RECONNECT: {rec_info}")
    print("=" * 94)

    if not accs:
        print("  (Chưa có tài khoản nào được nạp. Hãy kiểm tra file accounts.json hoặc dùng 'acc add')")
        print("=" * 94 + "\n")
        return

    header = f"{'ID':<4} | {'Tài Khoản':<12} | {'Tên NV':<14} | {'HP':<15} | {'Map (Khu)':<15} | {'Trạng Thái':<12} | {'Auto':<8}"
    print(header)
    print("-" * 94)

    import time
    for a in accs:
        acc_id = f"#{a.config.acc_id}"
        u = a.config.username[:12]
        cname = a.char_name[:14]
        hp = a.hp_str[:15]
        mz = a.map_zone_str[:15]
        st = a.status[:10]
        auto = a.auto_status_str[:8]

        # Đánh dấu trạng thái online / reconnecting
        if a.status == "RECONNECTING":
            rem = max(0, int(a.reconnect_timer_end - time.time()))
            st_marker = f"[~] Nối({rem}s)" if rem > 0 else "[~] Nối lại"
        elif not a.client or not a.client.isConnected():
            if a.status == "CONNECTING":
                st_marker = "[*] Đang vào"
            elif a.status == "ERROR":
                st_marker = "[!] Lỗi"
            else:
                st_marker = "[-] Offline"
        elif a.status == "ONLINE":
            st_marker = "[+] Online"
        elif a.status == "CONNECTING":
            st_marker = "[*] Đang vào"
        elif a.status == "ERROR":
            st_marker = "[!] Lỗi"
        else:
            st_marker = "[-] Offline"

        row = f"{acc_id:<4} | {u:<12} | {cname:<14} | {hp:<15} | {mz:<15} | {st_marker:<12} | {auto:<8}"
        print(row)

    print("=" * 90)
    print("  * Gợi ý: Gõ 'all <lệnh>' (vd: all hunt on) để điều khiển toàn bộ tài khoản.")
    print("           Gõ 'use <id>' (vd: use 1) để chọn và điều khiển riêng 1 tài khoản.\n")


def print_character_overview(char: Char):
    print("\n" + "=" * 55)
    print(f"THÔNG TIN NHÂN VẬT: {char.cName} (ID: {char.charID})")
    print("=" * 55)
    print(f"- Sức mạnh:      {char.cPower:,} ({format_big_number(char.cPower)})")
    print(f"- Tiềm năng:     {char.cTiemNang:,} ({format_big_number(char.cTiemNang)})")
    print(f"- HP:            {char.cHP:,} / {char.cHPFull:,}")
    print(f"- KI / MP:       {char.cMP:,} / {char.cMPFull:,}")
    print(f"- Vàng (Xu):     {char.xu:,} ({format_big_number(char.xu)} Xu)")
    ngoc_str = f" ({format_big_number(char.luong)} Ngọc)" if char.luong >= 1000 else ""
    khoa_str = f" ({format_big_number(char.luongKhoa)} Khóa)" if char.luongKhoa >= 1000 else ""
    print(f"- Ngọc:          {char.luong:,}{ngoc_str} | Hồng ngọc: {char.luongKhoa:,}{khoa_str}")
    print(f"- Hệ phái/Lớp:   {char.nClass}")
    print(f"- Tọa độ:        ({char.cx}, {char.cy})")


def print_inventory(char: Char):
    print("\n" + "-" * 55)
    print(f"1. HÀNH TRANG BALO ({len(char.arrItemBag)} món)")
    print("-" * 55)
    if not char.arrItemBag:
        print("  (Balo trống)")
    for i, it in enumerate(char.arrItemBag):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        it_name = get_item_name(it.template_id, it.info or "")
        print(f"  [{i+1:02d}] {it_name} (ID: {it.template_id}) x{it.quantity:<4}{opt_str}")

    print("\n" + "-" * 55)
    print(f"2. RƯƠNG ĐỒ ({len(char.arrItemBox)} món)")
    print("-" * 55)
    if not char.arrItemBox:
        print("  (Rương trống)")
    for i, it in enumerate(char.arrItemBox):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        it_name = get_item_name(it.template_id, it.info or "")
        print(f"  [{i+1:02d}] {it_name} (ID: {it.template_id}) x{it.quantity:<4}{opt_str}")

    print("\n" + "-" * 55)
    print(f"3. TRANG BỊ TRÊN NGƯỜI ({len(char.arrItemBody)} món)")
    print("-" * 55)
    if not char.arrItemBody:
        print("  (Chưa mặc trang bị)")
    for i, it in enumerate(char.arrItemBody):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        it_name = get_item_name(it.template_id, it.info or "")
        print(f"  [{i+1:02d}] {it_name} (ID: {it.template_id}){opt_str}")


def print_pet_info(pet: Pet):
    print("\n" + "-" * 55)
    print("4. THÔNG TIN ĐỆ TỬ / PET")
    print("-" * 55)
    if not pet.havePet:
        print("  -> Nhân vật chưa có đệ tử.")
        return

    print(f"- Tên đệ tử:     {pet.cName}")
    print(f"- Trạng thái:    {pet.statusName}")
    print(f"- HP:            {pet.cHP:,} / {pet.cHPFull:,}")
    print(f"- KI / MP:       {pet.cMP:,} / {pet.cMPFull:,}")
    print(f"- Sức đánh:      {pet.cDamFull:,}")
    print(f"- Giáp:          {pet.cDefull:,}")
    print(f"- Chí mạng:      {pet.cCriticalFull}%")
    print(f"- Sức mạnh:      {pet.cPower:,} ({format_big_number(pet.cPower)})")
    print(f"- Tiềm năng:     {pet.cTiemNang:,} ({format_big_number(pet.cTiemNang)})")
    print(f"- Thể lực:       {pet.cStamina} / {pet.cMaxStamina}")
    print(f"- Kỹ năng đệ:    {pet.arrPetSkill}")
    print(f"- Trang bị đệ:   {len(pet.arrItemBody)} món")
    for i, it in enumerate(pet.arrItemBody):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        print(f"    [{i+1}] Item ID: {it.template_id}{opt_str}")


def print_magic_tree(tree: MagicTree):
    print("\n" + "-" * 55)
    print("5. CÂY ĐẬU THẦN (MAGIC TREE)")
    print("-" * 55)
    print(f"- Tên cây đậu:   {tree.name}")
    print(f"- Cấp độ:        Cấp {tree.level}")
    print(f"- Số hạt:        {tree.currPeas} / {tree.maxPeas} hạt")
    print(f"- Thời gian:     {tree.seconds} giây còn lại")
    if tree.strInfo:
        print(f"- Trạng thái:    {tree.strInfo}")


def print_map_and_zones(map_info: MapInfo):
    print("\n" + "-" * 55)
    print(f"THÔNG TIN MAP: {map_info.mapName} (ID: {map_info.mapID}, Hành tinh: {map_info.planetID})")
    print(f"Khu vực hiện tại: Khu {map_info.zoneID}")
    print("-" * 55)

    if map_info.zones:
        print(f"\n* TỔNG SỐ KHU VỰC: {len(map_info.zones)} khu")
        for z in map_info.zones:
            curr_marker = " <== [BẠN ĐANG Ở ĐÂY]" if z.zoneId == map_info.zoneID else ""
            print(f"  - Khu {z.zoneId:02d}: {z.numPlayer:02d}/{z.maxPlayer:02d} người ({z.status}){curr_marker}")
    else:
        print("  (Đang cập nhật danh sách khu vực...)")

    print(f"\n* NGƯỜI CHƠI TRONG KHU VỰC ({len(map_info.chars)} người):")
    if not map_info.chars:
        print("  (Không có người chơi khác)")
    for pid, c in map_info.chars.items():
        print(f"  - [{c.cName}] (ID: {pid}) | HP: {c.cHP:,}/{c.cHPFull:,} | Tọa độ: ({c.cx}, {c.cy})")

    print(f"\n* QUÁI VẬT TRONG KHU VỰC ({len(map_info.mobs)} con):")
    for mid, m in list(map_info.mobs.items())[:5]:
        boss_str = " [BOSS]" if m.isBoss else ""
        print(f"  - Quái #{mid}: Type {m.templateId}{boss_str} | HP: {m.hp:,}/{m.maxHp:,} | Tọa độ: ({m.x}, {m.y})")
    if len(map_info.mobs) > 5:
        print(f"    ... và {len(map_info.mobs) - 5} quái khác.")

    if map_info.items:
        print(f"\n* VẬT PHẨM DƯỚI ĐẤT ({len(map_info.items)} món):")
        for item_id, it in map_info.items.items():
            print(f"  - ItemMap #{item_id} (Template {it.itemTemplateID}) tại ({it.x}, {it.y})")

    if map_info.waypoints:
        print(f"\n* CỔNG DỊCH CHUYỂN ({len(map_info.waypoints)} cổng):")
        for wp in map_info.waypoints:
            print(f"  - {wp.name}: ({wp.minX},{wp.minY}) -> ({wp.maxX},{wp.maxY})")


def print_boss_list(client: ClientNRO, filter_mode: str = "all"):
    all_bosses = client.get_bosses()
    alive_count = sum(1 for b in all_bosses if not b.is_died)
    dead_count = sum(1 for b in all_bosses if b.is_died)

    if filter_mode == "alive":
        display_bosses = [b for b in all_bosses if not b.is_died]
        title = "DANH SÁCH BOSS ĐANG CÒN SỐNG"
    elif filter_mode == "dead":
        display_bosses = [b for b in all_bosses if b.is_died]
        title = "DANH SÁCH BOSS ĐÃ BỊ TIÊU DIỆT"
    else:
        display_bosses = all_bosses
        title = "BẢNG THEO DÕI TOÀN BỘ BOSS"

    print("\n" + "=" * 70)
    print(f"             {title} ({len(display_bosses)} Boss)")
    print(f"         [[=] CÒN SỐNG: {alive_count}  |  [ ] ĐÃ CHẾT: {dead_count}]")
    print("=" * 70)

    if not display_bosses:
        print("  (Chưa có Boss nào thỏa điều kiện)")
        print("=" * 70 + "\n")
        return

    curr_map_id = getattr(client.myChar.mapInfo, "mapID", -1) if (client.myChar and client.myChar.mapInfo) else -1
    curr_zone_id = getattr(client.myChar.mapInfo, "zoneID", -1) if (client.myChar and client.myChar.mapInfo) else -1

    for b in display_bosses:
        try:
            stt = all_bosses.index(b) + 1
        except ValueError:
            stt = 0
        boss_str = b.to_string(use_color=True, current_map_id=curr_map_id, current_zone_id=curr_zone_id)
        print(f"  [{stt:02d}] {boss_str}")
    print("=" * 70 + "\n")


def print_hunt_status(client: ClientNRO):
    st = client.get_hunt_status()
    print("\n" + "=" * 65)
    print("        BẢNG TRẠNG THÁI AUTO SĂN BOSS (AUTONOMOUS HUNTER)       ")
    print("=" * 65)
    print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if st['is_enabled'] else 'ĐÃ TẮT [OFF]'}")
    print(f"- Máy trạng thái (FSM):  {st['state']}")
    print(f"- Tin nhắn trạng thái:   {st['status_message']}")
    print(f"- Chế độ săn:            {'Săn TẤT CẢ các Boss' if st['hunt_all'] else 'Chỉ săn Boss theo Whitelist'}")
    targets_str = ", ".join(st['target_bosses']) if st['target_bosses'] else "(Trống - Săn tất cả)"
    print(f"- Danh sách Whitelist:   {targets_str}")
    combo_sids = st.get('combo_skills', [])
    combo_str = " -> ".join([f"{s} ({SKILL_NAMES.get(s, 'Chiêu')})" for s in combo_sids]) if combo_sids else "Mặc định theo hành tinh"
    print(f"- Combo 3 Skill Pem:     {combo_str}")
    coop_scanners = st.get('cooperative_scanners', 0)
    print(f"- Phối hợp đa tài khoản: {coop_scanners} acc đang cùng chia việc quét map")
    print(f"- Boss đã tiêu diệt:     {st.get('boss_kill_count', 0)} Boss")
    print(f"- Đồ đã nhặt từ Boss:    {st.get('boss_looted_items_count', 0)} vật phẩm")
    looted_hist = st.get('boss_looted_items_history', [])
    if looted_hist:
        print("-" * 65)
        print("  [CHIẾN LỢI PHẨM NHẶT TỪ BOSS GẦN ĐÂY]")
        for item in looted_hist[-5:]:
            print(f"  [+] {item.get('time', '')}: {item.get('item_name', '')} (Boss: {item.get('boss_name', '')} | {item.get('map_name', '')})")
    print("-" * 65)
    print(f"- Tự nhặt đồ khi xong:   {'BẬT' if st['auto_loot'] else 'TẮT'}")
    print(f"- Tự hồi sinh:           {'BẬT' if st['auto_revive'] else 'TẮT'}")
    print(f"- Tự động tuần tra:      {'BẬT' if st.get('auto_patrol', True) else 'TẮT'}")
    if st['current_boss']:
        b = st['current_boss']
        z_str = f"Khu {b.get('zone_id')}" if b.get('zone_id', -1) >= 0 else "Chưa rõ khu"
        print(f"- Boss đang theo dấu:    {b.get('name')} | Map: {b.get('map_name')} ({b.get('map_id')}) | {z_str}")
    print("=" * 65 + "\n")


def print_quest_status(client: ClientNRO):
    st = client.get_quest_status()
    print("\n" + "=" * 65)
    print("        BẢNG TRẠNG THÁI AUTO NHIỆM VỤ BÒ MỘNG (NVBM)        ")
    print("=" * 65)
    print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if st['is_running'] else 'ĐÃ TẮT [OFF]'}")
    print(f"- Giai đoạn (state):     {st['state']}")
    print(f"- Nhiệm vụ hiện tại:     {st['quest']}")
    print(f"- Đã trả NV:             {st['quests_completed']} NV")
    print(f"- Tổng quái đã diệt:     {st['total_kills']} con")
    print(f"- Thời gian chạy:        {st['time_str']}")
    print("=" * 65 + "\n")


def print_shuttle_status(client: ClientNRO):
    st = client.get_shuttle_status()
    print("\n" + "=" * 65)
    print("        BẢNG TRẠNG THÁI SHUTTLE QUA LẠI 2 MAP        ")
    print("=" * 65)
    print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if st['is_running'] else 'ĐÃ TẮT [OFF]'}")
    print(f"- Tuyến:                 {st['map_a']} <-> {st['map_b']}")
    print(f"- Đã đi:                 {st['legs_done']} lượt")
    print(f"- Trạng thái:            {st['status_message']}")
    print("=" * 65 + "\n")


def print_cli_help():
    print("\n" + "=" * 76)
    print("             HƯỚNG DẪN DÒNG LỆNH (CLI) - CLIENT NRO PY              ")
    print("=" * 76)
    print("  [ĐIỀU KHIỂN ĐA TÀI KHOẢN (MULTI-ACCOUNT)]")
    print("  status / stt / ls           : Xem bảng tổng hợp trạng thái các tài khoản")
    print("  use <id|all>                : Chuyển ngữ cảnh sang tài khoản chỉ định hoặc tất cả")
    print("  all <lệnh>                  : Thực thi lệnh trên TOÀN BỘ tài khoản (vd: all hunt on)")
    print("  acc <id> <lệnh>             : Thực thi lệnh trên 1 tài khoản (vd: acc 1 xmap 0)")
    print("  login / connect [id|all]    : Đăng nhập kết nối tài khoản vào game")
    print("  logout / dis [id|all]       : Đăng xuất an toàn (dừng auto-reconnect)")
    print("-" * 76)
    print("  [TRA CỨU VẬT PHẨM & TÀI SẢN]")
    print("  item <id|tên> [all]         : Kiểm tra vật phẩm trong balo (vd: item 14, item đậu)")
    print("  info / thongtin             : Xem chi tiết toàn diện thông tin bản thân & đệ tử")
    print("  bag / box                   : Xem toàn bộ vật phẩm trong Balo / Rương đồ")
    print("  harvest / dau               : Thu hoạch đậu thần từ Cây Đậu Thần")
    print("-" * 76)
    print("  [AUTO SĂN BOSS & CHIẾN ĐẤU]")
    print("  hunt on / off / status      : Bật / Tắt / Xem tiến độ Auto Săn Boss & Tuần Tra")
    print("  boss / boss alive / boss go : Xem Boss đang xuất hiện / Bay tới vị trí Boss")
    print("  ak [on|off]                 : Tự động đánh mục tiêu focus")
    print("  ts / tansat [on|off|mob|pk] : Bật / Tắt tàn sát quái hoặc người chơi (Auto PK)")
    print("  anhat                       : Bật / Tắt tự động nhặt đồ")
    print("  cnn                         : Chỉ nhặt ngọc")
    print("  nsq                         : Né siêu quái")
    print("  abf [hp%]                   : Tự dùng đậu khi HP/KI xuống dưới ngưỡng (vd: abf 50)")
    print("  autohs [on|off|ngoc|ve]     : Bật / Tắt tự hồi sinh (Mặc định: BẬT bằng ngọc)")
    print("-" * 76)
    print("  [ĐỆ TỬ & LUYỆN TẬP TỰ ĐỘNG]")
    print("  pet <0-5|action>            : Đổi trạng thái đệ: follow, protect, attack, home, fuse, porata")
    print("  trainpet [normal|avoid|off] : Auto Úp đệ tử thông minh (Normal, Né siêu quái, Kaioken)")
    print("  trainacc [on|off]           : Auto làm chuỗi nhiệm vụ tân thủ sơ sinh (NV 0 -> 11)")
    print("-" * 76)
    print("  [TÌM ĐƯỜNG XMAP & KHU VỰC]")
    print("  xmap <id|tên>               : Tự động di chuyển tới bản đồ chỉ định")
    print("  xmap stop                   : Dừng di chuyển Xmap")
    print("  goto <map> [min|khu] [ts|..]: Macro: xmap -> đổi khu -> bật auto (vd: goto 112 min ts)")
    print("  zone [khu|min]              : Xem danh sách khu hoặc đổi khu (vd: zone min là khu vắng nhất)")
    print("  map                         : Xem chi tiết bản đồ, quái, NPC và người trong khu")
    print("-" * 76)
    print("  [TỰ ĐỘNG KẾT NỐI & HỆ THỐNG]")
    print("  reconnect [on|off|delay|now]: Cấu hình và kết nối lại ngay lập tức")
    print("  quiet / log off / log on    : Chế độ yên tĩnh (Tắt/Bật log nền trôi để gõ lệnh không bị nhảy)")
    print("  cls / clear                 : Xóa sạch màn hình console")
    print("  telegram / tg               : Xem trạng thái kết nối Telegram Bot")
    print("  exit / quit                 : Đăng xuất và thoát chương trình")
    print("=" * 76 + "\n")
