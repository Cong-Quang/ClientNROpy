# -*- coding: utf-8 -*-
"""
Bộ nạp và quản lý dữ liệu liên kết đồ thị bản đồ cho Xmap,
mô phỏng XmapData.cs trong Dragonboy C#.
"""

from collections import defaultdict
from typing import Dict, List, Optional
from .xmap_objects import MapNext, TypeMapNext, GroupMap
from .map_data import GROUP_MAPS_DEF

# Dữ liệu liên kết thủ công mô phỏng TextData/LinkMapsXmap.bytes
RAW_LINK_MAPS_XMAP = """
# Trái Đất - Namec
24 25 1 10 namec
25 24 1 11 trái_đất

# Trái Đất - Xayda
24 26 1 10 xayda
26 24 1 12 trái_đất

# Namec - Xayda
25 26 1 11 xayda
26 25 1 12 namec

# Hành tinh -> Siêu thị
24 84 1 10 siêu_thị
25 84 1 11 siêu_thị
26 84 1 12 siêu_thị

# Tpvgt - Nappa
19 68 1 12 nappa
68 19 1 12 tàu_vũ_trụ

# Nappa -> Yadat
80 131 1 60 yadrat
131 80 1 60 núi_khỉ_vàng

# Trái Đất - Tương lai
27 102 1 38 tương_lai
28 102 1 38 tương_lai
29 102 1 38 tương_lai
102 24 1 38 quá_khứ

# Thành phố Vegeta - Thành phố Santa
19 126 1 53 santa
126 19 1 53 tp_vegeta

# Trái Đất - Hành tinh Potaufeu
24 139 1 63 potaufeu
139 24 1 63 trái_đất

# Hành tinh Potaufeu - các hành tinh còn lại
139 25 1 63 namec
139 26 1 63 xayda

# Rừng Bamboo - Tường thành 1
27 53 1 25 tường_thành

# Thần điện - Hành tinh Kaio
45 48 1 19 kaio
48 45 1 20 thần_điện

# Thánh địa Kaio - Hành tinh Kaio
50 48 1 44 0
48 50 1 20 3 thánh_địa

# Trái Đất - Khí Gas
0 149 1 67 khí_gas

# Làng Aru - Ngũ Hành Sơn (NPC 49 Đường Tăng, chọn Đồng ý)
# Chỉ map 0 và map 123 có NPC này. Từ 122/124 phải đi bộ về 123 rồi mới NPC về 0.
0 123 1 49 đồng_ý
123 0 1 49 đồng_ý

# Nhảy toạ độ Thần điện -> Tháp Karin -> Chân tháp
45 46 3 576 552
46 47 3 576 552
"""

# Dữ liệu liên kết tự động qua Waypoint mô phỏng TextData/AutoLinkMapsWaypoint.bytes
RAW_AUTO_LINK_MAPS_WAYPOINT = """
# Trái đất
42 0 1 2 3 4 5 6
3 27 28 29 30
2 24
1 47
5 29
47 111
47 46 45

# Namec
43 7 8 9 11 12 13 10
11 31 32 33 34
9 25
13 33

# Xayda
213 44 14 15 16 17 18 20 19
52 44
17 35
35 36
20 37
37 38
16 26

# Nappa
68 69 70 71 72 64 65 63 66 67 73 74 75 76 77 81 82 83 79 80

# Tương Lai
102 92 93 94 96 97 98 99 100 103

# Cold
109 108 107 110 106
109 105
109 106
106 107
108 105

# Yadat
131 132 133

# Nappa - Cold
80 105

# Hành tinh Potaufeu - Hang động Potaufeu
139 140

# Doanh trại
53 58 59 60 61 62 55 56 54 57
53 27

# Khí Gas
149 147 152 151 148

# Siêu thị - Sân sau siêu thị (cổng đi bộ 2 chiều)
84 104

# Ngũ Hành Sơn (cổng đi bộ 2 chiều theo thứ tự 123-124-122)
123 124 122
"""


