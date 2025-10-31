#!/usr/bin/env python3
import os, math, json, socket, pygame

SOCKET_PATH = "/tmp/pathfinder.sock"

if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)

sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
sock.bind(SOCKET_PATH)
sock.setblocking(False)

WIDTH, HEIGHT = 700, 700
STEP = 15
OBSTACLES = [
    pygame.Rect(200, 200, 100, 200),
    pygame.Rect(400, 100, 150, 150),
    pygame.Rect(500, 400, 180, 150),
]

pygame.init()
screen = pygame.display.set_mode((800, 800))
pygame.display.set_caption("Interactive Pathfinder")
clock = pygame.time.Clock()

def heuristic(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])

def neighbors(node):
    dirs = [(STEP, 0), (-STEP, 0), (0, STEP), (0, -STEP),
            (STEP, STEP), (-STEP, -STEP), (STEP, -STEP), (-STEP, STEP)]
    result = []
    for dx, dy in dirs:
        x2, y2 = node[0] + dx, node[1] + dy
        if 0 <= x2 <= WIDTH and 0 <= y2 <= HEIGHT:
            if not any(o.collidepoint(x2, y2) for o in OBSTACLES):
                result.append((x2, y2))
    return result

def a_star(start, goal):
    open_set, came_from, g, f = {start}, {}, {start: 0}, {start: heuristic(start, goal)}
    while open_set:
        current = min(open_set, key=lambda x: f.get(x, float("inf")))
        if heuristic(current, goal) < STEP:
            path = [goal]
            while current in came_from:
                path.append(current)
                current = came_from[current]
            path.append(start)
            return path[::-1]
        open_set.remove(current)
        for n in neighbors(current):
            tentative_g = g[current] + heuristic(current, n)
            if tentative_g < g.get(n, float("inf")):
                came_from[n] = current
                g[n] = tentative_g
                f[n] = tentative_g + heuristic(n, goal)
                open_set.add(n)
    return []

def clear_line(a, b):
    ax, ay = a; bx, by = b
    for o in OBSTACLES:
        for t in [i / 10 for i in range(11)]:
            x = ax + (bx - ax) * t; y = ay + (by - ay) * t
            if o.collidepoint(x, y): return False
    return True

def smooth_path(path):
    if len(path) < 3: return path
    smoothed = [path[0]]
    i = 0
    while i < len(path)-1:
        j = len(path)-1
        while j > i+1:
            if clear_line(path[i], path[j]):
                smoothed.append(path[j]); i = j; break
            j -= 1
        else:
            smoothed.append(path[i+1]); i += 1
    blended = []
    for k in range(len(smoothed)-1):
        p1, p2 = smoothed[k], smoothed[k+1]
        for t in [i/10 for i in range(11)]:
            x = (1-t)*p1[0] + t*p2[0]
            y = (1-t)*p1[1] + t*p2[1]
            blended.append((x, y))
    return blended

def draw_env(path=None, smooth=None, start=None, goal=None):
    screen.fill((25, 25, 25))
    for o in OBSTACLES:
        pygame.draw.rect(screen, (80, 20, 20), o)
    if path: pygame.draw.lines(screen, (0, 100, 255), False, path, 2)
    if smooth: pygame.draw.lines(screen, (0, 255, 0), False, smooth, 3)
    if start: pygame.draw.circle(screen, (255, 255, 0), start, 6)
    if goal: pygame.draw.circle(screen, (255, 0, 0), goal, 6)
    pygame.display.flip()

start, goal, path, smooth = None, None, None, None

print("[PATHFINDER] Click to set start and goal points.")

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            pos = pygame.mouse.get_pos()
            if not start:
                start = pos
                print(f"[PATHFINDER] Start set: {start}")
            elif not goal:
                goal = pos
                print(f"[PATHFINDER] Goal set: {goal}")
                path = a_star(start, goal)
                smooth = smooth_path(path)

                msg = {
                    "timestamp": time.time(),
                    "start": start,
                    "goal": goal,
                    "path": smooth
                }
                sock.sendto(json.dumps(msg).encode(), SOCKET_PATH)
                print(f"[PATHFINDER] Path of {len(smooth)} waypoints sent.")
    draw_env(path, smooth, start, goal)
    clock.tick(30)

pygame.quit()
sock.close()
if os.path.exists(SOCKET_PATH):
    os.remove(SOCKET_PATH)
