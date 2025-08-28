# worker.py
# Luồng xử lý cho mỗi instance: launch, mở game, thực hiện tap, lưu account

from time import sleep
from logger_widget import log
from ldconsole import run_ldconsole
from account_manager import get_new_account, mark_done
from config import GAME_PACKAGE, LAUNCH_DELAY, GAME_LAUNCH_DELAY, TAP_RETRY_DELAY

def worker_instance(idx: int) -> None:
    log(f"[LD {idx}] Bắt đầu quản lý instance...")
    account_name = get_new_account()
    log(f"[LD {idx}] Gán account: {account_name}")

    run_ldconsole(["launch", "--index", str(idx)])
    log(f"[LD {idx}] Đã mở LDPlayer instance")

    sleep(LAUNCH_DELAY)
    run_ldconsole([
        "adb", "--index", str(idx),
        "--command", f"shell monkey -p {GAME_PACKAGE} -c android.intent.category.LAUNCHER 1"
    ])
    log(f"[LD {idx}] Đã mở game {GAME_PACKAGE}")

    sleep(GAME_LAUNCH_DELAY)
    for i in range(3):
        run_ldconsole(["adb", "--index", str(idx), "--command", "shell input tap 200 200"])
        log(f"[LD {idx}] ({account_name}) Tap (200,200)")
        sleep(TAP_RETRY_DELAY)

    mark_done(account_name)
    log(f"[LD {idx}] Hoàn thành công việc với {account_name}, đã lưu vào file.")