class XmapData:
    """
    Quản lý danh sách kề các bước chuyển map và dữ liệu đồ thị Xmap.
    """

    ID_MAP_SIEU_THI: int = 84
    ID_MAP_TPVGT: int = 19
    ID_MAP_TO_COLD: int = 109
    ID_MAP_HOME_BASE: int = 21
    ID_MAP_LANG_BASE: int = 7
    ID_MAP_TTVT_BASE: int = 24

    def __init__(self):
        self.links: Dict[int, List[MapNext]] = defaultdict(list)
        self.groups: List[GroupMap] = []
        self.is_loaded: bool = False

    def load(self, cgender: int = 0, task_id: int = 40) -> None:
        """
        Khởi tạo và nạp toàn bộ cấu trúc liên kết đồ thị.
        cgender: Giới tính nhân vật (0: Trái Đất, 1: Namếc, 2: Xayda)
        task_id: ID nhiệm vụ hiện tại (ảnh hưởng đến việc mở cổng đi Cold từ TPVGT)
        """
        self.links.clear()
        self._load_links_from_text(RAW_LINK_MAPS_XMAP)
        self._load_auto_waypoints_from_text(RAW_AUTO_LINK_MAPS_WAYPOINT)
        self._add_links_home(cgender)
        self._load_link_sieu_thi(cgender)
        self._load_link_to_cold(task_id)
        self._load_groups()
        self.is_loaded = True

    def _load_links_from_text(self, text: str) -> None:
        """Phân tích các liên kết thủ công từ TextData/LinkMapsXmap."""
        for line in text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = []
            for p in line.split():
                if p.lstrip("-").isdigit():
                    parts.append(int(p))
                else:
                    parts.append(p.replace("_", " "))
            if len(parts) < 3:
                continue
            map_start = parts[0]
            to = parts[1]
            type_next = TypeMapNext(parts[2])
            info = parts[3:]
            self.links[map_start].append(MapNext(map_start, to, type_next, info))

    def _load_auto_waypoints_from_text(self, text: str) -> None:
        """Phân tích các chuỗi AutoWaypoint liên kết hai chiều."""
        for line in text.strip().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            chain = [int(p) for p in line.split()]
            length = len(chain)
            for i in range(length):
                m_start = chain[i]
                if i != 0:
                    self.links[m_start].append(MapNext(m_start, chain[i - 1], TypeMapNext.AutoWaypoint, []))
                if i != length - 1:
                    self.links[m_start].append(MapNext(m_start, chain[i + 1], TypeMapNext.AutoWaypoint, []))

    def _add_links_home(self, cgender: int) -> None:
        """Bổ sung liên kết giữa Nhà và Làng xuất phát theo hành tinh nhân vật."""
        map_home = self.ID_MAP_HOME_BASE + cgender
        map_lang = self.ID_MAP_LANG_BASE * cgender
        self.links[map_home].append(MapNext(map_home, map_lang, TypeMapNext.AutoWaypoint, []))
        self.links[map_lang].append(MapNext(map_lang, map_home, TypeMapNext.AutoWaypoint, []))

    def _load_link_sieu_thi(self, cgender: int) -> None:
        """Bổ sung liên kết từ Siêu thị (84) về Trạm tàu vũ trụ của hành tinh tương ứng."""
        map_ttvt = self.ID_MAP_TTVT_BASE + cgender
        # NPC 10 (Quy Lão / Trọng tài), select=0 để về hành tinh
        self.links[self.ID_MAP_SIEU_THI].append(
            MapNext(self.ID_MAP_SIEU_THI, map_ttvt, TypeMapNext.NpcMenu, [10, 0])
        )

    def _load_link_to_cold(self, task_id: int) -> None:
        """Bổ sung liên kết từ Thành phố Vegeta (19) sang Hành tinh Cold (109) nếu đã qua nhiệm vụ 30."""
        if task_id > 30:
            # NPC 12 (Tàu vũ trụ Xayda), select=0 để bay sang Cold
            self.links[self.ID_MAP_TPVGT].append(
                MapNext(self.ID_MAP_TPVGT, self.ID_MAP_TO_COLD, TypeMapNext.NpcMenu, [12, 0])
            )

    def _load_groups(self) -> None:
        """Khởi tạo danh sách các nhóm map."""
        self.groups = [GroupMap(names, maps) for names, maps in GROUP_MAPS_DEF]

    def load_link_map_capsule(
        self,
        current_map: int,
        cgender: int = 0,
        capsule_map_names: Optional[List[str]] = None,
        capsule_item_id: int = 194,
        map_capsule_return: int = -1,
    ) -> None:
        """
        Nạp các liên kết chuyển map trực tiếp từ Capsule vào vị trí map hiện tại.
        Mô phỏng XmapData.LoadLinkMapCapsule() trong Dragonboy C#.
        """
        from .map_data import resolve_map_id

        # 1. Danh mục các điểm đến chuẩn của Capsule VIP (item 194)
        if capsule_item_id == 194:
            standard_capsule_destinations = [
                21 + cgender,  # Về nhà (0: Gohan House, 1: Moori House, 2: Broly House)
                47,            # Rừng Karin
                48,            # Hành tinh Kaio
                154,           # Hành tinh Bill
                0,             # Làng Aru
                7,             # Làng Mori
                14,            # Làng Kakarot
                5,             # Đảo Kame
                20,            # Vách núi đen
                13,            # Đảo Guru
                24 + cgender,  # Trạm tàu vũ trụ
                27,            # Rừng Bamboo
                19,            # Thành phố Vegeta
                79,            # Núi khỉ đỏ
                84,            # Siêu Thị
                83,            # Hang khỉ đen
                155,           # Hành tinh ngục tù
                103,           # Võ đài Xên bọ hung
                206,           # Địa Ngục
                110,           # Hang băng
                199,           # Vũ Trụ Số 9
                198,           # Làng Vamchar
            ]
        else:
            # Capsule Thường (item 193)
            standard_capsule_destinations = [
                21 + cgender,  # Về nhà
                24 + cgender,  # Trạm tàu vũ trụ
            ]
            if map_capsule_return != -1 and map_capsule_return != current_map:
                standard_capsule_destinations.append(map_capsule_return)

        dest_set = set(standard_capsule_destinations)

        # 2. Nếu có danh sách map từ server qua cmd -91, bổ sung thêm
        if capsule_map_names:
            for name in capsule_map_names:
                to_id = resolve_map_id(name, cgender=cgender)
                if to_id is not None:
                    dest_set.add(to_id)

        for to_id in dest_set:
            if to_id != current_map:
                if not any(step.to == to_id and step.type == TypeMapNext.Capsule for step in self.links[current_map]):
                    self.links[current_map].append(
                        MapNext(current_map, to_id, TypeMapNext.Capsule, [capsule_item_id])
                    )
