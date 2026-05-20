import socket
import threading
import hashlib
from plyer import notification

PORT = 9999
HANDSHAKE = bytes(b"CLIPSYNV1\n")

last_clipboard_hash: list[str] = [""]
peers: list[socket.socket] = []
peers_lock = threading.Lock()
clipboard_lock = threading.Lock()
display_mode:bool = False
tray_icon = None

def log(msg: str) -> None:
    print(msg)

def set_tray_icon(icon) -> None:
    global tray_icon
    tray_icon = icon

def set_display_mode(val: bool) -> None:
    global display_mode
    display_mode = val

def hash_data(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()

def make_message(msg_type: str, data: bytes) -> bytes:
    return f"{msg_type}\n{len(data)}\n".encode() + data

def broadcast(msg_type: str, data: bytes, exclude: socket.socket | None = None) -> None:
    msg = make_message(msg_type, data)
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

def notify(title: str, message: str) -> None:
    try:
        notification.notify(
            title=title,
            message=message,
            app_name="Network Clipboard",
            timeout=4,
        )
    except Exception:
        pass