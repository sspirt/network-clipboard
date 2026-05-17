import threading
import os
import sys
from network import find_server, run_as_client, run_as_server
from tray import run_tray, has_display
from state import log

def start_networking() -> None:
    server_ip = find_server()
    if server_ip:
        run_as_client(server_ip)
    else:
        run_as_server()

def quit_app() -> None:
    log("Quitting...")
    os._exit(0)

if __name__ == "__main__":
    if has_display():
        sys.stdout = open(os.devnull, "w")
        sys.stderr = open(os.devnull, "w")
        threading.Thread(target=start_networking, daemon=True).start()
        run_tray(on_quit_callback=quit_app)
    else:
        log("No display detected, running in terminal mode")
        start_networking()