import numpy as np
import moderngl
import math
import random
import pygame
import shaders
import _respath

from config import (
    DROP_PICKUP_DELAY, DROP_PICKUP_RANGE, DROP_LIFETIME,
    DROP_BOBSPEED, DROP_BOBHEIGHT, DROP_SPIN, DROP_SZ,
    DROP_G, DROP_F
)
from items.registry import REGISTRY
from world.animation import getanims




class ItemEntity:
    def __init__(self, iid, count, pos, vel=None, tint=(1.0, 1.0, 1.0), tint_mode=0, entity_id=0):
        self.itemId       = iid
        self.count        = count
        self.pos          = pos.astype('f4').copy()
        self.vel          = vel.astype('f4').copy() if vel is not None else np.zeros(3, dtype='f4')
        self.rot          = random.random() * math.pi * 2  # rand init spin [0, 2π]
        self.age          = 0.0
        self.pickup_delay = DROP_PICKUP_DELAY
        self.bob_phase    = random.random() * math.pi * 2
        self.active       = True
        self.grounded     = False
        self.tint         = tint
        self.tint_mode    = tint_mode
        self.entity_id    = entity_id
        self.tpos         = self.pos.copy()   # last pos the server sent


    def setnet(self, pos, vy):
        self.tpos   = pos.copy()
        self.vel[1] = vy


    def dbgtag(self):
        who = f"#{self.entity_id}" if self.entity_id else "local"
        gr  = "grnd" if self.grounded else "air"
        d   = float(np.linalg.norm(self.tpos - self.pos)) if self.entity_id else 0.0
        return (f"{who} item{self.itemId}x{self.count} y{self.pos[1]:.1f} "
                f"{gr} d{d:.2f}")


