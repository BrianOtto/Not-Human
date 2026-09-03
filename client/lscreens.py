import os, sys, math, time, shutil, subprocess, threading
import pygame

from lconst import (
    GS, WIN_W, WIN_H, GUI_W, GUI_H,
    ENTRY_H, ENTRY_PAD, LIST_BOT,
    BTN_H, BTN_Y_NORMAL, BTN_SRC_W, BTN_SRC_H, ICON_H,
    SIGNAL_W, SIGNAL_H, SIGNAL_Y,
    PING_ANIM_X, PING_ANIM_W, PING_ANIM_H, PING_ANIM_Y,
    RESOURCE_DIR, UI_DIR,
    SPLASH_TEXTS, __VERSION__,
    WHITE, GRAY, YELLOW, RED, GREEN, BLACK
)

from lwidgets import Button, Icon, TextInput, ListWidget, nine_slice
from ldata import (
    get_reasourceactive, set_reasourceactive,
    get_available, save_dir, getpname,
    load_servers, save_servers,
    wolrdlist, svping, ms_signal
)


class Screen:
    def __init__(self, launch):
        self.L       = launch
        self.bfont   = launch.bfont
        self.fontIcon = launch.fontIcon
        self.fontIconSolid = launch.fontIconSolid
        self.fontText = launch.fontText
        self.fontTextBold = launch.fontTextBold
        self.fontWidget = launch.fontWidget
        self.fontWidgetBold = launch.fontWidgetBold
        self.widgets = launch.wd_surf
        self.buttons = []
        self.inputs  = []
        self.icons  = []

    def btn_gui(self, gx, gy, gw, text, enabled=True):
        b = Button(gx*GS, gy*GS, gw*GS, BTN_H, text, self.fontWidget, self.widgets, enabled=enabled)
        self.buttons.append(b); return b

    def btn_px(self, x, y, w, text, enabled=True):
        b = Button(x, y, w, BTN_H, text, self.bfont, self.widgets, enabled=enabled)
        self.buttons.append(b); return b

    def _tabnext(self, current):
        if not self.inputs: return
        idx = self.inputs.index(current) if current in self.inputs else -1
        for ti in self.inputs: ti.active = False
        self.inputs[(idx+1) % len(self.inputs)].active = True

    def onevent(self, events): pass

    def update(self, mx, my):
        for btn in self.buttons: btn.update(mx, my)
        for ico in self.icons: ico.update(mx, my)

    def draw(self, surf):
        for btn  in self.buttons: btn.draw(surf)
        for inp in self.inputs:  inp.draw(surf)
        for ico in self.icons:  ico.draw(surf)


