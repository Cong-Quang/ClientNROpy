# -*- coding: utf-8 -*-
"""
Bộ thực thi các bước chuyển map trong Xmap,
mô phỏng Pk9rXmap.cs và Utils.ChangeMap trong Dragonboy C#.
"""

import time
from typing import Optional, TYPE_CHECKING
from .xmap_objects import MapNext, TypeMapNext
from .map_data import get_map_name, normalize_str

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

        # 3. Nếu map chỉ có đúng 1 hoặc 2 cổng, có thể fallback nếu cần
        if len(map_info.waypoints) == 1:
            return map_info.waypoints[0]

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

            # Gửi gói tin di chuyển nhân vật tới tâm cổng
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
            select_panel = map_next.info[0]
            capsule_item_id = map_next.info[1] if len(map_next.info) > 1 else 194
            # Mở panel Capsule tương ứng
            client.service.useItem(0, 1, -1, capsule_item_id)
            time.sleep(0.2)
            # Chọn map đích từ panel (cmd -91)
            client.service.requestMapSelect(select_panel)
            return True

        return False
