import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog
import threading
from datetime import datetime
from time import sleep
import os
import re
import cv2
import numpy as np
import tempfile
import glob
import time

LD_CONSOLE = r"D:\LDPlayer\LDPlayer9\ldconsole.exe"  # Đường dẫn ldconsole.exe
GAME_PACKAGE = "vn.kvtm.js"
ACCOUNTS_FILE = "accounts_used.txt"
REGIONS_DIR = "regions"  # thư mục gốc chứa các thư mục category
passwork = "pppppp"

# Biến toàn cục quản lý account
account_counter = 1
account_lock = threading.Lock()
selected_region = None  # (x1, y1, x2, y2)

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

# ================= Core / utils =================

#def run_ldconsole(args):
    #cmd = [LD_CONSOLE] + args
    # trả stdout text
    #result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    #return result.stdout.strip()

def run_ldconsole(args):
    cmd = [LD_CONSOLE]
    if "--command" in args:
        pos = args.index("--command")
        # Ghép tất cả sau --command thành một chuỗi duy nhất
        cmd += args[:pos+1] + [" ".join(args[pos+1:])]
    else:
        cmd += args

    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return (result.stdout + result.stderr).strip()

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
        # nếu gọi trước khi text_box sẵn sàng hoặc từ thread -> print ra console
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
    # # 1) exec-out
    # try:
    #     cmd = [LD_CONSOLE, "adb", "--index", str(idx), "--command", "exec-out screencap -p"]
    #     proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    #     if proc.stderr:
    #         errtxt = proc.stderr.decode(errors='ignore')
    #         if errtxt.strip():
    #             log(f"[LD {idx}] exec-out stderr: {errtxt.strip()}")
    #     out = proc.stdout
    #     # nếu proc.stdout là str (text mode) -> encode
    #     if isinstance(out, str):
    #         out_bytes = out.encode(errors='ignore')
    #     else:
    #         out_bytes = out
    #     png_bytes = _extract_png_from_bytes(out_bytes)
    #     if png_bytes:
    #         arr = np.frombuffer(png_bytes, dtype=np.uint8)
    #         img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    #         if img is not None:
    #             log(f"[LD {idx}] Chụp ảnh bằng exec-out thành công.")
    #             return img
    #         else:
    #             log(f"[LD {idx}] Không decode được ảnh từ exec-out (cv2.imdecode trả None).")
    #     else:
    #         log(f"[LD {idx}] exec-out không trả dữ liệu PNG hợp lệ (không tìm header).")
    # except Exception as e:
    #     log(f"[LD {idx}] Lỗi khi chạy exec-out: {e}")

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

def login(idx):
    # log(f"[LD {idx}] Bắt đầu quản lý instance...")
    # account_name = get_new_account()
    # log(f"[LD {idx}] Gán account: {account_name}")

    run_ldconsole(["launch", "--index", str(idx)])
    log(f"[LD {idx}] Đang mở LDPlayer instance")

    sleep(30)
    run_ldconsole([
       "adb", "--index", str(idx),
       "--command", f"shell monkey -p {GAME_PACKAGE} -c android.intent.category.LAUNCHER 1"
    ])
    run_ldconsole([
       "adb", "--index", str(idx),
       "--command", f"shell monkey -p {GAME_PACKAGE} -c android.intent.category.LAUNCHER 1"
    ])
    log(f"[LD {idx}] Đã mở game {GAME_PACKAGE}")

    sleep(12)  # đợi game load
    click_if_found_until_gone(idx, template_path="regions/login/login_1_20250916_185037.png")

    sleep(1)
    click_if_found_until_gone(idx, template_path="regions/login/login_2_20250916_185057.png")
    sleep(5)

def kiemtragoc(idx):
    if found_image(idx, template_path="regions/kiemtragoc/1.png"):
        return True
    else :
        return False

def autotrongcay(idx):
    if found_image(idx, template_path="regions/kiemtragoc/2.png", search_region=(663, 540, 740, 597)):
        sleep(0.2)
        click(idx,toadoclick=(298, 738))
        sleep(0.2)

        # kiểm tra presence
        # chạy thử
        #swipe_path(4, [(271, 625), (296, 734), (653, 729)])
        #ok, info = swipe_three_points_sendevent(4, (271, 625), (296, 734), (653, 729), total_ms=800,
        #                                        steps_per_segment=8, debug=True)
        #print(ok, info)

        #swipe_path_fast(idx, [(271, 625), (296, 734), (653, 729)])
        #swipe(idx, (271, 625), (296, 734), sleep_after=0.0)
        #swipe(idx, (296, 734), (653, 729), sleep_after=0.5)
        #swipe_path_fast(idx, point=[(271, 625),(296, 734)], total_duration_ms=1000)

