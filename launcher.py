#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClientNRO Launcher - Universal Single-File Entrypoint
Điểm chạy chính cho file ClientNRO.exe độc lập duy nhất.
Tự động cấu hình Console UTF-8 (Code Page 65001 + TrueType Font) để hiển thị Tiếng Việt có dấu chuẩn 100%.
Giữ màn hình không bao giờ bị tắt đột ngột khi gặp sự cố.
"""
import sys
import os
import ctypes
import traceback


def configure_windows_console():
    """
    Cấu hình toàn diện cho Windows Console (CMD / PowerShell / WinServer)
    để hỗ trợ hiển thị Tiếng Việt UTF-8 hoàn hảo và tránh lỗi font dấu hỏi '?'.
    """
    if sys.platform != "win32":
        return

    # 1. Đặt biến môi trường UTF-8 cho Python
    os.environ["PYTHONIOENCODING"] = "utf-8"

    # 2. Đặt Code Page của Console Windows sang 65001 (UTF-8)
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except Exception:
        try:
            os.system("chcp 65001 >nul")
        except Exception:
            pass

    # 3. Đổi font Console sang TrueType font (Consolas) nếu đang dùng Raster Font (font mặc định trên WinServer)
    try:
        class COORD(ctypes.Structure):
            _fields_ = [("X", ctypes.c_short), ("Y", ctypes.c_short)]

        class CONSOLE_FONT_INFOEX(ctypes.Structure):
            _fields_ = [
                ("cbSize", ctypes.c_ulong),
                ("nFont", ctypes.c_ulong),
                ("dwFontSize", COORD),
                ("FontFamily", ctypes.c_uint),
                ("FontWeight", ctypes.c_uint),
                ("FaceName", ctypes.c_wchar * 32)
            ]

        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        font_info = CONSOLE_FONT_INFOEX()
        font_info.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
        if kernel32.GetCurrentConsoleFontEx(handle, False, ctypes.byref(font_info)):
            face = font_info.FaceName.lower()
            # Raster fonts hoặc font rỗng không có bảng mã Unicode Tiếng Việt
            if "raster" in face or face == "" or "terminal" in face:
                new_font = CONSOLE_FONT_INFOEX()
                new_font.cbSize = ctypes.sizeof(CONSOLE_FONT_INFOEX)
                new_font.dwFontSize.X = 0
                new_font.dwFontSize.Y = 16
                new_font.FontFamily = 54  # TMPF_VECTOR | FF_MODERN
                new_font.FontWeight = 400
                new_font.FaceName = "Consolas"
                kernel32.SetCurrentConsoleFontEx(handle, False, ctypes.byref(new_font))
    except Exception:
        pass

    # 4. Reconfigure stdout, stderr, stdin sang UTF-8
    for stream in (sys.stdout, sys.stderr, sys.stdin):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


# Gọi cấu hình console trước mọi xử lý khác
configure_windows_console()

# Thêm thư mục gốc vào PYTHONPATH nếu đang chạy dạng script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ClientNROpy.main import main


def safe_entry():
    exit_code = 0
    try:
        main()
    except SystemExit as se:
        exit_code = se.code if se.code is not None else 0
    except Exception as ex:
        exit_code = 1
        print("\n" + "=" * 70)
        print(" [!] ĐÃ XẢY RA LỖI TRONG QUÁ TRÌNH THỰC THI:")
        print("=" * 70)
        traceback.print_exc()
        print("=" * 70)
    finally:
        # Nếu mở trực tiếp bằng click đúp trên Windows và không truyền --no-cli
        # luôn giữ màn hình để người dùng đọc được toàn bộ thông báo và nguyên nhân
        is_direct_double_click = "--no-cli" not in sys.argv and "--test-xmap" not in sys.argv and "--help" not in sys.argv and "-h" not in sys.argv
        if is_direct_double_click:
            try:
                print("\n" + "=" * 70)
                input(">> Nhấn phím [Enter] để đóng cửa sổ...")
            except Exception:
                pass
    sys.exit(exit_code)


if __name__ == "__main__":
    safe_entry()
