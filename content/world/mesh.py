import numpy as np
from numba import njit
from config import CHUNK_SZ, CHUNK_H


"""
@njit(cache=True, fastmath=True, nogil=True)
def _scan_extruded_jit(voxels):
    # TODO remove this method
    # custom geometry pipeline overrides ts
    results = []
    
    for x in range(CHUNK_SZ):
        for z in range(CHUNK_SZ):
            for y in range(CHUNK_H):
                
                bt = voxels[x, y, z] & 0x3FF
                if bt == 159 or bt == 170:
                    results.append((x, y, z, bt))
                    
    return results
"""







BLOCK_OPAC = np.full(1024, 255, dtype=np.uint8)

for i in (
    0, 10, 23, 47, 70, 96, 
    152, 156, 157, 158, 
    162, 167, 168, 169, 170, 171, 
    270, 277, 278, 279, 
    280, 285, 286, 291, 
    333, 334
):
    BLOCK_OPAC[i] = 0



for a, b in (
    (119, 134),  # staind glass
    (159, 166),  # redstone, doors
    (172, 205),  # flowers, rails, torches
    (206, 219),  # stairs
    (220, 233),  # slabs
    (234, 248),  # fences, gates, walls
    (249, 267),  # doors, buttons, plates
    (273, 275),  # chest
    (283, 284),  # bars, pane
    (287, 290),  # crops
    (292, 295),  # anvil, endportal
    (301, 316),  # carpets
    (317, 332),  # stained panes
):
    BLOCK_OPAC[a:b + 1] = 0









BLOCK_OPAC[8]   = 1    # leaves oak
BLOCK_OPAC[9]   = 1    # leaves birch
BLOCK_OPAC[76]  = 1    # spruce
BLOCK_OPAC[77]  = 1    # jngle
BLOCK_OPAC[78]  = 1    # acacia
BLOCK_OPAC[79]  = 1    # dark oak
BLOCK_OPAC[276] = 1    # cobweb
BLOCK_OPAC[5]   = 3    # water
BLOCK_OPAC[154] = 3    # waterflow
BLOCK_OPAC[48]  = 3    # ice




# material->isSolidBlocking() && isCubeShaped() => getShadeBrightness

BLOCK_AOSOLID = (BLOCK_OPAC == 255).astype(np.uint8)

for i in (
    8, 9, 23, 48, 
    70, 76, 77, 78, 79, 96, 
    156, 157, 158, 162, 167, 168,
    270, 279, 280, 283, 284
):
    BLOCK_AOSOLID[i] = 1

for a, b in (
    (119, 134),  # stained glass
    (163, 166),  # doors
    (206, 219),  # stairs
    (220, 233),  # slabs
    (234, 248),  # fences, gates, walls
    (249, 258),  # doors
    (265, 266),  # trapdors
    (273, 275),  # chests
    (291, 295),  # enchanttable, anvil, endportal
    (317, 332),  # stained pane
):
    BLOCK_AOSOLID[a:b + 1] = 1







@njit(cache=True, fastmath=True, nogil=True)
def _is_lightaware(block):
    return BLOCK_OPAC[block & 0x3FF] == 0


# light emiiters
EMITTERS = {
    45 : 15,  # glowstone
    56 : 15,  # sea lantern
    68 : 15,  # jack o lantern
    93 : 15,  # redstone lamp on
    #96 :  1,  # dragon egg
    97 : 15,  # beacon
    151: 15,  # lava
    152: 15,  # fire
    153: 13,  # furnace on
    155: 15,  # lava flow
    171:  1,  # brewing
    203: 14,  # torch
    205:  7,  # redstone torch on
    295:  1,  # end portal
}

BLOCK_EMIT = np.zeros(1024, dtype=np.uint8)
for i, j in EMITTERS.items(): BLOCK_EMIT[i] = j




# face norm -> downwards axis 0=x, 1=y, 2=z
FACE_AX = np.array([1, 1, 0, 0, 2, 2], dtype=np.int32)

# TileRenderer c11/c10/c3/c2
FACE_SHADE = np.array([1.0, 0.5, 0.6, 0.6, 0.8, 0.8], dtype=np.float32)


@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _nshade(nx, ny, nz):
    if ny >  0.5: return np.float32(1.0)
    if ny < -0.5: return np.float32(0.5)
    if abs(nz) > 0.5: return np.float32(0.8)
    if abs(nx) > 0.5: return np.float32(0.6)
    return np.float32(0.8)




# read cell 1block outside the chunk
@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _cellat(
        voxels, v_nx, v_px, v_nz, v_pz,
        sky, s_nx, s_px, s_nz, s_pz,
        blk, b_nx, b_px, b_nz, b_pz,
        x, y, z
    ):

    if y < 0:        return 0, 0, True
    if y >= CHUNK_H: return 0, 15, False


    if x < 0:
        if 0 <= z < CHUNK_SZ:
            i = CHUNK_SZ - 1
            return b_nx[i, y, z], s_nx[i, y, z], BLOCK_AOSOLID[v_nx[i, y, z] & 0x3FF] != 0
        x = 0

    elif x >= CHUNK_SZ:
        if 0 <= z < CHUNK_SZ:
            return b_px[0, y, z], s_px[0, y, z], BLOCK_AOSOLID[v_px[0, y, z] & 0x3FF] != 0
        x = CHUNK_SZ - 1

    if z < 0:
        i = CHUNK_SZ - 1
        return b_nz[x, y, i], s_nz[x, y, i], BLOCK_AOSOLID[v_nz[x, y, i] & 0x3FF] != 0

    if z >= CHUNK_SZ:
        return b_pz[x, y, 0], s_pz[x, y, 0], BLOCK_AOSOLID[v_pz[x, y, 0] & 0x3FF] != 0

    return blk[x, y, z], sky[x, y, z], BLOCK_AOSOLID[voxels[x, y, z] & 0x3FF] != 0








# - smooth lighting -
# each of the 4 corners averages all cells touching it
# x,y,z ->cell ahead
@njit(cache=True, fastmath=True, nogil=True)
def _corners(
        l4, p9, ax, x, y, z,
        voxels, v_nx, v_px, v_nz, v_pz,
        sky, s_nx, s_px, s_nz, s_pz,
        blk, b_nx, b_px, b_nz, b_pz
    ):

    # grab 3x3 patch on face plane up front
    if ax == 0:   inside = 0 <= x < CHUNK_SZ     and 1 <= y < CHUNK_H - 1 and 1 <= z < CHUNK_SZ - 1
    elif ax == 1: inside = 1 <= x < CHUNK_SZ - 1 and 0 <= y < CHUNK_H     and 1 <= z < CHUNK_SZ - 1
    else:         inside = 1 <= x < CHUNK_SZ - 1 and 1 <= y < CHUNK_H - 1 and 0 <= z < CHUNK_SZ
    

    for u in range(3):
        for w in range(3):
            if ax == 0:   cx, cy, cz = x, y + u - 1, z + w - 1
            elif ax == 1: cx, cy, cz = x + u - 1, y, z + w - 1
            else:         cx, cy, cz = x + u - 1, y + w - 1, z



            if inside:
                p9[u, w, 0] = blk[cx, cy, cz]
                p9[u, w, 1] = sky[cx, cy, cz]
                p9[u, w, 2] = BLOCK_AOSOLID[voxels[cx, cy, cz] & 0x3FF]

            else:
                cbb, css, coo = _cellat(
                    voxels, v_nx, v_px, v_nz, v_pz,
                    sky, s_nx, s_px, s_nz, s_pz,
                    blk, b_nx, b_px, b_nz, b_pz, cx, cy, cz
                )


                p9[u, w, 0] = cbb
                p9[u, w, 1] = css
                p9[u, w, 2] = 1 if coo else 0
                

    cb = p9[1, 1, 0]
    cs = p9[1, 1, 1]




    for a in range(2):
        for b in range(2):
            u = a * 2
            w = b * 2

            b1 = p9[u, 1, 0]; s1 = p9[u, 1, 1]; o1 = p9[u, 1, 2]
            b2 = p9[1, w, 0]; s2 = p9[1, w, 1]; o2 = p9[1, w, 2]

            # both sides shut -> nonvis corner -> reuse side
            if o1 != 0 and o2 != 0:
                b3, s3, o3 = b1, s1, o1
            else:
                b3 = p9[u, w, 0]; s3 = p9[u, w, 1]; o3 = p9[u, w, 2]



            # only swap blend() when a sample = #ffffff
            sh = 4.0
            if o1 != 0: sh -= 0.8
            if o2 != 0: sh -= 0.8
            if o3 != 0: sh -= 0.8

            if b1 == 0 and s1 == 0: b1, s1 = cb, cs
            if b2 == 0 and s2 == 0: b2, s2 = cb, cs
            if b3 == 0 and s3 == 0: b3, s3 = cb, cs

            i = a * 2 + b
            l4[i, 0] = (cb + b1 + b2 + b3) * 0.25
            l4[i, 1] = (cs + s1 + s2 + s3) * 0.25
            l4[i, 2] = sh * 0.25