def worker_instance(idx):
    log(f"[LD {idx}] Bắt đầu quản lý instance...")
    account_name = get_new_account()
    log(f"[LD {idx}] Gán account: {account_name}")
    #login(idx)
    sleep(0.2)
    autotrongcay(idx)
    sleep(0.2)
    # run_ldconsole([
    #     "adb", "--index", str(idx),
    #     "--command", "shell input keyevent 123"  # 123 = KEYCODE_MOVE_END
    # ])
    # for _ in range(10):  # giả sử tên tối đa 20 ký tự
    #     run_ldconsole([
    #         "adb", "--index", str(idx),
    #         "--command", "shell input keyevent 67"  # 67 = KEYCODE_DEL
    #     ])
    #
    # sleep(1)
    # run_ldconsole([
    #     "adb", "--index", str(idx),
    #     "--command", f"shell input text {account_name}"
    # ])
    #
    # sleep(1)
    # click_if_found(idx, template_path="regions/login/login_5_20250904_144633.png")

    save_account_done(account_name)
    log(f"[LD {idx}] Hoàn thành công việc với {account_name}, đã lưu vào file.")


def click(idx,toadoclick):
    # Click
    cx, cy = map(int, toadoclick)
    try:
        run_ldconsole([
            "adb", "--index", str(idx),
            "--command", f"shell input tap {cx} {cy}"
        ])
        log(f"[LD {idx}] Click tại ({cx},{cy})")
    except Exception as e:
        log(f"[LD {idx}] Lỗi click: {e}")

def click_if_found(idx, template_path, threshold=0.97, search_region=None):
    """
    Nếu template xuất hiện thì tap vào giữa template đó.
    """
    found, score, rect = find_template_on_screen(idx, template_path, threshold, search_region)
    if found and rect:
        x1, y1, x2, y2 = rect
        cx = (x1 + x2) // 2
        cy = (y1 + y2) // 2
        try:
            run_ldconsole([
                "adb", "--index", str(idx),
                "--command", f"shell input tap {cx} {cy}"
            ])
            log(f"[LD {idx}] Click vào {template_path} tại ({cx},{cy}), score={score:.3f}")
            return True
        except Exception as e:
            log(f"[LD {idx}] Lỗi khi click: {e}")
    else:
        log(f"[LD {idx}] Không tìm thấy {template_path} (score={score:.3f})")
    return False

def click_if_found_until_gone(
    idx,
    template_path,
    threshold=0.97,
    search_region=None,
    timeout=10.0,
    max_attempts=6,
    check_interval=1.5,
):
    """
    Tìm template, nếu thấy thì click vào tâm.
    Sau đó kiểm tra lại: nếu template vẫn còn thì click lại.
    Lặp cho tới khi biến mất hoặc hết timeout/số lần thử.
    Trả về True nếu thành công, False nếu không.
    """
    start_time = time.time()
    attempts = 0

    while time.time() - start_time < timeout and attempts < max_attempts:
        found, score, rect = find_template_on_screen(idx, template_path, threshold, search_region)

        if not found:
            log(f"[LD {idx}] Không tìm thấy {template_path} (score={score:.3f}), chờ {check_interval}s...")
            time.sleep(check_interval)
            continue

        if rect:
            x1, y1, x2, y2 = rect
            cx = (x1 + x2) // 2
            cy = (y1 + y2) // 2
        else:
            log(f"[LD {idx}] Tìm thấy {template_path} nhưng rect=None")
            time.sleep(check_interval)
            continue

        # Click
        try:
            run_ldconsole([
                "adb", "--index", str(idx),
                "--command", f"shell input tap {cx} {cy}"
            ])
            log(f"[LD {idx}] Click {template_path} tại ({cx},{cy}), score={score:.3f}, attempt {attempts+1}")
        except Exception as e:
            log(f"[LD {idx}] Lỗi click: {e}")
            attempts += 1
            time.sleep(check_interval)
            continue

        # Đợi rồi kiểm tra lại
        time.sleep(check_interval)
        found_after, score_after, _ = find_template_on_screen(idx, template_path, threshold, search_region)

        if not found_after:
            log(f"[LD {idx}] {template_path} đã biến mất sau click.")
            return True

        attempts += 1
        log(f"[LD {idx}] {template_path} vẫn còn sau click (score={score_after:.3f}), thử lại ({attempts}/{max_attempts})...")

    log(f"[LD {idx}] Không thể làm biến mất {template_path} sau {attempts} lần trong {timeout:.1f}s.")
    return False

