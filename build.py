#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================================
  ClientNROpy - Automated Single-File Compiler (With Custom Icon & UTF-8)
================================================================================
Tự động đóng gói toàn bộ dự án ClientNROpy thành DUY NHẤT 1 FILE EXECUTABLE:
  -> dist/ClientNRO.exe

Đặc tính:
1. Độc lập 100% (Single-File Standalone):
   - Nhúng toàn bộ mã nguồn, Python runtime và các DLL cần thiết.
   - Chỉ cần copy DUY NHẤT 1 file ClientNRO.exe lên Windows/VPS là chạy ngay.
   - Không cần cài đặt Python hay bất kỳ phần mềm nào khác.
2. Biểu tượng ứng dụng tùy chỉnh (Icon):
   - Tự động chuyển đổi và nhúng icon từ Downloads/ic.jpg hoặc icon.ico.
3. Hiển thị Tiếng Việt UTF-8 chuẩn:
   - Code Page 65001 + TrueType Font (Consolas) trên Windows Server.
   - Giữ màn hình không bị tắt đột ngột khi ngắt kết nối.
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
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
BUILD_DIR = os.path.join(PROJECT_ROOT, "build")
FINAL_EXE = os.path.join(DIST_DIR, "ClientNRO.exe")

# Đường dẫn icon mặc định
DEFAULT_ICON = os.path.join(PROJECT_ROOT, "icon.ico")
DOWNLOADS_IC_JPG = os.path.expanduser(r"~\Downloads\ic.jpg")


def log(msg: str, prefix: str = "[*]"):
    print(f"{prefix} {msg}", flush=True)


def log_success(msg: str):
    log(msg, prefix="[OK]")


def log_error(msg: str):
    log(msg, prefix="[!] ERROR:")


def ensure_icon():
    """Tự động chuyển đổi Downloads/ic.jpg sang icon.ico nếu có."""
    if os.path.exists(DOWNLOADS_IC_JPG):
        try:
            from PIL import Image
            img = Image.open(DOWNLOADS_IC_JPG)
            if img.mode != "RGBA":
                img = img.convert("RGBA")
            img.save(DEFAULT_ICON, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
            log_success(f"Đã cập nhật icon ứng dụng từ: {DOWNLOADS_IC_JPG}")
        except Exception as ex:
            log(f"Cảnh báo khi chuyển đổi icon: {ex}")


def clean_redundant_files():
    """Xoá sạch các thư mục thừa và file trung gian."""
    log("Dọn dẹp các thư mục thừa và file trung gian...")

    targets = [
        BUILD_DIR,
        os.path.join(DIST_DIR, "ClientNRO_Universal"),
        os.path.join(DIST_DIR, "Cai_Dat_VPS"),
        os.path.join(DIST_DIR, "launcher.dist"),
        os.path.join(DIST_DIR, "launcher.build"),
        os.path.join(PROJECT_ROOT, "universal_deps"),
    ]
    for t in targets:
        if os.path.exists(t):
            try:
                shutil.rmtree(t)
                log(f"  - Đã xoá: {t}")
            except Exception as ex:
                log(f"  - Cảnh báo khi xoá {t}: {ex}")

    for item in os.listdir(DIST_DIR) if os.path.exists(DIST_DIR) else []:
        if item.endswith(".zip") or (item.endswith(".exe") and item != "ClientNRO.exe"):
            try:
                os.remove(os.path.join(DIST_DIR, item))
                log(f"  - Đã xoá file cũ: {item}")
            except Exception:
                pass

    for item in os.listdir(PROJECT_ROOT):
        if item.endswith(".spec") or item.endswith(".build") or item.endswith(".dist"):
            p = os.path.join(PROJECT_ROOT, item)
            try:
                if os.path.isdir(p):
                    shutil.rmtree(p)
                else:
                    os.remove(p)
                log(f"  - Đã xoá file tạm: {item}")
            except Exception:
                pass


def check_environment():
    """Kiểm tra môi trường build."""
    log("Kiểm tra công cụ đóng gói...")
    try:
        import PyInstaller
        log(f"  - PyInstaller Version: {PyInstaller.__version__}")
    except ImportError:
        log_error("Chưa cài đặt PyInstaller! Vui lòng chạy: pip install pyinstaller")
        sys.exit(1)

    if not os.path.exists(ENTRY_SCRIPT):
        log_error(f"Không tìm thấy entrypoint: {ENTRY_SCRIPT}")
        sys.exit(1)

    log_success("Môi trường sẵn sàng để đóng gói 1 file duy nhất!")


def build_single_file(custom_icon: str = None) -> str:
    """Đóng gói toàn bộ dự án thành 1 file ClientNRO.exe duy nhất."""
    os.makedirs(DIST_DIR, exist_ok=True)
    ensure_icon()

    log("=" * 70)
    log(" BẮT ĐẦU ĐÓNG GÓI 1 FILE EXECUTABLE DUY NHẤT VỚI ICON TÙY CHỈNH")
    log("=" * 70)
    log(f"  - Entrypoint:      {ENTRY_SCRIPT}")
    log(f"  - Thư mục xuất:    {DIST_DIR}")
    log(f"  - File đích:       {FINAL_EXE}")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--onefile",
        "--noconfirm",
        "--name=ClientNRO",
        "--collect-all=ClientNROpy",
    ]

    # Cài đặt Icon
    icon_to_use = custom_icon if custom_icon and os.path.exists(custom_icon) else DEFAULT_ICON
    if os.path.exists(icon_to_use):
        log(f"  - Nhúng Icon:      {icon_to_use}")
        cmd.extend(["--icon", icon_to_use])
    else:
        log("  - Cảnh báo: Không tìm thấy icon tùy chỉnh, sử dụng mặc định.")

    cmd.append(ENTRY_SCRIPT)

    log("\nĐang thực thi lệnh đóng gói PyInstaller...")
    start_time = time.time()
    try:
        subprocess.run(cmd, cwd=PROJECT_ROOT, check=True)
    except subprocess.CalledProcessError as err:
        log_error(f"Quá trình build thất bại với mã lỗi: {err.returncode}")
        sys.exit(err.returncode)

    elapsed = time.time() - start_time
    log_success(f"Đóng gói hoàn tất trong {elapsed:.1f} giây!")

    # Dọn dẹp thư mục build tạm thời và file .spec
    if os.path.exists(BUILD_DIR):
        try:
            shutil.rmtree(BUILD_DIR)
        except Exception:
            pass
    spec_path = os.path.join(PROJECT_ROOT, "ClientNRO.spec")
    if os.path.exists(spec_path):
        try:
            os.remove(spec_path)
        except Exception:
            pass

    if os.path.exists(FINAL_EXE):
        size_mb = os.path.getsize(FINAL_EXE) / (1024 * 1024)
        log_success(f"Tạo thành công 1 file duy nhất: {FINAL_EXE} ({size_mb:.2f} MB)")
        return FINAL_EXE
    else:
        log_error(f"Không tìm thấy file kết quả tại {FINAL_EXE}!")
        sys.exit(1)