# no smoothing 
# cross, water, custom geom
@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _flat(l4, b, s):
    for i in range(4):
        l4[i, 0] = b
        l4[i, 1] = s
        l4[i, 2] = 1.0






@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _cidx(ax, vx, vy, vz):
    if ax == 0: return (2 if vy >= 0.5 else 0) + (1 if vz >= 0.5 else 0)
    if ax == 1: return (2 if vx >= 0.5 else 0) + (1 if vz >= 0.5 else 0)
    return (2 if vx >= 0.5 else 0) + (1 if vy >= 0.5 else 0)


# getExpected
@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _cost(b):
    o = BLOCK_OPAC[b & 0x3FF]
    return 1 if o < 1 else o


@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _pack(x, y, z):
    return (x * CHUNK_H + y) * CHUNK_SZ + z


# pull light <- the 4 loaded side neighbours
@njit(cache=True, fastmath=True, nogil=True)
def _seedneighb(voxels, light, n_nx, n_px, n_nz, n_pz, q, tail):
    for z in range(CHUNK_SZ):
        for y in range(CHUNK_H):
            v = int(n_nx[CHUNK_SZ - 1, y, z]) - _cost(voxels[0, y, z])

            if v > 0 and light[0, y, z] < v:
                light[0, y, z] = v
                q[tail] = _pack(0, y, z)
                tail += 1

            i = CHUNK_SZ - 1
            v = int(n_px[0, y, z]) - _cost(voxels[i, y, z])
            if v > 0 and light[i, y, z] < v:
                light[i, y, z] = v
                q[tail] = _pack(i, y, z)
                tail += 1



    for x in range(CHUNK_SZ):
        for y in range(CHUNK_H):
            v = int(n_nz[x, y, CHUNK_SZ - 1]) - _cost(voxels[x, y, 0])

            if v > 0 and light[x, y, 0] < v:
                light[x, y, 0] = v
                q[tail] = _pack(x, y, 0)
                tail += 1

            i = CHUNK_SZ - 1
            v = int(n_pz[x, y, 0]) - _cost(voxels[x, y, i])
            if v > 0 and light[x, y, i] < v:
                light[x, y, i] = v
                q[tail] = _pack(x, y, i)
                tail += 1

    return tail





# flood
@njit(cache=True, fastmath=True, nogil=True)
def _flood(voxels, light, q, tail):
    head = 0
    while head < tail:
        p = q[head]
        head += 1
        z = p % CHUNK_SZ
        p = p // CHUNK_SZ
        y = p % CHUNK_H
        x = p // CHUNK_H
        cur = int(light[x, y, z])
        if cur <= 1: continue

        for dx, dy, dz in (
            ( 1, 0, 0), (-1, 0, 0),
            ( 0, 1, 0), ( 0,-1, 0),
            ( 0, 0, 1), ( 0, 0,-1),
        ):

            nx, ny, nz = x + dx, y + dy, z + dz

            if not (0 <= nx < CHUNK_SZ and 0 <= ny < CHUNK_H and 0 <= nz < CHUNK_SZ): continue

            nxt = cur - _cost(voxels[nx, ny, nz])
            if nxt <= 0: continue

            if light[nx, ny, nz] < nxt:
                light[nx, ny, nz] = nxt
                q[tail] = _pack(nx, ny, nz)
                tail += 1





@njit(cache=True, fastmath=True, nogil=True)
def bakelight(
        voxels, sky, blk,
        s_nx, s_px, s_nz, s_pz,
        b_nx, b_px, b_nz, b_pz,
        emit
    ):


    sky[:, :, :] = 0
    blk[:, :, :] = 0
    # buffer = basecells + neighbor edge seed
    # 4 edges * CHUNK_SZ * CHUNK_H

    _max = 2 * CHUNK_SZ * CHUNK_H * CHUNK_SZ + 4 * CHUNK_SZ * CHUNK_H

    # bfs queue
    q = np.empty(_max, dtype=np.int32)
    tail = 0



    
    for x in range(CHUNK_SZ):
        for z in range(CHUNK_SZ):
            br = 15
            for y in range(CHUNK_H - 1, -1, -1):
                br -= int(BLOCK_OPAC[voxels[x, y, z] & 0x3FF])
                if br <= 0: break

                sky[x, y, z] = br
                q[tail] = _pack(x, y, z)
                tail += 1

    tail = _seedneighb(voxels, sky, s_nx, s_px, s_nz, s_pz, q, tail)
    _flood(voxels, sky, q, tail)



    # seed every emitter cell
    tail = 0
    for x in range(CHUNK_SZ):
        for y in range(CHUNK_H):
            for z in range(CHUNK_SZ):
                e = emit[voxels[x, y, z] & 0x3FF]
                if e > 0:
                    blk[x, y, z] = e
                    q[tail] = _pack(x, y, z)
                    tail += 1

    tail = _seedneighb(voxels, blk, b_nx, b_px, b_nz, b_pz, q, tail)
    _flood(voxels, blk, q, tail)


















@njit(cache=True, fastmath=True, nogil=True)
def is_localsolid(voxels, x, y, z):
    if 0 <= x < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= z < CHUNK_SZ:
        b = voxels[x, y, z] & 0x3FF
        if (
            b == 0  or  # air
            b == 5  or  # water
            b == 8  or  # leaves
            b == 9  or  # leaves
            b == 10 or  # grass
            b == 47 or  # snow
            b == 70 or  # cactus
            b == 23 or  # glass
            b == 96 or  # dragon egg
            b == 333 or # sugar cane
            b == 152 or # fire
            (119 <= b <= 134) or # glass, stained glass
            (156 <= b <= 177) or # barrier...saplings
            (178 <= b <= 205) or # flowers, plants, double plants, rails, torches
            (206 <= b <= 233) or # stairs, slabs
            (234 <= b <= 248) or # fences, fence gates, walls
            (249 <= b <= 264) or # doors, buttons, pressure plates
            (265 <= b <= 270) or # trapdoors, ladder, pistons
            (273 <= b <= 275) or # chests
            (276 <= b <= 280) or # cobweb, lever, tripwire hook, daylight
            (283 <= b <= 290) or # iron bars, glass pane, vine, lily pad, crops
            (291 <= b <= 295) or # enchanting table, anvils, end portal frame
            (301 <= b <= 316) or # carpets
            (317 <= b <= 332)    # colored glass panes
        ):
            return False
            
            
        return True
        
    return False






@njit(cache=True, fastmath=True, nogil=True)
def get_localblock(voxels, x, y, z):
    if 0 <= x < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= z < CHUNK_SZ:
        return voxels[x, y, z] & 0x3FF
    return 0




@njit(cache=True, fastmath=True, nogil=True)
def is_localwater(voxels, x, y, z):
    if 0 <= x < CHUNK_SZ and 0 <= y < CHUNK_H and 0 <= z < CHUNK_SZ:
        b = voxels[x, y, z] & 0x3FF
        return b == 5 or b == 154
    return False





@njit(cache=True, fastmath=True, nogil=True)
def get_waterh(bval):
    # lvl 0   = source block
    # lvl 1-7 = flowing lvels
    st = (bval >> 8) & 0x3FF
    lvl = st & 0x0F
    
    if lvl == 0: return 0.875  # source
    
    # flowing heights
    flvl = lvl if lvl < 8 else lvl - 8
    return (8.0 - flvl) / 9.0









