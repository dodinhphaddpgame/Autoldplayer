# gui.py
# Giao diện Tkinter chính (đã chỉnh để selectROI chạy an toàn trên main thread)
# - capture_screenshot_img chạy trong background thread
# - cv2.selectROI và các dialog Tkinter chạy trên main thread thông qua root.after

import threading
import tkinter as tk
from tkinter import simpledialog

from logger_widget import set_text_widget, log
from ldconsole import get_instances
from worker import worker_instance
from screenshot import capture_screenshot_img
from config import REGIONS_DIR
import os
import cv2
from datetime import datetime

# Biến global để có thể schedule callback từ thread khác
root = None
region_button = None

def open_tabs(entry_start, entry_end):
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
            from ldconsole import run_ldconsole
            run_ldconsole(["quit", "--index", idx])
            log(f"Đã gửi lệnh tắt LDPlayer instance {idx}")
        import time
        time.sleep(5)

# ---------- Chọn vùng (safe: capture trong background, dialog/ROI trên main thread) ----------

def select_region_start(idx=1):
    """
    Bắt đầu quy trình chọn vùng:
    - Hỏi category bằng simpledialog (phải chạy trên main thread)
    - Nếu user OK -> spawn background thread để capture ảnh
    """
    global region_button
    # Hỏi category trên main thread (an toàn)
    category = simpledialog.askstring("Category", "Nhập tên category (ví dụ: login, clickimage):", initialvalue="default")
    if category is None:
        log("Đã hủy (không nhập category).")
        return
    category = category.strip() or "default"

    try:
        # disable nút tránh bấm nhiều lần trong khi đang capture
        if region_button is not None:
            region_button.config(state='disabled')
    except Exception:
        pass

    log(f"Đang chụp màn hình LDPlayer {idx} (category={category})...")

    # Start background thread để capture (không block GUI)
    threading.Thread(target=_select_region_capture_thread, args=(idx, category), daemon=True).start()


def _select_region_capture_thread(idx, category):
    """
    Chạy trong background: lấy ảnh từ LDPlayer rồi schedule xử lý ROI trên main thread.
    Nếu không lấy được ảnh sẽ log và re-enable nút.
    """
    global root, region_button
    img = capture_screenshot_img(idx)
    if img is None:
        log("Không chụp được ảnh từ LDPlayer.")
        # re-enable nút trên main thread
        try:
            if root:
                root.after(0, lambda: region_button.config(state='normal') if region_button else None)
        except Exception:
            pass
        return

    # Schedule hàm xử lý ROI trên main thread
    try:
        if root:
            root.after(0, lambda: _show_roi_on_main_thread(img, idx, category))
        else:
            # nếu root chưa sẵn sàng (hiếm), xử lý trực tiếp (giữ an toàn)
            _show_roi_on_main_thread(img, idx, category)
    except Exception as e:
        log(f"Lỗi schedule ROI trên main thread: {e}")
        try:
            if root:
                root.after(0, lambda: region_button.config(state='normal') if region_button else None)
        except Exception:
            pass


def _show_roi_on_main_thread(img, idx, category):
    """
    Hàm chạy trên main thread: mở cv2.selectROI, lưu ROI, hiển thị xác nhận,
    và re-enable nút chọn vùng.
    """
    global region_button
    try:
        clone = img.copy()
        # cv2.selectROI cần chạy trên luồng chính để GUI OpenCV hoạt động ổn định
        r = cv2.selectROI("Chọn vùng ảnh (Enter: xác nhận, Esc: hủy)", clone, False, False)
        cv2.destroyAllWindows()
    except Exception as e:
        log(f"Lỗi khi mở cửa sổ chọn vùng: {e}")
        # bật lại nút
        try:
            if region_button:
                region_button.config(state='normal')
        except Exception:
            pass
        return

    if r == (0, 0, 0, 0):
        log("Bạn chưa chọn vùng nào.")
        try:
            if region_button:
                region_button.config(state='normal')
        except Exception:
            pass
        return

    x, y, w, h = r
    x1, y1, x2, y2 = int(x), int(y), int(x + w), int(y + h)

    # tạo thư mục lưu theo category
    os.makedirs(REGIONS_DIR, exist_ok=True)
    category_dir = os.path.join(REGIONS_DIR, category)
    os.makedirs(category_dir, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{category}_idx{idx}_{ts}.png"
    fullpath = os.path.join(category_dir, filename)

    roi = img[y1:y2, x1:x2]
    try:
        cv2.imwrite(fullpath, roi)
        log(f"Đã lưu ảnh vùng vào: {fullpath}")
    except Exception as e:
        log(f"Lỗi lưu ROI image: {e}")

    # Hiển thị vùng đã chọn để xác nhận (vẽ khung xanh, hiện 1s)
    try:
        disp = img.copy()
        cv2.rectangle(disp, (x1, y1), (x2, y2), (0, 255, 0), 3)
        cv2.imshow("Vùng đã chọn (đóng sau 1s)", disp)
        cv2.waitKey(1000)
        cv2.destroyAllWindows()
    except Exception:
        pass

    # Bật lại nút chọn vùng
    try:
        if region_button:
            region_button.config(state='normal')
    except Exception:
        pass

# ---------------------------------------------------------------------------------------------


def build_gui():
    """
    Xây dựng GUI chính và đăng ký text widget cho logger.
    Ghi chú: khai báo global root để có thể schedule root.after(...) từ các thread.
    """
    global root, region_button
    root = tk.Tk()
    root.title("LDPlayer Auto Controller")
    root.geometry("640x520")

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

    open_button = tk.Button(root, text="Open Tabs", font=("Arial", 14), bg="blue", fg="white",
                            command=lambda: open_tabs(entry_start, entry_end))
    open_button.pack(pady=8)

    close_button = tk.Button(root, text="Close All Tabs", font=("Arial", 14), bg="red", fg="white",
                             command=lambda: threading.Thread(target=close_all_tabs, daemon=True).start())
    close_button.pack(pady=4)

    frame_region = tk.Frame(root)
    frame_region.pack(pady=8)

    tk.Label(frame_region, text="Index chọn vùng:").grid(row=0, column=0, padx=5)
    entry_region_index = tk.Entry(frame_region, width=6)
    entry_region_index.grid(row=0, column=1, padx=5)
    entry_region_index.insert(0, "1")

    # nút gọi select_region_start (không spawn thread ở đây)
    region_button = tk.Button(frame_region, text="Chọn & Lưu vùng (index)", font=("Arial", 12), bg="green", fg="white",
                              command=lambda: select_region_start(int(entry_region_index.get())))
    region_button.grid(row=0, column=2, padx=6)

    text_box = tk.Text(root, height=18, width=80)
    text_box.pack(pady=10)

    # đăng ký text widget để logger dùng
    set_text_widget(text_box)

    root.mainloop()


if __name__ == '__main__':
    build_gui()
