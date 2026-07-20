import moderngl
import numpy as np
import pygame
from   pygame.locals import *
import socket
import threading
import time
import math
import sys
import os
import json
if getattr(sys, 'frozen', False):
    sys.path.insert(0, os.path.dirname(sys.executable))

from engine.camera import Camera
from entity.player.player import Player
from world.terrain import ChunkManager, PerlinNoise, get_biome, BIOME_NAMES

from world.blocks import (
    _FACINGTYPE, FACINGNONE, FACING_H, FACING_AX,
    FACE_N, FACE_S, FACE_E, FACE_W,
    AXY, AXX, AXZ,
)


import config
from config import (
    CHUNK_SZ, CHUNK_H, SEA_LEVEL, WIN_W, WIN_H,
    RENDER_DIST, SEED, SV_PORT, WATER_OFF,
    WATER_PLANE, SUN_SZ, HLIGHT_SCL, LINE_W,
    SCL_HUD, F_PLANE
)


import shaders
from ui.menu import UIManager
from network.client import NetworkClient
from entity.player.model import PlayerModel
from ui.hud import HUDManager
from ui.inv import Inventory
from engine.particle import ParticleManager
from entity.item.item import ItemEntityManager
from entity.player._held import HeldItemRenderer
import _respath
from commands.manager import CommandManager
from items import textures as text_items
from world.animation import getanims
from world.renderers.extruded import ExtrudedRenderer
from engine.gamma import Gamma
from entity.blockenty import BlockEntityManager, itemblock
import keys






