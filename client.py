import socket
import sys
import threading
import pyperclip
import time

import zeroconf
from zeroconf import ServiceBrowser, Zeroconf

PORT = 9999
host = [None]
found_event = threading.Event()

def try_connect(ip):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1)
        s.connect((ip, PORT))
        s.close()
        return True
    except:
        return False

def on_service_found(zeroconf, service_type, name, **kwargs):
    info = zeroconf.get_service_info(service_type, name)
    if info:
        for address in info.addresses:
            ip = socket.inet_ntoa(address)
            if ip.startswith("10.211"):
                print(ip)
                if try_connect(ip):
                    host[0] = ip
                    found_event.set()
                    return

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
        except:
            break

def receive_loop(conn):
    print("Receiving...")
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
            print(f"Receive error: {e}")  # ← покажет что сломалось
            break

if __name__ == "__main__":
    print("Searching server...")
    zc = Zeroconf()
    ServiceBrowser(zc, "_clipboard._tcp.local.", handlers=[on_service_found])
    found_event.wait(timeout=5)
    zc.close()
    if not host[0]:
        print("Server not found")
        sys.exit(1)
    print(f"Server found at {host[0]}")
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((host[0], PORT))
    threading.Thread(target=receive_loop, args=(client,), daemon=True).start()
    watch_and_send(client)