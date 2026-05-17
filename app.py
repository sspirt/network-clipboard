from network import find_server, run_as_client, run_as_server

if __name__ == "__main__":
    server_ip = find_server()
    if server_ip:
        run_as_client(server_ip)
    else:
        run_as_server()