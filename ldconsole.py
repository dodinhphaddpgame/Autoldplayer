# ldconsole.py
# Tất cả tương tác gọi ldconsole.exe được tập trung ở đây.

import subprocess
from typing import List
import re

from config import LD_CONSOLE
from logger_widget import log

def run_ldconsole(args: List[str], text_mode: bool = True, check: bool = False):
    """Chạy ldconsole với args là list các tham số.
    - text_mode=True: trả stdout/stderr là str
    - text_mode=False: trả bytes (dùng khi cần exec-out screencap)
    Trả về stdout (str hoặc bytes). Nếu lỗi thì trả chuỗi rỗng.
    """
    cmd = [LD_CONSOLE] + args
    try:
        if text_mode:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=check)
            if res.stderr:
                err_txt = res.stderr.strip()
                if err_txt:
                    log(f"LDConsole stderr: {err_txt}")
            return res.stdout.strip()
        else:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=check)
            if res.stderr:
                log(f"LDConsole stderr (bytes): {res.stderr[:200]!r}")
            return res.stdout
    except FileNotFoundError:
        log(f"Không tìm thấy LDConsole tại: {LD_CONSOLE}")
        return ""
    except Exception as e:
        log(f"Lỗi chạy ldconsole: {e}")
        return ""

def get_instances() -> List[str]:
    """Phân tích output của `ldconsole list2` để lấy danh sách instance index đang chạy."""
    out = run_ldconsole(["list2"]) or ""
    instances = []
    for line in out.splitlines():
        parts = [p.strip() for p in line.split(',') if p.strip()]
        if not parts:
            continue
        idx = parts[0]
        status = None
        if len(parts) >= 5:
            status = parts[4]
        else:
            m = re.search(r"\b(0|1)\b", line)
            status = m.group(1) if m else None
        if idx.isdigit() and idx != '99999' and status == '1':
            instances.append(idx)
    return instances
