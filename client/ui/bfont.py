import pygame
import os

GRID_COLS = 16
GRID_ROWS = 16
CHAR_W = 8
CHAR_H = 8
SPACING = 1


class Font:
    font_surf = None
    char_ws  = None

    def __init__(self, path="ui/font.png", scale=2):
        self.scale = max(1, int(scale))
        self.fpath = path

        if Font.font_surf is None:
            self.loadfont(path)

        self.font_surface = Font.font_surf

        if Font.char_ws is None:
            self.calcwidths()

        self._char_cache = {}
        self._text_cache = {}

    def loadfont(self, path):
        Font.font_surf = pygame.image.load(path).convert_alpha()
        
        

    def calcwidths(self):
        Font.char_ws = {}

        for code in range(256):
            gx = code % GRID_COLS
            gy = code // GRID_COLS
            sx = gx * CHAR_W
            sy = gy * CHAR_H

            w = 0
            for x in range(CHAR_W):
                for y in range(CHAR_H):
                    if self.font_surface.get_at((sx + x, sy + y))[3] > 0:
                        w = x + 1

            if code == 32:  w = 4
            elif code < 32: w = 0
            elif w == 0:    w = CHAR_W

            Font.char_ws[code] = w + 1





    def charw(self, char):
        c = ord(char) if isinstance(char, str) else char
        if c < 0 or c > 255:
            c = ord('?')
            
        return Font.char_ws.get(c, CHAR_W) * self.scale



    def textsize(self, text):
        if not text: return (0, CHAR_H * self.scale)
        

        l = text.split('\n')
        mw = 0
        for i in l:
            w = 0
            for j in i:
                w += self.charw(j)
            mw = max(mw, w)

        h = len(l) * (CHAR_H + 1) * self.scale
        return (mw, h)



    def charrect(self, char):
        c = ord(char) if isinstance(char, str) else char
        if c < 0 or c > 255:
            c = ord('?')
            
        gx = c % GRID_COLS
        gy = c // GRID_COLS
        return pygame.Rect(gx * CHAR_W, gy * CHAR_H, CHAR_W, CHAR_H)
        
        
        
        

    def renderchar(self, char, color):
        
        code = ord(char) if isinstance(char, str) else char
        ck   = (code, color)
        cached = self._char_cache.get(ck)
        
        if cached is not None:
            return cached

        sr = self.charrect(char)
        cs = self.font_surface.subsurface(sr).copy()

        if self.scale > 1:
            cs = pygame.transform.scale(cs, (
                CHAR_W * self.scale, 
                CHAR_H * self.scale
            ))
            

        if color != (255, 255, 255):
            tinted = cs.copy()
            tint = pygame.Surface(tinted.get_size(), pygame.SRCALPHA)
            tint.fill((*color[:3], 255))
            tinted.blit(tint, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
            cs = tinted
            

        self._char_cache[ck] = cs
        return cs
        
        
        
        
        
        
        

    def render(self, text, antialias=False, color=(255, 255, 255)):
        if not text: return pygame.Surface((1, CHAR_H * self.scale), pygame.SRCALPHA)
        

        tk = (text, color)
        cached = self._text_cache.get(tk)
        if cached is not None:
            return cached
            
        # character spacing
        charSpacing = 2
        l  = text.split('\n')
        w, h = self.textsize(text)
        w += charSpacing * len(text)
        soff   = self.scale
        surface = pygame.Surface((w + soff, h), pygame.SRCALPHA)

        shc = (
            max(0, color[0] // 4), 
            max(0, color[1] // 4), 
            max(0, color[2] // 4)
        )
        lh  = (CHAR_H + 1) * self.scale
        

        y = 2
        for i in l:
            x = 0
            for j in i:
                if j == ' ':
                    x += self.charw(' ')
                    continue
                    
                # removed the drop shadow
                # surface.blit(self.renderchar(j, shc), (x + soff, y + soff))
                surface.blit(self.renderchar(j, color), (x, y))
                x += self.charw(j) + charSpacing
            y += lh
            

        if len(self._text_cache) > 512:
            self._text_cache.clear()
            
        self._text_cache[tk] = surface
        return surface
        
        
        
        

    def renderns(self, text, color=(255, 255, 255)):
        if not text:
            return pygame.Surface((1, CHAR_H * self.scale), pygame.SRCALPHA)

        l = text.split('\n')
        w, h = self.textsize(text)
        surface = pygame.Surface((max(1, w), max(1, h)), pygame.SRCALPHA)
        lh = (CHAR_H + 1) * self.scale

        y = 0
        for i in l:
            x = 0
            for j in i:
                if j == ' ':
                    x += self.charw(' ')
                    continue
                surface.blit(self.renderchar(j, color), (x, y))
                x += self.charw(j)
            y += lh
        return surface
        
        

    def get_size(self):   return (CHAR_H + 1) * self.scale
    def get_height(self): return (CHAR_H + 1) * self.scale


_font_instances = {}


def getfont(scale=1, path="ui/font.png"):
    key = (path, scale)
    if key not in _font_instances:
        _font_instances[key] = Font(path, scale)
    return _font_instances[key]

















