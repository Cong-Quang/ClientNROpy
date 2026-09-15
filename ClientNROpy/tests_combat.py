# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động toàn diện cho hệ thống Focus, Teleport, AK (Auto Attack)
và Tàn Sát (Slaughter / Auto Mob / Auto PK / Auto Pick Item) trong ClientNROpy.
"""

import unittest
from unittest.mock import MagicMock

from ClientNROpy.char import Char
from ClientNROpy.mob import Mob
from ClientNROpy.item_map import ItemMap
from ClientNROpy.waypoint import Waypoint
from ClientNROpy.service import Service
from ClientNROpy.combat_manager import CombatManager
from ClientNROpy.message import Message


class TestCombatModule(unittest.TestCase):
    """Kiểm thử Focus, Teleport, AK, Tàn Sát và các gói tin chiến đấu."""

    def setUp(self):
        Char.clearMyChar()
        self.char = Char.myCharz()
        self.char.charID = 1001
        self.char.cName = "Goku"
        self.char.cx = 100
        self.char.cy = 200
        self.char.cHP = 1000
        self.char.cHPFull = 1000
        self.char.cMP = 500
        self.char.cMPFull = 500

        self.mock_client = MagicMock()
        self.mock_client.myChar = self.char
        self.mock_client.service = MagicMock()

        self.combat = CombatManager(client=self.mock_client)

    def tearDown(self):
        self.combat._is_running = False

    def test_focus_system(self):
        """Kiểm tra nhắm mục tiêu (Focus) vào Mob, Char, Item và hủy focus."""
        # 1. Tạo dữ liệu giả lập trong map
        mob1 = Mob(mobId=1, templateId=0, hp=500, maxHp=500, x=150, y=200, status=5)
        mob2 = Mob(mobId=2, templateId=1, hp=800, maxHp=800, x=300, y=200, status=5)
        self.char.mapInfo.mobs = {1: mob1, 2: mob2}

        char2 = Char()
        char2.charID = 2002
        char2.cName = "Vegeta"
        char2.cx = 250
        char2.cy = 200
        char2.cHP = 1200
        char2.cHPFull = 1200
        self.char.mapInfo.chars = {2002: char2}

        item1 = ItemMap(itemMapID=10, itemTemplateID=77, x=120, y=200, playerID=1001)
        self.char.mapInfo.items = {10: item1}

        # 2. Focus mob gần nhất
        ok, msg = self.combat.focus("mob")
        self.assertTrue(ok)
        self.assertEqual(self.char.mobFocus, mob1)
        self.assertIsNone(self.char.charFocus)

        # 3. Focus mob theo ID
        ok, msg = self.combat.focus("mob", 2)
        self.assertTrue(ok)
        self.assertEqual(self.char.mobFocus, mob2)

        # 4. Focus người chơi
        ok, msg = self.combat.focus("char", "Vegeta")
        self.assertTrue(ok)
        self.assertEqual(self.char.charFocus, char2)
        self.assertIsNone(self.char.mobFocus)

        # 5. Focus vật phẩm
        ok, msg = self.combat.focus("item", 10)
        self.assertTrue(ok)
        self.assertEqual(self.char.itemFocus, item1)

        # 6. Hủy focus
        ok, msg = self.combat.focus("clear")
        self.assertTrue(ok)
        self.assertIsNone(self.char.mobFocus)
        self.assertIsNone(self.char.charFocus)
        self.assertIsNone(self.char.itemFocus)

    def test_teleport_system(self):
        """Kiểm tra dịch chuyển tức thời tới toạ độ và các thực thể trong game."""
        # 1. Teleport toạ độ (x, y)
        ok = self.combat.teleport(500, 350)
        self.assertTrue(ok)
        self.assertEqual(self.char.cx, 500)
        self.assertEqual(self.char.cy, 350)
        # Kiểm tra bước đệm charMove được gọi đúng
        self.assertGreaterEqual(self.mock_client.service.charMove.call_count, 1)

        # 2. Teleport tới Mob
        mob = Mob(mobId=5, templateId=2, hp=100, maxHp=100, x=800, y=400)
        ok, msg = self.combat.teleport_to(mob)
        self.assertTrue(ok)
        self.assertEqual(self.char.cx, 800)
        self.assertEqual(self.char.cy, 400)

        # 3. Teleport tới Waypoint
        wp = Waypoint(minX=1100, minY=300, maxX=1200, maxY=300, isEnter=True, isOffline=False, name="Qua Đông Karin")
        ok, msg = self.combat.teleport_to(wp)
        self.assertTrue(ok)
        self.assertEqual(self.char.cx, 1150)
        self.assertEqual(self.char.cy, 300)

    def test_auto_attack_ak(self):
        """Kiểm tra tính năng AK (tự động tấn công mục tiêu đang focus)."""
        # Focus quái
        mob = Mob(mobId=3, templateId=1, hp=500, maxHp=500, x=150, y=200, status=5)
        self.char.focus_mob(mob)
        self.combat.toggle_ak(True)
        self.assertTrue(self.combat.is_ak)

        # Chạy 1 chu kỳ AK
        self.combat._step_ak()
        self.mock_client.service.sendPlayerAttack.assert_called_with(vMob=[mob], vChar=[])

        # Khi quái chết (hp=0 hoặc status=0), AK phải tự động clear focus quái
        mob.hp = 0
        mob.status = 0
        self.combat._step_ak()
        self.assertIsNone(self.char.mobFocus)

    def test_tansat_all_mobs(self):
        """Kiểm tra tàn sát toàn bộ quái trong map."""
        mob1 = Mob(mobId=1, templateId=0, hp=500, maxHp=500, x=120, y=200, status=5)
        mob2 = Mob(mobId=2, templateId=0, hp=500, maxHp=500, x=400, y=200, status=5)
        self.char.mapInfo.mobs = {1: mob1, 2: mob2}

        self.combat.toggle_tansat(True, mode="mob")
        self.assertTrue(self.combat.is_tansat)

        # Chu kỳ 1: Quái gần nhất là mob1 (x=120 vs myChar x=100)
        self.combat._step_tansat()
        self.assertEqual(self.char.cx, 120)
        self.assertEqual(self.char.cy, 200)
        self.assertEqual(self.char.mobFocus, mob1)
        self.mock_client.service.sendPlayerAttack.assert_called_with(vMob=[mob1], vChar=[])

    def test_tansat_specific_mob_type(self):
        """Kiểm tra tàn sát cụ thể 1 loại quái theo template ID (addtm)."""
        mob_type0 = Mob(mobId=1, templateId=0, hp=500, maxHp=500, x=110, y=200, status=5)  # Mộc nhân (gần hơn)
        mob_type2 = Mob(mobId=2, templateId=2, hp=500, maxHp=500, x=300, y=200, status=5)  # Khủng long (xa hơn)
        self.char.mapInfo.mobs = {1: mob_type0, 2: mob_type2}

        # Chỉ định chỉ đánh loại quái 2
        self.combat.add_mob_type_target(2)
        self.assertEqual(self.combat.target_mob_types, {2})
        self.combat.toggle_tansat(True, mode="mob")

        self.combat._step_tansat()
        # Phải bỏ qua mob_type0 và đánh mob_type2
        self.assertEqual(self.char.mobFocus, mob_type2)
        self.assertEqual(self.char.cx, 300)

    def test_avoid_super_mob(self):
        """Kiểm tra né siêu quái (nsq) khi tàn sát."""
        normal_mob = Mob(mobId=1, templateId=0, hp=500, maxHp=500, x=300, y=200, status=5)
        super_mob = Mob(mobId=2, templateId=0, hp=50000, maxHp=500, x=110, y=200, status=5, isBoss=True)  # Siêu quái HP khủng
        self.char.mapInfo.mobs = {1: normal_mob, 2: super_mob}

        self.combat.avoid_super_mob = True
        self.combat.toggle_tansat(True, mode="mob")

        self.combat._step_tansat()
        # Phải né super_mob dù nó gần hơn, và chọn normal_mob
        self.assertEqual(self.char.mobFocus, normal_mob)

    def test_tansat_players_pk(self):
        """Kiểm tra tàn sát người chơi (Auto PK)."""
        enemy1 = Char()
        enemy1.charID = 9001
        enemy1.cName = "Yamcha"
        enemy1.cx = 220
        enemy1.cy = 200
        enemy1.cHP = 1000
        enemy1.cHPFull = 1000
        self.char.mapInfo.chars = {9001: enemy1}

        self.combat.toggle_tansat(True, mode="player")
        self.combat._step_tansat()

        self.assertEqual(self.char.charFocus, enemy1)
        self.assertEqual(self.char.cx, 220)
        self.mock_client.service.sendPlayerAttack.assert_called_with(vMob=[], vChar=[enemy1])

    def test_auto_pick_items_and_gem_filter(self):
        """Kiểm tra tự động nhặt đồ rơi trên đất và bộ lọc chỉ nhặt ngọc (cnn)."""
        trash_item = ItemMap(itemMapID=1, itemTemplateID=225, x=110, y=200, playerID=1001)  # Mảnh đá vụn (bị chặn)
        gem_item = ItemMap(itemMapID=2, itemTemplateID=77, x=250, y=200, playerID=1001)     # Ngọc xanh
        self.char.mapInfo.items = {1: trash_item, 2: gem_item}

        # Bật chỉ nhặt ngọc
        self.combat.auto_pick = True
        self.combat.pick_gem_only = True
        self.combat.toggle_tansat(True)

        self.combat._step_tansat()
        # Teleport tới ngọc và gửi lệnh pickItem
        self.assertEqual(self.char.cx, 250)
        self.mock_client.service.pickItem.assert_called_with(2)

    def test_auto_pean_and_revive(self):
        """Kiểm tra tự động dùng đậu thần khi HP thấp và hồi sinh khi chết."""
        # 1. HP thấp -> dùng đậu
        self.char.cHP = 100  # 10% < 20%
        self.char.magicTree.currPeas = 5
        self.combat.auto_pean = True
        self.combat.toggle_tansat(True)

        self.combat._step_tansat()
        self.mock_client.service.magicTree.assert_called_with(2)

        # 2. Chết (cHP = 0) -> hồi sinh về làng
        self.char.cHP = 0
        self.combat.auto_revive = True
        self.combat._step_tansat()
        self.mock_client.service.returnTownFromDead.assert_called()

    def test_service_combat_messages(self):
        """Kiểm tra cấu trúc Message trong Service: sendPlayerAttack, selectSkill, pickItem."""
        mock_session = MagicMock()
        service = Service()
        service.session = mock_session

        # 1. Đánh quái (cmd 54)
        mob = Mob(mobId=7, templateId=1, hp=500, maxHp=500, x=100, y=200)
        service.sendPlayerAttack(vMob=[mob], vChar=[])
        mock_session.sendMessage.assert_called()
        msg_sent = mock_session.sendMessage.call_args[0][0]
        self.assertEqual(msg_sent.command, 54)

        # 2. Đánh người chơi (cmd -60)
        target_char = Char()
        target_char.charID = 777
        service.sendPlayerAttack(vMob=[], vChar=[target_char])
        msg_sent_char = mock_session.sendMessage.call_args[0][0]
        self.assertEqual(msg_sent_char.command, -60)

        # 3. Chọn skill (cmd 34)
        service.selectSkill(17)  # Liên hoàn
        msg_skill = mock_session.sendMessage.call_args[0][0]
        self.assertEqual(msg_skill.command, 34)

        # 4. Nhặt đồ (cmd -20)
        service.pickItem(102)
        msg_pick = mock_session.sendMessage.call_args[0][0]
        self.assertEqual(msg_pick.command, -20)


if __name__ == "__main__":
    unittest.main()
