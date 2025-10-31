#!/usr/bin/env python3
import os, time, math, json, socket, random
import pygame

SOCKET_PATH = "/tmp/pathfinder.sock"

if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)

sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
sock.bind(SOCKET_PATH)
sock.setblocking(False)

WIDTH, HEIGHT = 700, 700
screen = pygame.display.set_mode((800, 800))
pygame.display.set_caption("Pathfinder")
clock = pygame.time.Clock()

def find_path(start, goal, n_points=20):
    """Simple dummy curved path generator (placeholder for A* or RRT)."""
    path = [start]
    for i in range(1, n_points):
        t = i / n_points
        x = start[0] + t * (goal[0] - start[0]) + math.sin(t * 3.14) * 10
        y = start[1] + t * (goal[1] - start[1]) + math.cos(t * 3.14) * 10
        path.append((x, y))
    path.append(goal)
    return path

def draw_path(path):
    for i in range(len(path)-1):
        pygame.draw.line(screen, (0, 255, 0), path[i], path[i+1], 3)
    for p in path:
        pygame.draw.circle(screen, (255, 0, 0), (int(p[0]), int(p[1])), 4)

try:
    while True:
        # Simulated start and goal
        start = (random.uniform(50, 200), random.uniform(50, 200))
        goal = (random.uniform(500, 650), random.uniform(500, 650))
        path = find_path(start, goal)

        # Create message
        msg = {
            "timestamp": time.time(),
            "start": start,
            "goal": goal,
            "path": path
        }

        # Send JSON-encoded message
        sock.sendto(json.dumps(msg).encode(), SOCKET_PATH)

        # Draw visualization
        screen.fill((30, 30, 30))
        draw_path(path)
        pygame.display.flip()
        clock.tick(10)

        time.sleep(5)  # recompute every 5 seconds

except KeyboardInterrupt:
    print("\n[PATHFINDER] Stopped.")
finally:
    pygame.quit()
    sock.close()
    if os.path.exists(SOCKET_PATH):
        os.remove(SOCKET_PATH)
