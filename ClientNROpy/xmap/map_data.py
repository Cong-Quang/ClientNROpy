# -*- coding: utf-8 -*-
"""
Dữ liệu danh mục bản đồ Ngọc Rồng Online (Dragonboy) và bộ phân giải tên/ID.
Hỗ trợ tìm kiếm map bằng ID, tên tiếng Việt có dấu/không dấu, hoặc alias tắt ("nha", "home", v.v.).
"""

import re
import unicodedata
from typing import Dict, List, Optional, Union, Tuple

# Danh bạ chuẩn Map ID -> Tên bản đồ Tiếng Việt (trỏ từ game_data.py)
from ..game_data import MAP_NAMES, get_map_name

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

    # 7c. Alias Mê cung chết chóc = Vực chết (Map 67)
    if norm in ("me cung chet choc", "me cung", "me cung chet", "vuc chet"):
        return 67

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
