import os, sys, time, logging, subprocess, shutil, importlib.util
import pygame

_WIN = sys.platform == "win32"
if _WIN:
    import ctypes

import logformat

from lconst import (
    WIN_W, WIN_H, FPS, GS,
    UI_DIR, CONTENT_DIR, BASE_DIR, SAVES_DIR,
    WINDOW_TITLE,
    WHITE, GRAY, GREEN
)
from ldata    import get_reasourceactive
from lwidgets import nine_slice  # noqa

sys.path.insert(0, UI_DIR)
from bfont import Font

from lscreens import MenuScreen



def setsaves(wname):
    os.makedirs(SAVES_DIR, exist_ok=True)
    cdir = os.path.join(SAVES_DIR, wname, "cache")
    os.makedirs(cdir, exist_ok=True)
    os.environ["NUMBA_CACHE_DIR"] = cdir




class LoadingLog:
    MAX_LINES = 12

    def __init__(self, bfont):
        self.bfont = bfont
        self.lines = []

    def add(self, text, color=WHITE):
        self.lines.append((text, color))
        if len(self.lines) > self.MAX_LINES * 2:
            self.lines = self.lines[-self.MAX_LINES:]
            
            

    def draw(self, surf):
        cx = 5
        cy = WIN_H - 5
        for text, color in reversed(self.lines[-self.MAX_LINES:]):
            txt  = self.bfont.render(text, False, color)
            w, h = txt.get_size()
            pygame.draw.rect(surf, (0, 0, 0, 100), (cx-2, cy-h-2, w+4, h+4))
            surf.blit(txt, (cx, cy - h))
            cy -= h + 2




class onLoadHandler(logging.Handler):
    COLORS = {
        logging.DEBUG:    (150, 150, 150),
        logging.INFO:     (200, 200, 200),
        logging.WARNING:  (255, 200, 50),
        logging.ERROR:    (255, 80,  80),
        logging.CRITICAL: (255, 50,  50),
    }
    

    def __init__(self, log_ui):
        super().__init__(logging.INFO)
        self.log_ui = log_ui
        self.setFormatter(logging.Formatter("%(name)s: %(message)s"))

    def emit(self, record):
        col = self.COLORS.get(record.levelno, (200, 200, 200))
        self.log_ui.add(self.format(record), col)






