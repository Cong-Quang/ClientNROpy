# -*- coding: utf-8 -*-
"""
Module AutoTrainNewAccount mô phỏng 100% logic từ AutoTrainNewAccount.cs trong bản C# DragonBoy.
Tự động làm toàn bộ chuỗi nhiệm vụ tân thủ sơ sinh từ Nhiệm Vụ 0 đến Nhiệm Vụ 11:
- NV 0: Nhập game, mở rương nhận trang bị, thu hoạch đậu, nói chuyện sư phụ.
- NV 1: Đánh mộc nhân.
- NV 2: Thu thập đùi gà.
- NV 3: Nhặt sao băng.
- NV 4, 5, 6: Tiêu diệt quái mẹ (500 HP).
- NV 7: Tiêu diệt 20 quái bay (600 HP) (tự train sức mạnh > 78k, tự nhận bùa 1h).
- NV 8: Tìm ngọc rồng 7 sao (quái 1000 HP) (tự train sức mạnh > 140k).
- NV 9: Đến Rừng Karin và leo lên đỉnh tháp Karin (map 47 -> map 46).
- NV 10: Thách đấu & PK Thần Mèo Karin, sau đó xuống núi PK Tàu Pảy Pảy (T77).
- NV 11: Gặp sư phụ mới (Quy Lão, Trưởng lão Guru, Thần Vũ Trụ) -> Hoàn thành!

Hệ thống bổ trợ:
- Tự cộng điểm tiềm năng (AutoPoint: HP 400-500, MP 300, Sức đánh 70).
- Tự về nhà thu hoạch đậu khi hết đậu hoặc HP/MP < 15.
- Tự nâng cấp cây đậu khi đủ 5,000 vàng.
- Tự nhận bùa 1h miễn phí ở Bà Hạt Mít.
- Tự động tàn sát và nhặt đồ thông minh.
"""

import math
import random
import time
from typing import Any, List, Optional, Tuple