class MenuScreen(Screen):
    
    def __init__(self, launch):
        super().__init__(launch)
        # self._splash       = SPLASH_TEXTS[int(time.time()) % len(SPLASH_TEXTS)]
        # self._splash_start = time.time()

        cx = GUI_W // 2; W = 200
        self.btn1   = self.btn_gui(cx - W//2, 95, W, "Singleplayer")
        self.btn2   = self.btn_gui(cx - W//2, 120, W, "Multiplayer")
        # self.btn3   = self.btn_gui(cx - W//2, 186, W, "Resource Packs")
        self.btn4  = self.btn_gui(cx - W//2, 145, W, "Options")
        self.btn5 = self.btn_gui(cx - W//2, 180, W, "Quit Game")

        # TODO - Consolidate the song title draw logic 
        # and turn this into a music player widget
        mpy = WIN_H - ICON_H - 4*GS + 4
        self.musicPlayer = Icon(4*GS, mpy, ICON_H, ICON_H, "\uf04c", "\uf04b", self.fontIconSolid, GRAY, YELLOW)
        self.icons.append(self.musicPlayer)

        pygame.mixer.init()
        pygame.mixer.music.load(os.path.join(UI_DIR, "intro.ogg"));
        pygame.mixer.music.play(-1)
        self.L.music = True
        

    def onevent(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if   self.btn1.clk(mx, my): self.L.setscreen(WorldListScreen(self.L))
                elif self.btn2.clk(mx, my): self.L.setscreen(ServerListScreen(self.L))
                # elif self.btn3.clk(mx, my): self.L.setscreen(ResourcePackScreen(self.L))
                elif self.btn5.clk(mx, my): self.L.running = False
                elif self.musicPlayer.clk(mx, my): self.L.music = not self.L.music
                
                
                

    def draw(self, surf):
        title = self.L.ttle_surf
        
        tw = min(title.get_width(), WIN_W // 2)
        th = int(title.get_height() * tw / title.get_width())
        tx = (WIN_W - tw) // 2
        ty = 16 * GS - 1
        surf.blit(title, (tx, ty + 25))

        """
        sby = ty + th
        tr  = tx + tw

        t      = time.time() - self._splash_start
        wob    = abs(math.sin(t * 2.5))
        sf     = 1.0 + 0.08 * wob
        ss     = self.bfont.render(self._splash, False, YELLOW)
        sw     = int(ss.get_width()  * sf)
        sh     = int(ss.get_height() * sf)
        sc     = pygame.transform.rotate(pygame.transform.scale(ss, (sw, sh)), 15)
        cx     = tr  - 60 * GS
        cy     = sby - 8  * GS + 40
        surf.blit(sc, (cx - sc.get_width()//2, cy - sc.get_height()//2))
        """

        super().draw(surf)

        self._drawplayer(surf)

        songTitle = self.fontText.render("\"Atomic\" by kontraamusic", False, GRAY);
        surf.blit(songTitle, (4*GS + 40, WIN_H - songTitle.get_height() - 4*GS))


    def _drawplayer(self, surf):
        mini = self.L.mini
        sz   = mini.sz
        mcx  = (840 + WIN_W) // 2 
        mcy  = self.btn5.rect.bottom - int(sz * 0.35)
        

        mx, my = pygame.mouse.get_pos()
        nx  = max(-1.0, min(1.0, (mx - mcx) / 260.0))
        ny  = max(-1.0, min(1.0, (my - mcy) / 200.0))
        yaw   = 180.0 + nx * 35.0
        pitch = -ny * 28.0

        nm = getpname()
        t  = self.bfont.render(nm, False, WHITE)
        surf.blit(t, (mcx - t.get_width() // 2, mcy - sz // 2 - t.get_height()))

        ps = mini.render(yaw, pitch)
        surf.blit(ps, (mcx - sz // 2, mcy - sz // 2))


class ResourcePackScreen(Screen):
    def __init__(self, launch):
        super().__init__(launch)
        self.lw = ListWidget(
            self.bfont, launch.ico_surf, launch.ss_surf,
            wd_surf=launch.wd_surf
        )
        self.refresh()
        cx = GUI_W // 2
        uy = GUI_H - 52
        ly = GUI_H - 28
        self.btn_select = self.btn_gui(cx - 154, uy, 150, "Select", enabled=False)
        self.btn_folder = self.btn_gui(cx + 4,   uy, 150, "Open Folder")
        self.btn_done   = self.btn_gui(cx - 75,  ly, 150, "Done")

    def refresh(self):
        self.packs = get_available()
        self.lw.set_items(self.packs)
        active = get_reasourceactive()
        for i, p in enumerate(self.packs):
            if p["folder"] == active:
                self.lw.selected = i
                break

    def _sync(self):
        self.btn_select.enabled = self.lw.get_selected() is not None

    def onevent(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                self.lw._onclick(mx, my)
                self._sync()
                if   self.btn_select.clk(mx, my): self.select()
                elif self.btn_folder.clk(mx, my): self.openf()
                elif self.btn_done.clk(mx, my):   self.L.setscreen(MenuScreen(self.L))

            if e.type == pygame.MOUSEBUTTONUP   and e.button == 1: self.lw.on_release()
            if e.type == pygame.MOUSEWHEEL: self.lw._onscroll(e.y)
            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.L.setscreen(MenuScreen(self.L))

    def select(self):
        sel = self.lw.get_selected()
        if sel: set_reasourceactive(sel["folder"])

    def openf(self):
        os.makedirs(RESOURCE_DIR, exist_ok=True)
        if   sys.platform == 'win32':  os.startfile(RESOURCE_DIR)
        elif sys.platform == 'darwin': subprocess.Popen(['open',     RESOURCE_DIR])
        else:                          subprocess.Popen(['xdg-open', RESOURCE_DIR])

    def update(self, mx, my):
        super().update(mx, my)
        self.lw.update(mx, my)

    def draw(self, surf):
        t = self.bfont.render("Resource Packs", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 8 * GS))
        active = get_reasourceactive()
        self.lw.draw(surf, lambda s, it, x, y, w: self._drawentry(s, it, x, y, w, active))
        super().draw(surf)

    def _drawentry(self, surf, item, x, y, w, active_folder):
        lh  = self.bfont.get_height()
        ty  = y + ENTRY_PAD
        nm  = item["name"]
        act = item["folder"] == active_folder
        if act: nm += "  [Active]"
        surf.blit(self.bfont.render(nm, False, GREEN if act else WHITE), (x, ty))

        if item["description"]:
            surf.blit(self.bfont.render(item["description"], False, GRAY), (x, ty + lh))

        info = f"by {item['author']}"
        if item["version"]: info += f"  v{item['version']}"
        surf.blit(self.bfont.render(info, False, GRAY), (x, ty + lh * 2))




class WorldListScreen(Screen):
    def __init__(self, launch):
        super().__init__(launch)
        self.lw = ListWidget(
            self.bfont, launch.ico_surf, launch.ss_surf,
            wd_surf=launch.wd_surf
        )
        self.refresh()
        cx = GUI_W // 2
        uy = GUI_H - 52
        ly = GUI_H - 28
        self.btn_play     = self.btn_gui(cx - 154, uy, 150, "Play Selected", enabled=False)
        self.btn_create   = self.btn_gui(cx + 4,   uy, 150, "Create New")
        self.btn_edit     = self.btn_gui(cx - 154, ly, 72,  "Edit",      enabled=False)
        self.btn_del      = self.btn_gui(cx - 76,  ly, 72,  "Delete",    enabled=False)
        self.btn_recreate = self.btn_gui(cx + 4,   ly, 72,  "Re-Create", enabled=False)
        self.btn_cancel   = self.btn_gui(cx + 82,  ly, 72,  "Cancel")

    def refresh(self):
        self.worlds = wolrdlist()
        self.lw.set_items(self.worlds)

    def _sync(self):
        sel = self.lw.get_selected() is not None
        for b in (self.btn_play, self.btn_edit, self.btn_del, self.btn_recreate):
            b.enabled = sel

    def onevent(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.lw.ondblclk(mx, my): self.play()
                else: self.lw._onclick(mx, my)
                self._sync()
                if   self.btn_play.clk(mx, my):     self.play()
                elif self.btn_create.clk(mx, my):   self.L.setscreen(CreateWorldScreen(self.L))
                elif self.btn_edit.clk(mx, my):     self.edit()
                elif self.btn_del.clk(mx, my):      self.delete()
                elif self.btn_recreate.clk(mx, my): self.recreate()
                elif self.btn_cancel.clk(mx, my):   self.L.setscreen(MenuScreen(self.L))

            if e.type == pygame.MOUSEBUTTONUP and e.button == 1: self.lw.on_release()
            if e.type == pygame.MOUSEWHEEL: self.lw._onscroll(e.y)

            if e.type == pygame.KEYDOWN:
                if   e.key == pygame.K_ESCAPE: self.L.setscreen(MenuScreen(self.L))
                elif e.key == pygame.K_RETURN and self.lw.get_selected(): self.play()

    def play(self):
        sel = self.lw.get_selected()
        if sel: self.L.bootworld(sel["nm"])

    def edit(self):
        sel = self.lw.get_selected()
        if sel: self.L.setscreen(EditWorldScreen(self.L, sel))

    def delete(self):
        sel = self.lw.get_selected()
        if not sel: return
        self.L.setscreen(ConfirmScreen(
            self.L,
            f"Delete world '{sel['nm']}'?", "This cannot be undone!",
            on_yes=lambda: self._dodel(sel["nm"]),
            on_no =lambda: self.L.setscreen(WorldListScreen(self.L))
        ))

    def _dodel(self, nm):
        p = os.path.join(save_dir(), nm)
        if os.path.isdir(p): shutil.rmtree(p)
        self.L.setscreen(WorldListScreen(self.L))

    def recreate(self):
        sel = self.lw.get_selected()
        if not sel: return
        self.L.setscreen(ConfirmScreen(
            self.L,
            f"Re-create world '{sel['nm']}'?",
            "All data will be deleted and a fresh world created!",
            on_yes=lambda: self._dorec(sel["nm"]),
            on_no =lambda: self.L.setscreen(WorldListScreen(self.L))
        ))

    def _dorec(self, nm):
        p = os.path.join(save_dir(), nm)
        if os.path.isdir(p): shutil.rmtree(p)
        os.makedirs(p, exist_ok=True)
        self.L.setscreen(WorldListScreen(self.L))

    def update(self, mx, my):
        super().update(mx, my)
        self.lw.update(mx, my)

    def draw(self, surf):
        t = self.bfont.render("Select World", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 8 * GS))
        self.lw.draw(surf, self._drawentry)
        super().draw(surf)

    def _drawentry(self, surf, item, x, y, w):
        lh = self.bfont.get_height()
        ty = y + ENTRY_PAD
        surf.blit(self.bfont.render(item["nm"], False, WHITE), (x, ty))
        surf.blit(self.bfont.render(f"{item['nm']}  ({item['size_kb']} KB)", False, GRAY), (x, ty + lh))
        lp = item.get("last_played", "")
        if lp: surf.blit(self.bfont.render(lp, False, GRAY), (x, ty + lh * 2))




class CreateWorldScreen(Screen):
    def __init__(self, launch):
        super().__init__(launch)
        cx = WIN_W // 2; IW = 300 * GS
        self.ti_name = TextInput(
            cx - IW//2, 110*GS, IW, 18*GS, self.bfont,
            self.L.wd_surf, "World Name", "New World"
        )
        self.ti_name.active = True
        self.ti_seed = TextInput(
            cx - IW//2, 160*GS, IW, 18*GS, self.bfont,
            self.L.wd_surf, "Seed (default=12345)"
        )
        self.inputs = [self.ti_name, self.ti_seed]
        gc = GUI_W // 2
        self.btn_create = self.btn_gui(gc - 154, 210, 150, "Create and Play")
        self.btn_cancel = self.btn_gui(gc + 4,   210, 150, "Cancel")

    def onevent(self, events):
        for e in events:
            for ti in self.inputs:
                r = ti.onevent(e)
                if r == "tab":   self._tabnext(ti); break
                if r == "enter": self.create();     return

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if   self.btn_create.clk(mx, my): self.create()
                elif self.btn_cancel.clk(mx, my): self.L.setscreen(WorldListScreen(self.L))

            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.L.setscreen(WorldListScreen(self.L))

    def create(self):
        raw  = self.ti_name.text.strip()
        safe = "".join(c for c in raw if c.isalnum() or c in " _-").strip() or "world"
        sd   = save_dir()
        path = os.path.join(sd, safe); n = 1

        while os.path.exists(path):
            path = os.path.join(sd, f"{safe}_{n}"); n += 1

        safe = os.path.basename(path)
        os.makedirs(path, exist_ok=True)

        st   = self.ti_seed.text.strip()
        seed = int(st) if st.lstrip('-').isdigit() else (hash(st) & 0x7FFFFFFF if st else None)

        self.L.bootworld(safe, seed=seed)

    def draw(self, surf):
        t = self.bfont.render("Create New World", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 60 * GS))
        super().draw(surf)




class EditWorldScreen(Screen):
    def __init__(self, launch, info):
        super().__init__(launch)
        self.info = info
        cx = WIN_W // 2; IW = 300 * GS
        self.ti_name = TextInput(
            cx - IW//2, 140*GS, IW, 18*GS, self.bfont,
            self.L.wd_surf, "World Name", info["nm"]
        )
        self.ti_name.active = True
        self.inputs = [self.ti_name]
        gc = GUI_W // 2
        self.btn_done   = self.btn_gui(gc - 154, 190, 150, "Done")
        self.btn_cancel = self.btn_gui(gc + 4,   190, 150, "Cancel")

    def onevent(self, events):
        for e in events:
            for ti in self.inputs:
                r = ti.onevent(e)
                if r == "enter": self.save(); return

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if   self.btn_done.clk(mx, my):   self.save()
                elif self.btn_cancel.clk(mx, my): self.L.setscreen(WorldListScreen(self.L))

            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.L.setscreen(WorldListScreen(self.L))

    def save(self):
        raw  = self.ti_name.text.strip()
        safe = "".join(c for c in raw if c.isalnum() or c in " _-").strip()
        if safe and safe != self.info["nm"]:
            dst = os.path.join(save_dir(), safe)
            if not os.path.exists(dst): os.rename(self.info["path"], dst)
        self.L.setscreen(WorldListScreen(self.L))

    def draw(self, surf):
        t = self.bfont.render("Edit World", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 80 * GS))
        super().draw(surf)




class ServerListScreen(Screen):
    def __init__(self, launch):
        super().__init__(launch)
        self.servers = load_servers()
        self.lw = ListWidget(
            self.bfont, launch.ico_surf, launch.ss_surf,
            icos_surf=launch.icos_surf, wd_surf=launch.wd_surf
        )
        self.lw.set_items(self.servers)
        cx = GUI_W // 2
        uy = GUI_H - 52; ly = GUI_H - 28
        self.btn_join    = self.btn_gui(cx - 154, uy, 100, "Join Server",    enabled=False)
        self.btn_direct  = self.btn_gui(cx - 50,  uy, 100, "Direct Connect")
        self.btn_add     = self.btn_gui(cx + 54,  uy, 100, "Add Server")
        self.btn_edit    = self.btn_gui(cx - 154, ly, 70,  "Edit",    enabled=False)
        self.btn_del     = self.btn_gui(cx - 74,  ly, 70,  "Delete",  enabled=False)
        self.btn_refresh = self.btn_gui(cx + 4,   ly, 70,  "Refresh")
        self.btn_cancel  = self.btn_gui(cx + 80,  ly, 75,  "Cancel")
        self._last_refresh = 0
        self.refresh(force=True)

    def _sync(self):
        sel = self.lw.get_selected() is not None
        self.btn_join.enabled   = sel
        self.btn_edit.enabled   = sel
        self.btn_del.enabled = sel

    def onevent(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.lw.ondblclk(mx, my):
                    self.join()
                else:
                    r = self.lw._onclick(mx, my)
                    if r == "reorder":
                        self.servers = self.lw.items
                        save_servers([
                            {k: v for k, v in s.items() if k in ("name", "address")}
                            for s in self.servers
                        ])

                self._sync()
                if   self.btn_join.clk(mx, my):    self.join()
                elif self.btn_direct.clk(mx, my):  self.L.setscreen(DirectConnectScreen(self.L))
                elif self.btn_add.clk(mx, my):     self.L.setscreen(AddEditServerScreen(self.L))
                elif self.btn_edit.clk(mx, my):    self.edit()
                elif self.btn_del.clk(mx, my):     self.delete()
                elif self.btn_refresh.clk(mx, my): self.refresh(force=True)
                elif self.btn_cancel.clk(mx, my):  self.L.setscreen(MenuScreen(self.L))

            if e.type == pygame.MOUSEBUTTONUP and e.button == 1: self.lw.on_release()
            if e.type == pygame.MOUSEWHEEL: self.lw._onscroll(e.y)

            if e.type == pygame.KEYDOWN:
                if   e.key == pygame.K_ESCAPE: self.L.setscreen(MenuScreen(self.L))
                elif e.key == pygame.K_RETURN and self.lw.get_selected(): self.join()

    def join(self):
        sel = self.lw.get_selected()
        if sel: self.L.bootsv(sel["address"])

    def edit(self):
        sel = self.lw.get_selected()
        if sel: self.L.setscreen(AddEditServerScreen(self.L, sel, self.lw.selected))

    def delete(self):
        idx = self.lw.selected
        if 0 <= idx < len(self.servers):
            self.servers.pop(idx)
            save_servers(self.servers)
            self.lw.set_items(self.servers)
            self._sync()

    def refresh(self, force=False):
        self._last_refresh = time.time()
        fresh   = load_servers()
        _map = {s.get("address"): s for s in self.servers}
        result  = []

        for srv in fresh:
            old = _map.get(srv.get("address"))
            if old:
                st = old.get("_ping_state", "")
                if st == "pinging" and not force: result.append(old); continue
                if st == "fail"    and not force: result.append(old); continue

            srv["_ping_state"]   = "pinging"
            srv["_ping_attempt"] = 0
            srv["_ping_retries"] = 3 if force else 1
            srv["signal"]        = 5
            srv["players"]       = ""
            srv["status"]        = ""
            threading.Thread(
                target=self._pingone,
                args=(srv, srv["_ping_retries"]),
                daemon=True
            ).start()
            result.append(srv)

        self.servers     = result
        sel              = self.lw.selected
        self.lw.items    = self.servers
        self.lw.selected = sel
        self._sync()

    def _pingone(self, srv, retries=3):
        for a in range(retries):
            srv["_ping_attempt"] = a + 1
            try:
                ok, ms, info = svping(srv.get("address", ""), timeout=2.0)
            except Exception:
                ok, ms, info = False, -1, None

            if ok and info:
                srv["signal"]      = ms_signal(ms)
                srv["players"]     = f"{int(ms)}ms"
                srv["status"]      = info.get("motd", "")
                srv["_ping_state"] = "ok"
                return

            if a < retries - 1: time.sleep(5.0)

        srv["signal"]      = 5
        srv["players"]     = ""
        srv["status"]      = "Can't connect to server"
        srv["_ping_state"] = "fail"

    def update(self, mx, my):
        super().update(mx, my)
        self.lw.update(mx, my)
        if time.time() - self._last_refresh >= 5.0: self.refresh()

    def draw(self, surf):
        t = self.bfont.render("Multiplayer", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 8 * GS))
        self.lw.draw(surf, self._drawentry)
        super().draw(surf)

    def _drawentry(self, surf, item, x, y, w):
        lh = self.bfont.get_height()
        ty = y + ENTRY_PAD
        surf.blit(self.bfont.render(item.get("name", "Server"), False, WHITE), (x, ty))

        ps = item.get("_ping_state", "")

        if ps == "pinging":
            dots = "." * (1 + int(time.time() * 3) % 3)
            surf.blit(self.bfont.render(f"Pinging{dots}", False, GRAY), (x, ty + lh))
        elif ps == "fail":
            surf.blit(self.bfont.render(item.get("status", "Can't connect"), False, RED), (x, ty + lh))
        else:
            for i, ml in enumerate(item.get("status", "").split("\n")[:2]):
                c = GREEN if ps == "ok" else GRAY
                surf.blit(self.bfont.render(ml, False, c), (x, ty + lh * (i + 1)))

        surf.blit(self.bfont.render(item.get("address", ""), False, GRAY), (x, ty + lh * 3))

        rx    = x + w - ENTRY_PAD
        it    = ty
        ibm   = y + ENTRY_H - ENTRY_PAD
        sig_w = 0
        icon_y = it

        if self.lw.icos_surf:
            if ps == "pinging":
                n   = len(PING_ANIM_Y)
                tt  = int(time.time() * 5) % (2 * (n - 1))
                fr  = tt if tt < n else 2*(n-1) - tt
                src = pygame.Rect(PING_ANIM_X, PING_ANIM_Y[fr], PING_ANIM_W, PING_ANIM_H)
                sig_w = PING_ANIM_W * GS
                sig_h = PING_ANIM_H * GS
            else:
                lvl   = min(5, max(0, item.get("signal", 5)))
                src   = pygame.Rect(0, SIGNAL_Y[lvl], SIGNAL_W, SIGNAL_H)
                sig_w = SIGNAL_W * GS
                sig_h = SIGNAL_H * GS

            ic     = self.lw.icos_surf.subsurface(src)
            icon_y = min(it, ibm - sig_h)
            surf.blit(pygame.transform.scale(ic, (sig_w, sig_h)), (rx - sig_w, icon_y))

        if ps == "pinging":
            a  = item.get("_ping_attempt", 0)
            rt = item.get("_ping_retries", 3)
            rt_surf = self.bfont.render(f"({a}/{rt})", False, GRAY)
        elif item.get("players"):
            rt_surf = self.bfont.render(str(item["players"]), False, GRAY)
        else:
            rt_surf = None

        if rt_surf:
            surf.blit(rt_surf, (rx - sig_w - rt_surf.get_width() - 2*GS, icon_y))




class DirectConnectScreen(Screen):
    def __init__(self, launch):
        super().__init__(launch)
        cx = WIN_W // 2; IW = 300 * GS
        self.ti_addr = TextInput(
            cx - IW//2, 150*GS, IW, 18*GS, self.bfont,
            self.L.wd_surf, "Server Address", "localhost:25250"
        )
        self.ti_addr.active = True
        self.inputs = [self.ti_addr]
        gc = GUI_W // 2
        self.btn_join   = self.btn_gui(gc - 154, 200, 150, "Join Server")
        self.btn_cancel = self.btn_gui(gc + 4,   200, 150, "Cancel")

    def onevent(self, events):
        for e in events:
            for ti in self.inputs:
                r = ti.onevent(e)
                if r == "enter": self.join(); return

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if   self.btn_join.clk(mx, my):   self.join()
                elif self.btn_cancel.clk(mx, my): self.L.setscreen(ServerListScreen(self.L))

            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.L.setscreen(ServerListScreen(self.L))

    def join(self):
        addr = self.ti_addr.text.strip()
        if addr: self.L.bootsv(addr)

    def draw(self, surf):
        t = self.bfont.render("Direct Connect", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 90 * GS))
        super().draw(surf)




class AddEditServerScreen(Screen):
    def __init__(self, launch, info=None, idx=-1):
        super().__init__(launch)
        self.idx     = idx
        self.editing = info is not None
        cx = WIN_W // 2; IW = 300 * GS
        self.ti_name = TextInput(
            cx - IW//2, 110*GS, IW, 18*GS, self.bfont,
            self.L.wd_surf, "Server Name",
            info["name"] if info else "Minecraft Server"
        )
        self.ti_name.active = True
        self.ti_addr = TextInput(
            cx - IW//2, 160*GS, IW, 18*GS, self.bfont,
            self.L.wd_surf, "Server Address",
            info["address"] if info else "localhost:25250"
        )
        self.inputs = [self.ti_name, self.ti_addr]
        gc = GUI_W // 2
        self.btn_done   = self.btn_gui(gc - 154, 210, 150, "Done")
        self.btn_cancel = self.btn_gui(gc + 4,   210, 150, "Cancel")

    def onevent(self, events):
        for e in events:
            for ti in self.inputs:
                r = ti.onevent(e)
                if r == "tab":   self._tabnext(ti); break
                if r == "enter": self.save();       return

            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if   self.btn_done.clk(mx, my):   self.save()
                elif self.btn_cancel.clk(mx, my): self.L.setscreen(ServerListScreen(self.L))

            if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                self.L.setscreen(ServerListScreen(self.L))

    def save(self):
        nm      = self.ti_name.text.strip() or "Server"
        addr    = self.ti_addr.text.strip() or "localhost"
        servers = load_servers()
        entry   = {"name": nm, "address": addr}

        if self.editing and 0 <= self.idx < len(servers):
            servers[self.idx] = entry
        else:
            servers.append(entry)

        save_servers(servers)
        self.L.setscreen(ServerListScreen(self.L))

    def draw(self, surf):
        t = self.bfont.render("Edit Server" if self.editing else "Add Server", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 60 * GS))
        super().draw(surf)




class ConfirmScreen(Screen):
    def __init__(self, launch, line1, line2, on_yes, on_no):
        super().__init__(launch)
        self.line1  = line1
        self.line2  = line2
        self.on_yes = on_yes
        self.on_no  = on_no
        cx = GUI_W // 2
        self.btn_yes = self.btn_gui(cx - 104, 210, 100, "Confirm")
        self.btn_no  = self.btn_gui(cx + 4,   210, 100, "Cancel")

    def onevent(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if   self.btn_yes.clk(mx, my): self.on_yes()
                elif self.btn_no.clk(mx, my):  self.on_no()

            if e.type == pygame.KEYDOWN:
                if   e.key == pygame.K_ESCAPE: self.on_no()
                elif e.key == pygame.K_RETURN: self.on_yes()

    def draw(self, surf):
        ov = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 160))
        surf.blit(ov, (0, 0))

        dw, dh = 325*GS, 110*GS
        dx = (WIN_W - dw) // 2
        dy = (WIN_H - dh) // 2

        bg = self.widgets.subsurface(pygame.Rect(0, BTN_Y_NORMAL, BTN_SRC_W, BTN_SRC_H)).copy()
        dk = pygame.Surface((BTN_SRC_W, BTN_SRC_H), pygame.SRCALPHA)
        dk.fill((0, 0, 0, 160))
        bg.blit(dk, (0, 0))
        surf.blit(nine_slice(bg, dw, dh), (dx, dy))

        t1 = self.bfont.render(self.line1, False, YELLOW)
        surf.blit(t1, (dx + (dw - t1.get_width())//2, dy + 15*GS))
        t2 = self.bfont.render(self.line2, False, WHITE)
        surf.blit(t2, (dx + (dw - t2.get_width())//2, dy + 15*GS + t1.get_height() + 6*GS))

        super().draw(surf)


"""
class OptionsScreen(Screen):
    def __init__(self, launch):
        super().__init__(launch)
        cx = GUI_W // 2; W = 200
        self.btn_fov   = self.btn_gui(cx - W//2, 100, W, f"FOV: 90")
        self.btn_rdist = self.btn_gui(cx - W//2, 123, W, f"Render Distance: 8")
        self.btn_sens  = self.btn_gui(cx - W//2, 146, W, f"Sensitivity: 1.0")
        self.btn_done  = self.btn_gui(cx - W//2, 220, W, "Done")

    def onevent(self, events):
        for e in events:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                mx, my = e.pos
                if self.btn_done.clk(mx, my): self.L.setscreen(MenuScreen(self.L))

    def draw(self, surf):
        t = self.bfont.render("Options", False, WHITE)
        surf.blit(t, ((WIN_W - t.get_width()) // 2, 8 * GS))
        super().draw(surf)
"""
