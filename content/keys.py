import pygame
import threading
import time
from pygame.locals import *
from config import SCL_HUD, WIN_W, WIN_H
from entity.blockenty import itemblock
from items.registry import REGISTRY, ItemStack

SCRL_UP = 4
SCRL_DW = 5


def onEvent(w, events):
    for i in events:
        if i.type == QUIT: return False

        if i.type == KEYDOWN and i.key == K_TAB:
            w.tabdown = True
            continue
        if i.type == KEYUP and i.key == K_TAB:
            w.tabdown = False
            continue

        if w.onchat:
            if i.type == KEYDOWN:
                if i.key == K_ESCAPE:
                    w.onchat = False
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    
                    
                elif i.key == K_RETURN or i.key == K_KP_ENTER:
                    if w.ibuff.strip():
                        msg = w.ibuff.strip()
                        
                        if w.commands.execute(msg, w): pass
                        
                        elif w.netclient and w.netclient.isconn():
                            w.netclient.sendchat(msg)
                        else: w.ui.chatmsg(msg)


                    w.ibuff = ""
                    w.onchat = False
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    
                elif i.key == K_BACKSPACE:  
                    w.ibuff = w.ibuff[:-1]
                
            elif i.type == TEXTINPUT:
                w.ibuff += i.text


            continue



        if w.oninv:
            browser = w.ui.invbrwser
            if browser._onsearch:
                if i.type == KEYDOWN:
                    if browser.onkey(i):
                        continue
                        
                elif i.type == TEXTINPUT:
                    if browser.ontext(i.text):
                        continue



        if i.type == KEYUP:
            if i.key == K_t and not w.oninv and not w.onchat:
                w.onchat = True
                w.ibuff  = ""
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                continue

        if i.type == KEYDOWN:
            if i.key == K_t: continue
                
                
            if i.key == K_SLASH and not w.oninv:
                w.onchat = True
                w.ibuff = "/"
                pygame.event.set_grab(False)
                pygame.mouse.set_visible(True)
                continue
                
                

            if i.key == K_ESCAPE:
                if w.oninv:
                    w.oninv = False
                    w.ui.invbrwser._onsearch = False
                    w.ui.invbrwser.query = ""
                    w.ui.invbrwser.refresh()
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)
                    
                else:
                    grabbed = pygame.event.get_grab()
                    
                    if not grabbed: return False
                    else:
                        pygame.event.set_grab(False)
                        pygame.mouse.set_visible(True)

            elif i.key == K_F1 and not w.oninv:
                new = not w.showhud
                w.showhud   = new
                w.showdebug = new

            elif i.key == K_F2:
                pygame.image.save(w.screen, f"shot_{int(time.time())}.png")

            elif i.key == K_F3 and not w.oninv:
                w.showborder = not w.showborder
                w.ui.chatmsg(f"Chunk Borders: {'ON' if w.showborder else 'OFF'}", color=(200, 200, 255))

            elif i.key == K_F4 and not w.oninv:
                enabled = w.gamma_shader.toggle()
                w.ui.chatmsg(f"Gamma: {'ON' if enabled else 'OFF'}", color=(255, 255, 150))

            elif i.key == K_F5 and not w.oninv:
                if pygame.key.get_mods() & KMOD_SHIFT:
                    w.p.togglefreecam()
                    w.ui.chatmsg(f"Freecam: {'ON' if w.p.freecam else 'OFF'}", color=(200, 200, 255))
                else:
                    w.p.togglecam()
                    modes = ["First", "Third Back", "Third Front", "Orbital"]
                    w.ui.chatmsg(f"Camera: {modes[w.p.cmode]}", color=(200, 200, 255))

            elif i.key == K_c and w.p.freecam and not w.oninv:
                w.p.togglefcctrl()
                w.ui.chatmsg(f"Freecam control: {'camera' if w.p.fcmove else 'player'}", color=(200, 200, 255))

            elif i.key == K_F11 and not w.oninv:
                w._fs = not w._fs
                pygame.display.toggle_fullscreen()
                sw, sh       = pygame.display.get_window_size()
                w._scrw, w._scrh = sw, sh
                w.ctx.viewport   = (0, 0, sw, sh)
                if w.gamma_shader: w.gamma_shader.resize(sw, sh)
                w.ui.resize(sw, sh)
                w.hud.resize(sw, sh)

            elif i.key == K_p and not w.oninv:
                w.showborder = not w.showborder
                w.ui.chatmsg(f"Chunk Borders: {'ON' if w.showborder else 'OFF'}", color=(200, 200, 255))

            elif i.key == K_e:
                if w.oninv and w.ui.invbrwser._onsearch: continue
                w.oninv = not w.oninv
                if w.oninv:
                    w.p.vel[0] = 0.0
                    w.p.vel[2] = 0.0
                    pygame.event.set_grab(False)
                    pygame.mouse.set_visible(True)
                else:
                    w.ui.invbrwser._onsearch = False
                    w.ui.invbrwser.query = ""
                    w.ui.invbrwser.refresh()
                    pygame.event.set_grab(True)
                    pygame.mouse.set_visible(False)

            elif i.key == K_n and w.oninv: w.ui.invbrwser.prev_page()
            elif i.key == K_m and w.oninv: w.ui.invbrwser.next_page()

            elif K_1 <= i.key <= K_9: w.p._slot = i.key - K_1

            elif i.key == K_DELETE:
                mods = pygame.key.get_mods()

                if (mods & KMOD_SHIFT) and (mods & KMOD_CTRL):
                    w.p.inv.clear()
                    w.ui.chatmsg("Inventory cleared", color=(255, 180, 180))

                elif w.oninv:
                    hvr = w.p.inv._hslot
                    if hvr >= 0: w.p.inv.slots[hvr] = None

            elif i.key == K_q:
                ictrl = pygame.key.get_mods() & KMOD_CTRL
                
                if w.oninv:
                    
                    hvr = w.p.inv._hslot
                    
                    if hvr >= 0:
                        
                        si = w.p.inv.slots[hvr]
                        if si:
                            
                            dc = si.count if ictrl else 1
                            iid, cnt = w.p.inv.drop(hvr, dc)
                            
                            if iid is not None:
                                eye = w.p.eyepos()
                                td  = w.p.cam.front.copy()
                                pos = eye + td * 0.5
                                
                                
                                if w.netclient and w.netclient.isconn():
                                    vel = td * 3.0
                                    vel[1] += 2.0
                                    w.netclient.senddrop(iid, cnt, pos, vel)
                                    
                                else: w.itementys.spawn(iid, cnt, pos, td)
                
                else:
                    
                    
                    slot = w.p._slot
                    si   = w.p.inv.slots[slot]
                    
                    if si:
                        dc = si.count if ictrl else 1
                        iid, cnt = w.p.inv.drop(slot, dc)
                        
                        if iid is not None:
                            eye = w.p.eyepos()
                            td  = w.p.cam.front.copy()
                            pos = eye + td * 0.5
                            
                            if w.netclient and w.netclient.isconn():
                                vel = td * 3.0
                                vel[1] += 2.0
                                w.netclient.senddrop(iid, cnt, pos, vel)
                                
                            else: w.itementys.spawn(iid, cnt, pos, td)
                            
                            
                            

        elif i.type == MOUSEBUTTONDOWN:
            if w.oninv:
                mx, my  = pygame.mouse.get_pos()
                scale   = SCL_HUD
                ww, wh  = 176 * scale, 166 * scale
                ix, iy  = (WIN_W - ww) // 2, (WIN_H - wh) // 2
                browser = w.ui.invbrwser
                ctrl    = pygame.key.get_mods() & KMOD_CTRL
                
                if browser.onclick(mx, my, i.button, ctrl):
                    if browser._heldstack:
                        
                        w.p.inv._held = browser._heldstack
                        browser._heldstack = None
                        
                        
                        
                        
                else:
                    clk = w.p.inv.onclick(mx, my, ix, iy, scale, i.button)
                    
                    if not clk and w.p.inv._held:
                        held = w.p.inv._held
                        w.p.inv._held = None
                        eye = w.p.eyepos()
                        td  = w.p.cam.front.copy()
                        pos = eye + td * 0.5

                        if w.netclient and w.netclient.isconn():
                            vel = td * 3.0
                            vel[1] += 2.0
                            w.netclient.senddrop(held.item.itemId, held.count, pos, vel)

                        else: w.itementys.spawn(held.item.itemId, held.count, pos, td)
                        
                        
                        
                        

            elif pygame.event.get_grab():
                if i.button == 1:
                    tb, face = w.p.targetblock(5.0)
                    
                    
                    if tb:
                        
                        bx, by, bz = tb
                        bt = w.chunker.getblock(bx, by, bz)
                        w.p.is_breaking = True
                        w.p.break_time  = 0.0

                        # fuckass redstonbe
                        from world.blocks import REDSTONE_WIRE
                        if bt == REDSTONE_WIRE:
                            w.render_extruded.rm_block(bx, by, bz)
                            
                        w.chunker.breakblock(bx, by, bz)
                        
                        
                        if bt and bt != 0:
                            w.particles.spawn(bx, by, bz, bt)
                            
                            

                        if w.netclient and w.netclient.isconn():
                            w.netclient.sendchange(bx, by, bz, 0)
                            
                            
                    else:
                        w.p.is_breaking = True
                        w.p.break_time  = 0.0
                        
                        
                        
                        

                elif i.button == 3:
                    tb, face = w.p.targetblock(5.0)
                    
                    if tb:
                        pp = w.p.placepos(tb, face)
                        if pp:
                            px, py, pz = pp
                            bt = w.p.getsel()
                            
                            if bt is not None:
                                w.p.is_placing = True
                                w.p.break_time = 0.0
                                _facig = w.bakefacing(bt, face)
                                w.chunker.placeblock(px, py, pz, bt=bt, facing=_facig)

                                from world.blocks import REDSTONE_WIRE
                                
                                if bt == REDSTONE_WIRE:
                                    w.render_extruded.add_block(px, py, pz, bt)
                                    
                                    

                                if w.netclient and w.netclient.isconn():
                                    from world.blockstate import BLOCK_ID_MASK, STATE_SHIFT, PLAYER_PLACED_FLAG
                                    pkd = (bt & BLOCK_ID_MASK) | (_facig << STATE_SHIFT) | PLAYER_PLACED_FLAG
                                    w.netclient.sendchange(px, py, pz, pkd)
                                    
                                    
                                    

                        # TODO
                        # item-block interaction
                        # TODO: only got tnt now, make rest on next rlease
                        _stack = w.getstack()
                        if _stack and not _stack.item.is_block:
                            
                            bx, by, bz = tb
                            tid = w.chunker.getblock(bx, by, bz)
                            
                            if tid:
                                hand = itemblock(_stack.item.itemId, tid)
                                if hand: hand(w.blockentys, bx, by, bz, _stack, w)

                elif i.button == 2:
                    tb, face = w.p.targetblock(5.0)

                    if tb:
                        bx, by, bz = tb
                        bt = w.chunker.getblock(bx, by, bz)

                        if bt and REGISTRY.exists(bt):
                            idef = REGISTRY.get(bt)
                            w.p.inv.slots[w.p._slot] = ItemStack(idef, idef.max_stack)

                elif i.button == 4:
                    if w.oninv: w.ui.invbrwser.onscroll(1)
                    else: w.p._slot = (w.p._slot - 1) % 9

                elif i.button == 5:
                    if w.oninv: w.ui.invbrwser.onscroll(-1)
                    else: w.p._slot = (w.p._slot + 1) % 9





    return True


















