import numpy as np
import moderngl
import pygame
import shaders


class MiniInvModel:
    LEG_H    = 0.75
    BODY_H   = 0.75
    HEAD_SZ  = 0.5
    PLAYER_H = LEG_H + BODY_H + HEAD_SZ
    
    def __init__(self, ctx, pmodel):
        self.ctx = ctx
        self.pmodel = pmodel
        
        self.prog = ctx.program(
            vertex_shader   = shaders.load("inv.vert"),
            fragment_shader = shaders.load("inv.frag")
        )
        
        self.vao = ctx.vertex_array(self.prog, [
            (
                pmodel.model.vbo,
                '3f 2f 3f 1f', 
                'in_pos', 'in_uv', 'in_norm', 
                'in_part_id'
            ),
        ])
        
        self.yaw = 160.0
        self.pitch = 0.0
        
    def calcrot(self, mx, my, cx, cy, w, h):
        dx = mx - cx
        dy = my - cy

        # nx/ny = norm mous off [-1, 1] -> yaw/pitch
        nx = np.clip(dx / (w * 0.8), -1.0, 1.0)
        ny = np.clip(dy / (h * 0.8), -1.0, 1.0)

        yaw   = 180.0 + nx * 60.0
        pitch = -ny * 30.0

        return yaw, pitch
        
        
        
    
    def render(self, screen_sz, inv_ox, inv_oy, inv_scale, mouse_pos=None):
        tcx, tcy = 51, 45
        tw, th   = 60, 80

        mcx = inv_ox + tcx * inv_scale
        mcy = inv_oy + tcy * inv_scale
        mw  = tw * inv_scale
        mh  = th * inv_scale

        if mouse_pos:
            self.yaw, self.pitch = self.calcrot(
                mouse_pos[0], mouse_pos[1], 
                mcx, mcy, mw, mh
            )

        ms = (mh / screen_sz[1]) * 0.75

        # ndc position of model center
        nx = (mcx / screen_sz[0]) * 2.0 - 1.0
        ny = 1.0 - (mcy / screen_sz[1]) * 2.0

        aspect = 1.0 / (screen_sz[0] / screen_sz[1])

        # scale /aspect + translate -> ndc slot pos
        mvp = np.array([
            [aspect, 0.0, 0.0, 0.0],
            [0.0,    1.0, 0.0, 0.0],
            [0.0,    0.0, 0.5, 0.0],
            [nx,     ny,  0.0, 1.0]
        ], dtype='f4')
        
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)

        self.pmodel.skin_tex.use(0)

        self.prog['mvp'].write(mvp.astype('f4').tobytes())
        self.prog['model_yaw'].value   = self.yaw
        self.prog['model_pitch'].value = -self.pitch
        self.prog['model_scale'].value = ms
        self.prog['skin_texture'].value = 0

        self.vao.render(moderngl.TRIANGLES)

        # restor backface culling
        self.ctx.enable(moderngl.CULL_FACE)
    
    def release(self):
        self.vao.release()