def found_image(idx, template_path, threshold=0.85, search_region=None):
    found, score, rect = find_template_on_screen(idx, template_path, threshold, search_region)
    return found

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

# ================= Template matching helpers =================

def find_template_on_screen(idx, template_path, threshold=0.98, search_region=None):
    """
    Chụp màn từ LDPlayer idx, tìm template_path.
    Trả về (found, max_val, rect) where rect=(x1,y1,x2,y2) in screen coords.
    """
    img = capture_screenshot_img(idx)
    if img is None:
        log(f"[LD {idx}] Không chụp được ảnh để dò template.")
        return (False, 0.0, None)

    search_img = img
    offset_x = offset_y = 0
    if search_region:
        x1, y1, x2, y2 = map(int, search_region)
        # clamp
        x1 = max(0, min(search_img.shape[1]-1, x1))
        x2 = max(0, min(search_img.shape[1], x2))
        y1 = max(0, min(search_img.shape[0]-1, y1))
        y2 = max(0, min(search_img.shape[0], y2))
        if x2 <= x1 or y2 <= y1:
            log(f"[LD {idx}] search_region không hợp lệ: {search_region}")
            return (False, 0.0, None)
        search_img = img[y1:y2, x1:x2]
        offset_x, offset_y = x1, y1

    tpl = cv2.imread(template_path, cv2.IMREAD_COLOR)
    if tpl is None:
        log(f"[LD {idx}] Không đọc được template: {template_path}")
        return (False, 0.0, None)

    if tpl.shape[0] > search_img.shape[0] or tpl.shape[1] > search_img.shape[1]:
        # template to hơn vùng tìm -> skip
        return (False, 0.0, None)

    try:
        res = cv2.matchTemplate(search_img, tpl, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)
        top_left = max_loc
        h, w = tpl.shape[:2]
        x1m = int(top_left[0] + offset_x)
        y1m = int(top_left[1] + offset_y)
        x2m = x1m + w
        y2m = y1m + h
        found = (max_val >= threshold)
        return (found, float(max_val), (x1m, y1m, x2m, y2m))
    except Exception as e:
        log(f"[LD {idx}] Lỗi khi match template {os.path.basename(template_path)}: {e}")
        return (False, 0.0, None)

def tap_center_of_rect(idx, rect):
    x1,y1,x2,y2 = rect
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    run_ldconsole(["adb", "--index", str(idx), "--command", f"shell input tap {cx} {cy}"])
    log(f"[LD {idx}] Tap tại ({cx},{cy})")

def find_and_act_category(idx, category, threshold=0.85, search_region=None, first_only=True, do_tap=True):
    """
    Dò các ảnh trong regions/<category> theo thứ tự file.
    Nếu first_only True -> dừng ở template đầu tìm thấy.
    Trả về info dict nếu tìm thấy (template, score, rect) hoặc None.
    """
    folder = os.path.join(REGIONS_DIR, category)
    if not os.path.isdir(folder):
        log(f"Folder category không tồn tại: {folder}")
        return None

    templates = sorted(glob.glob(os.path.join(folder, "*.*")))
    if not templates:
        log(f"Category {category} rỗng: {folder}")
        return None

    for tpl in templates:
        found, score, rect = find_template_on_screen(idx, tpl, threshold=threshold, search_region=search_region)
        log(f"[LD {idx}] Template {os.path.basename(tpl)} -> score={score:.3f} found={found}")
        if found:
            info = {"template": tpl, "score": score, "rect": rect}
            if do_tap:
                try:
                    tap_center_of_rect(idx, rect)
                except Exception as e:
                    log(f"[LD {idx}] Lỗi tap: {e}")
            if first_only:
                return info
    return None

# -------------------------------
# Watcher (polling) để tự động dò
# -------------------------------
_watch_threads = {}  # map key -> {"thread":..., "stop":Event}

