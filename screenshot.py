# screenshot.py
# Logic chụp màn hình: ưu tiên exec-out (nhanh), nếu thất bại thì screencap -> pull

import tempfile
import os
import numpy as np
import cv2
from typing import Optional

from ldconsole import run_ldconsole
from logger_widget import log

def _extract_png_from_bytes(bts: bytes) -> Optional[bytes]:
    """Tìm header PNG trong bytes và trả phần dữ liệu PNG (bắt đầu từ \x89PNG tới IEND)."""
    if not bts:
        return None
    start = bts.find(b'\x89PNG')
    if start == -1:
        return None
    end_idx = bts.rfind(b'IEND')
    if end_idx == -1:
        return bts[start:]
    return bts[start:end_idx + 8]

def capture_screenshot_img(idx: int) -> Optional[np.ndarray]:
    """Thử exec-out trước, fallback screencap+pull. Trả về ảnh BGR (numpy) hoặc None."""
    # 1) exec-out
    try:
        cmd = ["adb", "--index", str(idx), "--command", "exec-out screencap -p"]
        out = run_ldconsole(cmd, text_mode=False)
        if out:
            if isinstance(out, str):
                out_bytes = out.encode('latin1', errors='ignore')
            else:
                out_bytes = out
            png = _extract_png_from_bytes(out_bytes)
            if png:
                arr = np.frombuffer(png, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    log(f"[LD {idx}] Chụp ảnh bằng exec-out thành công.")
                    return img
                else:
                    log(f"[LD {idx}] Không decode được ảnh từ exec-out.")
            else:
                log(f"[LD {idx}] exec-out không trả PNG hợp lệ.")
    except Exception as e:
        log(f"[LD {idx}] Lỗi exec-out: {e}")

    # 2) fallback: screencap -> pull
    try:
        _ = run_ldconsole(["adb", "--index", str(idx), "--command", "shell screencap -p /sdcard/screen.png"]) or ''
        tmpf = None
        try:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
            tmpf = tmp.name
            tmp.close()
            pull_cmd = ["adb", "--index", str(idx), "--command", f"pull /sdcard/screen.png {tmpf}"]
            _ = run_ldconsole(pull_cmd)
            if os.path.exists(tmpf):
                img = cv2.imread(tmpf)
                if img is None:
                    log(f"[LD {idx}] Đã pull file nhưng cv2.imread trả None.")
                else:
                    log(f"[LD {idx}] Chụp và pull file thành công.")
                    return img
            else:
                log(f"[LD {idx}] Pull không tạo file tạm: {tmpf}")
        finally:
            if tmpf and os.path.exists(tmpf):
                try:
                    os.remove(tmpf)
                except Exception:
                    pass
    except Exception as e:
        log(f"[LD {idx}] Lỗi fallback chụp/pull: {e}")

    return None
