#!/usr/bin/env python3
"""
pathfinder.py

- Loads map.json
- Connects as a client to car-state broadcaster (datagram)
- Builds a sampling-based PRM, runs A* to produce a waypoint list
- Recomputes path every PATH_UPDATE_INTERVAL seconds using current position
- Broadcasts path JSON to registered clients via a datagram server (/tmp/path_planner.sock)
- Optional pygame visualization (SET VISUALIZE=True)
"""

import os
import socket
import json
import time
import math
import random
import select
import sys

# ===== CONFIG =====
MAP_FILE = "map.json"
SENSOR_SERVER = "/tmp/car_state_server.sock"    # where car state is broadcast
SENSOR_CLIENT = f"/tmp/pathfinder_client_{os.getpid()}.sock"
PATH_SERVER = "/tmp/path_planner.sock"          # where pathfinder broadcasts paths
PATH_UPDATE_INTERVAL = 5.0                      # seconds between replans
PRM_SAMPLES = 600                               # number of free samples to try
PRM_K = 12                                      # neighbors to attempt to connect
MAX_EDGE_LEN = 200.0                            # max connection length (m)
VISUALIZE = True                                # set False to disable pygame window
SCREEN_W, SCREEN_H = 800, 800                   # visualization window size
SCALE = SCREEN_W / 700.0                        # convert map coords -> pixels

# ===== Utilities: geometry =====
def point_in_poly(pt, poly):
    """Ray casting algorithm for point-in-polygon. pt=(x,y), poly=list of (x,y)."""
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i+1) % n]
        # check if edge intersects the ray to the right of pt
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1):
            inside = not inside
    return inside

def seg_intersect(a, b, c, d):
    """Return True if segments ab and cd intersect (excluding touching)."""
    # helper
    def orient(p, q, r):
        return (q[0]-p[0])*(r[1]-p[1]) - (q[1]-p[1])*(r[0]-p[0])
    def on_seg(p,q,r):
        return min(p[0],r[0]) <= q[0] <= max(p[0],r[0]) and min(p[1],r[1]) <= q[1] <= max(p[1],r[1])
    o1 = orient(a,b,c)
    o2 = orient(a,b,d)
    o3 = orient(c,d,a)
    o4 = orient(c,d,b)
    if o1*o2 < 0 and o3*o4 < 0:
        return True
    # colinear special cases
    if abs(o1) < 1e-9 and on_seg(a,c,b): return True
    if abs(o2) < 1e-9 and on_seg(a,d,b): return True
    if abs(o3) < 1e-9 and on_seg(c,a,d): return True
    if abs(o4) < 1e-9 and on_seg(c,b,d): return True
    return False

def seg_intersects_poly(p1, p2, poly):
    n = len(poly)
    for i in range(n):
        q1 = tuple(poly[i])
        q2 = tuple(poly[(i+1)%n])
        if seg_intersect(p1, p2, q1, q2):
            return True
    return False

def collides(point, obstacles):
    for poly in obstacles:
        if point_in_poly(point, poly):
            return True
    return False

def edge_blocked(a, b, obstacles):
    # if either endpoint inside obstacle -> blocked
    if collides(a, obstacles) or collides(b, obstacles):
        return True
    for poly in obstacles:
        if seg_intersects_poly(a, b, poly):
            return True
    return False

# ===== Map loading =====
def load_map(path):
    with open(path) as f:
        m = json.load(f)
    width = m.get("width", 700)
    height = m.get("height", 700)
    obstacles = [ [tuple(p) for p in poly] for poly in m.get("obstacles", []) ]
    roads = [ [tuple(p) for p in poly] for poly in m.get("roads", []) ]
    return width, height, obstacles, roads

# ===== PRM builder =====
def sample_free(width, height, obstacles, n):
    pts = []
    attempts = 0
    while len(pts) < n and attempts < n * 20:
        x = random.uniform(0, width)
        y = random.uniform(0, height)
        if not collides((x,y), obstacles):
            pts.append((x,y))
        attempts += 1
    return pts

def dist(a,b):
    return math.hypot(a[0]-b[0], a[1]-b[1])

def build_prm(samples, k, obstacles):
    nodes = list(samples)
    edges = {i: set() for i in range(len(nodes))}
    for i,a in enumerate(nodes):
        # find neighbors by linear search (practical for our sizes)
        dists = [(j, dist(a, nodes[j])) for j in range(len(nodes)) if j != i]
        dists.sort(key=lambda x: x[1])
        for j, d in dists[:k]:
            if d > MAX_EDGE_LEN: 
                continue
            if not edge_blocked(a, nodes[j], obstacles):
                edges[i].add(j)
                edges[j].add(i)
    return nodes, edges

