# -*- coding: utf-8 -*-
"""
Dữ liệu danh mục bản đồ Ngọc Rồng Online (Dragonboy) và bộ phân giải tên/ID.
Hỗ trợ tìm kiếm map bằng ID, tên tiếng Việt có dấu/không dấu, hoặc alias tắt ("nha", "home", v.v.).
"""

import re
import unicodedata
from typing import Dict, List, Optional, Union, Tuple

# Danh bạ chuẩn Map ID -> Tên bản đồ Tiếng Việt trong Ngọc Rồng Online
MAP_NAMES: Dict[int, str] = {
    0: "Làng Aru",
    1: "Đồi hoa cúc",
    2: "Thung lũng tre",
    3: "Rừng nấm",
    4: "Rừng xương",
    5: "Đảo Kamê",
    6: "Đông Karin",
    7: "Làng Mori",
    8: "Đồi nấm tím",
    9: "Thị trấn Moori",
    10: "Thung lũng Namếc",
    11: "Thung lũng Maima",
    12: "Vực Maima",
    13: "Đảo Guru",
    14: "Làng Kakarot",
    15: "Đồi hoang",
    16: "Làng Plant",
    17: "Rừng đá",
    18: "Rừng cọ",
    19: "Thành phố Vegeta",
    20: "Vực cấm",
    21: "Nhà Gohan",
    22: "Nhà Moori",
    23: "Nhà Broly",
    24: "Trạm tàu vũ trụ Trái Đất",
    25: "Trạm tàu vũ trụ Namếc",
    26: "Trạm tàu vũ trụ Xayda",
    27: "Rừng Bamboo",
    28: "Rừng Dương Xỉ",
    29: "Nam Kamê",
    30: "Đảo Bulma",
    31: "Núi hoa vàng",
    32: "Núi hoa tím",
    33: "Nam Guru",
    34: "Đông Nam Guru",
    35: "Rừng Nguyên Sinh",
    36: "Rừng Thông",
    37: "Thung lũng Nappa",
    38: "Vực Nappa",
    39: "Vách núi Aru",
    40: "Vách núi Moori",
    41: "Vách núi Kakarot",
    42: "Vách núi đen",
    43: "Vách núi Namếc",
    44: "Vách núi Xayda",
    45: "Thần điện",
    46: "Tháp Karin",
    47: "Chân tháp Karin",
    48: "Hành tinh Kaio",
    49: "Phòng thời gian",
    50: "Thánh địa Kaio",
    51: "Vực xương",
    52: "Đỉnh núi khỉ đỏ",
    53: "Doanh trại Độc Nhãn",
    54: "Tầng 1",
    55: "Tầng 2",
    56: "Tầng 3",
    57: "Tầng 4",
    58: "Cửa 1",
    59: "Cửa 2",
    60: "Cửa 3",
    61: "Cửa 4",
    62: "Đại bản doanh",
    63: "Thung lũng Nappa",
    64: "Đồi cây Fide",
    65: "Núi cây Fide",
    66: "Rừng cây Fide",
    67: "Thung lũng cây Fide",
    68: "Thung lũng Nappa",
    69: "Vực tuyết",
    70: "Cánh đồng tuyết",
    71: "Rừng tuyết",
    72: "Núi tuyết",
    73: "Vực Nappa",
    74: "Rừng đá Nappa",
    75: "Đồi nấm Nappa",
    76: "Thung lũng nấm",
    77: "Thung lũng đen",
    78: "Thung lũng tím",
    79: "Núi khỉ đỏ",
    80: "Núi khỉ vàng",
    81: "Rừng nấm Nappa",
    82: "Núi khỉ đen",
    83: "Hang khỉ đen",
    84: "Siêu thị",
    85: "Đại hội võ thuật 1",
    86: "Đại hội võ thuật 2",
    87: "Đại hội võ thuật 3",
    88: "Đại hội võ thuật 4",
    89: "Đại hội võ thuật 5",
    90: "Đại hội võ thuật 6",
    91: "Đại hội võ thuật 7",
    92: "Thành phố phía đông",
    93: "Thành phố phía nam",
    94: "Thành phố đảo",
    96: "Rừng hoa vàng",
    97: "Rừng tre Tương Lai",
    98: "Thung lũng Tương Lai",
    99: "Rừng thông Tương Lai",
    100: "Thành phố phía bắc",
    101: "Vùng đất băng giá",
    102: "Nhà Trunks",
    103: "Võ đài Xên bọ hung",
    105: "Cánh đồng tuyết",
    106: "Rừng tuyết",
    107: "Núi tuyết",
    108: "Dòng sông băng",
    109: "Rừng băng",
    110: "Hang băng",
    111: "Đồi Fide",
    112: "Võ đài liên vũ trụ",
    113: "Đảo Kho Báu",
    114: "Vách núi đảo kho báu",
    126: "Thành phố Santa",
    131: "Hành tinh Yardrat",
    132: "Hành tinh Yardrat 2",
    133: "Hành tinh Yardrat 3",
    139: "Hành tinh Potaufeu",
    140: "Hang động Potaufeu",
    147: "Động Kho Báu",
    148: "Căn cứ Gas",
    149: "Hành tinh Gas",
    151: "Khí Gas hủy diệt",
    152: "Khí Gas hủy diệt 2",
}

