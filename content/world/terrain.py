import numpy as np
import moderngl
import threading
from collections import deque
from queue import Queue
from numba import njit, prange
import math
import struct
import time
import os
from world.trees import TreeManager, treetochunk, grasstochunk, cactitochunk
from world.decor import RockManager, addchunkrocks



from world.blocks import (
    UV_ARRAY, UV_W, UV_H,
    _FACINGTYPE, HOR_UV_REMAP, AXIS_UV_REMAP, AXIS_UV_ROT,
    FACINGNONE, FACING_H, FACING_AX,
    FACE_N, FACE_S, FACE_E, FACE_W,
    AXY, AXX, AXZ,
    NONSOLID_BLOCKS,
)

from world.renderers.registry import (
    BLOCK_MODE_RENDER, BLOCK_CUSTOM_FACES, BLOCK_STATE_HEIGHT,
    BLOCK_TYPE_CULL, MODE_SOLID, MODE_TRANSPARENT, MODE_CUSTOM,
    NUM_ELEMENTS, BLOCK_ELEMS, BLOCK_MODE_UV, CULL_TOPBOT,
    UV_MODE_IDX, UV_MODE_POS, UV_MODE_MODEL as UV_MODE_MINECRAFT, MODE_EXTRUDED,
    BLOCK_TINT_COLOR, MODE_FLAT, BLOCK_UVS, BLOCK_TEX,
    CONNECT_TYPE, CONNECT_FAMILY, BLOCK_ARM_NUM,
    BLOCK_ARM_ELEM, BLOCK_ARM_FUVS, BLOCK_ARM_FTEX,
    STATE_ELEM_OFF, STATE_ELEM_NUM,
)


import config
from config import (
    CHUNK_SZ, CHUNK_H, SEA_LEVEL, WATER_OFF,
    TERRAIN_SCL_X, TERRAIN_SCL_Z, TERRAIN_SCL_Y
)

# state [PSSS SSBB] [BBBB BBBB]
# lwer 10b = id (<=1024), 
# bits 10-14 = state, 
# bit 15 = mod flag
BLOCK_ID_MASK = 0x3FF  # 10b -> 1024 possible ids
STATE_SHIFT   = 10

EMPTY_VOXEL = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint16)
EMPTY_LIGHT = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint8)








from world.noise import (
    fade, lerp, grad, noise3d, fractal3d,
    get_climate, climate_tobiome, get_biome, smooth_bonus,
    _badlands_band, locate_biome,

    BIOME_PLAINS, BIOME_DESERT, BIOME_SNOWY,
    BIOME_JUNGLE, BIOME_BADLANDS, BIOME_FOREST, BIOME_NAMES,
)
from world.generate import _generate
from world.mesh import (
    bake_skylight, build_meshjit,
    is_localsolid, get_localblock, is_localwater,
    _is_lightaware, _emitface, _emitgrass,
    
    FACE_VERTS, FACE_NORMALS, FACE_UV_OFFSETS, GRASS_VERTS,
    BUILD_FACE_V, BUILD_FACE_N, BUILD_FACE_UV, MESH_GRASS_V,
)
from world.chunk import PerlinNoise, Chunk, EMPTY_VOXEL, EMPTY_LIGHT






