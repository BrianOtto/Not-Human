import shaders
import numpy as np
import moderngl
import math





class HeldItemRenderer:
    ARM_H   = 0.75
    B_SCALE = 0.3
    I_SCALE = 0.7

    def __init__(self, ctx, iem):
        self.ctx = ctx
        self.iem = iem

        self.prog = ctx.program(
            vertex_shader=shaders.load("held.vert"),
            fragment_shader=shaders.load("held.frag"),
        )

        # cube VAO -> own UV buffer, shared vert/norm buffers
        self.cuvbuf = ctx.buffer(reserve=self.iem.uv_buf.size)
        self.cvao   = ctx.vertex_array(self.prog, [
            (self.iem.vbo,      '3f', 'in_pos'),
            (self.cuvbuf,            '2f', 'in_uv'),
            (self.iem.norm_vbo, '3f', 'in_norm'),
        ])

        # sprite VAOs -> created on demand
        self.svaos = {}
        
        
        

    def spritevao(self, itemId):
        if itemId in self.svaos:
            return self.svaos[itemId]

        sprite = self.iem.spritevao(itemId)
        if not sprite:
            self.svaos[itemId] = None
            return None

        vao = self.ctx.vertex_array(self.prog, [
            (sprite['vbo'],      '3f', 'in_pos'),
            (sprite['uv_vbo'],   '2f', 'in_uv'),
            (sprite['norm_vbo'], '3f', 'in_norm'),
        ])
        
        self.svaos[itemId] = vao
        return vao
        
        
        
        

    def render(self, mvp, p, sun_dir=None):
        slot = p._slot
        if slot < 0 or slot >= 9: return

        stack = p.inv.slots[slot]
        if stack is None: return

        idef   = stack.item
        itemId = idef.itemId

        # l_arm / l_arm_z = visual right arm (part 3)
        _, l_arm, _, _, _, l_arm_z = p.animangles()

        prog = self.prog
        prog['mvp'].write(mvp.astype('f4').tobytes())
        prog['player_pos'].write(p.getpos().astype('f4').tobytes())
        prog['byaw'].value = p.byaw
        prog['arm_angle'].value = l_arm
        prog['arm_z_angle'].value = l_arm_z
        prog['crouch'].value = p._smthcrouch

        if sun_dir is not None:
            prog['sun_dir'].write(sun_dir.astype('f4').tobytes())

        tint   = self.iem.TINT_MAP.get(itemId, (1.0, 1.0, 1.0))
        tmode  = self.iem.TINT_MODE_MAP.get(itemId, self.iem.TINT_MODE_ALL)
        prog['tint'].write(np.array(tint, dtype='f4').tobytes())
        prog['tint_mode'].value = tmode

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        
        
        

        if idef.is_block:
            prog['scale'].value = self.B_SCALE
            prog['item_yaw'].value   = math.radians(-45.0)  # MC-style ~45° tilt
            prog['item_pitch'].value = 0.0
            prog['item_roll'].value  = 0.0
            prog['hand_offset'].write(np.array([0.0, -self.ARM_H + 0.05, 0.12], dtype='f4').tobytes())
            self.iem.texture.use(0)
            prog['texture0'].value = 0
            uvs = self.iem.blockuvs(itemId)
            self.cuvbuf.write(uvs.tobytes())
            self.cvao.render(moderngl.TRIANGLES)
            
        else:
            prog['scale'].value = self.I_SCALE
            prog['item_yaw'].value   = math.radians(90.0)   # edge forward
            prog['item_pitch'].value = 0.0
            prog['item_roll'].value  = math.radians(-45.0)
            prog['hand_offset'].write(np.array([0.0, -self.ARM_H + 0.1, 0.28], dtype='f4').tobytes())
            vao = self.spritevao(itemId)
            
            if vao:
                self.iem.text_item.use(0)
                prog['texture0'].value = 0
                vao.render(moderngl.TRIANGLES)
                
                

        self.ctx.disable(moderngl.BLEND)
        
        
        
        
        
        

    def remoterender(self, mvp, pos, yaw, pitch, itemId, arm_angle, sun_dir=None, crouch=0.0):
        from items.registry import REGISTRY
        if not REGISTRY.exists(itemId):
            return
            
        idef = REGISTRY.get(itemId)

        prog = self.prog
        prog['mvp'].write(mvp.astype('f4').tobytes())
        prog['player_pos'].write(pos.astype('f4').tobytes())
        prog['byaw'].value = yaw
        prog['arm_angle'].value = arm_angle
        prog['arm_z_angle'].value = 0.0
        prog['crouch'].value = crouch

        if sun_dir is not None:
            prog['sun_dir'].write(sun_dir.astype('f4').tobytes())

        tint  = self.iem.TINT_MAP.get(itemId, (1.0, 1.0, 1.0))
        tmode = self.iem.TINT_MODE_MAP.get(itemId, self.iem.TINT_MODE_ALL)
        prog['tint'].write(np.array(tint, dtype='f4').tobytes())
        prog['tint_mode'].value = tmode
        

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        
        

        if idef.is_block:
            prog['scale'].value      = self.B_SCALE
            prog['item_yaw'].value   = math.radians(-45.0)
            prog['item_pitch'].value = 0.0
            prog['item_roll'].value  = 0.0
            prog['hand_offset'].write(np.array([0.0, -self.ARM_H + 0.05, 0.12], dtype='f4').tobytes())
            self.iem.texture.use(0)
            prog['texture0'].value = 0
            uvs = self.iem.blockuvs(itemId)
            self.cuvbuf.write(uvs.tobytes())
            self.cvao.render(moderngl.TRIANGLES)
            
        else:
            prog['scale'].value      = self.I_SCALE
            prog['item_yaw'].value   = math.radians(90.0)
            prog['item_pitch'].value = 0.0
            prog['item_roll'].value  = math.radians(-45.0)
            prog['hand_offset'].write(np.array([0.0, -self.ARM_H + 0.1, 0.28], dtype='f4').tobytes())
            vao = self.spritevao(itemId)
            
            if vao:
                self.iem.text_item.use(0)
                prog['texture0'].value = 0
                vao.render(moderngl.TRIANGLES)

        self.ctx.disable(moderngl.BLEND)
        
        

    def release(self):
        for vao in self.svaos.values():
            if vao: vao.release()
        self.cvao.release()
        self.cuvbuf.release()
        self.prog.release()
        



















