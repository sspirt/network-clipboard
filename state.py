import socket
import threading
import hashlib
import zipfile
import io
from typing import TypedDict
from plyer import notification

PORT = 9999
HANDSHAKE = bytes(b"CLIPSYNV1\n")

last_clipboard_hash: list[str] = [""]
peers: list[socket.socket] = []
peers_lock = threading.Lock()
clipboard_lock = threading.Lock()
display_mode: bool = False
tray_icon = None
history_lock = threading.Lock()
ignore_clipboard_check = threading.Event()
menu_update_callback = None

class HistoryItem(TypedDict):
    type: str
    preview: str
    data: bytes

clipboard_history: list[HistoryItem] = []

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

def add_to_history(msg_type: str, data: bytes) -> None:
    if msg_type == "text":
        try:
            preview = data.decode("utf-8").strip()
            preview = (preview[:27] + "...") if len(preview) > 30 else preview
            preview = f"📝 {preview}"
        except Exception:
            preview = "📝 [Текст]"
    elif msg_type == "image":
        preview = "🖼 [Изображение]"
    elif msg_type == "file":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as zf:
                roots = {name.split("/")[0] for name in zf.namelist()}
            preview = f"📁 Файлы ({len(roots)} всего)"
        except Exception:
            preview = "📁 [Файлы]"
    else:
        preview = "📦 [Данные]"
    current_hash = hash_data(data)
    with history_lock:
        clipboard_history[:] = [item for item in clipboard_history if hash_data(item["data"]) != current_hash]
        clipboard_history.insert(0, {"type": msg_type, "data": data, "preview": preview})
        log(f"History size: {len(clipboard_history)}")
        if len(clipboard_history) > 10:
            clipboard_history.pop()
    global menu_update_callback
    if menu_update_callback is not None:
        try:
            menu_update_callback()
        except Exception as e:
            log(f"Tray updating error: {e}")