def warmup_jit_functions():
    print("Warming up JIT...")
    dvox = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint16)
    dlit = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint8)
    p = np.arange(512, dtype=np.int32) % 256

    for x in range(4):
        for z in range(4):
            dvox[x, 60, z] = 1
            dvox[x, 59, z] = 2
            dvox[x, 58, z] = 3

    _ = fade(0.5)
    _ = lerp(0.5, 0.0, 1.0)
    _ = grad(1, 0.5, 0.5, 0.5)
    _ = noise3d(0.0, 0.0, 0.0, p)
    _ = fractal3d(0.0, 0.0, 0.0, p, 4, 0.5, 2.0, 0.01, 0.01, 0.01)
    _, _ = get_climate(0.0, 0.0, p)
    _ = get_biome(0.0, 0.0, p)
    _ = smooth_bonus(0.5, 0.5, 64.0)
    _ = _badlands_band(64)
    _, _ = locate_biome(0.0, 0.0, 0, p, 0, 32)   # max_radius=0 -> instant return
    
    dbiomes = np.zeros((CHUNK_SZ, CHUNK_SZ), dtype=np.int8)
    _generate(dvox, 0.0, 0.0, p, dbiomes)
    bake_skylight(dvox, dlit, dlit, dlit, dlit, dlit)
    
    
    dn = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint16)
    _ = build_meshjit(
        dvox,
        0.0, 0.0,
        dn, dn, dn, dn,
        dlit, dlit, dlit, dlit, dlit,
        UV_ARRAY, UV_W, UV_H,
        BLOCK_CUSTOM_FACES, BLOCK_MODE_RENDER,
        NUM_ELEMENTS, BLOCK_ELEMS,
        BLOCK_MODE_UV, CULL_TOPBOT,
        BUILD_FACE_V, BUILD_FACE_N, BUILD_FACE_UV,
        MESH_GRASS_V, _FACINGTYPE, HOR_UV_REMAP,
        AXIS_UV_REMAP, AXIS_UV_ROT,
        BLOCK_UVS, BLOCK_TEX,
        CONNECT_TYPE, CONNECT_FAMILY,
        BLOCK_ARM_NUM, BLOCK_ARM_ELEM,
        BLOCK_ARM_FUVS, BLOCK_ARM_FTEX,
        STATE_ELEM_OFF,
        STATE_ELEM_NUM
    )
    
    
    _ = is_localsolid(dvox, 0, 0, 0)
    _ = get_localblock(dvox, 0, 0, 0)
    _ = is_localwater(dvox, 0, 0, 0)
    _ = _is_lightaware(0)

    dverts = np.empty(350, dtype=np.float32)
    _ = _emitface(
        dverts,
        0, 0.0, 0.0, 0.0, 0.0, 0.0,
        0, 1.0, 0.0, 0.0, 0.0625, 0.0625,
        FACE_VERTS, FACE_NORMALS, FACE_UV_OFFSETS
    )
        
    _ = _emitgrass(
        dverts,
        0, 0.0, 0.0, 0.0, 0.0, 0.0,
        1.0, 0.0, 0.0, 0.0625, 0.0625, 
        GRASS_VERTS
    )
    
    print("JIT complete!")


warmup_jit_functions()




