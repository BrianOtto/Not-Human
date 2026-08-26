import pygame

from lconst import (
    GS, WIN_W,
    ENTRY_H, ICON_SZ, ENTRY_PAD,
    LIST_TOP, LIST_BOT, LIST_ITEM_PAD,
    SS_CELL,
    BTN_SRC_W, BTN_SRC_H, BTN_Y_NORMAL, BTN_Y_HOVER, BTN_H, BTN_BORDER,
    WHITE, GRAY, DGRAY, YELLOW, BLACK
)


def drawgrad(surface, x, y, w, h, top_a, bot_a):
    g = pygame.Surface((w, h), pygame.SRCALPHA)
    for row in range(h):
        a = int(top_a + (bot_a - top_a) * row / max(1, h - 1))
        pygame.draw.line(g, (0, 0, 0, a), (0, row), (w, row))
    surface.blit(g, (x, y))



def pxscale(src, dw, dh):
    sw, sh = src.get_size()
    scaled = pygame.transform.scale(src, (sw * GS, sh * GS))
    ssw, ssh = scaled.get_size()

    if ssw == dw and ssh == dh:
        return scaled

    out = pygame.Surface((dw, dh), src.get_flags(), src)
    for tx in range(0, dw, ssw):
        for ty in range(0, dh, ssh):
            out.blit(scaled, (tx, ty))
            
    return out.subsurface(pygame.Rect(0, 0, dw, dh)).copy()





def nine_slice(src, tw, th):
    sw, sh = src.get_size()
    b   = BTN_BORDER
    sb  = b * GS
    out = pygame.Surface((tw, th), pygame.SRCALPHA)

    mw_src = sw - 2*b;  mw_dst = max(1, tw - 2*sb)
    mh_src = sh - 2*b;  mh_dst = max(1, th - 2*sb)

    pieces = [
        (0,      0,      b,      b,      0,      0,      sb,     sb),
        (b,      0,      mw_src, b,      sb,     0,      mw_dst, sb),
        (sw-b,   0,      b,      b,      tw-sb,  0,      sb,     sb),
        (0,      b,      b,      mh_src, 0,      sb,     sb,     mh_dst),
        (b,      b,      mw_src, mh_src, sb,     sb,     mw_dst, mh_dst),
        (sw-b,   b,      b,      mh_src, tw-sb,  sb,     sb,     mh_dst),
        (0,      sh-b,   b,      b,      0,      th-sb,  sb,     sb),
        (b,      sh-b,   mw_src, b,      sb,     th-sb,  mw_dst, sb),
        (sw-b,   sh-b,   b,      b,      tw-sb,  th-sb,  sb,     sb),
    ]
    
    
    for sx, sy, sw2, sh2, dx, dy, dw, dh in pieces:
        piece = src.subsurface(pygame.Rect(sx, sy, sw2, sh2))
        out.blit(pxscale(piece, max(1, dw), max(1, dh)), (dx, dy))
        
    return out







class Button:
    def __init__(
        self, x, y, w, h,
        text, bfont, widgets, enabled=True
    ):
        self.rect    = pygame.Rect(x, y, w, h)
        self.text    = text
        self.bfont   = bfont
        self.widgets = widgets
        self.enabled = enabled
        self.hovered = False
        self._src    = {}

        for tag, sy in (("on", BTN_Y_NORMAL), ("hi", BTN_Y_HOVER)):
            self._src[tag] = widgets.subsurface(pygame.Rect(0, sy, BTN_SRC_W, BTN_SRC_H))

        norm = widgets.subsurface(pygame.Rect(0, BTN_Y_NORMAL, BTN_SRC_W, BTN_SRC_H)).copy()
        dk   = pygame.Surface((BTN_SRC_W, BTN_SRC_H), pygame.SRCALPHA)
        dk.fill((0, 0, 0, 160))
        norm.blit(dk, (0, 0))
        self._src["off"] = norm

    def _key(self):
        if not self.enabled: return "off"
        return "hi" if self.hovered else "on"

    def update(self, mx, my):
        self.hovered = self.enabled and self.rect.collidepoint(mx, my)
        
        
        

    def draw(self, surf):
        surf.blit(
            nine_slice(
                self._src[self._key()], 
                self.rect.w, self.rect.h
                
            ), self.rect.topleft
        
        )
        col = DGRAY if not self.enabled else (BLACK if self.hovered else BLACK)
        txt = self.bfont.render(self.text, False, col)
        tx  = self.rect.x + (self.rect.w - txt.get_width())  // 2
        ty  = self.rect.y + (self.rect.h - txt.get_height()) // 2
        surf.blit(txt, (tx, ty))
        

    def clk(self, mx, my):
        return self.enabled and self.rect.collidepoint(mx, my)