# ===== A* search on roadmap =====
import heapq
def astar_on_graph(nodes, edges, start_pt, goal_pt):
    # add start and goal as temporary nodes, connect to roadmap
    nodes_ext = nodes[:]  # list copy
    edges_ext = {i:set(nei) for i,nei in edges.items()}
    s_idx = len(nodes_ext); nodes_ext.append(start_pt); edges_ext[s_idx]=set()
    g_idx = len(nodes_ext); nodes_ext.append(goal_pt); edges_ext[g_idx]=set()
    # connect start and goal to nearest k nodes
    for idx,pt in enumerate(nodes):
        d_s = dist(start_pt, pt)
        d_g = dist(goal_pt, pt)
        if d_s < MAX_EDGE_LEN and not edge_blocked(start_pt, pt, obstacles_global):
            edges_ext[s_idx].add(idx); edges_ext[idx].add(s_idx)
        if d_g < MAX_EDGE_LEN and not edge_blocked(goal_pt, pt, obstacles_global):
            edges_ext[g_idx].add(idx); edges_ext[idx].add(g_idx)
    # direct connect start-goal?
    if not edge_blocked(start_pt, goal_pt, obstacles_global):
        edges_ext[s_idx].add(g_idx); edges_ext[g_idx].add(s_idx)

    # A*
    openp = [(0 + dist(start_pt, goal_pt), 0, s_idx, None)]  # (f, g, node, parent)
    came = {}
    gscore = {s_idx:0}
    while openp:
        f,g,u,parent = heapq.heappop(openp)
        if u in came: continue
        came[u] = parent
        if u == g_idx:
            # reconstruct
            path = []
            cur = u
            while cur is not None:
                path.append(nodes_ext[cur])
                cur = came[cur]
            return list(reversed(path))
        for v in edges_ext.get(u, []):
            tentative = g + dist(nodes_ext[u], nodes_ext[v])
            if tentative < gscore.get(v, 1e18):
                gscore[v] = tentative
                heapq.heappush(openp, (tentative + dist(nodes_ext[v], goal_pt), tentative, v, u))
    return None

# ===== Socket: register to sensor server and receive position updates =====
def setup_sensor_client():
    # make client socket, bind unique path, register to SENSOR_SERVER
    if os.path.exists(SENSOR_CLIENT):
        os.remove(SENSOR_CLIENT)
    c = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    c.bind(SENSOR_CLIENT)
    try:
        c.sendto(f"REGISTER:{SENSOR_CLIENT}".encode(), SENSOR_SERVER)
    except Exception:
        pass
    c.setblocking(False)
    return c

# ===== Path broadcaster server (datagram with registrations) =====
def setup_path_server():
    if os.path.exists(PATH_SERVER):
        os.remove(PATH_SERVER)
    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    s.bind(PATH_SERVER)
    s.setblocking(False)
    return s

def handle_registration(msg, clients):
    if msg.startswith("REGISTER:"):
        clients.add(msg.split(":",1)[1])
    elif msg.startswith("UNREGISTER:"):
        clients.discard(msg.split(":",1)[1])

def broadcast_path(sock, clients, path):
    data = json.dumps({"path": path, "timestamp": time.time()}).encode()
    dead = []
    for p in list(clients):
        try:
            sock.sendto(data, p)
        except OSError:
            dead.append(p)
    for d in dead:
        clients.discard(d)

