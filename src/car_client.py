#!/usr/bin/env python3
import socket
import json

SOCKET_PATH = "/tmp/car_state.sock"

client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
client.connect(SOCKET_PATH)

print("📡 Connected to car server.")
try:
    while True:
        data = client.recv(1024)
        if not data:
            break
        for line in data.splitlines():
            state = json.loads(line)
            print(f"Car position: ({state['x']:.2f}, {state['y']:.2f}), angle={state['angle']:.1f}")
except KeyboardInterrupt:
    pass
finally:
    client.close()
    print("🔌 Client closed.")

