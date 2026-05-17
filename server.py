import socket
import threading
import time
import pyperclip
import netifaces
from zeroconf import ServiceInfo, Zeroconf

PORT = 9999

def get_all_ips():
    ips = []
    for interface in netifaces.interfaces():
        addresses = netifaces.ifaddresses(interface)
        if netifaces.AF_INET in addresses:
            for address in addresses[netifaces.AF_INET]:
                ips.append(address["addr"])
    return ips

def watch_and_send(conn):
    last = pyperclip.paste()
    while True:
        try:
            current = pyperclip.paste()
            if current != last:
                last = current
                conn.send(f"{len(current.encode())}\n".encode())
                conn.send(current.encode())
                print("Sent")
            time.sleep(0.5)
        except Exception as e:
            print(f"watch_and_send error: {e}")
            break

def receive_loop(conn):
    buffer = ""
    while True:
        try:
            data = conn.recv(4096).decode()
            buffer += data
            while "\n" in buffer:
                length, buffer = buffer.split("\n", 1)
                length = int(length)
                while len(buffer.encode()) < length:
                    buffer += conn.recv(4096).decode()
                text = buffer[:length]
                buffer = buffer[length:]
                pyperclip.copy(text)
                print("Received")
        except Exception as e:
            print(f"receive_loop error: {e}")
            break

if __name__ == "__main__":
    ips = get_all_ips()
    print(f"Registering on {ips}")
    info = ServiceInfo(
        "_clipboard._tcp.local.",
        "ClipboardSync._clipboard._tcp.local.",
        addresses=[socket.inet_aton(ip) for ip in ips],
        port=PORT
    )
    zc = Zeroconf()
    zc.register_service(info)
    print("Service registered")
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("0.0.0.0", PORT))
    server.listen(2)
    print(f"Listening on 0.0.0.0:{PORT}")
    conn, addr = server.accept()
    print(f"Connected by: {addr}")
    threading.Thread(target=watch_and_send, args=(conn,), daemon=True).start()
    receive_loop(conn)