def start_watch_category(idx, category, threshold=0.88, interval_sec=3, search_region=None, do_tap=True):
    key = f"{idx}:{category}"
    if key in _watch_threads:
        log(f"Watcher đã chạy cho {key}")
        return
    stop_flag = threading.Event()
    def worker():
        log(f"Watcher bắt đầu cho LD{idx} category={category} interval={interval_sec}s threshold={threshold}")
        while not stop_flag.is_set():
            res = find_and_act_category(idx, category, threshold=threshold, search_region=search_region, first_only=True, do_tap=do_tap)
            if res:
                log(f"[Watcher {key}] Tìm thấy {os.path.basename(res['template'])} score={res['score']:.3f} tại {res['rect']}")
            stop_flag.wait(interval_sec)
        log(f"Watcher dừng cho {key}")
    th = threading.Thread(target=worker, daemon=True)
    _watch_threads[key] = {"thread": th, "stop": stop_flag}
    th.start()

def stop_watch_category(idx, category):
    key = f"{idx}:{category}"
    info = _watch_threads.get(key)
    if not info:
        log(f"Không có watcher cho {key}")
        return
    info["stop"].set()
    del _watch_threads[key]
    log(f"Đã gửi lệnh dừng watcher cho {key}")

# ================= Region Select (cv2.selectROI) + Save images into category folders =================

# helper: gọi simpledialog.askstring trên luồng chính bằng root.after và trả về kết quả
def ask_category_on_main(initial="default"):
    result = {"value": None}
    evt = threading.Event()

    def _ask():
        try:
            result["value"] = simpledialog.askstring("Category",
                                                     "Nhập tên category (ví dụ: login, clickimage):",
                                                     initialvalue=initial)
        except Exception:
            result["value"] = None
        finally:
            evt.set()

    # schedule gọi trên luồng chính
    root.after(0, _ask)
    # chờ cho tới khi người dùng nhập hoặc huỷ
    evt.wait()
    return result["value"]


