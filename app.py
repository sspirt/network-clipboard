import threading
import os
import time
from network import find_server, run_as_client, run_as_server
from tray import run_tray, has_display
from state import log, set_display_mode

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
    os._exit(0)

if __name__ == "__main__":
    if has_display():
        set_display_mode(True)
        threading.Thread(target=start_networking, daemon=True).start()
        run_tray(on_quit_callback=quit_app)
    else:
        log("No display detected, running in terminal mode")
        start_networking()