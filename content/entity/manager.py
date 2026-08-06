import math
import numpy as np
import moderngl

import _respath
from skin import skintex
from config import HURT_T
from entity import motion
from entity.core import REND_MODEL, mkentity
from entity.store import entck, saveents, loadents
import entity.kinds  # noqa: F401


SYNC_INT = 1.0




class EntityManager:
    def __init__(self, ctx, pmodel, world=None):
        self.ctx    = ctx
        self.pmodel = pmodel
        self.world  = world
        self.chunker = None
        self.ents   = {}
        self.texs   = {}
        self.neid   = -1


        self.wdir    = None
        self.loaded  = set()
        self.synct   = 0.0


    def tex(self, nm):
        if nm not in self.texs:
            self.texs[nm] = skintex(self.ctx, _respath.text_entity(nm))
        return self.texs[nm]


    def spawn(self, kind, eid=0, pos=None, yaw=0.0):
        e = mkentity(kind, eid=eid, pos=pos)
        if e is None: return None

        if not eid:
            e.eid = self.neid
            self.neid -= 1

        e.yaw  = yaw
        e.tpos = e.pos.copy()
        self.ents[e.eid] = e
        return e


    def byeid(self, eid):  return self.ents.get(eid)
    def remove(self, eid): self.ents.pop(eid, None)
    def clear(self):       self.ents.clear()
    def count(self):       return len(self.ents)


    
    def update(self, dt, chunker, local=True):
        self.chunker = chunker


        for i in list(self.ents.values()):
            i.tick(dt, self)

            if local:
                if not i.frozen: i.think(dt, self)
                motion.tickmotion(i, chunker, dt)
            else:
                i.netease(dt)



            
            sp = float(np.linalg.norm(i.pos - i.lpos)) / max(dt, 1e-5)
            i.mspd = i.mspd * 0.7 + sp * 0.3
            i.lpos = i.pos.copy()


            if not i.alive: self.ents.pop(i.eid, None)



        if local: self.syncents(dt, chunker)





    # mirror of Instance.aiplayers @server
    def aiplayers(self):
        p = self.world.p if self.world else None
        return [p] if p is not None and p.health > 0 else []

    def hurtplayer(self, t, dmg):
        t.hurt(dmg)

    # singleplayer, nobody to tell
    def entanim(self, e, anim):
        e.playanim(anim)




    
    def syncents(self, dt, chunker):
        self.wdir = chunker.chunks_dir

        self.synct -= dt
        if self.synct > 0.0: return
        self.synct = SYNC_INT

        rdy = {k for k, c in chunker.chunks.items() if c.gen_ready}

        for k in rdy - self.loaded:
            self.loaded.add(k)
            for d in loadents(self.wdir, k[0], k[1]):
                e = mkentity(d.get('kind', 0), eid=self.neid)
                if e is None: continue
                self.neid -= 1
                e.load(d)
                self.ents[e.eid] = e

        for k in list(self.loaded - rdy):
            self.loaded.discard(k)
            gone = [i for i in self.ents.values()
                    if i.type.persist and entck(i) == k]
            for i in gone: self.ents.pop(i.eid, None)
            saveents(self.wdir, k[0], k[1], gone)


    def saveall(self):
        if not self.wdir: return

        live = [i for i in self.ents.values() if i.type.persist]
        byck = {k: [] for k in self.loaded}
        for i in live: byck.setdefault(entck(i), []).append(i)

        for k, es in byck.items():
            saveents(self.wdir, k[0], k[1], es)


    def posefor(self, e):
        #spd = math.sqrt(float(e.vel[0]) ** 2 + float(e.vel[2]) ** 2)
        ra = la = rl = ll = 0.0

        if e.mspd > 0.35:
            wc = e.age * 4.0
            ra = math.sin(wc) * 50.0
            la = -ra
            rl = ra
            ll = rl

            

        # zombies and stuff
        if e.type.armsup:
            ra = la = -80.0

        if e.swing > 0.0:
            sw = math.sin((1.0 - e.swing / 0.3) * math.pi) * -60.0
            ra += sw
            la += sw

        return self.pmodel.posemats(
            pitch=e.pitch, r_arm=ra, l_arm=la, r_leg=rl, l_leg=ll
        )


    def render(self, mvp, sun_pos):
        if not self.ents: return

        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)

        for i in self.ents.values():
            t = i.type
            if t.rend != REND_MODEL: continue

            self.pmodel.model.render(
                mvp, i.pos, i.yaw, self.posefor(i),
                sun_pos = sun_pos,
                tex     = self.tex(t.nm),
                hurt    = max(0.0, i.hurtt / HURT_T),
            )

        self.ctx.enable(moderngl.CULL_FACE)


    # nearest ent on the ray
    def pick(self, org, dr, maxd):
        best, bd = None, maxd

        for i in self.ents.values():
            if i.type.hp <= 0: continue
            d = motion.rayaabb(org, dr, i.aabb(), maxd)
            if d is not None and d < bd:
                best, bd = i, d

        return best


    def release(self):
        for i in self.texs.values(): i.release()
        self.texs.clear()
