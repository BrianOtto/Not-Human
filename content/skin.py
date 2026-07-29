import io
import moderngl
import pygame

SKIN_W = 64
SKIN_H = 64


# 64x32 legacy
_LEGACY_COPY = [
    (20, 48,  4, 16, 4,  4),
    (24, 48,  8, 16, 4,  4),
    (16, 52,  8, 20, 4, 12),
    (20, 52,  4, 20, 4, 12),
    (24, 52,  0, 20, 4, 12),
    (28, 52, 12, 20, 4, 12),
    (36, 48, 44, 16, 4,  4),
    (40, 48, 48, 16, 4,  4),
    (32, 52, 48, 20, 4, 12),
    (36, 52, 44, 20, 4, 12),
    (40, 52, 40, 20, 4, 12),
    (44, 52, 52, 20, 4, 12),
]


def _unlegacy(img):
    for dx, dy, sx, sy, w, h in _LEGACY_COPY:
        part = img.subsurface(pygame.Rect(sx, sy, w, h)).copy()
        img.blit(pygame.transform.flip(part, True, False), (dx, dy))


def loadskin(src):
    # path or raw png bytes -> a 64x64 surface, cropped from (0,0)
    src = pygame.image.load(io.BytesIO(src) if isinstance(src, bytes) else src)
    img = pygame.Surface((SKIN_W, SKIN_H), pygame.SRCALPHA)
    img.blit(src.convert_alpha(), (0, 0), pygame.Rect(0, 0, SKIN_W, SKIN_H))

    if src.get_height() < SKIN_H: _unlegacy(img)
    return img


def skintex(ctx, src):
    img  = pygame.transform.flip(loadskin(src), False, True)
    data = pygame.image.tostring(img, "RGBA")
    tex  = ctx.texture(img.get_size(), 4, data)
    tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
    return tex
