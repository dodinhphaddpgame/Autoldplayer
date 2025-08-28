# logger_widget.py
# Logger thread-safe: nếu đã đăng ký tkinter.Text thì ghi lên GUI, nếu không ghi ra console

import threading
from datetime import datetime

_text_widget = None
_widget_lock = threading.Lock()

def set_text_widget(widget) -> None:
    """Đăng ký widget tkinter.Text để logger ghi log lên GUI."""
    global _text_widget
    with _widget_lock:
        _text_widget = widget

def log(message: str) -> None:
    """Ghi log theo format [HH:MM:SS] message. An toàn khi dùng từ nhiều thread."""
    now = datetime.now().strftime("%H:%M:%S")
    line = f"[{now}] {message}\n"
    with _widget_lock:
        if _text_widget is not None:
            try:
                _text_widget.insert('end', line)
                _text_widget.see('end')
                return
            except Exception:
                # fallback in console nếu ghi vào widget lỗi
                pass
    print(line, end='')
