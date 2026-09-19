# -*- coding: utf-8 -*-
"""
Mô hình ItemOption mô phỏng ItemOption.cs trong C#.
"""

# Bảng tra cứu tên Option trang bị phổ biến trong Ngọc Rồng Online
OPTION_TEMPLATES = {
    0: "Tấn công +{param}",
    1: "HP +{param}k",
    2: "HP, KI +{param}k",
    5: "Sức đánh chí mạng +{param}%",
    6: "HP +{param}",
    7: "KI +{param}",
    8: "Hút {param}% HP, KI từ quái",
    9: "Hút {param}% HP từ người",
    10: "Hút {param}% KI từ người",
    14: "Chí mạng +{param}%",
    18: "Chính xác +{param}%",
    19: "Tấn công quái +{param}%",
    22: "HP +{param}%",
    23: "KI +{param}%",
    27: "Giáp +{param}",
    28: "Giáp +{param}%",
    30: "Không thể giao dịch",
    47: "Giáp +{param}",
    50: "Tấn công +{param}%",
    73: "Biến {param}% tấn công thành HP",
    77: "HP +{param}%",
    80: "Hồi {param}% HP/KI mỗi 30s",
    81: "Hồi {param}% KI mỗi 30s",
    88: "Tốc độ chạy +{param}%",
    93: "Hạn sử dụng: {param} ngày",
    94: "Giáp xạ thủ +{param}%",
    95: "Biến {param}% sát thương thành KI",
    96: "Phản {param}% sát thương",
    97: "Phản {param}% sát thương chưởng",
    98: "Xuyên giáp {param}% chưởng",
    99: "Xuyên giáp {param}% cận chiến",
    100: "Vàng rơi +{param}%",
    101: "Tiềm năng, sức mạnh +{param}%",
    102: "Cấp sao pha lê: {param}",
    103: "KI +{param}%",
    107: "Chỉ số may mắn +{param}%",
    108: "Né đòn +{param}%",
    131: "Kích hoạt trang bị set: {param}",
    143: "Chỉ số phụ: {param}",
    147: "Sức đánh +{param}%",
    210: "Chỉ số đặc biệt: {param}",
}


class ItemOption:
    """Tùy chọn / chỉ số của vật phẩm (chỉ số sao pha lê, % sức đánh, HP, v.v.)."""

    def __init__(self, option_id: int = 0, param: int = 0):
        self.option_id: int = option_id
        self.param: int = param

    def getText(self) -> str:
        """Định dạng chuỗi hiển thị chỉ số option dễ đọc."""
        fmt = OPTION_TEMPLATES.get(self.option_id)
        if fmt:
            try:
                return fmt.format(param=self.param)
            except Exception:
                pass
        return f"Option {self.option_id}: +{self.param}"

    def __repr__(self) -> str:
        return self.getText()
