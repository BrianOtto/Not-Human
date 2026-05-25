import pygame
import moderngl
import numpy as np
import shaders
from config import SCL_HUD, FONTPATH, SCL_FONT
from ui.bfont import Font
from world.animation import getanims
from world.isorender import get_itemicon_anim
import _respath



class HUDManager:
    def __init__(self, ctx, screen_sz=(1280, 720)):
        self.ctx         = ctx
        self.screen_sz   = screen_sz
        self.scale       = SCL_HUD
        self.font_scale  = SCL_FONT

        self.bfont = Font(FONTPATH, scale=SCL_HUD)

        self.ico_y     = 46
        self.cross_pos = (0, 46)
        self.cross_sz  = 16
        self.ico_pivot = (16, 46)
        self.ico_sz    = 9

        self.gui_tex   = pygame.image.load(_respath.text_gui()).convert_alpha()
        self.atlas_tex = pygame.image.load(_respath.atlas_block()).convert_alpha()
        self.items_tex = pygame.image.load(_respath.atlas_items()).convert_alpha()

        self.cachesprites()

        self.prog = shaders.prog(self.ctx, "hud.vert", "hud.frag")

        self.vertices = np.array([
            -1.0, 1.0, 0.0, 0.0, -1.0, -1.0, 0.0, 1.0, 1.0, -1.0, 1.0, 1.0,
            -1.0, 1.0, 0.0, 0.0,  1.0, -1.0, 1.0, 1.0, 1.0,  1.0, 1.0, 0.0
        ], dtype='f4')

        self.vbo = self.ctx.buffer(self.vertices.tobytes())
        self.vao = self.ctx.vertex_array(
            self.prog, [(self.vbo, '2f 2f', 'in_pos', 'in_uv')]
        )

        self.surface = pygame.Surface(screen_sz, pygame.SRCALPHA)
        self.texture = self.ctx.texture(screen_sz, 4)
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)

        self.prev_health   = None
        self.prev_hunger   = None
        self.prev_armor    = None
        self.prev_air      = None
        self.prev_underwater = None
        self.prev_activeslot = None
        self.prev_inventory  = None
        self.texture_valid   = False
        self._dirty_count    = 0
        
        
        


    def resize(self, w, h):
        self.screen_sz    = (w, h)
        self.surface      = pygame.Surface((w, h), pygame.SRCALPHA)
        self.texture.release()
        self.texture      = self.ctx.texture((w, h), 4)
        self.texture.filter = (moderngl.NEAREST, moderngl.NEAREST)
        self.texture_valid = False

    def extracticon(self, col, row):
        x = self.ico_pivot[0] + col * self.ico_sz
        y = self.ico_pivot[1] + row * self.ico_sz
        return self.gui_tex.subsurface(pygame.Rect(x, y, self.ico_sz, self.ico_sz))


    def cachesprites(self):
        s = self.scale
        icon_sz = (self.ico_sz * s, self.ico_sz * s)

        def si(col, row):
            return pygame.transform.scale(self.extracticon(col, row), icon_sz)

        self.ico_heart_bg     = si(0, 0)
        self.ico_heart_full   = si(4, 0)
        self.ico_heart_half   = si(5, 0)
        self.ico_hunger_bg    = si(0, 3)
        self.ico_hunger_full  = si(4, 3)
        self.ico_hunger_half  = si(5, 3)
        self.ico_armor_bg     = si(0, 1)
        self.ico_armor_full   = si(2, 1)
        self.ico_armor_half   = si(1, 1)
        self.ico_bubble_full  = si(0, 2)
        self.ico_bubble_pop   = si(1, 2)
        
        
        

        rc  = self.gui_tex.subsurface(pygame.Rect(
            self.cross_pos[0], self.cross_pos[1],
            self.cross_sz, self.cross_sz
        ))
        
        csz = self.cross_sz * s
        self.ico_cross = pygame.transform.scale(rc, (csz, csz))

        hw, hh = 182, 22
        self._icon_hotbar = pygame.transform.scale(
            self.gui_tex.subsurface(pygame.Rect(0, 0, hw, hh)),
            (hw * s, hh * s)
        )
        self._icon_selection = pygame.transform.scale(
            self.gui_tex.subsurface(pygame.Rect(0, 22, 24, 24)),
            (24 * s, 24 * s)
        )


    def processfoliage(self, icon, size):
        sc = pygame.transform.scale(icon, (size, size))
        p  = sc.convert_alpha()
        tint = pygame.Surface(p.get_size(), pygame.SRCALPHA)
        tint.fill((72, 181, 24, 255))
        p.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        return p
        
        


    def snapinv(self, p):
        inv = p.inv
        out = []
        for i in range(9):
            st = inv.slots[i]
            out.append((st.item.itemId, st.count) if st else None)
        return tuple(out)

        """
        elif isinstance(inv, list):
            out = []
            for i in range(min(9, len(inv))):
                it = inv[i]
                if it is None: out.append(None)
                elif isinstance(it, dict): out.append((it.get('texture_uv', (0, 0)), it.get('count', 1)))
                else: out.append((0, 1))
            return tuple(out)
        """
        
        
        


    def isdirty(self, p):
        # t0 = time.perf_counter()
        health = p.health
        hunger = p.hunger
        armor  = p.armor
        air    = p.air
        iuw    = p._underwater
        _slot  = p._slot
        snap   = self.snapinv(p)

        # anim block == dirty
        anims = getanims()
        for i in range(9):
            st = p.inv.slots[i]
            if st and st.item.is_block and anims.blockanimtext(st.item.itemId):
                return True

        changed = (
            health != self.prev_health or
            hunger != self.prev_hunger or
            armor  != self.prev_armor  or
            air    != self.prev_air    or
            iuw    != self.prev_underwater or
            _slot  != self.prev_activeslot or
            snap   != self.prev_inventory or
            not self.texture_valid
        )

        self.prev_health     = health
        self.prev_hunger     = hunger
        self.prev_armor      = armor
        self.prev_air        = air
        self.prev_underwater = iuw
        self.prev_activeslot = _slot
        self.prev_inventory  = snap
        # print(changed)
        return changed
        
    """
    def draw_debug(self, p):
        s   = self.scale
        lns = [
            f"pos:   {p.pos[0]:.2f} {p.pos[1]:.2f} {p.pos[2]:.2f}",
            f"vel:   {p.vel[0]:.2f} {p.vel[1]:.2f} {p.vel[2]:.2f}",
            f"gnd:   {p.on_ground}   fly: {p.fly}",
            f"chunk: {p.chunkpos(16)}",
        ]
        y = 2 * s
        for i in lns:
            t = self.bfont.render(i, False, (255, 255, 0))
            self.surface.blit(t, (2 * s, y))
            y += t.get_height() + s
    """


    def render(self, p):
        # t0 = time.perf_counter()
        if not self.isdirty(p):
            self.texture.use(0)
            self.prog['hud_texture'].value = 0
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            self.ctx.disable(moderngl.DEPTH_TEST)
            self.vao.render(moderngl.TRIANGLES)
            self.ctx.enable(moderngl.DEPTH_TEST)
            self.ctx.disable(moderngl.BLEND)
            return
            
            

        self.surface.fill((0, 0, 0, 0))

        s  = self.scale
        hw, hh = 182, 22
        dw = hw * s
        dh = hh * s
        dx = (self.screen_sz[0] - dw) // 2
        dy = self.screen_sz[1] - dh - 10

        self.surface.blit(self._icon_hotbar, (dx, dy))

        sx, sy = 3, 3
        sstep  = 20
        inv    = p.inv
        
        

        for i in range(9):
            count, hitem = 0, False
            col, row     = 0, 0
            bgtex        = self.atlas_tex

            st = inv.slots[i]
            if st:
                hitem = True
                count = st.count
                col, row = st.item.texture_uv
                if st.item.atlas == 'items': bgtex = self.items_tex

            """
            elif isinstance(inv, list) and i < len(inv):
                it = inv[i]
                hitem = True
                if isinstance(it, dict):
                    count    = it.get('count', 1)
                    col, row = it.get('texture_uv', (0, 0))
            """
            

            if hitem:
                idef = inv.slots[i]
                idef = idef.item if idef else None

                isz  = int(16 * s)
                if idef: icon = get_itemicon_anim(idef, self.atlas_tex, self.items_tex, isz)
                else:    icon = bgtex.subsurface(pygame.Rect(col * 16, row * 16, 16, 16))

                sc = pygame.transform.scale(icon, (isz, isz)) if icon.get_size() != (isz, isz) else icon

                ix = dx + (sx + i * sstep) * s
                iy = dy + sy * s
                self.surface.blit(sc, (ix, iy))

                if count > 1:
                    txt    = self.bfont.render(str(count), False, (255, 255, 255))
                    tw, th = txt.get_size()
                    soff   = self.bfont.scale
                    self.surface.blit(txt, (ix + isz - tw + 2*soff, iy + isz - th + 2*soff))

        slot = p._slot
        # print(slot)
        self.surface.blit(self._icon_selection, (dx + (-1 + slot * 20) * s, dy + -1 * s))

        csz = self.cross_sz * s
        self.surface.blit(self.ico_cross, (
            (self.screen_sz[0] - csz) // 2,
            (self.screen_sz[1] - csz) // 2
        ))
        
        
        

        # stats
        isz   = self.ico_sz * s
        istep = (self.ico_sz - 1) * s

        health = p.health
        hty    = dy - isz - 2 * s
        htx    = dx + s
        
        
        
        
        

        for i in range(10):
            hx = htx + i * istep
            self.surface.blit(self.ico_heart_bg, (hx, hty))
            hp = health - i * 2
            if hp >= 2:   self.surface.blit(self.ico_heart_full, (hx, hty))
            elif hp == 1: self.surface.blit(self.ico_heart_half, (hx, hty))

        hunger = p.hunger
        hux    = dx + dw - s - isz

        for i in range(10):
            hx = hux - i * istep
            self.surface.blit(self.ico_hunger_bg, (hx, hty))
            hu = hunger - i * 2
            if hu >= 2:   self.surface.blit(self.ico_hunger_full, (hx, hty))
            elif hu == 1: self.surface.blit(self.ico_hunger_half, (hx, hty))

        armor = p.armor
        if armor > 0:
            ary = hty - isz - s
            for i in range(10):
                ax = htx + i * istep
                self.surface.blit(self.ico_armor_bg, (ax, ary))
                ar = armor - i * 2
                if ar >= 2:   self.surface.blit(self.ico_armor_full, (ax, ary))
                elif ar == 1: self.surface.blit(self.ico_armor_half, (ax, ary))
                
                
                

        air   = p.air
        mair  = p.max_air
        undrw = p._underwater

        if air < mair or undrw:
            buy  = hty - isz - s
            aper = mair // 10
            for i in range(10):
                bx = hux - i * istep
                a  = air - i * aper
                if a >= aper:  self.surface.blit(self.ico_bubble_full, (bx, buy))
                elif a > 0:    self.surface.blit(self.ico_bubble_pop,  (bx, buy))
                
                

        self.texture.write(pygame.image.tostring(self.surface, "RGBA", False))
        self.texture_valid = True

        self.texture.use(0)
        self.prog['hud_texture'].value = 0
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ctx.disable(moderngl.DEPTH_TEST)
        self.vao.render(moderngl.TRIANGLES)
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.BLEND)
