class ChunkManager:
    def __init__(self, world, render_dist=10, wname="default", is_server=False):
        self.world = world
        self.render_dist = render_dist
        self.wname = wname
        self.is_server = is_server
        self.chunks = {}
        self.queue_chunkbuild = deque()
        self.queue_meshupload = Queue()
        self.last_camera_chunk = None
        self.world_dir = os.path.join(config.root, wname)
        self.chunks_dir = self.world_dir
        if self.is_server: os.makedirs(self.chunks_dir, exist_ok=True)
        self.modCache = {}
        self.dirtychunks = set()
        self.save_queue = Queue(maxsize=1000)
        self.loadedmods_cache = {}
        self.ui = None
        self.debugmsg_lastchunk = {}
        self.debugmsg_cool = 2.0
        self.vischunk_cache = []
        self._cam_pos = None
        self._cam_front = None
        self.updatecache_threshold = 2.0
        self.pending_decorations = {}
        self.meshthread_event = threading.Event()
        from concurrent.futures import ThreadPoolExecutor
        nw = min(4, max(2, (os.cpu_count() or 4) // 2))
        self.terrain_executor = ThreadPoolExecutor(max_workers=nw, thread_name_prefix="TerrainGen")
        self.queue_terraingen = deque()
        self.mesh_build_queue = deque()
        self.generating_chunks = set()
        self.generating_lock = threading.Lock()
        self.mesh_thread_active = True
        self.mesh_thread = threading.Thread(target=self._mesh_builder_thread, daemon=True)
        self.mesh_thread.start()
        self.io_thread_active = True
        self.io_thread = threading.Thread(target=self._io_thread, daemon=True)
        self.io_thread.start()
        self._total_meshed = 0
        
        

    def resetworld(self):
        self.queue_chunkbuild.clear()
        self.mesh_build_queue.clear()
        
        while not self.queue_meshupload.empty():
            try: self.queue_meshupload.get_nowait()
            except Exception: break
            
            
            
        for c in list(self.chunks.values()): c.release()
        
        self.chunks.clear()
        self.modCache.clear()
        self.dirtychunks.clear()
        self.loadedmods_cache.clear()
        self.vischunk_cache.clear()
        self.pending_decorations.clear()
        self.last_camera_chunk = None
        self._cam_pos = None
        self._cam_front = None
        
        with self.generating_lock: self.generating_chunks.clear()
        





    def _io_thread(self):
        while self.io_thread_active:
            
            try:
                cx, cz, mods = self.save_queue.get(timeout=0.1)
                self.savemodsync(cx, cz, mods)
                self.save_queue.task_done()
                
            except Exception:
                pass
                
                
                
                
    
    def _mesh_builder_thread(self):
        pfuts = {}  # future -> chunk

        while self.mesh_thread_active:
            wd  = False
            mif = 8

            while len(pfuts) < mif and self.queue_chunkbuild:
                try:
                    chunk = self.queue_chunkbuild.popleft()
                    
                except IndexError:
                    break
                    
                    

                ck = (chunk.x, chunk.z)
                if ck not in self.chunks:
                    continue
                    
                    

                with self.generating_lock:
                    if ck in self.generating_chunks:
                        continue
                        
                    self.generating_chunks.add(ck)
                    
                    



                if not chunk.gen_ready:
                    self.preloadmods(chunk.x, chunk.z)
                    future = self.terrain_executor.submit(self.genterrainonly, chunk)
                    pfuts[future] = chunk
                    wd = True
                    
                else:
                    chunk.mesh_pending = True
                    self.mesh_build_queue.append(chunk)
                    with self.generating_lock:
                        self.generating_chunks.discard(ck)
                    wd = True
                    
                    

            done = [f for f in list(pfuts.keys()) if f.done()]
            for f in done:
                chunk = pfuts.pop(f)
                ck = (chunk.x, chunk.z)
                #print(ck)
                try:
                    if f.result() and ck in self.chunks:
                        chunk.mesh_pending = True
                        self.mesh_build_queue.append(chunk)
                        wd = True
                        
                except Exception as e:
                    import traceback
                    print(f"Error generating terrain for chunk ({chunk.x}, {chunk.z}): {e}")
                    traceback.print_exc()
                finally:
                    with self.generating_lock: self.generating_chunks.discard(ck)

            mbuilt = 0
            
            

            while self.mesh_build_queue and mbuilt < 6:
                
                try: chunk = self.mesh_build_queue.popleft()
                except IndexError: break
                
                ck = (chunk.x, chunk.z)
                
                if ck not in self.chunks:
                    chunk.mesh_pending = False
                    continue
                    
                    
                try:
                    inew = chunk.birth_time is None or (time.time() - chunk.birth_time < 1.0)
                    if chunk.light_dirty:
                        chunk.bakelight()
                    verts, trans_verts = chunk.build_mesh()
                    vb, vc = None, 0
                    tvb, tvc = None, 0
                    if verts is not None and len(verts) > 0:
                        vb, vc = verts.tobytes(), len(verts) // 9
                        
                    if trans_verts is not None and len(trans_verts) > 0:
                        tvb, tvc = trans_verts.tobytes(), len(trans_verts) // 9
                        
                        
                        
                        
                    self.queue_meshupload.put((chunk, vb, vc, tvb, tvc))
                    mbuilt += 1
                    wd = True
                    
                    if inew:
                        for dx, dz in [(-1,0), (1,0), (0,-1), (0,1)]:
                            nk = (chunk.x + dx, chunk.z + dz)
                            n = self.chunks.get(nk)
                            
                            if n and n.gen_ready and not n.mesh_pending:
                                n.mesh_pending = True
                                n.light_dirty = True
                                self.mesh_build_queue.append(n)
                                
                                
                                
                except Exception as e:
                    chunk.mesh_pending = False
                    import traceback
                    print(f"Error building mesh for chunk ({chunk.x}, {chunk.z}): {e}")
                    traceback.print_exc()
                    
                    
                    
            
            if wd or mbuilt > 0:
                #import time
                time.sleep(0.0005)  # 0.5ms yield to main thread
                
            elif not pfuts:
                self.meshthread_event.wait(timeout=0.005)
                self.meshthread_event.clear()
                
                
                
                
                
                
    
    def genterrainonly(self, chunk):
        chunk.genchunk()
        return True

    
    
    
    def load_chunk(self, cx, cz):
        if (cx, cz) in self.chunks: return
        if abs(cx) > 10000 or abs(cz) > 10000: return
        chunk = Chunk(cx, cz, self.world)
        self.chunks[(cx, cz)] = chunk
        self.queue_chunkbuild.append(chunk)
        self.meshthread_event.set()
    
    
    
    
    def add_decor(self, wx, wy, wz, bt):
        if wy < 0 or wy >= CHUNK_H: return
        if bt not in [7, 8, 9]: return
        cx, cz = wx // CHUNK_SZ, wz // CHUNK_SZ
        lx, lz = wx % CHUNK_SZ, wz % CHUNK_SZ
        
        chunk = self.chunks.get((cx, cz))
        
        
        # store as pending <- !chunk OR !chunk.gen_ready
        if not chunk or not chunk.gen_ready:
            key = (cx, cz)
            if key not in self.pending_decorations:
                self.pending_decorations[key] = []
                
            self.pending_decorations[key].append((lx, wy, lz, bt))
    
    
    
    
    
    
    def updateloads(self, camera_chunk_x, camera_chunk_z):
        if self.last_camera_chunk == (camera_chunk_x, camera_chunk_z):
            return

        # print(camera_chunk_x, camera_chunk_z)
        self.last_camera_chunk = (camera_chunk_x, camera_chunk_z)
        
        rd_sq = self.render_dist * self.render_dist
        ulsq  = (self.render_dist + 2) ** 2

        for dist in range(self.render_dist + 1):
            for dx in range(-dist, dist + 1):
                for dz in range(-dist, dist + 1):
                    if max(abs(dx), abs(dz)) == dist:
                        cx   = camera_chunk_x + dx
                        cz   = camera_chunk_z + dz
                        d_sq = dx*dx + dz*dz
                        if d_sq <= rd_sq:
                            self.load_chunk(cx, cz)

        self.priorbuildq(camera_chunk_x, camera_chunk_z)

        rm = []
        for (cx, cz), c in self.chunks.items():
            d_sq = (cx - camera_chunk_x)**2 + (cz - camera_chunk_z)**2
            if d_sq > ulsq:
                rm.append((cx, cz))
                

        for key in rm:
            if key in self.modCache: del self.modCache[key]
            if key in self.loadedmods_cache: del self.loadedmods_cache[key]
            self.dirtychunks.discard(key)
            self.chunks[key].release()
            del self.chunks[key]
        
        
        if self.queue_chunkbuild:
            self.meshthread_event.set()
                
                
                
                
                
                
                
    def priorbuildq(self, cam_cx, cam_cz):
        if not self.queue_chunkbuild: return
        q = sorted(list(self.queue_chunkbuild), key=lambda c: (c.x - cam_cx)**2 + (c.z - cam_cz)**2)
        self.queue_chunkbuild = deque(q)
    
    
    
    
    def bake_mods(self):
        t0 = time.time()
        FRAME_BUDGET = 0.004  # 4ms budget

        qs = self.queue_meshupload.qsize()
        if qs == 0:
            return

        uploads = 0
        mu = 6 if qs > 20 else 4

        while not self.queue_meshupload.empty() and uploads < mu:
            el = time.time() - t0
            if el >= FRAME_BUDGET:
                break
            
            try:
                c, vb, vc, tvb, tvc = self.queue_meshupload.get_nowait()
                if (c.x, c.z) in self.chunks:
                    c.upload_mesh(vb, vc, tvb, tvc)
                    # scan for extruded ONCE per chunk (separate flag)
                    if not getattr(c, 'extruded_scanned', False):
                        c.extruded_scanned = True
                        self.regextruded(c)
                uploads += 1
                
            except Exception:
                break
    
    def regextruded(self, chunk):
        if not hasattr(self.world, 'render_extruded'):
            return
        renderer = self.world.render_extruded
        voxels = chunk.voxels
        ox, oz = int(chunk.offset_x), int(chunk.offset_z)
        #results = _scan_extruded_jit(voxels)
        for x, y, z, bt in results:
            renderer.add_block(ox + x, y, oz + z, bt)

    
    
    
    def issolid(self, x, y, z):
        if y < 0 or y >= CHUNK_H: return False
        c = self.chunks.get((x // CHUNK_SZ, z // CHUNK_SZ))
        if not c: return False
        lx, lz = x - c.offset_x, z - c.offset_z
        if 0 <= lx < CHUNK_SZ and 0 <= lz < CHUNK_SZ:
            b = c.voxels[lx, y, lz] & 0x3FF
            return b not in NONSOLID_BLOCKS
            
        return False



    def getblock(self, x, y, z):
        if y < 0 or y >= CHUNK_H: return 0
        c = self.chunks.get((x // CHUNK_SZ, z // CHUNK_SZ))
        if not c or not c.gen_ready: return 0
        lx, lz = x - c.offset_x, z - c.offset_z
        if 0 <= lx < CHUNK_SZ and 0 <= lz < CHUNK_SZ:
            return c.voxels[lx, y, lz] & 0x3FF
            
        return 0
    
    
    
    def getlight(self, x, y, z):
        if y < 0 or y >= CHUNK_H: return 0
        c = self.chunks.get((x // CHUNK_SZ, z // CHUNK_SZ))
        if not c or not c.gen_ready: return 0
        lx, lz = x - c.offset_x, z - c.offset_z
        if 0 <= lx < CHUNK_SZ and 0 <= lz < CHUNK_SZ:
            return int(c.light[lx, y, lz])
            
        return 0
    
    
    
    
    def rebuildc(self, chunk):
        if not chunk or not chunk.gen_ready: return
        verts, trans_verts = chunk.build_mesh()
        vb, vc = None, 0
        tvb, tvc = None, 0
        if verts is not None and len(verts) > 0:
            vb, vc = verts.tobytes(), len(verts) // 9
        if trans_verts is not None and len(trans_verts) > 0:
            tvb, tvc = trans_verts.tobytes(), len(trans_verts) // 9
            
        chunk.upload_mesh(vb, vc, tvb, tvc)
    
    
    
    
    
    def modsfile(self, cx, cz):
        return os.path.join(self.chunks_dir, f"{cx}_{cz}.dat")
        
        
    
    def preloadmods(self, cx, cz):
        key = (cx, cz)
        if key in self.loadedmods_cache: return
        fp = self.modsfile(cx, cz)
        if not os.path.exists(fp):
            self.loadedmods_cache[key] = {}
            return
        try:
            mods = {}
            with open(fp, 'rb') as f:
                
                data = f.read()
                if len(data) < 4:
                    self.loadedmods_cache[key] = {}
                    return
                count = struct.unpack('<I', data[:4])[0]
                off = 4
                
                for _ in range(count):
                    if off + 5 > len(data): break
                    lx, y, lz, bt = struct.unpack('<BBBH', data[off:off+5])
                    off += 5
                    if 0 <= lx < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= lz < CHUNK_SZ:
                        mods[(lx, y, lz)] = bt
                        
                        
            self.loadedmods_cache[key] = mods
            
            if self.ui and len(mods) > 0:
                self.ui.chatmsg(f"Loaded {len(mods)} block(s) for chunk ({cx}, {cz})", color=(200, 255, 200))
                
                
        except (struct.error, IOError) as e:
            emsg = f"Error loading chunk ({cx}, {cz}): {e}"
            print(emsg)
            if self.ui: self.ui.chatmsg(emsg, color=(255, 150, 150))
            self.loadedmods_cache[key] = {}
            
            
            
            
          
            
                
    
    def applymods(self, chunk):
        key = (chunk.x, chunk.z)
        mem_mods = self.modCache.get(key, {})
        
        if key not in self.loadedmods_cache:
            self.preloadmods(chunk.x, chunk.z)
            
        disk_mods = self.loadedmods_cache.get(key, {})
        mods = disk_mods.copy()
        mods.update(mem_mods)
        
        for (lx, y, lz), bt in mods.items():
            if 0 <= lx < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= lz < CHUNK_SZ:
                chunk.voxels[lx, y, lz] = bt
                
                
                
    
    def save_mods(self, cx, cz):
        if not self.is_server: return
        key = (cx, cz)
        
        if key not in self.modCache or len(self.modCache[key]) == 0: return
        mods = {(x, y, z): bt for (x, y, z), bt in self.modCache[key].items()}
        
        try: self.save_queue.put_nowait((cx, cz, mods))
        except Exception: self.save_queue.put((cx, cz, mods))
        
        
        
    
    
    
    
    def savemodsync(self, cx, cz, mods):
        if not self.is_server: return
        fp = self.modsfile(cx, cz)
        if mods is None or len(mods) == 0: return
        
        try:
            ext = {}
            if os.path.exists(fp):
                try:
                    
                    with open(fp, 'rb') as f:
                        data = f.read()
                        if len(data) >= 4:
                            cnt = struct.unpack('<I', data[:4])[0]
                            off = 4
                            
                            for _ in range(cnt):
                                if off + 5 > len(data): break
                                lx, ly, lz, bt = struct.unpack('<BBBH', data[off:off+5])
                                off += 5
                                ext[(lx, ly, lz)] = bt
                                
                                
                except Exception: pass
                    
                    
            fin = ext.copy() if ext else {}
            fin.update(mods)
            cnt = len(fin)
            buf = bytearray(4 + cnt * 5)
            struct.pack_into('<I', buf, 0, cnt)
            off = 4
            for (x, y, z), bt in fin.items():
                struct.pack_into('<BBBH', buf, off, x, y, z, bt)
                off += 5
            tmp = fp + '.tmp'
            
            
            with open(tmp, 'wb') as f:
                f.write(buf)
                f.flush()
                os.fsync(f.fileno())
                
            if os.path.exists(fp): os.replace(tmp, fp)
            else: os.rename(tmp, fp)
            
            
            
        except IOError as e:
            emsg = f"Error saving chunk ({cx}, {cz}): {e}"
            print(emsg)
            if self.ui: self.ui.chatmsg(emsg, color=(255, 150, 150))
            tmp = fp + '.tmp'
            if os.path.exists(tmp):
                os.remove(tmp)
                
                
                
                
                
                
                
    
    def recordmod(self, cx, cz, lx, y, lz, bt):
        key = (cx, cz)
        if key not in self.modCache: self.modCache[key] = {}
        self.modCache[key][(lx, y, lz)] = bt
        self.dirtychunks.add(key)
        
        if self.is_server:
            mods = {(x, y, z): b for (x, y, z), b in self.modCache[key].items()}
            try: self.save_queue.put_nowait((cx, cz, mods))
            except Exception: self.save_queue.put((cx, cz, mods))
            
            
    
    """
    def setblock(self, x, y, z, bt):
        if y < 0 or y >= CHUNK_H: return False
        cx, cz = x // CHUNK_SZ, z // CHUNK_SZ
        c = self.chunks.get((cx, cz))
        if not c or not c.gen_ready: return False
        lx, lz = x - c.offset_x, z - c.offset_z
        c.voxels[lx, y, lz] = bt
        c.mesh_built = False
        self.queue_chunkbuild.appendleft(c)
        self.meshthread_event.set()
        return True
    """
    
    

    def setblock(self, x, y, z, bt):
        # print(x, y, z, bt)
        if y < 0 or y >= CHUNK_H: return False
        cx, cz = x // CHUNK_SZ, z // CHUNK_SZ
        c = self.chunks.get((cx, cz))
        if not c or not c.gen_ready: return False
        
        lx, lz = x - c.offset_x, z - c.offset_z
        if 0 <= lx < CHUNK_SZ and 0 <= lz < CHUNK_SZ:
            c.voxels[lx, y, lz] = bt
            self.recordmod(cx, cz, lx, y, lz, bt)
            c.bakelight()
            c.mesh_built = False
            rbld = [c]
            nlit = []
            
            
            
            if lx == 0:
                n = self.chunks.get((cx - 1, cz))
                if n and n.gen_ready:
                    rbld.append(n); nlit.append(n)
                    
            elif lx == CHUNK_SZ - 1:
                n = self.chunks.get((cx + 1, cz))
                if n and n.gen_ready:
                    rbld.append(n); nlit.append(n)
                    

            if lz == 0:
                n = self.chunks.get((cx, cz - 1))
                if n and n.gen_ready:
                    rbld.append(n); nlit.append(n)
                    
            elif lz == CHUNK_SZ - 1:
                n = self.chunks.get((cx, cz + 1))
                if n and n.gen_ready:
                    rbld.append(n); nlit.append(n)
                    

            for n in nlit:
                n.bakelight()
                n.mesh_built = False
                
            if nlit:
                c.bakelight()

            for ch in rbld:
                ch.mesh_built = False
                self.rebuildc(ch)
                
            return True
            
            
        return False
        
        
        
        
        
        
    
    def breakblock(self, x, y, z):
        bt = self.getblock(x, y, z)
        
        if bt == 1:
            if y + 1 < CHUNK_H and self.getblock(x, y + 1, z) == 10:
                self.setblock(x, y + 1, z, 0)
                
        return self.setblock(x, y, z, 0)
        
        




    def batchbreak(self, positions):
        rm  = {}
        aff = {}   # (cx, cz) -> Chunk
        

        for (x, y, z) in positions:
            if y < 0 or y >= CHUNK_H:
                continue
                
                
            cx, cz = x // CHUNK_SZ, z // CHUNK_SZ
            c = self.chunks.get((cx, cz))
            if not c or not c.gen_ready:
                continue
                
                
            lx, lz = x - c.offset_x, z - c.offset_z
            if not (0 <= lx < CHUNK_SZ and 0 <= lz < CHUNK_SZ):
                continue


            old = c.voxels[lx, y, lz]
            if old == 0:
                continue
                

            c.voxels[lx, y, lz] = 0
            rm[(x, y, z)] = old
            self.recordmod(cx, cz, lx, y, lz, 0)
            aff[(cx, cz)] = c
            
            
            
            
            

            # mark neighbouring chunks dirty if on border
            if lx == 0:
                n = self.chunks.get((cx - 1, cz))
                if n and n.gen_ready:
                    aff[(cx - 1, cz)] = n
                    
            elif lx == CHUNK_SZ - 1:
                n = self.chunks.get((cx + 1, cz))
                if n and n.gen_ready:
                    aff[(cx + 1, cz)] = n
                    
            if lz == 0:
                n = self.chunks.get((cx, cz - 1))
                if n and n.gen_ready:
                    aff[(cx, cz - 1)] = n
                    
            elif lz == CHUNK_SZ - 1:
                n = self.chunks.get((cx, cz + 1))
                if n and n.gen_ready:
                    aff[(cx, cz + 1)] = n
                    



        for c in aff.values(): c.bakelight()
        for c in aff.values(): self.rebuildc(c)

        return rm
    
    
    
    
    
    
    
    
    
    
    
    def placeblock(self, x, y, z, bt=3, facing=0):
        if self.issolid(x, y, z): return False
        if y < 0 or y >= CHUNK_H: return False
        value = (bt & BLOCK_ID_MASK) | (facing << STATE_SHIFT) | 0x8000
        return self.setblock(x, y, z, value)
        
    
    def updatevischache(self, cam_pos, cam_front, far_plane):
        if self._cam_pos is not None and self._cam_front is not None:
            
            ds2 = (
                (cam_pos[0] - self._cam_pos[0])**2 + 
                (cam_pos[1] - self._cam_pos[1])**2 + 
                (cam_pos[2] - self._cam_pos[2])**2
            )
            
            dot = (
                cam_front[0] * self._cam_front[0] + 
                cam_front[1] * self._cam_front[1] + 
                cam_front[2] * self._cam_front[2]
            )
            
            tsq = self.updatecache_threshold * self.updatecache_threshold
            if ds2 < tsq and abs(1.0 - dot) <= 0.05: return
            
            

        self._cam_pos   = cam_pos.copy()   if isinstance(cam_pos,   np.ndarray) else np.array(cam_pos,   dtype='f4')
        self._cam_front = cam_front.copy() if isinstance(cam_front, np.ndarray) else np.array(cam_front, dtype='f4')

        cx, cy, cz   = cam_pos[0], cam_pos[1], cam_pos[2]
        max_d2       = (far_plane * 0.95) ** 2
        cfx, cfy, cfz = cam_front[0], cam_front[1], cam_front[2]
        
        

        hc   = CHUNK_SZ * 0.5
        hh   = CHUNK_H  * 0.5
        crsq = hc**2 + hh**2 + hc**2
        cr   = 65.0  # approx sqrt(crsq)

        vis = []
        for c in self.chunks.values():
            if not c.mesh_built: continue
            if c.vertex_count == 0 and c.trans_vertex_count == 0: continue

            dx = c.offset_x + hc - cx
            dy = hh - cy
            dz = c.offset_z + hc - cz
            d2 = dx*dx + dy*dy + dz*dz
            if d2 > max_d2: continue
            

            dp = dx * cfx + dy * cfy + dz * cfz
            if dp < -cr: continue

            # cull side-chunks behind cam: dot^2 / d2 < cos(-0.3)^2 = 0.09
            if dp < 0 and d2 > crsq * 4:
                dp2 = dp * dp
                if dp2 > 0.09 * d2:  # cos_angle < -0.3
                    continue

            vis.append((d2, c))

        vis.sort(key=lambda x: x[0])
        self.vischunk_cache = [c for _, c in vis]
        
        
        
        
        
    
    def renderall(self, cam_pos=None, cam_front=None, far_plane=500.0, pass_type=0):
        t    = time.time()
        fdur = 0.5
        rendered = 0
        

        if cam_pos is not None and cam_front is not None and pass_type == 0:
            self.updatevischache(cam_pos, cam_front, far_plane)

        rlist = self.vischunk_cache if self.vischunk_cache else [c for c in self.chunks.values() if c.mesh_built]
        
        

        fading, full = [], []
        for c in rlist:
            
            
            hd = (c.vertex_count > 0) if pass_type == 0 else (c.trans_vertex_count > 0)
            if not hd: continue

            if c.birth_time is None or t - c.birth_time >= fdur:
                full.append(c)
                
            else:
                fading.append(((t - c.birth_time) / fdur, c))
                
                
                
                
        
        if full:
            self.world.prog['chunk_fade'].value = 1.0
            for c in full:
                c.render(pass_type)
                rendered += 1
                
                
        for f, c in fading:
            self.world.prog['chunk_fade'].value = f
            c.render(pass_type)
            rendered += 1
            
            
        return rendered
        
        
        
        
    
    def shutdown(self):
        if self.is_server:
            
            for cx, cz in list(self.dirtychunks):
                self.save_mods(cx, cz)
            self.io_thread_active = False
            t = 10.0
            
            while not self.save_queue.empty() and t > 0:
                threading.Event().wait(0.1)
                t -= 0.1
            self.io_thread.join(timeout=2.0)
            
            
        else:
            self.io_thread_active = False
            self.io_thread.join(timeout=2.0)
            
            
        self.mesh_thread_active = False
        self.meshthread_event.set()
        self.mesh_thread.join(timeout=2.0)
        self.terrain_executor.shutdown(wait=False)
        for c in self.chunks.values(): c.release()















































































