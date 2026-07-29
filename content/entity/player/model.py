import json
import os
import numpy as np
import moderngl
import _respath
import shaders
from skin import skintex

PART_BODY  = 0.0
PART_HEAD  = 1.0
PART_R_ARM = 2.0
PART_L_ARM = 3.0
PART_R_LEG = 4.0
PART_L_LEG = 5.0

_PART_ID_TO_CONST = [PART_BODY, PART_HEAD, PART_R_ARM, PART_L_ARM, PART_R_LEG, PART_L_LEG]

_MODEL_JSON = os.path.join(os.path.dirname(__file__), "model.json")


class PlayerModel:

    def __init__(self, ctx, _spath=None):
        self.ctx = ctx
        if _spath is None:
            _spath = _respath.text_player()
        self._spath = _spath

        self._loadjson()

        self.skin_tex = self.loadskin()

        verts, uvs, norms, pts = self.createmesh()

        nv = len(verts)
        interleaved = np.empty((nv, 9), dtype='f4')
        interleaved[:, 0:3] = verts
        interleaved[:, 3:5] = uvs
        interleaved[:, 5:8] = norms
        interleaved[:, 8]   = pts

        self.vbo = ctx.buffer(interleaved.tobytes())

        self.prog = ctx.program(
            vertex_shader=shaders.load("player.vert"),
            fragment_shader=shaders.load("player.frag")
        )

        self.vao = ctx.vertex_array(self.prog, [
            (self.vbo, '3f 2f 3f 1f', 'in_pos', 'in_uv', 'in_norm', 'in_part_id'),
        ])


    def _loadjson(self):
        with open(_MODEL_JSON) as f:
            data = json.load(f)

        d = data["dims"]
        self.HEAD_SZ = d["HEAD_SZ"]
        self.BODY_W  = d["BODY_W"];  self.BODY_H = d["BODY_H"];  self.BODY_D = d["BODY_D"]
        self.ARM_W   = d["ARM_W"];   self.ARM_H  = d["ARM_H"];   self.ARM_D  = d["ARM_D"]
        self.LEG_W   = d["LEG_W"];   self.LEG_H  = d["LEG_H"];   self.LEG_D  = d["LEG_D"]
        self.P_H     = self.LEG_H + self.BODY_H + self.HEAD_SZ
        

        self._expand = data.get("outer_expand", 0.03)
        self._parts  = data["parts"]

    def loadskin(self):
        if not os.path.exists(self._spath):
            self._spath = _respath.text_player()
        return skintex(self.ctx, self._spath)
        
        

    def createmesh(self):
        verts, uvs, norms, pts = [], [], [], []

        def quad(v0, v1, v2, v3, n, uv0, uv1, uv2, uv3, part):
            verts.extend([v0, v1, v2, v0, v2, v3])
            uvs.extend([uv0, uv1, uv2, uv0, uv2, uv3])
            norms.extend([n] * 6)
            pts.extend([part] * 6)
            
            

        def uv(x, y):
            # atlas: x/64, flip y
            return (x / 64.0, (64.0 - y) / 64.0)

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

        eps = self._expand
        

        # HEAD
        hh  = self.HEAD_SZ / 2
        hy  = self.LEG_H + self.BODY_H + self.HEAD_SZ / 2
        hf  = self._parts["head"]["faces"]
        box(-hh,     hy-hh,     -hh,     hh,     hy+hh,     hh,     hf["base"],  PART_HEAD)
        box(-hh-eps, hy-hh-eps, -hh-eps, hh+eps, hy+hh+eps, hh+eps, hf["outer"], PART_HEAD)

        # BODY
        bw, bh, bd = self.BODY_W / 2, self.BODY_H, self.BODY_D / 2
        by = self.LEG_H
        bf = self._parts["body"]["faces"]
        box(-bw,     by,     -bd,     bw,     by+bh,     bd,     bf["base"],  PART_BODY)
        box(-bw-eps, by-eps, -bd-eps, bw+eps, by+bh+eps, bd+eps, bf["outer"], PART_BODY)

        # RIGHT ARM
        aw, ah, ad = self.ARM_W / 2, self.ARM_H, self.ARM_D / 2
        ay  = self.LEG_H
        aox = self.BODY_W / 2 + aw
        raf = self._parts["r_arm"]["faces"]
        box(aox-aw,     ay,     -ad,     aox+aw,     ay+ah,         ad,     raf["base"],  PART_R_ARM)
        box(aox-aw-eps, ay-eps, -ad-eps, aox+aw+eps, ay+ah+eps+eps, ad+eps, raf["outer"], PART_R_ARM)

        # LEFT ARM
        laox = -(self.BODY_W / 2 + aw)
        laf  = self._parts["l_arm"]["faces"]
        box(laox-aw,     ay,     -ad,     laox+aw,     ay+ah,         ad,     laf["base"],  PART_L_ARM, mirrored=True)
        box(laox-aw-eps, ay-eps, -ad-eps, laox+aw+eps, ay+ah+eps+eps, ad+eps, laf["outer"], PART_L_ARM, mirrored=True)

        # RIGHT LEG
        lw, lh, ld = self.LEG_W / 2, self.LEG_H, self.LEG_D / 2
        rlox = lw
        rlf  = self._parts["r_leg"]["faces"]
        box(rlox-lw,     0,    -ld,     rlox+lw,     lh,         ld,     rlf["base"],  PART_R_LEG)
        box(rlox-lw-eps, -eps, -ld-eps, rlox+lw+eps, lh+eps+eps, ld+eps, rlf["outer"], PART_R_LEG)

        # LEFT LEG
        llox = -lw
        llf  = self._parts["l_leg"]["faces"]
        box(llox-lw,     0,    -ld,     llox+lw,     lh,         ld,     llf["base"],  PART_L_LEG, mirrored=True)
        box(llox-lw-eps, -eps, -ld-eps, llox+lw+eps, lh+eps+eps, ld+eps, llf["outer"], PART_L_LEG, mirrored=True)

        return np.array(verts), np.array(uvs), np.array(norms), np.array(pts)

    """
    def createwire(self):
        edges, pts = [], []

        def wirebox(center, size, part):
            hw, hh, hd = size[0]/2, size[1]/2, size[2]/2
            cx, cy, cz = center
            e = [
                [cx-hw,cy-hh,cz-hd],[cx+hw,cy-hh,cz-hd],
                [cx+hw,cy-hh,cz-hd],[cx+hw,cy-hh,cz+hd],
                [cx+hw,cy-hh,cz+hd],[cx-hw,cy-hh,cz+hd],
                [cx-hw,cy-hh,cz+hd],[cx-hw,cy-hh,cz-hd],
                [cx-hw,cy+hh,cz-hd],[cx+hw,cy+hh,cz-hd],
                [cx+hw,cy+hh,cz-hd],[cx+hw,cy+hh,cz+hd],
                [cx+hw,cy+hh,cz+hd],[cx-hw,cy+hh,cz+hd],
                [cx-hw,cy+hh,cz+hd],[cx-hw,cy+hh,cz-hd],
                [cx-hw,cy-hh,cz-hd],[cx-hw,cy+hh,cz-hd],
                [cx+hw,cy-hh,cz-hd],[cx+hw,cy+hh,cz-hd],
                [cx+hw,cy-hh,cz+hd],[cx+hw,cy+hh,cz+hd],
                [cx-hw,cy-hh,cz+hd],[cx-hw,cy+hh,cz+hd],
            ]
            edges.extend(e)
            pts.extend([part] * len(e))

        hy = self.LEG_H + self.BODY_H + self.HEAD_SZ / 2
        wirebox([0, hy, 0], [self.HEAD_SZ]*3, PART_HEAD)
        wirebox([0, self.LEG_H+self.BODY_H/2, 0], [self.BODY_W, self.BODY_H, self.BODY_D], PART_BODY)

        aox = self.BODY_W/2 + self.ARM_W/2
        wirebox([ aox, self.LEG_H+self.ARM_H/2, 0], [self.ARM_W, self.ARM_H, self.ARM_D], PART_R_ARM)
        wirebox([-aox, self.LEG_H+self.ARM_H/2, 0], [self.ARM_W, self.ARM_H, self.ARM_D], PART_L_ARM)

        lox = self.LEG_W/2
        wirebox([ lox, self.LEG_H/2, 0], [self.LEG_W, self.LEG_H, self.LEG_D], PART_R_LEG)
        wirebox([-lox, self.LEG_H/2, 0], [self.LEG_W, self.LEG_H, self.LEG_D], PART_L_LEG)

        return np.array(edges), np.array(pts)
    """

    def render(
        self, mvp, pos, yaw, pitch=0.0, sun_pos=None,
        r_arm=0.0, l_arm=0.0, r_leg=0.0, l_leg=0.0, r_arm_z=0.0, l_arm_z=0.0,
        headyawoff=0.0, crouch=0.0, _hidehead=False, tex=None
    ):
        (tex or self.skin_tex).use(0)
        self.prog['mvp'].write(mvp.astype('f4').tobytes())
        self.prog['player_pos'].write(pos.astype('f4').tobytes())
        self.prog['player_yaw'].value        = yaw
        self.prog['player_pitch'].value      = pitch
        self.prog['right_arm_angle'].value   = r_arm
        self.prog['right_arm_z_angle'].value = r_arm_z
        self.prog['left_arm_angle'].value    = l_arm
        self.prog['left_arm_z_angle'].value  = l_arm_z
        self.prog['right_leg_angle'].value   = r_leg
        self.prog['left_leg_angle'].value    = l_leg
        self.prog['headyawoff'].value        = headyawoff
        self.prog['crouch'].value            = crouch
        self.prog['_hidehead'].value = 1.0 if _hidehead else 0.0
        
        
        if sun_pos is not None:
            self.prog['sun_pos'].write(sun_pos.astype('f4').tobytes())
            
        self.prog['skin_texture'].value = 0
        self.vao.render(moderngl.TRIANGLES)
            
            

    """
    def render(self, mvp, pos, yaw, sun_pos=None, wireframe=False):
        self.skin_tex.use(0)
        self.prog['mvp'].write(mvp.astype('f4').tobytes())
        self.prog['player_pos'].write(pos.astype('f4').tobytes())
        self.prog['player_yaw'].value   = yaw
        self.prog['skin_texture'].value = 0
        self.vao.render(moderngl.TRIANGLES)
        if wireframe:
            self.wire_prog['mvp'].write(mvp.astype('f4').tobytes())
            self.wire_prog['player_pos'].write(pos.astype('f4').tobytes())
            self.wire_prog['player_yaw'].value = yaw
            self.wire_vao.render(moderngl.LINES)
    """

    def release(self):
        for i in [self.vbo, self.skin_tex, self.vao]:
            i.release()
            
            
            


























