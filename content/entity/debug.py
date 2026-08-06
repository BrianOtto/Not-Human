import math
import numpy as np
import moderngl


MAXV = 8192   # verts, lines

CLR_BOX  = (0.25, 1.00, 0.35, 0.85)
CLR_LOOK = (1.00, 0.20, 0.20, 0.95)
CLR_PATH = (0.35, 0.65, 1.00, 0.85)

LOOKLEN = 2.0




def boxlines(b, out=[]):
    x0, y0, z0, x1, y1, z1 = b
    return [
        (x0,y0,z0),(x1,y0,z0), (x1,y0,z0),(x1,y0,z1),
        (x1,y0,z1),(x0,y0,z1), (x0,y0,z1),(x0,y0,z0),
        (x0,y1,z0),(x1,y1,z0), (x1,y1,z0),(x1,y1,z1),
        (x1,y1,z1),(x0,y1,z1), (x0,y1,z1),(x0,y1,z0),
        (x0,y0,z0),(x0,y1,z0), (x1,y0,z0),(x1,y1,z0),
        (x1,y0,z1),(x1,y1,z1), (x0,y0,z1),(x0,y1,z1),
    ]







class EntityDebug:
    def __init__(self, ctx, prog):
        self.ctx  = ctx
        self.prog = prog # wireframe
        self.vbo  = ctx.buffer(reserve=MAXV * 3 * 4)
        self.vao  = ctx.vertex_array(prog, [(self.vbo, '3f', 'in_pos')])









    def build(self, ents):
        box, look, path = [], [], []



        for e in ents:
            box.extend(boxlines(e.aabb()))


            # facing
            ey = e.eyepos()
            yr = math.radians(e.yaw)
            look.append(tuple(ey))
            look.append((
                float(ey[0]) + math.cos(yr) * LOOKLEN,
                float(ey[1]),
                float(ey[2]) + math.sin(yr) * LOOKLEN,
            ))

            # a* route leg by leg, ENTITY_DBG->mp
            pts = list(e.path[e.pathi:]) if e.path else []
            if not pts and e.navtgt is not None: pts = [e.navtgt]
            if not pts: continue



            prev = (float(e.pos[0]), float(e.pos[1]) + 0.05, float(e.pos[2]))

            for i in pts:
                nxt = (float(i[0]), float(i[1]) + 0.05, float(i[2]))
                path.append(prev)
                path.append(nxt)
                prev = nxt

            #tx, tz = float(e.navtgt[0]), float(e.navtgt[2])
            #fy     = float(e.pos[1]) + 0.05
            #path.append((float(e.pos[0]), fy, float(e.pos[2])))
            #path.append((tx, fy, tz))

            tx, ty, tz = prev
            path.extend([
                (tx - 0.3, ty, tz), (tx + 0.3, ty, tz),
                (tx, ty, tz - 0.3), (tx, ty, tz + 0.3),
            ])


        return box, look, path

    


    def render(self, mvp, ents):
        ents = [i for i in ents if i.type is not None]
        if not ents: return

        box, look, path = self.build(ents)
        allv = box + look + path
        if not allv: return
        if len(allv) > MAXV: allv = allv[:MAXV]




        self.vbo.write(np.array(allv, dtype='f4').tobytes())

        self.prog['mvp'].write(mvp.astype('f4').tobytes())
        self.prog['offset'].value = (0.0, 0.0, 0.0)

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA




        off = 0
        for n, col in ((len(box), CLR_BOX), (len(look), CLR_LOOK), (len(path), CLR_PATH)):
            if n <= 0 or off >= MAXV: continue
            n = min(n, MAXV - off)
            self.prog['wcolor'].value = col
            self.vao.render(moderngl.LINES, vertices=n, first=off)
            off += n

        self.ctx.disable(moderngl.BLEND)





    def release(self):
        self.vbo.release()
        self.vao.release()












