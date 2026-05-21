import sys
import importlib
import threading
import time
import io
import zipfile
import tempfile
from pathlib import Path
from state import (last_clipboard_hash, broadcast, peers, log, make_message, ignore_clipboard_check,
                   hash_data, peers_lock, clipboard_lock, notify, add_to_history)

temp_dir: Path | None = None
last_unpacked_paths: set[str] = set()

def get_temp_dir() -> Path | None:
    global temp_dir
    if temp_dir is None:
        temp_dir = Path(tempfile.mkdtemp(prefix="netclip_"))
    return temp_dir

def pack_files(paths: list[str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            p = Path(path)
            if p.is_dir():
                for file in p.rglob("*"):
                    if file.is_file():
                        arcname = Path(p.name) / file.relative_to(p)
                        info = zipfile.ZipInfo(str(arcname))
                        info.date_time = (1980, 1, 1, 0, 0, 0)
                        with open(file, "rb") as f:
                            zf.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
            elif p.is_file():
                info = zipfile.ZipInfo(p.name)
                info.date_time = (1980, 1, 1, 0, 0, 0)
                with open(p, "rb") as f:
                    zf.writestr(info, f.read(), zipfile.ZIP_DEFLATED)
    return buffer.getvalue()

def unpack_files(data: bytes) -> list[str]:
    global last_unpacked_paths
    receive_dir = get_temp_dir()
    extracted = set()
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        for member in zf.namelist():
            zf.extract(member, receive_dir)
            root = member.split("/")[0]
            extracted.add(str(receive_dir / root))
    last_unpacked_paths = extracted
    return list(extracted)

def is_our_unpacked(paths: list[str]) -> bool:
    return bool(last_unpacked_paths and set(paths) == last_unpacked_paths)

def read_clipboard() -> tuple[str, bytes] | None:
    readers = {
        "darwin": read_macos,
        "win32": read_windows,
        "linux": read_linux
    }
    reader = readers.get(sys.platform)
    if not reader:
        return None
    with clipboard_lock:
        try:
            return reader()
        except Exception as e:
            log(f"read_clipboard error: {e}")
            return None

def read_macos() -> tuple[str, bytes] | None:
    AppKit = importlib.import_module("AppKit")
    pb = AppKit.NSPasteboard.generalPasteboard()
    files = pb.propertyListForType_(AppKit.NSFilenamesPboardType)
    if files:
        paths = list(files)
        if is_our_unpacked(paths):
            return None
        return "file", "\n".join(paths).encode("utf-8")
    png = pb.dataForType_(AppKit.NSPasteboardTypePNG)
    if png:
        return "image", bytes(png)
    text = pb.stringForType_(AppKit.NSPasteboardTypeString)
    if text:
        return "text", text.encode("utf-8")
    return None

def read_windows() -> tuple[str, bytes] | None:
    from PIL import Image
    win32clipboard = importlib.import_module("win32clipboard")
    CF_HDROP = 15
    opened = False
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            opened = True
            break
        except Exception:
            time.sleep(0.05)
    if not opened:
        return None
    try:
        if win32clipboard.IsClipboardFormatAvailable(CF_HDROP):
            paths = list(win32clipboard.GetClipboardData(CF_HDROP))
            if is_our_unpacked(paths):
                return None
            return "file", "\n".join(paths).encode("utf-8")
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_DIB):
            try:
                dib = win32clipboard.GetClipboardData(win32clipboard.CF_DIB)
                bmp_header = (b"BM" + (len(dib) + 14).to_bytes(4, "little") +
                              b"\x00\x00\x00\x00\x36\x00\x00\x00")
                img = Image.open(io.BytesIO(bmp_header + dib))
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return "image", buf.getvalue()
            except Exception:
                pass
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):
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
    from urllib.parse import unquote, urlparse
    result = subprocess.run(["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
                            capture_output=True)
    if result.returncode == 0 and result.stdout:
        uris = result.stdout.decode().strip().splitlines()
        paths = [unquote(urlparse(uri.strip()).path) for uri in uris if uri.strip().startswith("file://")]
        if paths:
            if is_our_unpacked(paths):
                return None
            return "file", "\n".join(paths).encode("utf-8")
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
        return
    with clipboard_lock:
        try:
            writer(msg_type, data)
        except Exception as e:
            log(f"write_clipboard error: {e}")

def write_macos(msg_type: str, data: bytes) -> None:
    AppKit = importlib.import_module("AppKit")
    Foundation = importlib.import_module("Foundation")
    pb = AppKit.NSPasteboard.generalPasteboard()
    pb.clearContents()
    if msg_type == "file":
        paths = unpack_files(data)
        pb.setPropertyList_forType_(paths, AppKit.NSFilenamesPboardType)
    elif msg_type == "image":
        nsdata = Foundation.NSData.dataWithBytes_length_(data, len(data))
        pb.setData_forType_(nsdata, AppKit.NSPasteboardTypePNG)
    elif msg_type == "text":
        pb.setString_forType_(data.decode("utf-8"), AppKit.NSPasteboardTypeString)

def write_windows(msg_type: str, data: bytes) -> None:
    import struct
    from PIL import Image
    win32clipboard = importlib.import_module("win32clipboard")
    CF_HDROP = 15
    opened = False
    for _ in range(10):
        try:
            win32clipboard.OpenClipboard()
            opened = True
            break
        except Exception:
            time.sleep(0.05)
    if not opened:
        return
    try:
        win32clipboard.EmptyClipboard()
        if msg_type == "file":
            paths = unpack_files(data)
            paths_win = [str(Path(p).resolve()) for p in paths]
            files_bytes = ("\0".join(paths_win) + "\0\0").encode("utf-16-le")
            dropfiles = struct.pack("IIIII", 20, 0, 0, 0, 1)
            win32clipboard.SetClipboardData(CF_HDROP, dropfiles + files_bytes)
        elif msg_type == "image":
            img = Image.open(io.BytesIO(data)).convert("RGB")
            buf = io.BytesIO()
            img.save(buf, format="BMP")
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, buf.getvalue()[14:])
        elif msg_type == "text":
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, data.decode("utf-8"))
    except Exception as e:
        log(f"write_windows error: {e}")
    finally:
        win32clipboard.CloseClipboard()

