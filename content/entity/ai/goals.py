import math
import random
import numpy as np

from entity.ai import nav
from entity.ai.goal import Goal, MOVE, LOOK
from entity.core   import ANIM_SWING







def nearest(e, w, rng):
    best, bd = None, rng
    for i in w.aiplayers():
        d = float(np.linalg.norm(i.pos - e.pos))
        if d < bd: best, bd = i, d
    return best






class Melee(Goal):
    prio  = 2
    slots = MOVE | LOOK

    def __init__(self, rng=16.0, reach=2.2, dmg=2, cool=1.0):
        self.rng   = rng
        self.reach = reach
        self.dmg   = dmg
        self.cool  = cool
        self.tgt   = None
        self.cd    = 0.0






    def canstart(self, e, w):
        self.tgt = nearest(e, w, self.rng)
        return self.tgt is not None

    # sticky
    # re-pick on tick -> new PlayerState ie logout/die
    def running(self, e, w):
        self.tgt = nearest(e, w, self.rng * 1.5)
        return self.tgt is not None




    def stop(self, e, w):
        self.tgt = None
        e.navtgt = None
        e.path   = []
        nav.stop(e)




    def tick(self, e, w, dt):
        t = self.tgt
        if t is None: return

        self.cd -= dt
        d = float(np.linalg.norm(t.pos - e.pos))


        nav.look(e, t.pos[0], t.pos[2])

        if d <= self.reach:
            nav.stop(e)
            nav.turn(e, nav.yawto(e, t.pos[0], t.pos[2]), dt)

            if self.cd <= 0.0:
                self.cd = self.cool
                w.entanim(e, ANIM_SWING)
                w.hurtplayer(t, self.dmg, e)


        else:
            nav.pathto(
                e, w,
                t.pos[0], t.pos[1], t.pos[2],
                e.type.spd, dt,
                stopd=self.reach * 0.8,
            )









class Wander(Goal):
    prio  = 7
    slots = MOVE | LOOK

    def __init__(self, rng=8.0, idle=(2.0, 6.0)):

        self.rng  = rng
        self.idle = idle
        self.tgt  = None
        self.wait = 0.0






    def canstart(self, e, w): return True
    def running(self, e, w):  return True

    def stop(self, e, w):
        self.tgt = None
        e.navtgt = None
        e.path   = []
        nav.stop(e)


    def pick(self, e):
        a = random.random() * math.pi * 2
        r = 2.0 + random.random() * self.rng
        return (
            float(e.pos[0]) + math.cos(a) * r,
            float(e.pos[2]) + math.sin(a) * r,
        )


    def tick(self, e, w, dt):
        if self.tgt is None:
            self.wait -= dt
            if self.wait > 0.0: return
            self.tgt = self.pick(e)
            return

        

        # stop for a bit
        if nav.pathto(e, w, self.tgt[0], e.pos[1], self.tgt[1], e.type.spd * 0.6, dt):
            self.tgt  = None
            e.navtgt  = None
            self.wait = random.uniform(*self.idle)

        elif abs(float(e.vel[0])) < 0.01 and abs(float(e.vel[2])) < 0.01:
            self.tgt  = None
            e.navtgt  = None
            self.wait = random.uniform(*self.idle)






class LookAt(Goal):
    prio  = 9
    slots = LOOK

    def __init__(self, rng=8.0):
        self.rng = rng
        self.tgt = None


        

    def canstart(self, e, w):
        self.tgt = nearest(e, w, self.rng)
        return self.tgt is not None
    

    def running(self, e, w): return self.canstart(e, w)



    def tick(self, e, w, dt):
        if self.tgt is not None:
            nav.look(e, self.tgt.pos[0], self.tgt.pos[2])























