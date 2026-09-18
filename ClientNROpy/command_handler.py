# -*- coding: utf-8 -*-
"""
Bộ phân tích và thực thi dòng lệnh điều khiển (command_handler.py).
Hỗ trợ cả:
1. Lệnh điều khiển trò chơi cho 1 ClientNRO (execute_client_command)
2. Lệnh quản trị đa tài khoản (execute_multi_command):
   - all <lệnh> (thực thi trên mọi acc)
   - acc <id> <lệnh> (thực thi trên acc chỉ định)
   - use <id|all> (chuyển ngữ cảnh)
   - log on/off, log chat on/off, cls
   - acc list/status, acc start, acc stop
"""

import os
import sys
import time
import re
import difflib
from typing import Optional, Union, Tuple, List

from .client import ClientNRO
from .logger import logger
from .display import (
    print_cli_help,
    print_character_overview,
    print_inventory,
    print_pet_info,
    print_map_and_zones,
    print_boss_list,
    print_hunt_status,
    print_quest_status,
    print_shuttle_status,
    print_accounts_table,
)
from .xmap import resolve_map_id, get_map_name, GROUP_MAPS_DEF
from .game_data import (
    get_item_name,
    get_mob_name,
    get_npc_name,
    get_item_info,
    format_item_details,
    format_big_number,
)

# Bảng alias lệnh viết tắt phổ biến trong Terminal
CLI_ALIASES = {
    "stt": "status",
    "st": "status",
    "ls": "status",
    "inf": "info",
    "thongtin": "info",
    "itm": "item",
    "timitem": "item",
    "checkitem": "item",
    "finditem": "item",
    "zon": "zone",
    "zn": "zone",
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
    "h": "help",
    "trogiup": "help",
    "conn": "login",
    "dangnhap": "login",
    "dis": "logout",
    "dangxuat": "logout",
    "thoat": "logout",
}

# Danh sách toàn bộ các lệnh hợp lệ để gợi ý khi người dùng gõ nhầm (Fuzzy suggestion)
ALL_KNOWN_COMMANDS = [
    "status", "use", "all", "acc", "login", "logout", "reconnect",
    "item", "zone", "map", "info", "bag", "box", "pet", "harvest",
    "xmap", "goto", "hunt", "boss", "ak", "ts", "tansat",
    "anhat", "cnn", "nsq", "abf", "autohs", "trainpet", "trainacc",
    "nvbm", "shuttle", "chat", "cls", "clear", "log", "mute",
    "telegram", "proxy", "help", "exit", "quit"
]

_TRAVEL_ZONE_KEYS = ("min", "least", "itnguoi", "vang", "empty", "auto")
_TRAVEL_ACTIONS = {
    "ts": "ts on",
    "tansat": "ts on",
    "ak": "ak on",
    "hunt": "hunt on",
    "boss": "hunt on",
}


def _build_travel_chain(args: List[str], default_zone: Optional[str] = None,
                        default_action: Optional[str] = None) -> List[str]:
    """
    Dựng chuỗi lệnh di chuyển [xmap -> zone -> action] từ tham số.
    Dùng cho lệnh `goto`.
    - args[0]: <map_id|tên map>
    - args tiếp theo (thứ tự tự do): [min|khu] chọn khu, [ts|ak|hunt] hành động sau khi tới.
    """
    chain = [f"xmap {args[0]}"]
    zone_set = False
    action_set = False
    for raw in args[1:]:
        sub = raw.lower()
        if not zone_set and (sub in _TRAVEL_ZONE_KEYS or sub.isdigit()):
            chain.append("zone min" if sub in _TRAVEL_ZONE_KEYS else f"zone {sub}")
            zone_set = True
        elif not action_set and sub in _TRAVEL_ACTIONS:
            chain.append(_TRAVEL_ACTIONS[sub])
            action_set = True
    if default_zone and not zone_set:
        chain.append(default_zone)
    if default_action and not action_set:
        chain.append(default_action)
    return chain


