import math
import heapq

flr = math.floor

MAXNODES = 1200
MAXDROP  = 3
MAXRANGE = 24

STEPCOST = 1.0
JUMPCOST = 1.4
DROPCOST = 0.35   # p block fallen
DIAGCOST = 1.414

DIRS  = ((1, 0), (-1, 0), (0, 1), (0, -1))
DIAGS = ((1, 1), (1, -1), (-1, 1), (-1, -1))







def clearcol(ck, x, y, z, hb):
    for i in range(hb):
        if ck.issolid(x, y + i, z): return False
    return True



def standable(ck, x, y, z, hb):
    return ck.issolid(x, y - 1, z) and clearcol(ck, x, y, z, hb)






def steps(ck, n, hb, out=[]):
    x, y, z = n
    out = []

    for dx, dz in DIRS:
        nx, nz = x + dx, z + dz

        # straight on
        if standable(ck, nx, y, nz, hb):
            out.append(((nx, y, nz), STEPCOST))
            continue

        # up one, needs headroom
        if clearcol(ck, x, y + hb, z, 1) and standable(ck, nx, y + 1, nz, hb):
            out.append(((nx, y + 1, nz), JUMPCOST))
            continue

        # off a ledge
        # only if survives
        for d in range(1, MAXDROP + 1):
            ny = y - d
            if standable(ck, nx, ny, nz, hb):
                if clearcol(ck, nx, ny, nz, y - ny + hb):
                    out.append(((nx, ny, nz), STEPCOST + d * DROPCOST))
                break
            if ck.issolid(nx, ny, nz): break







    # flat diagonals
    
    for dx, dz in DIAGS:
        nx, nz = x + dx, z + dz
        if not standable(ck, nx, y, nz, hb):   continue
        if not clearcol(ck, nx, y, z, hb):     continue
        if not clearcol(ck, x, y, nz, hb):     continue
        out.append(((nx, y, nz), DIAGCOST))

    return out









def hcost(a, b):
    dx = abs(a[0] - b[0])
    dz = abs(a[2] - b[2])
    d  = (dx + dz) + (DIAGCOST - 2.0) * min(dx, dz)
    return d * 1.001 + abs(a[1] - b[1]) * 0.5








# A* over standable blocks
# ret [(x, y, z) centres] or []
def find(ck, start, goal, hb, maxnodes=MAXNODES):
    sx, sy, sz = start
    gx, gy, gz = goal


    if abs(gx - sx) > MAXRANGE or abs(gz - sz) > MAXRANGE: return []



    # unreachable goal -> ground pos
    if not standable(ck, gx, gy, gz, hb):
        for d in range(1, 5):
            if standable(ck, gx, gy - d, gz, hb):
                gy = gy - d
                break

            if standable(ck, gx, gy + d, gz, hb):
                gy = gy + d
                break

        else:
            return []



        

    goal = (gx, gy, gz)
    if start == goal: return []

    openq  = [(0.0, start)]
    came   = {}
    gscore = {start: 0.0}
    seen   = 0


    while openq and seen < maxnodes:
        _, cur = heapq.heappop(openq)
        seen += 1

        if cur == goal:
            out = []
            while cur in came:
                out.append((cur[0] + 0.5, float(cur[1]), cur[2] + 0.5))
                cur = came[cur]
            out.reverse()
            return out

        base = gscore[cur]
        for nb, c in steps(ck, cur, hb):
            if abs(nb[0] - sx) > MAXRANGE or abs(nb[2] - sz) > MAXRANGE: continue

            ng = base + c
            if ng < gscore.get(nb, 1e18):
                gscore[nb] = ng
                came[nb]   = cur
                heapq.heappush(openq, (ng + hcost(nb, goal), nb))

    return []




def blockpos(p):
    return (
        int(flr(p[0])), 
        int(flr(p[1] + 0.01)), 
        int(flr(p[2]))
    )
