import shaders
import numpy as np
import moderngl

from entity.blockenty.registry import blockenttype

import entity.blockenty.tnt  # noqa: F401




class BlockEntityManager:
    def __init__(self, ctx, atlas_tex):
        self.ctx     = ctx
        self.texture = atlas_tex
        self.entities = []

        self.prog = ctx.program(
            vertex_shader   = shaders.load("blockent.vert"),
            fragment_shader = shaders.load("blockent.frag"),
        )

        cv, cn        = self.buildcubegeo()
        self.vbo      = ctx.buffer(cv.tobytes())
        self.norm_vbo = ctx.buffer(cn.tobytes())
        # uv buffer overwritten p draw call -> 36 vert * 2 flt * 4 b
        self.uv_buf  = ctx.buffer(reserve=36 * 2 * 4)

        self.vao = ctx.vertex_array(self.prog, [
            (self.vbo,      '3f', 'in_pos'),
            (self.uv_buf,   '2f', 'in_uv'),
            (self.norm_vbo, '3f', 'in_norm'),
        ])
        
        
        
        

    def activate(self, x, y, z, bid, **kwargs):
        ecls = blockenttype(bid)
        if ecls is None:
            return False

        self.entities.append(ecls(x, y, z, **kwargs))
        return True

    def byeid(self, eid):
        for i in self.entities:
            if i.eid == eid: return i
        return None

    def update(self, dt, world_ctx):
        # snapshot entity spawned by explosion this frame -> start ticking next
        for i in list(self.entities):
            if i.alive:
                i.update(dt, world_ctx)
                
        self.entities = [i for i in self.entities if i.alive]

    def render(self, mvp, sun_dir):
        if not self.entities:
            return

        self.prog['mvp'].write(mvp.astype('f4').tobytes())
        self.prog['sun_dir'].write(sun_dir.astype('f4').tobytes())
        self.prog['texture0'].value = 0
        self.texture.use(0)

        self.ctx.enable(moderngl.DEPTH_TEST)

        for i in self.entities:
            if i.alive:
                i.render(self)

    def draw_cube(self, world_pos, uvs, tint=(1.0, 1.0, 1.0), flash=False):
        self.prog['world_pos'].write(np.array(world_pos, dtype='f4').tobytes())
        self.prog['tint'].write(np.array(tint, dtype='f4').tobytes())
        self.prog['flash'].value = 1 if flash else 0
        self.uv_buf.write(uvs.tobytes())
        self.vao.render(moderngl.TRIANGLES)
        
        

    @staticmethod
    def buildcubegeo():
        h = 0.5

        faces = [
            ([[-h,-h, h], [h,-h, h],  [h, h, h],  [-h,-h, h], [h, h, h],  [-h, h, h]], [ 0, 0, 1]),
            ([[ h,-h,-h], [-h,-h,-h], [-h, h,-h], [ h,-h,-h], [-h, h,-h], [ h, h,-h]], [ 0, 0,-1]),
            ([[ h,-h, h], [ h,-h,-h], [ h, h,-h], [ h,-h, h], [ h, h,-h], [ h, h, h]], [ 1, 0, 0]),
            ([[-h,-h,-h], [-h,-h, h], [-h, h, h], [-h,-h,-h], [-h, h, h], [-h, h,-h]], [-1, 0, 0]),
            ([[-h, h, h], [ h, h, h], [ h, h,-h], [-h, h, h], [ h, h,-h], [-h, h,-h]], [ 0, 1, 0]),
            ([[-h,-h,-h], [ h,-h,-h], [ h,-h, h], [-h,-h,-h], [ h,-h, h], [-h,-h, h]], [ 0,-1, 0]),
        ]
        
        verts, norms = [], []
        for i, j in faces:
            verts.extend(i)
            norms.extend([j] * 6)
            
            
        return np.array(verts, dtype='f4'), np.array(norms, dtype='f4')

    def release(self):
        
        for i in (self.vbo, self.norm_vbo, self.uv_buf):
            i.release()
        self.vao.release()
        self.prog.release()







