import pyperclip
import psutil
from zeroconf import ServiceInfo, ServiceBrowser, Zeroconf
import socket
import threading
from state import log, last_clipboard, broadcast, peers_lock, peers, HANDSHAKE, PORT, update_tray
from clipboard import watch_clipboard

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
                        log("Received & forwarded")
                    else:
                        log("Received")
        except Exception as e:
            log(f"receive_loop error: {e}")
            break
    with peers_lock:
        if conn in peers:
            peers.remove(conn)
    conn.close()
    log("Peer disconnected")
    with peers_lock:
        update_tray("server", f"ClipboardSync: сервер, {len(peers)} клиента")

def handle_incoming(conn: socket.socket, addr) -> None:
    conn.settimeout(2)
    try:
        hs = conn.recv(len(HANDSHAKE))
        if hs != HANDSHAKE:
            raise ValueError("bad handshake")
    except (socket.timeout, ValueError, OSError):
        log(f"Probe or bad client from {addr}, ignoring")
        conn.close()
        return
    conn.settimeout(None)
    log(f"Client connected: {addr}")
    with peers_lock:
        peers.append(conn)
        update_tray("server", f"ClipboardSync: сервер, {len(peers)} клиента")
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
    info = ServiceInfo(
        "_clipboard._tcp.local.",
        "ClipboardSync._clipboard._tcp.local.",
        addresses=[socket.inet_aton(ip) for ip in ips],
        port=PORT
    )
    zc = Zeroconf()
    zc.register_service(info)
    log(f"Service registered on {ips}")
    update_tray("server", "ClipboardSync: сервер, ожидание клиентов")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(10)
    log(f"Listening on 0.0.0.0:{PORT}")
    threading.Thread(target=watch_clipboard, daemon=True).start()
    while True:
        conn, addr = server.accept()
        threading.Thread(target=handle_incoming, args=(conn, addr), daemon=True).start()

def run_as_client(ip: str) -> None:
    log(f"Connecting to server at {ip}")
    update_tray("client", f"ClipboardSync: подключение к {ip}...")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((ip, PORT))
    client.sendall(HANDSHAKE)
    with peers_lock:
        peers.append(client)
    update_tray("client", f"ClipboardSync: клиент → {ip}")
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

    log("Searching for server...")
    zc = Zeroconf()
    ServiceBrowser(zc, "_clipboard._tcp.local.", handlers=[on_service_found])
    event.wait(timeout=5)
    zc.close()
    return host[0]

