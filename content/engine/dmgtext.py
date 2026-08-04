import math
import random
import numpy as np

from config import (
    CRIT_DIV, POP_VY, POP_G, POP_LIFE,
    POP_GROWR, POP_SHRINKR, POP_MAXMUL, POP_DRIFT,
)

# DAMAGE TEXT POPOFFS 


CRITWORDS = (
    "AIEEE", "AIIEEE", "ARRGH", "AWK", "AWKKKKKK", "BAM", "BANG", "BANG-ETH",
    "BIFF", "BLOOP", "BLURP", "BOFF", "BONK", "CLANK", "CLANK-EST", "CLASH",
    "CLUNK", "CLUNK-ETH", "CRRAACK", "CRASH", "CRUNCH", "CRUNCH-ETH", "EEE-YOW",
    "FLRBBBBB", "GLIPP", "GLURPP", "KAPOW", "KAYO", "KER-SPLOOSH", "KERPLOP",
    "KLONK", "KLUNK", "KRUNCH", "OOOFF", "OOOOFF", "OUCH", "OUCH-ETH", "OWWW",
    "OW-ETH", "PAM", "PLOP", "POW", "POWIE", "QUNCKKK", "RAKKK", "RIP", "SLOSH",
    "SOCK", "SPLATS", "SPLATT", "SPLOOSH", "SWAAP", "SWISH", "SWOOSH", "THUNK",
    "THWACK", "THWACKE", "THWAPE", "THWAPP", "UGGH", "URKKK", "VRONK", "WHACK",
    "WHACK-ETH", "WHAM-ETH", "WHAMM", "WHAMMM", "WHAP", "Z-ZWAP", "ZAM", "ZAMM",
    "ZAMMM", "ZAP", "ZAP-ETH", "ZGRUPPP", "ZLONK", "ZLOPP", "ZLOTT", "ZOK",
    "ZOWIE", "ZWAPP", "ZZWAP", "ZZZZWAP", "ZZZZZWAP",
)

CLR_DMG  = (255,  85,  85)   # red
CLR_CRIT = (255, 170,   0)   # gold
CLR_HEAL = ( 85, 255,  85)   # green

MAXPOPS = 48


class Popoff:
    def __init__(s, pos, txt, col):
        s.pos  = np.array(pos, dtype='f4')
        s.txt  = txt
        s.col  = col
        s.age  = 0.0
        s.scl  = 1.0
        s.grow = True

    
    # blow till 3x, := deflate 
    def step(s, dt):
        s.age += dt

        if s.grow:
            s.scl *= math.exp(POP_GROWR * dt)
            if s.scl > POP_MAXMUL: s.grow = False
        else:
            s.scl *= math.exp(-POP_SHRINKR * dt)

    
    def yoff(s):  return POP_VY * s.age + 0.5 * POP_G * s.age * s.age
    def xzoff(s): return POP_DRIFT * s.age


class DamageText:
    def __init__(self):
        self.pops = []


    #crit at maxhealth/2.5
    def hit(self, pos, dmg, maxhp=20):
        pos = np.array(pos, dtype='f4')
        d   = max(1, int(abs(dmg)))

        if d >= int(maxhp / CRIT_DIV):
            cp     = pos.copy()
            cp[1] += 0.5
            self.spawn(cp, random.choice(CRITWORDS) + "!", CLR_CRIT)

        self.spawn(pos, str(d), CLR_DMG)


    def spawn(self, pos, txt, col):
        if len(self.pops) >= MAXPOPS: self.pops.pop(0)
        self.pops.append(Popoff(pos, txt, col))


    def update(self, dt):
        for i in self.pops:
            i.step(dt)

        
        self.pops = [i for i in self.pops if i.age < POP_LIFE]


    def clear(self):
        self.pops = []
