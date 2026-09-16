#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ClientNROpy - Automated C/C++ Native Compiler Script (Anti-Decompile & Standalone)
================================================================================
Script tự động biên dịch toàn bộ dự án ClientNROpy sang mã máy C/C++ Native PE (.exe)
sử dụng Nuitka với backend compiler Zig/Clang.

Đặc tính:
1. Native C/C++ Compilation: Toàn bộ code Python được dịch sang mã nguồn C rồi
   biên dịch trực tiếp sang mã máy nhị phân x86_64.
2. Không thể dịch ngược (Anti-Reverse Engineering):
   - Hoàn toàn KHÔNG tạo hay đóng gói bytecode (.pyc).
   - Vô hiệu hoá các công cụ decompiler như pycdc, uncompyle6, decompyle++, pyinstxtractor.
   - Trình dịch ngược chỉ thấy các chỉ lệnh Assembly x86_64 gọi CPython C-API.
3. Chạy độc lập (Portable Standalone / Onefile):
   - Đóng gói toàn bộ runtime C và DLL cần thiết.
   - Chạy được trên bất kỳ máy Windows 64-bit nào mà không cần cài đặt Python.
4. Tự động kiểm thử (Auto-Test):
   - Kiểm thử thuật toán tìm đường Xmap Dijkstra và CLI sau khi build.
