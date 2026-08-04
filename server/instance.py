import json
import math
import random
import socket
import threading
import time
import struct
import os
import numpy as np
from collections import deque
from world.terrain import ChunkManager, PerlinNoise
import config
from config import (
    CHUNK_SZ, CHUNK_H, SV_PORT, SV_HOST, SEED,
    SV_RATE, SV_TIMEOUT, SV_MAXONLINE, SV_MOTD, RENDER_DIST,
)
from network.protocol import (
    MessageType, ReadMessage,
    mkservmsg, mkpos, mkitemcollect, mkdisconnect, mksvreply, mkleft, mkseed, mkpjoin,
    mkblockupd, mkchat, mkitemspawn, mkitemdespawn, mklist,
    mkentspawn, mkentpos, mkentgone, mksvchunks, mkblockbulk, mkchunk,
    mkplayerskin, validskin, mkblockdmgupd, mkplayerhurt, mkhealth, mkhunger,
)
from identity import bytetoken


# tnt
TNT_ID         = 60
TNT_FUSE       = 4.0
TNT_CFUSE_MIN  = 0.5
TNT_CFUSE_MAX  = 1.5
TNT_BLAST_R    = 4.0
BEDROCK_ID     = 4

# entity physics, shared by every kind
ENT_GRAV    = -32.0
ENT_TERMVEL = -78.4
ENT_IVELY   =  4.0

MAX_HEALTH = 20
MAX_HUNGER = 20

# item drops
ITEM_LIFE = 300.0
ITEM_FRIC = 0.8
ITEM_REACH = 2.5


def _tntsphere(r=TNT_BLAST_R):
    R, o = int(r), []
    for dx in range(-R-1, R+2):
        for dy in range(-R-1, R+2):
            for dz in range(-R-1, R+2):
                d = math.sqrt(dx*dx + dy*dy + dz*dz)
                if d <= r: o.append((dx, dy, dz))
    return o

_TNT_OFFS = _tntsphere()


class PlayerState:
    def __init__(self, pid, nm, sock, addr):
        self.pid    = pid
        self.nm     = nm
        self.token  = ""
        self.sock   = sock
        self.addr   = addr
        self.pos = np.array([0.0, 80.0, 0.0], dtype='f4')
        self.yaw    = 0.0
        self.pitch  = 0.0
        self._held  = 0
        self.aflags = 0
        self.health = MAX_HEALTH
        self.hunger = MAX_HUNGER
        self.skin   = b''
        self.lupd   = time.time()
        self.reader = ReadMessage(sock)
        self.conn   = True
        self.btimes = []
        self.ltele  = 0.0
        self.sentck = set()   # chunks done
        self.sq     = deque()   # normal traffic
        self.cq     = deque()   # chunk payloads, yield to sq
        self.slock  = threading.Lock()
        self.swake  = threading.Event()


