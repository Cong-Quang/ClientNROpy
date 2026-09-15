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
)


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


if __name__ == "__main__":
    host = sys.argv[1] if len(sys.argv) > 1 else "51.79.163.109"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 12457
    user = sys.argv[3] if len(sys.argv) > 3 else "poopooi02"
    pwd = sys.argv[4] if len(sys.argv) > 4 else "02082003"
    ver = sys.argv[5] if len(sys.argv) > 5 else "2.1.4"

    client = run_client(host=host, port=port, username=user, password=pwd, version=ver)
    time.sleep(1.0)
    client.disconnect()
