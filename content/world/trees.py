import pickle
import numpy as np
from pathlib import Path
import random
from numba import njit


class TreeSchem:
    def __init__(self, path):
        self.path = path
        self.nm = Path(path).stem
        
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        self.wgts = data['width']
        self.h    = data['height']
        self.l    = data['length']
        self.base = data['base_level']
        
        blist = data['blocks']
        n = len(blist)
        self.bcount = n
        self.bx = np.zeros(n, dtype=np.int32)
        self.by = np.zeros(n, dtype=np.int32)
        self.bz = np.zeros(n, dtype=np.int32)
        self.btypes = np.zeros(n, dtype=np.uint16)
        
        for i, (x, y, z, btype) in enumerate(blist):
            self.bx[i] = x
            self.by[i] = y
            self.bz[i] = z
            self.btypes[i] = int(btype)
        
        
        # TODO 
        # amke a better tree sorting system
        pts = self.nm.split('_')
        if len(pts) >= 3:
            self.tree_type = pts[1]
            self.size_cat = pts[2][0]
            
        else:
            self.tree_type = "Unknown"
            self.size_cat = "M"
    
    def footprint(self):
        return max(self.wgts, self.l) // 2 + 1


class TreeManager:
    def __init__(self, assetdir="assets"):
        self.assetdir = Path(assetdir)
        # server runs from repo root, cwd cant be trusted
        if not self.assetdir.is_dir():
            self.assetdir = Path(__file__).resolve().parent.parent / "assets"
        self.schems = []
        self.loadschems()
        self.tree_density = 0.03
        self.min_space = 4
        
    def loadschems(self):
        self.sizedtrees = {'S': [], 'M': [], 'L': []}
        
        for f in self.assetdir.glob("T_*.pkl"):
            schem = TreeSchem(f)
            self.schems.append(schem)

            if schem.h <= 7: cat = 'S'
            elif schem.h <= 13: cat = 'M'
            else: cat = 'L'
            self.sizedtrees[cat].append(schem)
    
    def getrand(self, y=64, sea=64):
        if not self.schems: return None
        alt = max(0, y - sea)
        
        count_l = len(self.sizedtrees['L'])
        count_m = len(self.sizedtrees['M'])
        count_s = len(self.sizedtrees['S'])
        w_l = max(0.0, 1.0 - alt / 30.0) * count_l if count_l else 0.0
        w_m = max(0.0, 1.0 - alt / 50.0) * count_m if count_m else 0.0
        w_s = 1.0 * count_s if count_s else 0.0
        
        
        
        wgts = [w_l, w_m, w_s]
        if sum(wgts) == 0:
            return random.choice(self.schems) if self.schems else None
            
        cat = random.choices(['L', 'M', 'S'], weights=wgts, k=1)[0]
        return random.choice(self.sizedtrees[cat]) if self.sizedtrees[cat] else random.choice(self.schems)
    
    def canplace(self, voxels, x, y, z, tree, chunk_sz=16, chunk_h=128):
        
        if y < 1 or y >= chunk_h or y + tree.h >= chunk_h: return False
        if x < 2 or x >= chunk_sz - 2 or z < 2 or z >= chunk_sz - 2: return False
        if y - 1 >= 0 and voxels[x, y - 1, z] != 1: return False
        if voxels[x, y, z] != 0: return False
        
        return True
    
    def place(
        self, 
        voxels, 
        wx, wy, wz, 
        tree, off_x=0, off_z=0, 
        chunk_sz=16, chunk_h=128, 
        cm=None, rot=0
    ):
            
            
        oy = wy - tree.base
        cx, cz = tree.wgts // 2, tree.l // 2
        
        p = _placetree_jit(
            voxels, 
            tree.bx, tree.by, tree.bz, 
            tree.btypes, tree.bcount,
            wx, oy, wz, 
            off_x, off_z, 
            cx, cz, rot, 
            chunk_sz, chunk_h
        )
        
        
        
        # FIX not working properly most of the time
        # cross chunk decor (object ref prevents jit)
        if cm:
            for i in range(tree.bcount):
                bx, by, bz = tree.bx[i], tree.by[i], tree.bz[i]
                vtype = tree.btypes[i]
                if vtype == 0: continue
                
                rx, rz = bx - cx, bz - cz
                if rot   == 1: rx, rz = -rz,  rx
                elif rot == 2: rx, rz = -rx, -rz
                elif rot == 3: rx, rz =  rz, -rx
                
                wbx = wx + rx
                wby = oy + by
                wbz = wz + rz
                lx  = wbx - off_x
                lz  = wbz - off_z
                
                if not (0 <= lx < chunk_sz and 0 <= lz < chunk_sz):
                    if 0 <= wby < chunk_h:
                        cm.add_decor(wbx, wby, wbz, vtype)
        
        return p





