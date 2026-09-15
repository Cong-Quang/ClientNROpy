# -*- coding: utf-8 -*-
"""
Bộ điều khiển chiến đấu tự động (CombatManager).
Mô phỏng các tính năng trong C# Mod:
- Tiêu điểm nhắm mục tiêu (Focus quái, người chơi, vật phẩm, NPC)
- Dịch chuyển tức thời (Teleport coordinates, mob, player, item, waypoint)
- Tự động tấn công (Auto Attack - AK / AutoSendAttack.cs)
- Tàn sát tự động (Slaughter - Tàn sát toàn bộ quái, theo loại, tàn sát người chơi PK, tự nhặt đồ, né siêu quái, tự ăn đậu)
Đảm bảo 1 file chỉ chứa đúng 1 class.
"""

import math
import time
import threading
from typing import Optional, List, Set, Tuple, Union, Any, Dict

from .char import Char
from .mob import Mob
from .item_map import ItemMap
from .waypoint import Waypoint
from .service import Service


class CombatManager:
    """
    Quản lý tập trung các chức năng Focus, Teleport, AK (Auto Attack)
    và Tàn Sát (Slaughter / Auto Mob / Auto PK / Auto Pick Item / Auto Pean).
    """

    # Danh sách item mặc định bị chặn nhặt (mô phỏng IdItemBlockBase trong Pk9rPickMob.cs)
    DEFAULT_BLOCKED_ITEMS: Set[int] = {225, 353, 354, 355, 356, 357, 358, 359, 360, 362}

    def __init__(self, client=None):
        self.client = client

        # Trạng thái AK (Auto Attack mục tiêu đang focus)
        self.is_ak: bool = False


        # Trạng thái Tàn Sát (Slaughter)
        self.is_tansat: bool = False
        self.tansat_mode: str = "mob"  # "mob": quái, "player": người chơi, "all": cả hai

        # Bộ lọc quái vật
        self.target_mob_ids: Set[int] = set()        # Rỗng = tất cả quái
        self.target_mob_types: Set[int] = set()      # Rỗng = tất cả loại quái
        self.avoid_super_mob: bool = True            # Né siêu quái (mặc định Bật - nsq)

        # Bộ lọc người chơi (Auto PK)
        self.target_char_names: Set[str] = set()     # Rỗng = tất cả người chơi
        self.target_char_ids: Set[int] = set()

        # Tự động nhặt đồ & Tự động dùng đậu
        self.auto_pick: bool = True                  # Tự động nhặt đồ (anhat)
        self.pick_gem_only: bool = False             # Chỉ nhặt ngọc (cnn)
        self.blocked_items: Set[int] = set(self.DEFAULT_BLOCKED_ITEMS)
        self.auto_pean: bool = True                  # Tự động dùng đậu (abf)
        self.pean_threshold: float = 0.2             # Ngưỡng HP/KI dùng đậu (20%)
        self.auto_revive: bool = True                # Tự động hồi sinh khi chết

        # Skill tàn sát theo hành tinh (templateId): đấm, chưởng, đặc biệt
        # Trái Đất (0): đấm 0, kamejoko 1, kaioken 9
        # Namek (1): đấm 2, masenko 3, trứng 12
        # Xayda (2): đấm 4, atomic 5, hoá hình 13
        self._tansat_skill_idx: int = 0
        self._skill_last_use: Dict[int, float] = {}

        # Quản lý luồng nền
        self._is_running: bool = False
        self._worker_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        self._start_worker()

    def _start_worker(self) -> None:
        """Khởi động luồng nền xử lý AK và Tàn Sát."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._is_running = True
            self._worker_thread = threading.Thread(target=self._loop_worker, daemon=True, name="CombatManagerThread")
            self._worker_thread.start()

    def _loop_worker(self) -> None:
        """Vòng lặp chu kỳ của luồng chiến đấu tự động."""
        while self._is_running:
            try:
                if self.is_ak:
                    self._step_ak()

                if self.is_tansat:
                    self._step_tansat()

            except Exception as ex:
                if getattr(self.client, "debug", False):
                    print(f"[CombatManager] loop error: {ex}")

            time.sleep(0.15)

    # --------------------------------------------------------------------------
    # 1. HỆ THỐNG TIÊU ĐIỂM (FOCUS SYSTEM)
    # --------------------------------------------------------------------------
    def focus(self, target_type: str = "", query: Optional[Union[int, str]] = None) -> Tuple[bool, str]:
        """
        Nhắm mục tiêu (Focus) vào quái, người chơi hoặc vật phẩm dưới đất.
        Cú pháp:
        - focus mob [id|name]: Focus vào quái (hoặc quái gần nhất nếu để trống)
        - focus char [name|id]: Focus vào người chơi
        - focus item [id]: Focus vào vật phẩm dưới đất
        - focus clear: Hủy toàn bộ focus
        - focus: Xem thông tin đối tượng đang focus
        """
        my_char = self._get_my_char()
        if my_char is None:
            return False, "Chưa đồng bộ nhân vật!"

        t_type = target_type.lower().strip()

        # Xem trạng thái focus hiện tại
        if not t_type:
            kind, target = my_char.get_focused_target()
            if kind is None:
                return True, "Hiện chưa focus vào đối tượng nào."
            if kind == "mob":
                return True, f"Đang focus Quái: ID={target.mobId}, Template={target.templateId}, HP={target.hp:,}/{target.maxHp:,} tại ({target.x},{target.y})"
            if kind == "char":
                return True, f"Đang focus Người chơi: '{target.cName}' (ID={target.charID}), HP={target.cHP:,}/{target.cHPFull:,} tại ({target.cx},{target.cy})"
            if kind == "item":
                return True, f"Đang focus Vật phẩm: MapID={target.itemMapID}, TemplateID={target.template_id} tại ({target.x},{target.y})"
            return True, f"Đang focus {kind}: {target}"

        # Hủy focus
        if t_type in ("clear", "none", "unfocus", "defocus"):
            my_char.clear_focus()
            return True, "Đã hủy bỏ toàn bộ tiêu điểm focus."

        # Focus Quái
        if t_type in ("mob", "quai", "m"):
            mob = self._find_mob(query)
            if mob is None:
                return False, f"Không tìm thấy quái phù hợp trong map với '{query}'!"
            my_char.focus_mob(mob)
            return True, f"Đã focus Quái ID {mob.mobId} (Template {mob.templateId}, HP: {mob.hp:,}/{mob.maxHp:,}) tại ({mob.x},{mob.y})!"

        # Focus Người chơi
        if t_type in ("char", "player", "nguoi", "c", "p"):
            ch = self._find_char(query)
            if ch is None:
                return False, f"Không tìm thấy người chơi phù hợp trong map với '{query}'!"
            my_char.focus_char(ch)
            return True, f"Đã focus Người chơi '{ch.cName}' (ID: {ch.charID}, HP: {ch.cHP:,}/{ch.cHPFull:,}) tại ({ch.cx},{ch.cy})!"

        # Focus Vật phẩm
        if t_type in ("item", "vatpham", "vp", "i"):
            it = self._find_item(query)
            if it is None:
                return False, f"Không tìm thấy vật phẩm phù hợp trong map với '{query}'!"
            my_char.focus_item(it)
            return True, f"Đã focus Vật phẩm ID {it.itemMapID} (Template {it.template_id}) tại ({it.x},{it.y})!"

        return False, f"Loại mục tiêu không hợp lệ: '{target_type}'. Hỗ trợ: mob, char, item, clear."

    def _find_mob(self, query: Optional[Union[int, str]]) -> Optional[Mob]:
        """Tìm quái vật phù hợp nhất trong map."""
        my_char = self._get_my_char()
        mobs = list(my_char.mapInfo.mobs.values()) if my_char else []
        alive_mobs = [m for m in mobs if getattr(m, "status", 0) not in (0, 1) and getattr(m, "hp", 0) > 0]
        if not alive_mobs:
            return None

        # Nếu không truyền query: lấy quái gần nhất
        if query is None or str(query).strip() == "":
            return min(alive_mobs, key=lambda m: self._calc_distance(my_char.cx, my_char.cy, m.x, m.y))

        # Nếu là số: tìm theo mobId hoặc templateId
        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            val = int(query)
            for m in alive_mobs:
                if m.mobId == val:
                    return m
            for m in alive_mobs:
                if m.templateId == val:
                    return m
            return None

        # Nếu là chuỗi: tìm theo tên quái
        q_str = str(query).lower()
        for m in alive_mobs:
            t_name = getattr(m, "template_name", "")
            if q_str in t_name.lower():
                return m

        return alive_mobs[0]

    def _find_char(self, query: Optional[Union[int, str]]) -> Optional[Char]:
        """Tìm người chơi khác trong map."""
        my_char = self._get_my_char()
        chars = list(my_char.mapInfo.chars.values()) if my_char else []
        other_chars = [c for c in chars if c.charID != my_char.charID]
        if not other_chars:
            return None

        if query is None or str(query).strip() == "":
            return min(other_chars, key=lambda c: self._calc_distance(my_char.cx, my_char.cy, c.cx, c.cy))

        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            val = int(query)
            for c in other_chars:
                if c.charID == val:
                    return c
            return None

        q_str = str(query).lower()
        for c in other_chars:
            if q_str in c.cName.lower():
                return c

        return None

    def _find_item(self, query: Optional[Union[int, str]]) -> Optional[ItemMap]:
        """Tìm vật phẩm rơi dưới đất trong map."""
        my_char = self._get_my_char()
        items = list(my_char.mapInfo.items.values()) if my_char else []
        if not items:
            return None

        if query is None or str(query).strip() == "":
            return min(items, key=lambda it: self._calc_distance(my_char.cx, my_char.cy, it.x, it.y))

        if isinstance(query, int) or (isinstance(query, str) and query.isdigit()):
            val = int(query)
            for it in items:
                if it.itemMapID == val:
                    return it
            for it in items:
                if it.template_id == val:
                    return it

        return None

    # --------------------------------------------------------------------------
    # 2. HỆ THỐNG DỊCH CHUYỂN (TELEPORT SYSTEM)
    # --------------------------------------------------------------------------
    def teleport(self, x: int, y: int) -> bool:
        """
        Dịch chuyển tức thời đến toạ độ (x, y) mô phỏng Utils.TeleportMyChar trong C#.
        Gửi bước đệm đồng bộ toạ độ với máy chủ.
        """
        my_char = self._get_my_char()
        if my_char is None:
            return False

        try:
            # 1. Thiết lập toạ độ đích
            my_char.cx = x
            my_char.cy = y
            self.service.charMove(x, y)

            # 2. Bước đệm chuẩn game NRO: (x, y+1) rồi (x, y)
            my_char.cx = x
            my_char.cy = y + 1
            self.service.charMove(x, y + 1)

            my_char.cx = x
            my_char.cy = y
            self.service.charMove(x, y)
            return True
        except Exception as ex:
            print(f"[CombatManager] teleport error: {ex}")
            return False

    def teleport_to(self, target: Any) -> Tuple[bool, str]:
        """Dịch chuyển tới thực thể chỉ định (Mob, Char, ItemMap, Waypoint hoặc chuỗi truy vấn)."""
        my_char = self._get_my_char()
        if my_char is None:
            return False, "Chưa vào game!"

        if isinstance(target, Mob):
            ok = self.teleport(target.x, target.y)
            return ok, f"Đã tele tới Quái ID {target.mobId} tại ({target.x},{target.y})"

        if isinstance(target, Char):
            ok = self.teleport(target.cx, target.cy)
            return ok, f"Đã tele tới Người chơi '{target.cName}' tại ({target.cx},{target.cy})"

        if isinstance(target, ItemMap):
            ok = self.teleport(target.x, target.y)
            return ok, f"Đã tele tới Vật phẩm ID {target.itemMapID} tại ({target.x},{target.y})"

        if isinstance(target, Waypoint):
            mid_x = (target.minX + target.maxX) // 2
            mid_y = (target.minY + target.maxY) // 2
            ok = self.teleport(mid_x, mid_y)
            return ok, f"Đã tele tới Waypoint '{target.name}' tại ({mid_x},{mid_y})"

        # Nếu không truyền tham số: tele tới mục tiêu đang focus
        if target is None or str(target).strip() == "":
            kind, focus_obj = my_char.get_focused_target()
            if focus_obj:
                return self.teleport_to(focus_obj)
            return False, "Chưa focus vào mục tiêu nào để tele! Hãy truyền toạ độ hoặc đối tượng."

        # Xử lý chuỗi lệnh: "x y" hoặc "mob 1", "char Goku", "wp 0"
        raw = str(target).strip()
        parts = raw.split()
        if len(parts) == 2 and parts[0].lstrip("-").isdigit() and parts[1].lstrip("-").isdigit():
            x, y = int(parts[0]), int(parts[1])
            ok = self.teleport(x, y)
            return ok, f"Đã tele tới toạ độ ({x},{y})"

        if len(parts) >= 2:
            sub = parts[0].lower()
            q = " ".join(parts[1:])
            if sub in ("mob", "quai", "m"):
                m = self._find_mob(q)
                if m:
                    return self.teleport_to(m)
                return False, f"Không tìm thấy quái '{q}'!"
            if sub in ("char", "player", "nguoi", "p", "c"):
                c = self._find_char(q)
                if c:
                    return self.teleport_to(c)
                return False, f"Không tìm thấy người chơi '{q}'!"
            if sub in ("item", "vp", "i"):
                it = self._find_item(q)
                if it:
                    return self.teleport_to(it)
                return False, f"Không tìm thấy item '{q}'!"
            if sub in ("wp", "waypoint", "cong"):
                for wp in my_char.mapInfo.waypoints:
                    if q in wp.name.lower() or (q.isdigit() and int(q) == my_char.mapInfo.waypoints.index(wp)):
                        return self.teleport_to(wp)
                return False, f"Không tìm thấy waypoint '{q}'!"

        # Thử tìm char hoặc mob trùng tên
        c = self._find_char(raw)
        if c:
            return self.teleport_to(c)
        m = self._find_mob(raw)
        if m:
            return self.teleport_to(m)

        return False, f"Không nhận diện được đích đến tele: '{target}'"

    # --------------------------------------------------------------------------
    # 3. HỆ THỐNG TỰ ĐỘNG ĐÁNH (AK - AUTO ATTACK)
    # --------------------------------------------------------------------------
    def toggle_ak(self, enable: Optional[bool] = None) -> bool:
        """Bật / Tắt chế độ Auto Attack (AK) mục tiêu đang focus."""
        if enable is not None:
            self.is_ak = enable
        else:
            self.is_ak = not self.is_ak
        return self.is_ak

    def attack_target(self, target: Any = None) -> bool:
        """Gửi lệnh tấn công mục tiêu (quái hoặc người chơi)."""
        my_char = self._get_my_char()
        if my_char is None:
            return False

        t = target
        if t is None:
            kind, t = my_char.get_focused_target()

        if isinstance(t, Mob):
            self.service.sendPlayerAttack(vMob=[t], vChar=[])
            return True
        elif isinstance(t, Char):
            self.service.sendPlayerAttack(vMob=[], vChar=[t])
            return True
        return False

    def _step_ak(self) -> None:
        """Chu kỳ gửi lệnh đánh mục tiêu đang focus mô phỏng AutoSendAttack.cs."""
        my_char = self._get_my_char()
        if my_char is None:
            return
        is_dead = (my_char.cHPFull > 0 and my_char.cHP <= 0) or getattr(my_char, "statusMe", 1) == 14
        if is_dead:
            return

        if my_char.mobFocus:
            mob = my_char.mobFocus
            if getattr(mob, "hp", 0) > 0 and getattr(mob, "status", 0) not in (0, 1):
                self.service.sendPlayerAttack(vMob=[mob], vChar=[])
            else:
                my_char.mobFocus = None

        elif my_char.charFocus:
            ch = my_char.charFocus
            if getattr(ch, "cHP", 0) > 0:
                self.service.sendPlayerAttack(vMob=[], vChar=[ch])
            else:
                my_char.charFocus = None

    # --------------------------------------------------------------------------
    # 4. HỆ THỐNG TÀN SÁT (SLAUGHTER / AUTO MOB / AUTO PK)
    # --------------------------------------------------------------------------
    def toggle_tansat(self, enable: Optional[bool] = None, mode: str = "mob") -> bool:
        """Bật / Tắt chế độ tàn sát tự động."""
        if enable is not None:
            self.is_tansat = enable
        else:
            self.is_tansat = not self.is_tansat

        if mode:
            self.tansat_mode = mode.lower()
        return self.is_tansat

    def add_mob_target(self, mob_id: int) -> None:
        """Thêm/Xóa quái ID cụ thể khỏi danh sách tàn sát (addm)."""
        if mob_id in self.target_mob_ids:
            self.target_mob_ids.remove(mob_id)
        else:
            self.target_mob_ids.add(mob_id)

    def add_mob_type_target(self, template_id: int) -> None:
        """Thêm/Xóa loại quái template ID khỏi danh sách tàn sát (addtm)."""
        if template_id in self.target_mob_types:
            self.target_mob_types.remove(template_id)
        else:
            self.target_mob_types.add(template_id)

    def clear_mob_targets(self) -> None:
        """Xóa danh sách lọc quái (đánh tất cả quái trong map - clrm)."""
        self.target_mob_ids.clear()
        self.target_mob_types.clear()

    # Bảng skill tàn sát theo hành tinh (ưu tiên: đặc biệt -> chưởng -> đấm)
    TANSAT_SKILLS_BY_GENDER: Dict[int, tuple] = {
        0: (9, 1, 0),    # Trái Đất: kaioken, kamejoko, đấm
        1: (12, 3, 2),   # Namek: trứng, masenko, đấm
        2: (13, 5, 4),   # Xayda: hoá hình, atomic, đấm
    }

    # Cooldown tối thiểu ước lượng cho từng skill đặc biệt (giây).
    # ClientNROpy chưa parse cooldown thật từ server nên dùng giá trị an toàn
    # để không spam skill đặc biệt khi đang hồi, fallback về đấm/chưởng.
    TANSAT_SKILL_COOLDOWN: Dict[int, float] = {
        0: 0.6, 1: 2.0, 9: 8.0,
        2: 0.6, 3: 2.0, 12: 10.0,
        4: 0.6, 5: 2.0, 13: 10.0,
    }

    def _get_tansat_skill_ids(self) -> tuple:
        """Lấy danh sách templateId tàn sát tương ứng hành tinh (cgender)."""
        my_char = self._get_my_char()
        gender = getattr(my_char, "cgender", 0) if my_char else 0
        try:
            gender = int(gender)
        except Exception:
            gender = 0
        return self.TANSAT_SKILLS_BY_GENDER.get(gender, (0, 2, 4))

    def _pick_tansat_skill(self) -> Optional[int]:
        """Chọn 1 skill templateId khả dụng, xoay vòng để dùng cả 3 skill.

        - Ưu tiên skill đặc biệt/chưởng khi hết cooldown, fallback về đấm.
        - Lọc theo char.skills nếu client đã đồng bộ (tránh chọn skill chưa học).
        - Xoay vòng (_tansat_skill_idx) nên không bao giờ kẹt ở 1 skill.
        """
        my_char = self._get_my_char()
        candidates = list(self._get_tansat_skill_ids())
        if not candidates:
            return None
        owned = set(getattr(my_char, "skills", []) or []) if my_char else set()
        # char.skills từ server là skillId; ở nhiều server nó trùng templateId
        # với skill cấp 1 nên lọc mềm: nếu khớp được thì lọc, không thì giữ full.
        filtered = [tid for tid in candidates if tid in owned]
        pool = filtered if filtered else candidates
        now = time.monotonic()
        # Thử xoay vòng trong pool, ưu tiên skill hết cooldown
        for offset in range(len(pool)):
            idx = (self._tansat_skill_idx + offset) % len(pool)
            tid = pool[idx]
            cd = self.TANSAT_SKILL_COOLDOWN.get(tid, 1.0)
            last = self._skill_last_use.get(tid, 0.0)
            if now - last >= cd:
                self._tansat_skill_idx = (idx + 1) % len(pool)
                return tid
        # Tất cả đang cooldown -> fallback về đấm (cuối pool) để không đứng yên
        punch = pool[-1]
        self._tansat_skill_idx = (self._tansat_skill_idx + 1) % len(pool)
        return punch

    def _select_and_attack(self, vMob: Optional[list] = None, vChar: Optional[list] = None) -> bool:
        """selectSkill theo hành tinh rồi mới sendPlayerAttack (fix TS chỉ xài 1 skill)."""
        my_char = self._get_my_char()
        if my_char is None:
            return False
        skill_id = self._pick_tansat_skill()
        if skill_id is not None:
            try:
                current = getattr(my_char, "skillTemplateId", None)
                if current != skill_id:
                    self.service.selectSkill(skill_id)
                    my_char.skillTemplateId = skill_id
                self._skill_last_use[skill_id] = time.monotonic()
            except Exception:
                pass
        try:
            self.service.sendPlayerAttack(vMob=(vMob or []), vChar=(vChar or []))
            return True
        except Exception:
            return False

    def _step_tansat(self) -> None:
        """Vòng lặp tàn sát quái / người chơi, tự nhặt đồ và ăn đậu."""
        my_char = self._get_my_char()
        if my_char is None:
            return

        # 1. Xử lý khi nhân vật chết thật sự (chỉ khi có cHPFull > 0 và cHP <= 0, hoặc statusMe == 14)
        is_dead = (my_char.cHPFull > 0 and my_char.cHP <= 0) or getattr(my_char, "statusMe", 1) == 14
        if is_dead:
            if self.auto_revive:
                self.service.returnTownFromDead()
                time.sleep(1.0)
            return

        # 2. Tự động dùng đậu thần khi HP hoặc KI thấp
        if self.auto_pean:
            needs_hp = my_char.cHPFull > 0 and (my_char.cHP / my_char.cHPFull) < self.pean_threshold
            needs_ki = my_char.cMPFull > 0 and (my_char.cMP / my_char.cMPFull) < self.pean_threshold
            if needs_hp or needs_ki:
                if my_char.magicTree.currPeas > 0:
                    self.service.magicTree(2)

        # 3. Tự động nhặt đồ rơi trong map
        if self.auto_pick and my_char.mapInfo.items:
            valid_items = []
            for it in my_char.mapInfo.items.values():
                if self.pick_gem_only:
                    if it.template_id in (77, 861):
                        valid_items.append(it)
                else:
                    if it.template_id not in self.blocked_items:
                        valid_items.append(it)

            if valid_items:
                # Chọn vật phẩm gần nhất
                nearest_item = min(valid_items, key=lambda it: self._calc_distance(my_char.cx, my_char.cy, it.x, it.y))
                self.teleport(nearest_item.x, nearest_item.y)
                self.service.pickItem(nearest_item.itemMapID)
                time.sleep(0.15)
                return

        # 4. Tàn Sát Quái Vật (Mode 'mob' hoặc 'all')
        if self.tansat_mode in ("mob", "all", "m"):
            mobs = list(my_char.mapInfo.mobs.values())
            candidate_mobs = []
            for m in mobs:
                # Quái phải còn sống
                if getattr(m, "status", 0) in (0, 1) or getattr(m, "hp", 0) <= 0:
                    continue
                # Né siêu quái
                if self.avoid_super_mob and (getattr(m, "isBoss", False) or getattr(m, "hp", 0) > getattr(m, "maxHp", 1) * 1.5):
                    continue
                # Bộ lọc ID quái
                if self.target_mob_ids and m.mobId not in self.target_mob_ids:
                    continue
                # Bộ lọc loại quái
                if self.target_mob_types and m.templateId not in self.target_mob_types:
                    continue
                candidate_mobs.append(m)

            if candidate_mobs:
                target_mob = min(candidate_mobs, key=lambda m: self._calc_distance(my_char.cx, my_char.cy, m.x, m.y))
                my_char.focus_mob(target_mob)
                # Dịch chuyển áp sát quái
                self.teleport(target_mob.x, target_mob.y)
                # Đánh quái (tự chọn skill theo hành tinh: đấm/chưởng/đặc biệt)
                self._select_and_attack(vMob=[target_mob], vChar=[])
                return

        # 5. Tàn Sát Người Chơi (Mode 'player', 'char' hoặc 'all')
        if self.tansat_mode in ("player", "char", "all", "pk", "p"):
            chars = list(my_char.mapInfo.chars.values())
            candidate_chars = []
            for ch in chars:
                if ch.charID == my_char.charID or getattr(ch, "cHP", 0) <= 0:
                    continue
                if self.target_char_names and ch.cName not in self.target_char_names:
                    continue
                if self.target_char_ids and ch.charID not in self.target_char_ids:
                    continue
                candidate_chars.append(ch)

            if candidate_chars:
                target_char = min(candidate_chars, key=lambda c: self._calc_distance(my_char.cx, my_char.cy, c.cx, c.cy))
                my_char.focus_char(target_char)
                self.teleport(target_char.cx, target_char.cy)
                self._select_and_attack(vMob=[], vChar=[target_char])
                return

    # --------------------------------------------------------------------------
    # TIỆN ÍCH TRỢ GIÚP
    # --------------------------------------------------------------------------
    @property
    def service(self) -> Service:
        if self.client and hasattr(self.client, "service") and self.client.service:
            return self.client.service
        return Service.gI()

    def _get_my_char(self) -> Optional[Char]:

        if self.client and hasattr(self.client, "myChar"):
            return self.client.myChar
        return Char.myCharz()

    @staticmethod
    def _calc_distance(x1: int, y1: int, x2: int, y2: int) -> float:
        return math.hypot(x1 - x2, y1 - y2)

    def get_status(self) -> Dict[str, Any]:
        """Lấy toàn bộ trạng thái cấu hình của hệ thống chiến đấu."""
        my_char = self._get_my_char()
        focus_kind, focus_target = my_char.get_focused_target() if my_char else (None, None)
        return {
            "is_ak": self.is_ak,
            "is_tansat": self.is_tansat,
            "tansat_mode": self.tansat_mode,
            "avoid_super_mob": self.avoid_super_mob,
            "auto_pick": self.auto_pick,
            "pick_gem_only": self.pick_gem_only,
            "auto_pean": self.auto_pean,
            "target_mob_ids": list(self.target_mob_ids),
            "target_mob_types": list(self.target_mob_types),
            "focus_kind": focus_kind,
            "focus_target": str(focus_target) if focus_target else None,
        }
