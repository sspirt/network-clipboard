import pyperclip
import socket
import threading

PORT = 9999
HANDSHAKE = bytes(b"CLIPSYNV1\n")

peers: list[socket.socket] = []
peers_lock = threading.Lock()
tray_icon = None

def log(msg: str) -> None:
    print(msg)

def safe_paste() -> str:
    try:
        return pyperclip.paste()
    except Exception:
        return ""

last_clipboard: list[str] = [safe_paste()]

def make_message(text: str) -> bytes:
    encoded = text.encode()
    return f"{len(encoded)}\n".encode() + encoded

def broadcast(text: str, exclude: socket.socket | None = None) -> None:
    msg = make_message(text)
    with peers_lock:
        for peer in peers[:]:
            if peer is exclude:
                continue
            try:
                peer.sendall(msg)
            except Exception:
                peers.remove(peer)

def update_tray(status: str, tooltip: str) -> None:
    from tray import create_icon_image
    if tray_icon is None:
        return
    tray_icon.icon = create_icon_image(status)
    tray_icon.title = tooltip