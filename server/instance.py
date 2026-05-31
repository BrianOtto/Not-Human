import json
import math
import random
import socket
import threading
import time
import struct
import os
import numpy as np
from world.terrain import ChunkManager, PerlinNoise
import config
from config import (
    CHUNK_SZ, CHUNK_H, SV_PORT, SV_HOST, SEED,
    SV_RATE, SV_TIMEOUT, SV_MAXONLINE, SV_MOTD,
)
from network.protocol import (
    MessageType, ReadMessage,
    mkservmsg, mkpos, mkitemcollect, mkdisconnect, mksvreply, mkleft, mkseed, mkpjoin,
    mkblockupd, mkchat, mkitemspawn, mkitemdespawn, mkmods, mklist,
)
from identity import bytetoken


# tnt
TNT_ID         = 60
TNT_FUSE       = 4.0
TNT_CFUSE_MIN  = 0.5
TNT_CFUSE_MAX  = 1.5
TNT_BLAST_R    = 4.0


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
        self.lupd   = time.time()
        self.reader = ReadMessage(sock)
        self.conn   = True
        self.btimes = []
        self.ltele  = 0.0


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
        self.tnts    = []   # [x, y, z, fuse]
        self.tntlock = threading.Lock()

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
            self.world, render_dist=1,
            wname=self.wname, is_server=True,
        )
        
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
                    try: p.sock.sendall(msg)
                    except Exception: pass
                    
                    

    def send(self, p, msg):
        try: p.sock.sendall(msg)
        except Exception: pass
        
        


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
        try:
            p.sock.sendall(mkitemcollect(itemId, count))
            return True
            
        except Exception:
            return False
            
            
            
            
            


    MAX_COORD     = 1_000_000
    MAX_SPEED     = 80.0
    MAX_REACH     = 14
    MAX_BID       = 600
    BLOCK_RATE    = 20
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
            print(f"Player {pid} ({addr[0]}:{addr[1]}) connecting...")
            self.postjoin(p, data)
            
            
        except Exception:
            sock.close()
            
            
            


    def postjoin(self, p, jdata):
        try:
            tb, nm = p.reader.parse_join(jdata)
            token  = bytetoken(tb)
            p.token = token
            p.sock.settimeout(1.0)

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
            self.sendmods(p)
            time.sleep(0.01)
            self.sendplrs(p)
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

            print(f"{p.nm} (id={p.pid}) joined from {p.addr[0]}:{p.addr[1]}")
            # print(p.token[:8])
            self.msgloop(p)
        except Exception: pass
        finally: self.disconn(p)
        
        
        


    def msgloop(self, p):
        nulls = 0
        while self.running and p.conn:
            try:
                msg = p.reader.readmsg()

                if msg is None:
                    nulls += 1
                    if nulls > 1000:
                        try:
                            p.sock.settimeout(0.1)
                            if not p.sock.recv(1, socket.MSG_PEEK): break
                            p.sock.settimeout(1.0)
                            nulls = 0

                        except socket.timeout:
                            p.sock.settimeout(1.0)
                            nulls = 0

                        except (socket.error, OSError): break

                    else: time.sleep(0.01)
                    continue

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

                elif mt == MessageType.BLOCK_CHANGE:
                    x, y, z, bt = p.reader.parse_blockchange(data)
                    if bt == 0x2000:
                        self.detonate(x, y, z)
                        continue
                    if self.validblock(p, x, y, z, bt):
                        ignite = (bt == 0x4000)
                        if ignite: bt = 0
                        cx, cz = x // CHUNK_SZ, z // CHUNK_SZ
                        lx, lz = x - cx * CHUNK_SZ, z - cz * CHUNK_SZ
                        if not self.chunker.setblock(x, y, z, bt):
                            self.chunker.recordmod(cx, cz, lx, y, lz, bt)
                        self.broadcast(
                            mkblockupd(x, y, z, bt),
                            exclude_pid=p.pid)

                        if ignite: self.ignitetnt(x, y, z)

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

        args     = self.commands._injdefault(cname, args, self._world_wrap)
        entities = self.commands.gather_entities(self._world_wrap)

        executor = None
        for e in entities:
            if e.kind == "player" and e.source.pid == p.pid:
                executor = e; break
                
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
            
            
            


    def sendmods(self, p):
        mods = {}
        cdir = os.path.join(config.root, self.wname)
        if os.path.exists(cdir):
            for fn in os.listdir(cdir):
                if not fn.endswith('.dat'): continue
                try:
                    pts = fn[:-4].split('_')
                    if len(pts) == 2:
                        cx, cz = int(pts[0]), int(pts[1])
                        j = self.loadcmods(os.path.join(cdir, fn))
                        if j: mods[(cx, cz)] = j
                except Exception:
                    continue
        # merge .dat files + memcache
        for (cx, cz), j in self.chunker.modCache.items():
            if (cx, cz) not in mods: mods[(cx, cz)] = {}
            mods[(cx, cz)].update(j)
        p.sock.sendall(mkmods(mods))
        
        
        


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




    def senditems(self, p):
        with self.ilock:
            for eid, it in self.aitems.items():
                self.send(p, mkitemspawn(
                    eid, it['iid'], it['cnt'], it['pos'], it['vel']))




    def itemdrop(self, iid, cnt, pos, vel):
        with self.ilock:
            eid = self.neid;  self.neid += 1
            self.aitems[eid] = {
                'iid': iid, 'cnt': cnt, 'pos': pos,
                'vel': vel, 'spawn_time': time.time(),
            }
            
        self.broadcast(mkitemspawn(eid, iid, cnt, pos, vel))




    def itempickup(self, p, eid):
        with self.ilock:
            if eid not in self.aitems: return
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
            }
            with open(self.plfile(p.token), 'w') as f: json.dump(data, f)
        except Exception:
            print(f"Could not save player data for {p.nm}")






    def disconn(self, p):
        self.savepl(p)
        p.conn = False
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
        while self.running:
            t0 = time.time()
            dt = t0 - lt
            lt = t0
            self.ticktnts(dt)
            if t0 - lpos >= self.pint:
                self._bcastpos()
                lpos = t0
            sd = time.time() - t0
            if sd < self.tint: time.sleep(self.tint - sd)



    def ignitetnt(self, x, y, z, fuse=30.0):
        # fallback fuse
        # client driven via detonate
        with self.tntlock:
            self.tnts.append([x, y, z, fuse])


    def detonate(self, x, y, z):
        # match by col (y) -> blast at the client-provided pos
        with self.tntlock:
            mi = None
            for i, t in enumerate(self.tnts):
                if t[0] == x and t[2] == z:
                    mi = i; break
            if mi is None: return
            del self.tnts[mi]
        self.explodetnt(x, y, z)


    def ticktnts(self, dt):
        with self.tntlock:
            if not self.tnts: return
            for t in self.tnts: t[3] -= dt
            ready    = [t for t in self.tnts if t[3] <= 0.0]
            self.tnts = [t for t in self.tnts if t[3] > 0.0]

        for x, y, z, _ in ready:
            self.explodetnt(x, y, z)


    def explodetnt(self, ox, oy, oz):
        # server has no loaded chunks -> work directly off modCache.
        # every sphere position is recorded as destroyed + broadcast to clients.
        chain = []

        for dx, dy, dz in _TNT_OFFS:
            bx, by, bz = ox + dx, oy + dy, oz + dz
            if by < 0 or by >= CHUNK_H: continue
            cx, cz = bx // CHUNK_SZ, bz // CHUNK_SZ
            lx, lz = bx - cx * CHUNK_SZ, bz - cz * CHUNK_SZ

            prev = self.chunker.modCache.get((cx, cz), {}).get((lx, by, lz), 0)
            if (prev & 0x3FF) == TNT_ID:
                chain.append((bx, by, bz))

            if not self.chunker.setblock(bx, by, bz, 0):
                self.chunker.recordmod(cx, cz, lx, by, lz, 0)
            self.broadcast(mkblockupd(bx, by, bz, 0))

        if chain:
            new = [[bx, by, bz, random.uniform(TNT_CFUSE_MIN, TNT_CFUSE_MAX)] for bx, by, bz in chain]
            with self.tntlock: self.tnts.extend(new)



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
                    if pid != o.pid:
                        try: o.sock.sendall(msg)
                        except Exception: pass