def run_tests(target_exe: str):
    """Kiểm thử tự động trên file thực thi."""
    log("=" * 70)
    log(" BẮT ĐẦU KIỂM THỬ TỰ ĐỘNG FILE EXECUTABLE")
    log("=" * 70)

    log("\n[TEST 1/2] Kiểm thử cờ --help và hiển thị Tiếng Việt UTF-8...")
    try:
        res = subprocess.run([target_exe, "--help"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=30)
        if res.returncode == 0 and "HƯỚNG DẪN SỬ DỤNG CLIENT NRO" in res.stdout:
            log_success("Test --help: PASSED! Tiếng Việt có dấu hiển thị chuẩn xác!")
        else:
            log_error(f"Test --help thất bại (Code {res.returncode}):\n{res.stderr}")
            sys.exit(1)
    except Exception as ex:
        log_error(f"Lỗi test --help: {ex}")
        sys.exit(1)

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
        log_error(f"Lỗi test --test-xmap: {ex}")
        sys.exit(1)

    log("\n" + "=" * 70)
    log_success("TẤT CẢ CÁC BƯỚC KIỂM THỬ ĐÃ THÀNH CÔNG VƯỢT TRỘI 100%!")
    log("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description="ClientNROpy - Single-File Packager with Custom Icon & UTF-8",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        default=True,
        help="Dọn dẹp sạch sẽ các file tạm và thư mục cũ (mặc định: bật).",
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

    clean_redundant_files()
    check_environment()
    target_exe = build_single_file(custom_icon=args.icon)

    if args.test and target_exe:
        run_tests(target_exe)

    log("\n" + "=" * 70)
    log_success("HOÀN TẤT! BẠN CHỈ CẦN COPY DUY NHẤT 1 FILE SAU LÊN VPS ĐỂ CHẠY:")
    log(f"   =>  {target_exe}")
    log("=" * 70 + "\n")


if __name__ == "__main__":
    main()
