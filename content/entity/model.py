import numpy as np
import moderngl
import shaders


MAXPARTS = 12   # entity.vert


def mident(n=MAXPARTS):
    return np.tile(np.eye(4, dtype='f4'), (n, 1, 1))






def rotx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([
        [1, 0,  0, 0],
        [0, c, -s, 0],
        [0, s,  c, 0],
        [0, 0,  0, 1],
    ], dtype='f4')


def roty(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([
        [ c, 0, -s, 0],
        [ 0, 1,  0, 0],
        [ s, 0,  c, 0],
        [ 0, 0,  0, 1],
    ], dtype='f4')


def rotz(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([
        [c, -s, 0, 0],
        [s,  c, 0, 0],
        [0,  0, 1, 0],
        [0,  0, 0, 1],
    ], dtype='f4')




def trans(x, y, z):
    m = np.eye(4, dtype='f4')
    m[0, 3] = x;  m[1, 3] = y;  m[2, 3] = z
    return m


def atpivot(m, p):
    return trans(p[0], p[1], p[2]) @ m @ trans(-p[0], -p[1], -p[2])










class EntityModel:
    def __init__(
        self, 
        ctx, verts, uvs, 
        norms, pids, tex=None
    ):



        self.ctx = ctx
        self.tex = tex

        nv = len(verts)
        iv = np.empty((nv, 9), dtype='f4')
        iv[:, 0:3] = verts
        iv[:, 3:5] = uvs
        iv[:, 5:8] = norms
        iv[:, 8]   = pids

        self.vbo  = ctx.buffer(iv.tobytes())
        self.prog = shaders.prog(ctx, "entity.vert", "entity.frag")
        self.vao  = ctx.vertex_array(self.prog, [
            (self.vbo, '3f 2f 3f 1f', 'in_pos', 'in_uv', 'in_norm', 'in_part_id'),
        ])

        self._ident = mident()








    def render(
        self, mvp, pos, yaw, 
        mats=None, sun_pos=None,
        tex=None, hurt=0.0, hide=-1.0
    ):


        (tex or self.tex).use(0)
        if mats is None: mats = self._ident

        self.prog['mvp'].write(mvp.astype('f4').tobytes())
        self.prog['ent_pos'].write(pos.astype('f4').tobytes())
        self.prog['ent_yaw'].value  = yaw
        self.prog['hidepart'].value = hide
        self.prog['hurt'].value     = hurt

        # mat4 column major -> gl
        # numpy -> row major
        self.prog['parts'].write(
            np.ascontiguousarray(mats.transpose(0, 2, 1), dtype='f4').tobytes()
        )

        if sun_pos is not None:
            self.prog['sun_pos'].write(sun_pos.astype('f4').tobytes())

        self.prog['tex'].value = 0
        self.vao.render(moderngl.TRIANGLES)




    def release(self):
        for i in (self.vbo, self.vao, self.prog):
            i.release()
