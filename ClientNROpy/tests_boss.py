# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động toàn diện cho tính năng Boss (Mod/Boss.cs) trong ClientNROpy.
Kiểm tra:
- Bóc tách thông báo Boss xuất hiện và bị tiêu diệt đa ngôn ngữ
- Quy tắc xác định MapId đặc biệt (Aru, Moori, Bojack, Ginyu Force)
- Tính toán thời gian sống
- Tự động cập nhật trạng thái sống/chết khi cùng map
- Tích hợp Xmap tự động chuyển map và đổi khu vực
- Tách bạch sạch sẽ giữa ChatVip và BossManager
"""

import unittest
import time
from unittest.mock import MagicMock

from ClientNROpy.boss import Boss
from ClientNROpy.boss_manager import BossManager
from ClientNROpy.chat_vip import ChatVip
from ClientNROpy.char import Char


class TestBossModule(unittest.TestCase):
    """Kiểm thử mô hình Boss, BossManager và cơ chế săn Boss."""

    def test_boss_model_properties_and_string(self):
        """Kiểm tra thuộc tính của Boss và định dạng chuỗi thời gian."""
        now = time.time()
        b = Boss(
            name="Broly",
            map_name="Đảo Kamê",
            map_id=5,
            zone_id=3,
            appear_time=now - 125,  # 2m 5s trước
        )
        self.assertEqual(b.name, "Broly")
        self.assertEqual(b.map_id, 5)
        self.assertEqual(b.zone_id, 3)
        self.assertFalse(b.is_died)
        self.assertGreaterEqual(b.time_alive_seconds, 125)

        time_str = b.time_alive_str()
        self.assertIn("2m", time_str)
        self.assertIn("s", time_str)

        # Chuỗi mô tả cơ bản
        s = b.to_string(use_color=False)
        self.assertIn("Broly", s)
        self.assertIn("Đảo Kamê [5]", s)
        self.assertIn("khu 3", s)

        # Khi Boss đã bị tiêu diệt
        b.is_died = True
        b.killer = "quangdeptrai"
        s_dead = b.to_string(use_color=False)
        self.assertIn("Bị quangdeptrai tiêu diệt", s_dead)

        # Dictionary export
        d = b.to_dict()
        self.assertEqual(d["name"], "Broly")
        self.assertEqual(d["killer"], "quangdeptrai")
        self.assertTrue(d["is_died"])

    def test_boss_spawn_parsing(self):
        """Kiểm tra bóc tách thông báo Boss xuất hiện từ ChatVip."""
        bm = BossManager()

        # 1. Tiếng Việt có khu vực
        msg1 = "BOSS Fide đại ca vừa xuất hiện tại Đảo Kamê khu vực 10"
        b1 = bm.handle_chat_vip(msg1)
        self.assertIsNotNone(b1)
        self.assertEqual(b1.name, "Fide đại ca")
        self.assertEqual(b1.map_name, "Đảo Kamê")
        self.assertEqual(b1.map_id, 5)
        self.assertEqual(b1.zone_id, 10)
        self.assertFalse(b1.is_died)

        # 2. Tiếng Việt không có khu vực
        msg2 = "BOSS Cell bọ hung vừa xuất hiện tại Rừng nấm"
        b2 = bm.handle_chat_vip(msg2)
        self.assertIsNotNone(b2)
        self.assertEqual(b2.name, "Cell bọ hung")
        self.assertEqual(b2.map_name, "Rừng nấm")
        self.assertEqual(b2.map_id, 3)
        self.assertEqual(b2.zone_id, -1)

        # 3. Tiếng Anh
        msg3 = "BOSS Cooler appear at Đồi hoa cúc zone 4"
        b3 = bm.handle_chat_vip(msg3)
        self.assertIsNotNone(b3)
        self.assertEqual(b3.name, "Cooler")
        self.assertEqual(b3.map_name, "Đồi hoa cúc")
        self.assertEqual(b3.map_id, 1)
        self.assertEqual(b3.zone_id, 4)

        # 4. Tiếng Indonesia
        msg4 = "BOSS Black Goku muncul di Thần điện zona 2"
        b4 = bm.handle_chat_vip(msg4)
        self.assertIsNotNone(b4)
        self.assertEqual(b4.name, "Black Goku")
        self.assertEqual(b4.map_name, "Thần điện")
        self.assertEqual(b4.map_id, 45)
        self.assertEqual(b4.zone_id, 2)

        # 5. Có dấu chấm than hiệu ứng pháo hoa (!BOSS ...)
        msg5 = "!BOSS Số 1 vừa xuất hiện tại Vực cấm khu vực 1"
        b5 = bm.handle_chat_vip(msg5)
        self.assertIsNotNone(b5)
        self.assertEqual(b5.name, "Số 1")
        self.assertEqual(b5.map_name, "Vực cấm")
        self.assertEqual(b5.map_id, 20)
        self.assertEqual(b5.zone_id, 1)

    def test_boss_killed_parsing(self):
        """Kiểm tra bóc tách thông báo Boss bị tiêu diệt và gắn người hạ gục."""
        bm = BossManager()

        # Cho boss xuất hiện trước
        bm.handle_chat_vip("BOSS Broly vừa xuất hiện tại Đảo Kamê khu vực 2")
        self.assertEqual(len(bm.get_alive_bosses()), 1)

        # Thông báo tiêu diệt
        kill_msg = "player1 : Đã tiêu diệt được BOSS Broly mọi người đều ngưỡng mộ."
        b_killed = bm.handle_chat_vip(kill_msg)

        self.assertIsNotNone(b_killed)
        self.assertEqual(b_killed.name, "Broly")
        self.assertTrue(b_killed.is_died)
        self.assertEqual(b_killed.killer, "player1")
        self.assertEqual(len(bm.get_alive_bosses()), 0)
        self.assertEqual(len(bm.get_all_bosses()), 1)

        # Thông báo tiêu diệt cho Boss chưa từng thấy xuất hiện (Boss xuất hiện trước khi kết nối)
        kill_msg2 = "hero99 : defeated BOSS Cooler everyone admired."
        b2 = bm.handle_chat_vip(kill_msg2)
        self.assertIsNotNone(b2)
        self.assertEqual(b2.name, "Cooler")
        self.assertTrue(b2.is_died)
        self.assertEqual(b2.killer, "hero99")

    def test_special_map_id_resolution(self):
        """Kiểm tra các quy tắc đặc biệt ánh xạ map ID theo chuẩn Mod/Boss.cs."""
        # 1. Vách núi Aru -> Map 42 (Vách núi đen)
        id_aru = BossManager.resolve_boss_map_id("Siêu Bọ Hung", "Vách núi Aru")
        self.assertEqual(id_aru, 42)

        # 2. Vách núi Moori -> Map 43 (Vách núi Namếc)
        id_moori = BossManager.resolve_boss_map_id("Siêu Bọ Hung", "Vách núi Moori")
        self.assertEqual(id_moori, 43)

        # 3. Trạm tàu vũ trụ - Tiểu đội sát thủ -> Map 25 (Namếc)
        id_ttvt_s1 = BossManager.resolve_boss_map_id("Số 1", "Trạm tàu vũ trụ")
        self.assertEqual(id_ttvt_s1, 25)

        id_ttvt_td = BossManager.resolve_boss_map_id("Tiểu đội trưởng", "Trạm tàu vũ trụ")
        self.assertEqual(id_ttvt_td, 25)

        # 4. Trạm tàu vũ trụ - Bojack team -> Map 24 (Trái Đất)
        id_ttvt_bojack = BossManager.resolve_boss_map_id("Bojack", "Trạm tàu vũ trụ")
        self.assertEqual(id_ttvt_bojack, 24)

        id_ttvt_zangya = BossManager.resolve_boss_map_id("Zangya", "Trạm tàu vũ trụ")
        self.assertEqual(id_ttvt_zangya, 24)

        # 5. Map thông thường
        id_cold = BossManager.resolve_boss_map_id("Fide", "Hành tinh Cold")
        self.assertEqual(id_cold, 109)

    def test_boss_status_update_on_map(self):
        """Kiểm tra cập nhật tự động khi người chơi vào cùng map/khu với Boss."""
        bm = BossManager()
        bm.handle_chat_vip("BOSS Broly vừa xuất hiện tại Đảo Kamê")  # Map 5, zone -1
        boss = bm.get_alive_bosses()[0]
        self.assertEqual(boss.zone_id, -1)

        # Giả lập người chơi ở map 5, khu 3 và thấy nhân vật 'Broly' trong map
        broly_char = Char()
        broly_char.cName = "Broly"
        broly_char.cHP = 1000000
        broly_char.isDie = False

        chars = {999: broly_char}
        bm.update_boss_status(current_map_id=5, current_zone_id=3, chars_in_map=chars)

        # Boss phải tự nhận diện được zone 3
        self.assertEqual(boss.zone_id, 3)
        self.assertFalse(boss.is_died)

        # Giả lập Broly bị đánh chết trong map (cHP == 0 hoặc isDie == True)
        broly_char.cHP = 0
        broly_char.isDie = True
        bm.update_boss_status(current_map_id=5, current_zone_id=3, chars_in_map=chars)
        self.assertTrue(boss.is_died)

    def test_boss_status_dead_when_missing_in_zone(self):
        """Nếu người chơi vào đúng khu của Boss mà không thấy Boss -> đánh dấu Boss đã chết."""
        bm = BossManager()
        bm.handle_chat_vip("BOSS Fide vừa xuất hiện tại Đảo Kamê khu vực 4")
        boss = bm.get_alive_bosses()[0]
        self.assertEqual(boss.zone_id, 4)

        # Người chơi vào map 5, khu 4 nhưng danh sách chars không có 'Fide'
        other_char = Char()
        other_char.cName = "Goku"
        chars = {123: other_char}

        bm.update_boss_status(current_map_id=5, current_zone_id=4, chars_in_map=chars)
        self.assertTrue(boss.is_died)

    def test_go_to_boss_auto_navigation(self):
        """Kiểm tra tích hợp tự động Xmap tới map Boss và đổi khu."""
        mock_client = MagicMock()
        mock_client.myChar.mapInfo.mapID = 0
        mock_client.myChar.mapInfo.zoneID = 1
        mock_client.xmap.return_value = True

        bm = BossManager(client=mock_client)
        bm.handle_chat_vip("BOSS Broly vừa xuất hiện tại Đảo Kamê khu vực 7")

        # 1. Gọi lệnh đến Boss theo tên
        ok, msg = bm.go_to_boss("Broly")
        self.assertTrue(ok)
        mock_client.xmap.assert_called_with(5)
        self.assertEqual(bm.pending_zone_id, 7)

        # 2. Giả lập khi đến nơi (Xmap finish) -> tự động đổi khu sang 7
        mock_client.myChar.mapInfo.mapID = 5
        mock_client.myChar.mapInfo.zoneID = 0
        bm._on_xmap_finished(success=True, message="Đến map")
        mock_client.change_zone.assert_called_with(7)

        # 3. Thử săn Boss đã chết
        b = bm.get_all_bosses()[0]
        b.is_died = True
        b.killer = "Vegeta"

        ok_dead, msg_dead = bm.go_to_boss("Broly")
        self.assertFalse(ok_dead)
        self.assertIn("bị Vegeta tiêu diệt", msg_dead)

    def test_clean_separation_chat_vip_and_boss_manager(self):
        """Kiểm tra phân tách sạch sẽ giữa ChatVip và BossManager."""
        # ChatVip chỉ là đối tượng gói tin
        cv_spawn = ChatVip.parse("BOSS Broly vừa xuất hiện tại Đảo Kamê khu vực 5")
        self.assertTrue(cv_spawn.is_boss)
        self.assertFalse(cv_spawn.is_killed)
        self.assertEqual(cv_spawn.boss_name, "Broly")
        self.assertEqual(cv_spawn.map_name, "Đảo Kamê")
        self.assertEqual(cv_spawn.map_id, 5)
        self.assertEqual(cv_spawn.zone_id, 5)

        # Tin nhắn người chơi bình thường
        cv_normal = ChatVip.parse("!Tuyển mem vào bang vui vẻ")
        self.assertFalse(cv_normal.is_boss)
        self.assertIsNone(cv_normal.boss)
        self.assertEqual(cv_normal.text, "Tuyển mem vào bang vui vẻ")


if __name__ == "__main__":
    unittest.main()
