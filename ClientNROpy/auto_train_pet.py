# -*- coding: utf-8 -*-
"""
Module AutoTrainPet mô phỏng 100% logic từ AutoTrainPet.cs trong bản C# DragonBoy.
Bao gồm:
- Các chế độ úp đệ: Thường (Normal), Né siêu quái (AvoidSuperMob), Kaioken.
- Các chế độ đánh khi đệ kêu lười: Đánh quái gần nhất, Đánh đệ tử (cờ đen), Tự đánh mình (cờ đen).
- Tự động cho đệ ăn đậu thần khi thể lực < 5.
- Tự động về nhà thu hoạch đậu thần khi hết đậu, sau đó quay lại đúng map và zone cũ.
- Tự động teleport đến vị trí an toàn (x=50) khi đệ tử chết để tránh quái vây chết sư phụ.
- Tự động khống chế Siêu Quái (Thái Dương Hạ San, Trói, Thôi Miên) bảo vệ đệ.
- Tự động hỗ trợ skill Trị thương (Namek) / Tái tạo năng lượng (Xayda).
- Tự động kéo đệ tử lại gần khi đệ đi lạc xa hơn 400px.
- Tự động nhặt đồ rơi dưới đất.
"""

import math
import random
import time
from enum import Enum
from typing import Any, List, Optional, Set, Tuple


class AutoTrainPetMode(Enum):
    DISABLED = 0
    NORMAL = 1
    AVOID_SUPER_MOB = 2
    KAIOKEN = 3


class AutoTrainPetAttackMode(Enum):
    ATTACK_CLOSEST_MOB = 0
    ATTACK_MY_PET = 1
    ATTACK_MYSELF = 2


