import os, json, time, socket, struct, datetime

from lconst import (
    LAUNCH_CONF,
    RESOURCE_DIR,
    SERVERS_FILE,
    NAME_FILE,
    SAVES_DIR,
    BASE_DIR
)


def loadcfg():
    if os.path.exists(LAUNCH_CONF):
        with open(LAUNCH_CONF) as f:
            return json.load(f)
    return {}


def savecfg(cfg):
    with open(LAUNCH_CONF, "w") as f:
        json.dump(cfg, f, indent=2)



def get_reasourceactive():
    return loadcfg().get("resource_pack", "default")


def set_reasourceactive(nm):
    cfg = loadcfg()
    cfg["resource_pack"] = nm
    savecfg(cfg)



def getpname(default="Player"):
    if os.path.exists(NAME_FILE):
        nm = open(NAME_FILE, encoding='utf-8').read().strip()
        if nm: return nm
    return default


def setpname(nm):
    with open(NAME_FILE, "w", encoding='utf-8') as f:
        f.write(nm.strip())


def get_available():
    out = []

    if not os.path.isdir(RESOURCE_DIR):
        return out

    for nm in sorted(os.listdir(RESOURCE_DIR)):
        pj = os.path.join(RESOURCE_DIR, nm, "pack.json")

        if not os.path.isfile(pj):
            continue

        with open(pj) as f:
            meta = json.load(f)

        out.append({
            "folder":      nm,
            "name":        meta.get("name", nm),
            "description": meta.get("description", ""),
            "version":     meta.get("version", ""),
            "author":      meta.get("author", "Unknown"),
        })

    return out



def save_dir():
    os.makedirs(SAVES_DIR, exist_ok=True)
    return SAVES_DIR



def load_servers():
    if os.path.exists(SERVERS_FILE):
        with open(SERVERS_FILE) as f:
            return json.load(f)
    return []


def save_servers(servers):
    with open(SERVERS_FILE, "w") as f:
        json.dump(servers, f, indent=2)


"""
def load_playerdata():
    import pickle
    p = os.path.join(BASE_DIR, "player_data.bin")
    if not os.path.exists(p): return {}
    with open(p, "rb") as f:
        return pickle.load(f)

def save_playerdata(data):
    import pickle
    p = os.path.join(BASE_DIR, "player_data.bin")
    with open(p, "wb") as f:
        pickle.dump(data, f)
"""


def wolrdlist():
    w  = []
    sd = save_dir()

    if not os.path.isdir(sd): return w

    for nm in sorted(os.listdir(sd)):
        wdir = os.path.join(sd, nm)

        if not os.path.isdir(wdir):
            continue

        tot  = 0
        lmod = 0

        for root, _d, files in os.walk(wdir):
            for fn in files:
                fp = os.path.join(root, fn)
                tot += os.path.getsize(fp)
                lmod   = max(lmod, os.path.getmtime(fp))

        lplayed = ""
        if lmod > 0:
            lplayed = datetime.datetime.fromtimestamp(lmod).strftime("%Y-%m-%d %H:%M")

        w.append(dict(nm=nm, path=wdir, size_kb=tot//1024, last_played=lplayed))

    return w



def svping(address, timeout=2.0):
    pts  = address.split(":")
    host = pts[0]
    port = int(pts[1]) if len(pts) > 1 else 25250

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    t0 = time.time()
    s.connect((host, port))
    s.sendall(struct.pack('<B', 30))

    buf = b''
    while len(buf) < 17:
        ch = s.recv(4096)
        if not ch: break
        buf += ch

    s.close()
    ms = (time.time() - t0) * 1000

    if len(buf) < 17 or buf[0] != 31:
        return False, -1, None

    nl, ml, cur, mx = struct.unpack_from('<IIII', buf, 1)
    needed = 17 + nl + ml

    if len(buf) < needed:
        return False, -1, None

    nm   = buf[17:17+nl].decode('utf-8', errors='replace')
    motd = buf[17+nl:needed].decode('utf-8', errors='replace')

    return True, ms, {'nm': nm, 'motd': motd, 'current_players': cur, 'maxp': mx}



def ms_signal(ms):
    if ms < 0:   return 5
    if ms < 50:  return 0
    if ms < 150: return 1
    if ms < 300: return 2
    if ms < 600: return 3
    return 4


