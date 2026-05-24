import threading
import os
import time
import atexit
import tkinter
from tkinter import simpledialog
from network import find_server, run_as_client, run_as_server
from tray import run_tray, has_display
from state import log, set_display_mode, init_crypto, close_all_connections

def start_networking() -> None:
    while True:
        server_ip = find_server()
        if server_ip:
            run_as_client(server_ip)
            log("Restarting...")
            time.sleep(3)
        else:
            run_as_server()
            time.sleep(3)

def quit_app() -> None:
    log("Quitting...")
    close_all_connections()
    os._exit(0)

if __name__ == "__main__":
    atexit.register(close_all_connections)
    root = tkinter.Tk()
    root.withdraw()
    password = simpledialog.askstring("Network Clipboard", "Введите ключ шифрования", show='*')
    if not password:
        quit_app()
    assert password is not None
    init_crypto(password)
    if has_display():
        set_display_mode(True)
        threading.Thread(target=start_networking, daemon=True).start()
        run_tray(on_quit_callback=quit_app)
    else:
        log("No display detected, running in terminal mode")
        start_networking()