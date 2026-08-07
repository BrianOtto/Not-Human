import numpy as np

from config import (
    ENT_GRAV, ENT_TERMVEL, ENT_DRAG, ENT_FRIC, ENT_EASE, HURT_T, KNOCK_T
)


# kind ids
KIND_TNT    = 1
KIND_ITEM   = 2
KIND_DUMMY  = 3
KIND_ZOMBIE = 4

# anims
ANIM_SWING = 1
SWING_T    = 0.3

# renderers
REND_NONE   = 0
REND_CUBE   = 1
REND_SPRITE = 2
REND_MODEL  = 3


TYPES = {} # kind -> EntityType
NAMES = {} # "name" -> kind




class EntityType:
    def __init__(
        self, kind, nm, cls,
        w       = 0.6,
        h       = 0.6,
        hp      = 0,
        grav    = ENT_GRAV,
        term    = ENT_TERMVEL,
        drag    = ENT_DRAG,
        fric    = ENT_FRIC,
        step    = 0.0,
        spd     = 0.0,
        eye     = None,
        yoff    = 0.0,
        armsup  = False,
        rend    = REND_CUBE,
        persist = False,
        despawn = 0.0,
        pin     = False,
    ):

        
        self.kind    = kind
        self.nm      = nm
        self.cls     = cls
        self.w       = w
        self.hw      = w * 0.5
        self.h       = h
        self.hp      = hp
        self.grav    = grav
        self.term    = term
        self.drag    = drag
        self.fric    = fric
        self.step    = step
        self.spd     = spd # speed
        self.armsup  = armsup
        self.eye     = eye if eye is not None else h * 0.85
        self.yoff    = yoff # feet -> wire pos
        self.rend    = rend
        self.persist = persist
        self.despawn = despawn # 0=never
        self.pin     = pin     # keeps its chunk loaded




def regentity(kind, nm, **kw):

    def decor(cls):
        cls.kind     = kind
        TYPES[kind]  = EntityType(kind, nm, cls, **kw)
        NAMES[nm]    = kind
        return cls


    return decor


def enttype(kind):   return TYPES.get(kind)
def entclass(kind):
    t = TYPES.get(kind)
    return t.cls if t else None

def kindbyname(nm):  return NAMES.get(nm.lower())
def kindnames():     return sorted(NAMES)












class Entity:
    kind = 0

    def __init__(self, eid=0, pos=None, yaw=0.0, pitch=0.0):
        self.eid   = eid # 0 = local only
        self.pos   = np.zeros(3, dtype='f4') if pos is None else np.array(pos, dtype='f4')
        self.vel   = np.zeros(3, dtype='f4')
        self.yaw   = yaw # body
        self.hyaw  = yaw # head
        self.pitch = pitch

        t = enttype(self.kind)
        self.type = t
        self.hp   = t.hp if t else 0

        self.alive    = True
        self.grounded = False
        self.age      = 0.0
        self.hurtt    = 0.0
        self.knockt   = 0.0
        self.swing    = 0.0
        self.driven   = False
        self.ai       = None

        
        self.mspd     = 0.0
        self.lpos     = self.pos.copy()
        self.navtgt   = None
        self.dbgai    = "" # goals

        self.path     = [] # a* waypoints
        self.pathi    = 0
        self.patht    = 0.0
        self.pathtgt  = None
        self.still    = False
        self.snt      = False
        self.frozen   = False
        self.tpos     = self.pos.copy()



    # pos[1] = feet
    def aabb(self):
        hw = self.type.hw
        return (
            self.pos[0] - hw, self.pos[1],               self.pos[2] - hw,
            self.pos[0] + hw, self.pos[1] + self.type.h, self.pos[2] + hw,
        )

    def eyepos(self):
        o = self.pos.copy()
        o[1] += self.type.eye
        return o

    def wirepos(self):
        o = self.pos.copy()
        o[1] += self.type.yoff
        return o


    # bookkeeping
    def tick(self, dt, w):
        self.age += dt
        if self.hurtt  > 0.0: self.hurtt  -= dt
        if self.knockt > 0.0: self.knockt -= dt
        if self.swing  > 0.0: self.swing  -= dt





    
    def think(self, dt, w):
        if self.ai is not None: self.ai.tick(self, w, dt)


    # the owner decides an anim happened, everyone plays it
    def playanim(self, anim):
        if anim == ANIM_SWING: self.swing = SWING_T


    def setnet(self, pos, vy):
        self.tpos   = np.array(pos, dtype='f4')
        self.vel[1] = vy

    def netease(self, dt, r=ENT_EASE):
        self.pos += (self.tpos - self.pos) * min(1.0, r * dt)


    def hurt(self, dmg, src=None):
        if dmg <= 0 or not self.alive: return False
        self.hp    = max(0, self.hp - int(dmg))
        self.hurtt = HURT_T
        if self.hp <= 0: self.kill()
        return True

    def knock(self, v):
        self.vel[0] += v[0]
        self.vel[1]  = max(float(self.vel[1]), v[1])
        self.vel[2] += v[2]
        self.knockt  = KNOCK_T
        self.grounded = False
        self.still    = False


    def kill(self):
        self.alive = False


    def dbgtag(self):

        who = f"#{self.eid}" if self.eid else "local"
        gr  = "grnd" if self.grounded else "air"
        d   = float(np.linalg.norm(self.tpos - self.pos)) if self.eid else 0.0
        nm  = self.type.nm if self.type else "?"

        # server owned goals ->ENTITY_DBG
        if   self.dbgai:      ai = " " + self.dbgai
        elif self.ai:         ai = " " + ",".join(self.ai.names())
        else:                 ai = ""

        return (
            f"{who} {nm} y{self.pos[1]:.1f} vy{self.vel[1]:.1f} "
            f"hp{self.hp} {gr} d{d:.2f}{ai}"
        )




    # persistence -> plain dict
    # packed by chunk writer
    def save(self):
        return {
            'kind': self.kind,
            'pos':  [float(i) for i in self.pos],
            'vel':  [float(i) for i in self.vel],
            'yaw':  float(self.yaw),
            'hp':   int(self.hp),
        }




    def load(self, d):
        self.pos = np.array(d['pos'], dtype='f4')
        self.vel = np.array(d.get('vel', (0, 0, 0)), dtype='f4')
        self.yaw = d.get('yaw', 0.0)
        self.hp  = d.get('hp', self.hp)
        self.tpos = self.pos.copy()




def mkentity(kind, eid=0, pos=None, **kw):
    cls = entclass(kind)
    if cls is None: return None
    return cls(eid=eid, pos=pos, **kw)
