#!/usr/bin/env python3
import socket
import os
import json
import select
import pygame
import sys
import math

SERVER_PATH = "/tmp/car_state_server.sock"
CLIENT_PATH = f"/tmp/car_client_{os.getpid()}.sock"

# Cleanup old client socket
if os.path.exists(CLIENT_PATH):
    os.remove(CLIENT_PATH)

# Create client datagram socket
client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
client.bind(CLIENT_PATH)

# Register with the server
client.sendto(f"REGISTER:{CLIENT_PATH}".encode(), SERVER_PATH)
print(f"[VISUALIZER] Registered as {CLIENT_PATH}")

# --- Pygame setup ---
pygame.init()
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Car Visualizer")

clock = pygame.time.Clock()

# Car render settings
CAR_SIZE = (40, 20)
CAR_COLOR = (255, 100, 50)
BG_COLOR = (30, 30, 30)
TEXT_COLOR = (200, 200, 200)
FONT = pygame.font.SysFont("consolas", 18)

# Coordinate scale (meters → pixels)
SCALE = 5.0

def draw_car(state):
    """Draw car position and orientation from state."""
    x = state.get("x", 0.0) * SCALE + WIDTH / 2
    y = HEIGHT / 2 - state.get("y", 0.0) * SCALE
    angle_deg = state.get("angle", 0.0)
    angle_rad = -math.radians(angle_deg)

    # Create car rect and rotate it
    car_rect = pygame.Rect(0, 0, *CAR_SIZE)
    car_rect.center = (x, y)
    car_surface = pygame.Surface(CAR_SIZE, pygame.SRCALPHA)
    car_surface.fill(CAR_COLOR)
    rotated = pygame.transform.rotate(car_surface, math.degrees(angle_rad))
    rotated_rect = rotated.get_rect(center=car_rect.center)
    screen.blit(rotated, rotated_rect)

    # Draw heading line
    line_len = 30
    end_x = x + line_len * math.cos(angle_rad)
    end_y = y + line_len * math.sin(angle_rad)
    pygame.draw.line(screen, (0, 255, 0), (x, y), (end_x, end_y), 2)

    # Draw info text
    info = f"x={state.get('x',0):.2f}  y={state.get('y',0):.2f}  θ={angle_deg:.1f}°  status={state.get('status','idle')}"
    text = FONT.render(info, True, TEXT_COLOR)
    screen.blit(text, (10, 10))

car_state = {}

# --- Main loop ---
try:
    while True:
        # Handle quit events
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                raise KeyboardInterrupt

        # Read from socket (non-blocking)
        readable, _, _ = select.select([client], [], [], 0.02)
        if readable:
            data, _ = client.recvfrom(4096)
            try:
                car_state = json.loads(data.decode())
            except json.JSONDecodeError:
                continue

        # Draw the scene
        screen.fill(BG_COLOR)
        if car_state:
            draw_car(car_state)
        pygame.display.flip()
        clock.tick(60)

except KeyboardInterrupt:
    print("\n[VISUALIZER] Shutting down...")
finally:
    # Unregister and cleanup
    client.sendto(f"UNREGISTER:{CLIENT_PATH}".encode(), SERVER_PATH)
    client.close()
    if os.path.exists(CLIENT_PATH):
        os.remove(CLIENT_PATH)
    pygame.quit()
    sys.exit(0)
