import math

from config import JUMP_V
from entity import motion
from entity.ai import path

flr = math.floor

LOOKAH   = 0.55   # test for walls ahead
STEPUP   = 1.05
MAXDROP  = 3







def face(e, tx, tz):
    dx = tx - e.pos[0]
    dz = tz - e.pos[2]
    if abs(dx) < 1e-6 and abs(dz) < 1e-6: return
    #conv: front.x = cos(yaw), front.z = sin(yaw)
    e.yaw = math.degrees(math.atan2(dz, dx))




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





def moveto(e, w, tx, tz, spd, stopd=0.2, guard=True):
    dx = tx - e.pos[0]
    dz = tz - e.pos[2]
    d  = math.sqrt(dx * dx + dz * dz)

    if d < stopd:
        stop(e)
        return True


    

    nx, nz = dx / d, dz / d
    face(e, tx, tz)

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

    #already proved route
    elif guard and e.grounded and not dropsafe(ck, px, e.pos[1], pz):
        stop(e)
        return False
    

    e.vel[0] = nx * spd
    e.vel[2] = nz * spd
    e.driven = True
    e.navtgt = (tx, e.pos[1], tz)
    return False

















REPATH  = 0.5 # secs between a* runs
WPNEAR  = 0.45




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
        return moveto(e, w, tx, tz, spd)

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
        return moveto(e, w, tx, tz, spd)

    wp = e.path[e.pathi]

    # waypoint steup->hop
    if e.grounded and wp[1] > e.pos[1] + 0.4: e.vel[1] = JUMP_V

    moveto(e, w, wp[0], wp[2], spd, stopd=0.05, guard=False)
    e.navtgt = (tx, ty, tz)
    return False