class AutoTrainPet:
    """
    Bộ điều khiển úp đệ tử tự động tương đương class AutoTrainPet trong C#.
    """

    DEFAULT_BLOCKED_ITEMS: Set[int] = {
        828, 829, 830, 831, 832, 833, 834, 835, 836, 837, 838, 839, 840, 841, 842,
        859, 362, 353, 354, 355, 356, 357, 358, 359, 360, 225
    }

    def __init__(self, client: Any):
        self.client: Any = client
        self.mode: AutoTrainPetMode = AutoTrainPetMode.DISABLED
        self.attack_mode: AutoTrainPetAttackMode = AutoTrainPetAttackMode.ATTACK_CLOSEST_MOB

        self.mob_template_id_list: List[int] = []
        self.mob_id_list: List[int] = []

        # Các biến trạng thái điều khiển
        self.last_time_pick: float = 0.0
        self.last_x: int = 0
        self.is_assigned_last_x: bool = False
        self.last_x_pet: int = 0
        self.is_assigned_last_x_pet: bool = False
        self.is_my_pet_died: bool = False
        self.is_picking: bool = False

        self.last_time_pet_follow: float = time.time()
        self.is_go_home_get_more_pean: bool = False
        self.is_magic_tree_upgrading: bool = False
        self.is_magic_tree_out_of_pean: bool = False
        self.last_time_check_magic_tree: float = 0.0
        self.map_zone_go_back: Tuple[int, int] = (0, 0)
        self.delay_check_pet: float = 0.0
        self.is_first_time_check_pet: bool = True
        self.is_ttnl: bool = False
        self.sao_may_luoi_the: bool = False

        self.last_time_skill3: float = 0.0
        self.last_time_control_skill: float = 0.0
        self.last_time_eat_hp: float = 0.0
        self.last_tick_toggle: int = 0

        # Đăng ký callback nghe đệ tử chat
        if hasattr(self.client, "controller") and self.client.controller:
            self.client.controller.on_pet_chat_callbacks.append(self._on_pet_chat)

    def _on_pet_chat(self, text: str) -> None:
        """Đệ tử chat trong map, nếu kêu lười thì kích hoạt đòn đánh."""
        lower = text.lower()
        if "lười" in lower or "luoi the" in lower:
            self.sao_may_luoi_the = True

    @property
    def is_enabled(self) -> bool:
        return self.mode != AutoTrainPetMode.DISABLED

    def set_mode(self, mode: AutoTrainPetMode) -> None:
        self.mode = mode
        if mode != AutoTrainPetMode.DISABLED:
            self.is_first_time_check_pet = True
            self.last_time_pet_follow = time.time()
            self._log(f"Bật Auto Úp Đệ Tử: Chế độ '{mode.name}'")
        else:
            self._log("Đã tắt Auto Úp Đệ Tử")

    def set_attack_mode(self, mode: AutoTrainPetAttackMode) -> None:
        self.attack_mode = mode
        self._log(f"Chế độ đánh khi đệ cần: '{mode.name}'")

    def _log(self, text: str) -> None:
        from .logger import logger
        tag = getattr(self.client, "account_tag", "")
        logger.system(f"[AutoTrainPet] {text}", account_tag=tag)

    # --------------------------------------------------------------------------
    # CHU KỲ MASTER STEP (GỌI TỪ WORKER THREAD CỦA AUTOMANAGER)
    # --------------------------------------------------------------------------
    def step(self) -> bool:
        """
        Thực hiện một bước cập nhật của AutoTrainPet.
        Trả về True nếu AutoTrainPet đã chiếm quyền xử lý (không làm việc khác).
        """
        if self.mode == AutoTrainPetMode.DISABLED:
            return False

        char = getattr(self.client, "myChar", None)
        if not char:
            return False

        # Đang di chuyển Xmap thì nhường đường
        xmap = getattr(self.client, "xmap", None)
        if xmap and getattr(xmap, "is_acting", False):
            return True

        now = time.time()
        if self.is_first_time_check_pet:
            self.delay_check_pet = now
            self.is_first_time_check_pet = False
            return True

        if now - self.delay_check_pet < 3.0:
            return True

        # 1. Tự nhặt đồ dưới đất
        self.auto_pick()

        # 2. Kiểm tra thể lực đệ tử & Tự dùng đậu cho đệ
        pet = getattr(char, "pet", None)
        hp_potion = getattr(char, "hp_potion", 0)

        if pet and pet.havePet:
            if pet.cStamina < 5 and hp_potion > 0 and pet.cHP > 0:
                if now - self.last_time_eat_hp > 2.0:
                    self.last_time_eat_hp = now
                    self._use_pean_for_pet()

        # 3. Cooldown kiểm tra lại cây đậu thần sau 10 phút nếu hết đậu
        if self.is_magic_tree_out_of_pean and (now - self.last_time_check_magic_tree >= 600.0):
            self.is_magic_tree_out_of_pean = False
            self.last_time_check_magic_tree = now

        # 4. Hết đậu trong túi -> kích hoạt chu trình về nhà thu hoạch
        home_map_id = char.cgender + 21
        current_map_id = getattr(char.mapInfo, "mapId", -1)
        current_zone_id = getattr(char.mapInfo, "zoneId", 0)

        if not self.is_magic_tree_upgrading:
            if hp_potion == 0 and not self.is_go_home_get_more_pean and not self.is_magic_tree_out_of_pean:
                self.is_go_home_get_more_pean = True
                self.map_zone_go_back = (current_map_id, current_zone_id)
                self._log(f"Hết đậu thần! Tạm ngưng úp đệ, bay về nhà (Map {home_map_id}) thu hoạch...")

        # 5. Xử lý hành trình về nhà thu hoạch đậu và quay lại
        if self.is_go_home_get_more_pean and not self.is_magic_tree_out_of_pean:
            if current_map_id != home_map_id:
                if xmap and not getattr(xmap, "is_acting", False) and hp_potion == 0:
                    xmap.start(home_map_id)
                    return True
            else:
                # Đang ở nhà: tương tác cây đậu thần (NPC 4)
                magic_tree = getattr(char, "magicTree", None)
                curr_peas = getattr(magic_tree, "currPeas", 0) if magic_tree else 0
                is_updating = getattr(magic_tree, "isUpdateTree", False) if magic_tree else False

                if curr_peas > 0:
                    self.client.service.openMenu(4)
                    time.sleep(0.3)
                    self.client.service.confirmMenu(4, 0)
                    self._log(f"Đã thu hoạch đậu thần tại nhà! Số lượng đậu hiện có: {char.hp_potion}")
                    time.sleep(0.5)
                else:
                    self.is_magic_tree_out_of_pean = True
                    self.last_time_check_magic_tree = now
                    self._log("Cây đậu thần hiện tại chưa có hạt đậu nào để thu hoạch.")

                if is_updating:
                    self.last_time_check_magic_tree = now
                    self.is_magic_tree_upgrading = True
                    self._log("Cây đậu thần đang trong quá trình nâng cấp.")

                # Đã thu hoạch xong hoặc cây hết đậu -> Xmap quay trở lại map cũ
                target_map, target_zone = self.map_zone_go_back
                if target_map > 0 and xmap and not getattr(xmap, "is_acting", False):
                    self._log(f"Quay trở lại bãi úp đệ: Map {target_map}, Khu {target_zone}...")
                    xmap.start(target_map)
                    return True

            target_map, target_zone = self.map_zone_go_back
            if current_map_id == target_map and xmap and not getattr(xmap, "is_acting", False):
                if current_zone_id != target_zone:
                    self.client.service.requestChangeZone(target_zone, 0)
                    time.sleep(0.8)
                else:
                    if self.last_x > 0 and abs(char.cx - self.last_x) > 20:
                        self.client.teleport(self.last_x, char.cy)
                    self.is_go_home_get_more_pean = False
                    self._log("Đã quay về đúng vị trí và khu vực cũ. Tiếp tục úp đệ!")
            return True

        # 6. Bảo vệ an toàn: Tele ra góc khi đệ tử chết
        self.tele_to_safe_pos()

        # 7. Tự tung kỹ năng hỗ trợ / khống chế siêu quái / phản ứng khi đệ lười
        self.auto_skill()

        # 8. Đệ đang chết thì không làm gì thêm
        if self.is_my_pet_died:
            return True

        # Trả về tọa độ cũ của đệ sau khi hồi sinh
        if self.is_assigned_last_x_pet:
            self.is_assigned_last_x_pet = False
            self.client.teleport(self.last_x_pet, char.cy)

        # 9. Đệ tử đi xa quá (> 400) hoặc quá 10 phút -> kéo đệ lại gần
        dist_pet = self._get_distance_to_my_pet()
        if (now - self.last_time_pet_follow > 600.0) or (dist_pet is not None and dist_pet > 400):
            self.last_time_pet_follow = now
            self.client.service.petStatus(0)  # Đi theo
            self.client.teleport(char.cx, char.cy)
            time.sleep(0.3)
            return True

        # 10. Điều khiển hành vi theo chế độ đã chọn
        if self.mode == AutoTrainPetMode.NORMAL:
            if pet and pet.petStatus != 2:
                self.client.service.petStatus(2)  # Tấn công

        elif self.mode == AutoTrainPetMode.AVOID_SUPER_MOB:
            if pet and pet.petStatus != 1:
                self.client.service.petStatus(1)  # Bảo vệ
            closest = self.get_closest_mob()
            if closest and getattr(closest, "x", 0) > 50 and getattr(closest, "y", 0) > 50:
                tx = closest.x + random.randint(-5, 5)
                ty = closest.y
                if abs(char.cx - tx) > 30:
                    self.client.teleport(tx, ty)

        elif self.mode == AutoTrainPetMode.KAIOKEN:
            if pet and pet.petStatus != 2:
                self.client.service.petStatus(2)  # Tấn công
            # Giật nhẹ tọa độ Y né đòn
            self.last_tick_toggle = (self.last_tick_toggle + 1) % 2
            if self.last_tick_toggle == 0:
                char.cy -= 1
            else:
                char.cy += 1
            self.client.service.charMove()

        return True

    # --------------------------------------------------------------------------
    # CÁC HÀM TIỆN ÍCH CON TƯƠNG ỨNG C#
    # --------------------------------------------------------------------------
    def _use_pean_for_pet(self) -> None:
        """Sử dụng đậu thần trong hành trang để hồi phục thể lực cho đệ."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return
        pean = char.get_first_pean_item()
        if pean:
            # cmd -43: useItem
            self.client.service.useItem(0, 1, -1, pean.template_id)
            self._log(f"Đã dùng 1 hạt đậu thần (ID {pean.template_id}) hồi phục thể lực cho đệ.")

    def _get_distance_to_my_pet(self) -> Optional[float]:
        """Lấy khoảng cách từ nhân vật tới đệ tử trên map (-charID)."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return None
        pet_char_id = -char.charID
        map_chars = getattr(char.mapInfo, "chars", {})
        if pet_char_id in map_chars:
            pet_obj = map_chars[pet_char_id]
            return char.distance_to(pet_obj.cx, pet_obj.cy)
        return None

    def tele_to_safe_pos(self) -> None:
        """Dịch chuyển nhân vật ra vị trí an toàn (x=50) khi đệ tử chết."""
        char = getattr(self.client, "myChar", None)
        if not char or self.is_picking:
            return

        pet = getattr(char, "pet", None)
        if not pet or not pet.havePet:
            return

        # Kiểm tra đệ tử có bị chết không
        pet_dead = (pet.cHP <= 0)
        pet_char_id = -char.charID
        map_chars = getattr(char.mapInfo, "chars", {})
        if pet_char_id in map_chars:
            ch_pet = map_chars[pet_char_id]
            if getattr(ch_pet, "cHP", 1) <= 0 or getattr(ch_pet, "statusMe", 1) == 14:
                pet_dead = True

        if pet_dead:
            if not self.is_my_pet_died:
                self.is_my_pet_died = True
                if not self.is_assigned_last_x_pet:
                    self.is_assigned_last_x_pet = True
                    self.last_x_pet = char.cx
                self._log("Đệ tử đã bị hạ gục! Dịch chuyển sư phụ ra vùng an toàn (x=50)...")
                self.client.teleport(50, char.cy)
        else:
            if self.is_my_pet_died:
                self.is_my_pet_died = False
                self._log("Đệ tử đã hồi sinh! Sư phụ quay trở lại vị trí chiến đấu.")

    def auto_skill(self) -> None:
        """Tự động sử dụng chiêu thức hỗ trợ, khống chế siêu quái và phản hồi đệ kêu lười."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return
        now = time.time()

        # Skill 3 theo hành tinh:
        # TD: Thái Dương Hạ San (template 2)
        # NM: Trị thương (template 2)
        # XD: Tái tạo năng lượng (template 2)
        skill_3_cd = 10.0
        if now - self.last_time_skill3 > skill_3_cd:
            pet = getattr(char, "pet", None)
            char_hp_pct = (char.cHP / max(1, char.cHPFull)) * 100.0
            char_mp_pct = (char.cMP / max(1, char.cMPFull)) * 100.0
            pet_hp_pct = (pet.cHP / max(1, pet.cHPFull)) * 100.0 if pet else 100.0
            pet_mp_pct = (pet.cMP / max(1, pet.cMPFull)) * 100.0 if pet else 100.0

            # 1. Hành tinh Namek: Trị thương cho đệ hoặc mình
            if char.cgender == 1 and (pet_hp_pct < 10 or pet_mp_pct < 10 or char_hp_pct < 10 or char_mp_pct < 10):
                self.client.service.selectSkill(2)  # Trị thương
                pet_char_id = -char.charID
                self.client.service.sendPlayerAttack([], [pet_char_id], 2)
                self.client.service.selectSkill(0)  # Quay lại chiêu đấm
                self.last_time_skill3 = now
                self._log("Tung chiêu Trị Thương hồi phục cho đệ tử!")
                return

            # 2. Hành tinh Xayda: Tái tạo năng lượng khi HP/MP < 10%
            if char.cgender == 2 and (char_hp_pct < 10 or char_mp_pct < 10):
                self.client.service.selectSkill(2)  # TTNL
                self.is_ttnl = True
                self.last_time_skill3 = now
                self._log("Tung chiêu Tái Tạo Năng Lượng hồi phục HP/KI!")
                return

        # 3. Khống chế Siêu Quái (SuperMob: mob.levelBoss > 0):
        # TD: skill 2 (Thái Dương), NM: skill 6 (Trói), XD: skill 6 (Thôi Miên)
        if now - self.last_time_control_skill > 8.0:
            ctrl_skill_id = 2 if char.cgender == 0 else 6
            super_mob = self._find_super_mob()
            if super_mob:
                self.client.service.selectSkill(ctrl_skill_id)
                self.client.service.sendPlayerAttack([super_mob.mobId], [], 1)
                self.client.service.selectSkill(0)
                self.last_time_control_skill = now
                self._log(f"Khống chế siêu quái (ID {super_mob.mobId}) bảo vệ đệ tử!")
                return

        # 4. Phản hồi khi đệ tử kêu lười ("sao may luoi the"):
        if self.sao_may_luoi_the:
            self.sao_may_luoi_the = False
            self.client.service.selectSkill(0)  # Đấm thường

            if self.attack_mode == AutoTrainPetAttackMode.ATTACK_CLOSEST_MOB:
                closest = self.get_closest_mob()
                if closest:
                    self.client.service.sendPlayerAttack([closest.mobId], [], 1)
                    self._log(f"Đệ kêu lười: Đấm kích hoạt vào quái gần nhất #{closest.mobId}")

            elif self.attack_mode == AutoTrainPetAttackMode.ATTACK_MY_PET:
                # Đổi cờ đen (flag 8) đấm đệ tử
                if char.cFlag != 8:
                    self.client.service.getFlag(1, 8)
                pet_char_id = -char.charID
                self.client.service.sendPlayerAttack([], [pet_char_id], 2)
                self._log("Đệ kêu lười: Bật cờ đen đấm đệ tử kích hoạt!")

            elif self.attack_mode == AutoTrainPetAttackMode.ATTACK_MYSELF:
                # Đổi cờ đen tự đánh bản thân
                if char.cFlag != 8:
                    self.client.service.getFlag(1, 8)
                self.client.service.sendPlayerAttack([], [char.charID], 2)
                self._log("Đệ kêu lười: Bật cờ đen tự đấm bản thân!")

    def _find_super_mob(self) -> Optional[Any]:
        """Tìm siêu quái (levelBoss > 0) còn sống trong map."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return None
        for mob in list(char.mapInfo.mobs.values()):
            if getattr(mob, "levelBoss", 0) > 0 and getattr(mob, "hp", 0) > 0 and not getattr(mob, "isMobMe", False):
                return mob
        return None

    def get_closest_mob(self) -> Optional[Any]:
        """Tìm quái thường gần nhất theo whitelist và không phải siêu quái."""
        char = getattr(self.client, "myChar", None)
        if not char:
            return None

        best_mob = None
        min_dist = float("inf")

        for mob in list(char.mapInfo.mobs.values()):
            if getattr(mob, "status", 0) in (0, 1):
                continue
            if getattr(mob, "hp", 0) <= 0 or getattr(mob, "isMobMe", False) or getattr(mob, "levelBoss", 0) != 0:
                continue

            # Kiểm tra whitelist filter
            t_id = getattr(mob, "templateId", -1)
            m_id = getattr(mob, "mobId", -1)
            if self.mob_template_id_list and t_id not in self.mob_template_id_list:
                continue
            if self.mob_id_list and m_id not in self.mob_id_list:
                continue

            dist = char.distance_to(mob.x, mob.y)
            if dist < min_dist:
                min_dist = dist
                best_mob = mob

        return best_mob

    def auto_pick(self) -> None:
        """Nhặt vật phẩm rơi trên đất, bỏ qua vật phẩm rác, quay về vị trí cũ."""
        now = time.time()
        if now - self.last_time_pick < 0.55:
            return

        char = getattr(self.client, "myChar", None)
        if not char:
            return

        items = list(char.mapInfo.items.values())
        if not items:
            self.is_picking = False
            return

        has_pickable = False
        for it in items:
            t_id = getattr(it, "itemTemplateID", -1)
            if t_id in self.DEFAULT_BLOCKED_ITEMS:
                continue

            # Đồ của mình hoặc rơi tự do (-1)
            p_id = getattr(it, "playerId", -1)
            if p_id == char.charID or p_id == -1 or t_id == 74:
                has_pickable = True
                if not self.is_assigned_last_x:
                    self.is_assigned_last_x = True
                    self.last_x = char.cx

                dist = char.distance_to(it.x, it.y)
                if dist > 60:
                    self.client.teleport(it.x, it.y)
                else:
                    self.client.service.charMove()

                self.client.service.pickItem(it.itemMapID)
                self.is_picking = True
                self.last_time_pick = now
                break

        # Đã nhặt hết vật phẩm -> dịch chuyển quay trở lại vị trí ban đầu
        if self.is_assigned_last_x and not has_pickable:
            if self.last_x <= 50 and self.last_x_pet > 50:
                self.last_x = self.last_x_pet
            self.is_picking = False
            if abs(char.cx - self.last_x) > 60:
                self.client.teleport(self.last_x, char.cy)
            self.is_assigned_last_x = False