# unit cube face vertices : [findex, vindex, xyz]
FACE_VERTS = np.array([
    [[0, 1, 0], [0, 1, 1], [1, 1, 1], [0, 1, 0], [1, 1, 1], [1, 1, 0]], # top +y
    [[0, 0, 1], [0, 0, 0], [1, 0, 0], [0, 0, 1], [1, 0, 0], [1, 0, 1]], # bot -y
    [[0, 0, 0], [0, 0, 1], [0, 1, 1], [0, 0, 0], [0, 1, 1], [0, 1, 0]], # west -x
    [[1, 0, 1], [1, 0, 0], [1, 1, 0], [1, 0, 1], [1, 1, 0], [1, 1, 1]], # east +x
    [[1, 0, 0], [0, 0, 0], [0, 1, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], # north -z
    [[0, 0, 1], [1, 0, 1], [1, 1, 1], [0, 0, 1], [1, 1, 1], [0, 1, 1]], # south +z
], dtype=np.float32)




# normals: [findex, xyz]
FACE_NORMALS = np.array([
    [ 0.0,  1.0,  0.0],  # top
    [ 0.0, -1.0,  0.0],  # bot
    [-1.0,  0.0,  0.0],  # west
    [ 1.0,  0.0,  0.0],  # east
    [ 0.0,  0.0, -1.0],  # north
    [ 0.0,  0.0,  1.0],  # south
], dtype=np.float32)



# uv offs for 6 verts p face quad
FACE_UV_OFFSETS = np.array([
    [0, 0], [0, 1], [1, 1], 
    [0, 0], [1, 1], [1, 0]
], dtype=np.float32)




# grass pattern
GRASS_VERTS = np.array([
    [[0, 0, 0], [1, 0, 1], [1, 1, 1], [0, 0, 0], [1, 1, 1], [0, 1, 0]], # p1 front
    [[1, 0, 1], [0, 0, 0], [0, 1, 0], [1, 0, 1], [0, 1, 0], [1, 1, 1]], # p1 back
    [[1, 0, 0], [0, 0, 1], [0, 1, 1], [1, 0, 0], [0, 1, 1], [1, 1, 0]], # p2 front
    [[0, 0, 1], [1, 0, 0], [1, 1, 0], [0, 0, 1], [1, 1, 0], [0, 1, 1]], # p2 back
], dtype=np.float32)









@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _emitface(
        vertices, vertidx, x, y, z, 
        offset_x, offset_z, face_idx, l4,
        u_start, v_start, uv_w, uv_h,
        face_verts, face_norms, face_uv_offs
    ):
    ax  = FACE_AX[face_idx]
    fsh = FACE_SHADE[face_idx]
    
    
    for i in range(6):
        vx = face_verts[face_idx, i, 0]
        vy = face_verts[face_idx, i, 1]
        vz = face_verts[face_idx, i, 2]
        
        vertices[vertidx + 0] = x + vx + offset_x
        vertices[vertidx + 1] = y + vy
        vertices[vertidx + 2] = z + vz + offset_z

        c = _cidx(ax, vx, vy, vz)
        vertices[vertidx + 3] = l4[c, 0]
        vertices[vertidx + 4] = l4[c, 1]
        vertices[vertidx + 5] = l4[c, 2] * fsh
        vertices[vertidx + 6] = u_start + face_uv_offs[i, 0] * uv_w
        vertices[vertidx + 7] = v_start + face_uv_offs[i, 1] * uv_h
        vertidx += 8
    
    return vertidx











@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _emitgrass(
        vertices, vertidx, x, y, z, 
        offset_x, offset_z, l4,
        u_start, v_start, uv_w, uv_h,
        grass_verts
    ):
        
        
    for plane in range(4):
        for i in range(6):
            vx = grass_verts[plane, i, 0]
            vy = grass_verts[plane, i, 1]
            vz = grass_verts[plane, i, 2]
            
            vertices[vertidx] = x + vx + offset_x
            vertices[vertidx + 1] = y + vy
            vertices[vertidx + 2] = z + vz + offset_z
            vertices[vertidx + 3] = l4[0, 0]
            vertices[vertidx + 4] = l4[0, 1]
            vertices[vertidx + 5] = l4[0, 2]


            if i == 0 or i == 3:
                vertices[vertidx + 6] = u_start
                vertices[vertidx + 7] = v_start
                
            elif i == 1:
                vertices[vertidx + 6] = u_start + uv_w
                vertices[vertidx + 7] = v_start
                
            elif i == 2 or i == 4:
                vertices[vertidx + 6] = u_start + uv_w
                vertices[vertidx + 7] = v_start + uv_h
                
            else:
                vertices[vertidx + 6] = u_start
                vertices[vertidx + 7] = v_start + uv_h
            
            vertidx += 8
    
    return vertidx





# face verts: [findex][vindex][x,y,z]
MESH_FACE_V = np.array([
    [[0,1,0], [0,1,1], [1,1,1], [0,1,0], [1,1,1], [1,1,0]],  # +y
    [[0,0,1], [0,0,0], [1,0,0], [0,0,1], [1,0,0], [1,0,1]],  # -y
    [[0,0,0], [0,0,1], [0,1,1], [0,0,0], [0,1,1], [0,1,0]],  # -x
    [[1,0,1], [1,0,0], [1,1,0], [1,0,1], [1,1,0], [1,1,1]],  # +x
    [[1,0,0], [0,0,0], [0,1,0], [1,0,0], [0,1,0], [1,1,0]],  # -z
    [[0,0,1], [1,0,1], [1,1,1], [0,0,1], [1,1,1], [0,1,1]],  # +z
], dtype=np.float32)




# norms: [findex][x,y,z]
MESH_FACE_N = np.array([
    [0, 1, 0], [0, -1,  0], [-1, 0, 0], 
    [1, 0, 0], [0,  0, -1], [ 0, 0, 1]
], dtype=np.float32)

# uv offs: [vindex][u,v]
# legacy BL, BR, TR, BL, TR, TL
MESH_FACE_UV = np.array([
    [0, 0], [1, 0], [1, 1], [0, 0], [1, 1], [0, 1]
], dtype=np.float32)

# grass 4 plnaes x 6 verts
MESH_GRASS_V = np.array([
    [[0,0,0], [1,0,1], [1,1,1], [0,0,0], [1,1,1], [0,1,0]],
    [[1,0,1], [0,0,0], [0,1,0], [1,0,1], [0,1,0], [1,1,1]],
    [[1,0,0], [0,0,1], [0,1,1], [1,0,0], [0,1,1], [1,1,0]],
    [[0,0,1], [1,0,0], [1,1,0], [0,0,1], [1,1,0], [0,1,1]],
], dtype=np.float32)












@njit(cache=True, fastmath=True, nogil=True, inline='always')
def is_nonsolidMesh(bt):
    if bt == 0: return True
    if bt == 5  or bt == 154: return True  # water
    if bt == 8  or bt == 9:   return True  # leaves
    if bt == 10 or bt == 70:  return True  # grass & catus
    if bt >= 156 and bt <= 171: return True  # custom geometry
    return False

BUILD_FACE_V = np.array([
    [[0,1,1], [1,1,1], [1,1,0], [0,1,1], [1,1,0], [0,1,0]], # top +y
    [[0,0,0], [1,0,0], [1,0,1], [0,0,0], [1,0,1], [0,0,1]], # bot -y
    [[0,0,0], [0,0,1], [0,1,1], [0,0,0], [0,1,1], [0,1,0]], # west -x
    [[1,0,1], [1,0,0], [1,1,0], [1,0,1], [1,1,0], [1,1,1]], # east +x
    [[1,0,0], [0,0,0], [0,1,0], [1,0,0], [0,1,0], [1,1,0]], # north -z
    [[0,0,1], [1,0,1], [1,1,1], [0,0,1], [1,1,1], [0,1,1]], # south +z
], dtype=np.float32)




# _cidx => cube verts
BUILD_CIX = np.zeros((6, 6), dtype=np.int32)
for f in range(6):
    for i in range(6):

        vx, vy, vz = BUILD_FACE_V[f, i]
        if   FACE_AX[f] == 0: p_, q_ = vy, vz
        elif FACE_AX[f] == 1: p_, q_ = vx, vz
        else:                 p_, q_ = vx, vy
        BUILD_CIX[f, i] = (2 if p_ >= 0.5 else 0) + (1 if q_ >= 0.5 else 0)






BUILD_FACE_N = np.array([
    [ 0.0,  1.0,  0.0], # +y
    [ 0.0, -1.0,  0.0], # -y
    [-1.0,  0.0,  0.0], # -x
    [ 1.0,  0.0,  0.0], # +x
    [ 0.0,  0.0, -1.0], # -z
    [ 0.0,  0.0,  1.0], # +z
], dtype=np.float32)

# standard uv offs
# BL, BR, TR, BL, TR, TL
BUILD_FACE_UV = np.array([
    [0, 0], [1, 0], [1, 1], 
    [0, 0], [1, 1], [0, 1]
], dtype=np.float32)

# Maps BUILD_FACE idx -> block_uvs face index
# BUILD     : 0=+y,  1=-y,     2=-x,    3=+x,    4=-z,   5=+z
# block uvs : 0=top, 1=bottom, 2=north, 3=south, 4=east, 5=west
FACE_UV_IDX = np.array([0, 1, 5, 4, 2, 3], dtype=np.int32)











@njit(cache=True, fastmath=True, nogil=True, inline='always')
def __emitface(
        vertices, idx, 
        x, y, z, ox, oz,
        face, l4,
        u0, v0, uw, uh,
        bfv, bfn, bfuv
    ):


    fsh = FACE_SHADE[face]


    for i in range(6):

        vx = bfv[face, i, 0]
        vy = bfv[face, i, 1]
        vz = bfv[face, i, 2]

        vertices[idx]     = x + vx + ox
        vertices[idx + 1] = y + vy
        vertices[idx + 2] = z + vz + oz
        c = BUILD_CIX[face, i]
        vertices[idx + 3] = l4[c, 0]
        vertices[idx + 4] = l4[c, 1]
        vertices[idx + 5] = l4[c, 2] * fsh
        vertices[idx + 6] = u0 + bfuv[i, 0] * uw
        vertices[idx + 7] = v0 + bfuv[i, 1] * uh
        idx += 8
        
        
    return idx








@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _emitToprot(
        vertices, 
        idx, x, y, z, 
        ox, oz, l4,
        c0u, c0v,
        c1u, c1v, 
        c2u, c2v, 
        c3u, c3v, 
        bfv
    ):
        
    # corners: v0->c0, v1->c1, v2->c2, v3->c0, v4->c2, v5->c3

    for i in range(6):
        vx = bfv[0, i, 0]
        vy = bfv[0, i, 1]
        vz = bfv[0, i, 2]

        vertices[idx]     = x + vx + ox
        vertices[idx + 1] = y + vy
        vertices[idx + 2] = z + vz + oz
        c = BUILD_CIX[0, i]
        vertices[idx + 3] = l4[c, 0]
        vertices[idx + 4] = l4[c, 1]
        vertices[idx + 5] = l4[c, 2]

        
        if   i == 0: vertices[idx + 6] = c0u; vertices[idx + 7] = c0v
        elif i == 3: vertices[idx + 6] = c0u; vertices[idx + 7] = c0v
        elif i == 1: vertices[idx + 6] = c1u; vertices[idx + 7] = c1v
        elif i == 2: vertices[idx + 6] = c2u; vertices[idx + 7] = c2v
        elif i == 4: vertices[idx + 6] = c2u; vertices[idx + 7] = c2v
        else:        vertices[idx + 6] = c3u; vertices[idx + 7] = c3v
        idx += 8
        
    return idx






@njit(cache=True, fastmath=True, nogil=True, inline='always')
def __emitwater(
        tverts, 
        idx, x, y, z, 
        ox, oz, face, l4,
        u0, v0, uw, uh,
        water_h, bfv, bfn, bfuv
    ):

    fsh = FACE_SHADE[face]


    for i in range(6):
        
        vx = bfv[face, i, 0]
        vy = bfv[face, i, 1]
        vz = bfv[face, i, 2]
        if vy > 0.5:
            vy = water_h
            
            
        tverts[idx]     = x + vx + ox
        tverts[idx + 1] = y + vy
        tverts[idx + 2] = z + vz + oz
        tverts[idx + 3] = l4[0, 0]
        tverts[idx + 4] = l4[0, 1]
        tverts[idx + 5] = l4[0, 2] * fsh
        tverts[idx + 6] = u0 + bfuv[i, 0] * uw
        tverts[idx + 7] = v0 + bfuv[i, 1] * uh
        idx += 8
        
        
    return idx


@njit(cache=True, fastmath=True, nogil=True, inline='always')
def __emitgrass(
        vertices, idx, 
        x, y, z, 
        ox, oz, l4,
        u0, v0, uw, uh,
        gv, bfuv
    ):
        
        
    for plane in range(4):
        for i in range(6):
            vertices[idx]     = x + gv[plane, i, 0] + ox
            vertices[idx + 1] = y + gv[plane, i, 1]
            vertices[idx + 2] = z + gv[plane, i, 2] + oz

            vertices[idx + 3] = l4[0, 0]
            vertices[idx + 4] = l4[0, 1]
            vertices[idx + 5] = l4[0, 2]
            vertices[idx + 6] = u0 + bfuv[i, 0] * uw
            vertices[idx + 7] = v0 + bfuv[i, 1] * uh
            idx += 8
            
    return idx








@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _remapface(
        btype, block_raw, 
        geom_face, facing_type, 
        h_remap, a_remap
    ):
        
        
    ft = facing_type[btype]
    if ft == 0: return geom_face
    
    
    
    facing_val = (block_raw >> 10) & 0x7
    if ft == 1:
        if facing_val > 3: facing_val = 0
        return h_remap[facing_val, geom_face]
        
        
    if ft == 2:
        if facing_val > 2: facing_val = 0
        return a_remap[facing_val, geom_face]
        
    return geom_face








@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _get_facerot(btype, block_raw, geom_face, facing_type, a_rot):
    
    if facing_type[btype] != 2: return 0
        
        
    facing_val = (block_raw >> 10) & 0x7
    if facing_val > 2: facing_val = 0
    
    return a_rot[facing_val, geom_face]






@njit(cache=True, fastmath=True, nogil=True, inline='always')
def _emit_facerot1(
        vertices, idx, 
        x, y, z, ox, oz, 
        face, l4,
        u0, v0, 
        uw, uh, 
        bfv, bfn
    ):
    # 90 uv rotate
    fsh = FACE_SHADE[face]



    for i in range(6):
        vx = bfv[face, i, 0]
        vy = bfv[face, i, 1]
        vz = bfv[face, i, 2]

        vertices[idx]     = x + vx + ox
        vertices[idx + 1] = y + vy
        vertices[idx + 2] = z + vz + oz
        c = BUILD_CIX[face, i]
        vertices[idx + 3] = l4[c, 0]
        vertices[idx + 4] = l4[c, 1]
        vertices[idx + 5] = l4[c, 2] * fsh

        
        if   i == 0: vertices[idx + 6] = u0;      vertices[idx + 7] = v0 + uh
        elif i == 3: vertices[idx + 6] = u0;      vertices[idx + 7] = v0 + uh
        elif i == 1: vertices[idx + 6] = u0;      vertices[idx + 7] = v0
        elif i == 2: vertices[idx + 6] = u0 + uw; vertices[idx + 7] = v0
        elif i == 4: vertices[idx + 6] = u0 + uw; vertices[idx + 7] = v0
        else:        vertices[idx + 6] = u0 + uw; vertices[idx + 7] = v0 + uh
        idx += 8
        
        
    return idx









# "The struggle itself toward the heights is enough to fill a man's heart. One must imagine Sisyphus happy."
# -- Albert Camus
@njit(cache=True, fastmath=True, nogil=True)
def build_meshjit(
        voxels, 
        offset_x, offset_z, 
        voxels_nx, voxels_px, 
        voxels_nz, voxels_pz, 
        skylight,
        light_nx, light_px,
        light_nz, light_pz,
        blocklight,
        blight_nx, blight_px,
        blight_nz, blight_pz,
        block_uvs, uv_w, uv_h,
        custom_faces, #
        render_mode, 
        num_elems, blk_elems, 
        uv_mode, 
        cull_topbot, 
        bfv, bfn, bfuv, gv, facing_type, 
        h_remap, a_remap, a_rot, b_faceuvs, b_facetex, 
        connect_type, connect_fam, 
        arm_num, arm_elems, arm_faceuvs, arm_facetex, 
        state_elemoff, state_elemnum
    ):



    # cast -> f32 : match buvs dtype
    uv_w = np.float32(uv_w)
    uv_h = np.float32(uv_h)
    
    maxv = min(CHUNK_SZ * CHUNK_H * CHUNK_SZ // 2 * 6 * 8, 1_500_000)
    vertices = np.empty(maxv, dtype=np.float32)
    vertidx  = 0
    
    # trans buff
    tverts = np.empty(maxv // 2, dtype=np.float32)
    tidx = 0

    # corner scratch + 3x3 face patch
    l4 = np.empty((4, 3), dtype=np.float32)
    p9 = np.empty((3, 3, 3), dtype=np.int32)


    
    for x in range(CHUNK_SZ):
        for y in range(CHUNK_H):
            for z in range(CHUNK_SZ):

                raw_btype = voxels[x, y, z]
                btype = raw_btype & 0x3FF
                if btype == 0: continue
                
                is_water = (btype == 5 or btype == 154)
                
                
                u_start = block_uvs[btype, 0, 0]
                v_start = block_uvs[btype, 0, 1]
                
                if btype == 10:
                    ly = y + 1 if y + 1 < CHUNK_H else y
                    _flat(l4, blocklight[x, ly, z], skylight[x, ly, z])
                    vertidx = __emitgrass(vertices, vertidx,
                        float(x), float(y), float(z), offset_x, offset_z,
                        l4, u_start, v_start, uv_w, uv_h, gv, bfuv)
                    continue
                
                if is_water:
                    ly = y + 1 if y + 1 < CHUNK_H else y
                    _flat(l4, blocklight[x, ly, z], skylight[x, ly, z])

                    u_start = block_uvs[btype, 0, 0]
                    v_start = block_uvs[btype, 0, 1]
                    
                    
                    water_h = get_waterh(raw_btype)
                    
                    # draw n if neighbor != water
                    
                    is_waterneighb = False
                    if x + 1 < CHUNK_SZ:
                        is_waterneighb = is_localwater(voxels, x + 1, y, z)
                        
                        
                    else:
                        nb = voxels_px[0, y, z] & 0x3FF
                        is_waterneighb = (nb == 5 or nb == 154)
                        
                    if not is_waterneighb:
                        tidx = __emitwater(
                            tverts, tidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z, 3, l4, 
                            u_start, v_start, uv_w, uv_h, 
                            water_h, bfv, bfn, 
                            bfuv
                        )
                        
                        
                        
                    
                    
                    is_waterneighb = False
                    if x - 1 >= 0:
                        is_waterneighb = is_localwater(voxels, x - 1, y, z)
                        
                    else:
                        nb = voxels_nx[CHUNK_SZ - 1, y, z] & 0x3FF
                        is_waterneighb = (nb == 5 or nb == 154)
                        
                        
                    if not is_waterneighb:
                        tidx = __emitwater(
                            tverts, tidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z,
                            2, l4, 
                            u_start, v_start, 
                            uv_w, uv_h, 
                            water_h, 
                            bfv, bfn, 
                            bfuv
                        )

                    
                    
                    is_waterneighb = False
                    if y + 1 < CHUNK_H:
                        is_waterneighb = is_localwater(voxels, x, y + 1, z)
                    if not is_waterneighb:
                        tidx = __emitwater(
                            tverts, tidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z,
                            0, l4, 
                            u_start, v_start, 
                            uv_w, uv_h, 
                            water_h, 
                            bfv, bfn, 
                            bfuv
                        )
                    
                    
                    is_waterneighb = False
                    if y - 1 >= 0:
                        is_waterneighb = is_localwater(voxels, x, y - 1, z)


                    if not is_waterneighb:
                        tidx = __emitwater(
                            tverts, tidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z,
                            1, l4, 
                            u_start, v_start, 
                            uv_w, uv_h, 
                            water_h, 
                            bfv, bfn, 
                            bfuv
                        )



                    
                    
                    is_waterneighb = False
                    if z + 1 < CHUNK_SZ:
                        is_waterneighb = is_localwater(voxels, x, y, z + 1)

                    else:
                        nb = voxels_pz[x, y, 0] & 0x3FF
                        is_waterneighb = (nb == 5 or nb == 154)


                    if not is_waterneighb:
                        tidx = __emitwater(
                            tverts, tidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z,
                            5, l4, 
                            u_start, v_start, 
                            uv_w, uv_h, 
                            water_h, 
                            bfv, bfn, 
                            bfuv
                        )
                    


                    
                    is_waterneighb = False
                    if z - 1 >= 0:
                        is_waterneighb = is_localwater(voxels, x, y, z - 1)
                        
                    else:
                        nb = voxels_nz[x, y, CHUNK_SZ - 1] & 0x3FF
                        is_waterneighb = (nb == 5 or nb == 154)


                    if not is_waterneighb:
                        tidx = __emitwater(
                            tverts, tidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z,
                            4, l4, 
                            u_start, v_start, 
                            uv_w, uv_h, 
                            water_h, 
                            bfv, bfn, 
                            bfuv
                        )
                    
                    continue
                
                
                
                
                
                
                
                
                if render_mode[btype] == 2 or render_mode[btype] == 3:
                    _flat(l4, blocklight[x, y, z], skylight[x, y, z])

                    # stained panes (317-332) -> trans buffer
                    is_customtrans = (btype >= 317 and btype <= 332)

                    _uvmode = uv_mode[btype]
                    do_cull = cull_topbot[btype]

                    n_elems = num_elems[btype]
                    bstate = (raw_btype >> 10) & 0x1F
                    elem_base = state_elemoff[btype, bstate]

                    # neighbor aware orientation
                    
                    # rails
                    # elem 0=N/S straight, 1=E/W straight, 2=NE curve, 3=NW, 4=SW, 5=SE
                    if btype >= 198 and btype <= 202:



                        _r_n = False; _r_s = False; _r_e = False; _r_w = False
                        _rnb = np.int32(0)
                        if z - 1 >= 0:       _rnb = voxels[x, y, z - 1] & 0x3FF
                        else:                _rnb = voxels_nz[x, y, CHUNK_SZ - 1] & 0x3FF
                        
                        if _rnb >= 198 and _rnb <= 202: _r_n = True
                        
                        if z + 1 < CHUNK_SZ: _rnb = voxels[x, y, z + 1] & 0x3FF
                        else:                _rnb = voxels_pz[x, y, 0] & 0x3FF
                        
                        if _rnb >= 198 and _rnb <= 202: _r_s = True
                        
                        if x + 1 < CHUNK_SZ: _rnb = voxels[x + 1, y, z] & 0x3FF
                        else:                _rnb = voxels_px[0, y, z] & 0x3FF
                        
                        if _rnb >= 198 and _rnb <= 202: _r_e = True
                        
                        if x - 1 >= 0:       _rnb = voxels[x - 1, y, z] & 0x3FF
                        else:                _rnb = voxels_nx[CHUNK_SZ - 1, y, z] & 0x3FF
                        
                        if _rnb >= 198 and _rnb <= 202: _r_w = True
                        
                        _r_ns = _r_n or _r_s
                        _r_ew = _r_e or _r_w
                        
                        
                        
                        
                        
                        # straight > curve
                        if btype == 198 and _r_ns and _r_ew:
                            if   _r_n and _r_s: elem_base = 0  # N/S straight>
                            elif _r_e and _r_w: elem_base = 1  # E/W straight>
                            elif _r_n and _r_e: elem_base = 2  # NE curve
                            elif _r_n and _r_w: elem_base = 3  # NW curve
                            elif _r_s and _r_w: elem_base = 4  # SW curve
                            else:               elem_base = 5  # SE curve
                            
                        elif _r_ew and not _r_ns: elem_base = 1  # E/W straight
                        else: elem_base = 0  # N/S straight
                        
                        
                        

                    # stair
                    # shape 0=straight, 1=out left, 2=out right, 3=inn left, 4=inn right
                    # lookup = shape * 4 + orient (0-19)
                    if btype >= 206 and btype <= 219:
                        _st_ori = np.int32(bstate)  # 0=N, 1=S, 2=E, 3=W
                        _st_shape = np.int32(0)
                        _st_fdx = np.int32(0); _st_fdz = np.int32(0)
                        _st_bdx = np.int32(0); _st_bdz = np.int32(0)
                        _st_lp  = np.int32(0); _st_rp  = np.int32(0)
                        
                        
                        
                        if _st_ori == 0:    # n: front=-z, back=+z, left=W(3), right=E(2)
                            _st_fdz = np.int32(-1); _st_bdz = np.int32(1)
                            _st_lp  = np.int32(3);  _st_rp  = np.int32(2)
                            
                        elif _st_ori == 1:  # s: front=+z, back=-z, left=E(2), right=W(3)
                            _st_fdz = np.int32(1);  _st_bdz = np.int32(-1)
                            _st_lp  = np.int32(2);  _st_rp  = np.int32(3)
                            
                        elif _st_ori == 2:  # e: front=+x, back=-x, left=N(0), right=S(1)
                            _st_fdx = np.int32(1);  _st_bdx = np.int32(-1)
                            _st_lp  = np.int32(0);  _st_rp  = np.int32(1)
                            
                        else:               # w: front=-x, back=+x, left=S(1), right=N(0)
                            _st_fdx = np.int32(-1); _st_bdx = np.int32(1)
                            _st_lp  = np.int32(1);  _st_rp  = np.int32(0)
                            
                            
                        
                        
                        # outer corner
                        _st_bx = np.int32(x) + _st_bdx
                        _st_bz = np.int32(z) + _st_bdz
                        _st_b_raw = np.uint16(0)
                        
                        if _st_bx < 0:           _st_b_raw = voxels_nx[CHUNK_SZ - 1, y, _st_bz]
                        elif _st_bx >= CHUNK_SZ: _st_b_raw = voxels_px[0, y, _st_bz]
                        elif _st_bz < 0:         _st_b_raw = voxels_nz[_st_bx, y, CHUNK_SZ - 1]
                        elif _st_bz >= CHUNK_SZ: _st_b_raw = voxels_pz[_st_bx, y, 0]
                        else:                    _st_b_raw = voxels[_st_bx, y, _st_bz]
                        
                        
                        
                        
                        _st_bt = np.int32(_st_b_raw & np.uint16(0x3FF))
                        if _st_bt >= 206 and _st_bt <= 219:
                            
                            _st_bf = np.int32((_st_b_raw >> np.uint16(10)) & np.uint16(0x1F))
                            if   _st_bf == _st_lp: _st_shape = np.int32(1)  # out left
                            elif _st_bf == _st_rp: _st_shape = np.int32(2)  # out right
                            
                        
                        
                        # inner
                        if _st_shape == 0:
                            _st_fx = np.int32(x) + _st_fdx
                            _st_fz = np.int32(z) + _st_fdz
                            _st_f_raw = np.uint16(0)
                            
                            if _st_fx < 0:           _st_f_raw = voxels_nx[CHUNK_SZ - 1, y, _st_fz]
                            elif _st_fx >= CHUNK_SZ: _st_f_raw = voxels_px[0, y, _st_fz]
                            elif _st_fz < 0:         _st_f_raw = voxels_nz[_st_fx, y, CHUNK_SZ - 1]
                            elif _st_fz >= CHUNK_SZ: _st_f_raw = voxels_pz[_st_fx, y, 0]
                            else:                    _st_f_raw = voxels[_st_fx, y, _st_fz]
                            
                            
                            
                            
                            _st_ft = np.int32(_st_f_raw & np.uint16(0x3FF))
                            if _st_ft >= 206 and _st_ft <= 219:
                                _st_ff = np.int32((_st_f_raw >> np.uint16(10)) & np.uint16(0x1F))
                                if   _st_ff == _st_lp: _st_shape = np.int32(3)  # inn left
                                elif _st_ff == _st_rp: _st_shape = np.int32(4)  # inn right
                        
                        
                        
                        
                        
                        _st_lookup = _st_shape * np.int32(4) + _st_ori
                        _n_override = state_elemnum[btype, _st_lookup]
                        if _n_override > 0: n_elems = _n_override
                        elem_base = state_elemoff[btype, _st_lookup]









                    # redstone wir
                    # 4-bit nsew connect mask -> 16 elem slot
                    # mask = (N<<3)|(S<<2)|(E<<1)|W -> elem_base = mask (0-15)
                    if btype == 159:
                        _rd_mask = np.int32(0)
                        _rdn = np.int32(0)
                        
                        if z - 1 >= 0:       _rdn = voxels[x, y, z - 1] & 0x3FF
                        else:                _rdn = voxels_nz[x, y, CHUNK_SZ - 1] & 0x3FF

                        if _rdn == 159:      _rd_mask = _rd_mask | np.int32(8) # N
                        if z + 1 < CHUNK_SZ: _rdn = voxels[x, y, z + 1] & 0x3FF
                        else:                _rdn = voxels_pz[x, y, 0] & 0x3FF

                        if _rdn == 159:      _rd_mask = _rd_mask | np.int32(4) # s
                        if x + 1 < CHUNK_SZ: _rdn = voxels[x + 1, y, z] & 0x3FF
                        else:                _rdn = voxels_px[0, y, z] & 0x3FF

                        if _rdn == 159:      _rd_mask = _rd_mask | np.int32(2) # e
                        if x - 1 >= 0:       _rdn = voxels[x - 1, y, z] & 0x3FF
                        else:                _rdn = voxels_nx[CHUNK_SZ - 1, y, z] & 0x3FF

                        if _rdn == 159:      _rd_mask = _rd_mask | np.int32(1) # w
                        
                        
                        elem_base = _rd_mask
                    
                    
                    
                    
                    
                    
                    
                    for elem_idx in range(elem_base, elem_base + n_elems):
                        elem_faces = blk_elems[btype, elem_idx]

                        for face in range(6):
                            draw = True
                            if btype == 159 and face > 0:  draw = False
                            if do_cull:
                                
                                
                                if face == 0:
                                    if y + 1 < CHUNK_H and get_localblock(voxels, x, y + 1, z) == btype:
                                        draw = False
                                        
                                elif face == 1:
                                    if y - 1 >= 0 and get_localblock(voxels, x, y - 1, z) == btype:
                                        draw = False

                            
                            
                            
                            
                            
                            if draw:
                                u_start = block_uvs[btype, face, 0]
                                v_start = block_uvs[btype, face, 1]

                                face_v = elem_faces[face]

                                if face == 0:   nx, ny, nz =  0.0,  1.0,  0.0
                                elif face == 1: nx, ny, nz =  0.0, -1.0,  0.0
                                elif face == 2: nx, ny, nz =  0.0,  0.0, -1.0
                                elif face == 3: nx, ny, nz =  0.0,  0.0,  1.0
                                elif face == 4: nx, ny, nz =  1.0,  0.0,  0.0
                                else:           nx, ny, nz = -1.0,  0.0,  0.0
                                
                                

                                if _uvmode == 2:
                                    
                                    # all BL BR TR TL pairs 
                                    tex_u = b_facetex[btype, elem_idx, face, 0]
                                    if tex_u >= 0.0:
                                        u_start = tex_u
                                        v_start = b_facetex[btype, elem_idx, face, 1]
                                    
                                    
                                    fuv = b_faceuvs[btype, elem_idx, face]
                                    # BL_u, BL_v, BR_u, BR_v, TR_u, TR_v, TL_u, TL_v
                                    # vertex indices: 0,3=BL  1=BR  2,4=TR  5=TL
                                    u_bl = u_start + fuv[0] * uv_w;  v_bl = v_start + fuv[1] * uv_h
                                    u_br = u_start + fuv[2] * uv_w;  v_br = v_start + fuv[3] * uv_h
                                    u_tr = u_start + fuv[4] * uv_w;  v_tr = v_start + fuv[5] * uv_h
                                    u_tl = u_start + fuv[6] * uv_w;  v_tl = v_start + fuv[7] * uv_h
                                
                                    
                                elif _uvmode == 1:
                                    u_bl = u_start;         v_bl = v_start
                                    u_br = u_start + uv_w;  v_br = v_start
                                    u_tr = u_start + uv_w;  v_tr = v_start + uv_h
                                    u_tl = u_start;         v_tl = v_start + uv_h

                                
                                    
                                for i in range(6):
                                    vx = face_v[i, 0]
                                    vy = face_v[i, 1]
                                    vz = face_v[i, 2]

                                    if _uvmode != 0:
                                        # precomp corner uv
                                        # 0,3=BL  1=BR  2,4=TR  5=TL
                                        if   i == 0: u = u_bl; v = v_bl
                                        elif i == 3: u = u_bl; v = v_bl
                                        elif i == 1: u = u_br; v = v_br
                                        elif i == 2 :u = u_tr; v = v_tr
                                        elif i == 4: u = u_tr; v = v_tr
                                        else:        u = u_tl; v = v_tl


                                        
                                    else:
                                        if face == 0:
                                            u = u_start + vx * uv_w
                                            v = v_start + (1.0 - vz) * uv_h
                                            
                                        elif face == 1:
                                            u = u_start + vx * uv_w
                                            v = v_start + vz * uv_h
                                            
                                        elif face == 2:
                                            u = u_start + (1.0 - vx) * uv_w
                                            v = v_start + (1.0 - vy) * uv_h
                                            
                                        elif face == 3:
                                            u = u_start + vx * uv_w
                                            v = v_start + (1.0 - vy) * uv_h
                                            
                                        elif face == 4:
                                            u = u_start + (1.0 - vz) * uv_w
                                            v = v_start + (1.0 - vy) * uv_h
                                            
                                        else:
                                            u = u_start + vz * uv_w
                                            v = v_start + (1.0 - vy) * uv_h




                                    if is_customtrans:
                                        tverts[tidx] = x + vx + offset_x
                                        tverts[tidx + 1] = y + vy
                                        tverts[tidx + 2] = z + vz + offset_z
                                        tverts[tidx + 3] = l4[0, 0]
                                        tverts[tidx + 4] = l4[0, 1]
                                        tverts[tidx + 5] = l4[0, 2] * _nshade(nx, ny, nz)
                                        tverts[tidx + 6] = u
                                        tverts[tidx + 7] = v
                                        tidx += 8
                                        
                                        
                                    else:
                                        vertices[vertidx] = x + vx + offset_x
                                        vertices[vertidx + 1] = y + vy
                                        vertices[vertidx + 2] = z + vz + offset_z
                                        vertices[vertidx + 3] = l4[0, 0]
                                        vertices[vertidx + 4] = l4[0, 1]
                                        vertices[vertidx + 5] = l4[0, 2] * _nshade(nx, ny, nz)
                                        vertices[vertidx + 6] = u
                                        vertices[vertidx + 7] = v
                                        vertidx += 8
                                        
                                        
                                        
                                        
                                        
                                        
                                        
                                        

                    
                    
                    # fence && walls
                    if connect_type[btype] > 0:
                        cf = connect_fam[btype]
                        
                        for dir_idx in range(4):
                            if dir_idx == 0:         # n -z
                                if z - 1 >= 0:       nb = voxels[x, y, z - 1] & 0x3FF
                                else:                nb = voxels_nz[x, y, CHUNK_SZ - 1] & 0x3FF
                                
                            elif dir_idx == 1:       # s +z
                                if z + 1 < CHUNK_SZ: nb = voxels[x, y, z + 1] & 0x3FF
                                else:                nb = voxels_pz[x, y, 0] & 0x3FF
                                
                            elif dir_idx == 2:       # e +x
                                if x + 1 < CHUNK_SZ: nb = voxels[x + 1, y, z] & 0x3FF
                                else:                nb = voxels_px[0, y, z] & 0x3FF
                                
                            else:                    # w -x
                                if x - 1 >= 0:       nb = voxels[x - 1, y, z] & 0x3FF
                                else:                nb = voxels_nx[CHUNK_SZ - 1, y, z] & 0x3FF

                            
                            
                            
                            _connect = False
                            if nb > 0:
                                nbf = connect_fam[nb]
                                if nbf == cf and cf > 0:   _connect = True # same fam
                                elif render_mode[nb] == 0: _connect = True # solid
                                
                                
                                    

                            if _connect:
                                n_arm = arm_num[btype, dir_idx]
                                for arm_ei in range(n_arm):
                                    arm_f = arm_elems[btype, dir_idx, arm_ei]
                                    for face in range(6):
                                        arm_fv = arm_f[face]
                                        # skip 0area faces
                                        if (
                                            arm_fv[0, 0] == arm_fv[1, 0] and 
                                            arm_fv[0, 1] == arm_fv[1, 1] and 
                                            arm_fv[0, 2] == arm_fv[1, 2]
                                        ): continue
                                        
                                        

                                        if   face == 0: anx, any_, anz =  0.0,  1.0,  0.0
                                        elif face == 1: anx, any_, anz =  0.0, -1.0,  0.0
                                        elif face == 2: anx, any_, anz =  0.0,  0.0, -1.0
                                        elif face == 3: anx, any_, anz =  0.0,  0.0,  1.0
                                        elif face == 4: anx, any_, anz =  1.0,  0.0,  0.0
                                        else:           anx, any_, anz = -1.0,  0.0,  0.0
                                        
                                        
                                        
                                        
                                        # arm_facetex -> atlas override
                                        # fallback -> block uv
                                        a_tex_u = arm_facetex[btype, dir_idx, arm_ei, face, 0]
                                        
                                        if a_tex_u >= 0.0:
                                            au_start = a_tex_u
                                            av_start = arm_facetex[btype, dir_idx, arm_ei, face, 1]
                                            
                                        else:
                                            au_start = block_uvs[btype, face, 0]
                                            av_start = block_uvs[btype, face, 1]
                                            
                                            
                                            

                                        # proportional uvs
                                        afuv = arm_faceuvs[btype, dir_idx, arm_ei, face]
                                        au_bl = au_start + afuv[0] * uv_w;  av_bl = av_start + afuv[1] * uv_h
                                        au_br = au_start + afuv[2] * uv_w;  av_br = av_start + afuv[3] * uv_h
                                        au_tr = au_start + afuv[4] * uv_w;  av_tr = av_start + afuv[5] * uv_h
                                        au_tl = au_start + afuv[6] * uv_w;  av_tl = av_start + afuv[7] * uv_h

                                        
                                        
                                        
                                        
                                            
                                        for i in range(6):
                                            avx = arm_fv[i, 0]
                                            avy = arm_fv[i, 1]
                                            avz = arm_fv[i, 2]
                                            if   i == 0: au = au_bl; av = av_bl
                                            elif i == 3: au = au_bl; av = av_bl
                                            elif i == 1: au = au_br; av = av_br
                                            elif i == 2: au = au_tr; av = av_tr
                                            elif i == 4: au = au_tr; av = av_tr
                                            else:        au = au_tl; av = av_tl
                                            
                                                
                                                
                                                
                                                    
                                            if is_customtrans:
                                                tverts[tidx] = x + avx + offset_x
                                                tverts[tidx + 1] = y + avy
                                                tverts[tidx + 2] = z + avz + offset_z
                                                tverts[tidx + 3] = l4[0, 0]
                                                tverts[tidx + 4] = l4[0, 1]
                                                tverts[tidx + 5] = l4[0, 2] * _nshade(anx, any_, anz)
                                                tverts[tidx + 6] = au
                                                tverts[tidx + 7] = av
                                                tidx += 8
                                                
                                                
                                            else:
                                                vertices[vertidx] = x + avx + offset_x
                                                vertices[vertidx + 1] = y + avy
                                                vertices[vertidx + 2] = z + avz + offset_z
                                                vertices[vertidx + 3] = l4[0, 0]
                                                vertices[vertidx + 4] = l4[0, 1]
                                                vertices[vertidx + 5] = l4[0, 2] * _nshade(anx, any_, anz)
                                                vertices[vertidx + 6] = au
                                                vertices[vertidx + 7] = av
                                                vertidx += 8

                    
                    
                    continue
                    
                    
                    
                    
                    
                    
                    
                    
                    
                    
                
                
                if btype == 156: continue #barrier:156

                # stained glass:119-134
                # -> trans buffer
                is_stainglass = (btype >= 119 and btype <= 134)



                # right +x (BUILD_FACE_V index 3)
                _draw = False
                if x + 1 < CHUNK_SZ:
                    if not is_localsolid(voxels, x + 1, y, z):
                        _draw = True

                else:
                    if not is_localsolid(voxels_px, 0, y, z):
                        _draw = True


                
                if _draw:
                    _corners(
                        l4, p9, 0, x + 1, y, z,
                        voxels, voxels_nx, voxels_px, voxels_nz, voxels_pz,
                        skylight, light_nx, light_px, light_nz, light_pz,
                        blocklight, blight_nx, blight_px, blight_nz, blight_pz
                    )

                    rf = _remapface(btype, raw_btype, 4, facing_type, h_remap, a_remap)
                    u_start = block_uvs[btype, rf, 0]
                    v_start = block_uvs[btype, rf, 1]
                    
                    
                    

                    if btype == 1:
                        is_grassbelw = False
                        if x + 1 < CHUNK_SZ:
                             if get_localblock(voxels, x + 1, y - 1, z) == 1:
                                 is_grassbelw = True
                                 
                        elif y - 1 >= 0:
                             if get_localblock(voxels_px, 0, y - 1, z) == 1:
                                 is_grassbelw = True
                                 
                        if is_grassbelw:
                            u_start = block_uvs[btype, 0, 0]
                            v_start = block_uvs[btype, 0, 1]
                    
                    
                    
                    
                    
                    
                    
                    if _get_facerot(btype, raw_btype, 4, facing_type, a_rot):
                        if is_stainglass:
                            tidx = _emit_facerot1(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                3, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                        else:
                            vertidx = _emit_facerot1(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                3, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                    
                    
                    else:
                        if is_stainglass:
                            tidx = __emitface(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                3, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )
                            
                        else:
                            vertidx = __emitface(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                3, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )

                # -x
                _draw = False
                if x - 1 >= 0:
                    if not is_localsolid(voxels, x - 1, y, z):
                        _draw = True
                        
                else:
                    if not is_localsolid(voxels_nx, CHUNK_SZ - 1, y, z):
                        _draw = True
                        
                        
                        
                        
                        

                if _draw:
                    _corners(
                        l4, p9, 0, x - 1, y, z,
                        voxels, voxels_nx, voxels_px, voxels_nz, voxels_pz,
                        skylight, light_nx, light_px, light_nz, light_pz,
                        blocklight, blight_nx, blight_px, blight_nz, blight_pz
                    )

                    rf = _remapface(btype, raw_btype, 5, facing_type, h_remap, a_remap)
                    u_start = block_uvs[btype, rf, 0]
                    v_start = block_uvs[btype, rf, 1]

                    if btype == 1:
                        is_grassbelw = False
                        if x - 1 >= 0:
                            if get_localblock(voxels, x - 1, y - 1, z) == 1:
                                is_grassbelw = True
                                
                        elif y - 1 >= 0:
                            if get_localblock(voxels_nx, CHUNK_SZ - 1, y - 1, z) == 1:
                                is_grassbelw = True
                                
                                
                        if is_grassbelw:
                            u_start = block_uvs[btype, 0, 0]
                            v_start = block_uvs[btype, 0, 1]
                            
                            
                            

                    if _get_facerot(btype, raw_btype, 5, facing_type, a_rot):
                        if is_stainglass:
                            tidx = _emit_facerot1(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                2, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                        else:
                            vertidx = _emit_facerot1(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                2, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                            
                    
                    else:
                        if is_stainglass:
                            tidx = __emitface(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                2, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )
                            
                        else:
                            vertidx = __emitface(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                2, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )

                
                
                
                
                # +y BUILD_FACE_V idc 0
                if not is_localsolid(voxels, x, y + 1, z):
                    _corners(
                        l4, p9, 1, x, y + 1, z,
                        voxels, voxels_nx, voxels_px, voxels_nz, voxels_pz,
                        skylight, light_nx, light_px, light_nz, light_pz,
                        blocklight, blight_nx, blight_px, blight_nz, blight_pz
                    )

                    rf = _remapface(btype, raw_btype, 0, facing_type, h_remap, a_remap)
                    u_start = block_uvs[btype, rf, 0]
                    v_start = block_uvs[btype, rf, 1]

                    #det rot top face + axis-block rot
                    rot = 0
                    is_player_placed = (raw_btype & 0x8000) != 0

                    if not is_player_placed and (btype == 1 or btype == 4 or btype == 6 or btype == 14):
                        wx = int(offset_x + x)
                        wz = int(offset_z + z)
                        k = (wx * 374761393) ^ (int(y) * 668265263) ^ (wz * 961748927)
                        k = (k ^ (k >> 13)) * 1274126177
                        rot = (k >> 24) & 3

                    rot = (rot + _get_facerot(btype, raw_btype, 0, facing_type, a_rot)) & 3

                    u0, v0 = u_start, v_start
                    u1, v1 = u_start + uv_w, v_start
                    u2, v2 = u_start + uv_w, v_start + uv_h
                    u3, v3 = u_start, v_start + uv_h
                    
                    if   rot == 0: c0u, c0v = u0, v0; c1u, c1v = u1, v1; c2u, c2v = u2, v2; c3u, c3v = u3, v3
                    elif rot == 1: c0u, c0v = u3, v3; c1u, c1v = u0, v0; c2u, c2v = u1, v1; c3u, c3v = u2, v2
                    elif rot == 2: c0u, c0v = u2, v2; c1u, c1v = u3, v3; c2u, c2v = u0, v0; c3u, c3v = u1, v1
                    else:          c0u, c0v = u1, v1; c1u, c1v = u2, v2; c2u, c2v = u3, v3; c3u, c3v = u0, v0

                    if is_stainglass:
                        tidx = _emitToprot(
                            tverts, tidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z, l4,
                            c0u, c0v, 
                            c1u, c1v, 
                            c2u, c2v, 
                            c3u, c3v, 
                            bfv
                        )
                        
                    else:
                        vertidx = _emitToprot(
                            vertices, vertidx,
                            float(x), float(y), float(z), 
                            offset_x, offset_z, l4,
                            c0u, c0v, 
                            c1u, c1v, 
                            c2u, c2v, 
                            c3u, c3v, 
                            bfv
                        )
                        
                        

                # -y BUILD_FACE_V idx 1
                if not is_localsolid(voxels, x, y - 1, z):
                    _corners(
                        l4, p9, 1, x, y - 1, z,
                        voxels, voxels_nx, voxels_px, voxels_nz, voxels_pz,
                        skylight, light_nx, light_px, light_nz, light_pz,
                        blocklight, blight_nx, blight_px, blight_nz, blight_pz
                    )

                    rf = _remapface(btype, raw_btype, 1, facing_type, h_remap, a_remap)
                    u_start = block_uvs[btype, rf, 0]
                    v_start = block_uvs[btype, rf, 1]



                    if _get_facerot(btype, raw_btype, 1, facing_type, a_rot):
                        if is_stainglass:
                            tidx = _emit_facerot1(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                1, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                            
                        else:
                            vertidx = _emit_facerot1(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                1, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                            
                    else:
                        if is_stainglass:
                            tidx = __emitface(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                1, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )
                            
                        else:
                            vertidx = __emitface(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                1, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )

                
                
                
                # +z
                _draw = False
                if z + 1 < CHUNK_SZ:
                    if not is_localsolid(voxels, x, y, z + 1):
                        _draw = True
                        
                else:
                    if not is_localsolid(voxels_pz, x, y, 0):
                        _draw = True
                
                
                
                
                
                if _draw:
                    _corners(
                        l4, p9, 2, x, y, z + 1,
                        voxels, voxels_nx, voxels_px, voxels_nz, voxels_pz,
                        skylight, light_nx, light_px, light_nz, light_pz,
                        blocklight, blight_nx, blight_px, blight_nz, blight_pz
                    )

                    rf = _remapface(btype, raw_btype, 3, facing_type, h_remap, a_remap)
                    u_start = block_uvs[btype, rf, 0]
                    v_start = block_uvs[btype, rf, 1]



                    if btype == 1:
                        is_grassbelw = False
                        if z + 1 < CHUNK_SZ:
                            if get_localblock(voxels, x, y - 1, z + 1) == 1:
                                is_grassbelw = True
                                
                        elif y - 1 >= 0:
                            if get_localblock(voxels_pz, x, y - 1, 0) == 1:
                                is_grassbelw = True
                                
                        if is_grassbelw:
                            u_start = block_uvs[btype, 0, 0]
                            v_start = block_uvs[btype, 0, 1]

                            

                    if _get_facerot(btype, raw_btype, 3, facing_type, a_rot):
                        if is_stainglass:
                            tidx = _emit_facerot1(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                5, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                        else:
                            vertidx = _emit_facerot1(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                5, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                            
                    else:
                        if is_stainglass:
                            tidx = __emitface(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                5, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )
                            
                        else:
                            vertidx = __emitface(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                5, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )
                            

                # -z
                _draw = False
                if z - 1 >= 0:
                    if not is_localsolid(voxels, x, y, z - 1):
                        _draw = True
                        
                else:
                    if not is_localsolid(voxels_nz, x, y, CHUNK_SZ - 1):
                        _draw = True
                        
                        
                        
                        
                        
                
                if _draw:
                    
                    _corners(
                        l4, p9, 2, x, y, z - 1,
                        voxels, voxels_nx, voxels_px, voxels_nz, voxels_pz,
                        skylight, light_nx, light_px, light_nz, light_pz,
                        blocklight, blight_nx, blight_px, blight_nz, blight_pz
                    )

                    
                    
                    rf = _remapface(btype, raw_btype, 2, facing_type, h_remap, a_remap)
                    u_start = block_uvs[btype, rf, 0]
                    v_start = block_uvs[btype, rf, 1]
                    
                    
                    

                    if btype == 1:
                        is_grassbelw = False
                        
                        if z - 1 >= 0:
                            if get_localblock(voxels, x, y - 1, z - 1) == 1:
                                is_grassbelw = True
                                
                        elif y - 1 >= 0:
                            if get_localblock(voxels_nz, x, y - 1, CHUNK_SZ - 1) == 1:
                                is_grassbelw = True
                                
                        if is_grassbelw:
                            u_start = block_uvs[btype, 0, 0]
                            v_start = block_uvs[btype, 0, 1]
                            
                            

                    if _get_facerot(btype, raw_btype, 2, facing_type, a_rot):
                        if is_stainglass:
                            tidx = _emit_facerot1(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                4, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                        else:
                            vertidx = _emit_facerot1(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                4, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn
                            )
                            
                            
                    else:
                        if is_stainglass:
                            tidx = __emitface(
                                tverts, tidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                4, l4, 
                                u_start, v_start,
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )
                            
                        else:
                            vertidx = __emitface(
                                vertices, vertidx,
                                float(x), float(y), float(z), 
                                offset_x, offset_z,
                                4, l4, 
                                u_start, v_start, 
                                uv_w, uv_h, 
                                bfv, bfn, 
                                bfuv
                            )

    return vertices[:vertidx], tverts[:tidx]
















