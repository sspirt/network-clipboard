import time
from state import last_clipboard, broadcast, peers, log, safe_paste

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