import subprocess
import tkinter as tk
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Đường dẫn tới ldconsole.exe (bạn sửa lại đúng trên máy mình)
LD_CONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"

# Hàm chạy lệnh ldconsole
def run_ldconsole(args):
    cmd = [LD_CONSOLE] + args
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()

# Lấy danh sách instance LDPlayer (chỉ lấy cái đang chạy)
def get_instances():
    output = run_ldconsole(["list2"])
    instances = []
    for line in output.splitlines():
        parts = line.split(",")
        if len(parts) >= 5 and parts[0].isdigit():
            index = parts[0].strip()
            status = parts[4].strip()
            if index != "99999" and status == "1":  # chỉ lấy instance đang chạy
                instances.append(index)
    return instances

# Lệnh tap
def tap_instance(index, x, y):
    run_ldconsole(["adb", "--index", index, "--command", f"shell input tap {x} {y}"])
    log(f"Tap ({x},{y}) trên LDPlayer {index}")

# Hàm auto
def test_all():
    instances = get_instances()
    log(f"Các instance đang chạy: {instances}")
    with ThreadPoolExecutor() as executor:
        executor.map(lambda idx: tap_instance(idx, 200, 200), instances)

# Hàm chạy auto trong thread riêng
def start_auto():
    threading.Thread(target=test_all, daemon=True).start()

# Hàm mở tab LDPlayer theo khoảng index
def open_tabs():
    try:
        start_idx = int(entry_start.get())
        end_idx = int(entry_end.get())
        for idx in range(start_idx, end_idx + 1):
            run_ldconsole(["launch", "--index", str(idx)])
            log(f"Đã mở LDPlayer instance {idx}")
    except ValueError:
        log("Vui lòng nhập số hợp lệ!")

# Hàm tắt tất cả tab đang chạy
def close_all_tabs():
    instances = get_instances()
    if not instances:
        log("Không có tab nào đang chạy.")
        return
    for idx in instances:
        run_ldconsole(["quit", "--index", idx])
        log(f"Đã tắt LDPlayer instance {idx}")

# Hàm log ra GUI có thời gian
def log(message):
    now = datetime.now().strftime("%H:%M:%S")
    text_box.insert(tk.END, f"[{now}] {message}\n")
    text_box.see(tk.END)

# ================= GUI =================
root = tk.Tk()
root.title("LDPlayer Auto Controller")
root.geometry("600x420")

# Nút Start Auto
start_button = tk.Button(root, text="Start Auto", font=("Arial", 14), bg="green", fg="white", command=start_auto)
start_button.pack(pady=10)

# Khung nhập start / end index
frame_range = tk.Frame(root)
frame_range.pack(pady=5)

tk.Label(frame_range, text="Start index:").grid(row=0, column=0, padx=5)
entry_start = tk.Entry(frame_range, width=5)
entry_start.grid(row=0, column=1, padx=5)
entry_start.insert(0, "1")  # mặc định từ 1

tk.Label(frame_range, text="End index:").grid(row=0, column=2, padx=5)
entry_end = tk.Entry(frame_range, width=5)
entry_end.grid(row=0, column=3, padx=5)
entry_end.insert(0, "3")  # mặc định đến 3

open_button = tk.Button(root, text="Open Tabs", font=("Arial", 14), bg="blue", fg="white", command=open_tabs)
open_button.pack(pady=10)

# Nút Close All Tabs
close_button = tk.Button(root, text="Close All Tabs", font=("Arial", 14), bg="red", fg="white", command=close_all_tabs)
close_button.pack(pady=10)

# Khung log hiển thị kết quả
text_box = tk.Text(root, height=12, width=70)
text_box.pack(pady=10)

root.mainloop()
