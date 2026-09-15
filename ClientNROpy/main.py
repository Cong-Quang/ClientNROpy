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


def run_client(host="51.79.163.109", port=12457, username="poopooi02", password="02082003", version="2.1.4"):
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
    client.on_chat(lambda cid, text: print(f"[CHAT MAP {cid}] {text}"))

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
    time.sleep(1.0)

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
    print("\n" + "=" * 60)
    print("         HƯỚNG DẪN DÒNG LỆNH (CLI) - CLIENT NRO PY         ")
    print("=" * 60)
    print("  xmap <id|tên>          : Bắt đầu Xmap di chuyển tới map chỉ định")
    print("                           Ví dụ: xmap 0, xmap 6, xmap 109, xmap nha, xmap cold")
    print("  xmap stop / cancel     : Dừng tiến trình Xmap hiện tại")
    print("  xmap status            : Xem trạng thái, tiến độ và cấu hình Capsule")
    print("  xmap csvip             : Bật / Tắt sử dụng Capsule Đặc Biệt (bay nhanh)")
    print("  xmap cs                : Bật / Tắt sử dụng Capsule Thường (bay nhanh)")
    print("  xmap path <from> <to>  : Tra cứu lộ trình tối ưu giữa 2 map (vd: xmap path 0 109)")
    print("  xmap list              : Xem danh sách các nhóm bản đồ")
    print("  map                    : Xem thông tin bản đồ hiện tại, tọa độ và waypoints")
    print("  zone [id]              : Xem danh sách khu hoặc đổi khu (vd: zone 5)")
    print("  chat <nội dung>        : Chat trong bản đồ")
    print("  info                   : In lại thông tin nhân vật")
    print("  help                   : Hiển thị bảng trợ giúp lệnh này")
    print("  exit / quit            : Đăng xuất và thoát chương trình")
    print("=" * 60 + "\n")


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

            elif sub in ("csvip", "csdb", "capsule"):
                is_on = client.xmap_controller.toggle_use_capsule_vip()
                print(f"[*] Đã {'BẬT' if is_on else 'TẮT'} sử dụng Capsule Đặc Biệt!")

            elif sub in ("cs", "xcsb", "capsule_thuong"):
                is_on = client.xmap_controller.toggle_use_capsule_normal()
                print(f"[*] Đã {'BẬT' if is_on else 'TẮT'} sử dụng Capsule Thường!")

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
    user = "poopooi02"
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
        time.sleep(1.0)
        client.disconnect()
