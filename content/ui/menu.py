import os
import pygame
import moderngl
import numpy as np
import time
import shaders

from config import SCL_HUD, FONTPATH, CHAT_MAX, CHAT_FADETIME, CHAT_LIFETIME, SCL_FONT
from ui.bfont import Font
from ui.invmodel import MiniInvModel
from ui.browser import ItemBrowser
import _respath
from world.isorender import get_itemicon_anim

CTRLS_TXT = [
    "[Q] drop",
    "[CTRL+Q] drop stack",
    "[DEL] delete slot",
    "[SHIFT+CTRL+DEL] clear all",
    "[N]/[M] browser page",
]




class UIManager:
    def __init__(self, ctx, screen_sz=(1280, 720)):
        self.ctx = ctx
        self.screen_sz = screen_sz

        self.bfont     = Font(FONTPATH, scale=SCL_FONT)
        self.item_font = Font(FONTPATH, scale=SCL_HUD)

        self.prog = shaders.prog(self.ctx, "ui.vert", "ui.frag")

        verts = np.array([
            -1.0, -1.0, 0.0, 0.0, 1.0, -1.0, 1.0, 0.0, 1.0, 1.0, 1.0, 1.0,
            -1.0, -1.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0, -1.0, 1.0, 0.0, 1.0
        ], dtype='f4')

        self.vbo = self.ctx.buffer(verts.tobytes())
        self.vao = self.ctx.vertex_array(
            self.prog, [(self.vbo, '2f 2f', 'in_pos', 'in_uv')]
        )

        self.texture = self.ctx.texture(screen_sz, 4)
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.surface = pygame.Surface(screen_sz, pygame.SRCALPHA)

        self.chat = []
        self.max_chat  = CHAT_MAX
        self.fade = CHAT_FADETIME
        self.life = CHAT_LIFETIME

        self.inv_surf = pygame.image.load(_respath.text_inv()).convert_alpha()
        self.inv_w, self.inv_h = 176, 166
        self.inv_tex = self.ctx.texture(
            self.inv_surf.get_size(), 4,
            pygame.image.tostring(self.inv_surf, "RGBA", True)
        )
        self.inv_tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

        self.atlas = pygame.image.load(_respath.atlas_block()).convert_alpha()
        
        

        ipath = _respath.atlas_items()
        if os.path.exists(ipath):
            self.items_atlas = pygame.image.load(ipath).convert_alpha()
        else:
            self.items_atlas = None

        self.inv_model = None
        self.invbrwser = ItemBrowser()
        
        
        
        

    def itemicon(self, u, v, size=16, atlas_type="blocks"):
        source = self.atlas if atlas_type == "blocks" else self.items_atlas

        if not source:
            s = pygame.Surface((size, size))
            s.fill((255, 0, 255))
            return s

        aw, ah = source.get_width(), source.get_height()
        rx, ry = u * 16, v * 16

        if rx + 16 > aw or ry + 16 > ah:
            s = pygame.Surface((size, size))
            s.fill((255, 0, 255))
            return s

        return source.subsurface(pygame.Rect(rx, ry, 16, 16))
        
        
        
        

    def resize(self, w, h):
        self.screen_sz = (w, h)
        self.surface   = pygame.Surface((w, h), pygame.SRCALPHA)
        self.texture.release()
        self.texture = self.ctx.texture((w, h), 4)
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def chatmsg(self, msg, color=(255, 255, 255)):
        self.chat.append((msg, color, time.time()))
        if len(self.chat) > self.max_chat * 2:
            self.chat = self.chat[-self.max_chat:]

    def render(
            self, stats, 
            nametags=None, keybinds=None, renderinv=False, 
            inv=None, pmodel=None, chat_input=None,
            tablist=None
    ):
        
        self.surface.fill((0, 0, 0, 0))

        yoff = 5
        xoff = 5
        lh   = self.bfont.get_height() + 2


        lines = []
        if renderinv: lines = CTRLS_TXT
        elif isinstance(stats, dict):
            for k, v in stats.items():
                lines.append(f"{k}: {v}")
                
        elif isinstance(stats, list): lines = stats
        else: lines = [str(stats)]
        
        

        for i in lines:
            txt = self.bfont.render(i, False, (255, 255, 255))
            w, h = txt.get_size()
            pygame.draw.rect(
                self.surface, (100, 100, 100, 160), 
                pygame.Rect(xoff - 2, yoff - 2, w + 4, h + 4)
            )
            self.surface.blit(txt, (xoff, yoff))
            yoff += lh
            
            

        if keybinds:
            yoff = 5
            for i in keybinds:
                txt = self.bfont.render(i, False, (255, 255, 255))
                w, h = txt.get_size()
                x = self.screen_sz[0] - w - 5
                pygame.draw.rect(
                    self.surface, (100, 100, 100, 160), 
                    pygame.Rect(x - 2, yoff - 2, w + 4, h + 4)
                )
                self.surface.blit(txt, (x, yoff))
                yoff += lh
                
                

        now    = time.time()
        chat_x = 5
        chat_y = self.screen_sz[1] - 5
        
        
        
        
        

        if chat_input is not None:
            txt = self.bfont.render(chat_input + "_", False, (255, 255, 255))
            w, h = txt.get_size()
            bgh   = h + 4
            bgrct = pygame.Rect(chat_x - 2, chat_y - h - 2, max(w + 4, 300), bgh)
            pygame.draw.rect(self.surface, (0, 0, 0, 180), bgrct)
            pygame.draw.rect(self.surface, (100, 100, 100, 255), bgrct, 1)
            self.surface.blit(txt, (chat_x, chat_y - h))
            chat_y -= (bgh + 2)
            
            

        vis = []
        if chat_input is not None:
            for msg, color, ts in self.chat:
                vis.append((msg, color, 255))
                
        else:
            for msg, color, ts in self.chat:
                age = now - ts
                if age < self.life:
                    if age > self.fade:
                        alpha = max(0, int(
                            255 * (1.0 - (age - self.fade) / (self.life - self.fade))
                            
                        ))
                        
                        
                    else: alpha = 255
                    vis.append((msg, color, alpha))
                    
                    
                    

        for msg, color, alpha in reversed(vis[-self.max_chat:]):
            txt = self.bfont.render(msg, False, color)
            w, h = txt.get_size()
            fade = pygame.Surface((w, h), pygame.SRCALPHA)
            fade.blit(txt, (0, 0))
            fade.set_alpha(alpha)
            
            pygame.draw.rect(
                self.surface, (0, 0, 0, min(alpha // 2, 100)), 
                pygame.Rect(chat_x - 2, chat_y - h - 2, w + 4, h + 4)
            )
            
            self.surface.blit(fade, (chat_x, chat_y - h))
            chat_y -= h + 2

        if nametags:
            for sx, sy, nm in nametags:
                if 0 <= sx < self.screen_sz[0] and 0 <= sy < self.screen_sz[1]:
                    txt = self.bfont.render(nm, False, (255, 255, 255))
                    w, h = txt.get_size()
                    tx, ty = int(sx - w / 2), int(sy - h)
                    
                    for dx in [-1, 0, 1]:
                        for dy in [-1, 0, 1]:
                            if dx != 0 or dy != 0:
                                self.surface.blit(
                                    self.bfont.render(nm, False, (0, 0, 0, 200)), 
                                    (tx + dx, ty + dy)
                                )
                                
                                
                    self.surface.blit(txt, (tx, ty))

        if tablist:
            self.rendtab(tablist)

        ix, iy, iscl = 0, 0, SCL_HUD
        
        
        
        

        if renderinv:
            dim = pygame.Surface(self.screen_sz, pygame.SRCALPHA)
            dim.fill((0, 0, 0, 150))
            self.surface.blit(dim, (0, 0))

            scale = SCL_HUD
            iscl  = scale
            w, h  = self.inv_w * scale, self.inv_h * scale
            ix    = (self.screen_sz[0] - w) // 2
            iy    = (self.screen_sz[1] - h) // 2

            sub = self.inv_surf.subsurface(pygame.Rect(0, 0, self.inv_w, self.inv_h))
            self.surface.blit(pygame.transform.scale(sub, (int(w), int(h))), (ix, iy))

            if inv:
                self.rendinvitems(inv, ix, iy, scale)

            self.invbrwser.setpos(ix, iy, w, h, scale, self.screen_sz)
            mx, my = pygame.mouse.get_pos()
            self.invbrwser.update(mx, my)
            self.invbrwser.render(self.surface, self.bfont, self.atlas, self.items_atlas)

            if inv and inv._held:
                self.rendheld(inv._held, mx, my, scale)

        self.texture.write(pygame.image.tostring(self.surface, "RGBA", True))

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ctx.disable(moderngl.DEPTH_TEST)

        self.texture.use(0)
        self.prog['ui_texture'].value = 0
        self.vao.render(moderngl.TRIANGLES)

        if renderinv and pmodel:
            if self.inv_model is None:
                self.inv_model = MiniInvModel(self.ctx, pmodel)
            self.inv_model.render(self.screen_sz, ix, iy, iscl, pygame.mouse.get_pos())
            
            

        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.BLEND)
        
        
        
        
        

    def geticon(self, item, size):
        sz   = int(size)
        icon = get_itemicon_anim(item, self.atlas, self.items_atlas, sz)
        return pygame.transform.scale(icon, (sz, sz)) if icon.get_width() != sz else icon
        
        

    def rendheld(self, stack, mx, my, scale):
        sz   = 16 * scale
        icon = self.geticon(stack.item, sz)
        self.surface.blit(icon, (mx - sz/2, my - sz/2))

        if stack.count > 1:
            txt  = self.item_font.render(str(stack.count), False, (255, 255, 255))
            soff = self.item_font.scale
            self.surface.blit( txt, (
                mx + sz/2 - txt.get_width() + 2*soff,
                my + sz/2 - txt.get_height() + 2*soff
            ))
            
            
            

    def rendinvitems(self, inv, inv_x, inv_y, scale):
        mx, my = pygame.mouse.get_pos()
        inv.updatehov(mx, my, inv_x, inv_y, scale)

        for i, (sx, sy) in enumerate(inv.spos):
            scrx = inv_x + sx * scale
            scry = inv_y + sy * scale
            ssz  = 16 * scale
            

            if i == inv._hslot:
                hl = pygame.Surface((int(ssz), int(ssz)), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 80))
                self.surface.blit(hl, (scrx, scry))
                

        for i, j in enumerate(inv.slots):
            if j and i < len(inv.spos):
                sx, sy = inv.spos[i]
                scrx = inv_x + sx * scale
                scry = inv_y + sy * scale
                sz   = 16 * scale

                icon = self.geticon(j.item, sz)
                self.surface.blit(icon, (scrx, scry))

                if j.count > 1:
                    txt  = self.item_font.render(str(j.count), False, (255, 255, 255))
                    soff = self.item_font.scale
                    tx   = scrx + sz - txt.get_width() + 2 * soff
                    ty   = scry + sz - txt.get_height() + 2 * soff
                    self.surface.blit(txt, (tx, ty))
                    
                    

        if inv._hslot >= 0 and inv._held is None:
            hovered = inv.hovitem()
            if hovered:
                nm  = hovered.item.nm
                txt = self.bfont.render(nm, False, (255, 255, 255))
                tw, th = txt.get_size()
                tx  = max(4, min(mx - tw // 2, self.screen_sz[0] - tw - 4))
                ty  = max(4, my - th - 2 * scale)
                pad = 4
                bg  = pygame.Rect(tx - pad, ty - pad, tw + pad * 2, th + pad * 2)
                pygame.draw.rect(self.surface, (32, 0, 64, 230), bg)
                pygame.draw.rect(self.surface, (80, 40, 120, 255), bg, 2)
                self.surface.blit(txt, (tx, ty))


    def rendtab(self, names):
        th  = self.bfont.get_height()
        eh  = th + 2

        y = 10
        for n in names:
            txt = self.bfont.render(n, False, (255, 255, 255))
            tw  = txt.get_width()
            bw  = tw + 2
            bx  = (self.screen_sz[0] - bw) // 2
            pygame.draw.rect(
                self.surface, (0, 0, 0, 120),
                pygame.Rect(bx, y, bw, eh)
            )
            self.surface.blit(txt, (bx + 1, y + 1))
            y += eh