# ===== Main =====
if __name__ == "__main__":
    random.seed(0)
    width, height, obstacles_global, roads = load_map(MAP_FILE)

    # build PRM once (can be rebuilt if map changes)
    samples = sample_free(width, height, obstacles_global, PRM_SAMPLES)
    nodes, edges = build_prm(samples, PRM_K, obstacles_global)
    print(f"[PRM] Nodes={len(nodes)} Edges approx={sum(len(v) for v in edges.values())//2}")

    # sockets
    sens_sock = setup_sensor_client()
    path_sock = setup_path_server()
    path_clients = set()

    # Visualization (optional)
    if VISUALIZE:
        try:
            import pygame
            pygame.init()
            screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
            pygame.display.set_caption("Pathfinder")
            font = pygame.font.SysFont("arial", 14)
        except Exception as e:
            print("pygame not available, disabling visualization:", e)
            VISUALIZE = False

    current_pos = None
    goal = None
    last_plan_time = 0
    current_path = []

    print("[PATHFINDER] Running. Send updates from sensor server; set goal via CLI or by sending UPDATE: JSON to sensor server.")

    # Accept a command-line goal if provided as: python3 pathfinder.py 100 200
    if len(sys.argv) >= 3:
        try:
            gx = float(sys.argv[1]); gy = float(sys.argv[2])
            goal = (gx, gy)
            print(f"[PATHFINDER] Goal set from CLI: {goal}")
        except:
            pass

    try:
        while True:
            # --- read sensor server messages (position updates) ---
            try:
                r,_,_ = select.select([sens_sock, path_sock], [], [], 0.05)
            except ValueError:
                r = []
            for s in r:
                if s is sens_sock:
                    try:
                        data, _ = sens_sock.recvfrom(8192)
                        msg = data.decode()
                        # sensor messages can be full JSON or UPDATE:... ; we'll try JSON first
                        try:
                            st = json.loads(msg)
                            # expect {"x":..., "y":..., "angle":...}
                            if "x" in st and "y" in st:
                                current_pos = (float(st["x"]), float(st["y"]))
                        except Exception:
                            # maybe it's REGISTER/UNREGISTER/UPDATE: for server
                            if msg.startswith("UPDATE:"):
                                try:
                                    payload = json.loads(msg.split(":",1)[1])
                                    if "goal" in payload:
                                        goal = tuple(payload["goal"])
                                        print("[PATHFINDER] Goal updated via UPDATE:", goal)
                                except:
                                    pass
                    except BlockingIOError:
                        pass
                elif s is path_sock:
                    try:
                        data, _ = path_sock.recvfrom(4096)
                        try:
                            handle_registration(data.decode().strip(), path_clients)
                        except:
                            pass
                    except BlockingIOError:
                        pass

            # periodic replan
            now = time.time()
            if goal is not None and (now - last_plan_time) > PATH_UPDATE_INTERVAL:
                last_plan_time = now
                start_pt = current_pos if current_pos is not None else (width/2.0, height/2.0)
                # quick check: if direct path is free, use it
                if not edge_blocked(start_pt, goal, obstacles_global):
                    current_path = [start_pt, goal]
                    print("[PATHFINDER] Direct path OK")
                else:
                    # run A* on PRM + start/goal
                    path = astar_on_graph(nodes, edges, start_pt, goal)
                    if path:
                        current_path = path
                        print(f"[PATHFINDER] Path found, len={len(path)}")
                    else:
                        current_path = []
                        print("[PATHFINDER] No path found")

                # broadcast to registered clients
                if path_clients:
                    broadcast_path(path_sock, path_clients, current_path)

            # draw visualization
            if VISUALIZE:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        raise KeyboardInterrupt
                    # allow setting goal by mouse click
                    if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                        mx,my = ev.pos
                        gx = (mx)/SCALE
                        gy = (SCREEN_H - my)/SCALE
                        goal = (gx, gy)
                        print("[PATHFINDER] Goal set by click:", goal)

                screen.fill((30,30,30))
                # draw obstacles
                for poly in obstacles_global:
                    pts = [ (int(p[0]*SCALE), SCREEN_H - int(p[1]*SCALE)) for p in poly ]
                    pygame.draw.polygon(screen, (180,60,60), pts)
                # draw PRM nodes (light)
                for p in nodes:
                    pygame.draw.circle(screen, (100,100,100), (int(p[0]*SCALE), SCREEN_H - int(p[1]*SCALE)), 2)
                # draw PRM edges
                for i,neis in edges.items():
                    a = nodes[i]
                    for j in neis:
                        b = nodes[j]
                        pygame.draw.aaline(screen, (60,60,60), (a[0]*SCALE, SCREEN_H - a[1]*SCALE), (b[0]*SCALE, SCREEN_H - b[1]*SCALE))
                # draw path
                if current_path:
                    pts = [ (int(p[0]*SCALE), SCREEN_H - int(p[1]*SCALE)) for p in current_path ]
                    pygame.draw.lines(screen, (50,200,50), False, pts, 4)
                # draw car pos and goal
                if current_pos:
                    px,py = int(current_pos[0]*SCALE), SCREEN_H - int(current_pos[1]*SCALE)
                    pygame.draw.circle(screen, (50,150,255), (px,py), 6)
                if goal:
                    gx,gy = int(goal[0]*SCALE), SCREEN_H - int(goal[1]*SCALE)
                    pygame.draw.circle(screen, (255,200,50), (gx,gy), 6)
                # info
                if 'font' in globals():
                    txt = font.render(f"pos={current_pos} goal={goal} pathlen={len(current_path)}", True, (220,220,220))
                    screen.blit(txt, (6,6))
                pygame.display.flip()

    except KeyboardInterrupt:
        print("\n[PATHFINDER] Exiting...")
    finally:
        try:
            sens_sock.sendto(f"UNREGISTER:{SENSOR_CLIENT}".encode(), SENSOR_SERVER)
        except Exception:
            pass
        try:
            os.remove(SENSOR_CLIENT)
        except Exception:
            pass
        try:
            path_sock.close()
            if os.path.exists(PATH_SERVER):
                os.remove(PATH_SERVER)
        except Exception:
            pass
        if VISUALIZE:
            try:
                import pygame
                pygame.quit()
            except:
                pass
