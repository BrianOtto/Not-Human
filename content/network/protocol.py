import struct
import socket
import select
import zlib
import numpy as np
from enum import IntEnum
from config import CHUNK_SZ, CHUNK_H


class MessageType(IntEnum):
    JOIN            = 1
    UPDATE_POS      = 2
    BLOCK_CHANGE    = 3
    SKIN_UPLOAD     = 4
    BLOCK_DMG       = 5
    PLAYER_DMG      = 6
    PLAYER_ATTACK   = 7
    _SEED           = 10
    PLAYER_JOIN     = 11
    PLAYER_LEFT     = 12
    PLAYER_POS      = 13
    BLOCK_UPDATE    = 14
    PLAYER_LIST     = 15
    SV_MESSAGE      = 16
    MODS            = 17
    CHAT            = 18
    PLAYER_SKIN     = 19
    ITEM_DROP       = 22
    ITEM_PICKUP     = 23
    ITEM_COLLECT    = 24
    ENTITY_SPAWN    = 40
    ENTITY_STATE    = 41
    ENTITY_GONE     = 42
    ENTITY_HURT     = 51
    ENTITY_ANIM     = 52
    ENTITY_ATTACK   = 53
    ENTITY_DBG      = 54
    DBG_MODE        = 55
    SV_CHUNKS       = 43
    BLOCK_BULK      = 44
    CHUNK_DATA      = 45
    CHUNK_REQ       = 46
    BLOCK_DAMAGE    = 47
    PLAYER_HURT     = 48
    PLAYER_HEALTH   = 49
    PLAYER_HUNGER   = 50
    SERVER_REQUEST  = 30
    SERVER_RESPONSE = 31
    DISCONNECT      = 32


MT = MessageType

# RANGE != kill := client must not run death fx
GONE_DESPAWN = 0
GONE_DEATH   = 1
GONE_RANGE   = 2

ENT_MAXBATCH = 200   # ents p ENTITY_STATE packet

SKIN_MAX  = 256 * 1024
PNG_MAGIC = b'\x89PNG\r\n\x1a\n'


def validskin(png):
    return bool(png) and len(png) <= SKIN_MAX and png[:8] == PNG_MAGIC




def mkjoin(nm, tb=b'\x00' * 16):
    b = nm.encode('utf-8')
    return struct.pack('<B16sI', MT.JOIN, tb, len(b)) + b




def mkposupd(pos, yaw, pitch, _held=0, anim_flags=0):
    return struct.pack(
        '<B3f2fHB', MT.UPDATE_POS,
        float(pos[0]), float(pos[1]), float(pos[2]),
        float(yaw), float(pitch), _held, anim_flags
    )







def mkskin(png):
    return struct.pack('<BI', MT.SKIN_UPLOAD, len(png)) + png



def mkplayerskin(pid, png):
    return struct.pack('<BII', MT.PLAYER_SKIN, pid, len(png)) + png



def mkblockchg(x, y, z, bt):
    return struct.pack('<BiiiH', MT.BLOCK_CHANGE, x, y, z, bt)



# stage 0-9, -1 = mine stop
def mkblockdmg(x, y, z, stage):
    return struct.pack('<Biiib', MT.BLOCK_DMG, x, y, z, stage)



def mkblockdmgupd(pid, x, y, z, stage):
    return struct.pack('<BIiiib', MT.BLOCK_DAMAGE, pid, x, y, z, stage)



def mkplayerdmg(dmg):
    return struct.pack('<BB', MT.PLAYER_DMG, min(255, max(0, dmg)))



def mkplayerhurt(pid, dmg):
    return struct.pack('<BIB', MT.PLAYER_HURT, pid, min(255, max(0, dmg)))




def mkhealth(hp):
    return struct.pack('<BB', MT.PLAYER_HEALTH, min(255, max(0, hp)))



def mkhunger(hg):
    return struct.pack('<BB', MT.PLAYER_HUNGER, min(255, max(0, hg)))



def mkseed(seed):
    return struct.pack('<BI', MT._SEED, seed)