# Các nhóm map theo GroupMapsXmap của Dragonboy
GROUP_MAPS_DEF: List[Tuple[List[str], List[int]]] = [
    (["Xayda", "Saiya"], [44, 23, 14, 15, 16, 17, 18, 20, 19, 35, 36, 37, 38, 26, 52, 84]),
    (["Namec", "Namek"], [43, 22, 7, 8, 9, 11, 12, 13, 10, 31, 32, 33, 34, 25]),
    (["Trái đất", "Earth"], [42, 21, 0, 1, 2, 3, 4, 5, 6, 27, 28, 29, 30, 47, 46, 45, 48, 50, 111, 24]),
    (["Nappa"], [68, 69, 70, 71, 72, 64, 65, 63, 66, 67, 73, 74, 75, 76, 77, 81, 82, 83, 79, 80]),
    (["Yardrat"], [131, 132, 133]),
    (["Tương lai", "Future"], [102, 92, 93, 94, 96, 97, 98, 99, 100, 103]),
    (["Cold"], [109, 108, 107, 110, 106, 105]),
    (["Potaufeu"], [139, 140]),
    (["Doanh trại", "Barracks"], [53, 58, 59, 60, 61, 62, 55, 56, 54, 57]),
    (["Khí Gas", "Gas"], [149, 147, 152, 151, 148]),
]


def normalize_str(s: str) -> str:
    """Chuyển đổi chuỗi về dạng chữ thường, không dấu tiếng Việt và chuẩn hoá khoảng trắng."""
    if not s:
        return ""
    s = s.strip().lower()
    # Chuyển ký tự đ/Đ
    s = s.replace("đ", "d").replace("Đ", "d")
    # Khử dấu Unicode NFD
    nfkd = unicodedata.normalize("NFD", s)
    no_accent = "".join([c for c in nfkd if not unicodedata.combining(c)])
    # Xoá ký tự đặc biệt thừa
    return re.sub(r"\s+", " ", no_accent).strip()


def get_map_name(map_id: int) -> str:
    """Lấy tên tiếng Việt của Map theo ID."""
    return MAP_NAMES.get(map_id, f"Bản đồ {map_id}")


def resolve_map_id(query: Union[int, str], cgender: int = 0) -> Optional[int]:
    """
    Phân giải chuỗi nhập từ người dùng hoặc số ID thành map_id hợp lệ.
    Hỗ trợ:
    - Số ID trực tiếp: 0, 6, 7, 19, 45, 82, 100, 109...
    - Từ khóa alias: 'nha', 'home', 'lang', 'ttvt' (phụ thuộc vào cgender của nhân vật)
    - Tên map tiếng Việt: 'làng aru', 'dong karin', 'than dien', 'cold'...
    """
    if isinstance(query, int):
        return query

    raw = str(query).strip()
    if not raw:
        return None

    # Nếu là số nguyên
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return int(raw)

    norm = normalize_str(raw)

    # 1. Alias Nhà
    if norm in ("nha", "home", "ve nha", "ve nha gohan", "ve nha moori", "ve nha broly"):
        return 21 + cgender

    # 2. Alias Làng
    if norm in ("lang", "ve lang", "village"):
        return 7 * cgender

    # 3. Alias Trạm tàu vũ trụ
    if norm in ("ttvt", "tram tau", "tram tau vu tru", "station"):
        return 24 + cgender

    # 4. Alias Siêu thị
    if norm in ("sieu thi", "market"):
        return 84

    # 5. Alias Cold
    if norm in ("cold", "hanh tinh cold"):
        return 109

    # 6. Alias Thần điện
    if norm in ("than dien", "thien dinh"):
        return 45

    # 7. Alias Nhà Trunks / Tương lai
    if norm in ("tuong lai", "future", "nha trunks"):
        return 102

    # Tìm kiếm chính xác tên chuẩn (không dấu)
    for mid, name in MAP_NAMES.items():
        if normalize_str(name) == norm:
            return mid

    # Tìm kiếm chuỗi con trong tên chuẩn
    matches = []
    for mid, name in MAP_NAMES.items():
        m_norm = normalize_str(name)
        if norm in m_norm:
            matches.append((mid, m_norm))

    if matches:
        # Ưu tiên chuỗi con bắt đầu bằng norm hoặc ngắn nhất
        matches.sort(key=lambda x: (not x[1].startswith(norm), len(x[1])))
        return matches[0][0]

    return None
