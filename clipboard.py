import pyperclip
import time
from state import last_clipboard, broadcast, peers

def watch_clipboard() -> None:
    while True:
        try:
            current = pyperclip.paste()
            if current != last_clipboard[0]:
                last_clipboard[0] = current
                broadcast(current)
                print(f"Sent to {len(peers)} peer(s)")
            time.sleep(0.5)
        except Exception as e:
            print(f"watch_clipboard error: {e}")