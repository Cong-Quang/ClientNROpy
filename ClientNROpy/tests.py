# -*- coding: utf-8 -*-
"""
Bộ kiểm thử tự động (Unit Tests) cho ClientNROpy.
"""

import unittest
from ClientNROpy.reader import myReader
from ClientNROpy.writer import myWriter
from ClientNROpy.message import Message
from ClientNROpy.session import Session_ME
from ClientNROpy.controller import Controller
from ClientNROpy.service import Service
from ClientNROpy.player_data import PlayerData
from ClientNROpy.char import Char
from ClientNROpy.pet import Pet
from ClientNROpy.magic_tree import MagicTree
from ClientNROpy.item import Item
from ClientNROpy.item_option import ItemOption
from ClientNROpy.zone_info import ZoneInfo
from ClientNROpy.map_info import MapInfo
from ClientNROpy.chat_vip import ChatVip


class TestClientNROpy(unittest.TestCase):
    def test_reader_writer_primitives(self):
        """Kiểm tra tính đối xứng của bộ đọc/ghi nhị phân myWriter và myReader."""
        w = myWriter()
        w.writeSByte(-128)
        w.writeSByte(127)
        w.writeByte(255)
        w.writeUnsignedByte(199)
        w.writeShort(-32768)
        w.writeShort(32767)
        w.writeUnsignedShort(65535)
        w.writeInt(-2147483648)
        w.writeInt(2147483647)
        w.writeLong(-9223372036854775808)
        w.writeLong(9223372036854775807)
        w.writeBoolean(True)
        w.writeBoolean(False)
        w.writeUTF("Ngọc Rồng Online - Headless Client")

        data = w.getData()
        self.assertIsNotNone(data)

        r = myReader(data)
        self.assertEqual(r.readSByte(), -128)
        self.assertEqual(r.readSByte(), 127)
        self.assertEqual(r.readSByte(), -1)
        self.assertEqual(r.readUnsignedByte(), 199)
        self.assertEqual(r.readShort(), -32768)
        self.assertEqual(r.readShort(), 32767)
        self.assertEqual(r.readUnsignedShort(), 65535)
        self.assertEqual(r.readInt(), -2147483648)
        self.assertEqual(r.readInt(), 2147483647)
        self.assertEqual(r.readLong(), -9223372036854775808)
        self.assertEqual(r.readLong(), 9223372036854775807)
        self.assertTrue(r.readBoolean())
        self.assertFalse(r.readBoolean())
        self.assertEqual(r.readUTF(), "Ngọc Rồng Online - Headless Client")
        self.assertEqual(r.available(), 0)

    def test_xor_cipher_symmetry(self):
        """Kiểm tra cơ chế mã hoá / giải mã XOR động theo khóa."""
        session = Session_ME()
        test_key = bytearray([12, 55, 99, 178, 240, 31, 88])
        session.key = test_key
        session.getKeyComplete = True
        session.curR = 0
        session.curW = 0

        raw_stream = [-120, 45, 0, 78, -32, 11, 90, -1, 100]
        # Client gửi lên -> mã hoá qua writeKey
        encrypted = [session.writeKey(b) for b in raw_stream]

        # Server nhận được hoặc Client nhận về -> giải mã qua readKey
        session.curR = 0
        decrypted = [session.readKey(b) for b in encrypted]

        self.assertEqual(raw_stream, decrypted)

    def test_message_encapsulation(self):
        """Kiểm tra đóng gói và phân tích gói tin Message."""
        msg = Message(-29)
        msg.writer().writeByte(2)
        msg.writer().writeUTF("Pc platform xxx|2.4.0")
        raw = msg.getData()

        msg_received = Message(-29, raw)
        self.assertEqual(msg_received.command, -29)
        self.assertEqual(msg_received.reader().readByte(), 2)
        self.assertEqual(msg_received.reader().readUTF(), "Pc platform xxx|2.4.0")

    def test_resource_skipping(self):
        """Kiểm tra Controller bỏ qua các gói tin tải tài nguyên (-74, 66, -87, v.v.)."""
        ctrl = Controller.gI()

        # Tạo gói tin -74 tải tài nguyên
        m74 = Message(-74)
        m74.writer().writeByte(0)  # server yêu cầu check version
        m74.writer().writeInt(12345)
        raw74 = m74.getData()

        msg74 = Message(-74, raw74)
        # onMessage không ném ngoại lệ và bỏ qua an toàn
        ctrl.onMessage(msg74)

        # Tạo gói tin hình ảnh 66
        m66 = Message(66)
        m66.writer().writeUTF("bg_img_dummy")
        msg66 = Message(66, m66.getData())
        ctrl.onMessage(msg66)

    def test_read_login(self):
        """Kiểm tra phân tích phản hồi đăng nhập thành công (cmd 0)."""
        ctrl = Controller.gI()
        login_result = []
        ctrl.on_login_ok_callbacks.append(lambda chars: login_result.extend(chars))

        msg = Message(0)
        msg.writer().writeByte(2)  # 2 nhân vật
        # Char 1
        msg.writer().writeInt(1001)
        msg.writer().writeUTF("Goku")
        msg.writer().writeShort(1)
        msg.writer().writeShort(2)
        msg.writer().writeShort(3)
        msg.writer().writeLong(5000000)
        # Char 2
        msg.writer().writeInt(1002)
        msg.writer().writeUTF("Vegeta")
        msg.writer().writeShort(4)
        msg.writer().writeShort(5)
        msg.writer().writeShort(6)
        msg.writer().writeLong(4800000)

        in_msg = Message(0, msg.getData())
        ctrl.onMessage(in_msg)

        self.assertEqual(len(login_result), 2)
        self.assertEqual(login_result[0].name, "Goku")
        self.assertEqual(login_result[0].playerID, 1001)
        self.assertEqual(login_result[1].name, "Vegeta")
        self.assertEqual(login_result[1].ppoint, 4800000)

    def test_item_and_options(self):
        """Kiểm tra mô hình Item và ItemOption format chuỗi hiển thị."""
        item = Item(template_id=194, quantity=5, info="Capsule bay", content="Dùng để bay tới map bất kỳ")
        item.addOption(0, 1500)  # Tấn công +1500
        item.addOption(77, 20)   # HP +20%
        item.addOption(30, 0)    # Không thể giao dịch

        self.assertEqual(item.template_id, 194)
        self.assertEqual(item.quantity, 5)
        self.assertEqual(len(item.options), 3)
        self.assertEqual(item.options[0].getText(), "Tấn công +1500")
        self.assertEqual(item.options[1].getText(), "HP +20%")
        self.assertEqual(item.options[2].getText(), "Không thể giao dịch")

    def test_pet_model(self):
        """Kiểm tra mô hình Pet / Đệ tử."""
        pet = Pet()
        self.assertFalse(pet.havePet)

        pet.havePet = True
        pet.cName = "DeTuGoku"
        pet.cHP = 50000
        pet.cHPFull = 50000
        pet.cDamFull = 3500
        pet.cPower = 1500000000
        pet.petStatus = 2  # Tấn công

        self.assertEqual(pet.statusName, "Tấn công")
        self.assertIn("DeTuGoku", str(pet))

    def test_magic_tree_model(self):
        """Kiểm tra mô hình Cây Đậu Thần."""
        tree = MagicTree()
        tree.level = 7
        tree.currPeas = 50
        tree.maxPeas = 50
        tree.seconds = 0
        self.assertEqual(tree.currPeas, 50)
        self.assertIn("Cấp=7", str(tree))

    def test_zone_info_and_map(self):
        """Kiểm tra ZoneInfo và MapInfo."""
        z1 = ZoneInfo(zoneId=1, numPlayer=5, maxPlayer=20)
        z2 = ZoneInfo(zoneId=2, numPlayer=15, maxPlayer=20)
        z3 = ZoneInfo(zoneId=3, numPlayer=20, maxPlayer=20)

        self.assertEqual(z1.status, "Vắng")
        self.assertEqual(z2.status, "Đông")
        self.assertEqual(z3.status, "Đầy")

        map_info = MapInfo()
        map_info.mapID = 21
        map_info.mapName = "Đảo Kame"
        map_info.zoneID = 1
        map_info.zones.extend([z1, z2, z3])

        self.assertEqual(len(map_info.zones), 3)
        self.assertIn("Đảo Kame", str(map_info))

    def test_chat_vip_and_boss_alert(self):
        """Kiểm tra bóc tách tin nhắn ChatVip và thông báo Boss xuất hiện/tiêu diệt (cmd 93)."""
        # 1. Boss xuất hiện
        spawn_msg = "BOSS Fide đại ca 1 vừa xuất hiện tại Núi Appule khu vực 5"
        cv1 = ChatVip.parse(spawn_msg)
        self.assertTrue(cv1.is_boss)
        self.assertFalse(cv1.is_killed)
        self.assertEqual(cv1.boss_name, "Fide đại ca 1")
        self.assertEqual(cv1.map_name, "Núi Appule")
        self.assertEqual(cv1.zone_id, 5)

        # 2. Boss bị tiêu diệt
        kill_msg = "poopooi02 : Đã tiêu diệt được BOSS Broly mọi người đều ngưỡng mộ."
        cv2 = ChatVip.parse(kill_msg)
        self.assertTrue(cv2.is_boss)
        self.assertTrue(cv2.is_killed)
        self.assertEqual(cv2.killer, "poopooi02")
        self.assertEqual(cv2.boss_name, "Broly")

        # 3. Tin nhắn chat VIP thông thường từ người chơi
        chat_msg = "!Chào cả server, bán vàng sll liên hệ"
        cv3 = ChatVip.parse(chat_msg)
        self.assertFalse(cv3.is_boss)
        self.assertEqual(cv3.text, "Chào cả server, bán vàng sll liên hệ")

        # 4. Kiểm tra Controller tiếp nhận gói tin cmd 93
        ctrl = Controller.gI()
        received_vips = []
        ctrl.on_chat_vip_callbacks.append(lambda cv: received_vips.append(cv))

        w = myWriter()
        w.writeUTF(spawn_msg)
        pkt = Message(93, w.getData())
        ctrl.onMessage(pkt)

        self.assertEqual(len(received_vips), 1)
        self.assertEqual(received_vips[0].boss_name, "Fide đại ca 1")
        self.assertEqual(received_vips[0].zone_id, 5)


if __name__ == "__main__":
    unittest.main()
