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
        """
        map_info = client.myChar.mapInfo
        target_name = get_map_name(target_map_id)
        target_norm = normalize_str(target_name)

        CUSTOM_WAYPOINT_NAMES = {
            20: "vach nui den",
            47: "rung karin",
        }
        if target_map_id in CUSTOM_WAYPOINT_NAMES:
            target_norm = CUSTOM_WAYPOINT_NAMES[target_map_id]

        for wp in map_info.waypoints:
            if normalize_str(wp.name) == target_norm:
                return wp

        for wp in map_info.waypoints:
            wp_norm = normalize_str(wp.name)
            if target_norm in wp_norm or wp_norm in target_norm:
                return wp

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

        if len(map_info.waypoints) == 1:
            return map_info.waypoints[0]

        try:
            names = [w.name for w in map_info.waypoints]
            from ..logger import logger
            tag = getattr(client, "account_id", "Client")
            logger.auto(f"[Xmap] Không tìm thấy cổng tới '{target_name}' (ID {target_map_id}). Cổng hiện có: {names}", account_tag=tag)
        except Exception:
            pass
        return None

    @staticmethod
    def TeleportMyChar(client: "ClientNRO", x: int, y: int) -> None:
        """Dịch chuyển tức thời đến tọa độ (x, y) bằng cách gửi charMove liên tiếp."""
        ch = client.myChar
        ch.currentMovePoint = None
        ch.cx = x
        ch.cy = y
        try:
            client.service.charMove(ch.cx, ch.cy)
            ch.cy = y + 1
            client.service.charMove(ch.cx, ch.cy)
            ch.cy = y
            client.service.charMove(ch.cx, ch.cy)
        except Exception as ex:
            from ..logger import logger
            tag = getattr(client, "account_id", "Client")
            logger.debug(f"[Xmap] TeleportMyChar exception: {ex}", account_tag=tag)

    @staticmethod
    def execute_next_map(client: "ClientNRO", map_next: MapNext) -> bool:
        """
        Thực hiện một bước chuyển map tiếp theo.
        Trả về True nếu gửi yêu cầu thành công, False nếu gặp lỗi.
        """
        next_type = map_next.type

        # 1. Chuyển map qua AutoWaypoint
        if next_type == TypeMapNext.AutoWaypoint:
            wp = XmapExecutor.find_waypoint_for_target(client, map_next.to)
            if wp is None:
                if map_next.map_start in (45, 46) and map_next.to in (46, 47):
                    XmapExecutor.TeleportMyChar(client, 576, 552)
                    client.service.requestChangeMap()
                    client.service.getMapOffline()
                    return True
                return False

            cx = wp.minX + (wp.maxX - wp.minX) // 2
            cy = wp.maxY
            if wp.maxX < 60: cx = 15
            elif wp.minX > 1500: cx = wp.minX + 15

            from ..logger import logger
            tag = getattr(client, "account_id", "Client")
            logger.auto(f"[Xmap] [AutoWaypoint] Dịch chuyển tới cổng ({cx}, {cy})...", account_tag=tag)
            XmapExecutor.TeleportMyChar(client, cx, cy)
            
            if wp.isOffline:
                client.service.getMapOffline()
            else:
                client.service.requestChangeMap()
            return True

        # 2. Chuyển map qua Menu NPC
        elif next_type == TypeMapNext.NpcMenu:
            if not map_next.info: return False
            npc_id = int(map_next.info[0])

            if npc_id == 38:
                curr_mid = client.myChar.mapInfo.mapID
                # NPC 38 chỉ di chuyển qua 3 map tại Trái Đất (27, 28, 29). Tại map 102 thì luôn cố định.
                if curr_mid in (27, 28, 29):
                    is_npc_found = any(npc.get("template_id") == 38 for npc in client.myChar.mapInfo.npcs)
                    if not is_npc_found:
                        import random
                        wp_target = 28 if curr_mid in (27, 29) else (27 if random.randint(27, 28) == 27 else 29)
                        wp = XmapExecutor.find_waypoint_for_target(client, wp_target)
                        if wp:
                            cx = wp.minX + (wp.maxX - wp.minX) // 2
                            if wp.maxX < 60: cx = 15
                            elif wp.minX > 1500: cx = wp.minX + 15
                            from ..logger import logger
                            tag = getattr(client, "account_id", "Client")
                            logger.auto(f"[Xmap] [NPC 38] Chưa thấy ở Map {curr_mid}. Tuần tra tìm sang Map {wp_target}...", account_tag=tag)
                            XmapExecutor.TeleportMyChar(client, cx, wp.maxY)
                            if wp.isOffline: client.service.getMapOffline()
                            else: client.service.requestChangeMap()
                        return True

            # Teleport to NPC first
            npc = None
            for n in client.myChar.mapInfo.npcs:
                if n.get("template_id") == npc_id:
                    npc = n
                    break
            if npc:
                XmapExecutor.TeleportMyChar(client, npc["x"] - 10, npc["y"])
                time.sleep(0.1)

            import threading
            menu_event = threading.Event()
            received_options = []
            
            def on_npc_menu(t_id, text, options):
                if t_id == npc_id:
                    received_options.clear()
                    received_options.extend(options)
                    menu_event.set()

            transport_event = threading.Event()
            transport_info = {}
            def on_trans(max_time, trans_type):
                transport_info["max_time"] = max_time
                transport_info["type"] = trans_type
                transport_event.set()

            if npc_id == 38:
                client.controller.on_transport_callbacks.append(on_trans)

            client.controller.on_npc_menu_callbacks.append(on_npc_menu)
            try:
                # Open menu
                menu_event.clear()
                client.service.openMenu(npc_id)
                
                # Chờ menu mở (chống lag/chống shuffle index)
                if menu_event.wait(timeout=2.5):
                    matched_idx = -1
                    
                    # 1. Khớp theo keyword từ dữ liệu (ví dụ: 'tương lai', 'quá khứ', 'namec', 'xayda', 'trái đất')
                    hint_keywords = [normalize_str(s) for s in map_next.info[1:] if isinstance(s, str) and not str(s).isdigit()]
                    for i, opt in enumerate(received_options):
                        opt_norm = normalize_str(opt)
                        if any(kw in opt_norm for kw in hint_keywords):
                            matched_idx = i
                            break
                            
                    # 2. Khớp theo tên map đích
                    if matched_idx == -1:
                        target_name = normalize_str(get_map_name(map_next.to))
                        for i, opt in enumerate(received_options):
                            opt_norm = normalize_str(opt)
                            if target_name in opt_norm or opt_norm in target_name:
                                matched_idx = i
                                break

                    # 3. Khớp theo từ khoá chung
                    if matched_idx == -1:
                        keywords = ["tàu vũ trụ", "trạm", "về nhà", "bay", "cold", "tương lai", "quá khứ"]
                        for i, opt in enumerate(received_options):
                            opt_norm = normalize_str(opt)
                            if any(kw in opt_norm for kw in keywords):
                                matched_idx = i
                                break

                    # 4. Fallback dùng index mặc định
                    for select in map_next.info[1:]:
                        if matched_idx != -1:
                            idx_to_send = matched_idx
                        else:
                            try:
                                idx_to_send = int(select)
                            except ValueError:
                                idx_to_send = 0  # Mặc định chọn ô đầu tiên nếu là chuỗi
                        client.service.confirmMenu(npc_id, idx_to_send)
                        time.sleep(0.2)
                else:
                    # Nếu timeout không nhận được menu, fallback click mù
                    for select in map_next.info[1:]:
                        try:
                            idx_to_send = int(select)
                        except ValueError:
                            idx_to_send = 0
                        client.service.confirmMenu(npc_id, idx_to_send)

                # Xử lý tăng tốc tàu thời gian (cmd -105) nếu là NPC 38
                if npc_id == 38:
                    if transport_event.wait(timeout=3.0):
                        is_speedup = getattr(client.xmap_controller, "is_auto_speedup", True)
                        from ..logger import logger
                        tag = getattr(client, "account_id", "Client")
                        if is_speedup:
                            logger.auto("[Xmap] [NPC 38] Đang bay tàu thời gian -> Kích hoạt tăng tốc (cmd -105, 1 ngọc)...", account_tag=tag)
                            time.sleep(0.1)
                            client.service.transportNow()
                        else:
                            max_t = transport_info.get("max_time", 60)
                            logger.auto(f"[Xmap] [NPC 38] Chờ tàu bay tự động (không tăng tốc, tối đa {max_t}s)...", account_tag=tag)
                return True
            finally:
                if on_npc_menu in client.controller.on_npc_menu_callbacks:
                    client.controller.on_npc_menu_callbacks.remove(on_npc_menu)
                if npc_id == 38 and on_trans in client.controller.on_transport_callbacks:
                    client.controller.on_transport_callbacks.remove(on_trans)

        # 3. Chuyển map qua NpcPanel
        elif next_type == TypeMapNext.NpcPanel:
            if len(map_next.info) < 3: return False
            idNpc = int(map_next.info[0])
            selectMenu = map_next.info[1]
            selectPanel = int(map_next.info[2])
            
            # Teleport to NPC first
            npc = None
            for n in client.myChar.mapInfo.npcs:
                if n.get("template_id") == idNpc:
                    npc = n
                    break
            if npc:
                XmapExecutor.TeleportMyChar(client, npc["x"] - 10, npc["y"])
                time.sleep(0.1)

            import threading
            menu_event = threading.Event()
            received_options = []
            
            def on_npc_menu(t_id, text, options):
                if t_id == idNpc:
                    received_options.clear()
                    received_options.extend(options)
                    menu_event.set()

            client.controller.on_npc_menu_callbacks.append(on_npc_menu)
            try:
                menu_event.clear()
                client.service.openMenu(idNpc)
                
                # Chờ menu mở để lấy đúng index (tương tự NpcMenu)
                if menu_event.wait(timeout=2.0):
                    matched_idx = -1
                    keywords = ["tàu vũ trụ", "về nhà", "đến", "trạm"]
                    for i, opt in enumerate(received_options):
                        if any(kw in normalize_str(opt) for kw in keywords):
                            matched_idx = i
                            break
                    if matched_idx != -1:
                        idx_to_send = matched_idx
                    else:
                        try:
                            idx_to_send = int(selectMenu)
                        except ValueError:
                            idx_to_send = 0
                    client.service.confirmMenu(idNpc, idx_to_send)
                else:
                    try:
                        idx_to_send = int(selectMenu)
                    except ValueError:
                        idx_to_send = 0
                    client.service.confirmMenu(idNpc, idx_to_send)
                    
                time.sleep(0.5)
                client.service.requestMapSelect(selectPanel)
                return True
            finally:
                if on_npc_menu in client.controller.on_npc_menu_callbacks:
                    client.controller.on_npc_menu_callbacks.remove(on_npc_menu)

        # 4. Chuyển map qua Capsule (khớp tên địa điểm động theo cmd -91)
        elif next_type == TypeMapNext.Capsule:
            capsule_tpl = map_next.info[0] if map_next.info else 194
            
            # Tìm vật phẩm capsule trong balo
            cap_item = None
            for it in client.myChar.arrItemBag:
                if it is not None and it.template_id == capsule_tpl:
                    cap_item = it
                    break
            
            # Nếu không tìm thấy đúng loại, thử tìm loại capsule khác (194 hoặc 193)
            if not cap_item:
                for it in client.myChar.arrItemBag:
                    if it is not None and it.template_id in (194, 193):
                        cap_item = it
                        break
            
            if not cap_item:
                from ..logger import logger
                tag = getattr(client, "account_id", "Client")
                logger.auto("[Xmap] [Capsule] Không tìm thấy Capsule trong hành trang!", account_tag=tag)
                return False

            import threading
            capsule_event = threading.Event()
            received_maps = []
            received_planets = []

            def on_capsule_list(maps, planets):
                received_maps.clear()
                received_maps.extend(maps)
                received_planets.clear()
                received_planets.extend(planets)
                capsule_event.set()

            client.controller.on_capsule_maps_callbacks.append(on_capsule_list)
            try:
                capsule_event.clear()
                # Sử dụng item theo index_ui trong balo
                client.service.useItem(0, 1, cap_item.index_ui, -1)

                if not capsule_event.wait(timeout=3.0):
                    from ..logger import logger
                    tag = getattr(client, "account_id", "Client")
                    logger.auto("[Xmap] [Capsule] Quá thời gian chờ phản hồi danh sách map (cmd -91) từ server!", account_tag=tag)
                    return False

                target_id = map_next.to
                cgender = client.myChar.cgender
                target_name = get_map_name(target_id)
                target_norm = normalize_str(target_name)

                matched_idx = -1

                # 1. Đích đến là Nhà của hành tinh (0: Gohan House - 21, 1: Moori House - 22, 2: Broly House - 23)
                if target_id in (21, 22, 23) or target_id == (21 + cgender):
                    house_kws = ["gohan house", "moori house", "broly house", "house", "nha", "ve nha"]
                    for i, opt in enumerate(received_maps):
                        opt_norm = normalize_str(opt)
                        if any(kw in opt_norm for kw in house_kws):
                            matched_idx = i
                            break
                    if matched_idx == -1 and len(received_maps) > 0:
                        matched_idx = 0  # Ô đầu tiên luôn là nhà của nhân vật

                # 2. Đích đến là Trạm tàu vũ trụ (24, 25, 26)
                elif target_id in (24, 25, 26) or target_id == (24 + cgender):
                    ttvt_kws = ["tram tau vu tru", "tram tau", "spaceship station", "station"]
                    for i, opt in enumerate(received_maps):
                        opt_norm = normalize_str(opt)
                        if any(kw in opt_norm for kw in ttvt_kws):
                            matched_idx = i
                            break

                # 3. Khớp tên bản đồ chính xác tuyệt đối (đã chuẩn hoá không dấu)
                if matched_idx == -1:
                    for i, opt in enumerate(received_maps):
                        if normalize_str(opt) == target_norm:
                            matched_idx = i
                            break

                # 4. Khớp qua resolve_map_id()
                if matched_idx == -1:
                    for i, opt in enumerate(received_maps):
                        if resolve_map_id(opt, cgender=cgender) == target_id:
                            matched_idx = i
                            break

                # 5. Khớp chuỗi con tương đồng (target_norm in opt_norm hoặc ngược lại)
                if matched_idx == -1:
                    for i, opt in enumerate(received_maps):
                        opt_norm = normalize_str(opt)
                        if target_norm in opt_norm or opt_norm in target_norm:
                            matched_idx = i
                            break

                if matched_idx == -1:
                    from ..logger import logger
                    tag = getattr(client, "account_id", "Client")
                    logger.auto(f"[Xmap] [Capsule] Không tìm thấy '{target_name}' (ID {target_id}) trong danh sách options của server! ({received_maps})", account_tag=tag)
                    return False

                selected_name = received_maps[matched_idx]
                from ..logger import logger
                tag = getattr(client, "account_id", "Client")
                logger.auto(f"[Xmap] [Capsule] Chọn ô [{matched_idx:02d}] '{selected_name}' -> '{target_name}' (ID {target_id})...", account_tag=tag)
                client.controller.map_capsule_return = client.myChar.mapInfo.mapID
                client.service.requestMapSelect(matched_idx)
                return True
            finally:
                if on_capsule_list in client.controller.on_capsule_maps_callbacks:
                    client.controller.on_capsule_maps_callbacks.remove(on_capsule_list)

        # 5. Chuyển map bằng toạ độ (Position)
        elif next_type == TypeMapNext.Position:
            if len(map_next.info) < 2: return False
            xPos = int(map_next.info[0])
            yPos = int(map_next.info[1])
            XmapExecutor.TeleportMyChar(client, xPos, yPos)
            client.service.requestChangeMap()
            client.service.getMapOffline()
            return True

        return False