def write_linux(msg_type: str, data: bytes) -> None:
    import subprocess
    if msg_type == "file":
        paths = unpack_files(data)
        uris = "\n".join(f"file://{p}" for p in paths).encode()
        subprocess.run(["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
                       input=uris, capture_output=True)
    elif msg_type == "image":
        subprocess.run(["xclip", "-selection", "clipboard", "-t", "image/png"], input=data, capture_output=True)
    elif msg_type == "text":
        subprocess.run(["xclip", "-selection", "clipboard"], input=data, capture_output=True)

def watch_clipboard() -> None:
    while True:
        try:
            if ignore_clipboard_check.is_set():
                time.sleep(0.1)
                continue
            clipboard_result = read_clipboard()
            if clipboard_result:
                msg_type, data = clipboard_result
                clipboard_hash = hash_data(data)
                if clipboard_hash != last_clipboard_hash[0]:
                    last_clipboard_hash[0] = clipboard_hash
                    if msg_type == "file":
                        log("Detected new files, packing...")
                        notify("Отправка", "Упаковка и отправка файлов...")
                        paths = data.decode("utf-8").split("\n")
                        send_data = pack_files(paths)
                    else:
                        send_data = data
                    add_to_history(msg_type, send_data)
                    broadcast(msg_type, send_data)
                    with peers_lock:
                        log(f"Sent {msg_type} to {len(peers)} peer(s)")
                    if msg_type == "file":
                        notify("Отправка", "Файлы отправлены")
            time.sleep(0.5)
        except Exception as e:
            log(f"watch_clipboard error: {e}")

def watch_and_send(conn, stop_event: threading.Event | None = None) -> None:
    while True:
        if stop_event and stop_event.is_set():
            break
        try:
            if ignore_clipboard_check.is_set():
                time.sleep(0.1)
                continue
            clipboard_result = read_clipboard()
            if clipboard_result:
                msg_type, data = clipboard_result
                clipboard_hash = hash_data(data)
                if clipboard_hash != last_clipboard_hash[0]:
                    last_clipboard_hash[0] = clipboard_hash
                    if msg_type == "file":
                        log("Detected new files, packing...")
                        notify("Отправка", "Упаковка и отправка файлов...")
                        paths = data.decode("utf-8").split("\n")
                        send_data = pack_files(paths)
                    else:
                        send_data = data
                    add_to_history(msg_type, send_data)
                    conn.sendall(make_message(msg_type, send_data))
                    log(f"Sent {msg_type}")
                    if msg_type == "file":
                        notify("Отправка", "Файлы отправлены")
            time.sleep(0.5)
        except Exception as e:
            log(f"watch_and_send error: {e}")
            break