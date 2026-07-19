import os
import json

_ACTIVE = None


def _getdir():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "client", "resourcepacks")


def _getavailable(out=[]):
    out = []
    d = _getdir()
    if not os.path.isdir(d): return out

    for n in sorted(os.listdir(d)):
        f = os.path.join(d, n, "pack.json")
        if os.path.isfile(f):
            with open(f, 'r') as f: meta = json.load(f)
            out.append({
                "folder":      n,
                "name":        meta.get("name", n),
                "description": meta.get("description", ""),
                "version":     meta.get("version", ""),
                "author":      meta.get("author", "Unknown"),
            })
    return out


def _setactive(nm):
    global _ACTIVE
    _ACTIVE = os.path.join(_getdir(), nm)


def _getactive():
    global _ACTIVE
    if _ACTIVE is None:
        _setactive("default")
    return _ACTIVE


# textures

def atlas_block():   return os.path.join(_getactive(), "textures", "blocks", "atlas.png")
def atlas_items():   return os.path.join(_getactive(), "textures", "items",  "items.png")
def clrmap_grass():  return os.path.join(_getactive(), "textures", "colormaps", "grass.png")
def clrmap_folage(): return os.path.join(_getactive(), "textures", "colormaps", "foliage.png")
def text_player():   return os.path.join(_getdir(), "player", "skin.png")
def text_ascii():    return os.path.join(_getactive(), "textures", "ui", "ascii.png")
def text_font():     return os.path.join(_getactive(), "textures", "ui", "font.png")
def text_gui():      return os.path.join(_getactive(), "textures", "ui", "gui.png")
def text_inv():      return os.path.join(_getactive(), "textures", "ui", "inventory.png")


# models

def dir_model(): return os.path.join(_getactive(), "models", "blocks")
def dir_anims(): return os.path.join(_getactive(), "animations")
