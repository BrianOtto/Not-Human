import math
import random
import numpy as np

from entity.blockenty.base import BlockEntity
from entity.blockenty.registry import regblockent, regitemblock


FUSE_TIME       = 4.0
CHAIN_FUSE_MIN  = 0.5
CHAIN_FUSE_MAX  = 1.5
BLAST_RADIUS    = 4.0
BLAST_KNOCK_RAD = 8.0
MAX_KNOCK_FORCE = 18.0

_GRAVITY      = -32.0
_TERMINAL_VEL = -78.4
_INITIAL_VEL_Y =  4.0

_FLASH_SLOW = 0.5    # fuse > 1 s
_FLASH_FAST = 0.1    # fuse ≤ 1 s




def buildsphere(radius):
    r = int(radius)
    offsets = []
    for dx in range(-r - 1, r + 2):
        for dy in range(-r - 1, r + 2):
            for dz in range(-r - 1, r + 2):
                dist = math.sqrt(dx*dx + dy*dy + dz*dz)
                if dist <= radius:
                    offsets.append((dx, dy, dz, dist))
    offsets.sort(key=lambda t: t[3])  # sorted center-out
    return offsets

BLAST_OFF = buildsphere(BLAST_RADIUS)


@regblockent(60)   # world.blocks.TNT = 60
class TNTEntity(BlockEntity):
    def __init__(self, x, y, z, fuse=None, _remote=False, eid=None):
        super().__init__(x, y, z)
        self.fuse    = fuse if fuse is not None else FUSE_TIME
        self._remote = _remote
        self.eid     = eid           # set -> server owns this one
        # pos[1] = bottom of the 1x1x1 cube
        self.pos = np.array([x + 0.5, float(y), z + 0.5], dtype='f4')
        self.vy  = _INITIAL_VEL_Y
        self.tpos = self.pos.copy()  # last pos the server sent

        self._on_ground   = False
        self._flash_timer = 0.0
        self._flash_on    = False
        self._uvs         = None


    # pos[1] = bot
    def aabb(self):
        return (
            self.pos[0] - 0.5, self.pos[1],       self.pos[2] - 0.5,
            self.pos[0] + 0.5, self.pos[1] + 1.0, self.pos[2] + 0.5,
        )


    def dbgtag(self):
        who = f"#{self.eid}" if self.eid is not None else "local"
        og  = "grnd" if self._on_ground else "air"
        d   = float(np.linalg.norm(self.tpos - self.pos)) if self.eid is not None else 0.0
        
        return (
            f"{who} tnt y{self.pos[1]:.1f} vy{self.vy:.1f} "
            f"f{max(self.fuse, 0.0):.1f} {og} d{d:.2f}"
        )


    def setnet(self, pos, vy):
        self.tpos = pos.copy()
        self.vy   = vy


    def update(self, dt, wc):
        # t0 = time.perf_counter()
        chunker = wc.get('chunker')
        if chunker: self.applygrav(dt, chunker)

        # server owned -> predict locally, ease onto the authoritative pos
        if self.eid is not None:
            self.pos += (self.tpos - self.pos) * min(1.0, 10.0 * dt)
            self.x = int(math.floor(self.pos[0]))
            self.y = int(math.floor(self.pos[1]))
            self.z = int(math.floor(self.pos[2]))

        intv = _FLASH_FAST if self.fuse <= 1.0 else _FLASH_SLOW
        self._flash_timer += dt
        if self._flash_timer >= intv:
            self._flash_timer -= intv
            self._flash_on = not self._flash_on

        self.fuse -= dt
        # print(self.fuse)
        # server owned ones blow up when it says so
        if self.fuse <= 0.0 and self.eid is None: self.explode(wc)

    def render(self, mgr):
        uvs = self.getuvs()
        mgr.draw_cube(
            (self.pos[0], self.pos[1] + 0.5, self.pos[2]),
            uvs,
            flash=self._flash_on,
        )

    def applygrav(self, dt, chunker):
        bx = int(math.floor(self.pos[0]))
        bz = int(math.floor(self.pos[2]))



        if self._on_ground:

            sy = int(math.floor(self.pos[1])) - 1
            if not chunker.issolid(bx, sy, bz):
                self._on_ground = False
                self.vy = 0.0


            return



        self.vy = max(self.vy + _GRAVITY * dt, _TERMINAL_VEL)
        ny      = self.pos[1] + self.vy * dt
        # print(self.vy, ny)
        # ny    = self.pos[1] + self.vy * dt + 0.5 * _GRAVITY * dt * dt


        if self.vy < 0:
            fb = int(math.floor(ny - 0.001))
            if chunker.issolid(bx, fb, bz):
                self.pos[1]     = float(fb + 1)
                self.vy         = 0.0
                self._on_ground = True

            else:
                self.pos[1] = ny


        else:
            cb = int(math.floor(ny + 1.001))
            if chunker.issolid(bx, cb, bz):
                self.pos[1] = float(cb) - 1.0
                self.vy = 0.0

            else:
                self.pos[1] = ny

        self.x = int(math.floor(self.pos[0]))
        self.y = int(math.floor(self.pos[1]))
        self.z = int(math.floor(self.pos[2]))




    def explode(self, wc):
        self.alive = False

        chunker    = wc.get('chunker')
        pmgr  = wc.get('particles')
        p     = wc.get('player')
        nc    = wc.get('netclient')
        bemgr = wc.get('blockentys')

        ex = self.pos[0]
        ey = self.pos[1] + 0.5
        ez = self.pos[2]
        cx = int(math.floor(ex))
        cy = int(math.floor(ey))
        cz = int(math.floor(ez))





        from world.blocks import TNT as TNT_ID

        # server authority for block destruction
        if nc and nc.isconn():
            # server does the block destruction, this is just the show
            if chunker and pmgr:
                for dx, dy, dz, dist in BLAST_OFF:
                    if dist > BLAST_RADIUS * 0.6: continue
                    bx, by, bz = cx + dx, cy + dy, cz + dz
                    bt = chunker.getblock(bx, by, bz)
                    if bt and bt != 0 and bt != TNT_ID:
                        pmgr.spawn(bx, by, bz, bt)
            if p: self.knockback(p, ex, ey, ez)
            return


        if chunker:
            cpos = []
            npos = []

            for dx, dy, dz, dist in BLAST_OFF:
                bx, by, bz = cx + dx, cy + dy, cz + dz
                bt = chunker.getblock(bx, by, bz)

                if not bt or bt == 0: continue

                if bt == TNT_ID: cpos.append((bx, by, bz))
                else:            npos.append((bx, by, bz, dist))

            rm = chunker.batchbreak(
                [(bx, by, bz) for bx, by, bz, _ in npos]
            )


            if pmgr:
                for bx, by, bz, dist in npos:
                    if dist <= BLAST_RADIUS * 0.6 and (bx, by, bz) in rm:
                        pmgr.spawn(bx, by, bz, rm[(bx, by, bz)])


            if bemgr is not None:
                for bx, by, bz in cpos:
                    chunker.breakblock(bx, by, bz)
                    fuse = random.uniform(CHAIN_FUSE_MIN, CHAIN_FUSE_MAX)
                    bemgr.activate(bx, by, bz, TNT_ID, fuse=fuse)


            # chain other tnt
            if bemgr is not None:
                for i in bemgr.entities:
                    if i is self or not i.alive: continue
                    if not isinstance(i, TNTEntity): continue
                    d = math.sqrt(
                        (i.pos[0]-ex)**2 +
                        (i.pos[1]+0.5-ey)**2 +
                        (i.pos[2]-ez)**2
                    )

                    if d <= BLAST_RADIUS * 1.5:
                        i.fuse = min(
                            i.fuse,
                            random.uniform(CHAIN_FUSE_MIN, CHAIN_FUSE_MAX)
                        )


        if p: self.knockback(p, ex, ey, ez)

    """
    def applygrav(self, dt, chunker):
        self.vy = max(self.vy + _GRAVITY * dt, _TERMINAL_VEL)
        ny = self.pos[1] + self.vy * dt
        bx = int(math.floor(self.pos[0]))
        bz = int(math.floor(self.pos[2]))
        fb = int(math.floor(ny))
        if self.vy < 0 and chunker.issolid(bx, fb, bz):
            self.pos[1]     = float(fb + 1)
            self.vy         = 0.0
            self._on_ground = True
        else:
            self.pos[1]     = ny
            self._on_ground = False
    """

    """
    def knockback(self, p, ex, ey, ez):
        px, py, pz = p.getpos()
        dx, dy, dz = px - ex, py - ey, pz - ez
        dist = math.sqrt(dx*dx + dy*dy + dz*dz) + 0.001
        if dist > BLAST_KNOCK_RAD: return
        f = MAX_KNOCK_FORCE * (1.0 - dist / BLAST_KNOCK_RAD)
        p.vel += np.array([dx/dist * f, dy/dist * f + 4.0, dz/dist * f], dtype='f4')
    """

    def knockback(self, p, ex, ey, ez):
        px, py, pz = p.getpos()
        dx, dy, dz = px - ex, py - ey, pz - ez
        dist = math.sqrt(dx*dx + dy*dy + dz*dz)
        if dist >= BLAST_KNOCK_RAD or dist < 0.01: return

        strength = (1.0 - dist / BLAST_KNOCK_RAD) * MAX_KNOCK_FORCE
        nx, ny, nz = dx / dist, dy / dist, dz / dist
        # ny = (ny + 1.0) * 0.5
        p.vel += np.array(
            [nx * strength, ny * strength + 6.0, nz * strength],
            dtype='f4',
        )







    def getuvs(self):
        if self._uvs is None:
            self._uvs = self.builduvs()
        return self._uvs






    @staticmethod
    def builduvs():
        from world.blocks import blockuvs, UV_W, UV_H, TNT

        buv = blockuvs(TNT)

        def face_quad(uv):
            u0, v0 = uv
            u1, v1 = u0 + UV_W, v0 + UV_H
            return [[u0,v0],[u1,v0],[u1,v1],[u0,v0],[u1,v1],[u0,v1]]


        fmap = [3, 2, 4, 5, 0, 1]
        auv = []
        for i in fmap:
            auv.extend(face_quad(buv[i]))

        return np.array(auv, dtype='f4')






def useflintonsteel(manager, x, y, z, item_stack, world_ref):
    from world.blocks import TNT
    if world_ref.chunker.getblock(x, y, z) != TNT:
        return

    world_ref.chunker.breakblock(x, y, z)

    nc = world_ref.netclient
    if nc and nc.isconn():
        nc.sendchange(x, y, z, 0x4000)  # tnt ignite signal, server spawns it
    else:
        manager.activate(x, y, z, TNT)






def reginteracts():
    from items.textures import FLINT_AND_STEEL
    from world.blocks import TNT
    regitemblock(FLINT_AND_STEEL, TNT, useflintonsteel)

reginteracts()