"""
class ProgressBar:
    def __init__(self, x, y, w, h, color=WHITE):
        self.rect  = pygame.Rect(x, y, w, h)
        self.color = color
        self.val   = 0.0

    def set(self, v): self.val = max(0.0, min(1.0, v))

    def draw(self, surf):
        pygame.draw.rect(surf, DGRAY, self.rect)
        fw = int(self.rect.w * self.val)
        if fw > 0:
            pygame.draw.rect(surf, self.color, (self.rect.x, self.rect.y, fw, self.rect.h))
        pygame.draw.rect(surf, GRAY, self.rect, 1)
"""


class TextInput:
    def __init__(
        self, x, y, w, h, bfont,
        widgets=None, label="", default="", max_len=60
    ):
        self.rect    = pygame.Rect(x, y, w, h)
        self.bfont   = bfont
        self.widgets = widgets
        self.label   = label
        self.text    = default
        self.max_len = max_len
        self.active  = False
        self._blink  = 0
        

        if widgets:
            bg = widgets.subsurface(pygame.Rect(0, BTN_Y_NORMAL, BTN_SRC_W, BTN_SRC_H)).copy()
            dk = pygame.Surface((BTN_SRC_W, BTN_SRC_H), pygame.SRCALPHA)
            dk.fill((0, 0, 0, 160))
            bg.blit(dk, (0, 0))
            self._bg = bg
            
        else:
            self._bg = None




    def draw(self, surf):
        if self.label:
            lbl = self.bfont.render(self.label, False, GRAY)
            surf.blit(lbl, (self.rect.x, self.rect.y - lbl.get_height() - 4))

        if self._bg:
            surf.blit(nine_slice(self._bg, self.rect.w, self.rect.h), self.rect.topleft)
            if self.active:
                pygame.draw.rect(surf, WHITE, self.rect, 2)
                
        else:
            bgc = (60, 60, 80) if self.active else (40, 40, 50)
            bd  = WHITE if self.active else GRAY
            pygame.draw.rect(surf, bgc, self.rect)
            pygame.draw.rect(surf, bd,  self.rect, 2)
            
            

        self._blink = (self._blink + 1) % 60
        cur = "_" if self.active and self._blink < 30 else ""
        txt = self.bfont.render(self.text + cur, False, WHITE)
        ty  = self.rect.y + (self.rect.h - txt.get_height()) // 2
        surf.blit(txt, (self.rect.x + 6, ty))
        
        
        

    def onevent(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(ev.pos)

        if not self.active:
            return None

        if ev.type == pygame.KEYDOWN:
            if   ev.key == pygame.K_BACKSPACE: self.text = self.text[:-1]
            elif ev.key == pygame.K_TAB:       return "tab"
            elif ev.key == pygame.K_RETURN:    return "enter"
            elif ev.key == pygame.K_KP_ENTER:  return "enter"
            
        elif ev.type == pygame.TEXTINPUT:
            if len(self.text) < self.max_len: self.text += ev.text

        return None




class ListWidget:
    def __init__(
        self, bfont, ico_surf, ss_surf,
        icos_surf=None, wd_surf=None
    ):
        self.bfont        = bfont
        self.ico_surf     = ico_surf
        self.ss_surf      = ss_surf
        self.icos_surf    = icos_surf
        self.wd_surf      = wd_surf
        self.items        = []
        self.selected     = -1
        self.scroll       = 0
        self.hovered      = -1
        self.hover_zone   = None
        self.dragging_sb  = False
        self.drag_off     = 0

        self.x = 0
        self.y = LIST_TOP
        self.w = WIN_W
        self.h = LIST_BOT - LIST_TOP

        self.entry_w = 360 * GS
        self.entry_x = (WIN_W - self.entry_w) // 2
        
        
        
        

        self._arrows = {}
        if ss_surf:
            for col, lx, ly in [(3, 3, 5), (2, 3, 20)]:
                for row in range(2):
                    sx = col * SS_CELL + lx
                    sy = row * SS_CELL + ly
                    self._arrows[(col, row)] = ss_surf.subsurface(
                        pygame.Rect(sx, sy, 11, 7)).copy()

            for row in range(2):
                sy = row * SS_CELL
                self._arrows[('play', row)] = ss_surf.subsurface(
                    pygame.Rect(16, sy + 5, 14, 22)).copy()
                    

        self.arrow_w = 11
        self.arrow_h = 7
        self.sb_w    = 8 * GS + 2
        self.sb_x    = self.entry_x + self.entry_w + 4 * GS - 1
        self._sb_src = None

        if wd_surf:
            self._sb_src = wd_surf.subsurface(
                pygame.Rect(0, BTN_Y_NORMAL, BTN_SRC_W, BTN_SRC_H)).copy()





    def set_items(self, items):
        self.items    = list(items)
        self.selected = -1
        self.scroll   = 0



    def _total_h(self):    return LIST_ITEM_PAD + len(self.items) * ENTRY_H
    def _max_scroll(self): return max(0, self._total_h() - self.h)




    def _sb_bar(self):
        if self._total_h() <= self.h: return None
        bh = max(20, int(self.h * self.h / self._total_h()))
        ms = self._max_scroll()
        by = self.y + int(self.scroll / max(1, ms) * (self.h - bh))
        return by, bh


    def update(self, mx, my):
        self.hovered    = -1
        self.hover_zone = None

        if self.dragging_sb:
            sb = self._sb_bar()
            if sb:
                _, bh = sb
                tk  = self.h - bh
                rel = (my - self.drag_off - self.y) / max(1, tk)
                self.scroll = max(0, min(int(rel * self._max_scroll()), self._max_scroll()))
            return
            
            

        if self.x <= mx < self.x + self.w and self.y <= my < self.y + self.h:
            rel_y = my - self.y - LIST_ITEM_PAD + self.scroll
            idx   = rel_y // ENTRY_H

            if 0 <= idx < len(self.items):
                self.hovered = idx
                ey = self.y + LIST_ITEM_PAD + idx * ENTRY_H - self.scroll
                ex = self.entry_x
                ix = ex + ENTRY_PAD
                iy = ey + ENTRY_PAD
                zr = ix + ICON_SZ // 2

                if ix <= mx < zr:
                    self.hover_zone = "arrow_up" if my < ey + ENTRY_H // 2 else "arrow_dn"
                elif ix <= mx < ix + ICON_SZ and iy <= my < iy + ICON_SZ:
                    self.hover_zone = "icon"




    def _onclick(self, mx, my):
        sb = self._sb_bar()

        if sb and self.sb_x <= mx < self.sb_x + self.sb_w:
            by, bh = sb
            if by <= my < by + bh:
                self.dragging_sb = True
                self.drag_off    = my - by
                return False
            elif self.y <= my < self.y + self.h:
                tk  = self.h - bh
                rel = (my - bh // 2 - self.y) / max(1, tk)
                self.scroll = max(0, min(int(rel * self._max_scroll()), self._max_scroll()))
                return False



        if self.hovered >= 0:
            if self.hover_zone == "arrow_up" and self.hovered > 0:
                i = self.hovered
                self.items[i], self.items[i-1] = self.items[i-1], self.items[i]
                if   self.selected == i:   self.selected -= 1
                elif self.selected == i-1: self.selected += 1
                return "reorder"


            elif self.hover_zone == "arrow_dn" and self.hovered < len(self.items) - 1:
                i = self.hovered
                self.items[i], self.items[i+1] = self.items[i+1], self.items[i]
                if   self.selected == i:   self.selected += 1
                elif self.selected == i+1: self.selected -= 1
                return "reorder"

            else:
                self.selected = self.hovered
                return True



        return False








    def on_release(self): self.dragging_sb = False

    def ondblclk(self, mx, my):
        return self.hovered >= 0 and self.hovered == self.selected

    def _onscroll(self, dy):
        self.scroll = max(0, min(self.scroll - dy * (ENTRY_H // 2), self._max_scroll()))

    def get_selected(self):
        if 0 <= self.selected < len(self.items): return self.items[self.selected]
        return None






    def draw(self, surf, render_fn):
        bg = pygame.Surface((self.w, self.h), pygame.SRCALPHA)
        bg.fill((0, 0, 0, 160))
        surf.blit(bg, (self.x, self.y))

        clip_prev = surf.get_clip()
        surf.set_clip(pygame.Rect(self.x, self.y, self.w, self.h))

        for i in range(len(self.items)):
            ey = self.y + LIST_ITEM_PAD + i * ENTRY_H - self.scroll

            if ey + ENTRY_H < self.y or ey > self.y + self.h:
                continue

            ex = self.entry_x
            ew = self.entry_w

            if i == self.selected:
                fill = pygame.Surface((ew, ENTRY_H), pygame.SRCALPHA)
                fill.fill((0, 0, 0, 160))
                surf.blit(fill, (ex, ey))
                pygame.draw.rect(surf, WHITE, (ex, ey, ew, ENTRY_H), GS)

            ix = ex + ENTRY_PAD
            iy = ey + ENTRY_PAD
            
            

            if self.ico_surf:
                ic = pygame.transform.scale(self.ico_surf, (ICON_SZ, ICON_SZ))
                surf.blit(ic, (ix, iy))
                
                

            if i == self.hovered and self.ss_surf:
                half = ICON_SZ // 2

                pr  = 1 if self.hover_zone == "icon" else 0
                psr = self._arrows.get(('play', pr))
                if psr:
                    pw, ph = psr.get_size()
                    pb = pygame.transform.scale(psr, (pw*2, ph*2))
                    rx = ix + half + (half - pw*2) // 2
                    ry = iy + (ICON_SZ - ph*2) // 2
                    surf.blit(pb, (rx, ry))
                    

                aw, ah = self.arrow_w * 2, self.arrow_h * 2
                ax     = ix + (half - aw) // 2
                hf     = ENTRY_H // 2

                ur  = 1 if self.hover_zone == "arrow_up" else 0
                usr = self._arrows.get((3, ur))
                if usr:
                    surf.blit(
                        pygame.transform.scale(usr, (aw, ah)),
                        (ax, ey + (hf - ah) // 2)
                    )

                dr  = 1 if self.hover_zone == "arrow_dn" else 0
                dsr = self._arrows.get((2, dr))
                if dsr:
                    surf.blit(
                        pygame.transform.scale(dsr, (aw, ah)),
                        (ax, ey + hf + (hf - ah) // 2)
                    )
                    
                    

            tx = ix + ICON_SZ + ENTRY_PAD
            tw = ew - (tx - ex)
            render_fn(surf, self.items[i], tx, ey, tw)

        surf.set_clip(clip_prev)

        gh = 8 * GS
        drawgrad(surf, 0, self.y, WIN_W, gh, 200, 0)
        drawgrad(surf, 0, self.y + self.h - gh, WIN_W, gh, 0,   200)

        sb = self._sb_bar()
        if sb:
            by, bh = sb
            if self._sb_src:
                surf.blit(nine_slice(self._sb_src, self.sb_w, bh), (self.sb_x, by))
            else:
                pygame.draw.rect(surf, (128, 128, 128), (self.sb_x, by, self.sb_w, bh))


