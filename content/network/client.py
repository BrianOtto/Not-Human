import os
import socket
import threading
import time
import numpy as np
from network.protocol import (
    MessageType, ReadMessage, validskin,
    mkjoin, mkposupd, mkblockchg, mkchat, mkitemdrop, mkitempick, mksvrq,
    mkchunkreq, mkskin,
)
from config import SV_PORT, SV_TIMEOUT, CL_UPD_INT
from identity import whoami, get_tokenbytes
import _respath


class RemotePlayer:
    def __init__(self, pid, nm, pos):
        self.pid    = pid
        self.nm     = nm
        self.pos = pos.copy()
        self.yaw    = 0.0
        self.pitch  = 0.0
        self.ppos   = pos.copy()
        self.tpos   = pos.copy()
        self.pyaw   = 0.0
        self.tyaw   = 0.0
        self.ppitch = 0.0
        self.tpitch = 0.0
        self.stime  = time.time()
        self.pstime = time.time()
        self.lupd   = time.time()
        self.velocity = np.zeros(3, dtype='f4')
        self.atime  = 0.0
        self._held  = 0
        self.aflags = 0
        self.swingt = 0.0
        self.skin   = None



class NetworkClient:
    def __init__(self, host='localhost', port=SV_PORT, pname="Player", ui_callback=None):
        self.host  = host
        self.port  = port
        self.pname = pname
        self.ucb   = ui_callback
        self.sock  = None
        self.conn  = False
        self.reader = None

        self.world_seed    = None
        self.seed_received = False
        self.drsn = ""
        self._dcfired = False
        self.rpl  = {}
        self.plock = threading.Lock()
        self.wlock = threading.Lock()

        # callbacks, set by caller
        self.on_seed        = None
        self.on_playerjoin  = None
        self.on_playerleft  = None
        self.on_update      = None
        self.on_entspawn    = None
        self.on_entpos      = None
        self.on_entgone     = None
        self.on_svchunks    = None
        self.on_chunk       = None
        self.on_svmsg       = None
        self.on_chatmsg     = None
        self.on_itemspawn   = None
        self.on_itemdespawn = None
        self.on_itemcollect = None
        #self.on_itempick    = None
        self.on_teleport    = None
        self.on_disconnect  = None
        

        self.lsend      = 0
        self.psi        = CL_UPD_INT
        self.lpos       = None
        self.lyaw       = None
        self.lpitch     = None
        self._last_held = -1
        self._last_anif = -1
        self.pct        = 0.05
        self.rct        = 1.0
        self._last_ping = 0.0
        
        


    @staticmethod
    def svping(host, port, timeout=2.0):
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.sendall(mksvrq())
            reader = ReadMessage(sock)
            msg    = reader.readmsg()
            sock.close()
            
            if msg and msg[0] == MessageType.SERVER_RESPONSE:
                return reader.parse_svreplyinfo(msg[1])
                
                
        except Exception:
            pass
            
            
        return None






    def log(self, msg, color=(200, 200, 200)):
        print(msg)
        if self.ucb: self.ucb(msg, color)
        
        
        





    def connect(self):
        identity = whoami()
        if self.pname == "Player": self.pname = identity['nm']
        token      = get_tokenbytes(identity)
        self.token = identity['token']

        # print(self.host, self.port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(5.0)
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(30.0)
        self.reader = ReadMessage(self.sock)
        self.conn   = True
        
        self.sock.sendall(mkjoin(self.pname, token))
        self.sendskin()
        self._recv_thread = threading.Thread(target=self._recvloop, daemon=True)
        self._recv_thread.start()
        
        return True




    def drop(self, reason="connection lost"):
        self.conn = False
        if self._dcfired: return
        self._dcfired = True
        if not self.drsn: self.drsn = reason
        if self.on_disconnect: self.on_disconnect(self.drsn)


    def disconnect(self):
        self._dcfired = True #dont bounce cb back
        self.conn = False
        if self.sock:
            try: self.sock.close()
            except Exception: pass
            self.sock = None





    def sendpos(self, pos, yaw, pitch, _held=0, anim_flags=0):
        if not self.conn: return
        now  = time.time()
        echg = (_held != self._last_held or anim_flags != self._last_anif)
        pchg = rchg = True
        

        if self.lpos is not None:
            pchg = np.linalg.norm(pos - self.lpos) >= self.pct
            yd = abs(yaw - self.lyaw);     yd = 360 - yd if yd > 180 else yd
            pd = abs(pitch - self.lpitch); pd = 360 - pd if pd > 180 else pd
            rchg = yd >= self.rct or pd >= self.rct
            

        if now - self.lsend < self.psi:
            if not pchg and not rchg and not echg: return
            
        if now - self.lsend > 0.2: pchg = True
        
        

        if not (pchg or rchg or echg): return
        # print(pos, yaw)

        self.lsend      = now
        self.lpos       = pos.copy()
        self.lyaw       = yaw
        self.lpitch     = pitch
        self._last_held = _held
        self._last_anif = anim_flags
        self.wsend(mkposupd(pos, yaw, pitch, _held, anim_flags))
            
            
     
            
                   
                                 
            


    def wsend(self, msg):
        if not self.conn: return
        with self.wlock:
            try: self.sock.sendall(msg)
            except Exception: self.drop()


    def sendchange(self, x, y, z, bt):
        self.wsend(mkblockchg(x, y, z, bt))


    def sendchat(self, msg):
        self.wsend(mkchat(msg))


    def senddrop(self, iid, cnt, pos, vel):
        self.wsend(mkitemdrop(iid, cnt, pos, vel))


    def sendpickup(self, eid):
        self.wsend(mkitempick(eid))


    def sendskin(self):
        fp = _respath.text_player()
        if not os.path.exists(fp): return

        with open(fp, 'rb') as f: png = f.read()
        if validskin(png): self.wsend(mkskin(png))


    def sendchunkreq(self, cx, cz):
        self.wsend(mkchunkreq(cx, cz))
        
       
        
          


    def _recvloop(self):
        self.log(f"connected as {self.pname}", (200, 255, 200))
        time.sleep(0.2)

        while self.conn:
            try:
                msg = self.reader.readmsg()
                if msg is None: continue

                mt, data = msg
                # print(mt)

                if mt == MessageType._SEED:
                    self.world_seed    = self.reader.parse_seed(data)
                    self.seed_received = True
                    if self.on_seed: self.on_seed(self.world_seed)
                    


                elif mt == MessageType.PLAYER_JOIN:
                    pid, nm, pos = self.reader.parse_playerjoin(data)
                    now = time.time()
                    with self.plock:
                        p = RemotePlayer(pid, nm, pos)
                        p.ppos   = pos.copy()
                        p.tpos   = pos.copy()
                        p.stime  = now
                        p.pstime = now
                        self.rpl[pid] = p
                        
                    if self.on_playerjoin: self.on_playerjoin(pid, nm, pos)
                    
                    
                    
                    

                elif mt == MessageType.PLAYER_SKIN:
                    pid, png = self.reader.parse_playerskin(data)
                    if validskin(png):
                        with self.plock:
                            if pid in self.rpl: self.rpl[pid].skin = png


                elif mt == MessageType.PLAYER_LEFT:
                    pid = self.reader.parse_playerleft(data)
                    with self.plock: self.rpl.pop(pid, None)
                    if self.on_playerleft: self.on_playerleft(pid)
                    
                    
                    

                elif mt == MessageType.PLAYER_POS:
                    pid, pos, yaw, pitch, _held, afl = self.reader.parse_playerpos(data)
                    with self.plock:
                        if pid not in self.rpl: continue
                        p    = self.rpl[pid]
                        pos  = np.clip(pos, -1e6, 1e6)
                        if not np.all(np.isfinite(pos)): continue
                        now  = time.time()
                        dt   = now - p.pstime
                        p.velocity = np.clip((pos - p.tpos) / dt, -1000.0, 1000.0) if dt > 0.001 else np.zeros(3, dtype='f4')
                        p.pstime = p.stime; p.stime  = now
                        p.ppos   = p.tpos.copy()
                        p.pyaw   = p.tyaw; p.ppitch = p.tpitch
                        p.tpos   = pos.copy()
                        p.tyaw   = yaw;      p.tpitch = pitch
                        p._held  = _held
                        if afl & 1 and p.swingt <= 0: p.swingt = 0.3
                        p.aflags = afl
                        p.lupd   = now
                        
                        

                elif mt == MessageType.BLOCK_UPDATE:
                    x, y, z, bt = self.reader.parse_blockupdate(data)
                    if self.on_update: self.on_update(x, y, z, bt)


                elif mt == MessageType.ENTITY_SPAWN:
                    eid, kind, pos, life = self.reader.parse_entspawn(data)
                    if self.on_entspawn: self.on_entspawn(eid, kind, pos, life)


                elif mt == MessageType.ENTITY_POS:
                    eid, pos, vy = self.reader.parse_entpos(data)
                    if self.on_entpos: self.on_entpos(eid, pos, vy)


                elif mt == MessageType.ENTITY_GONE:
                    eid = self.reader.parse_entgone(data)
                    if self.on_entgone: self.on_entgone(eid)


                elif mt == MessageType.BLOCK_BULK:
                    for x, y, z, bt in self.reader.parse_blockbulk(data):
                        if self.on_update: self.on_update(x, y, z, bt)


                elif mt == MessageType.CHUNK_DATA:
                    cx, cz, vox = self.reader.parse_chunk(data)
                    if self.on_chunk: self.on_chunk(cx, cz, vox)


                elif mt == MessageType.SV_CHUNKS:
                    keys = self.reader.parse_svchunks(data)
                    if self.on_svchunks: self.on_svchunks(keys)
                    
                    

                elif mt == MessageType.PLAYER_LIST:
                    players = self.reader.parse_list(data)
                    now     = time.time()
                    
                    with self.plock:
                        for i, j in players.items():
                            p        = RemotePlayer(i, j['nm'], j['pos'])
                            p.ppos   = j['pos'].copy()
                            p.tpos   = j['pos'].copy()
                            p.stime  = now
                            p.pstime = now
                            self.rpl[i] = p
                            



                elif mt == MessageType.SV_MESSAGE:
                    text = self.reader.parse_svmsg(data)
                    if self.on_svmsg: self.on_svmsg(text)

                elif mt == MessageType.CHAT:
                    text = self.reader.parse_chatmsg(data)
                    if self.on_chatmsg: self.on_chatmsg(text)

                elif mt == MessageType.ITEM_SPAWN:
                    eid, iid, cnt, pos, vel = self.reader.parse_itemspawn(data)
                    if self.on_itemspawn: self.on_itemspawn(eid, iid, cnt, pos, vel)

                elif mt == MessageType.ITEM_DESPAWN:
                    eid = self.reader.parse_itemdespawn(data)
                    if self.on_itemdespawn: self.on_itemdespawn(eid)

                elif mt == MessageType.ITEM_COLLECT:
                    iid, cnt = self.reader.parse_itemcollect(data)
                    if self.on_itemcollect: self.on_itemcollect(iid, cnt)

                elif mt == MessageType.DISCONNECT:
                    reason   = self.reader.parse_disconnect(data)
                    self.drsn = reason
                    self.log(f"disconnected by server: {reason}", (255, 150, 150))
                    break
                    
                    
                    

            except socket.timeout:
                continue
                
            except Exception as e:
                if self.conn: self.log(str(e), (255, 150, 150))
                break
                
                
                

        if not self._dcfired: self.log("client disconnect", (255, 200, 200))
        self.drop()
            




    def remoteplayers(self):
        with self.plock: return dict(self.rpl)





    """
    def interp(self, dt):
        with self.plock:
            for i, j in self.rpl.items():
                j.pos = j.tpos.copy()
                j.yaw = j.tyaw


    def sendpos(self, pos, yaw, pitch, _held=0, anim_flags=0):
        if not self.conn: return
        try: self.sock.sendall(mkposupd(pos, yaw, pitch, _held, anim_flags))
        except Exception: self.conn = False
    """




    def interp(self, dt):
        with self.plock:
            now   = time.time()
            stale = []

            for i, j in self.rpl.items():
                if now - j.lupd > SV_TIMEOUT:
                    stale.append(i); continue

                if j.swingt > 0: j.swingt -= dt

                idur   = j.stime - j.pstime
                idelay = 0.05
                
                if idur > 0.001:
                    ts   = now - j.pstime - idelay
                    edur = max(idur, 0.033)
                    t    = min(1.0, max(0.0, ts / edur))
                    
                else:
                    t = 1.0
                    
                    

                # print(i, t)
                if t < 1.0:
                    st  = t * t * (3.0 - 2.0 * t)   # smoothstep
                    j.pos = j.ppos * (1.0 - st) + j.tpos * st
                    yd = j.tyaw - j.pyaw
                    
                    if yd > 180: yd -= 360
                    elif yd < -180: yd += 360
                    
                    j.yaw = j.pyaw + yd * st
                    pd = j.tpitch - j.ppitch
                    
                    if pd > 180: pd -= 360
                    elif pd < -180: pd += 360
                    j.pitch = j.ppitch + pd * st
                    
                    
                else:
                    ts = now - j.stime - idelay
                    if 0 < ts < 0.25:
                        damp       = 1.0 - (ts / 0.25)
                        j.pos = j.tpos + j.velocity * ts * damp
                        j.yaw      = j.tyaw
                        j.pitch    = j.tpitch
                        
                    else:
                        j.pos = j.tpos.copy()
                        j.yaw      = j.tyaw
                        j.pitch    = j.tpitch

            for i in stale: del self.rpl[i]


    def isconn(self):
        return self.conn and self.sock is not None



















