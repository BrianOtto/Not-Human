import numpy as np
import threading
import time
import moderngl
from config import CHUNK_SZ, CHUNK_H, SEA_LEVEL
from world.trees import treetochunk, grasstochunk, cactitochunk
from world.decor import addchunkrocks
from world.blocks import (
    NONSOLID_BLOCKS,
    _FACINGTYPE, HOR_UV_REMAP, AXIS_UV_REMAP, AXIS_UV_ROT,
    UV_ARRAY, UV_W, UV_H,
)
from world.renderers.registry import (
    BLOCK_MODE_RENDER, BLOCK_CUSTOM_FACES,
    NUM_ELEMENTS, BLOCK_ELEMS, BLOCK_MODE_UV, CULL_TOPBOT,
    BLOCK_UVS, BLOCK_TEX,
    CONNECT_TYPE, CONNECT_FAMILY,
    BLOCK_ARM_NUM, BLOCK_ARM_ELEM, BLOCK_ARM_FUVS, BLOCK_ARM_FTEX,
    STATE_ELEM_OFF, STATE_ELEM_NUM,
)
from world.generate import _generate
from world.mesh import (
    bakelight, build_meshjit, BLOCK_EMIT,
    BUILD_FACE_V, BUILD_FACE_N, BUILD_FACE_UV, MESH_GRASS_V,
)

EMPTY_VOXEL = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint16)
EMPTY_LIGHT = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint8)




class PerlinNoise:
    def __init__(self, seed=0):
        # no idea
        # sourced from rips of MC beta 1.7.3
        p_base = np.array([
            151,160,137,91,90,15,131,13,201,95,96,53,194,233,7,225,
            140,36,103,30,69,142,8,99,37,240,21,10,23,190,6,148,
            247,120,234,75,0,26,197,62,94,252,219,203,117,35,11,32,
            57,177,33,88,237,149,56,87,174,20,125,136,171,168,68,175,
            74,165,71,134,139,48,27,166,77,146,158,231,83,111,229,122,
            60,211,133,230,220,105,92,41,55,46,245,40,244,102,143,54,
            65,25,63,161,1,216,80,73,209,76,132,187,208,89,18,169,
            200,196,135,130,116,188,159,86,164,100,109,198,173,186,3,64,
            52,217,226,250,124,123,5,202,38,147,118,126,255,82,85,212,
            207,206,59,227,47,16,58,17,182,189,28,42,223,183,170,213,
            119,248,152,2,44,154,163,70,221,153,101,155,167,43,172,9,
            129,22,39,253,19,98,108,110,79,113,224,232,178,185,112,104,
            218,246,97,228,251,34,242,193,238,210,144,12,191,179,162,241,
            81,51,145,235,249,14,239,107,49,192,214,31,181,199,106,157,
            184,84,204,176,115,121,50,45,127,4,150,254,138,236,205,93,
            222,114,67,29,24,72,243,141,128,195,78,66,215,61,156,180
        ], dtype=np.int32)
        np.random.seed(seed)
        np.random.shuffle(p_base)
        self.p = np.concatenate([p_base, p_base])








