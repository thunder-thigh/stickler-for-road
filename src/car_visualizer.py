#!/usr/bin/env python3
import pygame
import socket
import json
import math
import os
import time
import select

SOCKET_PATH = "/tmp/car_state.sock"
WIDTH, HEIGHT = 800, 600
BG_COLOR = (25, 25, 25)
CAR_COLOR = (0, 200, 255)
FPS = 60

# --- Pygame setup ---
pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Visualizer")
font = pygame.font.Font(None, 28)
clock = pygame.time.Clock()

# --- Connect to socket ---
client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
print(f"Connecting to {SOCKET_PATH} ...")
while True:
    try:
        client.connect(SOCKET_PATH)
        print("Connected to car state socket.")
        break
    except FileNotFoundError:
        print("Waiting for socket...")
        time.sleep(1)
    except ConnectionRefusedError:
        print("Socket exists but not ready...")
        time.sleep(1)

client.setblocking(False)

car_state = {"x": WIDTH / 2, "y": HEIGHT / 2, "angle": 0.0}
trail = []

def draw_car(surface, x, y, angle):
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

# --- Main loop ---
running = True
buffer = b""

while running:
    dt = clock.tick(FPS)
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # --- Read from socket ---
    try:
        ready, _, _ = select.select([client], [], [], 0)
        if ready:
            chunk = client.recv(4096)
            if not chunk:
                print("Disconnected from socket.")
                running = False
                break
            buffer += chunk
            while b"\n" in buffer:
                line, buffer = buffer.split(b"\n", 1)
                try:
                    car_state = json.loads(line.decode())
                    trail.append((car_state["x"], car_state["y"]))
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        pass

    # --- Draw ---
    screen.fill(BG_COLOR)
    # draw trail
    if len(trail) > 1:
        pygame.draw.lines(screen, (100, 100, 100), False, trail[-10:], 2)

    draw_car(screen, car_state["x"], car_state["y"], car_state["angle"])
    txt = font.render(f"x={car_state['x']:.1f}  y={car_state['y']:.1f}  angle={car_state['angle']:.1f}°", True, (200, 200, 200))
    screen.blit(txt, (10, 10))
    pygame.display.flip()

client.close()
pygame.quit()
print("Visualizer stopped.")
