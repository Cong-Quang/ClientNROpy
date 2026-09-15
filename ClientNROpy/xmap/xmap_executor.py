# -*- coding: utf-8 -*-
"""
Bộ thực thi các bước chuyển map trong Xmap,
mô phỏng Pk9rXmap.cs và Utils.ChangeMap trong Dragonboy C#.
"""

import math
import time
from typing import Optional, TYPE_CHECKING
from .xmap_objects import MapNext, TypeMapNext
from .map_data import get_map_name, normalize_str, resolve_map_id

if TYPE_CHECKING:
    from ..client import ClientNRO
    from ..waypoint import Waypoint


class XmapExecutor:
    """
    Điều khiển nhân vật gửi các gói tin tương tác tương ứng với từng bước MapNext.
    """

    @staticmethod
    def find_waypoint_for_target(client: "ClientNRO", target_map_id: int) -> Optional["Waypoint"]:
        """
        Tìm cổng dịch chuyển Waypoint trong bản đồ hiện tại dẫn tới target_map_id.
        Đối chiếu tên cổng (wp.name) với tên của target_map_id.
        """
        map_info = client.myChar.mapInfo
        target_name = get_map_name(target_map_id)
        target_norm = normalize_str(target_name)

        # 0. Hỗ trợ tên cổng đặc biệt của server lậu (tránh sai lệch so với MAP_NAMES chuẩn)
        CUSTOM_WAYPOINT_NAMES = {
            18: "rung thong xayda",
            35: "rung nguyen sinh",
            20: "vach nui den",
            17: "rung da",
            77: "thung lung den",
            47: "rung karin",
        }
        if target_map_id in CUSTOM_WAYPOINT_NAMES:
            target_norm = CUSTOM_WAYPOINT_NAMES[target_map_id]

        # 1. So khớp chính xác theo tên chuẩn hoá
        for wp in map_info.waypoints:
            wp_norm = normalize_str(wp.name)
            if wp_norm == target_norm:
                return wp

        # 2. So khớp chuỗi con (nhiều map có tiền tố / hậu tố như "Vực...", "Đồi...")
        for wp in map_info.waypoints:
            wp_norm = normalize_str(wp.name)
            if target_norm in wp_norm or wp_norm in target_norm:
                return wp

        # 3. So khớp rút gọn: bỏ tiền tố địa danh chung ở cả 2 phía
        # (vd cổng "Tháp Karin" ~ map "Chân tháp Karin")
        prefixes = ("chan ", "cong ", "loi ", "loi vao ", "duong toi ", "di ",
                    "tram ", "lang ", "thanh pho ", "dao ", "vach nui ", "vach ",
                    "thung lung ", "doi ", "rung ", "nui ", "hang ", "vuc ")

        def _strip(text: str) -> str:
            t = text
            for pre in prefixes:
                if t.startswith(pre):
                    t = t[len(pre):]
                    break
            return t

        stripped_target = _strip(target_norm)
        stripped_matches = []
        for wp in map_info.waypoints:
            wp_norm = normalize_str(wp.name)
            if _strip(wp_norm) == stripped_target and stripped_target:
                stripped_matches.append(wp)
        if len(stripped_matches) == 1:
            return stripped_matches[0]

        # 4. Nếu map chỉ có đúng 1 cổng, fallback
        if len(map_info.waypoints) == 1:
            return map_info.waypoints[0]

        # 5. Trượt: liệt kê cổng hiện có để chẩn đoán (tên cổng khác tên map?)
        try:
            names = [w.name for w in map_info.waypoints]
            print(f"[Xmap] Không tìm thấy cổng tới '{target_name}' (ID {target_map_id}). "
                  f"Cổng hiện có: {names}")
        except Exception:
            pass
        return None

    @staticmethod
    def execute_next_map(client: "ClientNRO", map_next: MapNext) -> bool:
        """
        Thực hiện một bước chuyển map tiếp theo.
        Trả về True nếu gửi yêu cầu thành công, False nếu gặp lỗi không tìm thấy cổng.
        """
        next_type = map_next.type

        # 1. Chuyển map qua AutoWaypoint
        if next_type == TypeMapNext.AutoWaypoint:
            wp = XmapExecutor.find_waypoint_for_target(client, map_next.to)
            if wp is None:
                # Trường hợp đặc biệt: Thần điện (45) -> Tháp Karin (46) hoặc 46 -> 47
                if map_next.map_start in (45, 46) and map_next.to in (46, 47):
                    client.service.charMove(576, 552)
                    client.service.requestChangeMap()
                    client.service.getMapOffline()
                    return True
                return False

            # Tính toạ độ tâm của cổng dịch chuyển
            cx = wp.minX + (wp.maxX - wp.minX) // 2
            cy = wp.maxY

            # Nếu cổng sát mép trái hoặc mép phải map
            if wp.maxX < 60:
                cx = 15
            elif wp.minX > 1500:  # Gần biên phải
                cx = wp.minX + 15

            dist = math.hypot(cx - client.myChar.cx, cy - client.myChar.cy)
            print(f"[Xmap] [AutoWaypoint] Cổng ở ({cx}, {cy}), myChar ở ({client.myChar.cx}, {client.myChar.cy}). Khoảng cách: {dist:.0f}px")
            if dist <= 20:
                print(f"[Xmap] [AutoWaypoint] Đã ở sát cổng (Cách {dist:.0f}px <= 20). Bỏ qua đi bộ.")
            else:
                print(f"[Xmap] Đi bộ tới cổng từ ({client.myChar.cx}, {client.myChar.cy}) đến ({cx}, {cy}) (Cách {dist:.0f}px)")
                
            steps = 0
            while dist > 20:
                dx = cx - client.myChar.cx
                dy = cy - client.myChar.cy
                step_x = 60 if dx > 60 else (-60 if dx < -60 else dx)
                step_y = 60 if dy > 60 else (-60 if dy < -60 else dy)
                client.myChar.cx += int(step_x)
                client.myChar.cy += int(step_y)
                try:
                    client.service.charMove(client.myChar.cx, client.myChar.cy)
                except Exception as ex:
                    print(f"[Xmap] charMove exception: {ex}")
                time.sleep(0.05)
                dist = math.hypot(cx - client.myChar.cx, cy - client.myChar.cy)
                steps += 1
                
            print(f"[Xmap] Đã đi {steps} bước tới cổng (Còn {dist:.0f}px). Gửi yêu cầu qua map...")
            time.sleep(0.1)

            # Gửi yêu cầu qua map
            if wp.isOffline:
                client.service.getMapOffline()
            else:
                client.service.requestChangeMap()
            return True

        # 2. Chuyển map qua Menu NPC
        elif next_type == TypeMapNext.NpcMenu:
            if not map_next.info:
                return False
            npc_id = int(map_next.info[0])
            # Cơ chế game: phải đứng gần NPC mới mở được menu
            if not XmapExecutor.teleport_near_npc(client, npc_id):
                return False
            
            import threading
            menu_event = threading.Event()
            received_options = []
            
            def on_npc_menu(t_id, text, options):
                if t_id == npc_id:
                    received_options.clear()
                    received_options.extend(options)
                    menu_event.set()

            client.controller.on_npc_menu_callbacks.append(on_npc_menu)
            try:
                # Mở menu NPC
                menu_event.clear()
                client.service.openMenu(npc_id)
                
                # Chọn các dòng tuỳ chọn liên tiếp
                for select in map_next.info[1:]:
                    if not menu_event.wait(timeout=3.0):
                        print(f"[Xmap] Timeout waiting for NPC {npc_id} menu")
                        return False
                    
                    actual_select = select
                    if isinstance(select, str):
                        matched_idx = -1
                        norm_select = normalize_str(select)
                        for i, opt in enumerate(received_options):
                            if norm_select in normalize_str(opt):
                                matched_idx = i
                                break
                        if matched_idx == -1:
                            print(f"[Xmap] Cannot find option '{select}' in NPC {npc_id} menu: {received_options}")
                            return False
                        actual_select = matched_idx
                        
                    menu_event.clear()
                    client.service.confirmMenu(npc_id, int(actual_select))
                return True
            finally:
                if on_npc_menu in client.controller.on_npc_menu_callbacks:
                    client.controller.on_npc_menu_callbacks.remove(on_npc_menu)

        # 3. Chuyển map qua Bảng chọn map NPC (NpcPanel)
        elif next_type == TypeMapNext.NpcPanel:
            if len(map_next.info) < 3:
                return False
            npc_id = int(map_next.info[0])
            select_menu = map_next.info[1]
            select_panel = map_next.info[2]
            
            import threading
            menu_event = threading.Event()
            received_options = []
            def on_npc_menu(t_id, text, options):
                if t_id == npc_id:
                    received_options.clear()
                    received_options.extend(options)
                    menu_event.set()

            panel_event = threading.Event()
            received_panel_maps = []
            def on_capsule_maps(map_names, planet_names):
                received_panel_maps.clear()
                received_panel_maps.extend(map_names)
                panel_event.set()

            # Cơ chế game: phải đứng gần NPC mới mở được menu
            if not XmapExecutor.teleport_near_npc(client, npc_id):
                return False
                
            client.controller.on_npc_menu_callbacks.append(on_npc_menu)
            client.controller.on_capsule_maps_callbacks.append(on_capsule_maps)
            try:
                # 1. Open Menu and find select_menu
                menu_event.clear()
                client.service.openMenu(npc_id)
                
                if not menu_event.wait(timeout=3.0):
                    print(f"[Xmap] Timeout waiting for NPC {npc_id} menu (NpcPanel)")
                    return False
                
                actual_select = select_menu
                if isinstance(select_menu, str):
                    matched_idx = -1
                    norm_select = normalize_str(select_menu)
                    for i, opt in enumerate(received_options):
                        if norm_select in normalize_str(opt):
                            matched_idx = i
                            break
                    if matched_idx == -1:
                        print(f"[Xmap] Cannot find option '{select_menu}' in NPC {npc_id} menu: {received_options}")
                        return False
                    actual_select = matched_idx
                
                # 2. Confirm Menu and wait for panel
                panel_event.clear()
                client.service.confirmMenu(npc_id, int(actual_select))
                
                if not panel_event.wait(timeout=3.0):
                    print(f"[Xmap] Timeout waiting for Panel maps (cmd -91) from NPC {npc_id}")
                    return False
                
                actual_panel = select_panel
                if isinstance(select_panel, str):
                    matched_idx = -1
                    norm_panel = normalize_str(select_panel)
                    for i, m_name in enumerate(received_panel_maps):
                        if norm_panel in normalize_str(m_name):
                            matched_idx = i
                            break
                    if matched_idx == -1:
                        print(f"[Xmap] Cannot find panel '{select_panel}' in capsule maps: {received_panel_maps}")
                        return False
                    actual_panel = matched_idx
                    
                client.service.requestMapSelect(int(actual_panel))
                return True
            finally:
                if on_npc_menu in client.controller.on_npc_menu_callbacks:
                    client.controller.on_npc_menu_callbacks.remove(on_npc_menu)
                if on_capsule_maps in client.controller.on_capsule_maps_callbacks:
                    client.controller.on_capsule_maps_callbacks.remove(on_capsule_maps)

        # 4. Nhảy toạ độ Position (Thần điện -> Tháp Karin, Tháp Karin -> Chân tháp)
        elif next_type == TypeMapNext.Position:
            if len(map_next.info) < 2:
                return False
            x_pos = map_next.info[0]
            y_pos = map_next.info[1]
            client.service.charMove(x_pos, y_pos)
            time.sleep(0.15)
            client.service.requestChangeMap()
            client.service.getMapOffline()
            return True

        # 5. Dùng Capsule (Đặc biệt hoặc Thường)
        elif next_type == TypeMapNext.Capsule:
            if not map_next.info:
                return False
            planned_select = map_next.info[0]
            capsule_item_id = map_next.info[1] if len(map_next.info) > 1 else 194
            controller = getattr(client, "controller", None)
            before = list(getattr(controller, "capsule_map_names", []) or []) if controller else []
            # Mở panel Capsule (server trả danh sách map thật qua cmd -91)
            client.service.useItem(0, 1, -1, capsule_item_id)
            # Chờ panel thật từ server (tối đa ~2.5s); bản C# đọc index từ
            # panel này nên không được dùng index kế hoạch nếu thứ tự khác.
            fresh = []
            for _ in range(25):
                time.sleep(0.1)
                cur = list(getattr(controller, "capsule_map_names", []) or []) if controller else []
                if cur and cur != before:
                    fresh = cur
                    break
                fresh = cur
            select_panel = planned_select
            if fresh:
                try:
                    cgender = client.myChar.cgender
                except Exception:
                    cgender = 0
                for idx, name in enumerate(fresh):
                    try:
                        if resolve_map_id(name, cgender=cgender) == map_next.to:
                            select_panel = idx
                            break
                    except Exception:
                        continue
            # Chọn map đích từ panel (cmd -91)
            try:
                print(f"[Capsule] Chot select={select_panel} cho map {map_next.to} "
                      f"(panel: {len(fresh)} muc, ke hoach: {planned_select})")
            except Exception:
                pass
            client.service.requestMapSelect(select_panel)
            return True

        return False

    # Khoảng cách tối đa để mở menu NPC (server check ~60px)
    # Khoảng cách tối đa để tương tác NPC (server check anti-cheat)
    NPC_INTERACT_DISTANCE = 20

    @staticmethod
    def teleport_near_npc(client: "ClientNRO", npc_template_id: int) -> bool:
        """Đi tới sát NPC rồi mới cho mở menu (cơ chế game).

        Chia nhỏ quãng đường (mỗi bước <= 60px) để server không coi là hack speed/teleport.
        """
        try:
            my_char = client.myChar
            map_info = my_char.mapInfo
            find = getattr(map_info, "find_npc", None)
            npc = find(npc_template_id) if callable(find) else None
            if npc is None:
                return True
                
            target_x = int(npc["x"]) - 10
            target_y = int(npc["y"])
            dist = math.hypot(target_x - my_char.cx, target_y - my_char.cy)
            
            print(f"[Xmap] [teleport_near_npc] NPC {npc_template_id} ở ({target_x}, {target_y}), myChar ở ({my_char.cx}, {my_char.cy}). Khoảng cách: {dist:.0f}px")
            
            if dist <= XmapExecutor.NPC_INTERACT_DISTANCE:
                print(f"[Xmap] [teleport_near_npc] Đã ở gần NPC {npc_template_id} (Cách {dist:.0f}px <= {XmapExecutor.NPC_INTERACT_DISTANCE}). Bỏ qua đi bộ.")
                return True
                
            print(f"[Xmap] Đi bộ tới NPC {npc_template_id} từ ({my_char.cx}, {my_char.cy}) đến ({target_x}, {target_y}) (Cách {dist:.0f}px)")
            
            # Đi bộ dần tới NPC (bước 60px)
            steps = 0
            while dist > XmapExecutor.NPC_INTERACT_DISTANCE:
                dx = target_x - my_char.cx
                dy = target_y - my_char.cy
                
                step_x = 60 if dx > 60 else (-60 if dx < -60 else dx)
                step_y = 60 if dy > 60 else (-60 if dy < -60 else dy)
                
                my_char.cx += int(step_x)
                my_char.cy += int(step_y)
                
                try:
                    client.service.charMove(my_char.cx, my_char.cy)
                except Exception as ex:
                    print(f"[Xmap] charMove exception: {ex}")
                    
                time.sleep(0.05)
                dist = math.hypot(target_x - my_char.cx, target_y - my_char.cy)
                steps += 1
                
            print(f"[Xmap] Đã đi {steps} bước tới sát NPC {npc_template_id} (Còn {dist:.0f}px). Gửi openMenu...")
                
            time.sleep(0.5)
            return True
        except Exception as ex:
            print(f"[Xmap] Lỗi tele tới NPC {npc_template_id}: {ex}")
            return True
