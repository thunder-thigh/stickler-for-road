#!/usr/bin/env python3
# car_control_dummy.py
import socket, time, json, math, os

SOCKET_PATH = "/tmp/car_state.sock"

if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)

server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(SOCKET_PATH)
server.listen(1)
print("Waiting for visualizer...")
conn, _ = server.accept()
print("Visualizer connected.")

angle = 0
x, y = 400, 300
t = 0
while True:
    x = 400 + math.cos(t / 10) * 150
    y = 300 + math.sin(t / 10) * 150
    angle = (angle + 2) % 360
    state = {"x": x, "y": y, "angle": angle}
    conn.sendall(json.dumps(state).encode() + b"\n")
    t += 1
    time.sleep(0.05)