# jit functions 

@njit(cache=True, fastmath=True, nogil=True)
def _placetree_jit(
        voxels, 
        bx_arr, by_arr, bz_arr, 
        btypes, n_blocks,
        wx, oy, wz, 
        off_x, off_z, 
        cx, cz, rot, 
        chunk_sz, chunk_h
    ):
    
    p = 0
    
    for i in range(n_blocks):
        bx, by, bz = bx_arr[i], by_arr[i], bz_arr[i]
        vtype = btypes[i]
        if vtype == 0: continue
        
        rx, rz = bx - cx, bz - cz
        if   rot == 1: rx, rz = -rz, rx
        elif rot == 2: rx, rz = -rx, -rz
        elif rot == 3: rx, rz = rz, -rx
        
        wbx = wx + rx
        wby = oy + by
        wbz = wz + rz
        
        lx = wbx - off_x
        lz = wbz - off_z
        
        
        
        if 0 <= lx < chunk_sz and 0 <= lz < chunk_sz:
            
            if 0 <= wby < chunk_h:
                cur = voxels[lx, wby, lz]
                
                if cur == 0 or cur == 1:  # air or grass
                    voxels[lx, wby, lz] = vtype
                    p += 1
    
    
    return p







@njit(cache=True, fastmath=True)
def fade(t): return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)


@njit(cache=True, fastmath=True)
def lerp(t, a, b): return a + t * (b - a)



@njit(cache=True, fastmath=True)
def grad(h, x, y, z):
    h = h & 15
    u = x if h < 8 else y
    v = y if h < 4 else (x if h == 12 or h == 14 else z)
    return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)







@njit(cache=True, fastmath=True)
def noise3d(x, y, z, p):
    
    xi = int(np.floor(x)) & 255
    yi = int(np.floor(y)) & 255
    zi = int(np.floor(z)) & 255
    
    xf = x - np.floor(x)
    yf = y - np.floor(y)
    zf = z - np.floor(z)
    
    u, v, wgts = fade(xf), fade(yf), fade(zf)
    
    
    
    
    
    aaa = p[p[p[xi] + yi] + zi]
    aba = p[p[p[xi] + yi + 1] + zi]
    aab = p[p[p[xi] + yi] + zi + 1]
    abb = p[p[p[xi] + yi + 1] + zi + 1]
    baa = p[p[p[xi + 1] + yi] + zi]
    bba = p[p[p[xi + 1] + yi + 1] + zi]
    bab = p[p[p[xi + 1] + yi] + zi + 1]
    bbb = p[p[p[xi + 1] + yi + 1] + zi + 1]
    
    
    x1 = lerp(u, grad(aaa, xf, yf, zf), grad(baa, xf - 1.0, yf, zf))
    x2 = lerp(u, grad(aba, xf, yf - 1.0, zf), grad(bba, xf - 1.0, yf - 1.0, zf))
    y1 = lerp(v, x1, x2)
    
    
    x1 = lerp(u, grad(aab, xf, yf, zf - 1.0), grad(bab, xf - 1.0, yf, zf - 1.0))
    x2 = lerp(u, grad(abb, xf, yf - 1.0, zf - 1.0), grad(bbb, xf - 1.0, yf - 1.0, zf - 1.0))
    y2 = lerp(v, x1, x2)
    
    
    return lerp(wgts, y1, y2)
    
    
    