def execute_client_command(client: ClientNRO, line: str) -> bool:
    """
    Thực thi 1 dòng lệnh trên 1 đối tượng ClientNRO cụ thể.
    Trả về False nếu gặp lệnh thoát (exit/quit), ngược lại trả về True.
    """
    line = line.strip()
    if not line:
        return True

    tag = client.account_id if hasattr(client, "account_id") else "Client"

    # Hỗ trợ chuỗi lệnh liên tiếp (then / && / ;)
    if re.search(r"\s+then\s+|\s*&&\s*", line, re.IGNORECASE):
        commands = [c.strip() for c in re.split(r"\s+then\s+|\s*&&\s*", line, flags=re.IGNORECASE) if c.strip()]
        if len(commands) > 1:
            logger.system(f"Bắt đầu chuỗi lệnh tự động: {' -> '.join(commands)}", account_tag=tag)
            client.execute_chain(commands)
            return True

    parts = line.split()
    cmd = parts[0].lower()
    if cmd in CLI_ALIASES:
        cmd = CLI_ALIASES[cmd]
    args = parts[1:]

    if cmd in ("exit", "quit", "q"):
        logger.system("Đang đăng xuất tài khoản...", account_tag=tag)
        client.logout()
        return False

    elif cmd == "help":
        print_cli_help()

    elif cmd == "info":
        print_character_overview(client.myChar)
        print_inventory(client.myChar)

    elif cmd in ("bag", "balo", "tui"):
        print_inventory(client.myChar)

    elif cmd in ("box", "ruong"):
        char = client.myChar
        print("\n" + "-" * 55)
        print(f"RƯƠNG ĐỒ [{tag}] ({len(char.arrItemBox)} món)")
        print("-" * 55)
        if not char.arrItemBox:
            print("  (Rương trống)")
        for i, it in enumerate(char.arrItemBox):
            opts = " | ".join([opt.getText() for opt in it.options])
            opt_str = f" [{opts}]" if opts else ""
            it_name = get_item_name(it.template_id, it.info or "")
            print(f"  [{i+1:02d}] {it_name} (ID: {it.template_id}) x{it.quantity:<4}{opt_str}")

    elif cmd in ("pet", "detu"):
        action_map = {
            "0": 0, "follow": 0, "dtheo": 0, "theo": 0,
            "1": 1, "protect": 1, "baove": 1, "bv": 1,
            "2": 2, "attack": 2, "tancong": 2, "tc": 2, "danh": 2,
            "3": 3, "home": 3, "venha": 3, "nha": 3,
            "4": 4, "fuse": 4, "hopthe": 4, "ht": 4,
            "5": 5, "porata": 5, "bongtai": 5,
        }
        if not args:
            print_pet_info(client.myChar.pet)
        elif args[0].lower() in action_map:
            act_code = action_map[args[0].lower()]
            client.change_pet_status(act_code)
            st_names = {0: "Đi theo", 1: "Bảo vệ", 2: "Tấn công", 3: "Về nhà", 4: "Hợp thể", 5: "Hợp thể Porata"}
            logger.system(f"Đã chuyển trạng thái đệ tử sang: {st_names.get(act_code)}", account_tag=tag)
        else:
            print("Cú pháp: pet [follow|protect|attack|home|fuse|porata|0-5]")

    elif cmd in ("harvest", "dau", "caydau", "nhatdau"):
        client.request_magic_tree(action=2)
        logger.system("Đã gửi yêu cầu thu hoạch đậu thần từ cây đậu.", account_tag=tag)

    elif cmd == "map":
        print_map_and_zones(client.myChar.mapInfo)

    elif cmd in ("item", "timitem", "checkitem"):
        if not args:
            print("Cú pháp: item <id|tên vật phẩm> (Ví dụ: item 14 hoặc item đậu)")
        else:
            q = " ".join(args).lower().strip()
            is_num = q.isdigit()
            tid = int(q) if is_num else -1
            bag = client.myChar.arrItemBag
            matched = []
            for s_idx, it in enumerate(bag):
                match = False
                it_name = get_item_name(it.template_id, it.info or "")
                if is_num and it.template_id == tid:
                    match = True
                elif not is_num:
                    if q in it_name.lower() or q in (it.info or "").lower():
                        match = True
                if match:
                    matched.append((s_idx, it, it_name))
            if matched:
                tot = sum(it.quantity for _, it, _ in matched)
                print(f"[*] Tìm thấy {len(matched)} ô chứa (Tổng cộng: x{tot:,}) [{tag}]:")
                sample_tid = matched[0][1].template_id
                meta_str = format_item_details(sample_tid)
                if meta_str:
                    print(f"    - [Thông tin]: {meta_str}")
                for s_idx, it, it_name in matched:
                    opt_str = f" [{ ' | '.join(opt.getText() for opt in it.options[:2]) }]" if it.options else ""
                    print(f"    - Ô {s_idx+1:02d}: x{it.quantity} {it_name} (ID: {it.template_id}){opt_str}")
            else:
                print(f"[x] Không tìm thấy vật phẩm '{q}' trong balo của [{tag}].")

    elif cmd == "zone":
        if args and args[0].lower() in ("min", "least", "itnguoi", "vang", "auto", "empty"):
            logger.system("Đang tìm và chuyển sang khu vực ít người nhất...", account_tag=tag)
            zid = client.change_to_least_populated_zone()
            if zid is not None:
                logger.system(f"Đã chuyển thành công sang Khu {zid} (ít người nhất).", account_tag=tag)
            else:
                logger.warn("Không lấy được danh sách khu hoặc đã ở khu tối ưu.", account_tag=tag)
        elif args and args[0].isdigit():
            z_id = int(args[0])
            logger.system(f"Yêu cầu chuyển sang Khu {z_id}...", account_tag=tag)
            client.change_zone(z_id)
        else:
            client.request_zones()
            time.sleep(0.4)
            print(f"\n* DANH SÁCH KHU VỰC ({len(client.myChar.mapInfo.zones)} khu) [{tag}]:")
            for z in client.myChar.mapInfo.zones:
                curr = " <== [HIỆN TẠI]" if z.zoneId == client.myChar.mapInfo.zoneID else ""
                print(f"  - Khu {z.zoneId:02d}: {z.numPlayer:02d}/{z.maxPlayer:02d} ({z.status}){curr}")

    elif cmd == "chat":
        if args:
            client.chat(" ".join(args))
        else:
            print("Cú pháp: chat <nội dung>")

    elif cmd in ("hs", "revive", "hoisinh", "wake"):
        at_place = False
        if args and args[0].lower() in ("ngoc", "gem", "place", "here", "1"):
            at_place = True
        ok, msg = client.revive(at_place=at_place)
        logger.system(f"Hồi sinh: {msg}", account_tag=tag)

    elif cmd in ("autohs", "autors", "auto_revive"):
        if not args:
            client.toggle_auto_revive()
        elif args[0].lower() in ("on", "start", "1", "true"):
            client.auto_revive_manager.enable()
        elif args[0].lower() in ("off", "stop", "0", "false"):
            client.auto_revive_manager.disable()
        elif args[0].lower() in ("gem", "ngoc", "place", "here"):
            client.set_auto_revive_mode("gem")
        elif args[0].lower() in ("town", "ve", "thanh", "nha"):
            client.set_auto_revive_mode("town")
        elif args[0].lower() in ("status", "st", "info"):
            st = client.get_auto_revive_status()
            print(f"\n=== TRẠNG THÁI TỰ ĐỘNG HỒI SINH [{tag}] ===")
            print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if st['is_enabled'] else 'ĐÃ TẮT [OFF]'}")
            print(f"- Chế độ:                {st['mode_str']}")
            print(f"- Đã hồi sinh:           {st['revive_count']} lần")
            print(f"- Trạng thái nhân vật:   {'ĐÃ CHẾT' if st['is_currently_dead'] else 'CÒN SỐNG'}\n")
        else:
            print("Cú pháp: autohs [on|off|ngoc|ve|status]")

    elif cmd == "useitem":
        if not args or args[0].lower() in ("status", "st", "info"):
            st = client.get_auto_use_item_status()
            print(f"\n=== TRẠNG THÁI TỰ ĐỘNG DÙNG ITEM [{tag}] ===")
            print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if st['is_enabled'] else 'ĐÃ TẮT [OFF]'}")
            if st['item_template_id'] is not None:
                print(f"- Item Template ID:      {st['item_template_id']}")
                print(f"- Chu kỳ:                {st['interval_minutes']:g} phút")
                print(f"- Đã dùng:               {st['use_count']} lần\n")
            else:
                print("Cú pháp: useitem <id> <phút> (vd: useitem 380 10)")
        elif args[0].lower() in ("stop", "off", "0", "false"):
            ok, msg = client.stop_auto_use_item()
            logger.system(msg, account_tag=tag)
        elif len(args) >= 2:
            try:
                ok, msg = client.start_auto_use_item(int(args[0]), float(args[1]))
                logger.system(msg, account_tag=tag)
            except ValueError:
                print("Cú pháp: useitem <id> <phút>")

    elif cmd == "boss":
        if not args or args[0].lower() in ("list", "ls", "all", "history"):
            print_boss_list(client, filter_mode="all")
        elif args[0].lower() in ("alive", "live", "song"):
            print_boss_list(client, filter_mode="alive")
        elif args[0].lower() in ("dead", "die", "chet"):
            print_boss_list(client, filter_mode="dead")
        elif args[0].lower() in ("go", "hunt", "to"):
            if len(args) < 2:
                print("Cú pháp: boss go <stt|tên>")
                return True
            target = " ".join(args[1:])
            ok, msg = client.go_to_boss(target)
            logger.system(msg, account_tag=tag)
        elif args[0].lower() in ("clear", "reset"):
            client.boss_manager.clear()
            logger.system("Đã xóa toàn bộ lịch sử Boss.", account_tag=tag)
        elif args[0].lower() in ("on", "start"):
            client.start_auto_hunt()
            logger.system("Auto Săn Boss: BẬT!", account_tag=tag)
        elif args[0].lower() in ("off", "stop"):
            client.stop_auto_hunt()
            logger.system("Auto Săn Boss: TẮT!", account_tag=tag)
        elif args[0].lower() in ("status", "st"):
            print_hunt_status(client)
        else:
            target = " ".join(args)
            ok, msg = client.go_to_boss(target)
            logger.system(msg, account_tag=tag)

    elif cmd in ("hunt", "autohunt", "huntauto"):
        if not args:
            is_on = client.toggle_auto_hunt()
            logger.system(f"Auto Săn Boss: {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)
        else:
            sub = args[0].lower()
            if sub in ("auto", "on", "start", "1", "true"):
                client.start_auto_hunt()
                logger.system("Auto Săn Boss & Tuần Tra: ĐÃ BẬT!", account_tag=tag)
            elif sub in ("off", "stop", "0", "false"):
                client.stop_auto_hunt()
                logger.system("Auto Săn Boss: ĐÃ TẮT!", account_tag=tag)
            elif sub in ("status", "st", "info"):
                print_hunt_status(client)
            elif sub in ("add", "them", "+"):
                if len(args) > 1:
                    b_name = " ".join(args[1:])
                    client.add_hunt_target(b_name)
                    logger.system(f"Đã thêm '{b_name}' vào Whitelist săn Boss.", account_tag=tag)
                else:
                    print("Cú pháp: hunt add <tên boss>")
            elif sub in ("del", "remove", "rm", "-"):
                if len(args) > 1:
                    b_name = " ".join(args[1:])
                    client.remove_hunt_target(b_name)
                    logger.system(f"Đã xóa '{b_name}' khỏi Whitelist săn Boss.", account_tag=tag)
            elif sub in ("clear", "reset"):
                client.clear_hunt_targets()
                logger.system("Đã xóa toàn bộ Whitelist (đang săn tất cả Boss).", account_tag=tag)
            elif sub in ("all", "tatca"):
                client.boss_hunter.set_hunt_all(not client.boss_hunter.hunt_all)
                logger.system(f"Săn tất cả Boss: {'BẬT' if client.boss_hunter.hunt_all else 'TẮT'}!", account_tag=tag)
            elif sub in ("loot", "nhatdo"):
                client.boss_hunter.auto_loot = not client.boss_hunter.auto_loot
                logger.system(f"Tự nhặt đồ khi diệt Boss: {'BẬT' if client.boss_hunter.auto_loot else 'TẮT'}!", account_tag=tag)
            elif sub in ("combo", "skill", "skills"):
                if len(args) > 1:
                    sids = []
                    for a in args[1:]:
                        if a.isdigit():
                            sids.append(int(a))
                    if sids:
                        ok, msg = client.set_combo_skills(sids)
                        logger.system(msg, account_tag=tag)
                    else:
                        print("Cú pháp: hunt combo <skill_id_1> <skill_id_2> <skill_id_3>")
                else:
                    print("Cú pháp: hunt combo <skill_id_1> <skill_id_2> <skill_id_3>")
            elif sub in ("patrol", "tuantra"):
                if len(args) > 1:
                    pmode = args[1].lower()
                    if pmode in ("namec", "namek"):
                        client.boss_hunter.set_patrol_mode("namec")
                    elif pmode in ("tl", "future"):
                        client.boss_hunter.set_patrol_mode("future")
                    elif pmode in ("all", "tatca"):
                        client.boss_hunter.set_patrol_mode("all")
                is_p = client.boss_hunter.toggle_auto_patrol()
                logger.system(f"Tự động tuần tra: {'BẬT' if is_p else 'TẮT'}!", account_tag=tag)
            else:
                b_name = " ".join(args)
                client.add_hunt_target(b_name)
                client.start_auto_hunt()
                logger.system(f"Đã thêm '{b_name}' vào Whitelist và kích hoạt Auto Săn Boss!", account_tag=tag)

    elif cmd in ("shuttle", "dual"):
        if not args or (len(args) == 1 and args[0].lower() in ("status", "st")):
            print_shuttle_status(client)
        elif len(args) == 1 and args[0].lower() in ("stop", "off"):
            client.stop_shuttle()
            logger.system("Shuttle: TẮT!", account_tag=tag)
        elif len(args) >= 2 and args[0].isdigit() and args[1].isdigit():
            rounds = int(args[2]) if len(args) >= 3 and args[2].isdigit() else 0
            ok = client.start_shuttle(int(args[0]), int(args[1]), rounds)
            logger.system(f"Shuttle {args[0]} <-> {args[1]}: {'BẬT!' if ok else 'THẤT BẠI!'}", account_tag=tag)
        else:
            print("Cú pháp: shuttle <mapA> <mapB> [vòng] | shuttle stop")

    elif cmd in ("nvbm", "nhiemvu", "quest", "bomong"):
        subs = [a.lower().strip() for a in args]
        if not subs or any(x in ("status", "st", "info") for x in subs):
            print_quest_status(client)
        elif any(x in ("off", "stop", "0") for x in subs):
            client.stop_auto_quest()
            logger.system("Auto NV Bò Mộng: TẮT!", account_tag=tag)
        elif any(x in ("on", "start", "1") for x in subs):
            client.start_auto_quest()
            logger.system("Auto NV Bò Mộng: BẬT!", account_tag=tag)
        else:
            print("Cú pháp: nvbm [on|off|status]")

    # Lệnh chiến đấu và tàn sát
    elif cmd == "focus":
        t_type = args[0] if args else ""
        q = " ".join(args[1:]) if len(args) > 1 else None
        ok, msg = client.focus(t_type, q)
        logger.system(msg, account_tag=tag)

    elif cmd in ("tele", "tp"):
        target = " ".join(args) if args else None
        ok, msg = client.teleport_to(target)
        logger.system(msg, account_tag=tag)

    elif cmd == "ak":
        enable = None
        if args:
            if args[0].lower() in ("on", "1", "true"):
                enable = True
            elif args[0].lower() in ("off", "0", "false"):
                enable = False
        is_on = client.toggle_ak(enable)
        logger.system(f"Tự động đánh (AK): {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)

    elif cmd in ("ts", "tansat"):
        if not args:
            is_on = client.toggle_tansat()
            logger.system(f"Tàn sát: {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)
        else:
            sub = args[0].lower()
            if sub in ("on", "start"):
                client.toggle_tansat(True)
                logger.system("Tàn sát: BẬT!", account_tag=tag)
            elif sub in ("off", "stop"):
                client.toggle_tansat(False)
                logger.system("Tàn sát: TẮT!", account_tag=tag)
            elif sub in ("mob", "quai"):
                client.toggle_tansat(True, mode="mob")
                logger.system("Tàn sát Quái vật: BẬT!", account_tag=tag)
            elif sub in ("player", "char", "pk"):
                client.toggle_tansat(True, mode="player")
                logger.system("Tàn sát Người chơi (Auto PK): BẬT!", account_tag=tag)
            elif sub == "clear":
                client.combat_manager.clear_mob_targets()
                logger.system("Đã xoá bộ lọc quái (tàn sát tất cả quái trong map).", account_tag=tag)

    elif cmd == "nsq":
        client.combat_manager.avoid_super_mob = not client.combat_manager.avoid_super_mob
        logger.system(f"Né siêu quái (nsq): {'BẬT' if client.combat_manager.avoid_super_mob else 'TẮT'}!", account_tag=tag)

    elif cmd == "anhat":
        is_on = client.toggle_auto_pick()
        logger.system(f"Tự nhặt đồ (anhat): {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)

    elif cmd == "cnn":
        client.combat_manager.pick_gem_only = not client.combat_manager.pick_gem_only
        client.combat_manager.auto_pick = True
        logger.system(f"Chỉ nhặt ngọc (cnn): {'BẬT' if client.combat_manager.pick_gem_only else 'TẮT'}!", account_tag=tag)

    elif cmd == "abf":
        if args and args[0].isdigit():
            val = int(args[0]) / 100.0
            client.combat_manager.pean_threshold = val
            client.combat_manager.auto_pean = True
            logger.system(f"Tự dùng đậu khi HP/KI dưới {int(val*100)}%!", account_tag=tag)
        else:
            is_on = client.toggle_auto_pean()
            logger.system(f"Tự dùng đậu (abf): {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)

    elif cmd == "combat":
        st = client.combat_status()
        print(f"\n=== CẤU HÌNH CHIẾN ĐẤU & TÀN SÁT [{tag}] ===")
        print(f"- Tự động đánh (AK):     {'BẬT' if st['is_ak'] else 'TẮT'}")
        print(f"- Tàn sát:               {'BẬT' if st['is_tansat'] else 'TẮT'} (Mode: {st['tansat_mode']})")
        print(f"- Tự nhặt đồ:            {'BẬT' if st['auto_pick'] else 'TẮT'}")
        print(f"- Chỉ nhặt ngọc:         {'BẬT' if st['pick_gem_only'] else 'TẮT'}")
        print(f"- Tự dùng đậu:           {'BẬT' if st['auto_pean'] else 'TẮT'}\n")

    elif cmd == "xmap":
        if not args:
            print("Cú pháp: xmap <id|tên>. Gõ 'help' để xem chi tiết.")
            return True
        sub = args[0].lower()
        if sub in ("stop", "cancel"):
            client.xmap_stop()
            logger.system("Đã dừng di chuyển Xmap.", account_tag=tag)
        elif sub == "status":
            st = client.xmap_status()
            print(f"[*] Trạng thái Xmap [{tag}]: {st['status_message']}")
            print(f"    Map hiện tại: {st['current_map_name']} (ID: {st['current_map_id']})")
            if st['target_map_id'] is not None:
                print(f"    Đích đến:     {st['target_map_name']} (ID: {st['target_map_id']})")
        elif sub in ("csvip", "csdb"):
            is_on = client.xmap_controller.toggle_use_capsule_vip()
            logger.system(f"Sử dụng Capsule Đặc Biệt: {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)
        elif sub in ("cs", "capsule"):
            is_on = client.xmap_controller.toggle_use_capsule_normal()
            logger.system(f"Sử dụng Capsule Thường: {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)
        elif sub == "speedup":
            is_on = client.xmap_controller.toggle_auto_speedup()
            logger.system(f"Tự tăng tốc tàu vũ trụ (1 ngọc): {'BẬT' if is_on else 'TẮT'}!", account_tag=tag)
        elif sub == "list":
            print("\n=== DANH SÁCH BẢN ĐỒ ===")
            for names, maps in GROUP_MAPS_DEF:
                print(f"* {' / '.join(names)} ({len(maps)} maps): " + ", ".join([f"{m}:{get_map_name(m)}" for m in maps[:6]]) + "...")
        else:
            target = " ".join(args)
            logger.system(f"Bắt đầu Xmap di chuyển tới: '{target}'...", account_tag=tag)
            client.xmap(target)

    elif cmd == "goto":
        if not args:
            print("Cú pháp: goto <map_id|tên> [min|khu] [ts|hunt|ak]")
            return True
        chain = _build_travel_chain(args)
        logger.system(f"Kích hoạt Macro Goto: {' -> '.join(chain)}", account_tag=tag)
        client.execute_chain(chain)

    elif cmd in ("trainpet", "upde", "autode", "petauto"):
        if not args or args[0].lower() in ("status", "st", "info"):
            tp = client.auto.train_pet
            print(f"\n=== TRẠNG THÁI AUTO ÚP ĐỆ TỬ [{tag}] ===")
            print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if tp.is_enabled else 'ĐÃ TẮT [OFF]'}")
            print(f"- Chế độ:                {tp.mode.name}")
            print(f"- Đánh khi đệ lười:      {tp.attack_mode.name}\n")
            print("Cú pháp: trainpet [normal|avoid|kaioken|off]")
            print("         trainpet atk [mob|pet|me]")
        elif args[0].lower() in ("off", "stop", "0", "tat"):
            ok, msg = client.auto.stop_train_pet()
            logger.system(msg, account_tag=tag)
        elif args[0].lower() in ("atk", "attack"):
            sub_atk = args[1].lower() if len(args) > 1 else "mob"
            ok, msg = client.auto.set_train_pet_attack_mode(sub_atk)
            logger.system(msg, account_tag=tag)
        else:
            mode_arg = args[0].lower()
            ok, msg = client.auto.start_train_pet(mode_arg)
            logger.system(msg, account_tag=tag)

    elif cmd in ("trainacc", "newacc", "autonewacc", "nvts"):
        if not args or args[0].lower() in ("on", "start", "1"):
            ok, msg = client.auto.start_train_new_account()
            logger.system(msg, account_tag=tag)
        elif args[0].lower() in ("off", "stop", "0", "tat"):
            ok, msg = client.auto.stop_train_new_account()
            logger.system(msg, account_tag=tag)
        elif args[0].lower() in ("status", "st", "info"):
            tna = client.auto.train_new_acc
            print(f"\n=== TRẠNG THÁI AUTO TÂN THỦ SƠ SINH [{tag}] ===")
            print(f"- Hoạt động:             {'ĐANG BẬT [ON]' if tna.is_enabled else 'ĐÃ TẮT [OFF]'}")
            print(f"- Nhiệm vụ hiện tại:     Task ID {client.myChar.ctaskId}\n")
        else:
            print("Cú pháp: trainacc [on|off|status]")

    else:
        matches = difflib.get_close_matches(cmd, ALL_KNOWN_COMMANDS, n=2, cutoff=0.55)
        if matches:
            suggestion_str = " hoặc ".join([f"'{m}'" for m in matches])
            print(f"Không rõ lệnh '{cmd}'. Có phải bạn muốn dùng: {suggestion_str}?")
            print("Gõ 'help' để xem danh sách lệnh.")
        else:
            print(f"Không rõ lệnh '{cmd}'. Gõ 'help' để xem danh sách lệnh.")

    return True


def _telegram_nettest(bot) -> None:
    """Chẩn đoán từng tầng đường ra Internet tới Telegram API: DNS -> TCP 443 -> TLS -> getMe."""
    import socket
    import ssl

    host = "api.telegram.org"
    print(f"[*] Kiểm tra kết nối tới {host} ...")
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var)
        if val:
            print(f"    - Proxy hệ thống: {var}={val}")

    try:
        ip = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)[0][4][0]
        print(f"    [1] DNS: OK ({host} -> {ip})")
    except Exception as ex:
        print(f"    [1] DNS: FAIL ({ex}) — VPS không phân giải được tên miền!")
        return

    try:
        t0 = time.time()
        sock = socket.create_connection((host, 443), timeout=10)
        print(f"    [2] TCP 443: OK ({int((time.time() - t0) * 1000)}ms)")
    except Exception as ex:
        print(f"    [2] TCP 443: FAIL ({ex}) — NAT/firewall chặn cổng 443!")
        return

    try:
        ctx = ssl.create_default_context()
        t0 = time.time()
        tls_sock = ctx.wrap_socket(sock, server_hostname=host)
        print(f"    [3] TLS: OK ({tls_sock.version()}, {tls_sock.cipher()[0]}, {int((time.time() - t0) * 1000)}ms)")
        tls_sock.close()
    except Exception as ex:
        print(f"    [3] TLS: FAIL ({ex}) — gãy bắt tay TLS!")
        try:
            sock.close()
        except Exception:
            pass
        return

    try:
        res = bot._api_call("getMe", {}, timeout=15) or {}
        if res.get("ok"):
            print(f"    [4] API getMe: OK (@{res.get('result', {}).get('username')}) — token hợp lệ!")
        else:
            print(f"    [4] API getMe: FAIL ({res}) — token sai hoặc bot đã bị xóa!")
    except Exception as ex:
        print(f"    [4] API getMe: FAIL ({ex})")


def execute_multi_command(
    account_manager,
    active_target: Optional[Union[str, int]],
    line: str,
) -> Tuple[bool, Optional[Union[str, int]]]:
    """
    Xử lý các dòng lệnh cấp hệ thống hoặc phân phối tới các tài khoản.
    Trả về: (should_continue, new_active_target)
    """
    line = line.strip()
    if not line:
        return True, active_target

    parts = line.split()
    cmd = parts[0].lower()
    if cmd in CLI_ALIASES:
        cmd = CLI_ALIASES[cmd]
    args = parts[1:]

    # 1. Thoát chương trình
    if cmd in ("exit", "quit", "q"):
        account_manager.stop_all()
        return False, active_target

    # 2. Xoá màn hình
    if cmd in ("cls", "clear"):
        os.system("cls" if os.name == "nt" else "clear")
        return True, active_target

    # 3. Trợ giúp
    if cmd == "help":
        print_cli_help()
        return True, active_target

    # 4. Quản lý Log Console
    if cmd in ("log", "mute"):
        if cmd == "mute" or (args and args[0].lower() in ("off", "0", "mute", "false")):
            logger.set_muted(True)
            print("[*] Đã TẮT toàn bộ log nền (Console yên tĩnh để gõ lệnh).")
            return True, active_target
        if args and args[0].lower() in ("on", "1", "unmute", "true"):
            logger.set_muted(False)
            print("[*] Đã BẬT lại log nền.")
            return True, active_target
        if len(args) >= 2:
            sub = args[0].lower()
            val = args[1].lower() in ("on", "1", "true")
            if logger.set_channel(sub, val):
                print(f"[*] Kênh log '{sub.upper()}': {'BẬT' if val else 'TẮT'}!")
            else:
                print(f"Không tìm thấy kênh log '{sub}'. Các kênh: boss, chat, system, auto, alert")
            return True, active_target
        print(f"[*] Trạng thái Log: {'TẮT [MUTED]' if logger.muted else 'BẬT [ACTIVE]'}")
        for ch, en in logger.channels.items():
            print(f"    - Kênh {ch.upper():<8}: {'BẬT' if en else 'TẮT'}")
        print("    Cú pháp: log on | log off | log chat on/off | log boss on/off")
        return True, active_target

    # 5. Xem danh sách / trạng thái tài khoản
    if cmd in ("status", "st", "list", "ls") or (cmd == "acc" and args and args[0].lower() in ("list", "ls", "status", "st")):
        print_accounts_table(account_manager)
        return True, active_target

    # 6. Chuyển ngữ cảnh điều khiển (use / acc select)
    if cmd in ("use", "select") or (cmd == "acc" and args and args[0].lower() in ("use", "select")):
        target_token = args[0] if cmd in ("use", "select") else args[1]
        if target_token.lower() in ("all", "tatca", "*"):
            print("[*] Đã chuyển ngữ cảnh sang: TOÀN BỘ TÀI KHOẢN [ALL].")
            return True, None
        inst = account_manager.get_account(target_token)
        if inst:
            print(f"[*] Đã chọn tài khoản: {inst.tag}")
            return True, inst.config.acc_id
        else:
            print(f"[!] Không tìm thấy tài khoản '{target_token}'! Gõ 'acc list' để xem danh sách.")
            return True, active_target

    # 6b. Tự động kết nối lại (reconnect / autoreconnect)
    if cmd in ("reconnect", "autoreconnect", "rec"):
        if not args:
            rec_str = f"BẬT (Chờ {int(account_manager.reconnect_delay)}s)" if account_manager.auto_reconnect else "TẮT"
            print(f"[*] Chế độ Auto-Reconnect toàn cục: {rec_str}")
            print("    Cú pháp: reconnect on | reconnect off | reconnect delay <giây> | reconnect now [id]")
            return True, active_target

        sub = args[0].lower()
        if sub in ("on", "start", "enable", "1", "true"):
            account_manager.set_auto_reconnect(True)
            print(f"[*] Đã BẬT tự động kết nối lại khi mất mạng (giãn cách {int(account_manager.reconnect_delay)}s)!")
            return True, active_target

        elif sub in ("off", "stop", "disable", "0", "false"):
            account_manager.set_auto_reconnect(False)
            print("[*] Đã TẮT tự động kết nối lại khi mất mạng!")
            return True, active_target

        elif sub in ("delay", "time", "wait"):
            if len(args) > 1 and args[1].isdigit():
                sec = float(args[1])
                account_manager.set_auto_reconnect(account_manager.auto_reconnect, delay=sec)
                print(f"[*] Đã cài đặt thời gian chờ kết nối lại: {int(sec)} giây.")
            else:
                print(f"[*] Thời gian chờ kết nối lại hiện tại: {int(account_manager.reconnect_delay)}s. Cú pháp: reconnect delay <giây>")
            return True, active_target

        elif sub in ("now", "relogin"):
            target = args[1] if len(args) > 1 else active_target
            if target is None or str(target).lower() in ("all", "tatca", "*"):
                print("[*] Đang kết nối lại cho TOÀN BỘ tài khoản...")
                for a in account_manager.accounts:
                    account_manager.relogin_account(a)
            else:
                inst = account_manager.get_account(target)
                if inst:
                    print(f"[*] Đang kết nối lại cho tài khoản: {inst.tag}...")
                    account_manager.relogin_account(inst)
                else:
                    print(f"[!] Không tìm thấy tài khoản '{target}'.")
            return True, active_target

        # Nếu người dùng gõ: reconnect <id> (ví dụ reconnect 1)
        inst = account_manager.get_account(sub)
        if inst:
            print(f"[*] Đang kết nối lại cho tài khoản: {inst.tag}...")
            account_manager.relogin_account(inst)
            return True, active_target

    # 6c. Quản lý Telegram Bot & AI (tg / telegram)
    if cmd in ("telegram", "tg", "bot"):
        bot = getattr(account_manager, "telegram_bot", None)
        if not bot:
            print("[!] Telegram Bot hiện đang TẮT. Hãy kiểm tra cài đặt trong 'settings.json'.")
            return True, active_target

        if not args or args[0].lower() in ("status", "info"):
            st_str = "ĐANG CHẠY [ONLINE]" if bot._running else "ĐÃ DỪNG [OFFLINE]"
            ai_str = f"BẬT (model: {bot.ai_model})" if bot.ai_enabled else "TẮT"
            print(f"[*] TELEGRAM BOT: {st_str}")
            print(f"    - Bot username:    @nroPy_Bot")
            print(f"    - Người nhận active: {len(bot.active_chat_ids)} người")
            print(f"    - Trợ lý AI:       {ai_str}")
            last_ok = getattr(bot, "_last_poll_ok", 0) or 0
            last_err = getattr(bot, "_last_poll_error", "") or ""
            upd = getattr(bot, "_poll_updates", 0) or 0
            if last_ok:
                print(f"    - Polling nhận lệnh: OK (lần cuối {int(time.time() - last_ok)}s trước, đã xử lý {upd} tin)")
            else:
                print(f"    - Polling nhận lệnh: CHƯA NHẬN ĐƯỢC TIN NÀO (đã xử lý {upd} tin)")
            if last_err:
                print(f"    - Lỗi polling gần nhất: {last_err}")
            streak = getattr(bot, "_poll_fail_streak", 0) or 0
            hold = getattr(bot, "_poll_hold", 10) or 10
            mode = "short-poll (mạng NAT)" if streak >= 3 else f"long-poll ({hold}s)"
            print(f"    - Chế độ polling: {mode}")
            print(f"    - Cú pháp:         telegram send <nội dung> | telegram webhook | telegram delwebhook | telegram test")
            return True, active_target

        sub = args[0].lower()
        if sub in ("webhook", "wh"):
            info = bot._api_call("getWebhookInfo", {}, timeout=15) or {}
            res = info.get("result", {}) if info.get("ok") else {}
            url = res.get("url", "")
            print(f"[*] Webhook: {url if url else '(không bật — polling nhận lệnh bình thường)'}")
            if url:
                print("    [!] Webhook đang bật sẽ NUỐT tin nhắn, bot không trả lời lệnh!")
                print("    Gõ 'telegram delwebhook' để tắt.")
            return True, active_target

        if sub in ("delwebhook", "unhook", "nowebhook"):
            res = bot._api_call("deleteWebhook", {"drop_pending_updates": True}, timeout=15) or {}
            print(f"[*] Xóa webhook: {'OK' if res.get('ok') else res}")
            return True, active_target

        if sub in ("test", "nettest", "check", "diag"):
            _telegram_nettest(bot)
            return True, active_target

        if sub in ("notify", "thongbao", "tb"):
            if len(args) < 3:
                print(f"[*] Thông báo tự động: {account_manager.get_notify_status()}")
                print("    Cú pháp: telegram notify <boss|login|dis> <on|off>")
                return True, active_target
            kind = args[1].lower()
            val = args[2].lower()
            if val in ("on", "1", "enable", "true"):
                ok, msg = account_manager.set_notify_and_save(kind, True)
            elif val in ("off", "0", "disable", "false"):
                ok, msg = account_manager.set_notify_and_save(kind, False)
            else:
                print("    Cú pháp: telegram notify <boss|login|dis> <on|off>")
                return True, active_target
            print(f"[*] {msg}")
            return True, active_target

        if sub in ("send", "bc", "broadcast"):
            msg = " ".join(args[1:]) if len(args) > 1 else "Thông báo thử nghiệm từ ClientNROpy!"
            bot.broadcast_message(f"= [CONSOLE]: {msg}")
            print(f"[*] Đã phát sóng thông báo tới {len(bot.active_chat_ids)} người dùng Telegram.")
            return True, active_target

    # 7. Quản trị tài khoản: acc start / stop / relogin / add
    if cmd == "acc":
        if not args:
            print_accounts_table(account_manager)
            return True, active_target

        sub = args[0].lower()
        if sub in ("start", "connect", "login"):
            if len(args) > 1:
                target_str = args[1]
                if target_str.lower() == "all":
                    account_manager.start_all()
                else:
                    inst = account_manager.get_account(target_str)
                    if inst:
                        account_manager.start_account(inst)
                    else:
                        print(f"[!] Không tìm thấy tài khoản '{target_str}'.")
            else:
                account_manager.start_all()
            return True, active_target

        elif sub in ("stop", "disconnect", "logout"):
            if len(args) > 1:
                target_str = args[1]
                if target_str.lower() == "all":
                    account_manager.stop_all()
                else:
                    inst = account_manager.get_account(target_str)
                    if inst:
                        account_manager.stop_account(inst)
                    else:
                        print(f"[!] Không tìm thấy tài khoản '{target_str}'.")
            else:
                account_manager.stop_all()
            return True, active_target

        elif sub in ("relogin", "restart", "reconnect"):
            if len(args) > 1:
                inst = account_manager.get_account(args[1])
                if inst:
                    account_manager.relogin_account(inst)
            return True, active_target

        elif sub in ("add", "them", "+"):
            if len(args) >= 3:
                u = args[1]
                p = args[2]
                prx = args[3] if len(args) > 3 else None
                ok, msg, inst = account_manager.add_account_and_save(u, p, proxy=prx, start_now=True)
                print(f"[*] {msg}")
            else:
                print("Cú pháp: acc add <username> <password> [proxy]")
            return True, active_target

        elif sub in ("del", "remove", "rm", "xoa", "-"):
            if len(args) > 1:
                ok, msg = account_manager.remove_account_and_save(args[1])
                print(f"[*] {msg}")
            else:
                print("Cú pháp: acc del <username|id>")
            return True, active_target

        elif sub in ("edit", "update", "sua"):
            if len(args) >= 3:
                target_u = args[1]
                new_p = args[2]
                new_prx = args[3] if len(args) > 3 else None
                ok, msg = account_manager.edit_account_and_save(target_u, new_password=new_p, new_proxy=new_prx)
                print(f"[*] {msg}")
            else:
                print("Cú pháp: acc edit <username|id> <mật_khẩu_mới> [proxy_mới]")
            return True, active_target

        # Nếu là dạng: acc <id> <lệnh> (vd: acc 1 xmap 0)
        inst = account_manager.get_account(sub)
        if inst:
            if len(args) > 1:
                sub_cmd = " ".join(args[1:])
                if inst.client and inst.client.isConnected():
                    execute_client_command(inst.client, sub_cmd)
                else:
                    print(f"[!] Tài khoản {inst.tag} hiện chưa kết nối! Gõ 'acc start {inst.config.acc_id}' để khởi động.")
            else:
                print(f"[*] Đã chọn tài khoản: {inst.tag}")
                return True, inst.config.acc_id
            return True, active_target

    # 7b. Quản lý Proxy hệ thống (proxy / prx)
    if cmd in ("proxy", "proxies", "prx"):
        if not args or args[0].lower() in ("list", "ls", "status", "st"):
            st = "BẬT" if account_manager.proxy_pool.use_proxy else "TẮT"
            print(f"\n[*] CHẾ ĐỘ PROXY TOÀN CỤC: {st} (Tổng cộng: {len(account_manager.proxy_pool)} proxy trong pool)")
            if account_manager.proxy_pool.proxies:
                for i, p in enumerate(account_manager.proxy_pool.proxies):
                    print(f"    [{i+1}] {p.display_str} (Đang gán: {p.active_accounts_count} acc)")
            else:
                print("    (Pool chưa có proxy nào. Dùng 'proxy add <proxy>' để thêm)")
            print("    Cú pháp: proxy on | proxy off | proxy add <proxy> | proxy del <stt|proxy>\n")
            return True, active_target

        sub = args[0].lower()
        if sub in ("on", "enable", "1", "true"):
            account_manager.set_use_proxy_and_save(True)
            print("[*] Đã BẬT chế độ Proxy và lưu settings.json!")
            return True, active_target

        elif sub in ("off", "disable", "0", "false"):
            account_manager.set_use_proxy_and_save(False)
            print("[*] Đã TẮT chế độ Proxy và lưu settings.json!")
            return True, active_target

        elif sub in ("add", "them", "+"):
            if len(args) > 1:
                ok, msg = account_manager.add_proxy_and_save(args[1])
                print(f"[*] {msg}")
            else:
                print("Cú pháp: proxy add <socks5://user:pass@host:port | host:port:user:pass>")
            return True, active_target

        elif sub in ("del", "remove", "rm", "xoa", "-"):
            if len(args) > 1:
                ok, msg = account_manager.remove_proxy_and_save(args[1])
                print(f"[*] {msg}")
            else:
                print("Cú pháp: proxy del <stt | proxy>")
            return True, active_target

    # 7c. Đăng nhập / Đăng xuất trực tiếp
    if cmd in ("login", "dangnhap"):
        target_str = args[0] if args else (str(active_target) if active_target is not None else "all")
        if target_str.lower() in ("all", "tatca", "*"):
            account_manager.start_all()
        else:
            inst = account_manager.get_account(target_str)
            if inst:
                account_manager.start_account(inst)
            else:
                print(f"[!] Không tìm thấy tài khoản '{target_str}'.")
        return True, active_target

    if cmd in ("logout", "dangxuat"):
        target_str = args[0] if args else (str(active_target) if active_target is not None else "all")
        if target_str.lower() in ("all", "tatca", "*"):
            account_manager.stop_all()
        else:
            inst = account_manager.get_account(target_str)
            if inst:
                account_manager.stop_account(inst)
            else:
                print(f"[!] Không tìm thấy tài khoản '{target_str}'.")
        return True, active_target

    # 7d. Thu hoạch đậu thần & Đệ tử cho toàn bộ hoặc nhiều tài khoản
    if cmd in ("harvest", "dau", "caydau", "nhatdau"):
        connected_accs = [a for a in account_manager.accounts if a.client and a.client.isConnected()]
        if not connected_accs:
            print("[!] Không có tài khoản nào đang online để thu hoạch đậu.")
            return True, active_target
        for a in connected_accs:
            a.client.request_magic_tree(action=2)
        print(f"[*] Đã gửi yêu cầu thu hoạch đậu thần cho {len(connected_accs)} tài khoản.")
        return True, active_target

    if cmd in ("pet", "detu"):
        action_map = {
            "0": 0, "follow": 0, "dtheo": 0, "theo": 0,
            "1": 1, "protect": 1, "baove": 1, "bv": 1,
            "2": 2, "attack": 2, "tancong": 2, "tc": 2, "danh": 2,
            "3": 3, "home": 3, "venha": 3, "nha": 3,
            "4": 4, "fuse": 4, "hopthe": 4, "ht": 4,
            "5": 5, "porata": 5, "bongtai": 5,
        }
        if args and args[0].lower() in action_map:
            act_code = action_map[args[0].lower()]
            connected_accs = [a for a in account_manager.accounts if a.client and a.client.isConnected()]
            for a in connected_accs:
                a.client.change_pet_status(act_code)
            st_names = {0: "Đi theo", 1: "Bảo vệ", 2: "Tấn công", 3: "Về nhà", 4: "Hợp thể", 5: "Hợp thể Porata"}
            print(f"[*] Đã chuyển trạng thái đệ tử sang: {st_names.get(act_code)} cho {len(connected_accs)} tài khoản.")
            return True, active_target

    # 7e. Tra cứu vật phẩm toàn đội (item <id|tên> all hoặc khi không chọn acc nào)
    if cmd in ("item", "timitem", "checkitem") and (args and (args[-1].lower() in ("all", "tatca", "*") or active_target is None)):
        q_args = args[:-1] if (args and args[-1].lower() in ("all", "tatca", "*")) else args
        q = " ".join(q_args).lower().strip()
        if not q:
            print("Cú pháp: item <id|tên> [all]")
            return True, active_target
        is_num = q.isdigit()
        tid = int(q) if is_num else -1
        grand_total = 0
        sample_tid = None
        print(f"\n[*] TỔNG HỢP VẬT PHẨM TOÀN ĐỘI: '{q}'")
        if is_num:
            meta_h = format_item_details(tid)
            if meta_h:
                print(f"    - [Thông tin]: {meta_h}")
        for a in account_manager.accounts:
            if not a.client or not a.client.isConnected() or not a.client.myChar:
                print(f"    - {a.tag:<20}: (OFFLINE)")
                continue
            bag = a.client.myChar.arrItemBag
            matched = []
            for s_idx, it in enumerate(bag):
                it_name = get_item_name(it.template_id, it.info or "")
                if (is_num and it.template_id == tid) or (not is_num and (q in it_name.lower() or q in (it.info or "").lower())):
                    matched.append((s_idx, it, it_name))
            if matched:
                sub_tot = sum(it.quantity for _, it, _ in matched)
                grand_total += sub_tot
                sample_name = matched[0][2]
                sample_tid = matched[0][1].template_id
                slots_str = ", ".join([f"Ô {s+1:02d} (x{it.quantity})" for s, it, _ in matched])
                print(f"    - {a.tag:<20}: Có x{sub_tot} *{sample_name}* ({slots_str})")
            else:
                print(f"    - {a.tag:<20}: [Không có]")
        print(f"[*] TỔNG CỘNG TOÀN ĐỘI: x{grand_total:,} vật phẩm!")
        if grand_total > 0 and not is_num and sample_tid is not None:
            meta_f = format_item_details(sample_tid)
            if meta_f:
                print(f"    - [Thông tin]: {meta_f}")
        print()
        return True, active_target

    # 8. Thực thi lệnh trên TẤT CẢ các tài khoản (all <cmd>)
    if cmd == "all":
        if not args:
            print("Cú pháp: all <lệnh> (Ví dụ: all hunt on, all hs ngoc, all zone 3, all xmap 0)")
            return True, active_target

        sub_cmd = " ".join(args)
        connected_accs = [a for a in account_manager.accounts if a.client and a.client.isConnected()]
        if not connected_accs:
            print("[!] Hiện không có tài khoản nào đang Online để thực thi lệnh.")
            return True, active_target

        print(f"[*] Đang phát lệnh '{sub_cmd}' tới {len(connected_accs)} tài khoản...")
        for a in connected_accs:
            try:
                execute_client_command(a.client, sub_cmd)
            except Exception as ex:
                logger.error(f"Lỗi khi thực thi lệnh '{sub_cmd}': {ex}", account_tag=a.tag)
        return True, active_target

    # 9. Nếu đang chọn 1 tài khoản cụ thể (active_target != None)
    if active_target is not None:
        inst = account_manager.get_account(active_target)
        if inst and inst.client and inst.client.isConnected():
            execute_client_command(inst.client, line)
            return True, active_target
        elif inst:
            print(f"[!] Tài khoản {inst.tag} chưa kết nối online.")
            return True, active_target

    # 10. Nếu đang ở chế độ ALL (active_target is None) và gõ lệnh game trực tiếp
    # Tự động gửi tới tất cả các tài khoản online
    connected_accs = [a for a in account_manager.accounts if a.client and a.client.isConnected()]
    if connected_accs:
        for a in connected_accs:
            try:
                execute_client_command(a.client, line)
            except Exception as ex:
                logger.error(f"Lỗi khi thực thi '{line}': {ex}", account_tag=a.tag)
        return True, active_target
    else:
        matches = difflib.get_close_matches(cmd, ALL_KNOWN_COMMANDS, n=2, cutoff=0.55)
        if matches:
            suggestion_str = " hoặc ".join([f"'{m}'" for m in matches])
            print(f"Không rõ lệnh '{cmd}'. Có phải bạn muốn dùng: {suggestion_str}?")
            print("Gõ 'help' hoặc 'status' để xem danh sách lệnh.")
        else:
            print(f"Không rõ lệnh '{cmd}'. Gõ 'help' hoặc 'status' để xem trạng thái.")
        return True, active_target