class Launcher:

    def __init__(self):
        logformat.setup()
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        ico = pygame.image.load('content/icon.ico') 
        pygame.display.set_icon(ico)
        pygame.display.set_caption(WINDOW_TITLE)

        self.loadassets()
        self.running = True
        self.clock   = pygame.time.Clock()
        self._screen = MenuScreen(self)


    def loadassets(self):
        self.bfont   = Font(os.path.join(UI_DIR, "font.png"), scale=GS)
        self.wd_surf = pygame.image.load(os.path.join(UI_DIR, "widgets.png")).convert_alpha()
        self.ss_surf = pygame.image.load(os.path.join(UI_DIR, "server_selection.png")).convert_alpha()

        def opt(fname):
            p = os.path.join(UI_DIR, fname)
            return pygame.image.load(p).convert_alpha() if os.path.isfile(p) else None

        self.ico_surf  = opt("icon.png")
        self.icos_surf = opt("icons.png")
        self.ttle_surf = opt("title.png")

        self.buildbg()


    def buildbg(self):
        src  = pygame.image.load(os.path.join(UI_DIR, "bg.png")).convert()
        ts   = 4 * GS * 16
        tile = pygame.transform.scale(src, (ts, ts))

        dk = pygame.Surface((ts, ts))
        dk.fill((100, 100, 100))
        tile.blit(dk, (0, 0), special_flags=pygame.BLEND_RGB_MULT)

        self.bg = pygame.Surface((WIN_W, WIN_H))
        for x in range(0, WIN_W, ts):
            for y in range(0, WIN_H, ts):
                self.bg.blit(tile, (x, y))

    """
    def buildbg(self):
        src  = pygame.image.load(os.path.join(UI_DIR, "bg.png")).convert()
        self.bg = pygame.transform.scale(src, (WIN_W, WIN_H))
    """


    def setscreen(self, s):
        self._screen = s


    def drawloading(self, log):
        self.screen.blit(self.bg, (0, 0))
        log.draw(self.screen)
        pygame.display.flip()
        pygame.event.pump()



    def bootworld(self, wname, seed=None):
        log = LoadingLog(self.bfont)
        log.add(f"Loading world '{wname}'...", GRAY)
        self.drawloading(log)
        self.rungame(wname=wname, seed=seed, log=log)


    def bootsv(self, address):
        log = LoadingLog(self.bfont)
        log.add(f"Connecting to {address}...", GRAY)
        self.drawloading(log)
        self.rungame(svaddr=address, log=log)



    def rungame(
            self,
            wname="default",
            seed=None,
            svaddr=None,
            log=None
        ):
        setsaves(wname)

        _cwd  = os.getcwd()
        _path = sys.path[:]
        _mods = set(sys.modules)
        sys.path.insert(0, CONTENT_DIR)
        os.chdir(CONTENT_DIR)

        hh = onLoadHandler(log) if log else None
        if hh: logging.root.addHandler(hh)

        try:
            if importlib.util.find_spec('_respath'):
                import _respath
                _respath._setactive(get_reasourceactive())

            from main     import VoxelWorld
            from identity import whoami
            import config
            config.root = SAVES_DIR
            from config import SV_PORT

            if log:
                log.add("Initializing engine...", GRAY)
                self.drawloading(log)

            world = VoxelWorld(
                wname=wname,
                svaddr=svaddr,
                seed=seed,
                managed=True
            )

            if svaddr:
                pts  = svaddr.split(":")
                host = pts[0]
                port = int(pts[1]) if len(pts) > 1 else SV_PORT
                nm   = whoami().get("nm", "Player")
                world.svconnect(host=host, port=port, pname=nm)

                if not (world.netclient and world.netclient.isconn()):
                    world.cleanup()
                    raise RuntimeError(f"Failed to connect to {svaddr}")

                t0   = time.time()
                conn = True
                while time.time() - t0 < 15.0:
                    for i in pygame.event.get():
                        if i.type == pygame.QUIT:
                            world.cleanup()
                            self.running = False
                            return

                    if not (world.netclient and world.netclient.isconn()):
                        conn = False; break

                    if world.is_client: break

                    if log:
                        dots = "." * (1 + int(time.time() * 3) % 3)
                        log.lines[-1] = (f"net: waiting for server data{dots}", GRAY)
                        self.drawloading(log)

                    time.sleep(0.05)

                if not conn or not (world.netclient and world.netclient.isconn()):
                    world.cleanup()
                    raise RuntimeError(f"Connection to {svaddr} lost during handshake")

                if log:
                    log.add("net: connected! starting game...", GREEN)
                    self.drawloading(log)

            _boot_t = time.time()
            # print(_boot_t)
            world.run()

        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"game error: {e}")
            if log:
                log.add(f"ERROR: {e}", (255, 80, 80))
                self.drawloading(log)
                dl = time.time() + 4.0
                while time.time() < dl:
                    for i in pygame.event.get():
                        if i.type in (
                                pygame.QUIT,
                                pygame.KEYDOWN,
                                pygame.MOUSEBUTTONDOWN
                            ): dl = 0

                    time.sleep(0.05)

        finally:
            if hh: logging.root.removeHandler(hh)
            os.chdir(_cwd)
            sys.path[:] = _path
            for i in list(sys.modules):
                if i not in _mods: del sys.modules[i]

        self.restore()
        self._screen = MenuScreen(self)


    def restore(self):
        Font.font_surf = None
        Font.char_ws  = None
        self.screen = pygame.display.set_mode((WIN_W, WIN_H))
        pygame.display.set_caption(WINDOW_TITLE)
        pygame.mouse.set_visible(True)
        pygame.event.set_grab(False)
        self.loadassets()


    def run(self):
        while self.running:
            events = pygame.event.get()

            for i in events:
                if i.type == pygame.QUIT: self.running = False
                

            mx, my = pygame.mouse.get_pos()
            # print(mx, my)
            self._screen.update(mx, my)
            self._screen.onevent(events)
            self.screen.blit(self.bg, (0, 0))
            self._screen.draw(self.screen)
            
            pygame.display.flip()
            self.clock.tick(FPS)

        pygame.quit()



if __name__ == "__main__":
    Launcher().run()
