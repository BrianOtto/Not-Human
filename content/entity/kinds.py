from config import DROP_F, DROP_LIFETIME, DROP_PICKUP_DELAY, ENT_STEP
from entity.core import (
    Entity, regentity,
    KIND_TNT, KIND_ITEM, KIND_DUMMY,
    REND_CUBE, REND_SPRITE, REND_MODEL,
)


TNT_FUSE = 4.0




@regentity(KIND_TNT, "tnt", w=0.98, h=0.98, rend=REND_CUBE, pin=True)
class TNTEnt(Entity):
    def __init__(self, eid=0, pos=None, fuse=TNT_FUSE, **kw):
        super().__init__(eid=eid, pos=pos, **kw)
        self.fuse = fuse


    def tick(self, dt, w):
        self.age  += dt
        self.fuse -= dt
        if self.fuse <= 0.0: self.kill()


    def dbgtag(self):
        return f"{super().dbgtag()} f{max(self.fuse, 0.0):.1f}"


    def save(self):
        d = super().save()
        d['fuse'] = float(self.fuse)
        return d

    def load(self, d):
        super().load(d)
        self.fuse = d.get('fuse', self.fuse)




@regentity(KIND_ITEM, "item", w=0.25, h=0.25, fric=DROP_F, yoff=0.1, rend=REND_SPRITE)
class ItemDrop(Entity):
    def __init__(self, eid=0, pos=None, iid=0, cnt=1, **kw):
        super().__init__(eid=eid, pos=pos, **kw)
        self.iid   = iid
        self.cnt   = cnt
        self.delay = DROP_PICKUP_DELAY


    def tick(self, dt, w):
        self.age += dt
        if self.delay > 0.0: self.delay -= dt
        
        if self.age > DROP_LIFETIME or self.pos[1] < 0.0: self.kill()


    def dbgtag(self):
        return f"{super().dbgtag()} i{self.iid}x{self.cnt}"


    def save(self):
        d = super().save()
        d['iid'] = int(self.iid)
        d['cnt'] = int(self.cnt)
        return d

    def load(self, d):
        super().load(d)
        self.iid = d.get('iid', self.iid)
        self.cnt = d.get('cnt', self.cnt)




@regentity(KIND_DUMMY, "dummy",
    w=0.6, h=1.8, hp=20, step=ENT_STEP,
    rend=REND_MODEL, persist=True,
)
class DummyEnt(Entity):
    def tick(self, dt, w):
        self.age += dt
        if self.hurtt > 0.0: self.hurtt -= dt
