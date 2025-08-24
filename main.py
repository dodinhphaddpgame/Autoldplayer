import subprocess
import tkinter as tk
from concurrent.futures import ThreadPoolExecutor

# Đường dẫn tới ldconsole.exe (bạn sửa lại cho đúng máy mình)
LD_CONSOLE = r"C:\LDPlayer\LDPlayer9\ldconsole.exe"

# Hàm chạy lệnh ldconsole
def run_ldconsole(args):
    cmd = [LD_CONSOLE] + args
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return result.stdout.strip()

# Lấy danh sách instance LDPlayer
def get_instances():
    output = run_ldconsole(["list2"])
    instances = []
    for line in output.splitlines():
        parts = line.split(",")
        if len(parts) >= 2 and parts[0].isdigit():
            index = parts[0].strip()
            if index != "99999":  # bỏ instance ảo
                instances.append(index)
    return instances

# Lệnh tap
def tap_instance(index, x, y):
    run_ldconsole(["adb", "--index", index, "--command", f"shell input tap {x} {y}"])
    log(f"[+] Tap ({x},{y}) trên LDPlayer {index}")

# Lệnh swipe
def swipe_instance(index, x1, y1, x2, y2, duration=500):
    run_ldconsole(["adb", "--index", index, "--command",
                   f"shell input swipe {x1} {y1} {x2} {y2} {duration}"])
    log(f"[+] Swipe ({x1},{y1}) → ({x2},{y2}) trên LDPlayer {index}")

# Hàm thực hiện auto
def test_all():
    instances = get_instances()
    log(f"Các instance đang chạy: {instances}")
    with ThreadPoolExecutor() as executor:
        # tap tại (200,200)
        executor.map(lambda idx: tap_instance(idx, 200, 200), instances)
        # swipe từ (100,400) lên (100,100) - bật lên nếu cần
        #executor.map(lambda idx: swipe_instance(idx, 100, 400, 100, 100), instances)

# Hàm log ra cửa sổ GUI
def log(message):
    text_box.insert(tk.END, message + "\n")
    text_box.see(tk.END)

# ================= GUI =================
root = tk.Tk()
root.title("LDPlayer Auto Controller")
root.geometry("500x300")

# Nút Start
start_button = tk.Button(root, text="Start Auto", font=("Arial", 14), bg="green", fg="white", command=test_all)
start_button.pack(pady=10)

# Khung log hiển thị kết quả
text_box = tk.Text(root, height=12, width=60)
text_box.pack(pady=10)

# Chạy GUI loop
root.mainloop()
