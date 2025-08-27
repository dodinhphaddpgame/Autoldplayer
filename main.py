import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
from datetime import datetime
from time import sleep
import os
import re
import cv2
import numpy as np
import tempfile
import json

LD_CONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"  # Đường dẫn ldconsole.exe
GAME_PACKAGE = "vn.kvtm.js"
ACCOUNTS_FILE = "accounts_used.txt"
REGIONS_FILE = "regions.json"
REGIONS_DIR = "regions"  # nơi lưu ảnh vùng (ROI)

# Biến toàn cục quản lý account
account_counter = 1
account_lock = threading.Lock()
selected_region = None  # (x1, y1, x2, y2)
regions = {}  # load từ REGIONS_FILE: {"1":[x1,y1,x2,y2], ...}

# ================= File Manager =================

def load_last_account():
    """Đọc file txt để biết đã dùng đến account thứ mấy"""
    global account_counter
    if not os.path.exists(ACCOUNTS_FILE):
        return
    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        max_num = 0
        for line in lines:
            match = re.match(r"phapha(\d+)", line.strip())
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)
        account_counter = max_num + 1
    except Exception as e:
        print("Lỗi đọc file account:", e)

def save_account_done(account_name):
    """Ghi account đã dùng xong vào file txt"""
    try:
        with open(ACCOUNTS_FILE, "a", encoding="utf-8") as f:
            f.write(account_name + "\n")
    except Exception as e:
        print("Lỗi ghi file account:", e)

# ================= Regions storage =================

def load_regions():
    """Nạp regions từ REGIONS_FILE vào biến regions (dictionary)."""
    global regions
    if os.path.exists(REGIONS_FILE):
        try:
            with open(REGIONS_FILE, "r", encoding="utf-8") as f:
                regions = json.load(f)
            # ensure keys are strings and values are lists of ints
            for k, v in list(regions.items()):
                regions[k] = [int(x) for x in v]
        except Exception as e:
            log(f"Lỗi đọc {REGIONS_FILE}: {e}")
            regions = {}
    else:
        regions = {}

