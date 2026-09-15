# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động toàn diện (Unit Tests) cho hệ thống Xmap trong ClientNROpy.
Kiểm tra đồ thị, thuật toán Dijkstra, phân giải tên và đường đi qua toàn bộ các map:
Nhà (21/22/23), Map ID 0, 6, 7, 19, 45, 82, 100, 109.
"""

import unittest
from ClientNROpy.xmap import (
    XmapData,
    XmapAlgorithm,
    XmapExecutor,
    XmapController,
    MapNext,
    TypeMapNext,
    MAP_NAMES,
    get_map_name,
    resolve_map_id,
    normalize_str,
)
from ClientNROpy.client import ClientNRO
from ClientNROpy.char import Char
from ClientNROpy.waypoint import Waypoint
from ClientNROpy.message import Message


class TestXmapSystem(unittest.TestCase):

    def setUp(self):
        Char.clearMyChar()
        self.xmap_data = XmapData()
        self.xmap_data.load(cgender=0, task_id=40)

    # --------------------------------------------------------------------------
    # 1. KIỂM TRA NẠP DỮ LIỆU ĐỒ THỊ & LIÊN KẾT ĐỘNG
    # --------------------------------------------------------------------------
    def test_graph_loading_and_dynamic_links(self):
        """Xác minh đồ thị được nạp đầy đủ và chính xác từ AutoLinkMapsWaypoint và LinkMapsXmap."""
        self.assertTrue(self.xmap_data.is_loaded)
        self.assertGreater(len(self.xmap_data.links), 50)

        # 1. Kiểm tra liên kết AutoWaypoint nội hành tinh Trái Đất (42 0 1 2 3 4 5 6)
        earth_0_to = [step.to for step in self.xmap_data.links[0]]
        self.assertIn(1, earth_0_to)
        self.assertIn(42, earth_0_to)

        # 2. Kiểm tra liên kết Trạm tàu vũ trụ qua lại giữa các hành tinh (LinkMapsXmap)
        td_ttvt_to = [step.to for step in self.xmap_data.links[24]]
        self.assertIn(25, td_ttvt_to)  # Sang Namếc
        self.assertIn(26, td_ttvt_to)  # Sang Xayda
        self.assertIn(84, td_ttvt_to)  # Sang Siêu thị

        # 3. Kiểm tra liên kết động Nhà <-> Làng theo cgender
        # Trái Đất (cgender=0): Nhà 21 <-> Làng 0
        data_earth = XmapData()
        data_earth.load(cgender=0)
        self.assertIn(0, [s.to for s in data_earth.links[21]])
        self.assertIn(21, [s.to for s in data_earth.links[0]])

        # Namếc (cgender=1): Nhà 22 <-> Làng 7
        data_namec = XmapData()
        data_namec.load(cgender=1)
        self.assertIn(7, [s.to for s in data_namec.links[22]])
        self.assertIn(22, [s.to for s in data_namec.links[7]])

        # Xayda (cgender=2): Nhà 23 <-> Làng 14
        data_xayda = XmapData()
        data_xayda.load(cgender=2)
        self.assertIn(14, [s.to for s in data_xayda.links[23]])
        self.assertIn(23, [s.to for s in data_xayda.links[14]])

        # 4. Kiểm tra nhảy toạ độ Position: Thần điện (45) -> Tháp Karin (46) -> Chân tháp (47)
        steps_45 = [s for s in self.xmap_data.links[45] if s.to == 46]
        self.assertTrue(len(steps_45) > 0)
        self.assertEqual(steps_45[0].type, TypeMapNext.Position)
        self.assertEqual(steps_45[0].info, [576, 552])

        steps_46 = [s for s in self.xmap_data.links[46] if s.to == 47]
        self.assertTrue(len(steps_46) > 0)
        self.assertEqual(steps_46[0].type, TypeMapNext.Position)

    # --------------------------------------------------------------------------
    # 2. KIỂM TRA PHÂN GIẢI MAP ID VÀ ALIAS TỪ DÒNG LỆNH
    # --------------------------------------------------------------------------
    def test_map_target_resolver(self):
        """Xác minh bộ phân giải chuỗi lệnh người dùng nhập vào."""
        # Số ID trực tiếp
        self.assertEqual(resolve_map_id(0), 0)
        self.assertEqual(resolve_map_id("6"), 6)
        self.assertEqual(resolve_map_id("7"), 7)
        self.assertEqual(resolve_map_id("19"), 19)
        self.assertEqual(resolve_map_id("45"), 45)
        self.assertEqual(resolve_map_id("82"), 82)
        self.assertEqual(resolve_map_id("100"), 100)
        self.assertEqual(resolve_map_id("109"), 109)

        # Alias Nhà theo cgender
        self.assertEqual(resolve_map_id("nha", cgender=0), 21)   # Trái Đất
        self.assertEqual(resolve_map_id("home", cgender=1), 22)  # Namếc
        self.assertEqual(resolve_map_id("ve nha", cgender=2), 23)# Xayda

        # Alias Làng theo cgender
        self.assertEqual(resolve_map_id("lang", cgender=0), 0)
        self.assertEqual(resolve_map_id("lang", cgender=1), 7)
        self.assertEqual(resolve_map_id("lang", cgender=2), 14)

        # Tên tiếng Việt có dấu / không dấu
        self.assertEqual(resolve_map_id("Làng Aru"), 0)
        self.assertEqual(resolve_map_id("lang aru"), 0)
        self.assertEqual(resolve_map_id("đông karin"), 6)
        self.assertEqual(resolve_map_id("dong karin"), 6)
        self.assertEqual(resolve_map_id("làng mori"), 7)
        self.assertEqual(resolve_map_id("thành phố vegeta"), 19)
        self.assertEqual(resolve_map_id("thần điện"), 45)
        self.assertEqual(resolve_map_id("núi khỉ đen"), 82)
        self.assertEqual(resolve_map_id("thành phố phía bắc"), 100)
        self.assertEqual(resolve_map_id("cold"), 109)

    # --------------------------------------------------------------------------
    # 3. KIỂM TRA TÌM ĐƯỜNG DIJKSTRA QUA TẤT CẢ CÁC MAP YÊU CẦU
    # --------------------------------------------------------------------------
    def test_path_nha_to_lang_aru(self):
        """1. Kiểm tra tìm đường: Nhà Gohan (21) -> Làng Aru (0)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 21, 0)
        self.assertIsNotNone(way)
        self.assertEqual(len(way), 1)
        self.assertEqual(way[0].map_start, 21)
        self.assertEqual(way[0].to, 0)

    def test_path_0_to_6(self):
        """2. Kiểm tra tìm đường: Làng Aru (0) -> Đông Karin (6)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 0, 6)
        self.assertIsNotNone(way)
        self.assertEqual(way[0].map_start, 0)
        self.assertEqual(way[-1].to, 6)
        hops = [step.to for step in way]
        self.assertEqual(hops, [1, 2, 3, 4, 5, 6])

    def test_path_6_to_7(self):
        """3. Kiểm tra tìm đường liên hành tinh: Đông Karin (6 - Trái Đất) -> Làng Mori (7 - Namec)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 6, 7)
        self.assertIsNotNone(way)
        self.assertEqual(way[0].map_start, 6)
        self.assertEqual(way[-1].to, 7)
        hops = [step.to for step in way]
        # Bắt buộc phải đi qua Trạm tàu vũ trụ Trái Đất (24) và Trạm tàu Namếc (25)
        self.assertIn(24, hops)
        self.assertIn(25, hops)

        # Kiểm tra bước chuyển giữa 24 và 25 là NpcMenu
        step_cross = [s for s in way if s.map_start == 24 and s.to == 25][0]
        self.assertEqual(step_cross.type, TypeMapNext.NpcMenu)
        self.assertEqual(step_cross.info, [10, 0])

    def test_path_7_to_19(self):
        """4. Kiểm tra tìm đường liên hành tinh: Làng Mori (7 - Namec) -> Thành phố Vegeta (19 - Xayda)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 7, 19)
        self.assertIsNotNone(way)
        self.assertEqual(way[0].map_start, 7)
        self.assertEqual(way[-1].to, 19)
        hops = [step.to for step in way]
        # Bắt buộc phải đi qua Trạm tàu Namếc (25) và Trạm tàu Xayda (26)
        self.assertIn(25, hops)
        self.assertIn(26, hops)

    def test_path_19_to_45(self):
        """5. Kiểm tra tìm đường: Thành phố Vegeta (19 - Xayda) -> Thần điện (45 - Trái Đất)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 19, 45)
        self.assertIsNotNone(way)
        self.assertEqual(way[0].map_start, 19)
        self.assertEqual(way[-1].to, 45)
        hops = [step.to for step in way]
        # Đi qua Trạm tàu Xayda 26 -> Trạm tàu TĐ 24 -> Chân tháp 47 -> Tháp Karin 46 -> Thần điện 45
        self.assertIn(26, hops)
        self.assertIn(24, hops)
        self.assertIn(47, hops)
        self.assertIn(46, hops)
        self.assertIn(45, hops)

    def test_path_45_to_82(self):
        """6. Kiểm tra tìm đường: Thần điện (45 - Trái Đất) -> Núi Khỉ Đen (82 - Nappa)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 45, 82)
        self.assertIsNotNone(way)
        self.assertEqual(way[0].map_start, 45)
        self.assertEqual(way[-1].to, 82)
        hops = [step.to for step in way]
        # Đi từ 45 -> 46 -> 47 bằng Position, sau đó qua TPVGT (19) -> Nappa (68) -> ... -> 82
        self.assertIn(46, hops)
        self.assertIn(47, hops)
        self.assertIn(19, hops)
        # Đường đi tối ưu từ 19 đến 82 có thể qua Cold (109->105->80) hoặc qua Nappa (68)
        self.assertTrue(68 in hops or 109 in hops)
        self.assertEqual(way[-1].to, 82)

    def test_path_82_to_100(self):
        """7. Kiểm tra tìm đường: Núi Khỉ Đen (82 - Nappa) -> Thành phố phía Bắc (100 - Tương Lai)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 82, 100)
        self.assertIsNotNone(way)
        self.assertEqual(way[0].map_start, 82)
        self.assertEqual(way[-1].to, 100)
        hops = [step.to for step in way]
        # Từ Nappa về TPVGT 19 -> Trái Đất -> Rừng Bamboo 27 -> Nhà Trunks 102 -> ... -> 100
        self.assertIn(68, hops)
        self.assertIn(19, hops)
        self.assertIn(27, hops)
        self.assertIn(102, hops)
        self.assertIn(100, hops)

    def test_path_100_to_109(self):
        """8. Kiểm tra tìm đường: Thành phố phía Bắc (100 - Tương Lai) -> Rừng Băng (109 - Cold)."""
        way = XmapAlgorithm.find_way(self.xmap_data, 100, 109)
        self.assertIsNotNone(way)
        self.assertEqual(way[0].map_start, 100)
        self.assertEqual(way[-1].to, 109)
        hops = [step.to for step in way]
        self.assertIn(109, hops)

    def test_pairwise_connectivity_all_targets(self):
        """9. Kiểm tra tính liên thông hai chiều giữa toàn bộ các cặp map yêu cầu."""
        target_maps = [21, 0, 6, 7, 19, 45, 82, 100, 109]
        for src in target_maps:
            for dst in target_maps:
                if src == dst:
                    continue
                way = XmapAlgorithm.find_way(self.xmap_data, src, dst)
                self.assertIsNotNone(
                    way,
                    f"Thất bại khi tìm đường từ Map {src} ({get_map_name(src)}) tới Map {dst} ({get_map_name(dst)})!"
                )
                self.assertEqual(way[0].map_start, src)
                self.assertEqual(way[-1].to, dst)
                # Kiểm tra tính liên tục của chuỗi các chặng
                for i in range(len(way) - 1):
                    self.assertEqual(
                        way[i].to,
                        way[i + 1].map_start,
                        f"Đứt gãy chuỗi liên kết tại chặng {i}: {way[i]} -> {way[i+1]}"
                    )

    # --------------------------------------------------------------------------
    # 4. KIỂM TRA BỘ THỰC THI (XMAP EXECUTOR) & ĐIỀU KHIỂN (CONTROLLER)
    # --------------------------------------------------------------------------
    def test_executor_waypoint_selection(self):
        """Kiểm tra Executor tìm đúng Waypoint theo tên map đích."""
        client = ClientNRO()
        # Giả lập map hiện tại là Làng Aru (0) với 2 cổng: Vách núi đen (42) và Đồi hoa cúc (1)
        client.myChar.mapInfo.mapID = 0
        client.myChar.mapInfo.mapName = "Làng Aru"
        wp1 = Waypoint(minX=1450, minY=384, maxX=1500, maxY=384, isEnter=True, isOffline=False, name="Đồi hoa cúc")
        wp2 = Waypoint(minX=10, minY=384, maxX=50, maxY=384, isEnter=True, isOffline=False, name="Vách núi đen")
        client.myChar.mapInfo.waypoints = [wp1, wp2]

        found_wp = XmapExecutor.find_waypoint_for_target(client, 1)
        self.assertIsNotNone(found_wp)
        self.assertEqual(found_wp.name, "Đồi hoa cúc")

        found_wp_42 = XmapExecutor.find_waypoint_for_target(client, 42)
        self.assertIsNotNone(found_wp_42)
        self.assertEqual(found_wp_42.name, "Vách núi đen")

    def test_controller_state_simulation(self):
        """Kiểm tra Controller lập lộ trình và hoàn tất khi đến đích."""
        client = ClientNRO()
        client.myChar.mapInfo.mapID = 0
        controller = XmapController(client)

        # Lập đường đi 0 -> 6
        path = controller.find_path(0, 6)
        self.assertIsNotNone(path)
        self.assertEqual(len(path), 6)

        # Kiểm tra start và status
        controller.start(6)
        status = controller.get_status()
        self.assertTrue(status["is_acting"])
        self.assertEqual(status["target_map_id"], 6)

        # Dừng xmap
        controller.stop()
        self.assertFalse(controller.is_acting)

    def test_capsule_vip_detection_and_pathfinding(self):
        """Kiểm tra nhận diện Capsule Đặc Biệt (194) và tối ưu lộ trình bay thẳng 1 chặng."""
        from ClientNROpy.item import Item
        client = ClientNRO()
        client.myChar.mapInfo.mapID = 0
        controller = XmapController(client)

        # Ban đầu không có Capsule trong Balo
        self.assertFalse(controller.has_item_capsule_vip())
        self.assertFalse(controller.can_use_capsule_vip())

        # Thêm Capsule Đặc Biệt (ID 194) vào Balo
        capsule_vip = Item(template_id=194, quantity=1, info="Capsule Đặc Biệt")
        client.myChar.arrItemBag.append(capsule_vip)

        self.assertTrue(controller.has_item_capsule_vip())
        self.assertTrue(controller.can_use_capsule_vip())

        # Tra cứu đường từ Làng Aru (0 - Trái Đất) sang Thành phố Vegeta (19 - Xayda):
        # Có Capsule Đặc Biệt: bay trực tiếp tới 19 chỉ trong đúng 1 chặng!
        path_with_capsule = controller.find_path(0, 19, use_capsule=True)
        self.assertIsNotNone(path_with_capsule)
        self.assertEqual(len(path_with_capsule), 1)
        self.assertEqual(path_with_capsule[0].type, TypeMapNext.Capsule)
        self.assertEqual(path_with_capsule[0].to, 19)

        # Tắt sử dụng Capsule Đặc Biệt
        controller.toggle_use_capsule_vip()
        self.assertFalse(controller.can_use_capsule_vip())

        # Đường đi trở về lộ trình thông thường (> 1 chặng)
        path_without_capsule = controller.find_path(0, 19, use_capsule=True)
        self.assertGreater(len(path_without_capsule), 1)


if __name__ == "__main__":
    unittest.main()