# bioe ids 
# mirror terrain constants
_BIOME_PLAINS   = 0
_BIOME_DESERT   = 1
_BIOME_SNOWY    = 2
_BIOME_JUNGLE   = 3
_BIOME_BADLANDS = 4
_BIOME_FOREST   = 5




@njit(cache=True, fastmath=True)
def gen_treepos(
        voxels, 
        off_x, off_z, 
        seed, dens, p, biomes, 
        chunk_sz=16, chunk_h=128, 
        sea=64
    ):
        
    pos = []
    np.random.seed(seed + off_x * 73856093 + off_z * 19349663)
    scale = 0.02
    
    # TODO
    # biome decor json config files
    # then delete ts functions
    # 8====3

    for x in range(chunk_sz):
        for z in range(chunk_sz):
            biome = biomes[x, z]
            # 1=desert, 4=badlands
            if biome == 1 or biome == 4: continue

            wx, wz = off_x + x, off_z + z
            ns = noise3d(wx * scale, 0.5, wz * scale, p)

            local_d = 0.0
            if biome == 5:      # forest
                if ns > 0.0:    local_d = dens * 5.0
                elif ns > -0.2: local_d = dens * 2.5
                else:           local_d = dens * 0.8
                
            elif biome == 3:    # jungle
                if ns > -0.1:   local_d = dens * 6.0
                else:           local_d = dens * 3.0
                
            else:               # plains&snow
                if ns > 0.1:    local_d = dens * 2.5
                elif ns > -0.1: local_d = dens * 0.2
                else:           local_d = 0.001
                
                
                

            for y in range(chunk_h - 1, sea - 10, -1):
                # grass:1/snow:47 valid gnd
                bv = voxels[x, y, z]
                if bv == 1 or bv == 47:
                    
                    if y + 1 < chunk_h and voxels[x, y + 1, z] == 0:
                        if np.random.random() < local_d:
                            pos.append((x, y + 1, z))
                            
                            
                    break
                    
                    
                    
    return pos










def treetochunk(
        voxels, 
        off_x, off_z, 
        tm, seed, p, cm=None,
        chunk_sz=16, chunk_h=128, 
        sea=64, biomes=None
    ):
        
    if not tm.schems: return 0

    # flat biomes array if none supplied 
    # all plains -> backward compat
    if biomes is None:
        import numpy as _np
        biomes = _np.zeros(
            (chunk_sz, chunk_sz), dtype=_np.int8
        )

    pos = gen_treepos(
        voxels, 
        off_x, off_z, 
        seed, tm.tree_density, 
        p, biomes, 
        chunk_sz, chunk_h, 
        sea
    )
    
    
    if not pos: return 0

    spacing = tm.min_space
    _gridsz = spacing
    grid = {}
    filtered = []

    for x, y, z in pos:
        gx, gz = x // _gridsz, z // _gridsz

        _tooclose = False
        for dx in range(-1, 2):
            for dz in range(-1, 2):
                key = (gx + dx, gz + dz)
                if key in grid:
                    ox, oz = grid[key]
                    if (x - ox)**2 + (z - oz)**2 < spacing**2:
                        _tooclose = True
                        break
                        
                        
            if _tooclose: break

        if not _tooclose:
            grid[(gx, gz)] = (x, z)
            filtered.append((x, y, z))
            
            

    if not filtered: return 0

    _seed = seed + off_x * 374761393 + off_z * 668265263
    random.seed(_seed)

    p = 0
    for x, y, z in filtered:
        if y < 1 or y >= chunk_h: continue
        if x < 2 or x >= chunk_sz - 2 or z < 2 or z >= chunk_sz - 2: continue
        
        
        # allow grass:1 / snow:47 below tree
        
        if y - 1 >= 0 and voxels[x, y - 1, z] not in (1, 47): continue
        if voxels[x, y, z] != 0: continue

        tree = tm.getrand(y, sea)
        if not tree: continue

        if y + tree.h >= chunk_h: continue

        rot = random.randint(0, 3)
        if tm.place(
            voxels, 
            off_x + x, y, 
            off_z + z, 
            tree,
            off_x, off_z, 
            chunk_sz, chunk_h, 
            cm, rot
        ) > 0:
            p += 1

    return p


