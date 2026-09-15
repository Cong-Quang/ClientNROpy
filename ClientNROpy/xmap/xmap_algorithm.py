# -*- coding: utf-8 -*-
"""
Thuật toán tìm đường ngắn nhất cho Xmap,
mô phỏng XmapAlgorithm.cs trong Dragonboy C#.
"""

import heapq
from typing import Dict, List, Optional
from .xmap_objects import MapNext, TypeMapNext
from .xmap_data import XmapData


class XmapAlgorithm:
    """
    Hiện thực thuật toán Dijkstra tìm kiếm chuỗi bước chuyển map tối ưu.
    """

    @staticmethod
    def find_way(xmap_data: XmapData, map_start: int, map_end: int) -> Optional[List[MapNext]]:
        """
        Tìm chuỗi bước chuyển MapNext từ map_start đến map_end.
        Nếu map_start == map_end: trả về danh sách rỗng [].
        Nếu không có đường đi: trả về None.
        """
        if map_start == map_end:
            return []

        if not xmap_data or not xmap_data.is_loaded:
            raise ValueError("XmapData chưa được khởi tạo hoặc chưa nạp dữ liệu liên kết!")

        # Khoảng cách từ map_start tới các đỉnh
        dist: Dict[int, int] = {map_start: 0}
        # Lưu bước đi MapNext dẫn tới mỗi đỉnh
        prev: Dict[int, MapNext] = {}
        # Hàng đợi ưu tiên (khoảng cách, map_id)
        pq: List[tuple] = [(0, map_start)]
        visited = set()

        while pq:
            curr_dist, u = heapq.heappop(pq)

            if u in visited:
                continue
            visited.add(u)

            if u == map_end:
                break

            for next_step in xmap_data.links.get(u, []):
                v = next_step.to
                # Trọng số mặc định là 1 bước chuyển
                cost = 1
                # Nếu qua NPC 38 (Tương Lai / Trunks), phạt trọng số 100 để tránh đi vòng ngoài ý muốn
                if (next_step.type == TypeMapNext.NpcMenu
                        and next_step.info
                        and next_step.info[0] == 38):
                    cost = 100

                tentative = curr_dist + cost
                if tentative < dist.get(v, float("inf")):
                    dist[v] = tentative
                    prev[v] = next_step
                    heapq.heappush(pq, (tentative, v))

        # Kiểm tra xem có đến được map_end hay không
        if map_end not in prev:
            return None

        # Tái hiện lại lộ trình từ map_end ngược về map_start
        way: List[MapNext] = []
        curr = map_end
        while curr != map_start:
            step = prev.get(curr)
            if step is None:
                return None
            way.append(step)
            curr = step.map_start

        way.reverse()

        # Xác thực tính liên tục của lộ trình
        if way and way[0].map_start == map_start and way[-1].to == map_end:
            return way

        return None
