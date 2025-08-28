# file_manager.py
# Đọc/ghi file accounts. Hàm trả counter bắt đầu để tránh dùng biến global lung tung.

import os
import re
from typing import Optional

from config import ACCOUNTS_FILE
from logger_widget import log

def load_last_account() -> int:
    """Đọc ACCOUNTS_FILE và trả số account tiếp theo.
    Nếu file không tồn tại hoặc có lỗi thì trả 1.
    """
    if not os.path.exists(ACCOUNTS_FILE):
        return 1
    try:
        with open(ACCOUNTS_FILE, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        max_num = 0
        for line in lines:
            m = re.match(r"phapha(\d+)", line.strip())
            if m:
                max_num = max(max_num, int(m.group(1)))
        return max_num + 1
    except Exception as e:
        log(f"Lỗi đọc file account: {e}")
        return 1

def save_account_done(account_name: str) -> None:
    """Ghi tên account đã dùng (append)."""
    try:
        with open(ACCOUNTS_FILE, 'a', encoding='utf-8') as f:
            f.write(account_name + "\n")
    except Exception as e:
        log(f"Lỗi ghi file account: {e}")
