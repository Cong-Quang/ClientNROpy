# -*- coding: utf-8 -*-
"""
Giao diện dòng lệnh tương tác trực tiếp (terminal.py).
Cung cấp prompt thông minh hiển thị ngữ cảnh:
- Khi ở chế độ tất cả: nro[all]>
- Khi ở chế độ acc riêng: nro[acc1:GokuVN]>
Hỗ trợ bắt Ctrl+C an toàn và dọn dẹp kết nối khi thoát.
"""

import sys
from typing import Optional, Union

from .command_handler import execute_multi_command
from .display import print_cli_help, print_accounts_table
from .logger import logger


def interactive_cli(account_manager, default_target: Optional[Union[int, str]] = None) -> None:
    """
    Vòng lặp nhận và xử lý lệnh từ bàn phím.
    Hỗ trợ điều khiển 1 hoặc nhiều tài khoản cùng lúc.
    """
    print_cli_help()
    print_accounts_table(account_manager)
    print("[+] ĐÃ SẴN SÀNG NHẬN LỆNH. Gõ 'help' để xem hướng dẫn hoặc 'exit' để thoát.\n")

    active_target: Optional[Union[int, str]] = default_target

    while True:
        # Xây dựng nhãn prompt theo ngữ cảnh hiện tại
        if active_target is None:
            online_count = sum(1 for a in account_manager.accounts if a.client and a.client.isConnected())
            total_count = len(account_manager.accounts)
            prompt = f"nro[all:{online_count}/{total_count}]> "
        else:
            inst = account_manager.get_account(active_target)
            if inst:
                cname = inst.char_name if inst.char_name != "Chưa vào" else inst.config.username
                st_icon = "=" if inst.status == "ONLINE" else (">" if inst.status == "CONNECTING" else ":")
                prompt = f"nro[#{inst.config.acc_id}:{cname} {st_icon}]> "
            else:
                prompt = f"nro[acc:{active_target}]> "

        try:
            line = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[*] Đang thoát giao diện dòng lệnh...")
            account_manager.stop_all()
            break

        if not line:
            continue

        try:
            should_continue, active_target = execute_multi_command(
                account_manager,
                active_target,
                line,
            )
            if not should_continue:
                break
        except Exception as ex:
            logger.error(f"Lỗi khi thực thi lệnh: {ex}")
