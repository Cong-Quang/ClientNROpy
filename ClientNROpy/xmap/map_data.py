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
    12: "Vực maima",
    13: "Đảo Guru",
    14: "Làng Kakarot",
    15: "Đồi hoang",
    16: "Làng Plant",
    17: "Rừng nguyên sinh",
    18: "Rừng thông Xayda",
    19: "Thành phố Vegeta",
    20: "Vách núi đen",
    21: "Nhà Gôhan",
    22: "Nhà Moori",
    23: "Nhà Broly",
    24: "Trạm tàu vũ trụ",
    25: "Trạm tàu vũ trụ",
    26: "Trạm tàu vũ trụ",
    27: "Rừng Bamboo",
    28: "Rừng dương xỉ",
    29: "Nam Kamê",
    30: "Đảo Bulông",
    31: "Núi hoa vàng",
    32: "Núi hoa tím",
    33: "Nam Guru",
    34: "Đông Nam Guru",
    35: "Rừng cọ",
    36: "Rừng đá",
    37: "Thung lũng đen",
    38: "Bờ vực đen",
    39: "Vách núi Aru",
    40: "Vách núi Moori",
    41: "Vực Plant",
    42: "Vách núi Aru",
    43: "Vách núi Moori",
    44: "Vách núi Kakarot",
    45: "Thần điện",
    46: "Tháp Karin",
    47: "Rừng Karin",
    48: "Hành tinh Kaio",
    49: "Phòng tập thời gian",
    50: "Thánh địa Kaio",
    51: "Đấu trường",
    52: "Đại hội võ thuật",
    53: "Tường thành 1",
    54: "Tầng 3",
    55: "Tầng 1",
    56: "Tầng 2",
    57: "Tầng 4",
    58: "Tường thành 2",
    59: "Tường thành 3",
    60: "Trại độc nhãn 1",
    61: "Trại độc nhãn 2",
    62: "Trại độc nhãn 3",
    63: "Trại lính Fide",
    64: "Núi dây leo",
    65: "Núi cây quỷ",
    66: "Trại qủy già",
    67: "Vực chết",
    68: "Thung lũng Nappa",
    69: "Vực cấm",
    70: "Núi Appule",
    71: "Căn cứ Raspberry",
    72: "Thung lũng Raspberry",
    73: "Thung lũng chết",
    74: "Đồi cây Fide",
    75: "Khe núi tử thần",
    76: "Núi đá",
    77: "Rừng đá",
    78: "Lãnh  địa Fize",
    79: "Núi khỉ đỏ",
    80: "Núi khỉ vàng",
    81: "Hang quỷ chim",
    82: "Núi khỉ đen",
    83: "Hang khỉ đen",
    84: "Siêu Thị",
    85: "Hành tinh M-2",
    86: "Hành tinh Polaris",
    87: "Hành tinh Cretaceous",
    88: "Hành tinh Monmaasu",
    89: "Hành tinh Rudeeze",
    90: "Hành tinh Gelbo",
    91: "Hành tinh Tigere",
    92: "Thành phố phía đông",
    93: "Thành phố phía nam",
    94: "Đảo Balê",
    95: "Hành tinh Bill 2",
    96: "Cao nguyên",
    97: "Thành phố phía bắc",
    98: "Ngọn núi phía bắc",
    99: "Thung lũng phía bắc",
    100: "Thị trấn Ginder",
    101: "Nhà Bunma",
    102: "Nhà Bunma",
    103: "Võ đài Xên bọ hung",
    104: "Sân sau siêu thị",
    105: "Cánh đồng tuyết",
    106: "Rừng tuyết",
    107: "Núi tuyết",
    108: "Dòng sông băng",
    109: "Rừng băng",
    110: "Hang băng",
    111: "Đông Nam Karin",
    112: "Võ đài Hạt Mít",
    113: "Đại hội võ thuật",
    114: "Cổng phi thuyền",
    115: "Phòng chờ",
    116: "Thánh địa Kaio",
    117: "Cửa Ải 1",
    118: "Cửa Ải 2",
    119: "Cửa Ải 3",
    120: "Phòng chỉ huy",
    121: "Đấu trường",
    122: "Ngũ Hành Sơn",
    123: "Ngũ Hành Sơn",
    124: "Ngũ Hành Sơn",
    125: "Võ đài Bang",
    126: "Thành phố Santa",
    127: "Cổng phi thuyền",
    128: "Bụng Mabư",
    129: "Đại hội võ thuật",
    130: "Đại hội võ thuật Vũ Trụ",
    131: "Hành Tinh Yardart",
    132: "Hành Tinh Yardart 2",
    133: "Hành Tinh Yardart 3",
    134: "Đấu Trường Jiren",
    135: "Động hải tặc",
    136: "Hang Bạch Tuộc",
    137: "Động kho báu",
    138: "Cảng hải tặc",
    139: "Hành tinh Potaufeu",
    140: "Hang động Potaufeu",
    141: "Con đường rắn độc",
    142: "Con đường rắn độc",
    143: "Con đường rắn độc",
    144: "Hoang mạc",
    145: "Võ Đài Siêu Cấp",
    146: "Tây Karin",
    147: "Sa mạc",
    148: "Lâu đài Lychee",
    149: "Thành phố Santa",
    150: "Lôi Đài",
    151: "Hành tinh bóng tối",
    152: "Vùng đất băng giá",
    153: "Lãnh địa bang hội",
    154: "Hành tinh Bill",
    155: "Hành tinh ngục tù",
    156: "Tây thánh địa",
    157: "Đông thánh Địa",
    158: "Bắc thánh địa",
    159: "Nam thánh Địa",
    160: "Khu hang động",
    161: "Bìa rừng nguyên thủy",
    162: "Rừng nguyên thủy",
    163: "Làng Plant nguyên thủy",
    164: "Tranh ngọc Namếc",
    165: "Map Boss",
    166: "Hành tinh ngục tù",
    167: "Địa ngục tầng 1",
    168: "Địa ngục tầng 2",
    169: "Địa ngục tầng 3",
    170: "Cổng địa ngục",
    171: "Đảo heo",
    172: "Đảo khỉ",
    173: "Vườn táo",
    174: "Vườn nho",
    175: "Vườn hoa",
    176: "Rừng cấm",
    177: "Thành Phố Xayda",
    178: "Thành Phố Cold",
    179: "Vùng đất 01",
    180: "Hang sói",
    181: "Vùng đất 02",
    182: "Map chiến trường",
    183: "Cánh đồng chiến thắng",
    198: "Làng Vamchar",
    199: "Vũ Trụ Số 9",
    206: "Địa Ngục",
    213: "Thánh địa Kakarot",
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
    (["Ngũ Hành Sơn", "NHS"], [122, 123, 124]),
    (["Siêu thị", "SieuThi"], [84, 104]),
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

    # 1. Alias Nhà (tự động theo hành tinh cgender: 0->Gohan, 1->Moori, 2->Broly)
    if norm in ("nha", "home", "ve nha", "ve nha gohan", "ve nha moori", "ve nha broly",
                "moori house", "gohan house", "broly house", "house", "nha gohan", "nha moori", "nha broly"):
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

    # 7b. Alias Ngũ Hành Sơn (122/123/124) và Sân sau siêu thị (104)
    if norm in ("ngu hanh son", "nhs", "ngu hanh son 1", "nhs 1"):
        return 122
    if norm in ("ngu hanh son 2", "nhs 2"):
        return 123
    if norm in ("ngu hanh son 3", "nhs 3"):
        return 124
    if norm in ("san sau sieu thi", "san sau", "sieu thi sau"):
        return 104

    # 8. Alias các map mới của TDStudio
    if norm in ("dia nguc", "hell"):
        return 206

    if norm in ("vu tru so 9", "vu tru 9", "universe 9"):
        return 199

    if norm in ("lang vamchar", "vamchar"):
        return 198

    if norm in ("dau truong jiren", "jiren"):
        return 134

    if norm in ("hanh tinh nguc tu", "nguc tu"):
        return 155

    if norm in ("hanh tinh bill", "bill", "beerus"):
        return 154

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
