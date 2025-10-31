#!/usr/bin/env python3
import socket
import os
import json
import time
import sys
import select

SERVER_PATH = "/tmp/car_state_server.sock"
CLIENT_PATH = f"/tmp/car_client_{os.getpid()}.sock"

if os.path.exists(CLIENT_PATH):
    os.remove(CLIENT_PATH)

client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
client.bind(CLIENT_PATH)

# Register with server
client.sendto(f"REGISTER:{CLIENT_PATH}".encode(), SERVER_PATH)

print(f"[CLIENT] Connected as {CLIENT_PATH}")

try:
    while True:
        readable, _, _ = select.select([client], [], [], 1)
        if readable:
            data, _ = client.recvfrom(4096)
            state = json.loads(data.decode())
            print(f"[CLIENT] State: {state}")
            time.sleep(0.1)
except KeyboardInterrupt:
    print("\n[CLIENT] Exiting...")
finally:
    client.sendto(f"UNREGISTER:{CLIENT_PATH}".encode(), SERVER_PATH)
    client.close()
    os.remove(CLIENT_PATH)