class VoxelWorld:
    def __init__(self, wname="default", svaddr=None, seed=None, managed=False):
        if not managed: pygame.init()
        self.managed = managed

        self._fs   = False
        self._scrw = WIN_W
        self._scrh = WIN_H

        self.screen = pygame.display.set_mode((WIN_W, WIN_H), OPENGL | DOUBLEBUF)
        pygame.display.set_caption("Kyklophobia")
        ico = pygame.image.load('icon.ico') 
        pygame.display.set_icon(ico)
        pygame.mouse.set_visible(False)
        pygame.event.set_grab(True)
        
        self.ctx = moderngl.create_context()
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.CULL_FACE)
        self.ctx.line_width = LINE_W
        
        self.prog = self.ctx.program(
            vertex_shader   = shaders.load("terrain.vert"),
            fragment_shader = shaders.load("terrain.frag")
        )
        
        
        self.sun_angle = 60.0
        self.sun_dir = np.array([0.5, 1.0, 0.1], dtype='f4')
        self.sun_dir = self.sun_dir / np.linalg.norm(self.sun_dir)
        self.sun_pos = np.array([0.0, 0.0, 0.0], dtype='f4')
        
        

        img = pygame.image.load(_respath.atlas_block()).convert_alpha()
        img = pygame.transform.flip(img, False, True)
        self.texture = self.ctx.texture(
            img.get_size(), 4, 
            pygame.image.tostring(img, "RGBA")
        )
        
        self.texture.filter = (
            moderngl.NEAREST, 
            moderngl.NEAREST
        )
        
        self.texture.use(0)
        self.prog['texture0'].value = 0
        
        
        
        
        
        _grassimg = pygame.image.load(_respath.clrmap_grass()).convert_alpha()
        _grassimg = pygame.transform.flip(_grassimg, False, True)
        self.text_grass = self.ctx.texture(
            _grassimg.get_size(), 4, 
            pygame.image.tostring(_grassimg, "RGBA")
        )
        
        
        self.text_grass.filter = (
            moderngl.LINEAR, 
            moderngl.LINEAR
        )
        
        self.text_grass.use(1)
        self.prog['clrmap_grass'].value = 1
        
        
        
        
        
        
        _folimg = pygame.image.load(_respath.clrmap_folage()).convert_alpha()
        _folimg = pygame.transform.flip(_folimg, False, True)
        
        self.text_fol = self.ctx.texture(
            _folimg.get_size(), 4, 
            pygame.image.tostring(_folimg, "RGBA")
        )
        
        self.text_fol.filter = (
            moderngl.LINEAR, 
            moderngl.LINEAR
        )
        
        self.text_fol.use(2)
        self.prog['clrmap_folage'].value = 2
            
        anims  = getanims()
        _meta  = anims.surfaceatlas()
        _metaf = pygame.transform.flip(_meta, False, True)
        
        self.text_meta = self.ctx.texture(
        
            _metaf.get_size(), 4,
            pygame.image.tostring(_metaf, "RGBA")
        )
        
        self.text_meta.filter = (
            moderngl.NEAREST,
            moderngl.NEAREST
        )
        
        self.text_meta.use(3)
        self.prog['meta_atlas'].value = 3
        self.meta_sz = anims.szatlas()
        self.prog['chunk_fade'].value = 1.0
        
        
        
        

        self.particles = ParticleManager(self.ctx, texture=self.texture)
        self.itementys       = None
        self.render_helditem = None
        self.render_extruded = None
        self.gamma_shader    = None
        

        self.wireprog = shaders.prog(self.ctx, "wireframe.vert", "wireframe.frag")
        wverts = np.array(
            [
                # bot
                0,0,0, 1,0,0,
                1,0,0, 1,0,1,
                1,0,1, 0,0,1,
                0,0,1, 0,0,0,
                # top
                0,1,0, 1,1,0,
                1,1,0, 1,1,1,
                1,1,1, 0,1,1,
                0,1,1, 0,1,0,
                # verts
                0,0,0, 0,1,0,
                1,0,0, 1,1,0,
                1,0,1, 1,1,1,
                0,0,1, 0,1,1,
            ], dtype='f4'
        )
        
        self.wirevbo = self.ctx.buffer(wverts.tobytes())
        self.wirevao = self.ctx.vertex_array(
            self.wireprog, [(self.wirevbo, '3f', 'in_pos')]
        )
        
        

        cb = np.array(
            [
                0,0,0, 
                CHUNK_SZ,0,      0, 
                CHUNK_SZ,0,      0, 
                CHUNK_SZ,0,      CHUNK_SZ, 
                CHUNK_SZ,0,      CHUNK_SZ, 
                0,       0,      CHUNK_SZ, 
                0,       0,      CHUNK_SZ, 
                0,       0,      0,
                
                0,       CHUNK_H,0, 
                CHUNK_SZ,CHUNK_H,0, 
                CHUNK_SZ,CHUNK_H,0, 
                CHUNK_SZ,CHUNK_H,CHUNK_SZ, 
                CHUNK_SZ,CHUNK_H,CHUNK_SZ, 
                0,       CHUNK_H,CHUNK_SZ, 
                0,       CHUNK_H,CHUNK_SZ, 
                0,       CHUNK_H,0,
                
                0,       0,      0, 
                0,       CHUNK_H,0, 
                CHUNK_SZ,0,      0, 
                CHUNK_SZ,CHUNK_H,0, 
                CHUNK_SZ,0,      CHUNK_SZ, 
                CHUNK_SZ,CHUNK_H,CHUNK_SZ, 
                0,       0,      CHUNK_SZ, 
                0,       CHUNK_H,CHUNK_SZ
            ], dtype='f4'
        )
        self.bordervbo = self.ctx.buffer(cb.tobytes())
        self.bordervao = self.ctx.vertex_array(
            self.wireprog, [(self.bordervbo, '3f', 'in_pos')]
        )
        

        self.pmodel = PlayerModel(self.ctx, _spath=_respath.text_player())
        self.sunprog = self.ctx.program(
            vertex_shader   = shaders.load("sun.vert"),
            fragment_shader = shaders.load("sun.frag")
        )
        
        soffs = np.array(
            [-1,-1, 1,-1, 1,1, -1,-1, 1,1, -1,1], dtype='f4'
        )
        self.sunvbo = self.ctx.buffer(soffs.tobytes())
        self.sunvao = self.ctx.vertex_array(
            self.sunprog, [(self.sunvbo, '2f', 'in_offset')]
        )
        
        
        self.tagprog = self.ctx.program(
            vertex_shader=shaders.load("nametag.vert"),
            fragment_shader=shaders.load("nametag.frag")
        )
        tagquad = np.array(
            [
                -0.5, -0.5, 0, 1, 
                 0.5, -0.5, 1, 1, 
                 0.5,  0.5, 1, 0, 
                -0.5, -0.5, 0, 1, 
                 0.5,  0.5, 1, 0, 
                -0.5,  0.5, 0, 0
            ], dtype='f4'
        )
        self.tagvbo = self.ctx.buffer(tagquad.tobytes())
        self.tagvao = self.ctx.vertex_array(
            self.tagprog, [(self.tagvbo, '2f 2f', 'in_offset', 'in_uv')]
        )
        

        from world.trees import TreeManager
        from world.decor import RockManager
        from ui.bfont import Font

        self.text_tag = {}
        self.font_tag = Font(_respath.text_font(), scale=1)

        self.wname    = wname
        self.svaddr   = svaddr
        self.seed     = seed if seed is not None else SEED
        self.noise    = PerlinNoise(seed=self.seed)
        
        self.trees = TreeManager(assetdir="assets")
        self.rocks = RockManager(assetdir="assets")
        self.ui       = UIManager(self.ctx, (WIN_W, WIN_H))
        self.hud      = HUDManager(self.ctx, (WIN_W, WIN_H))
        
        
        self.p   = Player(
            self, pos=np.array([0.0, 80.0, 0.0], dtype='f4')
        )
        self.p.ui = self.ui
        self.p.inv = Inventory()
        
        
        
        for i, c in [
                (1,  64), (2,  64), (3,  64),
                (12, 64), (6,  64), (7,  64),
                (8,  64), (14, 64), (11, 64),
                (4,  64), (5,  1),  (9,  64),
                (10, 64), (13, 64), (20, 64)
            ]:
            self.p.inv.add(i, c)

        self.p.inv.add(text_items.DIAMOND_SWORD,   1)
        self.p.inv.add(text_items.APPLE,          64)
        self.p.inv.add(60, 16) #tnt
        self.p.inv.add(text_items.FLINT_AND_STEEL, 1)
        
        
        
        
        
        
        

        from version import __VERSION__
        d = os.path.join(config.root, wname)
        os.makedirs(d, exist_ok=True)
        
        f = os.path.join(d, "VERSION")
        if not os.path.exists(f):
            with open(f, 'w') as f:
                f.write(__VERSION__ + '\n')
                

        self.chunker       = ChunkManager(self, render_dist=RENDER_DIST, wname=wname, is_server=True)
        self.chunker.ui    = self.ui
        self.itementys    = ItemEntityManager(self.ctx, self.texture, self)
        self.render_helditem = HeldItemRenderer(self.ctx, self.itementys)
        self.render_extruded = ExtrudedRenderer(self.ctx)
        self.ui.chatmsg("World loaded!", color=(200, 200, 200))
        self.clock = pygame.time.Clock()
        

        pf = os.path.join(config.root, wname, "player.json")
        if os.path.exists(pf):
            try:
                with open(pf) as f:  pd = json.load(f)
                if 'pos' in pd: self.p.teleport(np.array(pd['pos'], dtype='f4'))
                if 'yaw' in pd:      self.p.cam.yaw = float(pd['yaw'])
                if 'pitch' in pd:    self.p.cam.pitch = float(pd['pitch'])
                
            except Exception:
                pass
                
                

        cx, cz = self.p.chunkpos(CHUNK_SZ)
        self.chunker.updateloads(cx, cz)
        
        self.showborder  = False
        self.showhud     = True
        self.showdebug   = True
        self.netclient   = None
        self.is_client   = False
        self._dcreq      = None
        self.svport      = SV_PORT
        self.pchg        = set()
        self.pupdates    = []
        self._uplock     = threading.Lock()
        self._wup        = np.array([0.0, 1.0, 0.0], dtype='f4')
        self._cachedmvp  = None
        self._cachedpos  = None
        self._resetreq   = False
        self._nxtseed    = None
        self._pspawn     = None
        self.statelock   = threading.Lock()
        self.pmodpay     = None
        self.oninv       = False
        self.onchat      = False
        self.tabdown     = False
        self.ibuff       = ""
        self.commands = CommandManager()
        self.ptasks      = []
        self._tlock      = threading.Lock()
        
        self.blockentys   = BlockEntityManager(self.ctx, self.texture)
        
        
        
        self.gamma_shader = Gamma(self.ctx, WIN_W, WIN_H)
        self.gamma_shader.setgamma(2.0)





    def getstack(self):
        slot = self.p._slot
        if 0 <= slot < 9: return self.p.inv.slots[slot]
        return None
        
        
        

    def bakefacing(self, blockId, _placement):

        ft = _FACINGTYPE[blockId]
        # print(ft, _placement)
        if ft == FACINGNONE: return 0
        
        
        if ft == FACING_H:
            front = self.p.cam.front
            fx, fz = -front[0], -front[2]
            if abs(fx) > abs(fz):
                return FACE_E if fx > 0 else FACE_W
            return FACE_S if fz > 0 else FACE_N
            
        if ft == FACING_AX:
            if _placement is None: return AXY
            dx, dy, dz = _placement
            if dy != 0: return AXY
            if dx != 0: return AXX
            return AXZ
            
        return 0
        
        
        
        
        
        

    def issolid(self, x, y, z):
        return self.chunker.issolid(x, y, z)

    def onevent(self, events):
        return keys.onEvent(self, events)
        


    def run(self):
        _fc      = 0
        running  = True
        while running:
            if self._dcreq:
                print(f"back to launcher: {self._dcreq}")
                running = False
                continue

            if self._resetreq:
                self.resetworld()
                self._resetreq = False
                
            # t0 = time.perf_counter()
            dt = self.clock.tick(60) / 1000.0

            if not self.onevent(pygame.event.get()):
                running = False
                continue

            if not self.oninv and not self.onchat:
                self.p.oninput(dt)
                self.p.onmouse()
                
                
                

            self.p.update(dt)
            self.particles.update(dt)
            self.blockentys.update(dt, {
                'chunker':    self.chunker,
                'particles':  self.particles,
                'player':        self.p,
                'netclient':     self.netclient,
                'blockentys': self.blockentys,
            })
            
            getanims().update(dt)
            pp = self.p.getpos()
            
            
            
            
            
            if self.netclient and self.netclient.isconn():
                self.itementys.update(dt, pp, self.p.inv, self.netclient)
            else: self.itementys.update(dt, pp, self.p.inv, None)
            
            
            
            if self.netclient and self.netclient.isconn():
                hid    = self.p.getsel() or 0
                aflags = 0
                if self.p.is_breaking or self.p.is_placing: aflags |= 1  # swing
                if self.p.crouching: aflags |= 2  # sneak
                
                self.netclient.sendpos(
                    pp,
                    self.p.cam.yaw,
                    self.p.cam.pitch,
                    hid,
                    aflags
                )
                
                self.netclient.interp(dt)
                
                
                
                
                
            self.applyupdates()
            self.flush()
            
            cx, cz = self.p.chunkpos(CHUNK_SZ)
            self.chunker.updateloads(cx, cz)
            self.chunker.bake_mods()
            

            mvp  = self.p.cam.mvpmat(inverted=(self.p.cmode == 2))
            cpos = self.p.cam.pos
            cfr  = self.p.cam.front
            far  = F_PLANE
            
            rad   = math.radians(self.sun_angle)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            sd    = np.array([cos_r, sin_r, 0.1], dtype='f4')
            norm  = math.sqrt(cos_r*cos_r + sin_r*sin_r + 0.01)
            sd[0] /= norm; sd[1] /= norm; sd[2] /= norm
            self.sun_dir = sd
            self.sun_pos = (cpos + sd * min(0.8 * far, 300.0)).astype('f4')
            self.prog['sun_pos'].write(sd.tobytes())
            mvpb         = mvp.astype('f4').tobytes()
            
            anims = getanims()
            adat = []
            
            
            
            
            if self.text_meta:
                from world import blocks
                from world.animation import ANIM_TEXT
                
                
                c = 0
                for i in ANIM_TEXT:
                    if i not in blocks.TEXTURES: continue

                    suv = blocks.getuv(i)
                    if isinstance(suv, tuple):
                        su, sv = suv
                    else: continue

                    cs, _, _ = anims.atlaslayout(i)
                    _frame = anims.getframe(i)
                    tsz    = 16.0
                    mu = cs * (tsz / self.meta_sz[0])
                    mv = 1.0 - (_frame + 1) * (tsz / self.meta_sz[1])
                    adat.append([su, sv, mu, mv])
                    c += 1
                    
                
                while len(adat) < 10:
                    adat.append([0.0, 0.0, 0.0, 0.0])
                
                self.prog['num_animated'].value    = min(c, 10)
                self.prog['meta_szatlas'].value = (float(self.meta_sz[0]), float(self.meta_sz[1]))
                aarr = np.array(adat[:10], dtype='f4')
                self.prog['adat'].write(aarr.tobytes())
                
            else:
                self.prog['num_animated'].value = 0
                self.prog['meta_szatlas'].value = (16.0, 16.0)
            
            if self.gamma_shader.enabled:
                self.gamma_shader.fbo.use()
                self.gamma_shader.fbo.clear(0.5, 0.7, 1.0)

            else:
                self.ctx.screen.use()
                self.ctx.viewport = (0, 0, self._scrw, self._scrh)
                self.ctx.clear(0.5, 0.7, 1.0)
                
                
                
                

            self.texture.use(0)
            self.prog['mvp'].write(mvpb)

            self.ctx.disable(moderngl.BLEND)
            rendered = self.chunker.renderall(cpos, cfr, far, pass_type=0)

            self.ctx.enable(moderngl.BLEND)
            self.chunker.renderall(cpos, cfr, far, pass_type=1)
            self.ctx.disable(moderngl.BLEND)

            self.texture.use(0)
            self.particles.render(mvp, cfr, cpos)
            
            self.itementys.render(mvp, self.sun_dir)
            self.blockentys.render(mvp, self.sun_dir)

            self.render_extruded.render(mvp, ambient=0.4)
            
            targetb, targetf = self.p.targetblock(5.0)
            if targetb:
                self.ctx.enable(moderngl.BLEND)
                self.wireprog['mvp'].write(mvpb)
                self.wireprog['offset'].value = targetb
                self.wirevao.render(moderngl.LINES)
                self.ctx.disable(moderngl.BLEND)
            
            if self.showborder:
                self.ctx.enable(moderngl.BLEND)
                self.wireprog['mvp'].write(mvpb)
                for c in self.chunker.chunks.values():
                    self.wireprog['offset'].value = (c.offset_x, 0.0, c.offset_z)
                    self.bordervao.render(moderngl.LINES)
                self.ctx.disable(moderngl.BLEND)
                
                
            
            
            
            
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            self.sunprog['mvp'].write(mvpb)
            self.sunprog['sun_pos'].write(self.sun_pos.tobytes())
            
            front =-self.p.cam.front if self.p.cmode == 2 else self.p.cam.front
            
            
            cr = np.cross(front, self._wup)
            n = np.linalg.norm(cr)
            if n > 0: cr /= n
            
            cu = np.cross(cr, front)
            n = np.linalg.norm(cu)
            if n > 0: cu /= n
            
            
            self.sunprog['cam_r'].write(cr.astype('f4').tobytes())
            self.sunprog['cam_u'].write(cu.astype('f4').tobytes())
            self.sunprog['sun_sz'].value = SUN_SZ
            self.sunvao.render(moderngl.TRIANGLES)
            self.ctx.disable(moderngl.BLEND)
            
            
            
            
            if self.netclient and self.netclient.isconn():
                self.renderrmtplayer(mvp, dt)
                
                
            
            r_arm, l_arm, r_leg, l_leg, r_arm_z, l_arm_z = self.p.animangles()
            ppos   = self.p.getpos()
            pbyaw  = self.p.byaw
            ppitch = self.p.cam.pitch
            
            # head pitch compensated for body crouch tilt
            ppitch   += self.p._smthcrouch * 28.6479
            phead_yaw = self.p.headyawoff
            
            self.ctx.enable(moderngl.DEPTH_TEST)
            self.ctx.disable(moderngl.CULL_FACE)
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            
            self.pmodel.render(mvp, ppos, pbyaw, ppitch, self.sun_pos,
                r_arm=r_arm,
                l_arm=l_arm, 
                r_leg=r_leg, 
                l_leg=l_leg,
                r_arm_z=r_arm_z, 
                l_arm_z=l_arm_z,
                headyawoff=phead_yaw,
                crouch=self.p._smthcrouch,
                _hidehead=(self.p.cmode == 0)
            )
            
            
            
            
            
            
            
            self.render_helditem.render(mvp, self.p, self.sun_dir)
            
            self.ctx.enable(moderngl.CULL_FACE)
            self.ctx.disable(moderngl.BLEND)
            
            if self.gamma_shader.enabled:
                self.ctx.screen.use()
                self.ctx.viewport = (0, 0, self._scrw, self._scrh)
                self.ctx.clear(0.5, 0.7, 1.0)
                self.gamma_shader.color_tex.use(0)
                self.gamma_shader.prog['DiffuseSampler'].value = 0
                self.ctx.disable(moderngl.DEPTH_TEST)
                self.ctx.disable(moderngl.CULL_FACE)
                self.gamma_shader.vao.render()
                self.ctx.enable(moderngl.DEPTH_TEST)
                self.ctx.enable(moderngl.CULL_FACE)
                
                
            
            fps = self.clock.get_fps()
            # print(fps, rendered)
            fx, fy, fz = self.p.getpos()
            vx, vy, vz = self.p.getvel()
            flight = "Flying" if self.p.is_flying else "Walking"
            chx, chz = self.p.chunkpos(CHUNK_SZ)
            baf  = 0
            look = "None"
            if targetb:
                tx, ty, tz = int(targetb[0]), int(targetb[1]), int(targetb[2])
                c = self.chunker.chunks.get((tx // CHUNK_SZ, tz // CHUNK_SZ))
                if c and c.gen_ready:
                    lx, lz = tx - c.offset_x, tz - c.offset_z
                    if 0 <= lx < CHUNK_SZ and 0 <= lz < CHUNK_SZ and 0 <= ty < CHUNK_H:
                        baf = c.voxels[lx, ty, lz]
            
            bid   = baf & 0x3FF
            state = (baf >> 10) & 0x1F
            pmade = (baf >> 15) & 1

            from items.registry import REGISTRY
            bn = REGISTRY.get(bid)
            if not bn or bid == 0: targetb = False
            else: bn = bn.nm
            
            if targetb:
                look = f"{bn} {{st:{state}, pm:{pmade}}} ({tx}, {ty}, {tz})"
            
            ll = 0
            if targetb and targetf:
                ll = self.chunker.getlight(
                    targetb[0]+targetf[0], 
                    targetb[1]+targetf[1], 
                    targetb[2]+targetf[2]
                )

            yaw, pitch  = self.p.cam.yaw, self.p.cam.pitch
            yn   = yaw % 360
            fdir = [
                "S", "SW",
                "W", "NW",
                "N", "NE",
                "E", "SE"
            ][int((yn + 22.5) / 45) % 8]

            si, sip = "Singleplayer", ""
            if self.is_client and self.netclient and self.netclient.isconn():
                si, sip = "Connected", f"Server: {self.netclient.host}:{self.netclient.port}"
                
            bid  = get_biome(fx, fz, self.chunker.world.noise.p)
            bnm  = BIOME_NAMES[bid] if 0 <= bid < len(BIOME_NAMES) else "Unknown"
            
            stats = [
                     f"FPS: {fps:.1f}", "", 
                     f"Position: ({fx:.1f}, {fy:.1f}, {fz:.1f})", 
                     f"Facing: {fdir} (yaw={yaw:.0f})",
                     f"Chunk: ({chx}, {chz})",
                     f"Biome: {bnm}",
                     f"Looking at: {look}", 
                     f"Light: {ll}", "",
                     f"Velocity: ({vx:.2f}, {vy:.2f}, {vz:.2f})", 
                     f"Mode: {flight}",
                     f"Rotation: Yaw {yaw:.1f} Pitch {pitch:.1f}", "",
                     f"Chunks: {rendered}/{len(self.chunker.chunks)}",
                     f"Building: {len(self.chunker.queue_chunkbuild)}",
                     f"Uploading: {self.chunker.queue_meshupload.qsize()}",
                     f"Render Distance: {self.chunker.render_dist}", 
                     f"Seed: {self.seed}", "",
                     f"Server: {si}", 
                     sip,
            ]
            
            gst = "ON" if self.gamma_shader.enabled else "OFF"
            keybinds = [
                "github.com/maladaptivesoftware",
                "",
                "Down [LShift]",
                "Sprint [LCtrl]",
                "Toggle Flight [F]",
                "Camera [F5]",
                f"Gamma [{gst}] [F4]",
                "Borders [F3]",
                "Fullscreen [F11]",
                "HUD [F1]",
            ]

            self.hud.render(self.p)

            tablist = None
            if self.tabdown and self.netclient and self.netclient.isconn():
                tablist = [self.netclient.pname]
                rp = self.netclient.remoteplayers()
                for _, p in rp.items():
                    tablist.append(p.nm)

            self.ui.render(
                stats if self.showdebug else [],
                nametags  = [],
                keybinds  = keybinds if self.showhud else None,
                renderinv = self.oninv,
                inv = self.p.inv, 
                pmodel = self.pmodel,
                
                chat_input = self.ibuff if self.onchat else None,
                tablist = tablist
            )
            
            
            pygame.display.flip()
        
        self.cleanup()
        if not self.managed: pygame.quit()

    def savelocal(self):
        if self.is_client: return
        
        pos = self.p.getpos()
        data = {'pos': pos.tolist(), 'yaw': float(self.p.cam.yaw), 'pitch': float(self.p.cam.pitch)}
        with open(os.path.join(config.root, self.wname, "player.json"), 'w') as f:
            json.dump(data, f)
        

    """
    def perfstart(self):
        self._pt = {}
        self._ptick = time.time()

    def perfmark(self, lbl):
        now = time.time()
        self._pt[lbl] = now - self._ptick
        self._ptick = now

    def perfdump(self):
        for k, v in self._pt.items():
            print(f"  {k:20s} {v*1000:.2f}ms")
    """

    def cleanup(self):
        self.savelocal()
        if self.netclient: self.netclient.disconnect()
        self.pmodel.release()
        self.particles.release()
        if self.render_helditem: self.render_helditem.release()
        if self.itementys:    self.itementys.release()
        if self.render_extruded: self.render_extruded.cleanup()
        if self.gamma_shader:   self.gamma_shader.release()
        self.chunker.shutdown()
    
    def applyupdates(self):
        # drain net updates @ main thread (vbos)
        upd = []

        with self._uplock:
            if self.pupdates:
                upd = self.pupdates[:]
                self.pupdates.clear()
                
                
        for x, y, z, bt in upd:
            # print(x, y, z, bt)
            if not self.chunker.setblock(x, y, z, bt):
                cx, cz = x // CHUNK_SZ, z // CHUNK_SZ
                lx, lz = x - cx * CHUNK_SZ, z - cz * CHUNK_SZ
                key = (cx, cz)
                if key not in self.chunker.modCache:
                    self.chunker.modCache[key] = {}
                    
                self.chunker.modCache[key][(lx, y, lz)] = bt
                self.chunker.dirtychunks.add(key)
                
                
                
                
    
    def flush(self):
        # queued main thread tasks
        ts = []
        with self._tlock:
            if self.ptasks:
                ts = self.ptasks[:]
                self.ptasks.clear()
        for t in ts: t()
    
    def svconnect(self, host='localhost', port=SV_PORT, pname="netclient"):
        
        if self.is_client and self.netclient:
            self.svdisconnect()
            return

        self.ui.chatmsg(f"Connecting to {host}:{port}...", color=(200, 200, 255))
        self.netclient = NetworkClient(
            host=host, port=port, pname=pname, 
            ui_callback=self.ui.chatmsg
        )
        
        
        if self.netclient.connect():
            self.is_client = True
            self.chunker.is_server = False
            self.bindcallbacks()
            self.ui.chatmsg(f"connected to {host}:{port}", color=(200, 255, 200))
            
        else:
            self.ui.chatmsg(f"failed to connect {host}:{port}", color=(255, 150, 150))
            self.netclient = None
            
            
            
            

    """
    def svdisconnect(self):
        if self.netclient:
            self.netclient.disconnect()
        self.netclient  = None
        self.is_client  = False
        self.chunker.is_server = True
    """

    def svdisconnect(self, reason="disconnected"):
        # net thread can land here -> only set flag
        if self.netclient: self.netclient.disconnect()
        self.ui.chatmsg(reason, color=(255, 200, 200))
        self._dcreq = reason


    """
    def restoreworld(self):
        snap = self._lsnap
        self._lsnap = None
        if snap is None: return

        self.ui.chatmsg("restoring local world...", color=(200, 200, 200))
        self.seed  = snap['seed']
        self.noise = PerlinNoise(seed=self.seed)
        self.chunker.world.noise = self.noise
        self.chunker.resetworld()
        if snap['mods']:
            for k, m in snap['mods'].items():
                self.chunker.modCache[k] = m.copy()
            self.chunker.dirtychunks.update(snap['mods'].keys())

        pos = snap['pos']
        self.p.pos = pos.copy()
        self.p.vel = np.array([0.0, 0.0, 0.0], dtype='f4')
        ep = pos.copy()
        ep[1] += self.p.physics.eye_h
        self.p.cam.pos = ep
        cx, cz = self.p.chunkpos(CHUNK_SZ)
        self.chunker.updateloads(cx, cz)
    """



    def resetworld(self):
        with self.statelock:
            if self._nxtseed is None: return
            
            seed = self._nxtseed
            self.ui.chatmsg(f"resetting world {seed}...", color=(200, 255, 200))
            self.seed = seed
            self.noise = PerlinNoise(seed=seed)
            self.chunker.world.noise = self.noise
            self.chunker.resetworld()
            if self.pmodpay:
                self.ui.chatmsg(f"restoring {len(self.pmodpay)} chunks...", color=(200, 200, 255))
                for k, m in self.pmodpay.items():
                    self.chunker.modCache[k] = m.copy()
                self.chunker.dirtychunks.update(self.pmodpay.keys())
                self.pmodpay = None
            spawn = self._pspawn if self._pspawn is not None else np.array([0.0, 80.0, 0.0], dtype='f4')
            self._pspawn = None
            self.p.pos = spawn
            self.p.vel = np.array([0.0, 0.0, 0.0], dtype='f4')
            ep = self.p.pos.copy()
            ep[1] += self.p.physics.eye_h
            self.p.cam.pos = ep
            cx, cz = self.p.chunkpos(CHUNK_SZ)
            self.chunker.updateloads(cx, cz)
            self.ui.chatmsg("reset complete!", color=(200, 255, 200))
            
    ## --
        

    def bindcallbacks(self):
        if not self.netclient: return

        def on_seed(seed):
            with self.statelock:
                self.ui.chatmsg(str(seed), color=(200, 255, 200))
                self.ui.chatmsg("queue reload scheduled", color=(200, 255, 200))
                self._nxtseed, self._resetreq = seed, True
                self.pmodpay = None
                self._pspawn  = None
                
                
        
        def on_mods(mods):
            with self.statelock:
                if self._resetreq:
                    self.pmodpay = mods
                    return
            
            appl, pend = 0, {}
            self.ui.chatmsg(f"applying {len(mods)} chunks", color=(200, 200, 255))
            for (cx, cz), cm in mods.items():
                c = self.chunker.chunks.get((cx, cz))
                if c and c.gen_ready:
                    for (lx, y, lz), bt in cm.items():
                        if 0 <= lx < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= lz < CHUNK_SZ:
                            c.voxels[lx, y, lz] = bt
                            appl += 1
                    pend[c] = True
                    
                    
                    
                else:
                    # not loaded -> stash
                    if (cx, cz) not in self.chunker.modCache:
                        self.chunker.modCache[(cx, cz)] = {}
                    self.chunker.modCache[(cx, cz)].update(cm)
                    
                    
            for c in pend:
                c.bakelight()
                c.mesh_built = False
                self.chunker.queue_chunkbuild.append(c)
                self.chunker.meshthread_event.set()
                
                
            if appl > 0: self.ui.chatmsg(f"appl {appl} mods", color=(200, 255, 200))
        
        
        
        
        
        
        def on_update(x, y, z, bt):
            if (x, y, z) not in self.pchg:
                if bt == 0 and self.chunker.getblock(x, y, z) == 60:  # 60 = tnt
                    with self._tlock:
                        self.ptasks.append(lambda x=x, y=y, z=z: self.blockentys.activate(x, y, z, 60, _remote=True))
                with self._uplock:
                    self.pupdates.append((x, y, z, bt))
                    
        
        def on_playerjoin(pid, nm, pos): self.ui.chatmsg(f"'{nm}' joined", color=(200, 200, 255))
        def on_playerleft(pid):          self.ui.chatmsg(f"'{pid}'  left", color=(200, 200, 255))
        
            
        def on_svmsg(msg):
            if msg.startswith("TELEPORT:"):
                try:
                    
                    coords = msg[9:].split(",")
                    if len(coords) == 3:
                        x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
                        pos = np.array([x, y, z], dtype='f4')
                        
                        
                        # if  reset still pend, defer the teleport so
                        # resetworld doesnt overwrite i with starting coords
                        with self.statelock:
                            if self._resetreq:
                                self._pspawn = pos
                                return
                                
                                
                        self.p.teleport(pos)
                        return
                        
                except Exception: pass
                
            self.ui.chatmsg(msg, color=(255, 255, 200))
            
            
        def on_chatmsg(msg): self.ui.chatmsg(msg, color=(255, 255, 255))
        
        def on_itemspawn(eid, iid, cnt, pos, vel):
            item = self.itementys.spawn(iid, cnt, pos, entity_id=eid)
            if item:
                item.vel = vel
                item.grounded = False

        def on_itemdespawn(eid):
            for i in self.itementys.items:
                if i.entity_id == eid:
                    i.active = False
                    break
        
        def on_itemcollect(iid, cnt):
            self.p.inv.add(iid, cnt)
            
            
            
            

        def on_disconnect(reason = "connection lost"):
            self.ui.chatmsg(f"disconnected: {reason}", color=(255, 150, 150))
            self._dcreq = reason or "connection lost"

        self.netclient.on_seed        = on_seed
        self.netclient.on_mods        = on_mods
        self.netclient.on_update      = on_update
        self.netclient.on_playerjoin  = on_playerjoin
        self.netclient.on_playerleft  = on_playerleft
        self.netclient.on_svmsg       = on_svmsg
        self.netclient.on_chatmsg     = on_chatmsg
        self.netclient.on_itemspawn   = on_itemspawn
        self.netclient.on_itemdespawn = on_itemdespawn
        self.netclient.on_itemcollect = on_itemcollect
        self.netclient.on_disconnect  = on_disconnect
        
        

    def renderrmtplayer(self, mvp, dt):
        if not self.netclient or not self.netclient.isconn(): return
        rp = self.netclient.remoteplayers()
        if not rp: return
        
        
        
        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        
        
        for _, p in rp.items():
            pos = p.pos.copy()
            d = np.clip(pos - self.p.cam.pos, -1000, 1000)
            if np.sum(d**2) > 10000 or not np.isfinite(np.sum(d**2)): continue
            
            

            spd = math.sqrt(p.velocity[0]**2 + p.velocity[2]**2)
            p.atime += dt
            ra, la, rl, ll = 0.0, 0.0, 0.0, 0.0
            
            
            if spd > 0.1:
                wc = p.atime * 4.0
                ra = math.sin(wc) * 50.0
                la = -math.sin(wc) * 50.0
                rl = math.sin(wc) * 50.0
                ll = rl  
                
                
            if p.swingt > 0:
                
                swt = p.swingt / 0.3  # normalize 0..1
                ra  = math.sin(swt * math.pi) * -80.0
                
                
            self.pmodel.render(
                mvp, pos, p.yaw, p.pitch, self.sun_pos,
                r_arm=ra, l_arm=la, r_leg=rl, l_leg=ll
            )
                
            if p._held > 0 and self.render_helditem:
                self.render_helditem.remoterender(
                    mvp, pos,
                    p.yaw, p.pitch, p._held,
                    ra, self.sun_pos
                )
                
            self.rendertag(mvp, pos, p.nm)
            
            
            
        self.ctx.enable(moderngl.CULL_FACE)
        self.ctx.disable(moderngl.BLEND)
        
        
        

    def rendertag(self, mvp, ppos, nm):
        
        if nm not in self.text_tag:
            ts = self.font_tag.render(nm, False, (255, 255, 255))
            w, h = ts.get_size()
            bg = pygame.Surface((w + 2, 11), pygame.SRCALPHA)
            bg.fill((0, 0, 0, 100))
            bg.blit(ts, (1, 1))
            
            t = self.ctx.texture(bg.get_size(), 4, pygame.image.tostring(bg, "RGBA", False))
            t.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.text_tag[nm] = t
            
            
            
        t = self.text_tag[nm]
        t.use(10)
        self.tagprog['tex'].value = 10
        self.tagprog['mvp'].write(mvp.astype('f4').tobytes())
        tp = ppos + np.array([0.0, 2.3, 0.0], dtype='f4')
        self.tagprog['center_pos'].write(tp.tobytes())
        
        front =self.p.cam.front
        wu = np.array([0.0, 1.0, 0.0], dtype='f4')
        cr = np.cross(front, wu)
        n = np.linalg.norm(cr)
        
        if n > 0: cr /= n
        else: cr = np.array([1.0, 0.0, 0.0], dtype='f4')
        
        cu = np.cross(cr, front)
        self.tagprog['cam_r'].write(cr.astype('f4').tobytes())
        self.tagprog['cam_u'].write(cu.astype('f4').tobytes())
        sc = 0.02
        
        self.tagprog['size'].value = (t.width * sc, t.height * sc)
        self.tagvao.render(moderngl.TRIANGLES)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--world',          default='default')
    parser.add_argument('--server',         default=None, help='host:port')
    parser.add_argument('--seed', type=int, default=None)
    parser.add_argument('--pname',           default=None)
    args = parser.parse_args()

    world = VoxelWorld(
        wname=args.world, 
        svaddr=args.server, 
        seed=args.seed, 
        managed=False
    )

    if args.server:
        from identity import whoami
        pts    = args.server.split(':')
        host     = pts[0]
        port     = int(pts[1]) if len(pts) > 1 else SV_PORT
        identity = whoami()
        nm = args.pname or identity.get('nm', 'Player')
        world.svconnect(host=host, port=port, pname=nm)

    world.run()