def mkpjoin(pid, nm, pos):
    b = nm.encode('utf-8')
    return struct.pack(
        '<BI3fI', MT.PLAYER_JOIN, pid,
        float(pos[0]), float(pos[1]),
        float(pos[2]), len(b)
    ) + b



def mkleft(pid):
    return struct.pack('<BI', MT.PLAYER_LEFT, pid)



def mkpos(pid, pos, yaw, pitch, _held=0, anim_flags=0):
    return struct.pack(
        '<BI3f2fHB', MT.PLAYER_POS, pid,
        float(pos[0]), float(pos[1]), float(pos[2]),
        float(yaw), float(pitch), _held, anim_flags
    )



def mkblockupd(x, y, z, bt):
    return struct.pack('<BiiiH', MT.BLOCK_UPDATE, x, y, z, bt)



def mkentspawn(eid, kind, pos, yaw=0.0, hp=0, flags=0, pay=b''):
    return struct.pack(
        '<BIH3ffHBH', MT.ENTITY_SPAWN, eid, kind,
        float(pos[0]), float(pos[1]), float(pos[2]),
        float(yaw), hp, flags, len(pay)
    ) + pay



# [(eid, pos, yaw, vy, hoff, anim)] -> single packet.
# hoff = hyaw->byte
def mkentstate(ents):

    d = struct.pack('<BH', MT.ENTITY_STATE, len(ents))
    for eid, pos, yaw, vy, hoff, anim in ents:

        d += struct.pack(
            '<I3fffbB', eid,
            float(pos[0]), float(pos[1]), float(pos[2]),
            float(yaw), float(vy),
            max(-127, min(127, int(hoff * 127.0 / 180.0))), anim
        )


    return d



def mkentgone(eid, reason=GONE_DESPAWN):
    return struct.pack('<BIB', MT.ENTITY_GONE, eid, reason)



def mkenthurt(eid, dmg):
    return struct.pack('<BIB', MT.ENTITY_HURT, eid, min(255, max(0, dmg)))



def mkentanim(eid, anim):
    return struct.pack('<BIB', MT.ENTITY_ANIM, eid, anim)



def mkentattack(eid):
    return struct.pack('<BI', MT.ENTITY_ATTACK, eid)



def mkplattack(pid):
    return struct.pack('<BI', MT.PLAYER_ATTACK, pid)



DBG_MAXPTS = 24

# debug path + goal
def mkentdbg(eid, pts, txt):
    b = txt.encode('utf-8')[:255]
    n = min(len(pts), DBG_MAXPTS)

    d = struct.pack('<BIB', MT.ENTITY_DBG, eid, n)
    for i in pts[:n]:
        d += struct.pack('<3f', float(i[0]), float(i[1]), float(i[2]))

    return d + struct.pack('<B', len(b)) + b



def mkdbgmode(on):
    return struct.pack('<BB', MT.DBG_MODE, 1 if on else 0)




def packtnt(fuse):
    return struct.pack('<f', float(fuse))

def unpacktnt(pay):
    return struct.unpack('<f', pay)[0]


def packitem(iid, cnt, vel):
    return struct.pack(
        '<II3f', iid, cnt,
        float(vel[0]), float(vel[1]), float(vel[2])
    )

def unpackitem(pay):
    iid, cnt, vx, vy, vz = struct.unpack('<II3f', pay)
    return iid, cnt, np.array([vx, vy, vz], dtype='f4')



def mkblockbulk(chgs):
    d = struct.pack('<BI', MT.BLOCK_BULK, len(chgs))
    for x, y, z, bt in chgs: d += struct.pack('<iiiH', x, y, z, bt)
    return d



def mkchunk(cx, cz, vox):
    # voxels squash ~27x, mostly runs of the same id
    b = zlib.compress(vox.astype('<u2', copy=False).tobytes(), 6)
    return struct.pack('<BiiI', MT.CHUNK_DATA, cx, cz, len(b)) + b



