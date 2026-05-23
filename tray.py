import os
import sys
import pystray
from PIL import Image, ImageDraw
from state import (set_tray_icon, clipboard_history, history_lock, hash_data,
                   last_clipboard_hash, broadcast, log)
from clipboard import write_clipboard

def has_display() -> bool:
    if sys.platform in ("win32", "darwin"):
        return True
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))

def create_icon_image(status: str = "searching"):
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    colors = {
        "searching": "#FFA500",
        "server": "#4CAF50",
        "client": "#2196F3",
        "error": "#F44336",
    }
    color = colors.get(status, "#888888")
    draw.ellipse([4, 4, 60, 60], fill=color)

    cx, cy = size // 2, size // 2
    w = 4
    if status == "searching":
        for r, a in [(22, 60), (15, 60), (8, 60)]:
            draw.arc([cx - r, cy - r, cx + r, cy + r], start=200, end=340, fill="white", width=w)
    elif status == "server":
        draw.rectangle([cx - w, cy - 18, cx + w, cy + 18], fill="white")
        draw.rectangle([cx - 18, cy - w, cx + 18, cy + w], fill="white")
    elif status == "client":
        draw.polygon([
            (cx - 14, cy - 12),
            (cx + 4, cy),
            (cx - 14, cy + 12),
        ], fill="white")
        draw.rectangle([cx - 14, cy - w, cx + 4, cy + w], fill="white")
    elif status == "error":
        draw.line([cx - 14, cy - 14, cx + 14, cy + 14], fill="white", width=w + 1)
        draw.line([cx + 14, cy - 14, cx - 14, cy + 14], fill="white", width=w + 1)
    return img

def run_tray(on_quit_callback):
    def on_history_click(msg_type: str, data: bytes) -> None:
        import state
        state.ignore_clipboard_check.set()
        try:
            write_clipboard(msg_type, data)
            last_clipboard_hash[0] = hash_data(data)
            encrypted_data = state.cipher.encrypt(data)
            broadcast(msg_type, encrypted_data)
            log(f"Restored from history: {msg_type}")
        finally:
            state.ignore_clipboard_check.clear()

    def clear_history() -> None:
        with history_lock:
            clipboard_history.clear()
        update_menu()

    def make_history_callback(msg_type, data):
        def callback(icon, item):
            on_history_click(msg_type, data)
        return callback

    def build_menu():
        items = []
        with history_lock:
            for item in clipboard_history:
                cb = make_history_callback(item["type"], item["data"])
                items.append(pystray.MenuItem(item["preview"], cb))
        if items:
            items.append(pystray.Menu.SEPARATOR)
            items.append(pystray.MenuItem("Очистить историю", lambda icon, x: clear_history()))
            items.append(pystray.Menu.SEPARATOR)
        items.append(pystray.MenuItem("Выйти", lambda icon, x: (on_quit_callback(), icon.stop())))
        return items

    def update_menu():
        import state
        if state.tray_icon:
            state.tray_icon.menu = pystray.Menu(*build_menu())

    import state
    state.menu_update_callback = update_menu
    icon = pystray.Icon(
        name="Network Clipboard",
        icon=create_icon_image(),
        title="Поиск...",
        menu=pystray.Menu(*build_menu())
    )
    set_tray_icon(icon)
    icon.run()