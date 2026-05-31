# kyklophobia

recreation of beta Minecraft in pure* python
NOT affiliated with mojang

```
(MUST have UV installed for virtual environment)

make run         -> launches launch.py
make server      -> launched server.py
```

**OLD** demo video: https://www.youtube.com/watch?v=o_IDO01NylM
| | |
|---|---|
| <img width="1598" height="898" alt="image" src="https://github.com/user-attachments/assets/bd2d3750-bd5b-4125-910e-9e6774a14e4c" /> | <img width="1601" height="900" alt="image" src="https://github.com/user-attachments/assets/2409f418-ea9b-4f53-bfb4-d800f6211943" /> |
| <img width="1607" height="901" alt="image" src="https://github.com/user-attachments/assets/f03f35ff-7676-4691-aba3-8c18c7b37c4f" /> | <img width="1603" height="901" alt="image" src="https://github.com/user-attachments/assets/38ae0a7e-8841-41e5-9d67-58b46f2c3dec" /> |



root `launch.py` & `server.py` are shim -> `client/launch.py`, `server/server.py`. gamefiles in `/content`

## first launch

slow. numba compiles `_generate`, `build_meshjit`, `bake_skylight` + smaller jit on first run, cache per-world in `saves/<world>/cache` (via `NUMBA_CACHE_DIR`). subsequent launches of that world fine. each world keeps its own cache so loading a second world doesnt evict the first

if world doesnt render, double esc and reload. fps also bad on first few run

## layout

```
mine/
├── launch.py         shim
├── server.py         shim
├── client/           
│   ├── launch.py     
│   ├── lconst.py     gui, palette, splashes
│   ├── ldata.py      world, server, configs
│   ├── lwidgets.py   ui widgets
│   └── lscreens.py   
├── content/          
│   ├── main.py       VoxelWorld. god object. owns ctx + every subsystem
│   ├── config.py     
│   ├── engine/       camera, physics, particles, shaders, gamma
│   ├── world/        terrain gen, chunk, block registry, renderers, anim
│   ├── entities/     player, held, drops, block entities
│   ├── ui/           HUD, inv, menus, chat
│   ├── network/      client + wire proto
│   ├── commands/     
│   └── items/        item registry + atlas
└── server/           headless. dup of whatever content/ it needs
```

saves live in a dedicated dir, no junction. launcher sets `config.root` -> `client/saves/`, server -> `server/saves/`. keep on gitignore


## voxels

chunk = `(16, 128, 16) uint16`.

```
bit  15  14 13 12 11 10  9 8 7 6 5 4 3 2 1 0
     F   S  S  S  S  S   I I I I I I I I I I
     |   \___________/   \_________________/
     |    5b state         10b block id (0x3FF, 1024 ids)
     mod-flag
```

mod flag = player placed vs generated. only flagged voxel hit disk. skylight is separate `(16,128,16) uint8` array. block entity (chest etc) are side dict keyed `(lx,ly,lz)`


## terrain gen

all hot fn `@njit`. entry `_generate` @ `terrain.py:386`, runs on thread pool

2D fractal perlin for climate (temp+humid), sampled coarse then bilinear per column. density noise + biome height bonus, solid if above smoothstep threshold near sea level

tree/rock placed after. cross chunk tree queue in `pending_decorations` -> floating trunk thing

biomes: `plains`, `desert`, `snowy`, `jungle`, `badlands`, `forest`


## chunk threading

```
mesh_builder_thread   (1)
    ├─ drains queue_chunkbuild (deque, dist-sorted to player)
    ├─ ungen chunk: submit to gen pool, await future
    ├─ cap CHUNK_PARALLEL=32 in-flight futures (fresh-world OOM guard)
    ├─ gen chunk: bake_skylight(...) -> build_meshjit(...) -> queue_meshupload
    └─ CHUNK_MESH_PTICK=16 builds/iter cap

io_thread             (1)
    └─ drains save_queue -> pickle.dump

main / GL
    └─ each frame drain queue_meshupload until:
                  CHUNK_UPLD_CAP=16 done, or
                  CHUNK_UPLD_BUDG_L=16ms (small Q) / _H=100ms (large Q) burned
                  -> chunk.upload_mesh()
```

GL = main threaded -> `ctx.*` from worker = segfault on linux, silent corruption on windows

VBO pool: 32 prealloc, 1.5M float each


## meshing

`build_meshjit` @ `terrain.py:1455`. ~1200 line, single njit fn. recompile on change ~= 30s.

vert = `3f pos | 3f norm | 1f ao | 2f uv`. 6 vert/face non-indexed. 
AO baked at mesh time := transparent (water, glass) go in second VBO, back2front, depth write off

extruded -> skip meshing, render @ `world/extruded.py`


## lighting

BFS skylight, njit -> skylight only. packed into AO vert slot

sun = 1 directional uniform. fog + sky color driven by sun pitch


## shaders

`content/shaders/` -> terrain does diffuse * AO * biome tint, fog in frag. 
gamma is stolen from mc console edition, wont link.
animated tile (water, prismarine..) reupload subregion of atlas every frame


## physics

swept AABB, axis-separated. step-up handles stair/slab

```
GRAVITY=-32.0      TERM_V=-78.4       JUMP_V=10.0       MP_SPRINT=1.75
FL_SPEED=12.0      FL_FRIC=0.85
SURF_FRIC=0.50     SURF_ACCEL=0.25    AIR_ACCEL=0.03
```
per-tick coef, fixed rate


## network

custom binary proto over TCP. 1b opcode + LE payload, no length prefix. 30hz server tick, 1 thread/client, port 25250.

block edit: client click -> `BLOCK_CHANGE` -> server validate -> `BLOCK_UPDATE` to everyone. non-local command get forwarded as chat and server handle it.


## saves

only modified voxel hit disk. fresh world is few KB. chunk unload or `SAVE_INTERVAL` trigger flush. numba cache sits in `saves/<world>/cache`

> [!NOTE]
> saves dir set via `config.root` (launcher -> `client/saves/`, server -> `server/saves/`). no junction. `NUMBA_CACHE_DIR` still env-set per world for numba. keep on gitignore


## config

`content/config.py`. knob to touch based on hardware:

```python
RENDER_D          = 10        # chunk radius. 10 ~ 20 across, ~320 blocks.
CHUNK_H           = 128       # chunk height. don't change wo grep.
SEA_LEVEL         = 64
SEED              = 12345
FOV               = 70.0
SENSITIVITY       = 0.15
MOUS_SMOOTH       = 0.5

CHUNK_WORKERS     = 8         # gen pool
CHUNK_PARALLEL    = 32        # in-flight gen futures cap
CHUNK_MESH_PTICK  = 16        # mesh builds / builder iter
CHUNK_UPLD_CAP    = 16        # GL uploads / frame cap

VERTEX_BUFF_POOL_SZ = 32      # prealloc VBOs
VERTEX_BUFF_CAP_SZ  = 1_500_000   # floats / pool VBO

SV_PORT           = 25250
SV_RATE           = 30
SV_MAXONLINE      = 20
```

`RENDER_D > 14` saturates builder. 
`CHUNK_H > 256` breaks several njit fn that pack Y->8b


> [!NOTE]
> requirements.txt over on /content

## known bugs/ things to fix

* Multiplayer random disconnect
* TNT explosion not passing through socket on multiplayer
* Multiplayer player model arm attack missmatch


## license

Public domain project. feel free to change, fork and republish it, give credit.