class Chunk:
    
    def __init__(self, x, z, world):
        self.x, self.z, self.world = x, z, world
        self.voxels = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint16)
        self.light  = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint8)
        self.blight = np.zeros((CHUNK_SZ, CHUNK_H, CHUNK_SZ), dtype=np.uint8)
        self.mesh_built = False
        self.mesh_pending = False  # prevent re-queueing while mesh is being built
        self.gen_ready = False
        self.lighting_settled = False
        self.light_dirty = True
        self.vao = None
        self.vbo = None
        self.vertex_count = 0
        self.trans_vao = None
        self.trans_vbo = None
        self.trans_vertex_count = 0
        self.birth_time = None
        self.offset_x = x * CHUNK_SZ
        self.offset_z = z * CHUNK_SZ
        self._render_lock = threading.Lock()
        
        
    
    def genchunk(self):
        if self.gen_ready: return
        _MAX = 10000
        if abs(self.x) > _MAX or abs(self.z) > _MAX:
            self.gen_ready = True
            return
        


        
        off_x = np.clip(float(self.offset_x), -1e6, 1e6)
        off_z = np.clip(float(self.offset_z), -1e6, 1e6)
        biomes = np.zeros((CHUNK_SZ, CHUNK_SZ), dtype=np.int8)
        _generate(self.voxels, off_x, off_z, self.world.noise.p, biomes)

        if hasattr(self.world, 'trees') and self.world.trees:
            treetochunk(
                self.voxels, self.offset_x, self.offset_z, 
                self.world.trees, self.world.seed, 
                self.world.noise.p, self.world.chunker, 
                CHUNK_SZ, CHUNK_H, SEA_LEVEL, 
                biomes
            )
            

        key = (self.x, self.z)
        if key in self.world.chunker.pending_decorations:
            for lx, ly, lz, bt in self.world.chunker.pending_decorations[key]:

                if 0 <= lx < CHUNK_SZ and 0 <= ly < CHUNK_H and 0 <= lz < CHUNK_SZ:
                    if bt in [7, 8, 9] and self.voxels[lx, ly, lz] in [0, 1]:
                        self.voxels[lx, ly, lz] = bt


            del self.world.chunker.pending_decorations[key]

        if hasattr(self.world, 'rocks') and self.world.rocks:
            addchunkrocks(
                self.voxels, self.offset_x, self.offset_z, 
                self.world.rocks, self.world.seed, 
                self.world.noise.p, self.world.chunker, 
                CHUNK_SZ, CHUNK_H, SEA_LEVEL
            )

        if hasattr(self.world, 'trees'):
            grasstochunk(
                self.voxels, self.offset_x, self.offset_z, 
                self.world.seed, self.world.noise.p, biomes, 
                CHUNK_SZ, CHUNK_H, SEA_LEVEL
            )
            
            cactitochunk(
                self.voxels, self.offset_x, self.offset_z, 
                biomes, self.world.seed, 
                CHUNK_SZ, CHUNK_H, SEA_LEVEL
            )
            
            
            
            
        
        self.world.chunker.applymods(self)
        self.gen_ready = True
        self.light_dirty = True

        # headless keeps voxels only, no light/mesh
        if self.world.chunker.headless: return

        self.bakelight()



        chunks = self.world.chunker.chunks
        mq = self.world.chunker.mesh_build_queue

        for dx, dz in [(-1,0), (1,0), (0,-1), (0,1)]:
            n = chunks.get((self.x + dx, self.z + dz))
            if n and n.gen_ready and not n.mesh_pending:
                n.mesh_pending = True
                n.light_dirty = True
                mq.append(n)
                
                
    



    def bakelight(self):
        chunks = self.world.chunker.chunks
        
        def get_neighbor_light(dx, dz):
            c = chunks.get((self.x + dx, self.z + dz))
            return (c.light, c.blight) if c and c.gen_ready else (EMPTY_LIGHT, EMPTY_LIGHT)

        l_nx, b_nx = get_neighbor_light(-1, 0)
        l_px, b_px = get_neighbor_light(1, 0)
        l_nz, b_nz = get_neighbor_light(0, -1)
        l_pz, b_pz = get_neighbor_light(0, 1)

        bakelight(
            self.voxels, self.light, self.blight,
            l_nx, l_px, l_nz, l_pz,
            b_nx, b_px, b_nz, b_pz,
            BLOCK_EMIT
        )
        self.light_dirty = False
        
        
        
        
    
    def is_solid(self, x, y, z):
        if 0 <= x < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= z < CHUNK_SZ:
            b = self.voxels[x, y, z]
            return b not in NONSOLID_BLOCKS
            
        return self.world.issolid(self.offset_x + x, y, self.offset_z + z)
        
        
        
        
        
        
        
    
    def build_mesh(self):
        chunks = self.world.chunker.chunks
        
        def get_neighbor_voxels(dx, dz):
            c = chunks.get((self.x + dx, self.z + dz))
            return c.voxels if c and c.gen_ready else EMPTY_VOXEL

        def get_neighbor_light(dx, dz):
            c = chunks.get((self.x + dx, self.z + dz))
            return (c.light, c.blight) if c and c.gen_ready else (self.light, self.blight)

            

        if self.x == 0 and self.z == 0 and hasattr(self.world.chunker, 'ui') and self.world.chunker.ui:
            ck = (self.x, self.z)
            ct = time.time()


            if (ck not in self.world.chunker.debugmsg_lastchunk or
                ct - self.world.chunker.debugmsg_lastchunk[ck] > self.world.chunker.debugmsg_cool):
                nx = chunks.get((-1, 0))
                px = chunks.get((1, 0))
                nz = chunks.get((0, -1))
                pz = chunks.get((0, 1))
                nxs = nx is not None and nx.gen_ready
                pxs = px is not None and px.gen_ready
                nzs = nz is not None and nz.gen_ready
                pzs = pz is not None and pz.gen_ready

                self.world.chunker.ui.chatmsg(
                    f"Chunk(0,0) neighbors: NX={nxs}, PX={pxs}, NZ={nzs}, PZ={pzs}",
                    color=(150, 200, 255)
                )
                
                self.world.chunker.debugmsg_lastchunk[ck] = ct
                
                

        v_nx, v_px = get_neighbor_voxels(-1, 0), get_neighbor_voxels(1, 0)
        v_nz, v_pz = get_neighbor_voxels(0, -1), get_neighbor_voxels(0, 1)
        l_nx, b_nx = get_neighbor_light(-1, 0)
        l_px, b_px = get_neighbor_light(1, 0)
        l_nz, b_nz = get_neighbor_light(0, -1)
        l_pz, b_pz = get_neighbor_light(0, 1)
        
        
        

        vertices, tverts = build_meshjit(
            self.voxels, float(self.offset_x), float(self.offset_z), 
            v_nx, v_px, v_nz, v_pz,
            self.light, l_nx, l_px, l_nz, l_pz,
            self.blight, b_nx, b_px, b_nz, b_pz,
            
            UV_ARRAY, UV_W, UV_H, BLOCK_CUSTOM_FACES, 
            BLOCK_MODE_RENDER, NUM_ELEMENTS, BLOCK_ELEMS, BLOCK_MODE_UV, 
            CULL_TOPBOT, BUILD_FACE_V, BUILD_FACE_N, BUILD_FACE_UV, 
            MESH_GRASS_V, _FACINGTYPE, HOR_UV_REMAP, AXIS_UV_REMAP, AXIS_UV_ROT, 
            BLOCK_UVS, BLOCK_TEX, CONNECT_TYPE, CONNECT_FAMILY, 
            BLOCK_ARM_NUM, BLOCK_ARM_ELEM, BLOCK_ARM_FUVS, BLOCK_ARM_FTEX, 
            STATE_ELEM_OFF, STATE_ELEM_NUM
        )
        
        return vertices, tverts
        
        
        
        
    
    def upload_mesh(self, data, count, trans_data, trans_count):

        # double-buffer: build new buffers first, then atomically swap
        if not hasattr(self.world, 'ctx') or self.world.ctx is None: return
        nvao, nvbo     = None, None
        ntvao, ntvbo   = None, None
        nvc  = 0
        ntvc = 0

        if data is not None and count > 0:
            nvc  = count
            nvbo = self.world.ctx.buffer(data)
            nvao = self.world.ctx.vertex_array(
                self.world.prog, [(nvbo, '3f 3f 2f', 'in_pos', 'in_lit', 'in_uv')]
            )
            

        if trans_data is not None and trans_count > 0:
            ntvc  = trans_count
            ntvbo = self.world.ctx.buffer(trans_data)
            ntvao = self.world.ctx.vertex_array(
                self.world.prog, [(ntvbo, '3f 3f 2f', 'in_pos', 'in_lit', 'in_uv')]
            )
            
            
            
            
            

        with self._render_lock:
            ovao, ovbo   = self.vao, self.vbo
            otvao, otvbo = self.trans_vao, self.trans_vbo
            self.vao, self.vbo           = nvao, nvbo
            self.trans_vao, self.trans_vbo = ntvao, ntvbo
            self.vertex_count       = nvc
            self.trans_vertex_count = ntvc
            self.mesh_built   = True
            self.mesh_pending = False

            if self.birth_time is None:
                self.birth_time = time.time()
                
                
                
                

        # release old buffers outside lock to avoid GPU stalls
        if ovao:  ovao.release()
        if ovbo:  ovbo.release()
        if otvao: otvao.release()
        if otvbo: otvbo.release()
        
        
        
        
        
        
        
        
        
        
        
        
    
    def render(self, pass_type=0):
        if not self.mesh_built: return
        if pass_type == 0:
            vao = self.vao
            
            if vao and self.vertex_count > 0:
                vao.render(moderngl.TRIANGLES, vertices=self.vertex_count)
                
                
        else:
            tvao = self.trans_vao
            if tvao and self.trans_vertex_count > 0:
                tvao.render(moderngl.TRIANGLES, vertices=self.trans_vertex_count)
                
                
    
    def release(self):
        
        with self._render_lock:
            if self.vao: self.vao.release(); self.vao = None
            if self.vbo: self.vbo.release(); self.vbo = None
            if self.trans_vao: self.trans_vao.release(); self.trans_vao = None
            if self.trans_vbo: self.trans_vbo.release(); self.trans_vbo = None
            
            self.mesh_built = False
            self.vertex_count = 0
            self.trans_vertex_count = 0