def save_region_to_file(idx, coords):
    """
    Lưu coords cho index vào regions.json và lưu ảnh ROI vào thư mục regions/.
    coords = (x1, y1, x2, y2)
    """
    # đảm bảo thư mục tồn tại
    os.makedirs(REGIONS_DIR, exist_ok=True)
    # lưu coords vào regions dict rồi ghi file json
    regions[str(idx)] = [int(coords[0]), int(coords[1]), int(coords[2]), int(coords[3])]
    try:
        with open(REGIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(regions, f, ensure_ascii=False, indent=2)
    except Exception as e:
        log(f"Lỗi ghi {REGIONS_FILE}: {e}")

# ================= Core / utils =================

def run_ldconsole(args):
    cmd = [LD_CONSOLE] + args
    # dùng text=True nơi cần chuỗi, ở đây dùng chung - trả stdout text
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()

def get_instances():
    output = run_ldconsole(["list2"])
    instances = []
    for line in output.splitlines():
        parts = line.split(",")
        if len(parts) >= 5 and parts[0].isdigit():
            index = parts[0].strip()
            status = parts[4].strip()
            if index != "99999" and status == "1":
                instances.append(index)
    return instances

def log(message):
    now = datetime.now().strftime("%H:%M:%S")
    try:
        text_box.insert(tk.END, f"[{now}] {message}\n")
        text_box.see(tk.END)
    except Exception:
        print(f"[{now}] {message}")

# ================= Screenshot (robust) =================

def _extract_png_from_bytes(bts):
    if not bts:
        return None
    start = bts.find(b'\x89PNG')
    if start == -1:
        return None
    end_idx = bts.rfind(b'IEND')
    if end_idx == -1:
        return bts[start:]
    else:
        return bts[start:end_idx + 8]

def capture_screenshot_img(idx):
    """
    Thử exec-out rồi fallback pull. Trả về OpenCV BGR numpy image hoặc None.
    """
    # 1) exec-out
    try:
        cmd = [LD_CONSOLE, "adb", "--index", str(idx), "--command", "exec-out screencap -p"]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.stderr:
            errtxt = proc.stderr.decode(errors='ignore')
            if errtxt.strip():
                log(f"[LD {idx}] exec-out stderr: {errtxt.strip()}")
        out = proc.stdout
        png_bytes = _extract_png_from_bytes(out)
        if png_bytes:
            arr = np.frombuffer(png_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                log(f"[LD {idx}] Chụp ảnh bằng exec-out thành công.")
                return img
            else:
                log(f"[LD {idx}] Không decode được ảnh từ exec-out (cv2.imdecode trả None).")
        else:
            log(f"[LD {idx}] exec-out không trả dữ liệu PNG hợp lệ (không tìm header).")
    except Exception as e:
        log(f"[LD {idx}] Lỗi khi chạy exec-out: {e}")

    # 2) fallback
    try:
        cmd_capture = [LD_CONSOLE, "adb", "--index", str(idx), "--command", "shell screencap -p /sdcard/screen.png"]
        proc1 = subprocess.run(cmd_capture, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc1.returncode != 0:
            log(f"[LD {idx}] Lỗi khi chụp vào /sdcard: {proc1.stderr or proc1.stdout}")
        else:
            tmpf = None
            try:
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
                tmpf = tmp.name
                tmp.close()
                cmd_pull = [LD_CONSOLE, "adb", "--index", str(idx), "--command", f"pull /sdcard/screen.png {tmpf}"]
                proc2 = subprocess.run(cmd_pull, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                if proc2.returncode != 0:
                    log(f"[LD {idx}] Lỗi khi pull file: {proc2.stderr or proc2.stdout}")
                else:
                    img = cv2.imread(tmpf)
                    if img is None:
                        log(f"[LD {idx}] Đã pull file nhưng cv2.imread trả None.")
                    else:
                        log(f"[LD {idx}] Chụp và pull file thành công.")
                        return img
            finally:
                if tmpf and os.path.exists(tmpf):
                    try:
                        os.remove(tmpf)
                    except Exception:
                        pass
    except Exception as e:
        log(f"[LD {idx}] Lỗi fallback chụp/pull: {e}")

    return None

# ================= Account Manager =================

def get_new_account():
    global account_counter
    with account_lock:
        acc_name = f"phapha{account_counter}"
        account_counter += 1
    return acc_name

# ================= Per-Instance Worker =================

def worker_instance(idx):
    log(f"[LD {idx}] Bắt đầu quản lý instance...")
    account_name = get_new_account()
    log(f"[LD {idx}] Gán account: {account_name}")

    run_ldconsole(["launch", "--index", str(idx)])
    log(f"[LD {idx}] Đã mở LDPlayer instance")

    sleep(15)
    run_ldconsole([
        "adb", "--index", str(idx),
        "--command", f"shell monkey -p {GAME_PACKAGE} -c android.intent.category.LAUNCHER 1"
    ])
    log(f"[LD {idx}] Đã mở game {GAME_PACKAGE}")

    sleep(10)
    for i in range(3):
        run_ldconsole(["adb", "--index", str(idx), "--command", "shell input tap 200 200"])
        log(f"[LD {idx}] ({account_name}) Tap (200,200)")
        sleep(5)

    save_account_done(account_name)
    log(f"[LD {idx}] Hoàn thành công việc với {account_name}, đã lưu vào file.")

# ================= Control =================

def open_tabs():
    try:
        start_idx = int(entry_start.get())
        end_idx = int(entry_end.get())
        for idx in range(start_idx, end_idx + 1):
            threading.Thread(target=worker_instance, args=(idx,), daemon=True).start()
    except ValueError:
        log("Vui lòng nhập số hợp lệ!")

def close_all_tabs():
    while True:
        instances = get_instances()
        if not instances:
            log("Tất cả tab đã được tắt.")
            break
        for idx in instances:
            run_ldconsole(["quit", "--index", idx])
            log(f"Đã gửi lệnh tắt LDPlayer instance {idx}")
            sleep(5)

# ================= Region Select (cv2.selectROI) + Save =================

def select_region(idx=1):
    """
    Chụp ảnh, mở cv2.selectROI để chọn vùng.
    Sau khi chọn, tự động lưu ROI image và tọa độ vào regions.json.
    """
    global selected_region
    log(f"Đang chụp màn hình LDPlayer {idx}...")
    img = capture_screenshot_img(idx)
    if img is None:
        log("Không chụp được ảnh từ LDPlayer.")
        return

    clone = img.copy()
    r = cv2.selectROI("Chọn vùng ảnh (Enter: xác nhận, Esc: hủy)", clone, False, False)
    cv2.destroyAllWindows()

    if r == (0, 0, 0, 0):
        log("Bạn chưa chọn vùng nào.")
        return

    x, y, w, h = r
    x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)
    selected_region = (x1, y1, x2, y2)

    # Lưu ROI image vào thư mục regions
    os.makedirs(REGIONS_DIR, exist_ok=True)
    roi_filename = os.path.join(REGIONS_DIR, f"region_idx_{idx}.png")
    roi = img[y1:y2, x1:x2]
    try:
        cv2.imwrite(roi_filename, roi)
        log(f"Đã lưu ảnh vùng vào: {roi_filename}")
    except Exception as e:
        log(f"Lỗi lưu ROI image: {e}")

    # Lưu coords vào JSON
    try:
        save_region_to_file(idx, selected_region)
        log(f"Đã lưu tọa độ vùng vào {REGIONS_FILE} cho index {idx}: {selected_region}")
    except Exception as e:
        log(f"Lỗi lưu region json: {e}")

    # Hiện vùng đã chọn để xác nhận (vẽ khung xanh, hiện 1s)
    try:
        disp = img.copy()
        cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.imshow("Vùng đã chọn (đóng sau 1s)", disp)
        cv2.waitKey(1000)
        cv2.destroyAllWindows()
    except Exception:
        pass

def load_region_and_show(idx):
    """
    Load region coords từ regions dict và hiển thị trên screenshot (vẽ khung).
    """
    idx_str = str(idx)
    if idx_str not in regions:
        log(f"Chưa có vùng lưu cho index {idx}.")
        return
    coords = regions[idx_str]
    x1, y1, x2, y2 = map(int, coords)
    img = capture_screenshot_img(idx)
    if img is None:
        log("Không chụp được ảnh từ LDPlayer.")
        return
    try:
        disp = img.copy()
        cv2.rectangle(disp, (x1, y1), (x2, y2), (255, 0, 0), 3)
        cv2.imshow(f"Vùng đã lưu index {idx}", disp)
        cv2.waitKey(1000)
        cv2.destroyAllWindows()
    except Exception as e:
        log(f"Lỗi hiển thị vùng lưu: {e}")

# ================= GUI =================
root = tk.Tk()
root.title("LDPlayer Auto Controller")
root.geometry("640x560")

frame_range = tk.Frame(root)
frame_range.pack(pady=5)

tk.Label(frame_range, text="Start index:").grid(row=0, column=0, padx=5)
entry_start = tk.Entry(frame_range, width=5)
entry_start.grid(row=0, column=1, padx=5)
entry_start.insert(0, "1")

tk.Label(frame_range, text="End index:").grid(row=0, column=2, padx=5)
entry_end = tk.Entry(frame_range, width=5)
entry_end.grid(row=0, column=3, padx=5)
entry_end.insert(0, "3")

open_button = tk.Button(root, text="Open Tabs", font=("Arial", 14), bg="blue", fg="white", command=open_tabs)
open_button.pack(pady=8)

close_button = tk.Button(root, text="Close All Tabs", font=("Arial", 14), bg="red", fg="white",
                         command=lambda: threading.Thread(target=close_all_tabs, daemon=True).start())
close_button.pack(pady=4)

# region controls
frame_region = tk.Frame(root)
frame_region.pack(pady=8)

tk.Label(frame_region, text="Index chọn vùng:").grid(row=0, column=0, padx=5)
entry_region_index = tk.Entry(frame_region, width=6)
entry_region_index.grid(row=0, column=1, padx=5)
entry_region_index.insert(0, "1")

region_button = tk.Button(frame_region, text="Chọn & Lưu vùng (index)", font=("Arial", 12), bg="green", fg="white",
                          command=lambda: threading.Thread(target=select_region, args=(int(entry_region_index.get()),), daemon=True).start())
region_button.grid(row=0, column=2, padx=6)

load_region_button = tk.Button(frame_region, text="Load vùng đã lưu (index)", font=("Arial", 12), bg="orange", fg="white",
                               command=lambda: threading.Thread(target=load_region_and_show, args=(int(entry_region_index.get()),), daemon=True).start())
load_region_button.grid(row=0, column=3, padx=6)

# text log
text_box = tk.Text(root, height=18, width=80)
text_box.pack(pady=10)

# Khi mở app → đọc file để set counter + load regions
load_last_account()
load_regions()

root.mainloop()
