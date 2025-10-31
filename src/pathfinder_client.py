#!/usr/bin/env python3
import socket, os, json, sys

SERVER_SOCK = "/tmp/pathfinder_server.sock"
CLIENT_SOCK = f"/tmp/pathfinder_client_{os.getpid()}.sock"

if os.path.exists(CLIENT_SOCK):
    os.remove(CLIENT_SOCK)

client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
client.bind(CLIENT_SOCK)
client.sendto(f"REGISTER:{CLIENT_SOCK}".encode(), SERVER_SOCK)

print(f"[CLIENT {os.getpid()}] Listening for path data...")

try:
    while True:
        data, _ = client.recvfrom(65536)
        msg = json.loads(data.decode())
        print("\n=== New Path Data ===")
        print(f"Timestamp : {msg['timestamp']:.2f}")
        print(f"Start     : {msg['start']}")
        print(f"Goal      : {msg['goal']}")
        print(f"Waypoints : {len(msg['path'])}")
        for p in msg['path'][:5]:
            print(f"   {p}")
        print("=====================")
except KeyboardInterrupt:
    print("\n[CLIENT] Exiting...")
finally:
    client.sendto(f"UNREGISTER:{CLIENT_SOCK}".encode(), SERVER_SOCK)
    client.close()
    if os.path.exists(CLIENT_SOCK):
        os.remove(CLIENT_SOCK)