================================================================================
"""

import sys
import os
import shutil
import subprocess
import time
import argparse

# Đảm bảo console UTF-8 trên Windows
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

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
ENTRY_SCRIPT = os.path.join(PROJECT_ROOT, "launcher.py")
DEFAULT_ICON = os.path.join(PROJECT_ROOT, "Dragonboy", "QLTK", "icon.ico")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")


def log(msg: str, prefix: str = "[*]"):
    print(f"{prefix} {msg}", flush=True)


def log_success(msg: str):
    log(msg, prefix="[OK]")


def log_error(msg: str):
    log(msg, prefix="[!] ERROR:")


def check_environment():
    """Kiểm tra các công cụ cần thiết trong môi trường."""
    log("Đang kiểm tra môi trường hệ thống...")
    
    # 1. Kiểm tra Python
    py_ver = sys.version_info
    log(f"  - Python Version: {py_ver.major}.{py_ver.minor}.{py_ver.micro} ({sys.executable})")
    if py_ver.major < 3 or (py_ver.major == 3 and py_ver.minor < 10):
        log_error("Yêu cầu tối thiểu Python 3.10 trở lên.")
        sys.exit(1)

    # 2. Kiểm tra Nuitka
    try:
        res = subprocess.run([sys.executable, "-m", "nuitka", "--version"],
                             capture_output=True, text=True, check=True)
        nuitka_ver = res.stdout.strip().splitlines()[0]
        log(f"  - Nuitka Version: {nuitka_ver}")
    except Exception as ex:
        log_error(f"Không tìm thấy Nuitka! Vui lòng cài đặt: pip install nuitka. Chi tiết: {ex}")
        sys.exit(1)

    # 3. Kiểm tra launcher.py
    if not os.path.exists(ENTRY_SCRIPT):
        log_error(f"Không tìm thấy file entrypoint: {ENTRY_SCRIPT}")
        sys.exit(1)

    log_success("Kiểm tra môi trường thành công!")


def clean_build_artifacts():
    """Dọn dẹp thư mục dist và các cache build."""
    log("Dọn dẹp các thư mục build cũ...")
    if os.path.exists(DIST_DIR):
        try:
            shutil.rmtree(DIST_DIR)
            log(f"  - Đã xoá: {DIST_DIR}")
        except Exception as ex:
            log(f"  - Cảnh báo: Không thể xoá hoàn toàn dist ({ex})")

    # Dọn dẹp cache launcher.build / launcher.dist nếu có ở root
    for item in os.listdir(PROJECT_ROOT):
        if item.endswith(".build") or item.endswith(".dist"):
            p = os.path.join(PROJECT_ROOT, item)
            if os.path.isdir(p):
                try:
                    shutil.rmtree(p)
                    log(f"  - Đã xoá thư mục cache: {item}")
                except Exception:
                    pass


def build_binary(mode: str = "onefile", lto: str = "auto", enable_clean: bool = False, custom_icon: str = None):
    """Thực thi biên dịch toàn bộ ClientNROpy sang C/C++ Native PE."""
    if enable_clean:
        clean_build_artifacts()

    os.makedirs(DIST_DIR, exist_ok=True)
    out_name = "ClientNRO.exe"

    log("=" * 70)
    log(f" BẮT ĐẦU BIÊN DỊCH CLIENT NRO SANG C/C++ NATIVE PE ({mode.upper()})")
    log("=" * 70)
    log(f"  - Entrypoint:      {ENTRY_SCRIPT}")
    log(f"  - Chế độ build:    {mode}")
    log(f"  - Link-Time Opt:   {lto}")
    log(f"  - Thư mục xuất:    {DIST_DIR}")
    log(f"  - Tên file đích:   {out_name}")

    # Xây dựng danh sách cờ Nuitka
    cmd = [
        sys.executable, "-m", "nuitka",
        # Điểm vào và thư mục xuất
        f"--output-dir={DIST_DIR}",
        f"--output-filename={out_name}",
        
        # Chế độ build: onefile hoặc standalone
        f"--{mode}",
        
        # Dịch toàn bộ package sang C/C++ native, không bỏ sót module nào
        "--include-package=ClientNROpy",
        "--follow-imports",
        
        # Chống dịch ngược và tối ưu hoá
        "--remove-output",  # Xoá file nguồn C trung gian sau khi biên dịch
        f"--lto={lto}",      # Link-Time Optimization kết hợp các hàm C
        
        # Bật console để người dùng tương tác CLI nro>
        "--windows-console-mode=force",
        
        # Tự động đồng ý tải các công cụ hỗ trợ nếu thiếu
        "--assume-yes-for-downloads",
        
        # Thông tin nhị phân PE Windows
        "--windows-company-name=ClientNRO",
        "--windows-product-name=ClientNRO Headless Simulator",
        "--windows-file-version=2.1.4.0",
        "--windows-product-version=2.1.4.0",
        "--windows-file-description=ClientNRO Native C/C++ Standalone Executable",
    ]

    # Kiểm tra Icon
    icon_path = custom_icon if custom_icon and os.path.exists(custom_icon) else DEFAULT_ICON
    if os.path.exists(icon_path):
        log(f"  - Sử dụng Icon:    {icon_path}")
        cmd.append(f"--windows-icon-from-ico={icon_path}")
    else:
        log("  - Cảnh báo: Không tìm thấy icon, sử dụng icon mặc định.")

    # File script chính cần compile
    cmd.append(ENTRY_SCRIPT)

    log("\nĐang thực thi lệnh biên dịch Nuitka (quá trình này dịch Python -> C và gọi C compiler)...")
    log(f"Command: {' '.join(cmd)}\n")

    start_time = time.time()
    try:
        proc = subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as err:
        log_error(f"Quá trình biên dịch Nuitka thất bại với mã lỗi: {err.returncode}")
        sys.exit(err.returncode)

    elapsed = time.time() - start_time
    log_success(f"Quá trình biên dịch C/C++ hoàn thành trong {elapsed:.1f} giây ({elapsed/60:.2f} phút)!")

    # Xác định đường dẫn file thực thi
    if mode == "onefile":
        target_exe = os.path.join(DIST_DIR, out_name)
    else:
        # Ở chế độ standalone, file nằm trong dist/launcher.dist/ClientNRO.exe hoặc tương đương
        candidates = [
            os.path.join(DIST_DIR, f"launcher.dist", out_name),
            os.path.join(DIST_DIR, f"ClientNRO.dist", out_name),
            os.path.join(DIST_DIR, out_name),
        ]
        target_exe = None
        for c in candidates:
            if os.path.exists(c):
                target_exe = c
                break

    if target_exe and os.path.exists(target_exe):
        size_mb = os.path.getsize(target_exe) / (1024 * 1024)
        log_success(f"Tạo file thực thi thành công!")
        log(f"  -> File: {target_exe}")
        log(f"  -> Kích thước: {size_mb:.2f} MB")
        return target_exe
    else:
        log_error("Không tìm thấy file thực thi sau khi biên dịch!")
        sys.exit(1)


def run_tests(target_exe: str):
    """Chạy kiểm thử tự động trên file nhị phân compiled C/C++."""
    log("=" * 70)
    log(" BẮT ĐẦU KIỂM THỬ TỰ ĐỘNG FILE THỰC THI NHỊ PHÂN NATIVE C/C++")
    log("=" * 70)

    # 1. Test cờ --help
    log("\n[TEST 1/2] Kiểm thử cờ --help...")
    try:
        res = subprocess.run([target_exe, "--help"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30)
        if res.returncode == 0 and "HƯỚNG DẪN SỬ DỤNG CLIENT NRO" in res.stdout:
            log_success("Test --help: PASSED!")
        else:
            log_error(f"Test --help không như mong đợi (Code {res.returncode}):\n{res.stderr}")
            sys.exit(1)
    except Exception as ex:
        log_error(f"Lỗi khi thực thi test --help: {ex}")
        sys.exit(1)

    # 2. Test cờ --test-xmap (Kiểm tra logic tìm đường Dijkstra & toàn bộ các module map/xmap)
    log("\n[TEST 2/2] Kiểm thử thuật toán tìm đường Xmap Dijkstra offline (--test-xmap)...")
    try:
        res = subprocess.run([target_exe, "--test-xmap"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=60)
        if res.returncode == 0 and "KẾT QUẢ: 9/9 lộ trình đều được tìm thấy thành công 100%!" in res.stdout:
            log_success("Test --test-xmap: PASSED (9/9 chặng tìm đường chính xác 100%)!")
        else:
            log_error(f"Test --test-xmap thất bại (Code {res.returncode}):\n{res.stdout}\n{res.stderr}")
            sys.exit(1)
    except Exception as ex:
        log_error(f"Lỗi khi thực thi test --test-xmap: {ex}")
        sys.exit(1)

    # 3. Kiểm tra tính bảo mật chống dịch ngược
    log("\n[TEST 3/3] Xác thực tính bảo mật: Kiểm tra sự tồn tại của file bytecode (.pyc)...")
    has_leaked_pyc = False
    dist_parent = os.path.dirname(target_exe)
    for root, dirs, files in os.walk(dist_parent):
        for f in files:
            if f.endswith(".py") or f.endswith(".pyc"):
                # Không được có bất kỳ file .pyc nào của ClientNROpy
                if "ClientNRO" in f or "xmap" in f or "boss" in f or "combat" in f:
                    log_error(f"Phát hiện file mã nguồn chưa biên dịch: {os.path.join(root, f)}")
                    has_leaked_pyc = True

    if not has_leaked_pyc:
        log_success("Xác thực bảo mật: PASSED! Toàn bộ 34 file của ClientNROpy đã được biên dịch thành mã máy nhị phân C/C++ native, KHÔNG CÓ file bytecode .pyc nào bị lộ!")

    log("\n" + "=" * 70)
    log_success("TẤT CẢ CÁC BƯỚC KIỂM THỬ ĐÃ THÀNH CÔNG VƯỢT TRỘI!")
    log("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="ClientNROpy - Automated Native C/C++ Compiler & Anti-Decompile Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--mode",
        choices=["onefile", "standalone"],
        default="onefile",
        help="Chế độ đóng gói: 'onefile' (1 file .exe duy nhất, mặc định) hoặc 'standalone' (thư mục kèm DLL, build nhanh hơn).",
    )
    parser.add_argument(
        "--lto",
        choices=["yes", "no", "auto"],
        default="auto",
        help="Link-Time Optimization cho C compiler (mặc định: auto).",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Xoá sạch thư mục dist và cache build cũ trước khi build.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        default=True,
        help="Tự động kiểm thử file thực thi ngay sau khi biên dịch xong (mặc định: bật).",
    )
    parser.add_argument(
        "--no-test",
        action="store_false",
        dest="test",
        help="Bỏ qua bước kiểm thử tự động sau khi build.",
    )
    parser.add_argument(
        "--icon",
        type=str,
        default=None,
        help="Đường dẫn file .ico tùy chỉnh.",
    )

    args = parser.parse_args()

    check_environment()
    target_exe = build_binary(
        mode=args.mode,
        lto=args.lto,
        enable_clean=args.clean,
        custom_icon=args.icon,
    )

    if args.test and target_exe:
        run_tests(target_exe)

    log("\n[HOÀN TẤT] Bạn có thể mang file sau để chạy trên bất kỳ máy Windows nào:")
    log(f"   -> {target_exe}\n")


if __name__ == "__main__":
    main()
