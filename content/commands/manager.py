import numpy as np

from commands.entities  import CommandEntity
from commands.errors    import CommandError, UnknownCommand
from commands.registry  import CommandRegistry
from commands.selectors import resolve_target
from commands.utils     import parse_coord, splitline, try_float
from config import SV_PORT


class CommandContext:
    def __init__(self, world, executor, entities, reply):
        self.world    = world
        self.executor = executor
        self.entities = entities
        self.reply    = reply

    def info (self, m, c=(220, 220, 220)): self.reply(m, c)
    def ok   (self, m): self.reply(m, (200, 255, 200))
    def warn (self, m): self.reply(m, (255, 235, 140))
    def error(self, m): self.reply(m, (255, 150, 150))


def normitem(s):
    return "".join(j for j in s.lower() if j.isalnum())

def hostport(s):
    s = s.strip()
    if ":" not in s: return s, 0
    h, p = s.rsplit(":", 1)
    return h.strip() or "localhost", int(p)

"""
def hostport(s):
    if ":" in s:
        parts = s.split(":")
        return parts[0], int(parts[1])
    return s, 0
"""





class CommandManager:
    def __init__(self):
        self.registry = CommandRegistry()
        self.regbuiltins()


    def regbuiltins(self):
        r = self.registry
        r.register("help", self.cmdhelp, aliases=("?",),
            usage="/help [command]",
            desc="List of commands")

        r.register("tp", self.cmdtp, aliases=("teleport",),
            usage="/tp <x> <y> <z> | /tp <destination> | /tp <targets> <x> <y> <z> | /tp <targets> <destination>",
            desc="Teleport to <coords> or player")

        r.register("give", self.cmdgive,
            usage="/give <targets> <item> [count]",
            desc="Give items to players")

        r.register("time", self.cmdtime,
            usage="/time [query] | /time set <day|noon|night|midnight|ticks> | /time set <deg>deg | /time add <ticks> | /time add <deg>deg",
            desc="Change sun angle (sun_pos)")

        r.register("gamemode", self.cmdgamemode, aliases=("gm",),
            usage="/gamemode <survival|creative|0|1>",
            desc="Set gamemode")

        r.register("server", self.cmdsrv,
            usage="/server start [port] | /server connect <host:port> [name] | /server stop | /server status",
            desc="Manage mulltiplayer server")

        r.register("locatebiome", self.cmdlocbiome, aliases=("findbiome",),
            usage="/locatebiome <biome>",
            desc="Find nearest biome")




    def collectentys(self, world):
        ents  = []
        pname = "Player"
        if world.netclient:
            try: pname = world.netclient.pname or pname
            except Exception: pass
            

        ents.append(CommandEntity(
            kind = "player", nm=pname,
            get_pos   = lambda w=world: w.p.getpos(),
            teleport  = lambda pos, w=world: w.p.teleport(pos),
            give_item = lambda iid, cnt, w=world: w.p.inv.add(iid, cnt),
            source    = world.p))
            
            

        nc = world.netclient
        if nc and nc.isconn():
            try: rp = nc.remoteplayers()
            except Exception: rp = {}
            for _, p in rp.items():
                ents.append(CommandEntity(
                    kind="player", nm=p.nm,
                    get_pos=lambda p=p: p.pos.copy(), source=p))
                    

        itementys = world.itementys
        if itementys is not None:
            for i in list(itementys.items):
                if not i.active: continue
                nm = f"item#{i.entity_id}"
                ents.append(CommandEntity(
                    kind="item", nm=nm,
                    get_pos=lambda i=i: i.pos.copy(), 
                    source=i
                ))
                

        return ents
        
        


    def execute(self, raw_line, world):
        raw = (raw_line or "").strip()
        if not raw.startswith("/"): return False
        line = raw[1:].strip()
        if not line: return True

        toks  = splitline(line)
        if not toks: return True
        cname = toks[0].lower()
        args  = toks[1:]
        #print(cname, args)

        
        loconly = {"server", "gamemode", "gm"}
        nc = world.netclient
        if nc and nc.isconn() and cname not in loconly:
            nc.sendchat(raw)
            return True

        args = self.injtarget(cname, args, world)
        ents = self.collectentys(world)
        exe  = ents[0]
        ctx  = CommandContext(world, exe, ents, world.ui.chatmsg)

        try:
            spec = self.registry.get(cname)
            spec.handler(ctx, args)
        except UnknownCommand as e: ctx.error(str(e))
        except CommandError   as e: ctx.error(str(e))
        except Exception      as e: ctx.error(f"Command failed: {e}")
        return True


    def injtarget(self, cmd, args, world):
        # no selector -> @self
        if not args: return args
        if cmd == "give":
            if args[0].startswith("@"): return args
            from items.registry import REGISTRY
            first = args[0].lower()
            if first.isdigit() or bool(REGISTRY.search(first)):
                return ["@self"] + args
        return args
        
        
        
        

    """
    def _injdefault(self, cmd, args, world):
        return self.injtarget(cmd, args, world)
    """


    def cmdhelp(self, ctx, args):
        if args:
            sp = self.registry.get(args[0].lower())
            if sp.desc:    ctx.info(sp.desc, (255, 255, 200))
            if sp.usage:   ctx.info(f"Usage: {sp.usage}", (200, 200, 255))
            if sp.aliases: ctx.info(f"Aliases: {', '.join(sp.aliases)}", (200, 200, 200))
            return
            
            
        cmds = self.registry.list_commands()
        ctx.info("Commands: " + ", ".join(f"/{i.nm}" for i in cmds), (200, 200, 255))
        ctx.info("Tip: try /help <command>", (200, 200, 200))
        
        
        
        
        


    def cmdtime(self, ctx, args):
        if not args or args[0].lower() in ("query", "get"):
            ctx.ok(f"Sun angle: {ctx.world.sun_angle:.1f}°"); return

        sub = args[0].lower()
        if sub not in ("set", "add"):
            sub, rest = "set", args
        else:
            rest = args[1:]
        if not rest:
            raise CommandError("Usage: /time set <day|noon|night|midnight|ticks> | /time set <deg>deg | /time add <ticks> | /time add <deg>deg")

        raw = rest[0]
        v   = raw.lower()

        kw = {
            "day":   1000,  "noon":     6000,  "sunset":  12000,
            "night": 13000, "midnight": 18000, "sunrise": 23000,
        }

        if v.endswith("deg") or v.endswith("°"):
            v_num = v.replace("°", "")
            v_num = v_num[:-3] if v_num.endswith("deg") else v_num
            num = try_float(v_num)
            if num is None: raise CommandError(f"Invalid degrees value: {raw}")
            deg = float(num)
            
            
        elif v.endswith("ticks"):
            num = try_float(v[:-5])
            if num is None: raise CommandError(f"Invalid ticks value: {raw}")
            deg = (float(num) / 24000.0) * 360.0
            
            
        elif v.endswith("t") and try_float(v[:-1]) is not None:
            deg = (float(v[:-1]) / 24000.0) * 360.0
            
        elif v in kw:
            deg = (float(kw[v]) / 24000.0) * 360.0
            
            
        else:
            num = try_float(v)
            if num is None: raise CommandError(f"Invalid time value: {raw}")
            deg = (float(num) / 24000.0) * 360.0
            
            
            

        if sub == "set": ctx.world.sun_angle  = float(deg) % 360.0
        else:            ctx.world.sun_angle  = (float(ctx.world.sun_angle) + float(deg)) % 360.0
        ctx.ok(f"Sun angle set to {ctx.world.sun_angle:.1f}°")








    def cmdtp(self, ctx, args):
        if not args:
            raise CommandError("Usage: /tp <x> <y> <z> | /tp <destination> | /tp <targets> <x> <y> <z> | /tp <targets> <destination>")

        base = ctx.executor.pos()
        def xyz(a, b, c):
            return np.array([
                parse_coord(a, float(base[0])),
                parse_coord(b, float(base[1])),
                parse_coord(c, float(base[2])),
            ], dtype="f4")
            
            

        n = len(args)

        if n == 3:
            dest = xyz(args[0], args[1], args[2])
            #print(dest)
            if not ctx.executor.teleport: raise CommandError("You cannot be teleported.")

            ctx.executor.teleport(dest)
            ctx.ok(f"Teleported to ({dest[0]:.1f}, {dest[1]:.1f}, {dest[2]:.1f})")
            return
            

        if n == 1:
            dests = resolve_target(args[0], ctx.executor, ctx.entities)
            if not dests: raise CommandError("No destination matched.")
            if not ctx.executor.teleport: raise CommandError("You cannot be teleported.")
            
            dest = dests[0].pos().astype("f4")
            ctx.executor.teleport(dest)
            ctx.ok(f"Teleported to {dests[0].nm}")
            
            return
            

        if n == 4:
            targets = resolve_target(args[0], ctx.executor, ctx.entities)
            dest    = xyz(args[1], args[2], args[3])
            ok, fail = 0, 0
            for i in targets:
                if i.teleport: i.teleport(dest); ok += 1
                else: fail += 1
                
            if ok:   ctx.ok  (f"Teleported {ok} target(s) to ({dest[0]:.1f}, {dest[1]:.1f}, {dest[2]:.1f})")
            if fail: ctx.warn(f"{fail} target(s) could not be teleported (client-side only).")
            
            return
            

        if n == 2:
            targets = resolve_target(args[0], ctx.executor, ctx.entities)
            dests   = resolve_target(args[1], ctx.executor, ctx.entities)
            if not dests: raise CommandError("No destination matched.")
            
            dest = dests[0].pos().astype("f4")
            ok, fail = 0, 0
            for i in targets:
                if i.teleport: i.teleport(dest); ok += 1
                else: fail += 1
                
            if ok:   ctx.ok  (f"Teleported {ok} target(s) to {dests[0].nm}")
            if fail: ctx.warn(f"{fail} target(s) could not be teleported (client-side only).")
            return
            

        raise CommandError("Invalid /tp arguments. Use /help tp")




    def cmdgive(self, ctx, args):
        if len(args) < 2:
            raise CommandError("Usage: /give <targets> <item> [count]")
        from items.registry import REGISTRY

        targets = resolve_target(args[0], ctx.executor, ctx.entities)
        iarg    = args[1]
        count   = 1
        
        
        if len(args) >= 3:
            try:    count = int(args[2])
            except: raise CommandError("Count must be an integer")
            
        if count <= 0: raise CommandError("Count must be > 0")

        iid = None
        if iarg.isdigit():
            iid = int(iarg)
            
        else:
            m = REGISTRY.search(iarg)
            if m: iid = m[0].itemId
            
            

        #print(iid, count)
        if iid is None or not REGISTRY.exists(iid):
            raise CommandError(f"Unknown item: {iarg} (try numeric id or exact name)")

        #if iid not in REGISTRY._by_id: raise CommandError(f"item {iid} not loaded")

        ok, fail = 0, 0
        for i in targets:
            if i.give_item and i.give_item(iid, count): ok += 1
            else: fail += 1
            
        if ok:   ctx.ok  (f"Gave {count}x {REGISTRY.get(iid).nm} to {ok} player(s)")
        if fail: ctx.warn(f"{fail} target(s) could not receive items.")
        
    
    def cmdgamemode(self, ctx, args):
        modes = {"s": 0, "survival": 0, "0": 0, "c": 1, "creative": 1, "1": 1}
        if not args: raise CommandError("Usage: /gamemode <survival|creative|0|1>")

        m = modes.get(args[0].lower())
        if m is None: raise CommandError(f"Unknown gamemode: {args[0]}")

        ctx.world.p.setgmode(m)
        ctx.ok(f"Gamemode set to {'creative' if m else 'survival'}")


    def cmdsrv(self, ctx, args):
        if not args:
            raise CommandError("Usage: /server connect <host:port> [name] | /server disconnect | /server status | /server ping <host:port>")

        sub = args[0].lower()

        if sub == "status":
            nc = ctx.world.netclient
            if nc and nc.isconn(): ctx.ok(f"Connected to {nc.host}:{nc.port} as {nc.pname}")
            else: ctx.info("Not conn (singleplayer)")
            return
            

        if sub in ("disconnect", "stop"):
            ctx.world.svdisconnect()
            ctx.ok("Disconnected from server")
            return
            

        if sub == "connect":
            if len(args) < 2: raise CommandError("Usage: /server connect <host:port> [name]")
            host, port = hostport(args[1])
            if port == 0: port = ctx.world.svport
            nm = args[2] if len(args) >= 3 else "Player"
            ctx.world.svconnect(host, port, nm)
            return
            

        if sub == "ping":
            if len(args) < 2: raise CommandError("Usage: /server ping <host:port>")
            host, port = hostport(args[1])
            if port == 0: port = ctx.world.svport
            
            from network.client import NetworkClient
            info = NetworkClient.svping(host, port)
            
            
            if info: ctx.ok(f"{info['nm']} - {info['motd']} [{info['current_players']}/{info['maxp']}]")
            else: raise CommandError(f"Could not reach {host}:{port}")
            return

        raise CommandError("Unknown subcommand. Use: /server connect | disconnect | status | ping")





    def cmdlocbiome(self, ctx, args):
        BIOMES = {
            "plains":   0,
            "desert":   1,
            "snowy":    2,
            "jungle":   3,
            "badlands": 4,
            "forest":   5,
        }
        if not args:
            raise CommandError(f"Usage: /locatebiome <biome>. Available: {', '.join(BIOMES)}")

        narg = args[0].lower()
        if narg not in BIOMES:
            raise CommandError(f"Unknown biome '{args[0]}'. Available: {', '.join(BIOMES)}")
            

        tid    = BIOMES[narg]
        pos    = ctx.executor.pos()
        px, pz = float(pos[0]), float(pos[2])
        noise_p = ctx.world.chunker.world.noise.p

        from world.terrain import locate_biome
        ctx.info(f"Searching for {narg.capitalize()} biome…")
        fx, fz = locate_biome(px, pz, tid, noise_p)
        if fx == -1.0 and fz == -1.0:
            ctx.warn(f"No {narg.capitalize()} biome found within 3200 blocks.")
            return
            
            
        dist = ((fx - px)**2 + (fz - pz)**2) ** 0.5
        #print(fx, fz, dist)
        ctx.ok(
            f"Nearest {narg.capitalize()} biome at "
            f"({int(fx)}, ~, {int(fz)}), {dist:.0f} blocks away."
        )





