class Instance:
    def __init__(
        self, host=SV_HOST, port=SV_PORT, wname="default",
        seed=SEED, maxp=SV_MAXONLINE, motd=SV_MOTD
    ):
        
        self.host    = host
        self.port    = port
        self.wname   = wname
        self.seed    = seed
        self.maxpl   = maxp
        self.motd    = motd
        self.sock    = None
        self.running = False
        self.players = {}
        self.npid    = 1
        self.plock   = threading.Lock()
        self.trate   = SV_RATE
        self.tint    = 1.0 / self.trate
        self.pint    = 0.033
        self.aitems  = {}
        self.neid    = 1
        self.ilock   = threading.Lock()
        self.commands = None
        self.ents    = {}   # eid -> [kind, x, y, z, vy, fuse, onground]
        self.tntlock = threading.Lock()
        self._eid    = 0
        self.eidlock = threading.Lock()
        self._lastkeys = None
        self.pendblk   = {}   # (x,y,z) -> bt, flushed once a tick
        self.blklock   = threading.Lock()

        self.initworld()
        self.initcmds()


    def initworld(self):
        class _World:
            def __init__(s, seed):
                s.seed  = seed
                s.noise = PerlinNoise(seed=seed)
                from world.trees import TreeManager
                from world.decor import RockManager
                s.trees = TreeManager(assetdir="assets")
                s.rocks = RockManager(assetdir="assets")
                

        self.world     = _World(self.seed)
        self.chunker = ChunkManager(
            self.world, render_dist=self.SIM_DIST,
            wname=self.wname, is_server=True, headless=True,
        )
        self.world.chunker = self.chunker
        
        self.chunker.ui = None
        
        


    def initcmds(self):
        from commands.manager import CommandManager
        from commands.entities import CommandEntity
        self.commands = CommandManager()
        
        

        srv = self

        def _collect(world):
            ents = []
            with srv.plock:
                for p in srv.players.values():
                    if not p.conn: continue
                    ents.append( CommandEntity(
                        kind="player", nm=p.nm,
                        get_pos   = lambda p=p: p.pos.copy(),
                        teleport  = lambda pos, p=p: srv.teleport(p, pos),
                        give_item = lambda iid, cnt, p=p: srv.giveitem(p, iid, cnt),
                        set_hp     = lambda hp, p=p: srv.sethealth(p, hp),
                        set_hunger = lambda hg, p=p: srv.sethunger(p, hg),
                        source=p,
                    ))
                    
            return ents
            

        self.commands.gather_entities = _collect

        def _broadcast_reply(msg, color=(255, 255, 255)):
            srv.broadcast(mkservmsg(msg))
            

        class _WorldWrap:
            def __init__(s):
                s.sun_angle = 0.0
                s.netclient = None
                s.netserver = srv
                s.ui        = type('UI', (), {'add_chat_message': _broadcast_reply})()
                s.chunker = srv.chunker

        self._world_wrap = _WorldWrap()


    def broadcast(self, msg, exclude_pid=None):
        with self.plock:
            for p in self.players.values():
                if p.conn and p.pid != exclude_pid:
                    self.send(p, msg)



    def send(self, p, msg, low=False):
        # one writer thread owns the socket
        if not p.conn: return
        with p.slock:
            if low: p.cq.append(msg)
            else:   p.sq.append(msg)
        p.swake.set()


    def writeloop(self, p):
        while self.running and p.conn:
            with p.slock:
                if   p.sq: m = p.sq.popleft()
                elif p.cq: m = p.cq.popleft()   # chunks only when nothing else waits
                else:
                    m = None
                    p.swake.clear()

            if m is None:
                p.swake.wait(0.5)
                continue

            try: p.sock.sendall(m)
            except Exception:
                p.conn = False
                break




    def teleport(self, p, pos):
        p.pos = pos.astype('f4')
        p.lupd  = time.time()
        p.ltele = time.time()
        self.send(p, mkservmsg(
            f"TELEPORT:{pos[0]:.3f},{pos[1]:.3f},{pos[2]:.3f}"
        ))
        
        self.broadcast(
            mkpos(p.pid, p.pos, p.yaw, p.pitch),
            exclude_pid=p.pid
        )
        
        

    def giveitem(self, p, itemId, count):
        self.send(p, mkitemcollect(itemId, count))
        return True


    def hurtpl(self, p, dmg):
        dmg = max(0, min(MAX_HEALTH, int(dmg)))
        if dmg <= 0: return #or p.health <= 0: return

        p.health = max(0, p.health - dmg)
        self.broadcast(mkplayerhurt(p.pid, dmg), exclude_pid=p.pid)
        self.send(p, mkhealth(p.health))


    def sethealth(self, p, hp):
        p.health = max(0, min(MAX_HEALTH, int(hp)))
        self.send(p, mkhealth(p.health))
        return True


    def sethunger(self, p, hg):
        p.hunger = max(0, min(MAX_HUNGER, int(hg)))
        self.send(p, mkhunger(p.hunger))
        return True



            
            
            


    MAX_COORD     = 1_000_000
    MAX_SPEED     = 80.0
    MAX_REACH     = 14
    MAX_BID       = 600
    BLOCK_RATE    = 80
    # +1 margin, client meshes need a loaded neighbour for seams
    SIM_DIST      = RENDER_DIST + 1
    STREAM_DIST   = RENDER_DIST + 1
    STREAM_MAX    = 24    # chunks queued per player per pass
    LOAD_INT      = 0.25
    MAX_CHAT      = 256
    BLOCK_MASKID = 0x3FF
    


    """
    def validpos(self, p, pos):
        if not np.all(np.isfinite(pos)): return False
        if abs(pos[0]) > self.MAX_COORD or abs(pos[2]) > self.MAX_COORD: return False
        return True
    """

    def validpos(self, p, pos):
        if not np.all(np.isfinite(pos)): return False
        if abs(pos[0]) > self.MAX_COORD or abs(pos[2]) > self.MAX_COORD: return False
        if not (-64 <= pos[1] <= CHUNK_H + 64): return False
        
        
        # grace after tp | ~speed kick
        if time.time() - p.ltele > 1.5:
            dt = time.time() - p.lupd
            if 0 < dt < 5.0:
                dist = float(np.linalg.norm(pos - p.pos))
                if dist / dt > self.MAX_SPEED: return False
        return True
        
        
        
        

    def validblock(self, p, x, y, z, bt):
        if not (0 <= y < CHUNK_H): return False
        if not (0 <= (bt & self.BLOCK_MASKID) <= self.MAX_BID): return False
        if max(abs(x + 0.5 - p.pos[0]),
               abs(y + 0.5 - p.pos[1]),
               abs(z + 0.5 - p.pos[2])
        ) > self.MAX_REACH:
            return False
            
            
        # print(p.nm, x, y, z, bt)
        now      = time.time()
        p.btimes = [t for t in p.btimes if now - t < 1.0]
        if len(p.btimes) >= self.BLOCK_RATE: return False
        p.btimes.append(now)
        return True


    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(10)
        self.sock.settimeout(1.0)
        self.running    = True
        self.start_time = time.time()
        
        print(f"Listening on {self.host}:{self.port}")
        threading.Thread(target=self._acceptloop, daemon=True).start()
        threading.Thread(target=self._tickloop,   daemon=True).start()


    def stop(self):
        print("Stopping server...")
        self.running = False
        self.broadcast(mkdisconnect("Server shutting down"))
        
        with self.plock:
            for p in list(self.players.values()):
                self.savepl(p)
                p.sock.close()
            self.players.clear()
            
            
        if self.sock:      self.sock.close()
        if self.chunker: self.chunker.shutdown()
        
        print("Server stopped.")
        
        




    def _acceptloop(self):
        while self.running:
            try:
                sock, addr = self.sock.accept()
                sock.settimeout(1.0)
                threading.Thread(target=self.onconn, args=(sock, addr), daemon=True).start()
                
                
            except socket.timeout:
                continue
                
            except Exception:
                if self.running: print("Accept error")
                
                


    """
    def onconn(self, sock, addr):
        reader = ReadMessage(sock)
        sock.settimeout(5.0)
        msg = reader.readmsg()
        if msg is None or msg[0] != MessageType.JOIN:
            sock.close(); return
        pid = self.npid; self.npid += 1
        p   = PlayerState(pid, f"Player{pid}", sock, addr)
        p.reader = reader
        with self.plock: self.players[pid] = p
        print(f"Player {pid} ({addr[0]}:{addr[1]}) connecting...")
        self.postjoin(p, msg[1])
    """

    def onconn(self, sock, addr):
        try:

            reader = ReadMessage(sock)
            sock.settimeout(5.0)
            msg = reader.readmsg()
            if msg is None: sock.close(); return
            

            mt, data = msg

            if mt == MessageType.SERVER_REQUEST:
                with self.plock: count = len(self.players)
                try:
                    from version import __VERSION__
                    motd = self.motd.replace("{VERSION}", __VERSION__).replace("{PLAYER_COUNT}", str(count))
                    sock.sendall(mksvreply(
                        self.wname, motd, count, self.maxpl))
                except Exception: pass
                sock.close(); return

            if mt != MessageType.JOIN: sock.close(); return

            pid = self.npid;  self.npid += 1
            p   = PlayerState(pid, f"Player{pid}", sock, addr)
            p.reader = reader
            with self.plock: self.players[pid] = p
            threading.Thread(target=self.writeloop, args=(p,), daemon=True).start()
            print(f"Player {pid} ({addr[0]}:{addr[1]}) connecting...")
            self.postjoin(p, data)
            
            
        except Exception:
            sock.close()
            
            
            


    def postjoin(self, p, jdata):
        try:
            tb, nm = p.reader.parse_join(jdata)
            token  = bytetoken(tb)
            p.token = token
            p.sock.settimeout(30.0)

            registry = self.loadreg()

            if token in registry:
                old  = registry[token]
                p.nm = nm
                if nm != old:
                    registry[token] = nm
                    self.savereg(registry)
                    print(f"'{old}' renamed to '{nm}' (token: {token[:8]}...)")

                with self.plock:
                    stale = [
                        o for o in self.players.values()
                        if o.token == token and o.pid != p.pid
                    ]
                    
                for s in stale:
                    s.conn = False
                    self.send(s, mkdisconnect("Logged in from another location"))
                    s.sock.close()
                    with self.plock: self.players.pop(s.pid, None)
                    self.broadcast(mkleft(s.pid))
                    
            else:
                p.nm = nm
                registry[token] = nm
                self.savereg(registry)
                print(f"Registered new player '{p.nm}' (token: {token[:8]}...)")
                

            with self.plock:
                taken = {o.nm for o in self.players.values()
                         if o.token != token and o.conn}
                         

            if p.nm in taken:
                n = 2
                while f"{p.nm}_{n}" in taken: n += 1
                p.nm = f"{p.nm}_{n}"
                

            # dont burst seed+mods+players at once
            self.send(p, mkseed(self.seed))
            time.sleep(0.01)
            # mods are baked into the chunk voxels
            self.sendents(p)
            self.send(p, mksvchunks(sorted(self.chunker.chunks.keys())))
            time.sleep(0.01)
            self.sendplrs(p)
            self.sendskins(p)
            time.sleep(0.01)
            self.broadcast(
                mkpjoin(p.pid, p.nm, p.pos),
                exclude_pid=p.pid
            )
            
            self.senditems(p)
            self.send(p, mkservmsg(f"Welcome to the server, {p.nm}!"))

            pd = self.loadpl(p.token)
            if pd and 'pos' in pd:
                pos        = pd['pos']
                p.pos = np.array(pos, dtype='f4')
                p.ltele    = time.time()
                self.send(p, mkservmsg(
                    f"TELEPORT:{pos[0]:.3f},{pos[1]:.3f},{pos[2]:.3f}"
                ))
                print(f"Restored {p.nm} to ({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f})")

            if pd and 'health' in pd: p.health = max(0, min(MAX_HEALTH, int(pd['health'])))
            if pd and 'hunger' in pd: p.hunger = max(0, min(MAX_HUNGER, int(pd['hunger'])))
            self.send(p, mkhealth(p.health))
            self.send(p, mkhunger(p.hunger))

            print(f"{p.nm} (id={p.pid}) joined from {p.addr[0]}:{p.addr[1]}")
            # print(p.token[:8])
            self.msgloop(p)
        except Exception: pass
        finally: self.disconn(p)
        
        
        


    def msgloop(self, p):
        while self.running and p.conn:
            try:
                msg = p.reader.readmsg()

                if msg is None: continue

                nulls = 0
                mt, data = msg
                # print(p.nm, mt)

                if mt == MessageType.UPDATE_POS:
                    pos, yaw, pitch, held, flags = p.reader.parse_posupdate(data)
                    if self.validpos(p, pos):
                        p.pos = pos
                        p.yaw      = yaw
                        p.pitch    = pitch
                        p._held    = held
                        p.aflags   = flags
                        p.lupd     = time.time()

                elif mt == MessageType.SKIN_UPLOAD:
                    png = p.reader.parse_skin(data)
                    if validskin(png):
                        p.skin = png
                        self.broadcast(
                            mkplayerskin(p.pid, png),
                            exclude_pid=p.pid
                        )


                elif mt == MessageType.CHUNK_REQ:
                    cx, cz = p.reader.parse_chunkreq(data)
                    p.sentck.discard((cx, cz))


                elif mt == MessageType.BLOCK_CHANGE:
                    x, y, z, bt = p.reader.parse_blockchange(data)
                    if not self.validblock(p, x, y, z, bt):
                        # resend the chunk, predicted->overwritten
                        p.sentck.discard((x // CHUNK_SZ, z // CHUNK_SZ))
                        continue

                    ignite = (bt == 0x4000)
                    if ignite: bt = 0
                    cx, cz = x // CHUNK_SZ, z // CHUNK_SZ
                    lx, lz = x - cx * CHUNK_SZ, z - cz * CHUNK_SZ
                    if not self.chunker.setblock(x, y, z, bt):
                        self.chunker.recordmod(cx, cz, lx, y, lz, bt)
                    self.queueblk(x, y, z, bt)

                    if ignite: self.ignitetnt(x, y, z)

                elif mt == MessageType.BLOCK_DMG:
                    x, y, z, st = p.reader.parse_blockdmg(data)
                    self.broadcast(mkblockdmgupd(p.pid, x, y, z, st), exclude_pid=p.pid)


                elif mt == MessageType.PLAYER_DMG:
                    self.hurtpl(p, p.reader.parse_playerdmg(data))


                elif mt == MessageType.CHAT:
                    text = p.reader.parse_chatmsg(data)
                    if len(text) > self.MAX_CHAT: text = text[:self.MAX_CHAT]
                    if text.startswith("/") and self.commands:
                        self.runcmd(p, text)
                    else:
                        full = f"{p.nm}: {text}"
                        print(f"[Chat] {full}")
                        self.broadcast(mkchat(full))

                elif mt == MessageType.ITEM_DROP:
                    iid, cnt, pos, vel = p.reader.parse_itemdrop(data)
                    self.itemdrop(iid, cnt, pos, vel)

                elif mt == MessageType.ITEM_PICKUP:
                    eid = p.reader.parse_itempickup(data)
                    self.itempickup(p, eid)
                    
                    

            except socket.timeout: continue
            except Exception: break
                
                


    def runcmd(self, p, raw):
        from commands.utils import splitline
        from commands.manager import CommandContext

        line = raw[1:].strip()
        if not line: return
        
        tokens = splitline(line)
        if not tokens: return
        
        cname = tokens[0].lower()
        args  = tokens[1:]

        args     = self.commands.injtarget(cname, args, self._world_wrap)
        entities = self.commands.gather_entities(self._world_wrap)

        executor = None
        for i in entities:
            if i.kind == "player" and i.source.pid == p.pid:
                executor = i; break

        if not executor:
            executor = entities[0] if entities else None

        if not executor:
            self.send(p, mkservmsg("Command error: could not identify executor"))
            return

        def reply(msg, color=(255, 255, 255)):
            self.send(p, mkservmsg(msg))

        self._world_wrap.ui = type('UI', (), {'add_chat_message': reply})()

        ctx = CommandContext(
            world=self._world_wrap, executor=executor,
            entities=entities, reply=reply,
        )


        try:
            spec = self.commands.registry.get(cname)
            spec.handler(ctx, args)

        except Exception as e:
            self.send(p, mkservmsg(f"Command error: {e}"))
            
            
            


        


    def loadcmods(self, fp):
        mods = {}
        try:
            with open(fp, 'rb') as f: data = f.read()
            if len(data) < 4: return mods
            cnt = struct.unpack('<I', data[:4])[0]
            off = 4
            for _ in range(cnt):
                if off + 5 > len(data): break
                lx, y, lz, bt = struct.unpack('<BBBH', data[off:off + 5])
                off += 5
                if 0 <= lx < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= lz < CHUNK_SZ:
                    mods[(lx, y, lz)] = bt
        except Exception: pass
        return mods
        
        
        
        


    def sendplrs(self, p):
        with self.plock:
            pd = {pid: {'pos': o.pos.copy(), 'nm': o.nm}
                  for pid, o in self.players.items() if pid != p.pid}
        if pd: self.send(p, mklist(pd))




    def sendskins(self, p):
        with self.plock:
            sk = [(pid, o.skin) for pid, o in self.players.items()
                  if pid != p.pid and o.skin]
        for pid, png in sk: self.send(p, mkplayerskin(pid, png))




    def senditems(self, p):
        with self.ilock:
            for eid, it in self.aitems.items():
                self.send(p, mkitemspawn(
                    eid, it['iid'], it['cnt'], it['pos'], it['vel']))




    def itemdrop(self, iid, cnt, pos, vel):
        with self.ilock:
            eid = self.newid()
            self.aitems[eid] = {
                'iid': iid, 'cnt': cnt, 'pos': np.array(pos, dtype='f4'),
                'vel': np.array(vel, dtype='f4'), 'spawn_time': time.time(),
                'grnd': False, 'still': False, 'snt': False,
            }

        self.broadcast(mkitemspawn(eid, iid, cnt, pos, vel))



    def newid(self):
        # items and entities share the eid space
        with self.eidlock:
            self._eid += 1
            return self._eid



    def itemgrav(self, it, dt):
        p, v = it['pos'], it['vel']
        bx = int(math.floor(p[0]))
        bz = int(math.floor(p[2]))

        # no chunk under it -> cant tell where the floor is, sit still
        c = self.chunker.chunks.get((bx // CHUNK_SZ, bz // CHUNK_SZ))
        if not c or not c.gen_ready:
            it['still'] = True
            return

        if it['grnd']:
            if self.chunker.issolid(bx, int(math.floor(p[1] - 0.2)), bz):
                it['still'] = True
                return

            it['grnd'] = False

        it['still'] = False

        v[1] = max(v[1] + ENT_GRAV * dt, ENT_TERMVEL)
        ny   = p[1] + v[1] * dt
        fb   = int(math.floor(ny - 0.1))

        if v[1] < 0 and self.chunker.issolid(bx, fb, bz):
            p[1] = float(fb + 1) + 0.1
            v[1] = 0.0
            it['grnd'] = True
            v[0] *= ITEM_FRIC
            v[2] *= ITEM_FRIC

        else: p[1] = ny

        p[0] += v[0] * dt
        p[2] += v[2] * dt



    def tickitems(self, dt):
        now  = time.time()
        with self.ilock:
            for i in self.aitems.values(): self.itemgrav(i, dt)
            # timed out, or fell out of the world
            old = [i for i, j in self.aitems.items()
                   if now - j['spawn_time'] > ITEM_LIFE or j['pos'][1] < 0.0]

            for i in old: del self.aitems[i]

        for eid in old: self.broadcast(mkitemdespawn(eid))



    def bcastitems(self):
        # settled ones stop costing bandwidth, one last pos when they stop
        with self.ilock:
            snap = []
            for i, j in self.aitems.items():
                if j['still'] and j['snt']: continue
                j['snt'] = j['still']
                snap.append((i, j['pos'].copy(), float(j['vel'][1])))

        for eid, pos, vy in snap: self.broadcast(mkentpos(eid, pos, vy))




    def itempickup(self, p, eid):
        with self.ilock:
            it = self.aitems.get(eid)
            if it is None: return
            # too far -> someone is reaching thru the floor
            if np.linalg.norm(it['pos'] - p.pos) > ITEM_REACH: return
            item = self.aitems.pop(eid)

        self.send(p, mkitemcollect(item['iid'], item['cnt']))
        self.broadcast(mkitemdespawn(eid))





    def regfile(self):
        return os.path.join(config.root, self.wname, "regist.json")



    def loadreg(self):
        fp = self.regfile()
        if os.path.exists(fp):
            with open(fp, 'r') as f: return json.load(f)
        return {}



    def savereg(self, reg):
        try:
            with open(self.regfile(), 'w') as f: json.dump(reg, f, indent=2)
            
        except Exception:
            print("Could not save player registry")




    def plfile(self, token):
        d = os.path.join(config.root, self.wname, "players")
        os.makedirs(d, exist_ok=True)
        return os.path.join(d, f"{token.replace('-', '')}.json")


    def loadpl(self, token):
        fp = self.plfile(token)
        if os.path.exists(fp):
            with open(fp, 'r') as f: return json.load(f)
        return None



    def savepl(self, p):
        try:
            data = {
                'nm': p.nm, 'token': p.token,
                'pos': p.pos.tolist(),
                'yaw': float(p.yaw), 'pitch': float(p.pitch),
                'health': int(p.health),
                'hunger': int(p.hunger),
            }
            with open(self.plfile(p.token), 'w') as f: json.dump(data, f)
        except Exception:
            print(f"Could not save player data for {p.nm}")






    def disconn(self, p):
        self.savepl(p)
        p.conn = False
        p.swake.set()   # let the writer notice
        p.sock.close()
        with self.plock: self.players.pop(p.pid, None)
        print(f"{p.nm} (id={p.pid}) disconnected")
        self.broadcast(mkleft(p.pid))




    def pcount(self):
        with self.plock: return len(self.players)

    def pllist(self):
        with self.plock:
            return [(p.pid, p.nm, p.pos.copy())
                    for p in self.players.values() if p.conn]



    def bcastmsg(self, msg):
        self.broadcast(mkservmsg(msg))
        print(f"[Server] {msg}")



    def kick(self, nm, reason="Kicked by server"):
        kicked = None
        with self.plock:
            for p in list(self.players.values()):
                if p.nm.lower() == nm.lower():
                    self.savepl(p)
                    self.send(p, mkdisconnect(reason))
                    p.conn = False
                    p.sock.close()
                    del self.players[p.pid]
                    print(f"Kicked {p.nm}: {reason}")
                    kicked = p
                    break
        if kicked:
            self.broadcast(mkleft(kicked.pid))
            return True
        return False



    """
    def _tickloop(self):
        while self.running:
            t0 = time.time()
            self._bcastpos()
            dt = time.time() - t0
            if dt < self.tint:
                time.sleep(self.tint - dt)
    """

    def _tickloop(self):
        lpos = time.time()
        lt   = time.time()
        lld  = 0.0
        while self.running:
            t0 = time.time()
            dt = t0 - lt
            lt = t0
            if t0 - lld >= self.LOAD_INT:
                self.updateloads()
                lld = t0
            self.tickents(dt)
            self.tickitems(dt)
            self.flushblks()
            if t0 - lpos >= self.pint:
                self._bcastpos()
                self.bcastents()
                self.bcastitems()
                lpos = t0
            sd = time.time() - t0
            if sd < self.tint: time.sleep(self.tint - sd)



    def updateloads(self):
        cs = set()
        with self.plock:
            for p in self.players.values():
                if not p.conn: continue
                cs.add((int(p.pos[0] // CHUNK_SZ), int(p.pos[2] // CHUNK_SZ)))

        with self.tntlock:
            for e in self.ents.values():
                cs.add((int(e[1] // CHUNK_SZ), int(e[3] // CHUNK_SZ)))

        self.chunker.updateloadsmulti(sorted(cs))
        self.streamchunks()

        keys = sorted(self.chunker.chunks.keys())
        if keys != self._lastkeys:
            rdy = sum(1 for c in self.chunker.chunks.values() if c.gen_ready)
            print(f"chunks: {rdy}/{len(keys)} generated, {len(cs)} centers, {len(self.ents)} entities")
            self._lastkeys = keys
            self.broadcast(mksvchunks(keys))


    def streamchunks(self):
        # ready voxels -> anyone close enough who hasnt got them
        with self.plock:
            pl = [p for p in self.players.values() if p.conn]

        # late decor landed on chunks already sent -> they go again
        dd = self.chunker.decordirty
        if dd:
            stale = set(dd); dd.clear()
            for p in pl: p.sentck -= stale

        r2 = self.STREAM_DIST * self.STREAM_DIST
        for p in pl:
            pcx = int(p.pos[0] // CHUNK_SZ)
            pcz = int(p.pos[2] // CHUNK_SZ)
            want = set()

            for dx in range(-self.STREAM_DIST, self.STREAM_DIST + 1):
                for dz in range(-self.STREAM_DIST, self.STREAM_DIST + 1):
                    if dx * dx + dz * dz > r2: continue
                    want.add((pcx + dx, pcz + dz))

            
            p.sentck &= want

            # nearest first so the world fills in around him
            todo = sorted(want - p.sentck,
                          key=lambda k: (k[0] - pcx) ** 2 + (k[1] - pcz) ** 2)

            for k in todo[:self.STREAM_MAX]:
                c = self.chunker.chunks.get(k)
                if not c or not c.gen_ready: continue
                self.send(p, mkchunk(k[0], k[1], c.voxels), low=True)
                p.sentck.add(k)


    def queueblk(self, x, y, z, bt):
        with self.blklock: self.pendblk[(x, y, z)] = bt


    def flushblks(self):
        with self.blklock:
            if not self.pendblk: return
            chgs = [(x, y, z, bt) for (x, y, z), bt in self.pendblk.items()]
            self.pendblk.clear()

        # chunked broadcast
        for i in range(0, len(chgs), 512):
            self.broadcast(mkblockbulk(chgs[i:i+512]))


    def spawnent(self, kind, x, y, z, life, vy=ENT_IVELY):
        eid = self.newid()
        with self.tntlock:
            # x/z centred on the block, y = cube bottom
            self.ents[eid] = [kind, x + 0.5, float(y), z + 0.5, vy, life, False]
            e = self.ents[eid]

        self.broadcast(mkentspawn(eid, kind, (e[1], e[2], e[3]), life))
        return eid


    def ignitetnt(self, x, y, z, fuse=TNT_FUSE):
        self.spawnent(TNT_ID, x, y, z, fuse)


    def sendents(self, p):
        # late joiner gets whats already alive
        with self.tntlock:
            snap = [(i, e[0], e[1], e[2], e[3], e[5]) for i, e in self.ents.items()]
        for eid, kind, x, y, z, life in snap:
            self.send(p, mkentspawn(eid, kind, (x, y, z), life))


    def entdeath(self, kind, x, y, z):
        if kind == TNT_ID: self.explodetnt(x, y, z)


    def entgrav(self, e, dt):
        bx = int(math.floor(e[1]))
        bz = int(math.floor(e[3]))

        if e[6]:
            if not self.chunker.issolid(bx, int(math.floor(e[2])) - 1, bz):
                e[6] = False
                e[4] = 0.0
            return

        e[4] = max(e[4] + ENT_GRAV * dt, ENT_TERMVEL)
        ny   = e[2] + e[4] * dt

        if e[4] < 0:
            fb = int(math.floor(ny - 0.001))
            if self.chunker.issolid(bx, fb, bz):
                e[2] = float(fb + 1)
                e[4] = 0.0
                e[6] = True
            else:
                e[2] = ny
        else:
            cb = int(math.floor(ny + 1.001))
            if self.chunker.issolid(bx, cb, bz):
                e[2] = float(cb) - 1.0
                e[4] = 0.0
            else:
                e[2] = ny


    def tickents(self, dt):
        with self.tntlock:
            if not self.ents: return
            for e in self.ents.values():
                self.entgrav(e, dt)
                e[5] -= dt

            done = [(i, e) for i, e in self.ents.items() if e[5] <= 0.0]
            for i, _ in done: del self.ents[i]

        for eid, e in done:
            self.broadcast(mkentgone(eid))
            self.entdeath(e[0], e[1], e[2], e[3])


    def bcastents(self):
        with self.tntlock:
            snap = [(i, e[1], e[2], e[3], e[4]) for i, e in self.ents.items()]
        for eid, x, y, z, vy in snap:
            self.broadcast(mkentpos(eid, (x, y, z), vy))


    def explodetnt(self, ex, ey, ez):
        # centre of the 1x1x1 cube -> block it sits in
        ox = int(math.floor(ex))
        oy = int(math.floor(ey + 0.5))
        oz = int(math.floor(ez))
        chain = []

        for dx, dy, dz in _TNT_OFFS:
            bx, by, bz = ox + dx, oy + dy, oz + dz
            if by < 0 or by >= CHUNK_H: continue

            prev = self.chunker.getblock(bx, by, bz)
            if prev == 0: continue           # nothing to destroy
            if prev == BEDROCK_ID: continue  # indestructible
            if prev == TNT_ID: chain.append((bx, by, bz))

            cx, cz = bx // CHUNK_SZ, bz // CHUNK_SZ
            lx, lz = bx - cx * CHUNK_SZ, bz - cz * CHUNK_SZ
            if not self.chunker.setblock(bx, by, bz, 0):
                self.chunker.recordmod(cx, cz, lx, by, lz, 0)
            self.queueblk(bx, by, bz, 0)

        for bx, by, bz in chain:
            self.spawnent(TNT_ID, bx, by, bz,
                          random.uniform(TNT_CFUSE_MIN, TNT_CFUSE_MAX))



    def _bcastpos(self):
        with self.plock: plist = list(self.players.values())
        now  = time.time()
        msgs = []
        _sent = 0
        for p in plist:
            if p.conn and now - p.lupd < 1.0:
                msgs.append((p.pid, mkpos(
                    p.pid, p.pos, p.yaw, p.pitch, p._held, p.aflags)))
        with self.plock:
            for o in self.players.values():
                if not o.conn: continue
                for pid, msg in msgs:
                    if pid != o.pid: self.send(o, msg)


