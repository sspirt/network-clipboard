import pyperclip
import socket
import threading

PORT = 9999
HANDSHAKE = bytes(b"CLIPSYNV1\n")

last_clipboard = [pyperclip.paste()]
peers: list[socket.socket] = []
peers_lock = threading.Lock()

def log(msg: str) -> None:
    print(msg)

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