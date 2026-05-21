import psutil
from zeroconf import ServiceInfo, ServiceBrowser, Zeroconf, NonUniqueNameException
import socket
import threading
from state import (log, broadcast, peers_lock, peers, HANDSHAKE, PORT,
                   update_tray, notify, hash_data, last_clipboard_hash, add_to_history)
from clipboard import watch_clipboard, watch_and_send, write_clipboard

def receive_loop(conn: socket.socket) -> None:
    buffer = b""
    BUFF_SIZE = 262144
    while True:
        try:
            data = conn.recv(BUFF_SIZE)
            if not data:
                break
            buffer += data
            while True:
                if b"\n" not in buffer:
                    break
                nl = buffer.index(b"\n")
                msg_type = buffer[:nl].decode()
                buffer = buffer[nl + 1:]
                if b"\n" not in buffer:
                    chunk = conn.recv(BUFF_SIZE)
                    if not chunk:
                        break
                    buffer += chunk
                nl = buffer.index(b"\n")
                length = int(buffer[:nl].decode())
                buffer = buffer[nl + 1:]
                while len(buffer) < length:
                    chunk = conn.recv(BUFF_SIZE)
                    if not chunk:
                        break
                    buffer += chunk
                if len(buffer) < length:
                    break
                payload = buffer[:length]
                buffer = buffer[length:]
                last_clipboard_hash[0] = hash_data(payload)
                write_clipboard(msg_type, payload)
                add_to_history(msg_type, payload)
                if msg_type == "file":
                    notify("Получение", "Файлы получены и распакованы")
                broadcast(msg_type, payload, exclude=conn)
                with peers_lock:
                    if len(peers) >= 2:
                        log(f"Received {msg_type} and forwarded")
                    else:
                        log(f"Received {msg_type}")
        except Exception as e:
            log(f"receive_loop error: {e}")
            break
    with peers_lock:
        if conn in peers:
            peers.remove(conn)
    conn.close()
    log("Peer disconnected")
    with peers_lock:
        peers_count = len(peers)
        update_tray("server", f"Сервер, {peers_count} в сети")
    notify("Потеря соединения", f"Клиент отключился, {peers_count} в сети")

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
        peers_count = len(peers)
    update_tray("server", f"Сервер, {peers_count} в сети")
    notify("Сервер", f"Подключился клиент {addr[0]} ({peers_count} в сети)")
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
    try:
        zc.register_service(info)
    except NonUniqueNameException:
        log("Server already running, restarting...")
        zc.close()
        return
    log(f"Service registered on {ips}")
    notify("Сервер", f"Сервер запущен на {', '.join(ips)}")
    update_tray("server", "Сервер, ожидание клиентов")
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
    update_tray("client", f"Подключение к {ip}...")
    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect((ip, PORT))
        client.sendall(HANDSHAKE)
    except OSError as e:
        log(f"Connection error: {e}")
        return
    with peers_lock:
        peers.append(client)
    update_tray("client", f"Клиент → {ip}")
    notify("Клиент", f"Подключено к {ip}")
    disconnected = threading.Event()

    def receive() -> None:
        receive_loop(client)
        disconnected.set()

    t = threading.Thread(target=receive, daemon=True)
    t.start()
    watch_and_send(client, disconnected)
    t.join()
    log("Disconnected from server")
    notify("Клиент", "Соединение потеряно")

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
    update_tray("searching", "Поиск...")
    zc = Zeroconf()
    ServiceBrowser(zc, "_clipboard._tcp.local.", handlers=[on_service_found])
    event.wait(timeout=5)
    zc.close()
    return host[0]