@njit(cache=True, fastmath=True)
def gen_grasspos(
        voxels, 
        off_x, off_z, 
        seed, dens, 
        p, biomes, 
        chunk_sz=16, chunk_h=128, 
        sea=64
    ):
    pos = []
    np.random.seed(seed + off_x * 91274893 + off_z * 48271947)
    scale = 0.05

    for x in range(chunk_sz):
        for z in range(chunk_sz):
            biome = biomes[x, z]
            # desert:1, badlands:4, snowy:2
            if (
                biome == 1 or 
                biome == 4 or 
                biome == 2
                ):
                continue

            wx, wz = off_x + x, off_z + z
            ns = noise3d(wx * scale, 0.3, wz * scale, p)

            local_d = 0.0
            if ns > 0.2:    local_d = dens * 3.0
            elif ns > -0.1: local_d = dens * 0.5

            for y in range(chunk_h - 1, sea - 10, -1):
                if voxels[x, y, z] == 1:
                    if y + 1 < chunk_h and voxels[x, y + 1, z] == 0:
                        if np.random.random() < local_d:
                            pos.append((x, y + 1, z))
                    break
                    
                    
                    
    return pos


def grasstochunk(
        voxels, 
        off_x, off_z, 
        seed, p, biomes=None, 
        chunk_sz=16, chunk_h=128, 
        sea=64
    ):
        
    
    if biomes is None:
        import numpy as _np
        biomes = _np.zeros((chunk_sz, chunk_sz), dtype=_np.int8)

    dens = 0.15
    pos  = gen_grasspos(
        voxels, 
        off_x, off_z, 
        seed, dens, p, 
        biomes, 
        chunk_sz, chunk_h, 
        sea
    )
    
    
    if not pos: return 0

    _seed = seed + off_x * 482917463 + off_z * 738291047
    random.seed(_seed)
    
    

    p = 0
    for x, y, z in pos:
        
        if y - 1 >= 0 and y < chunk_h:
            if voxels[x, y - 1, z] == 1 and voxels[x, y, z] == 0:
                voxels[x, y, z] = 10
                p += 1
                
                
                
    return p





@njit(cache=True, fastmath=True)
def _place_cactijit(
        voxels, 
        off_x, off_z, 
        seed, biomes, 
        chunk_sz, chunk_h,
        sea
    ):
    
    np.random.seed(seed + int(off_x) * 48271947 + int(off_z) * 91274893)
    p = 0

    for x in range(chunk_sz):
        for z in range(chunk_sz):
            # desert:1
            if biomes[x, z] != 1:  continue
            
            
            # topmost sand above sea
            for y in range(chunk_h - 1, sea - 1, -1):
                if voxels[x, y, z] == 6:   # sand:6
                    
                    if np.random.random() < 0.05:
                        # 5 % density
                        # must not touch adjacent solids at +1 height
                        ok = True
                        if x > 0 and voxels[x - 1, y + 1, z] != 0:                   ok = False
                        if ok and x < chunk_sz - 1 and voxels[x + 1, y + 1, z] != 0: ok = False
                        if ok and z > 0 and voxels[x, y + 1, z - 1] != 0:            ok = False
                        if ok and z < chunk_sz - 1 and voxels[x, y + 1, z + 1] != 0: ok = False
                        
                        
                        if ok:
                            height = 1 + int(np.random.random() * 2.9)  # 1–3 tall
                            for i in range(height):
                                
                                if y + 1 + i < chunk_h and voxels[x, y + 1 + i, z] == 0:
                                    voxels[x, y + 1 + i, z] = 70   # cactus:70
                                    p += 1
                                    
                                    
                    break 
    
    
    
    return p









def cactitochunk(
        voxels, 
        off_x, off_z, 
        biomes, seed, 
        chunk_sz=16, chunk_h=128, 
        sea=64
    ):
    return _place_cactijit(
        voxels, 
        float(off_x), 
        float(off_z), 
        seed, biomes, 
        chunk_sz, chunk_h, 
        sea
    )
