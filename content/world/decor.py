import pickle
import numpy as np
from pathlib import Path
import random
from numba import njit

BLOCK_MAP = {
    'stone': 3, 
    'cobblestone': 3, 
    'undefined': 0
}


class RockSchematic:
    def __init__(self, path):
        self.path = path
        self.nm = Path(path).stem
        
        with open(path, 'rb') as f:
            data = pickle.load(f)
        
        self.w = data['width']
        self.h = data['height']
        self.l = data['length']
        self.base   = data.get('base_level', 0)
        self.blocks = data['blocks']


class RockManager:
    def __init__(self, assetdir="assets"):
        self.assetdir = Path(assetdir)
        # server runs from repo root, cwd cant be trusted
        if not self.assetdir.is_dir():
            self.assetdir = Path(__file__).resolve().parent.parent / "assets"
        self.schems = []
        self.loadschems()
        self.rock_density = 0.0003
        
        
    
    def loadschems(self):
        for f in self.assetdir.glob("R_*.pkl"):
            self.schems.append(RockSchematic(f))
            
    
    def getrand(self):
        return random.choice(self.schems) if self.schems else None
        
        
        
    
    def canplace(self, voxels, x, y, z, rock, chunk_sz=16, chunk_h=128):
        if (
            (y < 1 or y >= chunk_h  or y + rock.h >= chunk_h) or
            (x < 1 or x >= chunk_sz - 1 or z < 1 or z >= chunk_sz - 1) or
            (y - 1 >= 0 and voxels[x, y - 1, z] != 1) or
            (voxels[x, y, z] != 0)
        ):
            return False
            
        
        for dx, dz in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, nz = x + dx, z + dz
            if 0 <= nx < chunk_sz and 0 <= nz < chunk_sz:
                if voxels[nx, y - 1, nz] != 1 or voxels[nx, y, nz] != 0:
                    return False
                    
        return True
        
        
        
    
    def place(
        self, voxels, 
        wx, wy, wz, 
        rock, off_x=0, off_z=0, 
        chunk_sz=16, chunk_h=128, 
        cm=None, rot=0, 
        scale=1.0
    ):
        
        if rot % 2 == 0: w, l = rock.w, rock.l
        else: w, l = rock.l, rock.w
        
        
        
        
        oy = wy - rock.base
        cx, cz = rock.w // 2, rock.l // 2
        placed = 0
        
        
        
        for bx, by, bz, btype in rock.blocks:
            rx, rz = bx - cx, bz - cz
            if rot   == 1: rx, rz = -rz,  rx
            elif rot == 2: rx, rz = -rx, -rz
            elif rot == 3: rx, rz =  rz, -rx
            
            wbx = wx + rx
            wby = oy + by
            wbz = wz + rz
            
            vtype = BLOCK_MAP.get(btype, 3)
            if vtype == 0: continue
            
            lx = wbx - off_x
            lz = wbz - off_z
            
            if 0 <= lx < chunk_sz and 0 <= lz < chunk_sz:
                if 0 <= wby < chunk_h:
                    cur = voxels[lx, wby, lz]
                    if cur == 0 or cur == 1:
                        voxels[lx, wby, lz] = vtype
                        placed += 1
                        
                        
            elif cm:
                cm.add_decor(wbx, wby, wbz, vtype)
                placed += 1
                
                
        return placed










from world.trees import noise3d





@njit(cache=True, fastmath=True)
def genrockpos(
        voxels, 
        off_x, off_z, 
        seed, density, p, 
        chunk_sz=16, 
        chunk_h=128, 
        sea=64
    ):
    
    
    _pos = []
    np.random.seed(seed + off_x * 56473829 + off_z * 93847261)
    scale = 0.02
    
    for x in range(chunk_sz):
        for z in range(chunk_sz):
            wx, wz = off_x + x, off_z + z
            noise = noise3d(wx * scale, 0.5, wz * scale, p)
            
            local_d = 0.0
            if noise < -0.1: local_d = density * 4.0
            elif noise < 0.1: local_d = density * 0.5
            
            for y in range(chunk_h - 1, sea - 5, -1):
                if voxels[x, y, z] == 1:
                    if y >= 90 or y - sea < 0: break
                    if y + 1 < chunk_h and voxels[x, y + 1, z] == 0:
                        if np.random.random() < local_d:
                            _pos.append((x, y + 1, z))
                            
                    break
                    
                    
                    
    return _pos










def addchunkrocks(
        voxels, 
        off_x, off_z, 
        rm, seed, p, cm=None, 
        chunk_sz=16, 
        chunk_h=128, 
        sea=64
    ):
        
    if not rm.schems: return 0
    
    _pos = genrockpos(
        voxels, off_x, off_z, 
        seed, rm.rock_density, p, 
        chunk_sz, chunk_h, sea
    )
    if not _pos: return 0
    
    
    
    
    chunk_seed = seed + off_x * 627384921 + off_z * 849273641
    random.seed(chunk_seed)
    
    p = 0
    for x, y, z in _pos:
        
        rock = rm.getrand()
        if not rock: continue
        
        if rm.canplace(voxels, x, y, z, rock, chunk_sz, chunk_h):
            rot   = random.randint(0, 3)
            scale = random.uniform(0.8, 1.2)
            
            if rm.place(
                    voxels, 
                    off_x + x, y, 
                    off_z + z, rock, 
                    off_x, off_z, 
                    chunk_sz, chunk_h, 
                    cm, rot, scale
            ) > 0:
                p += 1
                
    return p