# Thay thế hàm select_region cũ bằng hàm này
def select_region(idx=1):
    """
    Chụp ảnh, mở cv2.selectROI để chọn vùng.
    Sau khi chọn, chỉ lưu ảnh ROI (không lưu tọa độ) vào thư mục:
      regions/<category>/...
    Lưu ý: dialog nhập category sẽ được gọi trên luồng chính (sử dụng ask_category_on_main).
    """
    global selected_region

    # gọi dialog trên main thread để tránh TclError
    category = ask_category_on_main(initial="kiemtragoc")
    if category is None:
        log("Đã hủy (không nhập category).")
        return
    category = category.strip() or "default"

    log(f"Đang chụp màn hình LDPlayer {idx} (category={category})...")
    img = capture_screenshot_img(idx)
    if img is None:
        log("Không chụp được ảnh từ LDPlayer.")
        return

    clone = img.copy()
    # cv2.selectROI có thể mở cửa sổ riêng; vẫn gọi nó ở thread con (như trước)
    r = cv2.selectROI("Chọn vùng ảnh (Enter: xác nhận, Esc: hủy)", clone, False, False)
    cv2.destroyAllWindows()

    if r == (0, 0, 0, 0):
        log("Bạn chưa chọn vùng nào.")
        return

    x, y, w, h = r
    x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)
    selected_region = (x1, y1, x2, y2)

    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    midselected_region = (cx, cy)

    os.makedirs(REGIONS_DIR, exist_ok=True)
    category_dir = os.path.join(REGIONS_DIR, category)
    os.makedirs(category_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{category}_idx{idx}_{ts}.png"
    fullpath = os.path.join(category_dir, filename)

    roi = img[y1:y2, x1:x2]
    try:
        cv2.imwrite(fullpath, roi)
        log(f"Đã lưu ảnh vùng vào: {fullpath}, tọa độ: {selected_region} , tâm tọa độ: {midselected_region}")
    except Exception as e:
        log(f"Lỗi lưu ROI image: {e}")

    # hiển thị vùng đã chọn để xác nhận (vẽ khung xanh, hiện 1s)
    try:
        disp = img.copy()
        cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.imshow("Vùng đã chọn (đóng sau 1s)", disp)
        cv2.waitKey(1000)
        cv2.destroyAllWindows()
    except Exception:
        pass


# ================= GUI =================
root = tk.Tk()
root.title("LDPlayer Auto Controller")
root.geometry("760x640")

frame_range = tk.Frame(root)
frame_range.pack(pady=5)

tk.Label(frame_range, text="Start index:").grid(row=0, column=0, padx=5)
entry_start = tk.Entry(frame_range, width=5)
entry_start.grid(row=0, column=1, padx=5)
entry_start.insert(0, "4")

tk.Label(frame_range, text="End index:").grid(row=0, column=2, padx=5)
entry_end = tk.Entry(frame_range, width=5)
entry_end.grid(row=0, column=3, padx=5)
entry_end.insert(0, "4")

open_button = tk.Button(frame_range, text="Open Tabs", font=("Arial", 12), bg="blue", fg="white", command=open_tabs)
open_button.grid(row=0, column=4, padx=8)

close_button = tk.Button(frame_range, text="Close All Tabs", font=("Arial", 12), bg="red", fg="white",
                         command=lambda: threading.Thread(target=close_all_tabs, daemon=True).start())
close_button.grid(row=0, column=5, padx=8)

# region controls
frame_region = tk.Frame(root)
frame_region.pack(pady=8)

tk.Label(frame_region, text="Index chọn vùng:").grid(row=0, column=0, padx=5)
entry_region_index = tk.Entry(frame_region, width=6)
entry_region_index.grid(row=0, column=1, padx=5)
entry_region_index.insert(0, "4")

region_button = tk.Button(frame_region, text="Chọn & Lưu vùng (index)", font=("Arial", 12), bg="green", fg="white",
                          command=lambda: threading.Thread(target=select_region, args=(int(entry_region_index.get()),), daemon=True).start())
region_button.grid(row=0, column=2, padx=6)

# match controls (mới)
frame_match = tk.Frame(root)
frame_match.pack(pady=6)

tk.Label(frame_match, text="Category:").grid(row=0, column=0, padx=4)
entry_match_category = tk.Entry(frame_match, width=18)
entry_match_category.grid(row=0, column=1, padx=4)
entry_match_category.insert(0, "default")

tk.Label(frame_match, text="Threshold:").grid(row=0, column=2, padx=4)
entry_threshold = tk.Entry(frame_match, width=6)
entry_threshold.grid(row=0, column=3, padx=4)
entry_threshold.insert(0, "0.88")

tk.Label(frame_match, text="Interval(s):").grid(row=0, column=4, padx=4)
entry_interval = tk.Entry(frame_match, width=6)
entry_interval.grid(row=0, column=5, padx=4)
entry_interval.insert(0, "3")

def on_check_once():
    try:
        idx = int(entry_region_index.get())
        cat = entry_match_category.get().strip()
        thresh = float(entry_threshold.get())
        res = find_and_act_category(idx, cat, threshold=thresh, first_only=True, do_tap=True)
        if res:
            log(f"[Manual] Found {os.path.basename(res['template'])} score={res['score']:.3f}")
        else:
            log("[Manual] Không tìm thấy template nào.")
    except Exception as e:
        log(f"Lỗi check once: {e}")

def on_start_watch():
    try:
        idx = int(entry_region_index.get())
        cat = entry_match_category.get().strip()
        thresh = float(entry_threshold.get())
        interval = float(entry_interval.get())
        # sử dụng selected_region nếu bạn đã chọn vùng trước đó; nếu None -> toàn màn
        start_watch_category(idx, cat, threshold=thresh, interval_sec=interval, search_region=selected_region, do_tap=True)
    except Exception as e:
        log(f"Lỗi start watch: {e}")

def on_stop_watch():
    try:
        idx = int(entry_region_index.get())
        cat = entry_match_category.get().strip()
        stop_watch_category(idx, cat)
    except Exception as e:
        log(f"Lỗi stop watch: {e}")

btn_check = tk.Button(frame_match, text="Check Once", command=on_check_once, bg="#6fa")
btn_check.grid(row=1, column=0, columnspan=2, pady=4, padx=6)

btn_watch_start = tk.Button(frame_match, text="Start Watch", command=on_start_watch, bg="#a6f")
btn_watch_start.grid(row=1, column=2, columnspan=2, pady=4, padx=6)

btn_watch_stop = tk.Button(frame_match, text="Stop Watch", command=on_stop_watch, bg="#f66")
btn_watch_stop.grid(row=1, column=4, columnspan=2, pady=4, padx=6)

# text log
text_box = tk.Text(root, height=20, width=100)
text_box.pack(pady=10)

# Khi mở app → đọc file để set counter
load_last_account()

root.mainloop()
