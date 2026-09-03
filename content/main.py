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
    AXY, AXX, AXZ, UV_W, UV_H,
)
from world import blocks


import config
from config import (
    CHUNK_SZ, CHUNK_H, SEA_LEVEL, WIN_W, WIN_H,
    RENDER_DIST, SEED, SV_PORT, WATER_OFF,
    WATER_PLANE, SUN_SZ, HLIGHT_SCL, LINE_W,
    SCL_HUD, F_PLANE, RAYCAST_DIST,
    HARDNESS, MINE_MULT, CRACK_SCL, HURT_T, POP_SCL, POP_YOFF, ENT_REACH,
    P_W, P_H
)


import shaders
from ui.menu import UIManager
from network.client import NetworkClient
from entity.player.model import PlayerModel
from skin import skintex
from ui.hud import HUDManager
from ui.inv import Inventory
from engine.particle import ParticleManager
from engine.sound import SoundManager, SND_HURT
from engine.dmgtext import DamageText
from engine.lightmap import Lightmap, skydarken, skybright

SKY_COL = np.array([0.5, 0.7, 1.0], dtype='f4')
from entity.item.item import ItemEntityManager
from entity.player._held import HeldItemRenderer
import _respath
from commands.manager import CommandManager
from items import textures as text_items
from world.animation import getanims
from world.renderers.extruded import ExtrudedRenderer
from engine.gamma import Gamma
from entity.blockenty import BlockEntityManager, itemblock
from entity.core import KIND_TNT, KIND_ITEM, KIND_DUMMY
from entity.manager import EntityManager
from entity.debug import EntityDebug
from entity import motion
from network.protocol import unpacktnt, unpackitem, GONE_DEATH
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
        self.skycol    = SKY_COL.copy()
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

        self.lightmap = Lightmap(self.ctx)
        self.lightmap.use(4)
        self.prog['lightmap'].value = 4
        self.prog['chunk_fade'].value = 1.0
        
        
        
        

        self.particles = ParticleManager(self.ctx, texture=self.texture)
        self.sfx       = SoundManager()
        self.dmgtext   = DamageText()
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


        # destroy_stage overlay
        self.crackprog = shaders.prog(self.ctx, "crack.vert", "crack.frag")
        cfaces = (
            ((0,0,0), (1,0,0), (1,1,0), (0,1,0)),   # -z
            ((1,0,1), (0,0,1), (0,1,1), (1,1,1)),   # +z
            ((0,0,1), (0,0,0), (0,1,0), (0,1,1)),   # -x
            ((1,0,0), (1,0,1), (1,1,1), (1,1,0)),   # +x
            ((0,0,1), (1,0,1), (1,0,0), (0,0,0)),   # -y
            ((0,1,0), (1,1,0), (1,1,1), (0,1,1)),   # +y
        )
        cuv = ((0,0), (1,0), (1,1), (0,1))
        cv  = []
        for i in cfaces:
            for j in (0, 1, 2, 0, 2, 3):
                cv += [(k - 0.5) * CRACK_SCL + 0.5 for k in i[j]]
                cv += list(cuv[j])

        self.crackvbo = self.ctx.buffer(np.array(cv, dtype='f4').tobytes())
        self.crackvao = self.ctx.vertex_array(
            self.crackprog, [(self.crackvbo, '3f 2f', 'in_pos', 'in_uv')]
        )
        self.crackuvs = [blocks.getuv(f"destroy_stage_{i}") for i in range(10)]
        self.crackprog['texture0'].value = 0
        

        self.pmodel = PlayerModel(self.ctx, _spath=_respath.text_player())
        self.rskins = {}
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
        self.text_pop = {}
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
                if 'gm' in pd:       self.p.setgmode(int(pd['gm']))
                if 'health' in pd:   self.p.health = int(pd['health'])
                if 'hunger' in pd:   self.p.hunger = int(pd['hunger'])
                
            except Exception:
                pass
                
                

        cx, cz = self.p.chunkpos(CHUNK_SZ)
        self.chunker.updateloads(cx, cz)
        
        self.showborder  = False
        self._dbgsent    = None
        self.svchunks    = set()
        self.dbgtags     = {}
        self.showhud     = True
        self.showdebug   = True
        self.netclient   = None
        self.is_client   = False
        self._dcreq      = None
        self.svport      = SV_PORT
        self.pupdates    = []
        self._uplock     = threading.Lock()
        self._wup        = np.array([0.0, 1.0, 0.0], dtype='f4')
        self._cachedmvp  = None
        self._cachedpos  = None
        self._dmgsent    = (None, 0)
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
        self.netserver   = None
        self.ptasks      = []
        self._tlock      = threading.Lock()
        
        self.blockentys   = BlockEntityManager(self.ctx, self.texture)
        self.entitys      = EntityManager(self.ctx, self.pmodel, self)
        self.entdbg       = EntityDebug(self.ctx, self.wireprog)

        
        
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

    
    # fx only
    def hurtfx(self, dmg):
        self.sfx.play(SND_HURT)

        pp    = self.p.getpos()
        pp[1] += POP_YOFF
        self.dmgtext.hit(pp, dmg, self.p.max_health)


    def onhurt(self, dmg):
        self.hurtfx(dmg)

        if self.netclient and self.netclient.isconn():
            self.netclient.sendhurt(dmg)

    def breakblock(self, bx, by, bz):
        bt = self.chunker.getblock(bx, by, bz)

        # fuckass redstonbe
        from world.blocks import REDSTONE_WIRE
        if bt == REDSTONE_WIRE:
            self.render_extruded.rm_block(bx, by, bz)

        self.chunker.breakblock(bx, by, bz)

        if bt and bt != 0:
            self.particles.spawn(bx, by, bz, bt)

        if self.netclient and self.netclient.isconn():
            self.netclient.sendchange(bx, by, bz, 0)

        if not self.p.gmode: self.dropblock(bx, by, bz, bt)


    
    # TODO drop tables
    # return self -> drop
    def dropblock(self, bx, by, bz, bt):
        from items.registry import REGISTRY
        if not bt or not REGISTRY.exists(bt): return

        pos = np.array([bx + 0.5, by + 0.5, bz + 0.5], dtype='f4')

        if self.netclient and self.netclient.isconn():
            # server owned
            self.netclient.senddrop(bt, 1, pos, np.array([0.0, 2.0, 0.0], dtype='f4'))
        else:
            self.itementys.spawn(bt, 1, pos)



    def onmine(self, dt):
        p  = self.p
        on = (
            not p.gmode and not self.oninv and not self.onchat
            and pygame.event.get_grab() 
            and pygame.mouse.get_pressed()[0]
        )

        tb = p.targetblock(RAYCAST_DIST)[0] if on else None

        if tb is None:
            p.mtgt  = None
            p.mprog = 0.0
            self.senddmg(None, 0)
            return

        # off block
        if tb != p.mtgt:
            p.mtgt  = tb
            p.mprog = 0.0

        p.mprog += dt / (HARDNESS * MINE_MULT)

        # retrigger swing
        if not p.is_breaking:
            p.swing()

        if p.mprog >= 1.0:
            self.breakblock(*tb)
            p.mtgt  = None
            p.mprog = 0.0
            self.senddmg(None, 0)
        else:
            self.senddmg(tb, min(int(p.mprog * 10), 9))


    
    def enthurtfx(self, e, dmg):
        hp    = e.pos.copy()
        hp[1] += e.type.h + 0.5
        self.dmgtext.hit(hp, dmg, e.type.hp or 20)


    # nearest player ahead
    def pickplayer(self, org, dr, maxd):
        nc = self.netclient
        if not (nc and nc.isconn()): return None, maxd

        hw = P_W * 0.5
        best, bd = None, maxd

        for _, rp in nc.remoteplayers().items():
            box = (
                rp.pos[0] - hw, rp.pos[1],       rp.pos[2] - hw,
                rp.pos[0] + hw, rp.pos[1] + P_H, rp.pos[2] + hw,
            )
            d = motion.rayaabb(org, dr, box, maxd)
            if d is not None and d < bd: best, bd = rp, d

        return best, bd


    def onattack(self):
        org = self.p.cam.pos
        dr  = self.p.cam.front

        e  = self.entitys.pick(org, dr, ENT_REACH)
        ed = motion.rayaabb(org, dr, e.aabb(), ENT_REACH) if e else ENT_REACH
        rp, rd = self.pickplayer(org, dr, ENT_REACH)

        if e is None and rp is None: return False

        # whichever is in front
        hd = min(ed, rd)

        # check block in way
        tb = self.p.targetblock(ENT_REACH)[0]
        if tb:
            bd = motion.rayaabb(
                org, dr,
                (tb[0], tb[1], tb[2], tb[0] + 1, tb[1] + 1, tb[2] + 1),
                ENT_REACH,
            )
            if bd is not None and bd < hd: return False

        if rp is not None and rd <= ed:
            self.netclient.sendattackpl(rp.pid)
            return True

        # wait for ENTITY_HURT
        if self.netclient and self.netclient.isconn():
            self.netclient.sendattack(e.eid)
        else:
            e.hurt(1)
            e.knock(motion.knockvec(self.p.getpos(), e.pos))
            self.enthurtfx(e, 1)

        return True


    def senddmg(self, tb, st):
        if (tb, st) == self._dmgsent: return
        self._dmgsent = (tb, st)

        if not (self.netclient and self.netclient.isconn()): return
        if tb is None: self.netclient.senddmg(0, 0, 0, -1)
        else:          self.netclient.senddmg(tb[0], tb[1], tb[2], st)

    
    def rendercracks(self, mvpb):
        cr = []
        if self.p.mtgt and self.p.mprog > 0.0:
            cr.append((self.p.mtgt, min(int(self.p.mprog * 10), 9)))

        if self.netclient and self.netclient.isconn():
            for x, y, z, st in self.netclient.blockdmg().values():
                cr.append(((x, y, z), max(0, min(st, 9))))

        if not cr: return

        self.ctx.enable(moderngl.BLEND)
        self.ctx.disable(moderngl.CULL_FACE)
        self.texture.use(0)
        self.crackprog['mvp'].write(mvpb)
        self.crackprog['uvsz'].value = (UV_W, UV_H)

        for i, j in cr:
            self.crackprog['offset'].value = i
            self.crackprog['uv0'].value    = self.crackuvs[j]
            self.crackvao.render()

        self.ctx.enable(moderngl.CULL_FACE)
        self.ctx.disable(moderngl.BLEND)


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

            for event in pygame.event.get():
                if event.type == pygame.JOYDEVICEADDED:
                    pygame.joystick.init()
                if event.type == pygame.JOYDEVICEREMOVED:
                    pygame.joystick.quit()
            
            if not self.oninv and not self.onchat:
                self.p.oninput(dt)
                self.p.onmouse()
                self.p.onjoystick()

            self.onmine(dt)

            if self.groundready(): self.p.update(dt)
            self.particles.update(dt)
            self.dmgtext.update(dt)
            self.blockentys.update(dt, self.worldctx())
            mp = bool(self.netclient and self.netclient.isconn())
            self.entitys.update(dt, self.chunker, local=not mp)

            # debug := request goals && nav targets
            if mp and self.showborder != self._dbgsent:
                self._dbgsent = self.showborder
                self.netclient.senddbgmode(self.showborder)

            getanims().update(dt)
            pp = self.p.getpos()
            
            
            
            
            
            if self.netclient and self.netclient.isconn():
                self.itementys.update(dt, pp, self.p.inv, self.netclient)
            else: self.itementys.update(dt, pp, self.p.inv, None)
            
            
            
            if self.netclient and self.netclient.isconn():
                #hid    = self.p.getsel() or 0
                # getsel() = nulls -> every nonblock
                st     = self.getstack()
                hid    = st.item.itemId if st else 0
                aflags = 0
                if self.p.is_breaking or self.p.is_placing: aflags |= 1  # swing
                if self.p.crouching: aflags |= 2  # sneak
                aflags |= (self.p.swseq & 3) << 4
                
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
            

            rc   = self.p.rcam()
            mvp  = rc.mvpmat(inverted=(not self.p.freecam and self.p.cmode == 2))
            cpos = rc.pos
            cfr  = rc.front
            far  = F_PLANE
            
            rad   = math.radians(self.sun_angle)
            cos_r, sin_r = math.cos(rad), math.sin(rad)
            sd    = np.array([cos_r, sin_r, 0.1], dtype='f4')
            norm  = math.sqrt(cos_r*cos_r + sin_r*sin_r + 0.01)
            sd[0] /= norm; sd[1] /= norm; sd[2] /= norm
            self.sun_dir = sd
            self.sun_pos = (cpos + sd * min(0.8 * far, 300.0)).astype('f4')

            # sun_angle 90 = noon
            td = ((self.sun_angle - 90.0) / 360.0) % 1.0
            self.lightmap.update(dt, skydarken(td))
            self.lightmap.use(4)

            self.skycol = SKY_COL * skybright(td)
            self.prog['fog_col'].write(self.skycol.tobytes())

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
                self.gamma_shader.fbo.clear(*self.skycol)

            else:
                self.ctx.screen.use()
                self.ctx.viewport = (0, 0, self._scrw, self._scrh)
                self.ctx.clear(*self.skycol)
                
                
                
                

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
            self.entitys.render(mvp, self.sun_pos)

            self.render_extruded.render(mvp, ambient=0.4)
            
            targetb, targetf = self.p.targetblock(5.0)
            if targetb:
                self.ctx.enable(moderngl.BLEND)
                self.wireprog['mvp'].write(mvpb)
                self.wireprog['wcolor'].value = (0.0, 0.0, 0.0, 0.4)
                self.wireprog['offset'].value = targetb
                self.wirevao.render(moderngl.LINES)

                """
                if self.p.mtgt == targetb and self.p.mprog > 0.0:
                    st = min(int(self.p.mprog * 10), 9)
                    self.ctx.disable(moderngl.CULL_FACE)
                    self.texture.use(0)
                    self.crackprog['mvp'].write(mvpb)
                    self.crackprog['offset'].value = targetb
                    self.crackprog['uv0'].value    = self.crackuvs[st]
                    self.crackprog['uvsz'].value   = (UV_W, UV_H)
                    self.crackvao.render()
                    self.ctx.enable(moderngl.CULL_FACE)
                """

                self.ctx.disable(moderngl.BLEND)

            self.rendercracks(mvpb)
            
            if self.showborder:
                self.ctx.enable(moderngl.BLEND)
                self.wireprog['mvp'].write(mvpb)
                for (cx, cz), c in self.chunker.chunks.items():
                    # green = server has it loaded too
                    if (cx, cz) in self.svchunks: col = (0.2, 1.0, 0.2, 0.6)
                    else:                         col = (0.0, 0.0, 0.0, 0.4)
                    self.wireprog['wcolor'].value = col
                    self.wireprog['offset'].value = (c.offset_x, 0.0, c.offset_z)
                    self.bordervao.render(moderngl.LINES)
                self.wireprog['wcolor'].value = (0.0, 0.0, 0.0, 0.4)
                self.ctx.disable(moderngl.BLEND)
                
                
            
            
            
            
            self.ctx.enable(moderngl.BLEND)
            self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
            self.sunprog['mvp'].write(mvpb)
            self.sunprog['sun_pos'].write(self.sun_pos.tobytes())
            
            front =-rc.front if (not self.p.freecam and self.p.cmode == 2) else rc.front
            
            
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

            if self.showborder:
                self.entdbg.render(
                    mvp, list(self.entitys.ents.values()),
                    [i for i in self.itementys.items if i.active] +
                    [i for i in self.blockentys.entities if i.alive],
                )
                self.renderenttags(mvp)

            self.renderpopoffs(mvp)
                
                
            
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
                _hidehead=(self.p.cmode == 0 and not self.p.freecam),
                hurt=max(0.0, self.p.hurtt / HURT_T)
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
            
            ll, lb = 0, 0
            if targetb and targetf:
                ll, lb = self.chunker.getlight(
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

            if pygame.joystick.get_count() > 0:
                joystick = pygame.joystick.Joystick(0)
            else:
                joystick = None

            jname = "None" if joystick == None else joystick.get_name()
            j0 = "0.00" if not joystick else round(joystick.get_axis(0), 2)
            j1 = "0.00" if not joystick else round(joystick.get_axis(1), 2)
            j2 = "0.00" if not joystick else round(joystick.get_axis(2), 2)
            j3 = "0.00" if not joystick else round(joystick.get_axis(3), 2)
            j4 = "0.00" if not joystick else round(joystick.get_axis(4), 2)
            j5 = "0.00" if not joystick else round(joystick.get_axis(5), 2)
            
            stats = [
                     f"FPS: {fps:.1f}", "", 
                     f"Controller: {jname}",
                     f"Controller Axis: 0={j0} 1={j1} 3={j3} 4={j4} 2={j2} 5={j5}",
                     f"Position: ({fx:.1f}, {fy:.1f}, {fz:.1f})", 
                     f"Facing: {fdir} (yaw={yaw:.0f})",
                     f"Chunk: ({chx}, {chz})",
                     f"Biome: {bnm}",
                     f"Looking at: {look}", 
                     f"Light: {max(ll, lb)} (sky {ll}, blk {lb})", "",
                     f"Velocity: ({vx:.2f}, {vy:.2f}, {vz:.2f})",
                     f"Mode: {flight}",
                     f"Gamemode: {self.p.gmode}",
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
            if self.p.freecam:
                keybinds = [
                    "github.com/paaracetamol",
                    "",
                    "Down [LCtrl]",
                    "Sprint [LShift]",
                    f"Move [{'Cam' if self.p.fcmove else 'Body'}] [C]",
                    f"Stick [{'ON' if self.p.fcstick else 'OFF'}] [V]",
                    "Exit [Shift+F5]",
                ]
            else:
                keybinds = [
                    "github.com/paaracetamol",
                    "",
                    "Down [LCtrl]",
                    "Sprint [LShift]",
                    "Toggle Flight [F]",
                    "Camera [F5]",
                    f"Gamma [{gst}] [F4]",
                    "Borders [F3]",
                    "Fullscreen [F11]",
                    "HUD [F1]",
                ]

            if self.showhud: self.hud.render(self.p)

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
        data = {
            'pos': pos.tolist(), 
            'yaw': float(self.p.cam.yaw), 
            'pitch': float(self.p.cam.pitch),
            'gm': int(self.p.gmode),
            'health': int(self.p.health),
            'hunger': int(self.p.hunger)
        }

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
        self.dropskins()
        self.pmodel.release()
        self.particles.release()
        self.sfx.release()
        for i in self.text_pop.values(): i.release()
        self.text_pop.clear()
        if self.render_helditem: self.render_helditem.release()
        if self.itementys:    self.itementys.release()
        if self.entitys:
            self.entitys.saveall()
            self.entitys.release()
        if self.entdbg: self.entdbg.release()
        if self.render_extruded: self.render_extruded.cleanup()
        if self.gamma_shader:   self.gamma_shader.release()
        self.chunker.shutdown()
    
    def worldctx(self):
        return {
            'chunker':    self.chunker,
            'particles':  self.particles,
            'player':        self.p,
            'netclient':     self.netclient,
            'blockentys': self.blockentys,
        }

    def applyupdates(self):
        # drain net updates @ main thread (vbos)
        upd = []

        with self._uplock:
            if self.pupdates:
                upd = self.pupdates[:]
                self.pupdates.clear()
                
                
        if not upd: return

        # chunks not loaded yet come back as misses -> stash them
        for x, y, z, bt in self.chunker.setblocks(upd):
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
            self.chunker.is_client = True
            self.chunker.netmode   = True
            self.chunker.netreq    = self.netclient.sendchunkreq
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

    def groundready(self):
        # netmode -> dont drop thru terrain that hasnt landed yet
        if not self.chunker.netmode: return True
        pp = self.p.getpos()
        c  = self.chunker.chunks.get(
            (int(pp[0] // CHUNK_SZ), int(pp[2] // CHUNK_SZ)))
        return c is not None and c.gen_ready


    def svdisconnect(self, reason="disconnected"):
        # net thread can land here -> only set flag
        if self.netclient: self.netclient.disconnect()
        self.ui.chatmsg(reason, color=(255, 200, 200))
        self.svchunks = set()
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
            self.entitys.clear()
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
                
                
        
        
        
        
        
        
        
        def on_update(x, y, z, bt):
            with self._uplock:
                self.pupdates.append((x, y, z, bt))


        def on_chunk(cx, cz, vox):
            def ld(): self.chunker.recvchunk(cx, cz, vox)
            with self._tlock: self.ptasks.append(ld)


        def on_svchunks(keys):
            self.svchunks = set(keys)


        def on_entspawn(eid, kind, pos, yaw, hp, flags, pay):
            def mk():
                if kind == KIND_TNT:
                    from world.blocks import TNT
                    self.blockentys.activate(
                        int(pos[0]), int(pos[1]), int(pos[2]), TNT,
                        fuse=unpacktnt(pay), _remote=True, eid=eid,
                    )
                    e = self.blockentys.byeid(eid)
                    if e is not None: e.pos = pos.copy(); e.tpos = pos.copy()


                elif kind == KIND_ITEM:
                    iid, cnt, vel = unpackitem(pay)
                    it = self.itementys.spawn(iid, cnt, pos, entity_id=eid)
                    if it:
                        it.vel = vel
                        it.grounded = False


                else:
                    e = self.entitys.spawn(kind, eid=eid, pos=pos, yaw=yaw)
                    if e is not None: e.hp = hp



            with self._tlock: self.ptasks.append(mk)


        def on_entstate(ents):
            def mv():
                for eid, pos, yaw, vy, hoff, anim in ents:
                    e = self.blockentys.byeid(eid)
                    if e is None: e = self.itementys.byeid(eid)
                    if e is None: e = self.entitys.byeid(eid)
                    if e is None: continue
                    e.setnet(pos, vy)
                    e.yaw  = yaw
                    e.hyaw = yaw + hoff

            with self._tlock: self.ptasks.append(mv)


        def on_entgone(eid, reason):
            def rm():
                e = self.blockentys.byeid(eid)
                if e is not None:
                    # out of range is not death, dont blow it up
                    if reason == GONE_DEATH: e.explode(self.worldctx())
                    e.alive = False
                    return

                it = self.itementys.byeid(eid)
                if it is not None:
                    it.active = False
                    return

                self.entitys.remove(eid)

            with self._tlock: self.ptasks.append(rm)


        def on_entanim(eid, anim):
            e = self.entitys.byeid(eid)
            if e is not None: e.playanim(anim)


        def on_entdbg(eid, pts, txt):
            e = self.entitys.byeid(eid)
            if e is not None:
                # server owned route
                e.path   = pts
                e.pathi  = 0
                e.navtgt = pts[-1] if pts else None
                e.dbgai  = txt


        def on_enthurt(eid, dmg):
            e = self.entitys.byeid(eid)
            if e is not None:
                e.hurtt = HURT_T
                e.hp    = max(0, e.hp - dmg)
                self.enthurtfx(e, dmg)

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
        
        """
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
        """

        def on_itemcollect(iid, cnt):
            self.p.inv.add(iid, cnt)
            
            
            
            

        def on_disconnect(reason = "connection lost"):
            self.ui.chatmsg(f"disconnected: {reason}", color=(255, 150, 150))
            self._dcreq = reason or "connection lost"

        def on_playerhurt(rp, dmg):
            self.sfx.playat(SND_HURT, rp.tpos, self.p.pos)
            hp    = rp.tpos.copy()
            hp[1] += POP_YOFF
            self.dmgtext.hit(hp, dmg)

        # server owned
        def on_knock(v):
            self.p.knock(v)


        def on_health(hp):

            d = self.p.health - hp
            self.p.health = hp

            if d > 0:
                self.p.hurtt = HURT_T
                self.hurtfx(d)

        def on_hunger(hg):
            self.p.hunger = hg

        self.netclient.on_seed        = on_seed
        self.netclient.on_update      = on_update
        self.netclient.on_entspawn    = on_entspawn
        #self.netclient.on_entpos      = on_entpos
        self.netclient.on_entstate    = on_entstate
        self.netclient.on_entgone     = on_entgone
        self.netclient.on_enthurt     = on_enthurt
        self.netclient.on_entanim     = on_entanim
        self.netclient.on_entdbg      = on_entdbg
        self.netclient.on_svchunks    = on_svchunks
        self.netclient.on_chunk       = on_chunk
        self.netclient.on_playerjoin  = on_playerjoin
        self.netclient.on_playerleft  = on_playerleft
        self.netclient.on_svmsg       = on_svmsg
        self.netclient.on_chatmsg     = on_chatmsg
        #self.netclient.on_itemspawn   = on_itemspawn
        #self.netclient.on_itemdespawn = on_itemdespawn
        self.netclient.on_itemcollect = on_itemcollect
        self.netclient.on_disconnect  = on_disconnect
        self.netclient.on_playerhurt  = on_playerhurt
        self.netclient.on_health      = on_health
        self.netclient.on_knock       = on_knock
        self.netclient.on_hunger      = on_hunger
        
        

    def dropskins(self, keep=()):
        for pid in [i for i in self.rskins if i not in keep]:
            self.rskins.pop(pid).release()


    def renderrmtplayer(self, mvp, dt):
        if not self.netclient or not self.netclient.isconn(): return
        rp = self.netclient.remoteplayers()
        self.dropskins(rp)
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
                la  = math.sin(swt * math.pi) * -80.0
                
                
            if p.skin is not None:
                old = self.rskins.pop(p.pid, None)
                if old: old.release()
                self.rskins[p.pid] = skintex(self.ctx, p.skin)
                p.skin = None

            crch = 1.0 if p.aflags & 2 else 0.0

            self.pmodel.render(
                mvp, pos, p.yaw, p.pitch, self.sun_pos,
                r_arm=ra, l_arm=la, r_leg=rl, l_leg=ll,
                crouch=crch, tex=self.rskins.get(p.pid),
                hurt=max(0.0, p.hurtt / HURT_T)
            )

            if p._held > 0 and self.render_helditem:
                self.render_helditem.remoterender(
                    mvp, pos,
                    p.yaw, p.pitch, p._held,
                    la, self.sun_pos, crch
                )
                
            self.rendertag(mvp, pos, p.nm)
            
            
            
        self.ctx.enable(moderngl.CULL_FACE)
        self.ctx.disable(moderngl.BLEND)
        
        
        

    def renderpopoffs(self, mvp):
        if not self.dmgtext.pops: return

        self.ctx.enable(moderngl.BLEND)
        self.ctx.blend_func = moderngl.SRC_ALPHA, moderngl.ONE_MINUS_SRC_ALPHA
        self.ctx.disable(moderngl.CULL_FACE)
        self.ctx.disable(moderngl.DEPTH_TEST) 

        for i in self.dmgtext.pops:
            r, g, b = i.col
            dr = i.xzoff()
            self.rendertag(
                mvp, i.pos + np.array([dr, 0.0, dr], dtype='f4'), i.txt,
                yoff=i.yoff(), cache=self.text_pop, maxn=128,
                tint=(r / 255.0, g / 255.0, b / 255.0, 1.0),
                sc=POP_SCL * i.scl, box=False,
            )

        self.ctx.enable(moderngl.DEPTH_TEST)
        self.ctx.enable(moderngl.CULL_FACE)
        self.ctx.disable(moderngl.BLEND)


    def renderenttags(self, mvp):
        for e in self.blockentys.entities:
            if not e.alive: continue
            self.rendertag(
                mvp, e.pos, e.dbgtag(),
                yoff=1.4, cache=self.dbgtags, maxn=96,
            )

        for i in self.entitys.ents.values():
            self.rendertag(
                mvp, i.pos, i.dbgtag(),
                yoff=i.type.h + 0.4, cache=self.dbgtags, maxn=96,
            )

        for i in self.itementys.items:
            if not i.active: continue
            self.rendertag(
                mvp, i.pos, i.dbgtag(),
                yoff=0.7, cache=self.dbgtags, maxn=96,
            )


    def tagtex(self, nm, cache, maxn=0, box=True):
        if nm not in cache:
            
            if maxn and len(cache) >= maxn:
                for i in cache.values(): i.release()
                cache.clear()

            ts = self.font_tag.render(nm, False, (255, 255, 255))
            w, h = ts.get_size()

            """
            bg = pygame.Surface((w + 2, 11), pygame.SRCAL-PHA)
            bg.fill((0, 0, 0, 100))
            bg.blit(ts, (1, 1))
            """

            if box:
                bg = pygame.Surface((w + 2, 11), pygame.SRCALPHA)
                bg.fill((0, 0, 0, 100))
                bg.blit(ts, (1, 1))

            else:
                # no plate
                sh = self.font_tag.render(nm, False, (0, 0, 0))
                bg = pygame.Surface((w + 1, h + 1), pygame.SRCALPHA)
                bg.blit(sh, (1, 1))
                bg.blit(ts, (0, 0))

            t = self.ctx.texture(bg.get_size(), 4, pygame.image.tostring(bg, "RGBA", False))
            t.filter = (moderngl.NEAREST, moderngl.NEAREST)
            cache[nm] = t

        return cache[nm]


    def rendertag(
            self, mvp, ppos, nm, yoff=2.3, cache=None, maxn=0,
            tint=(1.0, 1.0, 1.0, 1.0), sc=0.02, box=True
        ):
        t = self.tagtex(nm, self.text_tag if cache is None else cache, maxn, box)
        t.use(10)
        self.tagprog['tex'].value  = 10
        self.tagprog['tint'].value = tint
        self.tagprog['mvp'].write(mvp.astype('f4').tobytes())
        tp = ppos + np.array([0.0, yoff, 0.0], dtype='f4')
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
