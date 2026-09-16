#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ClientNRO Launcher - Native Standalone Entrypoint
Điểm chạy chính khi biên dịch sang Native C/C++ Binary bằng Nuitka.
"""
import sys
import os

# Đảm bảo console Windows hỗ trợ tiếng Việt UTF-8
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Thêm thư mục gốc vào PYTHONPATH nếu đang chạy dạng script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ClientNROpy.main import main

if __name__ == "__main__":
    main()
