import os, sys, json, time
import numpy as np
import moderngl
import pygame

from lconst import CONTENT_DIR

sys.path.insert(0, CONTENT_DIR)
from skin import skintex
sys.path.pop(0)

_MODEL_JSON = os.path.join(CONTENT_DIR, "entity", "player", "model.json")
_SH_DIR     = os.path.join(CONTENT_DIR, "shaders")

PART_BODY  = 0.0
PART_HEAD  = 1.0
PART_R_ARM = 2.0
PART_L_ARM = 3.0
PART_R_LEG = 4.0
PART_L_LEG = 5.0


def _sh(nm):
    with open(os.path.join(_SH_DIR, nm), encoding='utf-8') as f:
        return f.read()


# offscreen mini player for launcher
class MiniPlayer:

    def __init__(self, skinpath, sz=220):
        self.sz  = sz
        self.ctx = moderngl.create_standalone_context()

        with open(_MODEL_JSON) as f:
            self.md = json.load(f)

        verts, uvs, norms, pts = self._mesh()
        nv = len(verts)
        inter = np.empty((nv, 9), dtype='f4')
        inter[:, 0:3] = verts
        inter[:, 3:5] = uvs
        inter[:, 5:8] = norms
        inter[:, 8]   = pts
        self.vbo = self.ctx.buffer(inter.tobytes())

        self.skin = self._skin(skinpath)

        self.prog = self.ctx.program(
            vertex_shader   = _sh("inv.vert"),
            fragment_shader = _sh("inv.frag")
        )
        self.vao = self.ctx.vertex_array(self.prog, [
            (self.vbo, '3f 2f 3f 1f', 'in_pos', 'in_uv', 'in_norm', 'in_part_id'),
        ])

        self.ctex = self.ctx.texture((sz, sz), 4)
        self.dtex = self.ctx.depth_renderbuffer((sz, sz))
        self.fbo  = self.ctx.framebuffer(self.ctex, self.dtex)

        self.yaw   = 180.0
        self.pitch = 0.0
        self.scale = 0.82


    def _skin(self, fp):
        return skintex(self.ctx, fp)


    def _mesh(self, verts=[], uvs=[], norms=[], pts=[]):
        verts, uvs, norms, pts = [], [], [], []
        d = self.md["dims"]
        HEAD_SZ = d["HEAD_SZ"]
        BODY_W, BODY_H, BODY_D = d["BODY_W"], d["BODY_H"], d["BODY_D"]
        ARM_W,  ARM_H,  ARM_D  = d["ARM_W"],  d["ARM_H"],  d["ARM_D"]
        LEG_W,  LEG_H,  LEG_D  = d["LEG_W"],  d["LEG_H"],  d["LEG_D"]
        eps = self.md.get("outer_expand", 0.03)
        parts = self.md["parts"]

        def quad(v0, v1, v2, v3, n, uv0, uv1, uv2, uv3, part):
            verts.extend([v0, v1, v2, v0, v2, v3])
            uvs.extend([uv0, uv1, uv2, uv0, uv2, uv3])
            norms.extend([n] * 6)
            pts.extend([part] * 6)

        def uv(x, y): return (x / 64.0, (64.0 - y) / 64.0)

        def box(x0, y0, z0, x1, y1, z1, fuvs, part, mirrored=False):
            f = lambda nm: [uv(*c) for c in fuvs[nm]]
            if mirrored:
                quad([x1,y0,z1],[x0,y0,z1],[x0,y1,z1],[x1,y1,z1], [0,0,1],  *f("front"),  part)
                quad([x0,y0,z0],[x1,y0,z0],[x1,y1,z0],[x0,y1,z0], [0,0,-1], *f("back"),   part)
                quad([x1,y0,z0],[x1,y0,z1],[x1,y1,z1],[x1,y1,z0], [1,0,0],  *f("right"),  part)
                quad([x0,y0,z1],[x0,y0,z0],[x0,y1,z0],[x0,y1,z1], [-1,0,0], *f("left"),   part)
                quad([x1,y1,z1],[x0,y1,z1],[x0,y1,z0],[x1,y1,z0], [0,1,0],  *f("top"),    part)
                quad([x1,y0,z0],[x0,y0,z0],[x0,y0,z1],[x1,y0,z1], [0,-1,0], *f("bottom"), part)
            else:
                quad([x0,y0,z1],[x1,y0,z1],[x1,y1,z1],[x0,y1,z1], [0,0,1],  *f("front"),  part)
                quad([x1,y0,z0],[x0,y0,z0],[x0,y1,z0],[x1,y1,z0], [0,0,-1], *f("back"),   part)
                quad([x1,y0,z1],[x1,y0,z0],[x1,y1,z0],[x1,y1,z1], [1,0,0],  *f("right"),  part)
                quad([x0,y0,z0],[x0,y0,z1],[x0,y1,z1],[x0,y1,z0], [-1,0,0], *f("left"),   part)
                quad([x0,y1,z1],[x1,y1,z1],[x1,y1,z0],[x0,y1,z0], [0,1,0],  *f("top"),    part)
                quad([x0,y0,z0],[x1,y0,z0],[x1,y0,z1],[x0,y0,z1], [0,-1,0], *f("bottom"), part)

        # head
        hh = HEAD_SZ / 2
        hy = LEG_H + BODY_H + HEAD_SZ / 2
        hf = parts["head"]["faces"]
        box(-hh,     hy-hh,     -hh,     hh,     hy+hh,     hh,     hf["base"],  PART_HEAD)
        box(-hh-eps, hy-hh-eps, -hh-eps, hh+eps, hy+hh+eps, hh+eps, hf["outer"], PART_HEAD)

        # body
        bw, bh, bd = BODY_W / 2, BODY_H, BODY_D / 2
        by = LEG_H
        bf = parts["body"]["faces"]
        box(-bw,     by,     -bd,     bw,     by+bh,     bd,     bf["base"],  PART_BODY)
        box(-bw-eps, by-eps, -bd-eps, bw+eps, by+bh+eps, bd+eps, bf["outer"], PART_BODY)

        # r arm
        aw, ah, ad = ARM_W / 2, ARM_H, ARM_D / 2
        ay  = LEG_H
        aox = BODY_W / 2 + aw
        raf = parts["r_arm"]["faces"]
        box(aox-aw,     ay,     -ad,     aox+aw,     ay+ah,         ad,     raf["base"],  PART_R_ARM)
        box(aox-aw-eps, ay-eps, -ad-eps, aox+aw+eps, ay+ah+eps+eps, ad+eps, raf["outer"], PART_R_ARM)

        # l arm
        laox = -(BODY_W / 2 + aw)
        laf  = parts["l_arm"]["faces"]
        box(laox-aw,     ay,     -ad,     laox+aw,     ay+ah,         ad,     laf["base"],  PART_L_ARM, mirrored=True)
        box(laox-aw-eps, ay-eps, -ad-eps, laox+aw+eps, ay+ah+eps+eps, ad+eps, laf["outer"], PART_L_ARM, mirrored=True)

        # r leg
        lw, lh, ld = LEG_W / 2, LEG_H, LEG_D / 2
        rlox = lw
        rlf  = parts["r_leg"]["faces"]
        box(rlox-lw,     0,    -ld,     rlox+lw,     lh,         ld,     rlf["base"],  PART_R_LEG)
        box(rlox-lw-eps, -eps, -ld-eps, rlox+lw+eps, lh+eps+eps, ld+eps, rlf["outer"], PART_R_LEG)

        # l leg
        llox = -lw
        llf  = parts["l_leg"]["faces"]
        box(llox-lw,     0,    -ld,     llox+lw,     lh,         ld,     llf["base"],  PART_L_LEG, mirrored=True)
        box(llox-lw-eps, -eps, -ld-eps, llox+lw+eps, lh+eps+eps, ld+eps, llf["outer"], PART_L_LEG, mirrored=True)

        return np.array(verts), np.array(uvs), np.array(norms), np.array(pts)


    def render(self, yaw=None, pitch=None):
        if yaw   is not None: self.yaw   = yaw
        if pitch is not None: self.pitch = pitch

        mvp = np.identity(4, dtype='f4')

        self.fbo.use()
        self.ctx.clear(0.0, 0.0, 0.0, 0.0)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)

        self.skin.use(0)
        self.prog['mvp'].write(mvp.tobytes())
        self.prog['model_yaw'].value    = self.yaw
        self.prog['model_pitch'].value  = -self.pitch
        self.prog['model_scale'].value  = self.scale
        self.prog['skin_texture'].value = 0
        self.vao.render(moderngl.TRIANGLES)

        data = self.fbo.read(components=4, alignment=1)
        surf = pygame.image.frombuffer(data, (self.sz, self.sz), "RGBA")
        return pygame.transform.flip(surf, False, True)


    def release(self):
        for i in [self.vbo, self.skin, self.ctex, self.fbo, self.vao]:
            i.release()
