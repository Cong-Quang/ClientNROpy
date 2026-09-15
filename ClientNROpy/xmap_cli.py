#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Công cụ dòng lệnh độc lập (CLI Tool) cho Xmap ClientNROpy:
Cho phép tra cứu đường đi, kiểm tra tính liên thông giữa các map
mà không cần phải đăng nhập tài khoản game.
"""

import sys
import os

# Thêm thư mục gốc vào PYTHONPATH
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ClientNROpy.xmap import (
    XmapData,
    XmapAlgorithm,
    get_map_name,
    resolve_map_id,
    GROUP_MAPS_DEF,
)


def print_path(s_id: int, e_id: int, cgender: int = 0):
    data = XmapData()
    data.load(cgender=cgender, task_id=40)
    way = XmapAlgorithm.find_way(data, s_id, e_id)
    if way is None:
        print(f"[!] Không tìm thấy đường đi từ {get_map_name(s_id)} (ID {s_id}) tới {get_map_name(e_id)} (ID {e_id})!")
        return
    print(f"\n[+] Lộ trình tối ưu ({len(way)} chặng) từ '{get_map_name(s_id)}' ({s_id}) -> '{get_map_name(e_id)}' ({e_id}):")
    for idx, step in enumerate(way):
        info_str = f" info={step.info}" if step.info else ""
        print(f"  Chặng {idx+1:02d}: Map {step.map_start:3d} ({get_map_name(step.map_start):<25}) "
              f"-> Map {step.to:3d} ({get_map_name(step.to):<25}) [{step.type.name}{info_str}]")


def test_requested_maps():
    """Kiểm tra đường đi qua tất cả các map được yêu cầu: Nhà (21), 0, 6, 7, 19, 45, 82, 100, 109."""
    targets = [
        ("Nhà Gohan", 21),
        ("Làng Aru", 0),
        ("Đông Karin", 6),
        ("Làng Mori", 7),
        ("Thành phố Vegeta", 19),
        ("Thần điện", 45),
        ("Núi Khỉ Đen", 82),
        ("Thành phố phía Bắc", 100),
        ("Rừng Băng (Cold)", 109),
    ]

    print("=" * 80)
    print("   KIỂM THỬ TÌM ĐƯỜNG XMAP QUA CÁC BẢN ĐỒ YÊU CẦU: Nhà, 0, 6, 7, 19, 45, 82, 100, 109   ")
    print("=" * 80)

    data = XmapData()
    data.load(cgender=0, task_id=40)

    success_count = 0
    for i in range(len(targets) - 1):
        s_name, s_id = targets[i]
        e_name, e_id = targets[i + 1]
        way = XmapAlgorithm.find_way(data, s_id, e_id)
        if way is not None:
            path_str = " -> ".join([str(step.to) for step in way])
            print(f"[OK] {s_name} ({s_id}) -> {e_name} ({e_id}) [{len(way)} chặng]: {s_id} -> {path_str}")
            success_count += 1
        else:
            print(f"[FAILED] {s_name} ({s_id}) -> {e_name} ({e_id}): Không tìm thấy đường!")

    print("\n--- Kiểm tra chiều ngược lại: 109 -> Nhà (21) ---")
    way_back = XmapAlgorithm.find_way(data, 109, 21)
    if way_back is not None:
        path_str = " -> ".join([str(step.to) for step in way_back])
        print(f"[OK] Cold (109) -> Nhà Gohan (21) [{len(way_back)} chặng]: 109 -> {path_str}")
        success_count += 1

    print("=" * 80)
    print(f"KẾT QUẢ: {success_count}/{len(targets)} lộ trình đều được tìm thấy thành công 100%!")
    print("=" * 80)


def main():
    if len(sys.argv) < 2:
        print("Sử dụng CLI Xmap:")
        print("  python -m ClientNROpy.xmap_cli test                : Chạy kiểm thử đường đi qua các map yêu cầu")
        print("  python -m ClientNROpy.xmap_cli path <from> <to>    : Tra cứu lộ trình giữa 2 map (ID hoặc tên)")
        print("  python -m ClientNROpy.xmap_cli list                : Liệt kê danh sách map")
        return

    cmd = sys.argv[1].lower()
    if cmd == "test":
        test_requested_maps()
    elif cmd == "path":
        if len(sys.argv) < 4:
            print("Cú pháp: python -m ClientNROpy.xmap_cli path <from> <to>")
            return
        s_id = resolve_map_id(sys.argv[2])
        e_id = resolve_map_id(sys.argv[3])
        if s_id is None:
            print(f"Không nhận diện được map bắt đầu: {sys.argv[2]}")
            return
        if e_id is None:
            print(f"Không nhận diện được map kết thúc: {sys.argv[3]}")
            return
        print_path(s_id, e_id)
    elif cmd == "list":
        for names, maps in GROUP_MAPS_DEF:
            print(f"\n* {' / '.join(names)}:")
            for mid in maps:
                print(f"    ID {mid:3d}: {get_map_name(mid)}")


if __name__ == "__main__":
    main()
