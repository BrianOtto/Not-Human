import math

from config import JUMP_V
from entity import motion

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





def moveto(e, w, tx, tz, spd, stopd=0.2):
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

        else:
            stop(e)
            return False



        

    elif e.grounded and not dropsafe(ck, px, e.pos[1], pz):
        stop(e)
        return False
    

    e.vel[0] = nx * spd
    e.vel[2] = nz * spd
    e.driven = True
    return False















