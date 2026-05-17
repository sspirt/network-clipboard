import pyperclip
import time
import psutil
from zeroconf import ServiceInfo, ServiceBrowser, Zeroconf
import socket
import threading

PORT = 9999
HANDSHAKE = b"CLIPSYNV1\n"

last_clipboard = [pyperclip.paste()]
peers: list[socket.socket] = []
peers_lock = threading.Lock()

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

def receive_loop(conn: socket.socket) -> None:
    buffer = ""
    while True:
        try:
            data = conn.recv(4096).decode()
            if not data:
                break
            buffer += data
            while "\n" in buffer:
                length_str, buffer = buffer.split("\n", 1)
                length = int(length_str)
                while len(buffer.encode()) < length:
                    chunk = conn.recv(4096).decode()
                    if not chunk:
                        return
                    buffer += chunk
                text = buffer[:length]
                buffer = buffer[length:]
                last_clipboard[0] = text
                pyperclip.copy(text)
                broadcast(text, exclude=conn)
                with peers_lock:
                    if len(peers) >= 2:
                        print("Received & forwarded")
                    else:
                        print("Received")
        except Exception as e:
            print(f"receive_loop error: {e}")
            break
    with peers_lock:
        if conn in peers:
            peers.remove(conn)
    conn.close()
    print("Peer disconnected")

def handle_incoming(conn: socket.socket, addr) -> None:
    conn.settimeout(2)
    try:
        hs = conn.recv(len(HANDSHAKE))
        if hs != HANDSHAKE:
            raise ValueError("bad handshake")
    except (socket.timeout, ValueError, OSError):
        print(f"Probe or bad client from {addr}, ignoring")
        conn.close()
        return
    conn.settimeout(None)
    print(f"Client connected: {addr}")
    with peers_lock:
        peers.append(conn)
    receive_loop(conn)

def run_as_server() -> None:
    def get_all_ips() -> list[str]:
        ips = []
        for addresses in psutil.net_if_addrs().values():
            for address in addresses:
                if address.family == socket.AF_INET and address.address != "127.0.0.1":
                    ips.append(address.address)
        return ips

    ips = get_all_ips()
    info = ServiceInfo("_clipboard._tcp.local.","ClipboardSync._clipboard._tcp.local.",
                       addresses=[socket.inet_aton(ip) for ip in ips], port=PORT)
    zc = Zeroconf()
    zc.register_service(info)
    print(f"Service registered on {ips}")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(10)
    print(f"Listening on 0.0.0.0:{PORT}")
    threading.Thread(target=watch_clipboard, daemon=True).start()
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_incoming, args=(conn, addr), daemon=True).start()

def run_as_client(ip: str) -> None:
    print(f"Connecting to server at {ip}")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((ip, PORT))
    client.sendall(HANDSHAKE)
    with peers_lock:
        peers.append(client)
    threading.Thread(target=receive_loop, args=(client,), daemon=True).start()
    watch_clipboard()

def find_server() -> str | None:
    host: list[str | None] = [None]
    event = threading.Event()

    def try_connect(ip: str) -> bool:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        try:
            return s.connect_ex((ip, PORT)) == 0
        finally:
            s.close()

    def on_service_found(zeroconf, service_type, name, **kwargs) -> None:
        info = zeroconf.get_service_info(service_type, name)
        if info:
            for address in info.addresses:
                ip = socket.inet_ntoa(address)
                if try_connect(ip):
                    host[0] = ip
                    event.set()
                    return

    print("Searching for server...")
    zc = Zeroconf()
    ServiceBrowser(zc, "_clipboard._tcp.local.", handlers=[on_service_found])
    event.wait(timeout=5)
    zc.close()
    return host[0]

if __name__ == "__main__":
    server_ip = find_server()
    if server_ip:
        run_as_client(server_ip)
    else:
        run_as_server()