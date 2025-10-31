#!/usr/bin/env python3
import socket
import os
import json
import time
import select

SERVER_PATH = "/tmp/car_state_server.sock"

# Remove previous socket if it exists
if os.path.exists(SERVER_PATH):
    os.remove(SERVER_PATH)

# Create the UNIX datagram socket
server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
server.bind(SERVER_PATH)
server.setblocking(False)

clients = set()

# --- DEFINE YOUR BASE STATE HERE --- aka update the data after the bot starts
car_state = {
    "x": 0.0,
    "y": 0.0,
    "angle": 0.0,
    "speed": 0.0,
    "status": "idle",
    "timestamp": time.time()
}
# -----------------------------------

def broadcast_state():
    """Send the current car_state JSON to all registered clients."""
    data = json.dumps(car_state).encode()
    dead = []
    for path in list(clients):
        try:
            server.sendto(data, path)
        except OSError:
            dead.append(path)
    for d in dead:
        clients.discard(d)

print(f"[SERVER] Listening on {SERVER_PATH}")

try:
    while True:
        # Handle incoming messages (REGISTER/UNREGISTER or state updates)
        readable, _, _ = select.select([server], [], [], 0.1)
        for s in readable:
            msg, _ = s.recvfrom(4096)
            msg = msg.decode().strip()

            if msg.startswith("REGISTER:"):
                client_path = msg.split(":", 1)[1]
                clients.add(client_path)
                print(f"[SERVER] Registered client {client_path}")

            elif msg.startswith("UNREGISTER:"):
                client_path = msg.split(":", 1)[1]
                clients.discard(client_path)
                print(f"[SERVER] Unregistered client {client_path}")

            elif msg.startswith("UPDATE:"):
                try:
                    payload = msg.split(":", 1)[1]
                    update = json.loads(payload)
                    car_state.update(update)
                    car_state["timestamp"] = time.time()
                    print(f"[SERVER] Updated state: {update}")
                except Exception as e:
                    print(f"[SERVER] Invalid update: {e}")

        # Broadcast current car state to all clients
        broadcast_state()
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n[SERVER] Shutting down...")
finally:
    server.close()
    if os.path.exists(SERVER_PATH):
        os.remove(SERVER_PATH)