def mkchunkreq(cx, cz):
    return struct.pack('<Bii', MT.CHUNK_REQ, cx, cz)



def mksvchunks(keys):
    d = struct.pack('<BI', MT.SV_CHUNKS, len(keys))
    for cx, cz in keys: d += struct.pack('<ii', cx, cz)
    return d



def mkmods(mods):
    total = sum(len(cm) for cm in mods.values())
    d = struct.pack('<BII', MT.MODS, total, len(mods))
    
    for (cx, cz), cm in mods.items():
        d += struct.pack('<iiI', cx, cz, len(cm))
        for (lx, y, lz), bt in cm.items():
            d += struct.pack('<BBBH', lx, y, lz, bt)
            
            
    return d



def mklist(players):
    d = struct.pack('<BI', MT.PLAYER_LIST, len(players))
    for pid, pd in players.items():
        pos = pd['pos']
        nm  = pd.get('nm', f'Player{pid}')
        b   = nm.encode('utf-8')
        d += struct.pack(
            '<I3fI', pid,
            float(pos[0]), float(pos[1]),
            float(pos[2]), len(b)
        ) + b
        
    return d





def mkservmsg(msg):
    b = msg.encode('utf-8')
    return struct.pack('<BI', MT.SV_MESSAGE, len(b)) + b




def mkchat(msg):
    b = msg.encode('utf-8')
    return struct.pack('<BI', MT.CHAT, len(b)) + b



"""
def mkitemspawn(eid, iid, cnt, pos, vel):
    return struct.pack(
        '<BIII3f3f', MT.ITEM_SPAWN, eid, iid, cnt,
        float(pos[0]), float(pos[1]), float(pos[2]),
        float(vel[0]), float(vel[1]), float(vel[2])
    )




def mkitemdespawn(eid):
    return struct.pack('<BI', MT.ITEM_DESPAWN, eid)
"""




def mkitemdrop(iid, cnt, pos, vel):
    return struct.pack(
        '<BII3f3f', MT.ITEM_DROP, iid, cnt,
        float(pos[0]), float(pos[1]), float(pos[2]),
        float(vel[0]), float(vel[1]), float(vel[2])
    )
    
    
    
    

def mkitempick(eid):
    return struct.pack('<BI', MT.ITEM_PICKUP, eid)

def mkitemcollect(iid, cnt):
    return struct.pack('<BII', MT.ITEM_COLLECT, iid, cnt)

def mksvrq():
    return struct.pack('<B', MT.SERVER_REQUEST)






def mksvreply(nm, motd, cp, mp):
    nb = nm.encode('utf-8')
    mb = motd.encode('utf-8')
    return struct.pack(
        '<BIIII', MT.SERVER_RESPONSE,
        len(nb), len(mb), cp, mp
    ) + nb + mb



def mkdisconnect(reason=""):
    b = reason.encode('utf-8')
    return struct.pack('<BI', MT.DISCONNECT, len(b)) + b










