import pygame
from items.registry import REGISTRY, ItemStack
from world.isorender import get_itemicon_anim


class ItemBrowser:
    def __init__(self):
        self.cell_size = 18
        self.margin    = 4

        self.cols = 9
        self.rows = 1
        self.x    = 0
        self.y    = 0
        self.width  = 0
        self.height = 0
        self.scale  = 1

        self.query    = ""
        self._onsearch = False

        self.scroll = 0
        self.per_pg    = 0
        self.fitems = []

        self.hovi       = -1
        self._heldstack = None

        self.grid_x   = 0
        self.grid_y   = 0
        self.search_x = 0
        self.search_y = 0
        self.search_w = 0
        self.search_h = 0
        self.page_x   = 0
        self.page_y   = 0

        self.refresh()


    def refresh(self):
        self.fitems = REGISTRY.search(self.query) if self.query else REGISTRY.getall()
        ms = self.maxscroll()
        if self.scroll > ms: self.scroll = max(0, ms)


    def maxscroll(self):
        return (self.maxpages() - 1) * self.rows

    def visitems(self):
        start = self.scroll * self.cols
        return self.fitems[start:start + self.cols * self.rows]

    def maxpages(self):
        tr = (len(self.fitems) + self.cols - 1) // self.cols
        tp = (tr + self.rows - 1) // self.rows if self.rows > 0 else 1
        return max(1, tp)
        
        
        

    @property
    def page(self):
        return self.scroll // self.rows if self.rows > 0 else 0

    @page.setter
    def page(self, val):
        self.scroll = val * self.rows
        

    def next_page(self): self.scroll = min(self.scroll + self.rows, self.maxscroll())
    def prev_page(self): self.scroll = max(0, self.scroll - self.rows)







    def setpos(self, inv_x, inv_y, inv_w, inv_h, scale, screen_sz=None):
        self.scale = scale
        
        if screen_sz is None: screen_sz = (1280, 720)
        sw, sh = screen_sz
        cpx  = int(self.cell_size * scale)
        marg = self.margin * scale
        srh  = int(16 * scale)
        pth  = int(14 * scale)

        avw       = sw - (inv_x + inv_w) - marg * 2
        self.cols = max(1, int(avw / cpx))

        gtop      = marg + pth
        gbot      = sh - srh - marg * 2
        self.rows = max(1, int((gbot - gtop) / cpx))
        self.per_pg  = self.cols * self.rows

        gw          = self.cols * cpx
        self.width  = gw + marg * 2
        self.x      = sw - self.width
        self.y      = 0
        self.height = sh

        self.grid_x   = self.x + marg
        self.grid_y   = self.y + gtop
        self.page_x   = self.grid_x
        self.page_y   = self.y + marg

        self.search_x = self.x + marg
        self.search_y = self.grid_y + self.rows * cpx + marg
        self.search_w = gw
        self.search_h = srh
        
        
        


    def update(self, mx, my):
        self.hovi = -1
        if not self.ingrid(mx, my): return
        
        lx  = (mx - self.grid_x) / self.scale
        ly  = (my - self.grid_y) / self.scale
        col = int(lx / self.cell_size)
        row = int(ly / self.cell_size)
        
        if 0 <= col < self.cols and 0 <= row < self.rows:
            idx = row * self.cols + col
            if idx < len(self.visitems()): self.hovi = idx
            
            


    def ingrid(self, mx, my):
        gw = self.cols * self.cell_size * self.scale
        gh = self.rows * self.cell_size * self.scale
        return (
            self.grid_x <= mx < self.grid_x + gw and
            self.grid_y <= my < self.grid_y + gh
        )

    def inpanel(self, mx, my):
        return (
            self.x <= mx < self.x + self.width and
            self.y <= my < self.y + self.height
        )

    def insearch(self, mx, my):
        return (
            self.search_x <= mx < self.search_x + self.search_w and
            self.search_y <= my < self.search_y + self.search_h
        )


    def onclick(self, mx, my, button, ctrl_held=False):
        if not self.inpanel(mx, my):
            self._onsearch = False
            return False
            

        if self.insearch(mx, my):
            self._onsearch = True
            return True
            
            
            

        self._onsearch = False

        if self.ingrid(mx, my) and self.hovi >= 0:
            items = self.visitems()
            if self.hovi < len(items):
                idef = items[self.hovi]
                if   button == 1: self._heldstack = ItemStack(idef, idef.max_stack)
                elif button == 3: self._heldstack = ItemStack(idef, 1)
                return True

        return True


    def onscroll(self, direction):
        if direction > 0: self.scroll = max(0, self.scroll - 1)
        else: self.scroll = min(self.maxscroll(), self.scroll + 1)


    def onkey(self, ev):
        if not self._onsearch: return False
        if   ev.key == pygame.K_ESCAPE:    self._onsearch = False; return True
        elif ev.key == pygame.K_BACKSPACE: self.query = self.query[:-1]; self.refresh(); return True
        elif ev.key == pygame.K_RETURN:    self._onsearch = False; return True
        return False
        
        

    def ontext(self, text):
        if not self._onsearch: return False
        self.query += text
        self.refresh()
        return True








    def render(self, surface, bfont, atlas, items_atlas):
        scale = self.scale
        cpx   = int(self.cell_size * scale)

        page = self.scroll // self.rows + 1 if self.rows > 0 else 1
        mp   = self.maxpages()
        ptxt = bfont.render(f"[N] {page}/{mp} [M]", False, (200, 200, 200))
        px   = self.grid_x + (self.cols * cpx - ptxt.get_width()) // 2
        surface.blit(ptxt, (px, self.page_y))

        visible = self.visitems()

        for i, j in enumerate(visible):
            col = i % self.cols
            row = i // self.cols
            cx  = self.grid_x + col * cpx
            cy  = self.grid_y + row * cpx

            if i == self.hovi:
                hl = pygame.Surface((cpx, cpx), pygame.SRCALPHA)
                hl.fill((255, 255, 255, 60))
                surface.blit(hl, (cx, cy))

            if atlas or items_atlas:
                icsz   = int(16 * scale)
                icon   = get_itemicon_anim(j, atlas, items_atlas, icsz)
                scaled = pygame.transform.scale(icon, (icsz, icsz)) if icon.get_width() != icsz else icon
                surface.blit(scaled, (cx + 1, cy + 1))
                
                

        srect = pygame.Rect(self.search_x, self.search_y, self.search_w, self.search_h)
        pygame.draw.rect(surface, (0, 0, 0, 140), srect)
        bcol = (200, 200, 200) if self._onsearch else (100, 100, 100)
        pygame.draw.rect(surface, bcol, srect, 1)
        

        if self.query:
            display = self.query + ("_" if self._onsearch else "")
            color   = (255, 255, 255)
            
        else:
            display = "_" if self._onsearch else "Search..."
            color   = (255, 255, 255) if self._onsearch else (150, 150, 150)

        txt = bfont.render(display, False, color)
        ty  = self.search_y + (self.search_h - txt.get_height()) // 2
        surface.blit(txt, (self.search_x + 4 * scale, ty))

        if 0 <= self.hovi < len(visible):
            self.rendertooltip(surface, bfont, visible[self.hovi], pygame.mouse.get_pos())




    def applytint(self, icon, tint_color):
        out  = icon.copy().convert_alpha()
        tint = pygame.Surface(out.get_size(), pygame.SRCALPHA)
        tint.fill((*tint_color, 255))
        out.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        return out



    def rendertooltip(self, surface, bfont, item, pos):
        mx, my = pos
        nsurf = bfont.render(item.nm, False, (255, 255, 255))
        csurf = bfont.render(item.category, False, (150, 150, 200))

        tw = max(nsurf.get_width(), csurf.get_width()) + 8
        th = nsurf.get_height() + csurf.get_height() + 8
        tx = mx + 12
        ty = my - th - 4

        sw, sh = surface.get_size()
        if tx + tw > sw: tx = mx - tw - 12
        if ty < 4: ty = my + 16

        bg = pygame.Rect(tx, ty, tw, th)
        pygame.draw.rect(surface, (32, 0, 64, 230), bg)
        pygame.draw.rect(surface, (80, 40, 120), bg, 2)
        surface.blit(nsurf, (tx + 4, ty + 2))
        surface.blit(csurf, (tx + 4, ty + 2 + nsurf.get_height() + 2))
