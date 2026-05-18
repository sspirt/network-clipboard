import os
import sys
import pystray
from PIL import Image, ImageDraw
from state import set_tray_icon

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
            (cx + 4,  cy),
            (cx - 14, cy + 12),
        ], fill="white")
        draw.rectangle([cx - 14, cy - w, cx + 4, cy + w], fill="white")
    elif status == "error":
        draw.line([cx - 14, cy - 14, cx + 14, cy + 14], fill="white", width=w + 1)
        draw.line([cx + 14, cy - 14, cx - 14, cy + 14], fill="white", width=w + 1)
    return img

def run_tray(on_quit_callback):
    menu = pystray.Menu(pystray.MenuItem("Выйти", lambda icon, _ : (on_quit_callback(), icon.stop())))
    icon = pystray.Icon(
        name="Network Clipboard",
        icon=create_icon_image(),
        title="Поиск...",
        menu=menu
    )
    set_tray_icon(icon)
    icon.run()