import subprocess
import tkinter as tk
import threading
from datetime import datetime
from time import sleep
import os
import re

LD_CONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"
GAME_PACKAGE = "vn.kvtm.js"
ACCOUNTS_FILE = "accounts_used.txt"

# Biến toàn cục quản lý account
account_counter = 1
account_lock = threading.Lock()

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

# ================= Core =================

def run_ldconsole(args):
    cmd = [LD_CONSOLE] + args
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
    text_box.insert(tk.END, f"[{now}] {message}\n")
    text_box.see(tk.END)

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

    # Xin account riêng cho instance này
    account_name = get_new_account()
    log(f"[LD {idx}] Gán account: {account_name}")

    # Mở LDPlayer
    run_ldconsole(["launch", "--index", str(idx)])
    log(f"[LD {idx}] Đã mở LDPlayer instance")

    # Mở game
    sleep(15)
    run_ldconsole([
        "adb", "--index", str(idx),
        "--command", f"shell monkey -p {GAME_PACKAGE} -c android.intent.category.LAUNCHER 1"
    ])
    log(f"[LD {idx}] Đã mở game {GAME_PACKAGE}")

    # Vòng lặp xử lý (giả sử chỉ chạy 3 lần rồi kết thúc)
    sleep(10)
    for i in range(3):
        run_ldconsole(["adb", "--index", str(idx), "--command", "shell input tap 860 9300"])
        log(f"[LD {idx}] ({account_name}) Tap (922,466)")
        sleep(5)

    # Khi luồng hoàn tất → lưu account vào file
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
            sleep(1)  # chờ LDPlayer xử lý shutdown

# Chạy close_all_tabs trong thread riêng để tránh treo GUI
def close_all_tabs_thread():
    threading.Thread(target=close_all_tabs, daemon=True).start()

# ================= GUI =================
root = tk.Tk()
root.title("LDPlayer Auto Controller")
root.geometry("600x420")

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
open_button.pack(pady=10)

# Gọi close_all_tabs_thread thay vì close_all_tabs trực tiếp
close_button = tk.Button(root, text="Close All Tabs", font=("Arial", 14), bg="red", fg="white", command=close_all_tabs_thread)
close_button.pack(pady=10)

text_box = tk.Text(root, height=12, width=70)
text_box.pack(pady=10)

# Khi mở app → đọc file để set counter
load_last_account()

root.mainloop()
