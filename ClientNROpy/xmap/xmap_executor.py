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

            # Đứng sát cổng (tele kiểu combat + chờ đồng bộ) rồi mới xin qua map
            try:
                client.teleport(cx, cy)
            except Exception:
                client.service.charMove(cx, cy)
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
            npc_id = map_next.info[0]
            # Cơ chế game: phải đứng gần NPC mới mở được menu
            if not XmapExecutor.teleport_near_npc(client, npc_id):
                return False
            # Mở menu NPC
            client.service.openMenu(npc_id)
            time.sleep(0.15)
            # Chọn các dòng tuỳ chọn liên tiếp
            for select in map_next.info[1:]:
                client.service.confirmMenu(npc_id, select)
                time.sleep(0.1)
            return True

        # 3. Chuyển map qua Bảng chọn map NPC (NpcPanel)
        elif next_type == TypeMapNext.NpcPanel:
            if len(map_next.info) < 3:
                return False
            npc_id = map_next.info[0]
            select_menu = map_next.info[1]
            select_panel = map_next.info[2]
            # Cơ chế game: phải đứng gần NPC mới mở được menu
            if not XmapExecutor.teleport_near_npc(client, npc_id):
                return False
            client.service.openMenu(npc_id)
            time.sleep(0.15)
            client.service.confirmMenu(npc_id, select_menu)
            time.sleep(0.1)
            client.service.requestMapSelect(select_panel)
            return True

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
    NPC_INTERACT_DISTANCE = 55

    @staticmethod
    def teleport_near_npc(client: "ClientNRO", npc_template_id: int) -> bool:
        """Tele tới sát NPC rồi mới cho mở menu (cơ chế game).

        Trả về True khi đã đứng trong tầm (hoặc không rõ tọa độ NPC thì
        vẫn cho thử kiểu cũ). False khi tele xong mà vẫn đứng xa -> Xmap
        retry thay vì spam gói menu bị server lờ.
        """
        try:
            my_char = client.myChar
            map_info = my_char.mapInfo
            find = getattr(map_info, "find_npc", None)
            npc = find(npc_template_id) if callable(find) else None
            if npc is None:
                return True
            dist = math.hypot(npc["x"] - my_char.cx, npc["y"] - my_char.cy)
            if dist <= XmapExecutor.NPC_INTERACT_DISTANCE:
                return True
            ok = client.teleport(int(npc["x"]) - 10, int(npc["y"]))
            time.sleep(0.5)
            my_char = client.myChar
            dist2 = math.hypot(npc["x"] - my_char.cx, npc["y"] - my_char.cy)
            if dist2 <= XmapExecutor.NPC_INTERACT_DISTANCE:
                return True
            print(f"[Xmap] NPC {npc_template_id} vẫn xa ({dist2:.0f}px) sau tele "
                  f"(gửi {'thành công' if ok else 'thất bại'}). Thử lại...")
            return False
        except Exception as ex:
            print(f"[Xmap] Lỗi tele tới NPC {npc_template_id}: {ex}")
            return True