class ItemEntityManager:
    BLOCK_UV_MAP = {
        1:  (1, 0), 2:  (2, 0), 3:  (3, 0), 4:  (1, 1), 5:  (2, 1),
        6:  (0, 1), 7:  (3, 1), 8:  (0, 2), 9:  (1, 2), 10: (2, 2),
        11: (3, 2), 12: (4, 0), 13: (4, 1), 14: (4, 2), 20: (2, 1),
    }

    TINT_MAP = {
        1: (0.47, 0.75, 0.35),
        8: (0.28, 0.70, 0.09),
        9: (0.38, 0.60, 0.38),
        10: (0.47, 0.75, 0.35),
    }

    TINT_MODE_ALL = 0
    TINT_MODE_TOP = 1
    TINT_MODE_MAP = {1: 1}

    B_ATLAS_SZ = 320 # 20 * 16
    B_TILE_SZ  = 16
    I_ATLAS_SZ = 240 # 15 * 16
    I_TILE_SZ  = 16
    I_ATLAS_COLS = 15
    
    
    
    
    
    

    def __init__(self, ctx, texture, world):
        self.ctx     = ctx
        self.texture = texture
        self.world   = world
        self.items   = []
        
        

        self.items_img = pygame.image.load(_respath.atlas_items()).convert_alpha()

        imgf = pygame.transform.flip(self.items_img, False, True)
        self.text_item = ctx.texture(imgf.get_size(), 4, pygame.image.tostring(imgf, "RGBA"))
        self.text_item.filter = (moderngl.NEAREST, moderngl.NEAREST)
        

        anims  = getanims()
        _meta = anims.surfaceatlas()
        if _meta:
            metaf = pygame.transform.flip(_meta, False, True)
            self.text_meta_atlas = ctx.texture(metaf.get_size(), 4, pygame.image.tostring(metaf, "RGBA"))
            self.text_meta_atlas.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.meta_atlas_width, self.meta_atlas_height = anims.szatlas()
        else:
            self.text_meta_atlas = None
            self.meta_atlas_width   = 16
            self.meta_atlas_height  = 16
            
            
            

        self.prog = shaders.prog(ctx, "item.vert", "item.frag")

        cv, cu, cn   = self.createcube()
        self.vbo      = ctx.buffer(cv.astype('f4').tobytes())
        self.uv_buf   = ctx.buffer(reserve=cu.nbytes)
        self.norm_vbo = ctx.buffer(cn.astype('f4').tobytes())
        self.vao      = ctx.vertex_array(self.prog, [
            (self.vbo,      '3f', 'in_pos'),
            (self.uv_buf,   '2f', 'in_uv'),
            (self.norm_vbo, '3f', 'in_norm'),
        ])

        self.sprcache = {}
        self.sundir   = np.array([0.5, 1.0, 0.3], dtype='f4')

    def createcube(self):
        h = 0.5
        verts, uvs, norms = [], [], []
        uvc = [(0, 0), (1, 0), (1, 1), (0, 0), (1, 1), (0, 1)]

        faces = [
            ([[-h,-h,h], [h,-h,h],  [h,h,h],   [-h,-h,h],  [h,h,h],   [-h,h,h]],  [0,0,1]),
            ([[h,-h,-h], [-h,-h,-h],[-h,h,-h], [h,-h,-h],  [-h,h,-h], [h,h,-h]],  [0,0,-1]),
            ([[h,-h,h],  [h,-h,-h], [h,h,-h],  [h,-h,h],   [h,h,-h],  [h,h,h]],   [1,0,0]),
            ([[-h,-h,-h],[-h,-h,h], [-h,h,h],  [-h,-h,-h], [-h,h,h],  [-h,h,-h]], [-1,0,0]),
            ([[-h,h,h],  [h,h,h],   [h,h,-h],  [-h,h,h],   [h,h,-h],  [-h,h,-h]], [0,1,0]),
            ([[-h,-h,-h],[h,-h,-h], [h,-h,h],  [-h,-h,-h], [h,-h,h],  [-h,-h,h]], [0,-1,0]),
        ]

        for i, j in faces:
            verts.extend(i)
            norms.extend([j] * 6)
            uvs.extend(uvc)

        return np.array(verts), np.array(uvs, dtype='f4'), np.array(norms)
        
        
        
        
        

    def bakesprite(self, iid):
        idef = REGISTRY.get(iid)
        if not idef:
            return None

        col, row = idef.texture_uv
        px, py   = col * 16, row * 16
        atc      = self.items_img.get_width()  // 16
        atr      = self.items_img.get_height() // 16

        eps = 0.0001
        u0  = col / atc + eps;             u1 = (col + 1) / atc - eps
        v0  = 1.0 - (row + 1) / atr + eps; v1 = 1.0 - row / atr - eps

        h   = 0.5;  d = 0.035
        pix = 1.0 / 16.0
        pu  = (u1 - u0) / 16.0
        pv  = (v1 - v0) / 16.0

        verts = []; uvs = []; norms = []
        
        

        # front +z
        verts.extend([[-h,-h,d], [h,-h,d], [h,h,d], [-h,-h,d], [h,h,d], [-h,h,d]])
        uvs.extend([[u0,v0], [u1,v0], [u1,v1], [u0,v0], [u1,v1], [u0,v1]])
        norms.extend([[0,0,1]] * 6)

        # back -z
        verts.extend([[h,-h,-d], [-h,-h,-d], [-h,h,-d], [h,-h,-d], [-h,h,-d],[h,h,-d]])
        uvs.extend([[u1,v0], [u0,v0], [u0,v1], [u1,v0], [u0,v1], [u1,v1]])
        norms.extend([[0,0,-1]] * 6)
        
        

        def is_opaque(tx, ty):
            if tx < 0 or tx >= 16 or ty < 0 or ty >= 16:
                return False
            c = self.items_img.get_at((px + tx, py + ty))
            return c[3] > 128
            
            
            

        for ty in range(16):
            for tx in range(16):
                if not is_opaque(tx, ty):
                    continue
                ovlp = 0.001
                x0 = -h + tx * pix - ovlp;      x1 = -h + (tx+1) * pix + ovlp
                y0 = h - (ty+1) * pix - ovlp;   y1 = h - ty * pix + ovlp
                puc = u0 + (tx + 0.5) * pu
                pvc = v1 - (ty + 0.5) * pv

                if not is_opaque(tx+1, ty):  # right +x
                    verts.extend([[x1,y0,d],[x1,y0,-d],[x1,y1,-d],[x1,y0,d],[x1,y1,-d],[x1,y1,d]])
                    uvs.extend([[puc,pvc]]*6);  norms.extend([[1,0,0]]*6)
                if not is_opaque(tx-1, ty):  # left -x
                    verts.extend([[x0,y0,-d],[x0,y0,d],[x0,y1,d],[x0,y0,-d],[x0,y1,d],[x0,y1,-d]])
                    uvs.extend([[puc,pvc]]*6);  norms.extend([[-1,0,0]]*6)
                if not is_opaque(tx, ty-1):  # top +y
                    verts.extend([[x0,y1,d],[x1,y1,d],[x1,y1,-d],[x0,y1,d],[x1,y1,-d],[x0,y1,-d]])
                    uvs.extend([[puc,pvc]]*6);  norms.extend([[0,1,0]]*6)
                if not is_opaque(tx, ty+1):  # bot -y
                    verts.extend([[x0,y0,-d],[x1,y0,-d],[x1,y0,d],[x0,y0,-d],[x1,y0,d],[x0,y0,d]])
                    uvs.extend([[puc,pvc]]*6);  norms.extend([[0,-1,0]]*6)

        if not verts: return None
        
        
        
        

        vbo      = self.ctx.buffer(np.array(verts, dtype='f4').tobytes())
        uv_vbo   = self.ctx.buffer(np.array(uvs,   dtype='f4').tobytes())
        norm_vbo = self.ctx.buffer(np.array(norms, dtype='f4').tobytes())
        vao = self.ctx.vertex_array(self.prog, [
            (vbo,      '3f', 'in_pos'),
            (uv_vbo,   '2f', 'in_uv'),
            (norm_vbo, '3f', 'in_norm'),
        ])
        
        
        return {
            'vao': vao, 'vbo': vbo, 
            'uv_vbo': uv_vbo, 'norm_vbo': norm_vbo, 
            'count': len(verts)
        }
        
        

    def spritevao(self, iid):
        if iid not in self.sprcache:
            self.sprcache[iid] = self.bakesprite(iid)
        return self.sprcache[iid]
        
        

    def itemuvs(self, iid):
        idef = REGISTRY.get(iid)
        if idef and idef.is_block:
            return self.blockuvs(iid), True
        return self.rawitemuvs(iid), False
        
        

    def blockuvs(self, bid):
        from world.blocks import blockuvs, UV_W, UV_H

        def fuv(uv):
            u0, v0 = uv
            return [
                [u0,v0],[u0+UV_W,v0],[u0+UV_W,v0+UV_H],
                [u0,v0],[u0+UV_W,v0+UV_H],[u0,v0+UV_H]
            ]

        uvs  = blockuvs(bid)
        fmap = [3, 2, 4, 5, 0, 1]  # faces -> blockuv idx
        auv  = []
        
        for i in fmap:
            auv.extend(fuv(uvs[i]))
        return np.array(auv, dtype='f4')
        
        
        

    def animblockuvs(self, anim_name):
        anims = getanims()
        fr   = anims.getframe(anim_name)
        cs, rs, fc = anims.atlaslayout(anim_name)
        tsz  = 16
        px, py = cs * tsz, fr * tsz

        from world.animation import ANIM_TEXT
        cused = ANIM_TEXT.get(anim_name, 16) // 16
        tw = cused * tsz
        aw = self.meta_atlas_width;  ah = self.meta_atlas_height

        u0 = px / aw;           u1 = (px + tw) / aw
        v0 = 1.0 - (py + tsz) / ah; v1 = 1.0 - py / ah

        fuv = [[u0,v0],[u1,v0],[u1,v1],[u0,v0],[u1,v1],[u0,v1]]
        auv = []
        for _ in range(6): auv.extend(fuv)
        
        return np.array(auv, dtype='f4')
        
        

    def rawitemuvs(self, iid):
        from items import textures as text_items

        idef = REGISTRY.get(iid)
        col, row = idef.texture_uv if idef else text_items.getuv(iid)

        u0 = col / 15.0;        u1 = (col + 1) / 15.0
        v0 = 1.0 - (row+1) / 15.0; v1 = 1.0 - row / 15.0
        pix = 1.0 / (15.0 * 16.0)

        auv = []
        auv.extend([[u0,v0],[u1,v0],[u1,v1],[u0,v0],[u1,v1],[u0,v1]])       # front
        auv.extend([[u1,v0],[u0,v0],[u0,v1],[u1,v0],[u0,v1],[u1,v1]])       # back
        
        ru0, ru1 = u1 - pix, u1
        auv.extend([[ru0,v0],[ru1,v0],[ru1,v1],[ru0,v0],[ru1,v1],[ru0,v1]]) # r
        
        lu0, lu1 = u0, u0 + pix
        auv.extend([[lu0,v0],[lu1,v0],[lu1,v1],[lu0,v0],[lu1,v1],[lu0,v1]]) # l
        
        tv0, tv1 = v1 - pix, v1
        auv.extend([[u0,tv0],[u1,tv0],[u1,tv1],[u0,tv0],[u1,tv1],[u0,tv1]]) # top
        
        bv0, bv1 = v0, v0 + pix
        auv.extend([[u0,bv0],[u1,bv0],[u1,bv1],[u0,bv0],[u1,bv1],[u0,bv1]]) # bot
        return np.array(auv, dtype='f4')
        
        
        

    def spawn(self, iid, count, pos, throw_dir=None, throw_spd=3.0, entity_id=0):
        if not REGISTRY.exists(iid):
            print(f"cannot spawn unknown item: {iid}")
            return None

        if throw_dir is not None:
            td = throw_dir.astype('f4')
            norm = np.linalg.norm(td)
            if norm > 0: td /= norm
            vel = td * throw_spd
            vel[1] += 2.0
        else:
            vel = np.array(
                [
                    (random.random() - 0.5) * 2.0,
                    2.0,
                    (random.random() - 0.5) * 2.0
                ], dtype='f4'
            )
            

        tint  = self.TINT_MAP.get(iid, (1.0, 1.0, 1.0))
        tmode = self.TINT_MODE_MAP.get(iid, self.TINT_MODE_ALL)

        item = ItemEntity(iid, count, pos, vel, tint, tmode, entity_id)
        self.items.append(item)
        return item
        
        

    def byeid(self, eid):
        for i in self.items:
            if i.entity_id == eid: return i
        return None


    def update(self, dt, player_pos, inv, netclient=None):
        rm = []

        for i in self.items:
            if not i.active:
                rm.append(i);  continue

            i.age += dt
            i.pickup_delay = max(0, i.pickup_delay - dt)

            # server owned ones die when it says so
            if i.age > DROP_LIFETIME and not i.entity_id:
                i.active = False;  rm.append(i);  continue

            if not i.grounded:
                i.vel[1] += DROP_G * dt

            np2 = i.pos + i.vel * dt
            gy  = self.groundy(np2[0], np2[1], np2[2])
            

            if np2[1] < gy + 0.1:
                np2[1]       = gy + 0.1
                i.vel[1]    = 0
                i.grounded  = True
                i.vel[0]   *= DROP_F;  i.vel[2] *= DROP_F
            else:
                i.grounded = False
                
                

            i.pos  = np2

            # server owned -> ease onto the pos it keeps sending
            if i.entity_id and netclient:
                i.pos += (i.tpos - i.pos) * min(1.0, 10.0 * dt)

            i.rot += DROP_SPIN * dt
            

            if i.pickup_delay <= 0:
                dist = np.linalg.norm(player_pos - i.pos)
                if dist < DROP_PICKUP_RANGE:
                    if netclient:
                        netclient.sendpickup(i.entity_id)
                        i.pickup_delay = 0.5
                    else:
                        if inv.add(i.itemId, i.count):
                            i.active = False;  rm.append(i)
                            
                            

        for i in rm:
            if i in self.items:
                self.items.remove(i)
                
                
                
                
                
                

    def groundy(self, x, y_start, z):
        cx, cz = int(math.floor(x)), int(math.floor(z))
        sy = int(math.floor(y_start))

        for y in range(sy, sy - 10, -1):
            if y < 0 or y >= 128: continue
            if self.world.chunker.issolid(cx, y, cz):
                return y + 1.0
        return -1000.0
        
        
        
        
        

    def render(self, mvp, sun_dir=None):
        if not self.items: return

        self.prog['mvp'].write(mvp.astype('f4').tobytes())

        if sun_dir is not None:
            self.sundir = sun_dir.astype('f4')
        self.prog['sun_dir'].write(self.sundir.tobytes())
        
        
        bsc = DROP_SZ
        ssc = DROP_SZ * 1.5

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        
        

        ctex = None

        for i in self.items:
            if not i.active: continue

            bob  = (math.sin(i.bob_phase + i.age * DROP_BOBSPEED) + 1.0) * DROP_BOBHEIGHT + 0.2
            idef = REGISTRY.get(i.itemId)
            isb  = idef and idef.is_block

            if isb:
                self.prog['scale'].value = bsc
                anims  = getanims()
                n = anims.blockanimtext(i.itemId)

                if n and self.text_meta_atlas:
                    if ctex != 'meta':
                        self.text_meta_atlas.use(0)
                        self.prog['texture0'].value = 0
                        ctex = 'meta'
                    uvs = self.animblockuvs(n)
                else:
                    if ctex != 'block':
                        self.texture.use(0)
                        self.prog['texture0'].value = 0
                        ctex = 'block'
                    uvs = self.blockuvs(i.itemId)

                self.uv_buf.write(uvs.tobytes())
                
                

                self.prog['item_pos'].write(i.pos.tobytes())
                self.prog['rotation'].value   = i.rot
                self.prog['bob_offset'].value = bob
                self.prog['tint'].write(np.array(i.tint, dtype='f4').tobytes())
                self.prog['tint_mode'].value  = i.tint_mode

                self.vao.render(moderngl.TRIANGLES)
                
                
                
                
            else:
                self.prog['scale'].value = ssc
                spr = self.spritevao(i.itemId)
                
                if not spr:
                    continue
                    
                    
                    

                if ctex != 'item':
                    self.text_item.use(0)
                    self.prog['texture0'].value = 0
                    ctex = 'item'
                    
                    

                self.prog['item_pos'].write(i.pos.tobytes())
                self.prog['rotation'].value   = i.rot
                self.prog['bob_offset'].value = bob
                self.prog['tint'].write(np.array(i.tint, dtype='f4').tobytes())
                self.prog['tint_mode'].value  = i.tint_mode
                
                

                spr['vao'].render(moderngl.TRIANGLES)
                
                

        self.ctx.disable(moderngl.BLEND)
        
        
        
        
        
        
        

    def itemcount(self):
        return len(self.items)

    def clear(self):
        self.items.clear()
        
        

    def release(self):
        for i in [self.vbo, self.uv_buf, self.norm_vbo, self.vao, self.prog]:
            i.release()
        for i in self.sprcache.values():
            if i:
                i['vao'].release();    i['vbo'].release()
                i['uv_vbo'].release(); i['norm_vbo'].release()
        if self.text_item and self.text_item != self.texture:
            self.text_item.release()
        if self.text_meta_atlas:
            self.text_meta_atlas.release()