class AutoTrainNewAccount:
    """
    Bộ điều khiển tự động làm nhiệm vụ tân thủ sơ sinh (NV 0 -> NV 11).
    """

    def __init__(self, client: Any):
        self.client: Any = client
        self.is_enabled: bool = False

        self.is_tansat: bool = False
        self.is_picking: bool = False
        self.is_nhap_code_tan_thu: bool = False
        self.is_harvesting_pean: bool = False
        self.is_nhan_bua: bool = False
        self.is_tele_t77: bool = True
        self.is_pk_karin_sama: bool = False
        self.is_pk_t77: bool = False

        self.my_min_mp: int = 15
        self.my_min_hp: int = 15
        self.min_hp_mob: int = 0
        self.max_hp_mob: int = 2147483647
        self.min_peans: int = 0

        self.last_time_eat_pean: float = 0.0
        self.last_time_picked_item: float = 0.0
        self.last_time_auto_point: float = 0.0
        self.last_time_check_tn: float = 0.0
        self.last_tn: int = 0
        self.last_time_action: float = 0.0

    def set_state(self, value: bool) -> None:
        self.is_enabled = value
        if value:
            self._log("Bật Auto Tân Thủ: Bắt đầu chuỗi nhiệm vụ NV 0 -> NV 11!")
        else:
            self.is_tansat = False
            self.is_pk_karin_sama = False
            self.is_pk_t77 = False
            self._log("Đã tắt Auto Tân Thủ")

    def _log(self, text: str) -> None:
        from .logger import logger
        tag = getattr(self.client, "account_tag", "")
        logger.system(f"[AutoTrainNewAccount] {text}", account_tag=tag)

    # --------------------------------------------------------------------------
    # CHU KỲ MASTER STEP (GỌI TỪ WORKER THREAD CỦA AUTOMANAGER)
    # --------------------------------------------------------------------------
    def step(self) -> bool:
        """
        Thực hiện một bước làm nhiệm vụ tân thủ.
        Trả về True nếu AutoTrainNewAccount đã chiếm quyền xử lý.
        """
        if not self.is_enabled:
            return False

        char = getattr(self.client, "myChar", None)
        if not char:
            return False

        task = getattr(char, "task", None)
        task_id = getattr(task, "taskId", getattr(char, "ctaskId", 0))

        # Đã hoàn thành toàn bộ chuỗi nhiệm vụ tân thủ (> 11)
        if task_id > 11:
            self._log("Chúc mừng! Đã hoàn thành xuất sắc toàn bộ chuỗi nhiệm vụ sơ sinh (NV 0 -> 11). Tự động tắt auto!")
            self.set_state(False)
            return False

        xmap = getattr(self.client, "xmap", None)
        now = time.time()

        # 1. Tự nhập mã Code tân thủ nếu có cờ
        if self.is_nhap_code_tan_thu:
            self.client.service.sendClientInput(["tan thu nro"])
            self.is_nhap_code_tan_thu = False
            self._log("Đã gửi mã giftcode tân thủ 'tan thu nro'.")
            time.sleep(0.5)

        # 2. Hồi sinh về làng khi chết
        if char.is_dead:
            self.client.service.returnTownFromDead()
            self._log("Nhân vật bị hạ gục! Đang hồi sinh về nhà...")
            time.sleep(1.0)
            return True

        # 3. Kiểm tra hết đậu thần và máu/ki cạn kiệt -> Tự về nhà thu hoạch đậu
        home_map_id = char.cgender + 21
        current_map_id = getattr(char.mapInfo, "mapId", -1)
        hp_potion = getattr(char, "hp_potion", 0)

        if hp_potion <= 0 and (char.cMP < 15 or char.cHP < 15):
            if not self.is_harvesting_pean:
                self.is_harvesting_pean = True
                self.is_tansat = False
                self.is_pk_karin_sama = False
                self.is_pk_t77 = False
            if current_map_id != home_map_id and xmap and not getattr(xmap, "is_acting", False):
                self._log(f"Cạn kiệt HP/KI và hết đậu thần! Bay về nhà (Map {home_map_id}) thu hoạch...")
                xmap.start(home_map_id)
                return True

        # 4. Tự ăn đậu hồi phục HP/KI
        if (char.cMP < self.my_min_mp or char.cHP < self.my_min_hp) and not self.is_harvesting_pean:
            if (current_map_id != home_map_id or task_id < 3) and (now - self.last_time_eat_pean > 2.0):
                if self.min_peans <= 0 or hp_potion >= self.min_peans:
                    self.last_time_eat_pean = now
                    self._use_hp_potion()

        # 5. Xử lý các tác vụ tại Nhà (Map 21 TD, 22 NM, 23 XD)
        if current_map_id == home_map_id:
            if not self.is_harvesting_pean and self.min_peans > 0 and hp_potion < self.min_peans:
                self.is_harvesting_pean = True

            # Nhặt vật phẩm dưới đất tại nhà
            self._pick_items_in_map()

            magic_tree = getattr(char, "magicTree", None)
            curr_peas = getattr(magic_tree, "currPeas", 0) if magic_tree else 0
            tree_level = getattr(magic_tree, "level", 1) if magic_tree else 1
            is_updating = getattr(magic_tree, "isUpdateTree", False) if magic_tree else False

            # Điều kiện kết thúc thu hoạch
            if self.min_peans <= 0:
                max_peans = 30 if char.cgender == 1 else 20
                if curr_peas == 0 or hp_potion >= max_peans:
                    self.is_harvesting_pean = False
            elif hp_potion >= self.min_peans:
                self.is_harvesting_pean = False

            # Thu hoạch đậu thần từ NPC 4
            target_limit = 30 if char.cgender == 1 else 20
            if task_id >= 2 and curr_peas > 0 and hp_potion < target_limit:
                self.client.service.openMenu(4)
                time.sleep(0.3)
                self.client.service.confirmMenu(4, 0)
                self._log(f"Đã thu hoạch đậu thần tại nhà! (Hiện có: {char.hp_potion})")
                time.sleep(0.5)

            # Nâng cấp cây đậu thần lên cấp 2 nếu có >= 5000 vàng
            if char.xu >= 5000 and tree_level == 1 and not is_updating:
                self.client.service.openMenu(4)
                time.sleep(0.3)
                self.client.service.confirmMenu(4, 1)
                time.sleep(0.3)
                self.client.service.confirmMenu(5, 0)
                self._log("Đã nâng cấp Cây Đậu Thần lên cấp 2!")
                self.is_harvesting_pean = False
                time.sleep(0.5)

        # 6. Tự động tăng điểm tiềm năng (AutoPoint)
        if 3 < task_id <= 11:
            self._auto_point()

        # 7. Di chuyển Xmap đang chạy thì nhường đường
        if xmap and getattr(xmap, "is_acting", False):
            return True

        # 8. Thực hiện nhiệm vụ chính
        if not self.is_nhap_code_tan_thu and not self.is_harvesting_pean and not self.is_picking and char.cHP > 1:
            self._execute_quest_by_id(task_id)

        # 9. Tàn sát quái nhiệm vụ / PK Thần Mèo / PK Tàu Pảy Pảy
        if not self.is_nhap_code_tan_thu and not self.is_harvesting_pean and char.cHP > 1:
            if self.is_tansat and not self._auto_pick():
                self._tan_sat()
            if self.is_pk_karin_sama:
                self._pk_than_meo()
            elif self.is_pk_t77:
                self._pk_t77()

        return True

    # --------------------------------------------------------------------------
    # TỰ TĂNG ĐIỂM TIỀM NĂNG (AUTO POINT)
    # --------------------------------------------------------------------------
    def _auto_point(self) -> None:
        """Tự động nâng điểm tiềm năng cho acc sơ sinh: HP 400-500, MP 300, Sức đánh 70."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return
        now = time.time()
        if now - self.last_time_auto_point < 1.0:
            return
        self.last_time_auto_point = now

        # 1. Nâng HP gốc lên 400 (hoặc 500 nếu sức đánh đã >= 40)
        if (char.cHPGoc < 400 or (char.cDamGoc >= 40 and char.cHPGoc < 500)) and char.cTiemNang > char.cHPGoc + 1000:
            self.client.service.upPotential(0, 1)
            self._log(f"AutoPoint: Tăng Máu Gốc (HP: {char.cHPGoc})")
            return

        # 2. Nâng MP/KI gốc lên 300
        if char.cMPGoc < 300 and char.cDamGoc >= 25 and char.cTiemNang > char.cMPGoc + 1000:
            self.client.service.upPotential(1, 1)
            self._log(f"AutoPoint: Tăng Thể Lực / KI Gốc (MP: {char.cMPGoc})")
            return

        # 3. Nâng Sức đánh gốc lên 70
        if char.cDamGoc < 70 and char.cTiemNang > char.cDamGoc * 100:
            self.client.service.upPotential(2, 1)
            self._log(f"AutoPoint: Tăng Sức Đánh Gốc (Dam: {char.cDamGoc})")
            return

    # --------------------------------------------------------------------------
    # BỘ ĐIỀU PHỐI 12 NHIỆM VỤ SƠ SINH (NV 0 -> 11)
    # --------------------------------------------------------------------------
    def _execute_quest_by_id(self, task_id: int) -> None:
        if task_id == 0:
            self._auto_nv0()
        elif task_id == 1:
            self._auto_nv1()
        elif task_id == 2:
            self._auto_nv2()
        elif task_id == 3:
            self._auto_nv3()
        elif 4 <= task_id <= 6:
            self._auto_nv4_to_6()
        elif task_id == 7:
            self._auto_nv7()
        elif task_id == 8:
            self._auto_nv8()
        elif task_id == 9:
            self._auto_nv9()
        elif task_id == 10:
            self._auto_nv10()
        elif task_id == 11:
            self._auto_nv11()

    # NV 0: Vào game, mở rương, hái đậu, trả nhiệm vụ sư phụ
    def _auto_nv0(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)

        # Đang ở các map tàu vũ trụ đầu game (39-41) -> tele qua waypoint
        if 39 <= map_id <= 41:
            self.client.teleport(char.cx + 200, char.cy)
            time.sleep(0.5)
            return

        if 21 <= map_id <= 23:
            # Sư phụ ở nhà: TD 0, NM 2, XD 1
            sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

            if task_index == 2:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV0: Nói chuyện với Sư Phụ tại nhà.")
                time.sleep(0.5)

            elif task_index == 3:
                # Nhặt rương đồ ở tọa độ chuẩn
                box_x, box_y = 85, 336
                if char.cgender == 1:
                    box_x, box_y = 638, 336
                elif char.cgender == 2:
                    box_x, box_y = 94, 336

                if abs(char.cx - box_x) <= 15 and abs(char.cy - box_y) <= 15:
                    self.client.service.getItem(0, 0)
                    self._log("NV0: Mở rương trang bị nhận đồ tân thủ!")
                    time.sleep(0.5)
                else:
                    self.client.teleport(box_x, box_y)

            elif task_index == 4:
                # Thu hoạch đậu thần
                self.client.service.openMenu(4)
                time.sleep(0.3)
                self.client.service.confirmMenu(4, 0)
                self._log("NV0: Thu hoạch hạt đậu thần đầu tiên.")
                time.sleep(0.5)

            elif task_index == 5:
                # Trả nhiệm vụ cho Sư Phụ
                self.client.service.openMenu(sp_npc_id)
                self._log("NV0: Trả nhiệm vụ cho Sư Phụ tại nhà.")
                time.sleep(0.5)

    # NV 1: Đánh mộc nhân
    def _auto_nv1(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)
        moc_nhan_map = char.cgender * 7
        home_map = char.cgender + 21
        sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

        if task_index == 0:
            if map_id != moc_nhan_map:
                self.is_tansat = False
                self._xmap_to(moc_nhan_map)
            else:
                self.is_tansat = True
        elif task_index == 1:
            self.is_tansat = False
            if map_id != home_map:
                self._xmap_to(home_map)
            else:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV1: Trả nhiệm vụ đánh mộc nhân!")
                time.sleep(0.5)

    # NV 2: Thu thập đùi gà
    def _auto_nv2(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)
        dui_ga_map = char.cgender * 7 + 1
        home_map = char.cgender + 21
        sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

        if task_index == 0:
            if map_id != dui_ga_map:
                self.is_tansat = False
                self._xmap_to(dui_ga_map)
            else:
                self.is_tansat = True
        elif task_index == 1:
            self.is_tansat = False
            if map_id != home_map:
                self._xmap_to(home_map)
            else:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV2: Trả nhiệm vụ thu thập đùi gà!")
                time.sleep(0.5)

    # NV 3: Sao băng
    def _auto_nv3(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)
        sao_bang_map = char.cgender + 42
        home_map = char.cgender + 21
        sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

        if task_index == 0:
            self.client.service.upPotential(2, 1)  # Tăng sức đánh
            self._log("NV3: Tăng điểm sức đánh ban đầu.")
            time.sleep(0.5)

        elif task_index == 1:
            if map_id != sao_bang_map:
                self._xmap_to(sao_bang_map)
            else:
                sb_x, sb_y = 149, 288
                if char.cgender == 1:
                    sb_x, sb_y = 126, 264
                elif char.cgender == 2:
                    sb_x, sb_y = 156, 288
                self.client.teleport(sb_x, sb_y)
                self._auto_pick()
                self._log("NV3: Đến tọa độ sao băng và nhặt!")

        elif task_index == 2:
            if map_id != home_map:
                self._xmap_to(home_map)
            else:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV3: Trả nhiệm vụ nhặt sao băng!")
                time.sleep(0.5)

    # NV 4 -> 6: Quái mẹ (500 HP)
    def _auto_nv4_to_6(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)
        home_map = char.cgender + 21
        sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

        self.my_min_hp = 30
        self.max_hp_mob = 500
        self.min_hp_mob = 499

        if task_index < 3:
            target_map = 2 + char.cgender * 7
            if task_index == 1:
                target_map = 9 if char.cgender == 0 else 2
            elif task_index == 2:
                target_map = 9 if char.cgender == 2 else 16

            if map_id == target_map:
                self.is_tansat = True
            else:
                self.is_tansat = False
                self._xmap_to(target_map)
        else:
            self.is_tansat = False
            self.max_hp_mob = 2147483647
            self.min_hp_mob = 0
            if map_id != home_map:
                self._xmap_to(home_map)
            else:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV4-6: Trả nhiệm vụ tiêu diệt quái mẹ!")
                time.sleep(0.5)

    # NV 7: 20 quái bay (600 HP)
    def _auto_nv7(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)
        home_map = char.cgender + 21
        sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

        # Train sức mạnh > 78,000 trước khi đánh quái bay
        if char.cPower <= 78000 or task_index == 0:
            self._train_until_strong_enough(200)
            return

        if task_index == 1:
            qb_map = 3 if char.cgender == 0 else (11 if char.cgender == 1 else 17)
            if map_id == qb_map:
                self.my_min_hp = 45
                self.max_hp_mob = 600
                self.min_hp_mob = 599
                self.is_tansat = True
            else:
                self.is_tansat = False
                self._xmap_to(qb_map)

        elif task_index == 2:
            self.is_tansat = False
            self.max_hp_mob = 2147483647
            self.min_hp_mob = 0
            npc_map = char.cgender * 7
            if map_id == npc_map:
                self.client.service.openMenu(char.cgender + 7)
                self._log("NV7: Nói chuyện với Quy Lão / Trưởng Lão.")
                time.sleep(0.5)
            else:
                self._xmap_to(npc_map)

        elif task_index == 3:
            if map_id != home_map:
                self._xmap_to(home_map)
            else:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV7: Trả nhiệm vụ đánh 20 quái bay!")
                time.sleep(0.5)

    # NV 8: Ngọc rồng 7 sao (quái 1000 HP)
    def _auto_nv8(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)
        home_map = char.cgender + 21
        sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

        # Train sức mạnh > 140,000
        if char.cPower <= 140000 or task_index == 0:
            self._train_until_strong_enough(500)
            return

        if task_index == 1:
            self.my_min_hp = 60
            nr_map = 12 if char.cgender == 0 else (18 if char.cgender == 1 else 4)
            if map_id == nr_map:
                self.max_hp_mob = 1000
                self.min_hp_mob = 999
                self.is_tansat = True
            else:
                self.is_tansat = False
                self._xmap_to(nr_map)

        elif task_index == 2:
            self.is_tansat = False
            if map_id != home_map:
                self._xmap_to(home_map)
            else:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV8: Trả nhiệm vụ tìm ngọc rồng 7 sao!")
                time.sleep(0.5)

        elif task_index == 3:
            # Bay tới Rừng Karin (map 47)
            if map_id != 47:
                self._xmap_to(47)

    # NV 9: Rừng Karin và leo lên tháp
    def _auto_nv9(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)

        if task_index <= 1:
            if map_id == 47:
                self.client.service.openMenu(17)
                self._log("NV9: Nói chuyện với NPC 17 tại Rừng Karin.")
                time.sleep(0.5)
            else:
                self._xmap_to(47)

        elif task_index == 2:
            # Leo tháp: (600, 336) -> bay lên đỉnh (600, 10) chuyển sang map 46
            if map_id != 47:
                self._xmap_to(47)
            else:
                if abs(char.cx - 600) >= 20:
                    self.client.teleport(600, 336)
                else:
                    self.client.teleport(600, 10)
                time.sleep(0.5)

        elif task_index == 3:
            if map_id == 46:
                # Đang ở đỉnh tháp: nói chuyện Thần Mèo Karin (NPC 18)
                self.client.service.openMenu(18)
                time.sleep(0.3)
                self.client.service.confirmMenu(18, 0)
                self._log("NV9: Nói chuyện với Thần Mèo Karin trên đỉnh tháp!")
                time.sleep(0.5)
            elif map_id == 47:
                if abs(char.cx - 600) >= 20:
                    self.client.teleport(600, 336)
                else:
                    self.client.teleport(600, 10)
            else:
                self._xmap_to(47)

    # NV 10: Thách đấu Thần Mèo & PK Tàu Pảy Pảy
    def _auto_nv10(self) -> None:
        char = getattr(self.client, "myChar", None)
        task = getattr(char, "task", None)
        task_index = getattr(task, "index", 0) if task else 0
        map_id = getattr(char.mapInfo, "mapId", -1)
        home_map = char.cgender + 21
        sp_npc_id = 0 if char.cgender == 0 else (2 if char.cgender == 1 else 1)

        self.is_pk_karin_sama = False
        self.is_pk_t77 = False
        self.min_peans = 0 if task_index > 1 else 7

        if task_index == 0:
            # PK Thần Mèo trên đỉnh tháp Karin (map 46)
            if map_id == 46:
                self.client.teleport(421, 408)
                time.sleep(0.3)
                # Thách đấu Thần Mèo
                self.client.service.openMenu(18)
                time.sleep(0.3)
                self.client.service.confirmMenu(18, 3)
                time.sleep(0.3)
                self.client.service.confirmMenu(18, 0)
                self.is_pk_karin_sama = True
                self._log("NV10: Bắt đầu PK Thần Mèo Karin!")
            elif map_id == 47:
                self.client.teleport(600, 10)
            else:
                self._xmap_to(47)

        elif task_index == 1:
            # Leo xuống map 47 PK Tàu Pảy Pảy
            if map_id == 46:
                self.client.teleport(576, 552)
                self.is_tele_t77 = True
            elif map_id == 47:
                if self.is_tele_t77 and (char.cx != 371 or char.cy != 336):
                    self.is_tele_t77 = False
                    self.client.teleport(371, 336)
                else:
                    self.is_pk_t77 = True
                    self._log("NV10: Bắt đầu PK Tàu Pảy Pảy (T77)!")
            else:
                self.is_tele_t77 = True
                self._xmap_to(47)

        elif task_index == 2:
            if map_id == 47:
                self.client.service.openMenu(17)
                self._log("NV10: Nói chuyện với NPC 17 tại Rừng Karin.")
                time.sleep(0.5)
            else:
                self._xmap_to(47)

        elif task_index == 3:
            if map_id != home_map:
                self._xmap_to(home_map)
            else:
                self.client.service.openMenu(sp_npc_id)
                self._log("NV10: Trả nhiệm vụ Thách đấu Thần Mèo!")
                time.sleep(0.5)

    # NV 11: Gặp sư phụ mới
    def _auto_nv11(self) -> None:
        char = getattr(self.client, "myChar", None)
        map_id = getattr(char.mapInfo, "mapId", -1)
        sp_moi_map = 5 if char.cgender == 0 else (13 if char.cgender == 1 else 20)
        sp_moi_npc = 13 + char.cgender

        if map_id != sp_moi_map:
            self._xmap_to(sp_moi_map)
        else:
            self.client.service.openMenu(sp_moi_npc)
            time.sleep(0.3)
            self.client.service.confirmMenu(sp_moi_npc, 0)
            self._log("NV11: Đã bái kiến Sư Phụ Mới! Hoàn tất chuỗi nhiệm vụ tân thủ sơ sinh.")
            self.set_state(False)

    # --------------------------------------------------------------------------
    # TRAIN SỨC MẠNH & NHẬN BÙA 1H MIỄN PHÍ
    # --------------------------------------------------------------------------
    def _train_until_strong_enough(self, max_hp: int) -> None:
        """Tự động nhận bùa 1h miễn phí ở Bà Hạt Mít và train quái lên đủ sức mạnh."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return
        map_id = getattr(char.mapInfo, "mapId", -1)
        bua_map = char.cgender + 42

        # 1. Nhận bùa 1h miễn phí từ Bà Hạt Mít (NPC 21)
        if not self.is_nhan_bua:
            if map_id != bua_map:
                self.is_tansat = False
                self._xmap_to(bua_map)
            else:
                self.client.teleport(char.cx, char.cy)
                self.client.service.openMenu(21)
                time.sleep(0.3)
                self.client.service.confirmMenu(21, 0)
                self.is_nhan_bua = True
                self._log("Đã nhận Bùa 1h Miễn Phí từ Bà Hạt Mít!")
                time.sleep(0.5)
            return

        # 2. Sang map train thích hợp (map 3 TD, 9 NM, 17 XD)
        train_map = 3 if char.cgender == 0 else (9 if char.cgender == 1 else 17)
        if map_id == train_map:
            self.max_hp_mob = max_hp
            self.min_hp_mob = 0
            self.is_tansat = True
        else:
            self.is_tansat = False
            self._xmap_to(train_map)

    # --------------------------------------------------------------------------
    # HÀNH ĐỘNG TÀN SÁT & PK
    # --------------------------------------------------------------------------
    def _tan_sat(self) -> None:
        """Tự động tìm quái phù hợp điều kiện HP và gửi đòn tấn công."""
        char = getattr(self.client, "myChar", None)
        if not char or self.is_picking:
            return

        now = time.time()
        # Kiểm tra tiềm năng có tăng không sau 3s (chống kẹt)
        if now - self.last_time_check_tn > 3.0:
            self.last_time_check_tn = now
            if char.cTiemNang == self.last_tn and self.last_tn > 0:
                self.client.teleport(char.cx, char.cy)
            self.last_tn = char.cTiemNang

        mob = self._find_closest_mob()
        if not mob:
            return

        # Di chuyển tới sát quái
        dist = char.distance_to(mob.x, mob.y)
        if dist > 50:
            self.client.teleport(mob.x, mob.y)
            return

        # Tấn công quái
        char.mobFocus = mob
        self.client.service.selectSkill(0)
        self.client.service.sendPlayerAttack([mob.mobId], [], 1)

    def _pk_than_meo(self) -> None:
        """Tự động tiếp cận và tấn công Thần Mèo Karin (map 46)."""
        char = getattr(self.client, "myChar", None)
        if not char or self.is_picking:
            return
        self.my_min_hp = 60
        self.my_min_mp = 20

        for ch in char.mapInfo.chars.values():
            if getattr(ch, "cName", "") == "Karin" and getattr(ch, "cTypePk", 0) == 3:
                dist = char.distance_to(ch.cx, ch.cy)
                if dist > 50:
                    self.client.teleport(ch.cx + random.randint(-5, 5), ch.cy)
                else:
                    char.charFocus = ch
                    self.client.service.selectSkill(0)
                    self.client.service.sendPlayerAttack([], [ch.charID], -1)
                break

    def _pk_t77(self) -> None:
        """Tự động tiếp cận và tấn công Tàu Pảy Pảy (T77 map 47)."""
        char = getattr(self.client, "myChar", None)
        if not char or self.is_picking:
            return
        self.my_min_hp = 100
        self.my_min_mp = 20

        for ch in char.mapInfo.chars.values():
            c_name = getattr(ch, "cName", "")
            if ("Tao" in c_name or "T77" in c_name or "Mercenary" in c_name) and getattr(ch, "cTypePk", 0) == 3:
                dist = char.distance_to(ch.cx, ch.cy)
                if dist > 50:
                    self.client.teleport(ch.cx + random.randint(-5, 5), ch.cy)
                else:
                    char.charFocus = ch
                    self.client.service.selectSkill(0)
                    self.client.service.sendPlayerAttack([], [ch.charID], -1)
                break

    def _find_closest_mob(self) -> Optional[Any]:
        char = getattr(self.client, "myChar", None)
        if not char:
            return None
        best = None
        min_d = float("inf")
        for mob in char.mapInfo.mobs.values():
            if getattr(mob, "status", 0) in (0, 1) or getattr(mob, "hp", 0) <= 0 or getattr(mob, "isMobMe", False):
                continue
            max_hp = getattr(mob, "maxHp", getattr(mob, "hp", 0))
            if max_hp < self.min_hp_mob or max_hp > self.max_hp_mob:
                continue
            d = char.distance_to(mob.x, mob.y)
            if d < min_d:
                min_d = d
                best = mob
        return best

    def _auto_pick(self) -> bool:
        """Nhặt đồ rơi trên đất nếu có."""
        now = time.time()
        char = getattr(self.client, "myChar", None)
        if not char:
            return False
        items = list(char.mapInfo.items.values())
        if not items:
            self.is_picking = False
            return False

        has_pick = False
        for it in items:
            p_id = getattr(it, "playerId", -1)
            dist = char.distance_to(it.x, it.y)
            if p_id == char.charID or (p_id == -1 and dist <= 60) or getattr(it, "itemTemplateID", -1) == 74:
                has_pick = True
                if now - self.last_time_picked_item > 0.55:
                    self.is_picking = True
                    char.mobFocus = None
                    if dist > 60:
                        self.client.teleport(it.x, it.y)
                    self.client.service.pickItem(it.itemMapID)
                    self.last_time_picked_item = now
                    break
        if not has_pick:
            self.is_picking = False
        return has_pick

    def _pick_items_in_map(self) -> None:
        """Nhặt item tại nhà."""
        now = time.time()
        char = getattr(self.client, "myChar", None)
        if not char:
            return
        items = list(char.mapInfo.items.values())
        if items and now - self.last_time_picked_item > 0.55:
            self.last_time_picked_item = now
            it = items[0]
            self.client.service.pickItem(it.itemMapID)

    def _use_hp_potion(self) -> None:
        """Dùng đậu thần trong hành trang."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return
        pean = char.get_first_pean_item()
        if pean:
            self.client.service.useItem(0, 1, -1, pean.template_id)

    def _xmap_to(self, map_id: int) -> None:
        xmap = getattr(self.client, "xmap", None)
        if xmap and not getattr(xmap, "is_acting", False):
            xmap.start(map_id)
