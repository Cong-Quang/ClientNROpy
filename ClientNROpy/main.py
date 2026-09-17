#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Điểm chạy chính của Client NRO Headless Simulator (main.py).
Hỗ trợ:
1. Đa tài khoản cùng lúc (Multi-Account Orchestrator)
2. Chạy qua Proxy (SOCKS5 & HTTP CONNECT thuần Python, tỷ lệ 4 acc / 1 proxy)
3. Console sạch sẽ, không spam log, dễ dàng điều khiển
4. Tương thích ngược 100% với cách chạy 1 tài khoản đơn lẻ truyền thống
"""

import sys
import os
import time

# Đảm bảo console Windows hỗ trợ in Unicode tiếng Việt
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

# Thêm thư mục gốc vào PYTHONPATH nếu cần
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from ClientNROpy.account_manager import AccountManager
from ClientNROpy.terminal import interactive_cli
from ClientNROpy.display import print_banner
from ClientNROpy.logger import logger


def print_usage():
    print("=" * 75)
    print("   HƯỚNG DẪN SỬ DỤNG CLIENT NRO (MULTI-ACCOUNT & PROXY)")
    print("=" * 75)
    print("1. Chạy nhiều tài khoản (Mặc định dùng accounts.json):")
    print("   ClientNRO.exe [--accounts accounts.json] [--use-proxy]")
    print()
    print("2. Chạy 1 tài khoản đơn lẻ truyền thống:")
    print("   ClientNRO.exe [host] [port] [username] [password] [version] [--proxy <proxy>]")
    print()
    print("Các tùy chọn (Options):")
    print("  --help, -h          Hiển thị màn hình trợ giúp này và thoát.")
    print("  --accounts <path>   Chỉ định đường dẫn file cấu hình tài khoản (mặc định: accounts.json).")
    print("  --use-proxy         Bật chế độ kết nối qua Proxy (mặc định: 4 acc / 1 proxy).")
    print("  --proxy <proxy>     Chỉ định proxy cho tài khoản (vd: socks5://user:pass@host:port).")
    print("  --no-cli            Đăng nhập xong rồi chạy ngầm (không vào giao diện gõ lệnh).")
    print("  --test-xmap         Chạy tự động kiểm thử tìm đường Xmap offline.")
    print("=" * 75)


def main():
    if "--help" in sys.argv or "-h" in sys.argv:
        print_usage()
        sys.exit(0)

    if "--test-xmap" in sys.argv:
        from ClientNROpy.xmap_cli import test_requested_maps
        test_requested_maps()
        sys.exit(0)

    print_banner()

    # Phân tích cờ dòng lệnh
    accounts_file = "accounts.json"
    settings_file = "settings.json"
    use_proxy_flag = False
    custom_proxy_arg = None
    no_cli = False
    no_telegram = False

    args = sys.argv[1:]
    clean_args = []
    idx = 0
    while idx < len(args):
        a = args[idx]
        if a == "--accounts" and idx + 1 < len(args):
            accounts_file = args[idx + 1]
            idx += 2
        elif a == "--settings" and idx + 1 < len(args):
            settings_file = args[idx + 1]
            idx += 2
        elif a in ("--use-proxy", "--proxy-on"):
            use_proxy_flag = True
            idx += 1
        elif a == "--proxy" and idx + 1 < len(args):
            custom_proxy_arg = args[idx + 1]
            use_proxy_flag = True
            idx += 2
        elif a == "--no-cli":
            no_cli = True
            idx += 1
        elif a == "--no-telegram":
            no_telegram = True
            idx += 1
        elif a in ("--web", "-w", "--terminal", "-t", "--cli"):
            idx += 1
        else:
            clean_args.append(a)
            idx += 1

    mgr = AccountManager(config_file=accounts_file, settings_file=settings_file)
    mgr.load_settings(settings_file)

    # Nếu người dùng truyền tham số dòng lệnh kiểu đơn lẻ: [host] [port] [user] [pwd] [ver]
    if len(clean_args) >= 3:
        host = clean_args[0]
        try:
            port = int(clean_args[1])
        except ValueError:
            port = 12457
        user = clean_args[2]
        pwd = clean_args[3] if len(clean_args) > 3 else "02082003"
        ver = clean_args[4] if len(clean_args) > 4 else "2.1.4"

        if use_proxy_flag:
            mgr.proxy_pool.set_use_proxy(True)

        logger.system(f"Chạy chế độ đơn tài khoản: '{user}' tại {host}:{port}")
        mgr.add_account_direct(user, pwd, proxy=custom_proxy_arg, host=host, port=port, version=ver)
    else:
        # Chế độ đa tài khoản qua file cấu hình accounts.json
        mgr.load_accounts(accounts_file)
        if use_proxy_flag:
            mgr.proxy_pool.set_use_proxy(True)

    if not mgr.accounts:
        logger.error(f"Không có tài khoản nào được cấu hình trong '{accounts_file}'!")
        print(f"[*] Hãy chỉnh sửa file '{accounts_file}' để thêm tài khoản hoặc gõ lệnh thêm.")

    # Khởi động Telegram Bot & Trợ lý AI OpenRouter nếu được cấu hình
    tg_bot = None
    if not no_telegram and mgr.telegram_config.get("enabled", True):
        token = mgr.telegram_config.get("token", "")
        if token:
            from ClientNROpy.telegram_bot import TelegramAIBot
            ai_cfg = mgr.ai_config
            tg_bot = TelegramAIBot(
                token=token,
                account_manager=mgr,
                allowed_chat_ids=mgr.telegram_config.get("allowed_chat_ids", []),
                notify_boss=mgr.telegram_config.get("notify_boss", True),
                notify_disconnect=mgr.telegram_config.get("notify_disconnect", True),
                notify_login=mgr.telegram_config.get("notify_login", True),
                ai_enabled=ai_cfg.get("enabled", True),
                ai_api_key=ai_cfg.get("api_key", ""),
                ai_model=ai_cfg.get("model", "openrouter/free"),
                ai_system_prompt=ai_cfg.get("system_prompt"),
            )
            mgr.telegram_bot = tg_bot
            tg_bot.start()

    # Khởi động toàn bộ tài khoản
    mgr.start_all(delay=1.5)

    if not no_cli:
        # Đợi các tài khoản khởi động và hoàn tất đăng nhập ban đầu trước khi hiển thị bảng trạng thái
        startup_wait = min(max(len(mgr.accounts) * 1.5 + 1.0, 2.0), 6.0)
        time.sleep(startup_wait)
        interactive_cli(mgr)
        if tg_bot:
            tg_bot.stop()
    else:
        logger.system("Chạy chế độ ngầm không có CLI (--no-cli). Nhấn Ctrl+C để thoát.")
        try:
            while True:
                time.sleep(1.0)
        except KeyboardInterrupt:
            if tg_bot:
                tg_bot.stop()
            mgr.stop_all()


if __name__ == "__main__":
    main()
