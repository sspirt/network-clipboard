import sys
import importlib
import threading
import time
from state import last_clipboard_hash, broadcast, peers, log, make_message, hash_data, peers_lock

def read_clipboard() -> tuple[str, bytes] | None:
    readers = {
        "darwin": read_macos,
        "win32": read_windows,
        "linux": read_linux
    }
    reader = readers.get(sys.platform)
    if not reader:
        log(f"Platform {sys.platform} not supported")
        return None
    try:
        return reader()
    except Exception as e:
        log(f"read_clipboard error: {e}")
        return None

def read_macos() -> tuple[str, bytes] | None:
    AppKit = importlib.import_module("AppKit")
    NSPasteboard = AppKit.NSPasteboard
    NSPasteboardTypeString = AppKit.NSPasteboardTypeString
    NSPasteboardTypePNG = AppKit.NSPasteboardTypePNG
    pb = NSPasteboard.generalPasteboard()
    png = pb.dataForType_(NSPasteboardTypePNG)
    if png:
        return "image", bytes(png)
    text = pb.stringForType_(NSPasteboardTypeString)
    if text:
        return "text", text.encode("utf-8")
    return None

def read_windows() -> tuple[str, bytes] | None:
    import io
    from PIL import Image
    win32clipboard = importlib.import_module("win32clipboard")
    opened = False
    for attempt in range(10):
        try:
            win32clipboard.OpenClipboard()
            opened = True
            break
        except Exception as e:
            log(f"read_windows error: {e}, attempt {attempt}")
            time.sleep(0.1)
    if not opened:
        log("read_windows error: could not open clipboard")
        return None
    try:
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
            dib = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
            bmp_header = (b"BM" + (len(dib) + 14).to_bytes(4, "little") +
                          b"\x00\x00\x00\x00\x36\x00\x00\x00")
            img = Image.open(io.BytesIO(bmp_header + dib))
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return "image", buf.getvalue()
        elif win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
            text = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
            return "text", text.encode("utf-8")
    except Exception as e:
        log(f"read_windows error: {e}")
    finally:
        if opened:
            win32clipboard.CloseClipboard()
    return None

def read_linux() -> tuple[str, bytes] | None:
    import subprocess
    result = subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
                            capture_output=True)
    if result.returncode == 0 and result.stdout:
        return "image", result.stdout
    result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True)
    if result.returncode == 0 and result.stdout:
        return "text", result.stdout
    return None

def write_clipboard(msg_type: str, data: bytes) -> None:
    writers = {
        "darwin": write_macos,
        "win32": write_windows,
        "linux": write_linux
    }
    writer = writers.get(sys.platform)
    if not writer:
        log(f"Platform {sys.platform} not supported")
        return None
    try:
        writer(msg_type, data)
    except Exception as e:
        log(f"write_clipboard error: {e}")
        return None

def write_macos(msg_type: str, data: bytes) -> None:
    AppKit = importlib.import_module("AppKit")
    NSPasteboard = AppKit.NSPasteboard
    NSPasteboardTypeString = AppKit.NSPasteboardTypeString
    NSPasteboardTypePNG = AppKit.NSPasteboardTypePNG
    Foundation = importlib.import_module("Foundation")
    NSData = Foundation.NSData
    pb = NSPasteboard.generalPasteboard()
    pb.clearContents()
    if msg_type == "image":
        pb.setData_forType_(NSData.dataWithBytes_length_(data, len(data)), NSPasteboardTypePNG)
    elif msg_type == "text":
        pb.setString_forType_(data.decode("utf-8"), NSPasteboardTypeString)

def write_windows(msg_type: str, data: bytes) -> None:
    import io
    from PIL import Image
    win32clipboard = importlib.import_module("win32clipboard")
    opened = False
    for attempt in range(10):
        try:
            win32clipboard.OpenClipboard()
            opened = True
            break
        except Exception as e:
            log(f"write_windows error: {e}, attempt {attempt}")
            time.sleep(0.1)
    if not opened:
        log(f"write_windows error: could not open clipboard")
        return
    try:
        win32clipboard.EmptyClipboard()
        if msg_type == "image":
            img = Image.open(io.BytesIO(data)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="BMP")
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, buf.getvalue()[14:])
        elif msg_type == "text":
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, data.decode("utf-8"))
    except Exception as e:
        log(f"write_windows error: {e}")
    finally:
        if opened:
            win32clipboard.CloseClipboard()

def write_linux(msg_type: str, data: bytes) -> None:
    import subprocess
    mime = "image/png" if msg_type == "image" else "text/plain"
    subprocess.run(["xclip", "-selection", "clipboard", "-t", mime], input=data, capture_output=True)

def watch_clipboard() -> None:
    while True:
        try:
            clipboard_result = read_clipboard()
            if clipboard_result:
                msg_type, data = clipboard_result
                clipboard_hash = hash_data(data)
                if clipboard_hash != last_clipboard_hash[0]:
                    last_clipboard_hash[0] = clipboard_hash
                    broadcast(msg_type, data)
                    with peers_lock:
                        log(f"Sent {msg_type} to {len(peers)} peer(s)")
            time.sleep(0.5)
        except Exception as e:
            log(f"watch_clipboard error: {e}")

def watch_and_send(conn, stop_event: threading.Event | None = None) -> None:
    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            clipboard_result = read_clipboard()
            if clipboard_result:
                msg_type, data = clipboard_result
                clipboard_hash = hash_data(data)
                if clipboard_hash != last_clipboard_hash[0]:
                    last_clipboard_hash[0] = clipboard_hash
                    conn.sendall(make_message(msg_type, data))
                    log(f"Sent {msg_type}")
            time.sleep(0.5)
        except Exception as e:
            log(f"watch_and_send error: {e}")
            break