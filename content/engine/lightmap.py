import math
import random
import numpy as np
import moderngl



AMBIENT = 0.0

BRIGHT_RAMP = np.empty(16, dtype=np.float32)
for i in range(16):
    v = 1.0 - i / 15.0
    BRIGHT_RAMP[i] = ((1.0 - v) / (v * 3.0 + 1.0)) * (1.0 - AMBIENT) + AMBIENT







# td 0..1, 0 =noon 
# noon -> 1.0, midnight -> 0.2
def skydarken(td, rain=0.0, thunder=0.0):

    br = 1.0 - (math.cos(td * math.pi * 2.0) * 2.0 + 0.2)
    if br < 0.0: br = 0.0
    if br > 1.0: br = 1.0

    br  = 1.0 - br
    br *= 1.0 - rain    * 5.0 / 16.0
    br *= 1.0 - thunder * 5.0 / 16.0

    return br * 0.8 + 0.2






def skybright(td):
    br = math.cos(td * math.pi * 2.0) * 2.0 + 0.5
    if br < 0.0: br = 0.0
    if br > 1.0: br = 1.0
    return br




"""

def skydarken(td, rain=0.0, thunder=0.0):
    br = 1 - (math.cos(td * math.pi * 2) * 2 + 0.5)
    br = min(max(br, 0.0), 1.0)
    br = 1 - br
    br *= 1 - rain    * 5 / 16.0
    br *= 1 - thunder * 5 / 16.0
    br = 1 - br
    return int(br * 11)
"""








class Lightmap:
    

    def __init__(self, ctx):
        self.ctx  = ctx
        self.px   = np.empty((16, 16, 3), dtype=np.uint8)
        self.blr  = 0.0
        self.blrt = 0.0
        self.gam  = 0.0  # options->gamma
        self.bolt = 0    # lightningBoltTime
        self.acc  = 0.0
        self.dkn  = -1.0

        self.tex = ctx.texture((16, 16), 3, dtype='f1')
        self.tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.tex.repeat_x = False
        self.tex.repeat_y = False

        self.build(1.0)




    def tick(self):
        self.blrt += (random.random() - random.random()) * random.random() * random.random()
        self.blrt *= 0.9
        self.blr  += self.blrt - self.blr








    def update(self, dt, darken):

        
        self.acc += dt
        hit = False
        while self.acc >= 0.05:
            self.acc -= 0.05
            self.tick()
            hit = True

        if hit or darken != self.dkn:
            self.dkn = darken
            self.build(darken)



    def build(self, darken):
        # row = skylvl, cols = blvl
        d = 1.0 if self.bolt > 0 else darken * 0.95 + 0.05
        s = BRIGHT_RAMP[:, None] * d
        b = BRIGHT_RAMP[None, :] * (self.blr * 0.1 + 1.5)

        f  = darken * 0.65 + 0.35
        rs = s * f
        gs = s * f
        bs = s


        
        rb = b
        gb = b * ((b * 0.6 + 0.4) * 0.6 + 0.4)
        bb = b * ((b * b) * 0.6 + 0.4)


        r = (rs + rb) * 0.96 + 0.03
        g = (gs + gb) * 0.96 + 0.03
        v = (bs + bb) * 0.96 + 0.03

        np.clip(r, None, 1.0, out=r)
        np.clip(g, None, 1.0, out=g)
        np.clip(v, None, 1.0, out=v)

        if self.gam > 0.0:
            r = r * (1 - self.gam) + (1 - (1 - r) ** 4) * self.gam
            g = g * (1 - self.gam) + (1 - (1 - g) ** 4) * self.gam
            v = v * (1 - self.gam) + (1 - (1 - v) ** 4) * self.gam


        r = np.clip(r * 0.96 + 0.03, 0.0, 1.0)
        g = np.clip(g * 0.96 + 0.03, 0.0, 1.0)
        v = np.clip(v * 0.96 + 0.03, 0.0, 1.0)

        self.px[:, :, 0] = (r * 255.0).astype(np.uint8)
        self.px[:, :, 1] = (g * 255.0).astype(np.uint8)
        self.px[:, :, 2] = (v * 255.0).astype(np.uint8)
        self.tex.write(self.px.tobytes())




    def use(self, unit):
        self.tex.use(unit)





















