#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Điểm chạy chính của Client NRO Headless Simulator (main.py).
Mô phỏng đầy đủ mạng game Ngọc Rồng Online (Dragonboy) không cần đồ hoạ.

Hỗ trợ lấy đầy đủ:
1. Hành trang balo (arrItemBag: item, số lượng, chỉ số options).
2. Rương đồ (arrItemBox).
3. Trang bị trên người (arrItemBody).
4. Thông tin Đệ tử / Pet (chỉ số, HP, KI, sức đánh, trạng thái, chiêu thức, trang bị đệ).
5. Cây đậu thần (cấp độ, số hạt hiện tại, số hạt tối đa, thời gian chín).
6. Thông tin Map: tên bản đồ, ID, hành tinh, tọa độ.
7. Danh sách Khu vực: số khu, số người hiện tại, số người tối đa, trạng thái từng khu.
8. Các nhân vật khác đang có mặt trong khu vực.
9. Quái vật và vật phẩm rơi trên mặt đất.
"""

import sys
import os
import time
import threading

# Đảm bảo console Windows hỗ trợ in Unicode tiếng Việt
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Thêm thư mục gốc vào PYTHONPATH nếu cần
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ClientNROpy import (
    ClientNRO,
    Char,
    Item,
    ZoneInfo,
    MapInfo,
    Pet,
    MagicTree,
    ChatVip,
    get_map_name,
    resolve_map_id,
    GroupMap,
    MapNext,
)
from ClientNROpy.xmap import GROUP_MAPS_DEF


def print_banner():
    print("=" * 75)
    print("   DRAGONBOY / NGOC RONG ONLINE - HEADLESS CLIENT SIMULATOR (PYTHON)   ")
    print("=" * 75)


def print_character_overview(char: Char):
    print("\n" + "=" * 50)
    print(f"THÔNG TIN NHÂN VẬT CHÍNH: {char.cName} (ID: {char.charID})")
    print("=" * 50)
    print(f"- Sức mạnh:      {char.cPower:,}")
    print(f"- Tiềm năng:     {char.cTiemNang:,}")
    print(f"- Vàng (Xu):     {char.xu:,}")
    print(f"- Ngọc (Lượng):  {char.luong:,} (Khóa: {char.luongKhoa:,})")
    print(f"- Hệ phái/Lớp:   {char.nClass}")
    print(f"- Tọa độ:        ({char.cx}, {char.cy})")


def print_inventory(char: Char):
    print("\n" + "-" * 50)
    print(f"1. HÀNH TRANG BALO ({len(char.arrItemBag)} món)")
    print("-" * 50)
    if not char.arrItemBag:
        print("  (Balo trống)")
    for i, it in enumerate(char.arrItemBag):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        info_str = f" - {it.info}" if it.info else ""
        print(f"  [{i+1:02d}] Item ID: {it.template_id:<5} x{it.quantity:<4}{opt_str}{info_str}")

    print("\n" + "-" * 50)
    print(f"2. RƯƠNG ĐỒ ({len(char.arrItemBox)} món)")
    print("-" * 50)
    if not char.arrItemBox:
        print("  (Rương trống)")
    for i, it in enumerate(char.arrItemBox):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        info_str = f" - {it.info}" if it.info else ""
        print(f"  [{i+1:02d}] Item ID: {it.template_id:<5} x{it.quantity:<4}{opt_str}{info_str}")

    print("\n" + "-" * 50)
    print(f"3. TRANG BỊ TRÊN NGƯỜI ({len(char.arrItemBody)} món)")
    print("-" * 50)
    if not char.arrItemBody:
        print("  (Chưa mặc trang bị)")
    for i, it in enumerate(char.arrItemBody):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        print(f"  [{i+1:02d}] Item ID: {it.template_id:<5}{opt_str}")


def print_pet_info(pet: Pet):
    print("\n" + "-" * 50)
    print("4. THÔNG TIN ĐỆ TỬ / PET")
    print("-" * 50)
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
    print(f"- Sức mạnh:      {pet.cPower:,}")
    print(f"- Tiềm năng:     {pet.cTiemNang:,}")
    print(f"- Thể lực:       {pet.cStamina} / {pet.cMaxStamina}")
    print(f"- Kỹ năng đệ:    {pet.arrPetSkill}")
    print(f"- Trang bị đệ:   {len(pet.arrItemBody)} món")
    for i, it in enumerate(pet.arrItemBody):
        opts = " | ".join([opt.getText() for opt in it.options])
        opt_str = f" [{opts}]" if opts else ""
        print(f"    [{i+1}] Item ID: {it.template_id}{opt_str}")


def print_magic_tree(tree: MagicTree):
    print("\n" + "-" * 50)
    print("5. CÂY ĐẬU THẦN (MAGIC TREE)")
    print("-" * 50)
    print(f"- Tên cây đậu:   {tree.name}")
    print(f"- Cấp độ:        Cấp {tree.level}")
    print(f"- Số hạt:        {tree.currPeas} / {tree.maxPeas} hạt")
    print(f"- Thời gian:     {tree.seconds} giây còn lại")
    if tree.strInfo:
        print(f"- Trạng thái:    {tree.strInfo}")


def print_map_and_zones(map_info: MapInfo):
    print("\n" + "-" * 50)
    print(f"6. THÔNG TIN MAP: {map_info.mapName} (ID: {map_info.mapID}, Hành tinh: {map_info.planetID})")
    print(f"   Khu vực hiện tại: Khu {map_info.zoneID}")
    print("-" * 50)

    # Danh sách các khu trong map
    if map_info.zones:
        print(f"\n* TỔNG SỐ KHU VỰC: {len(map_info.zones)} khu")
        for z in map_info.zones:
            curr_marker = " <== [BẠN ĐANG Ở ĐÂY]" if z.zoneId == map_info.zoneID else ""
            print(f"  - Khu {z.zoneId:02d}: {z.numPlayer:02d}/{z.maxPlayer:02d} người ({z.status}){curr_marker}")
    else:
        print("  (Đang cập nhật danh sách khu vực...)")

    # Người chơi trong map
    print(f"\n* NGƯỜI CHƠI TRONG KHU VỰC ({len(map_info.chars)} người):")
    if not map_info.chars:
        print("  (Không có người chơi khác)")
    for pid, c in map_info.chars.items():
        print(f"  - [{c.cName}] (ID: {pid}) | HP: {c.cHP:,}/{c.cHPFull:,} | Tọa độ: ({c.cx}, {c.cy})")

    # Quái trong map
    print(f"\n* QUÁI VẬT TRONG KHU VỰC ({len(map_info.mobs)} con):")
    for mid, m in list(map_info.mobs.items())[:5]:
        boss_str = " [BOSS]" if m.isBoss else ""
        print(f"  - Quái #{mid}: Type {m.templateId}{boss_str} | HP: {m.hp:,}/{m.maxHp:,} | Tọa độ: ({m.x}, {m.y})")
    if len(map_info.mobs) > 5:
        print(f"    ... và {len(map_info.mobs) - 5} quái khác.")

    # Vật phẩm dưới đất
    if map_info.items:
        print(f"\n* VẬT PHẨM DƯỚI ĐẤT ({len(map_info.items)} món):")
        for item_id, it in map_info.items.items():
            print(f"  - ItemMap #{item_id} (Template {it.itemTemplateID}) tại ({it.x}, {it.y})")

    # Waypoints
    if map_info.waypoints:
        print(f"\n* CỔNG DỊCH CHUYỂN / WAYPOINTS ({len(map_info.waypoints)} cổng):")
        for wp in map_info.waypoints:
            print(f"  - {wp.name}: ({wp.minX},{wp.minY}) -> ({wp.maxX},{wp.maxY})")


def run_client(host="51.79.163.109", port=12457, username="poopooi01", password="02082003", version="2.1.4"):
    print_banner()
    print(f"[*] Kết nối tới máy chủ: {host}:{port} (phiên bản {version})")
    print(f"[*] Đăng nhập tài khoản: '{username}'")

    client = ClientNRO(host=host, port=port, version=version)
    has_entered_map = threading.Event()
    has_got_zones = threading.Event()

    def on_char_info(char: Char):
        print("\n[+] ĐÃ VÀO THẾ GIỚI GAME THÀNH CÔNG!")
        has_entered_map.set()

    def on_zone_info(zones: list):
        has_got_zones.set()

    client.on_char_info(on_char_info)
    client.on_zone_info(on_zone_info)

    client.on_server_message(lambda text: print(f"[THÔNG BÁO TỪ SERVER] {text}"))

    _last_chat = {}

    def _on_chat_throttled(cid, text):
        # Bỏ qua tin lặp y hệt trong 10s (NPC spam thoại che ô nhập lệnh)
        import time as _t
        key = (cid, text)
        now = _t.monotonic()
        if _last_chat.get(key, 0.0) + 10.0 > now:
            return
        _last_chat[key] = now
        # Dọn entry cũ để dict không phình
        if len(_last_chat) > 50:
            _last_chat.clear()
            _last_chat[key] = now
        print(f"[CHAT MAP {cid}] {text}")

    client.on_chat(_on_chat_throttled)

    def on_vip_msg(cv: ChatVip):
        if cv.is_boss:
            if cv.is_killed:
                print(f"\n[!] >>> [BOSS BỊ HẠ GỤC]: '{cv.boss_name}' đã bị hạ bởi '{cv.killer}'!")
            else:
                z_str = f" khu vực {cv.zone_id}" if cv.zone_id >= 0 else ""
                print(f"\n[!] >>> [BOSS XUẤT HIỆN]: BOSS '{cv.boss_name}' vừa xuất hiện tại {cv.map_name}{z_str}!")
        else:
            print(f"\n[*] >>> [CHAT VIP / THẾ GIỚI]: {cv.text}")

    client.on_chat_vip(on_vip_msg)

    # Bắt đầu kết nối
    client.connect()
    time.sleep(0.2)

    # Đăng nhập
    client.login(username, password, version=version)

    print("[*] Đang chờ đồng bộ dữ liệu từ server...")
    if not has_entered_map.wait(timeout=25.0):
        print("[!] Không nhận được phản hồi nhân vật trong thời gian chờ!")

    time.sleep(2.0)

    # Gửi yêu cầu lấy thêm danh sách khu, thông tin đệ tử và cây đậu
    print("[*] Gửi yêu cầu đồng bộ Danh sách khu, Đệ tử, Cây đậu thần...")
    client.request_zones()
    client.request_pet_info()
    client.request_magic_tree(1)

    time.sleep(2.0)

    # In toàn bộ dữ liệu đã bóc tách
    char = client.get_my_char()
    print_character_overview(char)
    print_inventory(char)
    print_pet_info(char.pet)
    print_magic_tree(char.magicTree)
    print_map_and_zones(char.mapInfo)

    print("\n" + "=" * 75)
    print("   HOÀN TẤT ĐỒNG BỘ VÀ BÓC TÁCH TOÀN BỘ DỮ LIỆU HEADLESS THÀNH CÔNG!   ")
    print("=" * 75)

    return client


def print_cli_help():
    print("\n" + "=" * 65)
    print("           HƯỚNG DẪN DÒNG LỆNH (CLI) - CLIENT NRO PY           ")
    print("=" * 65)
    print("  [CHIẾN ĐẤU & TÀN SÁT - MOD C#]")
    print("  focus [mob|char|item|clear] : Tiêu điểm nhắm mục tiêu (vd: focus mob, focus char Goku)")
    print("  tele [x y|mob|char|item|wp] : Dịch chuyển tức thời tới toạ độ hoặc đối tượng")
    print("  ak [on|off]                 : Tự động đánh mục tiêu đang focus (Auto Attack)")
    print("  ts / tansat [on|off|mob|pk] : Bật/Tắt tàn sát quái hoặc người chơi (Auto PK)")
    print("  ts type <id>                : Chỉ tàn sát 1 loại quái (theo template ID)")
    print("  ts id <id>                  : Chỉ tàn sát 1 quái ID cụ thể")
    print("  ts clear                    : Xoá bộ lọc quái (tàn sát tất cả quái trong map)")
    print("  nsq                         : Bật / Tắt né siêu quái khi tàn sát")
    print("  anhat                       : Bật / Tắt tự động nhặt vật phẩm rơi trên đất")
    print("  cnn                         : Cài đặt nhanh chỉ nhặt ngọc")
    print("  abf [ngưỡng %]              : Bật / Tắt tự động dùng đậu khi HP/KI thấp (vd: abf 20)")
    print("  combat                      : Xem bảng cấu hình chiến đấu và tàn sát hiện tại")
    print("-" * 65)
    print("  [AUTO SĂN BOSS HOÀN CHỈNH - AUTO HUNT]")
    print("  hunt [on|off]               : Bật / Tắt Auto Săn Boss (Tự tìm, di chuyển, dò khu, đánh)")
    print("  hunt status                 : Xem trạng thái, mục tiêu và tiến độ săn Boss")
    print("  hunt delay <min> [max]      : Cài đặt thời gian ngẫu nhiên đổi khu (vd: hunt delay 0.5 0.7)")
    print("  hunt add <tên>              : Thêm Boss vào danh sách săn (Whitelist)")
    print("  hunt del <tên>              : Xóa Boss khỏi danh sách săn")
    print("  hunt list                   : Xem danh sách Boss trong Whitelist")
    print("  hunt all                    : Bật / Tắt săn tất cả Boss (không theo whitelist)")
    print("  hunt loot                   : Bật / Tắt tự động nhặt đồ khi Boss chết")
    print("  hunt revive                 : Bật / Tắt tự hồi sinh và quay lại map Boss")
    print("  hunt clear                  : Xóa toàn bộ Whitelist (quay về săn tất cả)")
    print("-" * 65)
    print("  captest                     : Test xài capsule ĐB (194), in panel map server trả về")
    print("  npcs                        : Liệt kê NPC trong map hiện tại")
    print("  npctest <npc> [chon...]     : Mở menu NPC và in nội dung (vd: npctest 25)")
    print("  [AUTO NHIỆM VỤ BÒ MỘNG HẰNG NGÀY]")
    print("  nvbm [on|off|status]      : Bật / Tắt / Xem auto NV Bò Mộng (farm + trả NV)")
    print("-" * 65)
    print("  [QUẢN LÝ & SĂN BOSS THỦ CÔNG]")
    print("  boss                        : Xem danh sách Boss đang còn sống (map, khu, thời gian)")
    print("  boss all / history          : Xem toàn bộ lịch sử các Boss (kể cả đã bị hạ gục)")
    print("  boss go <stt|tên>           : Tự động Xmap bay đến map và tự đổi sang khu của Boss")
    print("  boss clear                  : Xóa danh sách lịch sử Boss đã lưu")
    print("-" * 65)
    print("  [TỰ ĐỘNG TÌM ĐƯỜNG XMAP]")
    print("  xmap <id|tên>               : Bắt đầu Xmap di chuyển tới map chỉ định")
    print("  xmap stop / cancel          : Dừng tiến trình Xmap hiện tại")
    print("  xmap status                 : Xem trạng thái, tiến độ và cấu hình Capsule")
    print("  xmap csvip                  : Bật / Tắt sử dụng Capsule Đặc Biệt (bay nhanh)")
    print("  xmap cs                     : Bật / Tắt sử dụng Capsule Thường (bay nhanh)")
    print("  xmap speedup                : Bật / Tắt tự tăng tốc tàu thời gian (tốn 1 ngọc, mặc định BẬT)")
    print("  xmap path <from> <to>       : Tra cứu lộ trình tối ưu giữa 2 map (vd: xmap path 0 109)")
    print("  xmap list                   : Xem danh sách các nhóm bản đồ")
    print("  shuttle <A> <B> [vòng]      : Tự đi qua lại giữa 2 map (vd: shuttle 92 27, vòng=0 là vô hạn)")
    print("  shuttle stop / status       : Dừng / xem trạng thái shuttle")
    print("-" * 65)
    print("  [TIỆN ÍCH KHÁC]")
    print("  map                         : Xem thông tin bản đồ hiện tại, tọa độ và waypoints")
    print("  zone [id]                   : Xem danh sách khu hoặc đổi khu (vd: zone 5)")
    print("  chat <nội dung>             : Chat trong bản đồ")
    print("  info                        : In lại thông tin nhân vật")
    print("  help                        : Hiển thị bảng trợ giúp lệnh này")
    print("  exit / quit                 : Đăng xuất và thoát chương trình")
    print("=" * 65 + "\n")


def print_hunt_status(client: ClientNRO):
    """In trực quan bảng trạng thái hệ thống Auto Săn Boss."""
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
    print(f"- Thời gian đổi khu:     {st.get('scan_zone_delay_str', '0.50s - 0.70s')}")
    print(f"- Tự nhặt đồ khi xong:   {'BẬT' if st['auto_loot'] else 'TẮT'}")
    print(f"- Tự hồi sinh quay lại:  {'BẬT' if st['auto_revive'] else 'TẮT'}")
    if st['current_boss']:
        b = st['current_boss']
        z_str = f"Khu {b.get('zone_id')}" if b.get('zone_id', -1) >= 0 else "Chưa rõ khu"
        print(f"- Boss đang theo dấu:    {b.get('name')} | Map: {b.get('map_name')} ({b.get('map_id')}) | {z_str}")
        print(f"                         Xuất hiện lúc: {b.get('appear_time_str')} (Cách đây: {b.get('time_alive_str')})")
    print(f"- Tiến độ dò khu:        Khu {st['current_scan_zone']} (Đã quét {len(st['scanned_zones'])} khu)")
    print("=" * 65 + "\n")



def print_quest_status(client: ClientNRO):
    """In bảng trạng thái Auto NV Bò Mộng."""
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
    if st.get("quests_total"):
        print(f"- NV còn lại hôm nay:    {st['quests_remaining']}/{st['quests_total']}")
    try:
        xc = client.xmap_controller
        print(f"- Capsule ĐB (csdb):        {'BẬT' if xc.is_use_capsule_vip else 'TẮT'} "
              f"(có item 194: {'có' if xc.has_item_capsule_vip() else 'không'})")
        print(f"- Capsule Thường (cs):      {'BẬT' if xc.is_use_capsule_normal else 'TẮT'}")
        if xc.capsule_broken:
            print("- Chú ý: Capsule đang bị TỰ TẮT do kẹt (sẽ đi bộ). Gõ lại xmap/nvbm để thử lại.")
    except Exception:
        pass
    print("=" * 65 + "\n")


def print_shuttle_status(client: ClientNRO):
    """In bảng trạng thái shuttle qua lại 2 map."""
    st = client.get_shuttle_status()
    print("\n" + "=" * 65)
    print("        BẢNG TRẠNG THÁI SHUTTLE QUA LẠI 2 MAP        ")
    print("=" * 65)
    print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if st['is_running'] else 'ĐÃ TẮT [OFF]'}")
    print(f"- Tuyến:                 {st['map_a']} <-> {st['map_b']}")
    print(f"- Đã đi:                 {st['legs_done']} lượt" + (f"/{st['rounds']}" if st['rounds'] else " (vô hạn)"))
    print(f"- Đích hiện tại:         {st['current_target']}")
    print(f"- Trạng thái:            {st['status_message']}")
    print("=" * 65 + "\n")


def print_boss_list(client: ClientNRO, show_all: bool = False):
    bosses = client.get_bosses() if show_all else client.get_alive_bosses()
    title = "TOÀN BỘ LỊCH SỬ BOSS" if show_all else "DANH SÁCH BOSS ĐANG CÒN SỐNG"
    print("\n" + "=" * 65)
    print(f"             {title} ({len(bosses)} Boss)             ")
    print("=" * 65)
    if not bosses:
        if show_all:
            print("  (Chưa có thông báo Boss nào từ server)")
        else:
            print("  (Hiện không có Boss nào còn sống. Gõ 'boss all' để xem lịch sử)")
        print("=" * 65 + "\n")
        return

    curr_map_id = client.myChar.mapInfo.mapID
    curr_zone_id = client.myChar.mapInfo.zoneID

    for i, b in enumerate(bosses):
        boss_str = b.to_string(use_color=True, current_map_id=curr_map_id, current_zone_id=curr_zone_id)
        print(f"  [{i+1:02d}] {boss_str}")
    print("=" * 65)
    print("  * Mẹo: Gõ 'boss go <stt|tên>' để tự động Xmap và đổi khu đến Boss!\n")



def interactive_cli(client: ClientNRO):
    """Vòng lặp nhận và xử lý lệnh từ bàn phím tương tác với game."""
    print_cli_help()
    print("[+] ĐÃ SẴN SÀNG NHẬN LỆNH. Nhập 'help' để xem hướng dẫn hoặc 'exit' để thoát.\n")

    while client.isConnected():
        try:
            line = input("nro> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[*] Ngắt kết nối từ bàn phím...")
            break

        if not line:
            continue

        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("exit", "quit", "q"):
            print("[*] Đang đăng xuất an toàn...")
            client.logout()
            break

        elif cmd == "help":
            print_cli_help()

        elif cmd == "info":
            print_character_overview(client.myChar)
            print_inventory(client.myChar)

        elif cmd == "map":
            print_map_and_zones(client.myChar.mapInfo)

        elif cmd == "zone":
            if args and args[0].isdigit():
                z_id = int(args[0])
                print(f"[*] Yêu cầu chuyển sang Khu {z_id}...")
                client.change_zone(z_id)
            else:
                client.request_zones()
                time.sleep(0.5)
                print(f"\n* DANH SÁCH KHU VỰC ({len(client.myChar.mapInfo.zones)} khu):")
                for z in client.myChar.mapInfo.zones:
                    curr = " <== [HIỆN TẠI]" if z.zoneId == client.myChar.mapInfo.zoneID else ""
                    print(f"  - Khu {z.zoneId:02d}: {z.numPlayer:02d}/{z.maxPlayer:02d} ({z.status}){curr}")

        elif cmd == "chat":
            if args:
                client.chat(" ".join(args))
            else:
                print("Cú pháp: chat <nội dung>")

        elif cmd == "boss":
            if not args or args[0].lower() in ("list", "ls"):
                print_boss_list(client, show_all=False)

            elif args[0].lower() in ("all", "history", "his"):
                print_boss_list(client, show_all=True)

            elif args[0].lower() in ("go", "hunt", "to"):
                if len(args) < 2:
                    print("Cú pháp: boss go <stt|tên> (Ví dụ: boss go 1, boss go Broly)")
                    continue
                target = " ".join(args[1:])
                ok, msg = client.go_to_boss(target)
                print(f"[*] {msg}")

            elif args[0].lower() in ("clear", "reset"):
                client.boss_manager.clear()
                print("[*] Đã xóa toàn bộ lịch sử Boss!")

            # Alias cho Auto Săn Boss (giống lệnh hunt)
            elif args[0].lower() in ("on", "start", "1", "true"):
                client.start_auto_hunt()
                print("[*] Auto Săn Boss: BẬT!")
                
            elif args[0].lower() in ("off", "stop", "0", "false"):
                client.stop_auto_hunt()
                print("[*] Auto Săn Boss: TẮT!")
                
            elif args[0].lower() in ("status", "st", "info"):
                print_hunt_status(client)
                
            elif args[0].lower() in ("target", "add"):
                if len(args) > 1:
                    boss_name = " ".join(args[1:])
                    client.add_hunt_target(boss_name)
                    print(f"[*] Đã thêm '{boss_name}' vào Whitelist săn Boss: {list(client.boss_hunter.target_bosses)}")
                else:
                    print("Cú pháp: boss target <tên boss> (Ví dụ: boss target Broly)")

            else:
                # Nếu gõ trực tiếp STT hoặc tên boss (vd: 'boss 1' hoặc 'boss broly')
                target = " ".join(args)
                ok, msg = client.go_to_boss(target)
                print(f"[*] {msg}")

        elif cmd in ("hunt", "autohunt"):
            if not args:
                is_on = client.toggle_auto_hunt()
                print(f"[*] Auto Săn Boss: {'BẬT' if is_on else 'TẮT'}!")
            else:
                sub = args[0].lower()
                if sub in ("on", "start", "1", "true"):
                    client.start_auto_hunt()
                    print("[*] Auto Săn Boss: BẬT!")
                elif sub in ("off", "stop", "0", "false"):
                    client.stop_auto_hunt()
                    print("[*] Auto Săn Boss: TẮT!")
                elif sub in ("status", "st", "info"):
                    print_hunt_status(client)
                elif sub in ("delay", "wait", "speed", "tg"):
                    if len(args) >= 3:
                        try:
                            min_d = float(args[1])
                            max_d = float(args[2])
                            client.boss_hunter.set_scan_delay(min_d, max_d)
                            print(f"[*] Đã cập nhật thời gian ngẫu nhiên đổi khu: {min_d}s - {max_d}s!")
                        except ValueError:
                            print("Cú pháp: hunt delay <min_giây> <max_giây> (Ví dụ: hunt delay 0.5 0.7)")
                    elif len(args) == 2:
                        try:
                            val = float(args[1])
                            client.boss_hunter.set_scan_delay(val, val)
                            print(f"[*] Đã cập nhật thời gian đổi khu cố định: {val}s!")
                        except ValueError:
                            print("Cú pháp: hunt delay <giây> (Ví dụ: hunt delay 0.5)")
                    else:
                        st = client.get_hunt_status()
                        print(f"[*] Thời gian đổi khu hiện tại: {st.get('scan_zone_delay_str', '0.5s - 0.7s')}")
                elif sub in ("add", "them", "+"):
                    if len(args) > 1:
                        boss_name = " ".join(args[1:])
                        client.add_hunt_target(boss_name)
                        print(f"[*] Đã thêm '{boss_name}' vào Whitelist săn Boss: {list(client.boss_hunter.target_bosses)}")
                    else:
                        print("Cú pháp: hunt add <tên boss> (Ví dụ: hunt add Broly)")
                elif sub in ("del", "remove", "rm", "-"):
                    if len(args) > 1:
                        boss_name = " ".join(args[1:])
                        client.remove_hunt_target(boss_name)
                        print(f"[*] Đã xóa '{boss_name}' khỏi Whitelist săn Boss.")
                    else:
                        print("Cú pháp: hunt del <tên boss>")
                elif sub in ("list", "ls"):
                    targets = client.boss_hunter.get_targets()
                    print(f"[*] Danh sách Boss trong Whitelist ({len(targets)}): {targets if targets else '(Trống - Săn tất cả)'}")
                elif sub in ("clear", "reset"):
                    client.clear_hunt_targets()
                    print("[*] Đã xóa toàn bộ Whitelist (đang săn tất cả các Boss)!")
                elif sub in ("all", "tatca"):
                    client.boss_hunter.set_hunt_all(not client.boss_hunter.hunt_all)
                    print(f"[*] Chế độ săn tất cả Boss (hunt_all): {'BẬT' if client.boss_hunter.hunt_all else 'TẮT (Chỉ săn whitelist)'}!")
                elif sub in ("loot", "nhatdo"):
                    client.boss_hunter.auto_loot = not client.boss_hunter.auto_loot
                    print(f"[*] Tự động nhặt đồ khi Boss chết (auto_loot): {'BẬT' if client.boss_hunter.auto_loot else 'TẮT'}!")
                elif sub in ("revive", "hoisinh"):
                    client.boss_hunter.auto_revive = not client.boss_hunter.auto_revive
                    print(f"[*] Tự hồi sinh và quay lại map Boss (auto_revive): {'BẬT' if client.boss_hunter.auto_revive else 'TẮT'}!")
                else:
                    # Nếu gõ: hunt Broly hoặc tên boss
                    boss_name = " ".join(args)
                    client.add_hunt_target(boss_name)
                    if not client.boss_hunter.is_enabled:
                        client.start_auto_hunt()
                    print(f"[*] Đã thêm '{boss_name}' vào Whitelist và kích hoạt Auto Săn Boss!")

        elif cmd in ("captest", "capsule", "testcap"):
            ctrl = client.controller
            print(f"[*] Panel capsule TRƯỚC test: {len(ctrl.capsule_map_names)} mục")
            print("[*] Bật sniff gói tin 8s + gửi useItem capsule ĐB (194)...")
            ctrl.debug = True
            client.service.useItem(0, 1, -1, 194)
            time.sleep(8.0)
            ctrl.debug = False
            names = list(ctrl.capsule_map_names)
            print(f"[*] Panel capsule SAU test: {len(names)} mục")
            for i, nm in enumerate(names[:40]):
                print(f"    [{i}] {nm}")

        elif cmd in ("npcs", "npc"):
            npcs = client.myChar.mapInfo.npcs
            print(f"[*] NPC trong map '{client.myChar.mapInfo.mapName}' ({len(npcs)}):")
            for n in npcs:
                print(f"    - template {n.get('template_id')} tại ({n.get('x')},{n.get('y')}) "
                      f"avatar={n.get('avatar')} status={n.get('status')}")

        elif cmd in ("npctest", "menutest", "testnpc"):
            if not args:
                print("Cú pháp: npctest <npc_template_id> [select...] (vd: npctest 25)")
            else:
                try:
                    tid = int(args[0])
                except ValueError:
                    print("npc_template_id phải là số.")
                    tid = None
                if tid is not None:
                    captured = {}
                    def _cap(t_id, text, opts):
                        captured["t"] = t_id
                        captured["text"] = text
                        captured["opts"] = list(opts)
                    client.controller.on_npc_menu_callbacks.append(_cap)
                    client.controller.debug = True
                    print(f"[*] Mở menu NPC {tid}...")
                    client.service.openMenu(tid)
                    time.sleep(3.0)
                    for a in args[1:]:
                        try:
                            client.service.confirmMenu(tid, int(a))
                            time.sleep(1.5)
                        except ValueError:
                            pass
                    client.controller.debug = False
                    try:
                        client.controller.on_npc_menu_callbacks.remove(_cap)
                    except ValueError:
                        pass
                    if captured:
                        print(f"[*] Menu NPC {captured['t']}: {captured['text'][:300]}")
                        for i, o in enumerate(captured["opts"]):
                            print(f"    [{i}] {o}")
                    else:
                        print("[*] Server không trả menu (NPC vắng/không nói chuyện được).")

        elif cmd in ("shuttle", "shut", "dual"):
            if not args or (len(args) == 1 and args[0].lower() in ("status", "st", "info")):
                print_shuttle_status(client)
            elif len(args) == 1 and args[0].lower() in ("stop", "off", "0", "false"):
                client.stop_shuttle()
                print("[*] Shuttle: TẮT!")
            elif len(args) >= 2 and args[0].lstrip("-").isdigit() and args[1].lstrip("-").isdigit():
                rounds = 0
                if len(args) >= 3 and args[2].isdigit():
                    rounds = int(args[2])
                ok = client.start_shuttle(int(args[0]), int(args[1]), rounds)
                print(f"[*] Shuttle {args[0]} <-> {args[1]}: {'BẬT!' if ok else 'THẤT BẠI (2 map phải khác nhau)!'}")
            else:
                print("Cú pháp: shuttle <mapA> <mapB> [số_vòng] | shuttle stop | shuttle status")

        elif cmd in ("nvbm", "nhiemvu", "quest", "bomong"):
            # Quét mọi token để chịu được nhập dính chữ khi console bị log nền xen vào
            subs = [a.lower().strip(".,;:!?") for a in args]
            if not subs or any(x in ("status", "st", "info") for x in subs):
                print_quest_status(client)
            elif any(x in ("off", "stop", "0", "false") for x in subs):
                client.stop_auto_quest()
                print("[*] Auto NV Bò Mộng: TẮT!")
            elif any(x in ("on", "start", "1", "true") for x in subs):
                client.start_auto_quest()
                print("[*] Auto NV Bò Mộng: BẬT!")
            else:
                print(f"Không rõ tham số '{args[0]}'. Cú pháp: nvbm [on|off|status]")

        # ----------------------------------------------------------------------
        # CÁC LỆNH CHIẾN ĐẤU & TÀN SÁT (FOCUS, TELE, AK, TÀN SÁT)
        # ----------------------------------------------------------------------
        elif cmd == "focus":
            t_type = args[0] if args else ""
            q = " ".join(args[1:]) if len(args) > 1 else None
            ok, msg = client.focus(t_type, q)
            print(f"[*] {msg}")

        elif cmd in ("tele", "tp"):
            target = " ".join(args) if args else None
            ok, msg = client.teleport_to(target)
            print(f"[*] {msg}")

        elif cmd == "ak":
            enable = None
            if args:
                if args[0].lower() in ("on", "1", "true", "start"):
                    enable = True
                elif args[0].lower() in ("off", "0", "false", "stop"):
                    enable = False
            is_on = client.toggle_ak(enable)
            print(f"[*] Tự động đánh (AK): {'BẬT' if is_on else 'TẮT'}!")

        elif cmd in ("ts", "tansat"):
            if not args:
                is_on = client.toggle_tansat()
                mode_str = "Quái" if client.combat_manager.tansat_mode == "mob" else ("Người chơi (Auto PK)" if client.combat_manager.tansat_mode in ("player", "char") else "Toàn bộ (Quái & Người)")
                print(f"[*] Tàn sát ({mode_str}): {'BẬT' if is_on else 'TẮT'}!")
            else:
                sub = args[0].lower()
                if sub in ("on", "start"):
                    client.toggle_tansat(True)
                    print("[*] Tàn sát: BẬT!")
                elif sub in ("off", "stop"):
                    client.toggle_tansat(False)
                    print("[*] Tàn sát: TẮT!")
                elif sub in ("mob", "quai", "m"):
                    client.toggle_tansat(True, mode="mob")
                    print("[*] Đã bật tàn sát Quái vật!")
                elif sub in ("player", "char", "pk", "nguoi", "p", "c"):
                    client.toggle_tansat(True, mode="player")
                    print("[*] Đã bật tàn sát Người chơi (Auto PK)!")
                elif sub in ("all", "tatca"):
                    client.toggle_tansat(True, mode="all")
                    print("[*] Đã bật tàn sát Toàn bộ (Cả quái và người chơi)!")
                elif sub in ("type", "addtm"):
                    if len(args) > 1 and args[1].isdigit():
                        tid = int(args[1])
                        client.combat_manager.add_mob_type_target(tid)
                        print(f"[*] Đã cập nhật loại quái Template ID {tid} trong danh sách tàn sát: {list(client.combat_manager.target_mob_types)}")
                    else:
                        print("Cú pháp: ts type <template_id> (Ví dụ: ts type 1)")
                elif sub in ("id", "addm", "mobid"):
                    if len(args) > 1 and args[1].isdigit():
                        mid = int(args[1])
                        client.combat_manager.add_mob_target(mid)
                        print(f"[*] Đã cập nhật quái ID {mid} trong danh sách tàn sát: {list(client.combat_manager.target_mob_ids)}")
                    else:
                        print("Cú pháp: ts id <mob_id> (Ví dụ: ts id 3)")
                elif sub in ("clear", "clrm", "reset"):
                    client.combat_manager.clear_mob_targets()
                    print("[*] Đã xoá bộ lọc quái (đang tàn sát toàn bộ quái trong map)!")
                elif sub == "skill":
                    if len(args) > 1 and args[1].isdigit():
                        skill_id = int(args[1])
                        client.combat_manager.tansat_skill_id = skill_id
                        print(f"[*] Đã cấu hình skill tàn sát cố định thành Template ID {skill_id}!")
                    elif len(args) > 1 and args[1].lower() in ("clear", "none", "off"):
                        client.combat_manager.tansat_skill_id = None
                        print("[*] Đã huỷ cấu hình skill tàn sát (sẽ tự lấy skill đang chọn hiện tại).")
                    else:
                        print("Cú pháp: ts skill <id> (VD: ts skill 9) hoặc ts skill clear")
                else:
                    print(f"Không rõ tham số '{sub}'. Cú pháp: ts [on|off|mob|pk|all|type <id>|id <id>|skill <id>|clear]")
        elif cmd == "nsq":
            client.combat_manager.avoid_super_mob = not client.combat_manager.avoid_super_mob
            print(f"[*] Né siêu quái (nsq): {'BẬT' if client.combat_manager.avoid_super_mob else 'TẮT'}!")

        elif cmd == "anhat":
            is_on = client.toggle_auto_pick()
            print(f"[*] Tự động nhặt đồ (anhat): {'BẬT' if is_on else 'TẮT'}!")

        elif cmd == "cnn":
            client.combat_manager.pick_gem_only = not client.combat_manager.pick_gem_only
            client.combat_manager.auto_pick = True
            print(f"[*] Chế độ chỉ nhặt ngọc (cnn): {'BẬT' if client.combat_manager.pick_gem_only else 'TẮT'}!")

        elif cmd == "abf":
            if args and args[0].isdigit():
                val = int(args[0]) / 100.0
                client.combat_manager.pean_threshold = val
                client.combat_manager.auto_pean = True
                print(f"[*] Đã bật tự động dùng đậu khi HP/KI dưới {int(val * 100)}%!")
            else:
                is_on = client.toggle_auto_pean()
                print(f"[*] Tự động dùng đậu (abf): {'BẬT' if is_on else 'TẮT'} (Ngưỡng: {int(client.combat_manager.pean_threshold * 100)}%)!")

        elif cmd == "combat":
            st = client.combat_status()
            print("\n=== CẤU HÌNH CHIẾN ĐẤU & TÀN SÁT ===")
            print(f"- Tự động đánh (AK):     {'BẬT' if st['is_ak'] else 'TẮT'}")
            print(f"- Tàn sát (Slaughter):    {'BẬT' if st['is_tansat'] else 'TẮT'} (Chế độ: {st['tansat_mode']})")
            print(f"- Né siêu quái (nsq):     {'BẬT' if st['avoid_super_mob'] else 'TẮT'}")
            print(f"- Tự nhặt đồ (anhat):     {'BẬT' if st['auto_pick'] else 'TẮT'}")
            print(f"- Chỉ nhặt ngọc (cnn):    {'BẬT' if st['pick_gem_only'] else 'TẮT'}")
            print(f"- Tự dùng đậu (abf):      {'BẬT' if st['auto_pean'] else 'TẮT'}")
            print(f"- Lọc quái ID:            {st['target_mob_ids'] or 'Tất cả'}")
            print(f"- Lọc loại quái:          {st['target_mob_types'] or 'Tất cả'}")
            print(f"- Tiêu điểm Focus:        {st['focus_kind']}: {st['focus_target']}\n")

        elif cmd == "xmap":


            if not args:
                print("Cú pháp: xmap <id|tên|nha|cold...>. Gõ 'help' để xem chi tiết.")
                continue

            sub = args[0].lower()
            if sub in ("stop", "cancel"):
                client.xmap_stop()

            elif sub == "status":
                st = client.xmap_status()
                print(f"[*] Trạng thái: {st['status_message']}")
                print(f"    Map hiện tại:    {st['current_map_name']} (ID: {st['current_map_id']})")
                if st['target_map_id'] is not None:
                    print(f"    Map đích:        {st['target_map_name']} (ID: {st['target_map_id']})")
                    print(f"    Tiến độ:         Chặng {st['current_step']}/{st['total_steps']}")
                print(f"    Capsule Đặc Biệt: {st['capsule_vip']} (Có trong Balo: {st['has_capsule_vip']})")
                print(f"    Capsule Thường:   {st['capsule_normal']} (Có trong Balo: {st['has_capsule_normal']})")
                print(f"    Tăng tốc tàu thời gian: {st.get('auto_speedup', '?')} (tốn 1 ngọc)")

            elif sub in ("csvip", "csdb", "capsule"):
                is_on = client.xmap_controller.toggle_use_capsule_vip()
                print(f"[*] Đã {'BẬT' if is_on else 'TẮT'} sử dụng Capsule Đặc Biệt!")

            elif sub in ("cs", "xcsb", "capsule_thuong"):
                is_on = client.xmap_controller.toggle_use_capsule_normal()
                print(f"[*] Đã {'BẬT' if is_on else 'TẮT'} sử dụng Capsule Thường!")

            elif sub in ("speedup", "speed", "nhanh"):
                is_on = client.xmap_controller.toggle_auto_speedup()
                print(f"[*] Tự tăng tốc tàu thời gian: {'BẬT (tốn 1 ngọc/lượt)!' if is_on else 'TẮT (chờ miễn phí ~10s)!'}")

            elif sub == "path":
                if len(args) < 3:
                    print("Cú pháp: xmap path <start_map> <end_map> (Ví dụ: xmap path 0 109)")
                    continue
                cgender = client.myChar.cgender
                s_id = resolve_map_id(args[1], cgender=cgender)
                e_id = resolve_map_id(args[2], cgender=cgender)
                if s_id is None:
                    print(f"[!] Không nhận diện được map xuất phát: '{args[1]}'")
                    continue
                if e_id is None:
                    print(f"[!] Không nhận diện được map đích: '{args[2]}'")
                    continue

                way = client.find_path(s_id, e_id)
                if way is None:
                    print(f"[!] Không tìm thấy đường đi từ ID {s_id} đến ID {e_id}!")
                else:
                    print(f"\n[+] Lộ trình tối ưu ({len(way)} bước) từ '{get_map_name(s_id)}' ({s_id}) -> '{get_map_name(e_id)}' ({e_id}):")
                    for idx, step in enumerate(way):
                        info_str = f" (info={step.info})" if step.info else ""
                        print(f"  [{idx+1:02d}] Map {step.map_start:3d} ({get_map_name(step.map_start):<22}) "
                              f"-> Map {step.to:3d} ({get_map_name(step.to):<22}) [{step.type.name}{info_str}]")

            elif sub == "list":
                print("\n=== DANH SÁCH CÁC HÀNH TINH VÀ BẢN ĐỒ ===")
                for names, maps in GROUP_MAPS_DEF:
                    print(f"\n* {' / '.join(names)} ({len(maps)} maps):")
                    for mid in maps:
                        print(f"    - ID {mid:3d}: {get_map_name(mid)}")

            else:
                target = " ".join(args)
                client.xmap(target)

        else:
            print(f"Không rõ lệnh '{cmd}'. Gõ 'help' để xem danh sách lệnh.")


if __name__ == "__main__":
    # Hỗ trợ cờ kiểm thử nhanh từ dòng lệnh:
    # python -m ClientNROpy.main --test-xmap
    if "--test-xmap" in sys.argv:
        from ClientNROpy.xmap_cli import test_requested_maps
        test_requested_maps()
        sys.exit(0)

    # Đọc cấu hình kết nối
    host = "51.79.163.109"
    port = 12457
    user = "poopooi01"
    pwd = "02082003"
    ver = "2.1.4"
    auto_xmap_target = None
    no_cli = False

    args = sys.argv[1:]
    idx = 0
    clean_args = []
    while idx < len(args):
        a = args[idx]
        if a == "--xmap" and idx + 1 < len(args):
            auto_xmap_target = args[idx + 1]
            idx += 2
        elif a == "--no-cli":
            no_cli = True
            idx += 1
        else:
            clean_args.append(a)
            idx += 1

    if len(clean_args) > 0:
        host = clean_args[0]
    if len(clean_args) > 1:
        port = int(clean_args[1])
    if len(clean_args) > 2:
        user = clean_args[2]
    if len(clean_args) > 3:
        pwd = clean_args[3]
    if len(clean_args) > 4:
        ver = clean_args[4]

    client = run_client(host=host, port=port, username=user, password=pwd, version=ver)

    if auto_xmap_target:
        print(f"\n[*] Kích hoạt tự động Xmap tới: '{auto_xmap_target}'...")
        client.xmap(auto_xmap_target)

    if not no_cli:
        interactive_cli(client)
    else:
        time.sleep(0.2)
        client.disconnect()
