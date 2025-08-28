# account_manager.py
# Quản lý cấp account mới thread-safe và ghi khi hoàn thành

import threading

from file_manager import load_last_account, save_account_done

_account_lock = threading.Lock()
_counter = load_last_account()

def get_new_account() -> str:
    """Trả về 'phapha{n}' và tăng counter an toàn trong thread."""
    global _counter
    with _account_lock:
        name = f"phapha{_counter}"
        _counter += 1
        return name

def mark_done(name: str) -> None:
    """Ghi account đã dùng vào file (append)."""
    save_account_done(name)
