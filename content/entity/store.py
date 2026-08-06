import os
import json
import math

from config import CHUNK_SZ


def entck(e):
    return (
        int(math.floor(e.pos[0])) // CHUNK_SZ,
        int(math.floor(e.pos[2])) // CHUNK_SZ,
    )


def entfile(wdir, cx, cz):
    return os.path.join(wdir, f"{cx}_{cz}.ent")


# empty -> drop file
def saveents(wdir, cx, cz, ents):
    fp = entfile(wdir, cx, cz)

    if not ents:
        if os.path.exists(fp): os.remove(fp)
        return

    with open(fp, 'w') as f:
        json.dump([i.save() for i in ents], f)


def loadents(wdir, cx, cz):
    fp = entfile(wdir, cx, cz)
    if not os.path.exists(fp): return []

    with open(fp) as f:
        return json.load(f)
