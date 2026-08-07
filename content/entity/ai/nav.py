import math

from config import JUMP_V
from entity import motion
from entity.ai import path

flr = math.floor

LOOKAH   = 0.55   # test for walls ahead
STEPUP   = 1.05
MAXDROP  = 3
TURNRATE = 400.0  # body degs
HEADMAX  = 60.0







def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def yawto(e, tx, tz):
    #conv: front.x = cos(yaw), front.z = sin(yaw)
    return math.degrees(math.atan2(tz - e.pos[2], tx - e.pos[0]))




def look(e, tx, tz):
    dx = tx - e.pos[0]
    dz = tz - e.pos[2]
    if abs(dx) < 1e-6 and abs(dz) < 1e-6: return
    e.hyaw = yawto(e, tx, tz)





def turn(e, want, dt, rate=TURNRATE):
    d = wrap(want - e.yaw)
    m = rate * dt
    e.yaw = wrap(e.yaw + (d if abs(d) <= m else math.copysign(m, d)))


def face(e, tx, tz):
    dx = tx - e.pos[0]
    dz = tz - e.pos[2]
    if abs(dx) < 1e-6 and abs(dz) < 1e-6: return
    e.yaw  = yawto(e, tx, tz)
    e.hyaw = e.yaw




def stop(e):
    e.vel[0] = 0.0
    e.vel[2] = 0.0





# ground below?
def dropsafe(ck, x, y, z, maxd=MAXDROP):
    bx, bz = int(flr(x)), int(flr(z))
    by     = int(flr(y))
    for i in range(1, maxd + 1):
        if ck.issolid(bx, by - i, bz): return True
    return False





def moveto(e, w, tx, tz, spd, dt=0.05, stopd=0.2, guard=True):
    dx = tx - e.pos[0]
    dz = tz - e.pos[2]
    d  = math.sqrt(dx * dx + dz * dz)

    if d < stopd:
        stop(e)
        return True

    
    
    turn(e, yawto(e, tx, tz), dt)

    yr = math.radians(e.yaw)
    nx, nz = math.cos(yr), math.sin(yr)

    ck = w.chunker
    t  = e.type
    px = e.pos[0] + nx * LOOKAH
    pz = e.pos[2] + nz * LOOKAH





    if not motion.boxfree(ck, px, e.pos[1], pz, t.hw, t.h):

        if e.grounded and motion.boxfree(ck, px, e.pos[1] + STEPUP, pz, t.hw, t.h):
            e.vel[1] = JUMP_V

        elif guard:
            stop(e)
            return False
        

    # already proved path
    elif guard and e.grounded and not dropsafe(ck, px, e.pos[1], pz):
        stop(e)
        return False


    #ease
    al = math.cos(math.radians(wrap(yawto(e, tx, tz) - e.yaw)))
    sc = max(0.0, al)

    e.vel[0] = nx * spd * sc
    e.vel[2] = nz * spd * sc
    e.driven = True
    e.navtgt = (tx, e.pos[1], tz)
    return False










REPATH  = 0.5 # secs between a* runs
WPNEAR  = 0.45





def clearline(ck, e, wp, step=0.4):
    t  = e.type
    dx = wp[0] - e.pos[0]
    dz = wp[2] - e.pos[2]
    d  = math.sqrt(dx * dx + dz * dz)
    if d < 1e-4: return True



    n = int(d / step) + 1
    for i in range(1, n + 1):
        f = min(1.0, (i * step) / d)
        x = e.pos[0] + dx * f
        z = e.pos[2] + dz * f
        if not motion.boxfree(ck, x, e.pos[1], z, t.hw, t.h): return False
        if not dropsafe(ck, x, e.pos[1], z): return False

    return True







# a* to target && walk on waypoints
# fallback->steering if no route
def pathto(e, w, tx, ty, tz, spd, dt, stopd=0.6):
    ck = w.chunker
    dx = tx - e.pos[0]
    dz = tz - e.pos[2]


    if math.sqrt(dx * dx + dz * dz) < stopd:
        stop(e)
        e.path = []
        return True

    e.patht -= dt
    gb = path.blockpos((tx, ty, tz))
    hb = int(math.ceil(e.type.h))

    if not e.path or e.patht <= 0.0 or e.pathtgt != gb:
        e.path    = path.find(ck, path.blockpos(e.pos), gb, hb)
        e.pathi   = 0
        e.patht   = REPATH
        e.pathtgt = gb




    if not e.path:
        return moveto(e, w, tx, tz, spd, dt)

    # eat waypoints
    while e.pathi < len(e.path):
        wp = e.path[e.pathi]
        if (
            abs(wp[0] - e.pos[0]) < WPNEAR and abs(wp[2] - e.pos[2]) < WPNEAR
            and abs(wp[1] - e.pos[1]) < 1.3
        ):
            e.pathi += 1

        else:
            break



    if e.pathi >= len(e.path):
        e.path = []
        return moveto(e, w, tx, tz, spd, dt)

    
    
    j   = e.pathi
    lim = min(e.pathi + 5, len(e.path))
    for k in range(e.pathi + 1, lim):
        if abs(e.path[k][1] - e.pos[1]) > 0.6: break
        if clearline(ck, e, e.path[k]): j = k

    wp = e.path[j]

    # waypoint steup->hop
    if e.grounded and e.path[e.pathi][1] > e.pos[1] + 0.4: e.vel[1] = JUMP_V

    moveto(e, w, wp[0], wp[2], spd, dt, stopd=0.05, guard=False)
    e.navtgt = (tx, ty, tz)
    return False
