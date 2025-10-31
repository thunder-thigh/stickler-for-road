#!/usr/bin/env python3
import os, math, json, socket, pygame, time

SERVER_SOCK = "/tmp/pathfinder_server.sock"
if os.path.exists(SERVER_SOCK):
    os.remove(SERVER_SOCK)

server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
server.bind(SERVER_SOCK)
server.setblocking(False)

WIDTH, HEIGHT = 700, 700
STEP = 15
OBSTACLES = [
    pygame.Rect(200, 200, 100, 200),
    pygame.Rect(400, 100, 150, 150),
    pygame.Rect(500, 400, 180, 150),
]
BORDER_THICKNESS = 10
OBSTACLES += [
    pygame.Rect(0, 0, WIDTH, BORDER_THICKNESS),                     # Top
    pygame.Rect(0, HEIGHT - BORDER_THICKNESS, WIDTH, BORDER_THICKNESS),  # Bottom
    pygame.Rect(0, 0, BORDER_THICKNESS, HEIGHT),                    # Left
    pygame.Rect(WIDTH - BORDER_THICKNESS, 0, BORDER_THICKNESS, HEIGHT),  # Right
]

pygame.init()
screen = pygame.display.set_mode((700, 700))
pygame.display.set_caption("Pathfinder Server")
clock = pygame.time.Clock()

clients = set()

def broadcast(msg: dict):
    """Send JSON state to all known clients."""
    data = json.dumps(msg).encode()
    dead = []
    for path in list(clients):
        try:
            server.sendto(data, path)
        except OSError:
            dead.append(path)
    for d in dead:
        clients.discard(d)

def heuristic(a, b): return math.hypot(a[0]-b[0], a[1]-b[1])

def neighbors(node):
    dirs = [(STEP,0),(-STEP,0),(0,STEP),(0,-STEP),
            (STEP,STEP),(-STEP,-STEP),(STEP,-STEP),(-STEP,STEP)]
    res=[]
    for dx,dy in dirs:
        x2,y2=node[0]+dx,node[1]+dy
        if 0<=x2<=WIDTH and 0<=y2<=HEIGHT:
            if not any(o.collidepoint(x2,y2) for o in OBSTACLES):
                res.append((x2,y2))
    return res

def a_star(start,goal):
    open_set,came_from,g,f={start},{},{start:0},{start:heuristic(start,goal)}
    while open_set:
        cur=min(open_set,key=lambda x:f.get(x,float("inf")))
        if heuristic(cur,goal)<STEP:
            path=[goal]
            while cur in came_from:
                path.append(cur)
                cur=came_from[cur]
            path.append(start)
            return path[::-1]
        open_set.remove(cur)
        for n in neighbors(cur):
            ng=g[cur]+heuristic(cur,n)
            if ng<g.get(n,float("inf")):
                came_from[n]=cur
                g[n]=ng
                f[n]=ng+heuristic(n,goal)
                open_set.add(n)
    return []

def clear_line(a,b):
    ax,ay=a; bx,by=b
    for o in OBSTACLES:
        for t in [i/10 for i in range(11)]:
            x=ax+(bx-ax)*t; y=ay+(by-ay)*t
            if o.collidepoint(x,y): return False
    return True

def smooth_path(path):
    if len(path)<3: return path
    sm=[path[0]]; i=0
    while i<len(path)-1:
        j=len(path)-1
        while j>i+1:
            if clear_line(path[i],path[j]):
                sm.append(path[j]); i=j; break
            j-=1
        else:
            sm.append(path[i+1]); i+=1
    blended=[]
    for k in range(len(sm)-1):
        p1,p2=sm[k],sm[k+1]
        for t in [i/10 for i in range(11)]:
            x=(1-t)*p1[0]+t*p2[0]; y=(1-t)*p1[1]+t*p2[1]
            blended.append((x,y))
    return blended

def draw_env(path=None,smooth=None,start=None,goal=None):
    screen.fill((25,25,25))
    for o in OBSTACLES: pygame.draw.rect(screen,(80,20,20),o)
    if path: pygame.draw.lines(screen,(0,100,255),False,path,2)
    if smooth: pygame.draw.lines(screen,(0,255,0),False,smooth,3)
    if start: pygame.draw.circle(screen,(255,255,0),start,6)
    if goal: pygame.draw.circle(screen,(255,0,0),goal,6)
    pygame.display.flip()

start = goal = path = smooth = None
print("[PATHFINDER] Click once for start, once for goal. Click again to reset.")

import select
running=True
while running:
    # Handle client registration messages
    readable, _, _ = select.select([server], [], [], 0)
    for s in readable:
        msg, addr = s.recvfrom(4096)
        msg = msg.decode().strip()
        if msg.startswith("REGISTER:"):
            clients.add(msg.split(":",1)[1])
            print(f"[PATHFINDER] Registered client {msg.split(':',1)[1]}")
        elif msg.startswith("UNREGISTER:"):
            path = msg.split(":",1)[1]
            clients.discard(path)
            print(f"[PATHFINDER] Unregistered {path}")

    for e in pygame.event.get():
        if e.type == pygame.QUIT: running=False
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            running=False
        elif e.type == pygame.MOUSEBUTTONDOWN:
            pos=pygame.mouse.get_pos()
            if not start:
                start=pos
                print(f"[PATHFINDER] Start set: {start}")
            elif not goal:
                goal=pos
                print(f"[PATHFINDER] Goal set: {goal}")
                path=a_star(start,goal)
                smooth=smooth_path(path)
                msg={"timestamp":time.time(),"start":start,"goal":goal,"path":smooth}
                broadcast(msg)
                print(f"[PATHFINDER] Sent path ({len(smooth)} pts) to {len(clients)} client(s).")
            else:
                start=goal=path=smooth=None
                print("[PATHFINDER] Reset. Click new start/goal.")

    draw_env(path,smooth,start,goal)
    clock.tick(30)

pygame.quit()
server.close()
os.remove(SERVER_SOCK)
