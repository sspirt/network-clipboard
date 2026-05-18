import threading
import time
from state import last_clipboard, broadcast, peers, log, safe_paste, make_message

def watch_clipboard() -> None:
    while True:
        try:
            current = safe_paste()
            if current and current != last_clipboard[0]:
                last_clipboard[0] = current
                broadcast(current)
                log(f"Sent to {len(peers)} peer(s)")
            time.sleep(0.5)
        except Exception as e:
            log(f"watch_clipboard error: {e}")

def watch_and_send(conn, stop_event: threading.Event = None) -> None:
    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            current = safe_paste()
            if current and current != last_clipboard[0]:
                last_clipboard[0] = current
                conn.sendall(make_message(current))
                log("Sent")
            time.sleep(0.5)
        except Exception as e:
            log(f"watch_and_send error: {e}")
            break