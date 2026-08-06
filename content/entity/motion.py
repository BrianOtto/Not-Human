import math

from config import CHUNK_SZ, ENT_EPS, ENT_STILLV

flr, cl = math.floor, math.ceil



def loaded(ck, x, z):
    c = ck.chunks.get((int(flr(x)) // CHUNK_SZ, int(flr(z)) // CHUNK_SZ))
    return bool(c and c.gen_ready)






def boxfree(ck, x, y, z, hw, h, m=ENT_EPS):
    is_solid = ck.issolid   # cache for loop
    sx = int(flr(x - hw - m)); ex = int(cl(x + hw + m))
    sy = int(flr(y - m));      ey = int(cl(y + h  + m))
    sz = int(flr(z - hw - m)); ez = int(cl(z + hw + m))
    

    for bx in range(sx, ex):
        for by in range(sy, ey):
            for bz in range(sz, ez):
                if is_solid(bx, by, bz):
                    if (x - hw < bx + 1 and x + hw > bx and
                        y      < by + 1 and y + h  > by and
                        z - hw < bz + 1 and z + hw > bz):
                        return False
    return True



# slab method
def rayaabb(org, dr, box, maxd=1e9):
    t0, t1 = 0.0, maxd

    for i in range(3):
        d = dr[i]
        lo, hi = box[i], box[i + 3]

        if abs(d) < 1e-8:
            if org[i] < lo or org[i] > hi: return None
            continue

        a = (lo - org[i]) / d
        b = (hi - org[i]) / d
        if a > b: a, b = b, a

        if a > t0: t0 = a
        if b < t1: t1 = b
        if t0 > t1: return None

    return t0


def fluidat(ck, x, y, z):
    from world.blocks import WATER, WATER_FLOWING, LAVA, LAVA_FLOWING
    b = ck.getblock(int(flr(x)), int(flr(y)), int(flr(z)))
    return b in (WATER, WATER_FLOWING, LAVA, LAVA_FLOWING)




def movey(ck, fp, my, hw, h):
    # physics.check_coll copy


    ty = fp[1] + my
    if boxfree(ck, fp[0], ty, fp[2], hw, h):
        fp[1] = ty
        return False, False

    

    precise = abs(my) > 0.6
    grnd    = my < 0
    ceil_   = my > 0

    if precise:

        lo, hi = (ty, fp[1]) if grnd else (fp[1], ty)
        for _ in range(6):
            mid = 0.5 * (lo + hi)
            if boxfree(ck, fp[0], mid, fp[2], hw, h):
                if grnd: hi = mid
                else:    lo = mid
            else:
                if grnd: lo = mid
                else:    hi = mid


        fp[1] = hi if grnd else lo







    elif grnd:
        sy    = float(flr(ty))
        found = False
        for _ in range(10):
            if boxfree(ck, fp[0], sy, fp[2], hw, h):
                fp[1] = sy
                found = True
                break
            sy += 0.05
        if not found: 
            fp[1] = float(cl(ty)) + 0.001

    else:
        fp[1] = float(flr(ty + h)) - h - 0.01

    # bisect/creep leave the feet a hair over the block top, snap them down
    # onto it -> client && server agree on where a settled ent rests
    if grnd:
        sy = float(flr(fp[1]))
        if sy != fp[1] and boxfree(ck, fp[0], sy, fp[2], hw, h): fp[1] = sy

    return grnd, ceil_






def movexz(ck, fp, mx, mz, hw, h, step):
    wall = False


    if mx:
        tx = fp[0] + mx
        if boxfree(ck, tx, fp[1], fp[2], hw, h):
            fp[0] = tx
        elif step and boxfree(ck, tx, fp[1] + step, fp[2], hw, h):
            fp[0] = tx
            fp[1] += step
        else:
            wall = True



    if mz:
        tz = fp[2] + mz
        if boxfree(ck, fp[0], fp[1], tz, hw, h):
            fp[2] = tz
        elif step and boxfree(ck, fp[0], fp[1] + step, tz, hw, h):
            fp[2] = tz
            fp[1] += step
        else:
            wall = True

    return wall




def movebox(ck, pos, vel, hw, h, step, dt):
    fp = pos.copy()

    grnd, ceil_ = movey(ck, fp, vel[1] * dt, hw, h)
    wall        = movexz(ck, fp, vel[0] * dt, vel[2] * dt, hw, h, step)

    if grnd or ceil_: vel[1] = 0.0
    if wall:
        # kill only blocked axis
        if not boxfree(ck, fp[0] + vel[0] * dt, fp[1], fp[2], hw, h): vel[0] = 0.0
        if not boxfree(ck, fp[0], fp[1], fp[2] + vel[2] * dt, hw, h): vel[2] = 0.0

    return fp, grnd, wall




def tickmotion(e, ck, dt):
    t = e.type

    if not loaded(ck, e.pos[0], e.pos[2]):
        e.frozen = True
        return
    e.frozen = False

    if e.grounded and not boxfree(ck, e.pos[0], e.pos[1] - ENT_EPS, e.pos[2], t.hw, t.h):
        if e.vel[1] < 0: e.vel[1] = 0.0
    else:
        e.vel[1] = max(e.vel[1] + t.grav * dt, t.term)

    #f = t.fric if e.grounded else t.drag
    if not e.driven:
        f = t.fric if e.grounded else t.drag
        e.vel[0] *= f
        e.vel[2] *= f

        

    fp, grnd, wall = movebox(ck, e.pos, e.vel, t.hw, t.h, t.step, dt)
    e.pos      = fp
    e.grounded = grnd or not boxfree(ck, fp[0], fp[1] - ENT_EPS, fp[2], t.hw, t.h)

    sp = abs(e.vel[0]) + abs(e.vel[1]) + abs(e.vel[2])
    e.still = e.grounded and sp < ENT_STILLV
    if e.still:
        e.vel[0] = 0.0
        e.vel[2] = 0.0

    e.driven = False


"""
def tickmotion(e, ck, dt):
    t = e.type
    e.vel[1] = max(e.vel[1] + t.grav * dt, t.term)
    ny = e.pos[1] + e.vel[1] * dt
    bx = int(flr(e.pos[0]))
    bz = int(flr(e.pos[2]))
    fb = int(flr(ny))
    if e.vel[1] < 0 and ck.issolid(bx, fb, bz):
        e.pos[1]   = float(fb + 1)
        e.vel[1]   = 0.0
        e.grounded = True
    else:
        e.pos[1]   = ny
        e.grounded = False
"""