class ReadMessage:
    def __init__(self, sock):
        self.sock   = sock
        self.buffer = b''


    def recv(self, needed=4096):
        data = self.sock.recv(needed)
        if data: self.buffer += data
        return data


    def _pull(self, n):
        # recv until buffer has n bytes
        
        while len(self.buffer) < n:
            r, _, _ = select.select([self.sock], [], [], 1.0)
            if not r: continue
            try:
                d = self.sock.recv(max(4096, n - len(self.buffer)))
                if not d: return False
                self.buffer += d

            except (socket.error, OSError):
                return False

        return True







    def readmsg(self):
        if not self.buffer:
            r, _, _ = select.select([self.sock], [], [], 0.1)
            if not r: return None
            try:
                d = self.sock.recv(4096)
                if not d: return None
                self.buffer += d

            except (socket.error, OSError):
                return None

        if not self.buffer: return None
        mt = self.buffer[0]
        
        
        
        

        # fixed-size messages
        _fixed = {                # B + *
            MT.UPDATE_POS:    24, # 3f(12) + 2f(8) + H(2) + B(1)
            MT.BLOCK_CHANGE:  15, # iii(12) + H(2)
            MT.BLOCK_UPDATE:  15,
            MT.BLOCK_DMG:     14, # iii(12) + b(1)
            MT.BLOCK_DAMAGE:  18, # I(4) + iii(12) + b(1)
            MT.PLAYER_DMG:     2, # B(1)
            MT.PLAYER_HURT:    6, # I(4) + B(1)
            MT.PLAYER_HEALTH:  2, # B(1)
            MT.PLAYER_HUNGER:  2,
            MT._SEED:          5, # I(4)
            MT.PLAYER_LEFT:    5,
            # MT.ITEM_SPAWN:    37, # III(12) + 3f(12) + 3f(-12)
            # MT.ITEM_DESPAWN:   5,
            MT.ITEM_DROP:     33, # II(8) + 3f(12) + 3f(12)
            MT.ITEM_PICKUP:    5,
            MT.ITEM_COLLECT:   9, # II(8)
            MT.PLAYER_POS:    28, # I(4) + 3f(12) + 2f(8) + H(2) + B(1)
            MT.SERVER_REQUEST: 1,
            MT.CHUNK_REQ:      9, # ii(8)
            # MT.ENTITY_SPAWN:  23, # I(4) + H(2) + 3f(12) + f(4)
            # MT.ENTITY_POS:    21, # I(4) + 3f(12) + f(4)
            # MT.ENTITY_GONE:    5, # I(4)
            MT.ENTITY_GONE:    6, # I(4) + B(1)
            MT.ENTITY_HURT:    6,
            MT.ENTITY_ANIM:    6,
            MT.ENTITY_ATTACK:  5, # I(4)
            MT.PLAYER_ATTACK:  5,
            MT.DBG_MODE:       2, # B(1)
        }
        
        
        

        if mt in _fixed:
            tl = _fixed[mt]
            if not self._pull(tl): return None
            d = self.buffer[:tl]
            self.buffer = self.buffer[tl:]
            return (mt, d)



        # B(1) + 16s + I(4) + nm
        if mt == MT.JOIN:
            if not self._pull(21): return None
            nl = struct.unpack('<I', self.buffer[17:21])[0]
            if not self._pull(21 + nl): return None
            d = self.buffer[1:21 + nl]
            self.buffer = self.buffer[21 + nl:]
            return (mt, d)



        #  B(1) + I(4) + 3f(12) + I(4) + nm
        if mt == MT.PLAYER_JOIN:
            if not self._pull(21): return None
            nl = struct.unpack('<I', self.buffer[17:21])[0]
            if not self._pull(21 + nl): return None
            d = self.buffer[1:21 + nl]
            self.buffer = self.buffer[21 + nl:]
            return (mt, d)



        # B(1) + I(4) + text
        if mt in (MT.SV_MESSAGE, MT.CHAT, MT.DISCONNECT):
            if not self._pull(5): return None
            ml = struct.unpack('<I', self.buffer[1:5])[0]
            if not self._pull(5 + ml): return None
            d = self.buffer[1:5 + ml]
            self.buffer = self.buffer[5 + ml:]
            return (mt, d)



        #  B + I(cnt) + [I + 3f + I + nm] * cnt
        if mt == MT.PLAYER_LIST:
            if not self._pull(5): return None
            cnt = struct.unpack('<I', self.buffer[1:5])[0]
            off = 5
            for _ in range(cnt):
                if not self._pull(off + 20): return None
                nl = struct.unpack('<I', self.buffer[off+16:off+20])[0]
                if not self._pull(off + 20 + nl): return None
                off += 20 + nl
            d = self.buffer[:off]
            self.buffer = self.buffer[off:]
            return (mt, d)



        # B + I(n) + png
        if mt == MT.SKIN_UPLOAD:
            if not self._pull(5): return None
            n = struct.unpack('<I', self.buffer[1:5])[0]
            if n > SKIN_MAX:
                self.buffer = b''
                return None
            if not self._pull(5 + n): return None
            d = self.buffer[:5 + n]
            self.buffer = self.buffer[5 + n:]
            return (mt, d)



        # B + I(pid) + I(n) + png
        if mt == MT.PLAYER_SKIN:
            if not self._pull(9): return None
            n = struct.unpack('<I', self.buffer[5:9])[0]
            if n > SKIN_MAX:
                self.buffer = b''
                return None
            if not self._pull(9 + n): return None
            d = self.buffer[:9 + n]
            self.buffer = self.buffer[9 + n:]
            return (mt, d)



        # B + I(cnt) + (iiiH)*cnt
        if mt == MT.BLOCK_BULK:
            if not self._pull(5): return None
            cnt = struct.unpack('<I', self.buffer[1:5])[0]
            tl  = 5 + cnt * 14
            if not self._pull(tl): return None
            d = self.buffer[:tl]
            self.buffer = self.buffer[tl:]
            return (mt, d)



        # B + I + H + 3f + f + H + B + H(n) + payload
        if mt == MT.ENTITY_SPAWN:
            if not self._pull(28): return None
            n = struct.unpack('<H', self.buffer[26:28])[0]
            if not self._pull(28 + n): return None
            d = self.buffer[:28 + n]
            self.buffer = self.buffer[28 + n:]
            return (mt, d)



        # B + I + B + 3f + B(n) + txt
        if mt == MT.ENTITY_DBG:
            if not self._pull(6): return None
            need = 6 + self.buffer[5] * 12 + 1

            if not self._pull(need): return None
            tl = self.buffer[need - 1]

            if not self._pull(need + tl): return None
            d = self.buffer[:need + tl]

            self.buffer = self.buffer[need + tl:]
            return (mt, d)



        # B + H(cnt) + (I + 3f + f + f + B)*cnt
        if mt == MT.ENTITY_STATE:
            if not self._pull(3): return None
            cnt = struct.unpack('<H', self.buffer[1:3])[0]
            tl  = 3 + cnt * 26
            if not self._pull(tl): return None
            d = self.buffer[:tl]
            self.buffer = self.buffer[tl:]
            return (mt, d)



        # B + ii + I(n) + zlib payload
        if mt == MT.CHUNK_DATA:
            if not self._pull(13): return None
            n = struct.unpack('<I', self.buffer[9:13])[0]
            if not self._pull(13 + n): return None
            d = self.buffer[:13 + n]
            self.buffer = self.buffer[13 + n:]
            return (mt, d)



        # B + I(cnt) + ii*cnt
        if mt == MT.SV_CHUNKS:
            if not self._pull(5): return None
            cnt = struct.unpack('<I', self.buffer[1:5])[0]
            tl  = 5 + cnt * 8
            if not self._pull(tl): return None
            d = self.buffer[:tl]
            self.buffer = self.buffer[tl:]
            return (mt, d)



        #  B + I(total) + I(chunks) + [ii + I(cnt) + (BBB+H)*cnt]
        if mt == MT.MODS:
            if not self._pull(9): return None
            _, nc = struct.unpack('<II', self.buffer[1:9])
            off = 9
            for _ in range(nc):
                if not self._pull(off + 12): return None
                _, _, cnt = struct.unpack('<iiI', self.buffer[off:off+12])
                off += 12
                bs = cnt * 5
                if not self._pull(off + bs): return None
                off += bs
            d = self.buffer[:off]
            self.buffer = self.buffer[off:]
            return (mt, d)



        #  B + IIII + nm + motd
        if mt == MT.SERVER_RESPONSE:
            if not self._pull(17): return None
            nl, ml, _, _ = struct.unpack('<IIII', self.buffer[1:17])
            if not self._pull(17 + nl + ml): return None
            d = self.buffer[:17 + nl + ml]
            self.buffer = self.buffer[17 + nl + ml:]
            return (mt, d)


        self.buffer = self.buffer[1:]
        return None






    def parse_join(self, data):
        token = data[:16]
        nl    = struct.unpack('<I', data[16:20])[0]
        nm    = data[20:20+nl].decode('utf-8')
        return token, nm




    def parse_posupdate(self, data):
        x, y, z, yaw, pitch, _held, afl = struct.unpack('<3f2fHB', data[1:])
        return np.array([x, y, z], dtype='f4'), yaw, pitch, _held, afl



    def parse_blockchange(self, data):
        x, y, z, bt = struct.unpack('<iiiH', data[1:])
        return x, y, z, bt


    def parse_blockdmg(self, data):
        x, y, z, st = struct.unpack('<iiib', data[1:])
        return x, y, z, st


    def parse_playerdmg(self, data):
        return struct.unpack('<B', data[1:])[0]


    def parse_playerhurt(self, data):
        pid, dmg = struct.unpack('<IB', data[1:])
        return pid, dmg


    def parse_health(self, data):
        return struct.unpack('<B', data[1:])[0]


    def parse_hunger(self, data):
        return struct.unpack('<B', data[1:])[0]


    def parse_blockdmgupd(self, data):
        pid            = struct.unpack('<I', data[1:5])[0]
        x, y, z, st    = struct.unpack('<iiib', data[5:])
        return pid, x, y, z, st


    def parse_seed(self, data):
        return struct.unpack('<I', data[1:])[0]








    def parse_playerjoin(self, data):
        if len(data) < 20:
            raise ValueError(f"PLAYER_JOIN too short: {len(data)}")

        pid     = struct.unpack('<I', data[0:4])[0]
        x, y, z = struct.unpack('<3f', data[4:16])
        nl      = struct.unpack('<I', data[16:20])[0]
        nm      = data[20:20+nl].decode('utf-8', errors='replace')
        return pid, nm, np.array([x, y, z], dtype='f4')


    def parse_skin(self, data):
        n = struct.unpack('<I', data[1:5])[0]
        return data[5:5+n]


    def parse_playerskin(self, data):
        pid, n = struct.unpack('<II', data[1:9])
        return pid, data[9:9+n]


    def parse_playerleft(self, data):
        return struct.unpack('<I', data[1:])[0]




    def parse_playerpos(self, data):
        pid             = struct.unpack('<I', data[1:5])[0]
        x, y, z, yaw, pitch, _held, afl = struct.unpack('<3f2fHB', data[5:])
        return pid, np.array([x, y, z], dtype='f4'), yaw, pitch, _held, afl




    def parse_blockupdate(self, data):
        x, y, z, bt = struct.unpack('<iiiH', data[1:])
        return x, y, z, bt


    def parse_entspawn(self, data):
        eid, kind, x, y, z, yaw, hp, flags, n = struct.unpack('<IH3ffHBH', data[1:28])
        return (
            eid, kind, np.array([x, y, z], dtype='f4'),
            yaw, hp, flags, data[28:28+n]
        )


    def parse_entstate(self, data, out=[]):
        cnt = struct.unpack('<H', data[1:3])[0]
        out = []
        off = 3


        for _ in range(cnt):
            eid, x, y, z, yaw, vy, hoff, anim = struct.unpack(
                '<I3fffbB', data[off:off+26]
            )

            out.append((
                eid, np.array([x, y, z], dtype='f4'), yaw, vy,
                hoff * 180.0 / 127.0, anim,
            ))
            off += 26
            
        return out


    def parse_entgone(self, data):
        return struct.unpack('<IB', data[1:])


    def parse_enthurt(self, data):
        return struct.unpack('<IB', data[1:])


    def parse_entanim(self, data):
        return struct.unpack('<IB', data[1:])


    def parse_entattack(self, data):
        return struct.unpack('<I', data[1:])[0]


    def parse_plattack(self, data):
        return struct.unpack('<I', data[1:])[0]


    def parse_entdbg(self, data):
        eid = struct.unpack('<I', data[1:5])[0]
        n   = data[5]
        off = 6
        pts = []

        for _ in range(n):
            pts.append(struct.unpack('<3f', data[off:off+12]))
            off += 12

        tl = data[off]; off += 1
        return eid, pts, data[off:off+tl].decode('utf-8', errors='replace')


    def parse_dbgmode(self, data):
        return bool(data[1])


    def parse_blockbulk(self, data):
        cnt = struct.unpack('<I', data[1:5])[0]
        out = []
        off = 5

        for _ in range(cnt):
            out.append(struct.unpack('<iiiH', data[off:off+14]))
            off += 14
        return out


    def parse_chunkreq(self, data):
        return struct.unpack('<ii', data[1:])


    def parse_chunk(self, data):
        cx, cz, n = struct.unpack('<iiI', data[1:13])
        v = np.frombuffer(zlib.decompress(data[13:13+n]), dtype='<u2')
        return cx, cz, v.reshape(CHUNK_SZ, CHUNK_H, CHUNK_SZ).astype(np.uint16)


    def parse_svchunks(self, data):
        cnt = struct.unpack('<I', data[1:5])[0]
        out = []
        off = 5
        for _ in range(cnt):
            out.append(struct.unpack('<ii', data[off:off+8]))
            off += 8
        return out





    def parse_mods(self, data):
        if len(data) < 9: raise ValueError("MODS too short")
        _, nc = struct.unpack('<II', data[1:9])
        mods  = {}
        off   = 9

        for _ in range(nc):
            if off + 12 > len(data): raise ValueError("chunk header missing")
            cx, cz, cnt = struct.unpack('<iiI', data[off:off+12])
            off += 12
            cm = {}

            for _ in range(cnt):
                if off + 5 > len(data): raise ValueError("block data missing")
                lx, y, lz = struct.unpack('<BBB', data[off:off+3])
                bt = struct.unpack('<H', data[off+3:off+5])[0]
                cm[(lx, y, lz)] = bt
                off += 5

            mods[(cx, cz)] = cm

        return mods




    def parse_list(self, data):
        cnt     = struct.unpack('<I', data[1:5])[0]
        players = {}
        off     = 5

        for _ in range(cnt):
            pid     = struct.unpack('<I', data[off:off+4])[0]
            x, y, z = struct.unpack('<3f', data[off+4:off+16])
            nl      = struct.unpack('<I', data[off+16:off+20])[0]
            nm      = data[off+20:off+20+nl].decode('utf-8')
            players[pid] = {'pos': np.array([x, y, z], dtype='f4'), 'nm': nm}
            off += 20 + nl

        return players




    def parse_svmsg(self, data):
        ml = struct.unpack('<I', data[:4])[0]
        return data[4:4+ml].decode('utf-8')



    def parse_chatmsg(self, data):
        ml = struct.unpack('<I', data[:4])[0]
        return data[4:4+ml].decode('utf-8')



    """
    def parse_itemspawn(self, data):
        eid, iid, cnt, x, y, z, vx, vy, vz = struct.unpack('<III3f3f', data[1:])
        return eid, iid, cnt, np.array([x, y, z], dtype='f4'), np.array([vx, vy, vz], dtype='f4')



    def parse_itemdespawn(self, data):
        return struct.unpack('<I', data[1:])[0]
    """




    def parse_itemdrop(self, data):
        iid, cnt, x, y, z, vx, vy, vz = struct.unpack('<II3f3f', data[1:])
        return iid, cnt, np.array([x, y, z], dtype='f4'), np.array([vx, vy, vz], dtype='f4')



    def parse_itempickup(self, data):
        return struct.unpack('<I', data[1:])[0]




    def parse_itemcollect(self, data):
        iid, cnt = struct.unpack('<II', data[1:])
        return iid, cnt




    def parse_svreplyinfo(self, data):
        nl, ml, cp, mp = struct.unpack('<IIII', data[1:17])
        nm   = data[17:17+nl].decode('utf-8')
        motd = data[17+nl:17+nl+ml].decode('utf-8')
        return {'nm': nm, 'motd': motd, 'current_players': cp, 'maxp': mp}




    def parse_disconnect(self, data):
        rl = struct.unpack('<I', data[:4])[0]
        return data[4:4+rl].decode('utf-8')
