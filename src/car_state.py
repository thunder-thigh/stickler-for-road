#!/usr/bin/env python3
import pygame
import socket
import json
import math
import os
import time

# ========== Config ==========
SOCKET_PATH = "/tmp/car_state.sock"
WIDTH, HEIGHT = 800, 600
BG_COLOR = (30, 30, 30)
CAR_COLOR = (0, 150, 255)
TARGET_FPS = 60

# ========== Setup Socket ==========
if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)

server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
server.bind(SOCKET_PATH)
server.listen(1)
server.setblocking(False)

conn = None

# ========== Car State ==========
car_state = {
    "x": WIDTH / 2,
    "y": HEIGHT / 2,
    "angle": 0.0,
    "speed": 0.0,
    "max_speed": 5.0,
    "acceleration": 0.2,
    "turn_rate": 4.0
}

# ========== Pygame Init ==========
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Simulator (WASD)")
clock = pygame.time.Clock()
font = pygame.font.Font(None, 28)

def draw_car(surface, x, y, angle):
    """Draw the car as a triangle pointing in heading direction."""
    size = 20
    pts = [
        (math.cos(math.radians(angle)) * size,
         math.sin(math.radians(angle)) * size),
        (math.cos(math.radians(angle + 140)) * size * 0.6,
         math.sin(math.radians(angle + 140)) * size * 0.6),
        (math.cos(math.radians(angle - 140)) * size * 0.6,
         math.sin(math.radians(angle - 140)) * size * 0.6),
    ]
    pts = [(x + px, y + py) for (px, py) in pts]
    pygame.draw.polygon(surface, CAR_COLOR, pts)

# ========== Main Loop ==========
running = True
print("🚗 Car simulator running — use W/A/S/D to move, ESC to quit.")
print(f"Socket path: {SOCKET_PATH}")

while running:
    dt = clock.tick(TARGET_FPS) / 1000.0  # delta time (s)

    # --- Handle socket connection ---
    if conn is None:
        try:
            conn, _ = server.accept()
            conn.setblocking(False)
            print("📡 Client connected.")
        except BlockingIOError:
            pass

    # --- Event handling ---
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    keys = pygame.key.get_pressed()
    if keys[pygame.K_ESCAPE]:
        running = False

    # --- Car movement logic ---
    if keys[pygame.K_w]:
        car_state["speed"] = min(car_state["speed"] + car_state["acceleration"], car_state["max_speed"])
    elif keys[pygame.K_s]:
        car_state["speed"] = max(car_state["speed"] - car_state["acceleration"], -car_state["max_speed"]/2)
    else:
        # friction
        car_state["speed"] *= 0.95

    if keys[pygame.K_a]:
        car_state["angle"] = (car_state["angle"] - car_state["turn_rate"]) % 360
    if keys[pygame.K_d]:
        car_state["angle"] = (car_state["angle"] + car_state["turn_rate"]) % 360

    car_state["x"] += math.cos(math.radians(car_state["angle"])) * car_state["speed"]
    car_state["y"] += math.sin(math.radians(car_state["angle"])) * car_state["speed"]

    # Keep inside bounds
    car_state["x"] = max(0, min(WIDTH, car_state["x"]))
    car_state["y"] = max(0, min(HEIGHT, car_state["y"]))

    # --- Send JSON state to client ---
    if conn:
        try:
            data = json.dumps(car_state).encode() + b"\n"
            conn.sendall(data)
        except (BrokenPipeError, ConnectionResetError):
            print("⚠️ Client disconnected.")
            conn.close()
            conn = None

    # --- Draw ---
    screen.fill(BG_COLOR)
    draw_car(screen, car_state["x"], car_state["y"], car_state["angle"])
    txt = font.render(f"x={car_state['x']:.1f}  y={car_state['y']:.1f}  angle={car_state['angle']:.1f}°", True, (200, 200, 200))
    screen.blit(txt, (10, 10))
    pygame.display.flip()

pygame.quit()
if conn:
    conn.close()
server.close()
if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)
print("👋 Simulation ended.")

