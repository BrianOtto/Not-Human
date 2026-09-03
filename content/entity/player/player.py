import numpy as np
import pygame
from pygame.locals import *
import math

from engine.camera import Camera
from engine.physics import PhysicsEngine
from config import BREAK_T, RAYCAST_DIST, HURT_T, KNOCK_T, JS_SMOOTHING
from world.blocks import WATER, WATER_FLOWING


class Player:
    def __init__(self, world, pos=None):
        self.world   = world
        self.physics = PhysicsEngine(world)

        if pos is None:
            pos = np.array([0.0, 80.0, 0.0], dtype='f4')
        else:
            pos = np.array(pos, dtype='f4')

        self.pos = pos.copy()
        self.vel = np.array([0.0, 0.0, 0.0], dtype='f4')
        self.knockt = 0.0   # shoved, input doesnt steer for a moment

        self.on_ground = False
        self.gmode  = 1
        self.fly    = True
        self.sprint = False
        self.crouching = False
        self._smthcrouch  = 0.0
        self.world_ready  = False

        self.cmode = 0

        ep    = self.pos.copy()
        ep[1] += self.physics.eye_h
        self.cam = Camera(pos=ep)
        self.eye = ep.copy()

        self.freecam = False
        self.fcmove  = True
        self.fcstick = False
        self.fcam    = None

        self.on_jump    = False
        self.on_toggleflight = False
        self.bob_time   = 0.0
        self.bob_amp    = 0.0
        self.limb_swing = 0.0

        self.ui       = None
        self.last_pos = self.pos.copy()

        self.mtgt = None
        self.mprog = 0.0
        self.swseq = 0
        self.falld = 0.0
        self.hurtt = 0.0

        self.anim_time    = 0.0
        self.is_breaking  = False
        self.is_placing   = False
        self.break_time   = 0.0
        self.break_duration = BREAK_T

        bids     = [1, 2, 3, 12, 6, 7, 8, 14, 11]
        self.inv = [{'id': bid, 'count': 64} for bid in bids]
        self._slot = 0

        self.health     = 20
        self.max_health = 20
        self.hunger     = 20
        self.max_hunger = 20
        self.armor      = 20
        self.max_armor  = 20
        self.air        = 300
        self.max_air    = 300
        self._underwater = True

        self.byaw       = 0.0
        self.headyawoff = 0.0

        self._smooth_r_arm = 0.0
        self._smooth_l_arm = 0.0
        self._smooth_r_leg = 0.0
        self._smooth_l_leg = 0.0
        self._last_dt      = 0.0

        self.orbital_distance = 6.0
        self.orb_yaw      = 0.0
        self.orb_pitch    = 30.0

    def inwater(self):
        bx = int(math.floor(self.pos[0]))
        by = int(math.floor(self.pos[1]))
        bz = int(math.floor(self.pos[2]))
        return self.world.chunker.getblock(bx, by, bz) in (WATER, WATER_FLOWING)

    # ceil(dist - 3)
    def onfall(self):
        if self.fly or self.gmode or self.inwater():
            self.falld = 0.0
            return
        """
        if not self.on_ground:
            dy = self.last_pos[1] - self.pos[1]
            if dy > 0: self.falld += dy
            return
        """

        dy = self.last_pos[1] - self.pos[1]
        if dy > 0: self.falld += dy

        if self.on_ground and self.falld > 0:
            dmg = math.ceil(self.falld - 3.0)
            if dmg > 0: self.hurt(dmg)
            self.falld = 0.0

    def sethealth(self, hp):
        self.health = max(0, min(self.max_health, int(hp)))
        return True

    def sethunger(self, hg):
        self.hunger = max(0, min(self.max_hunger, int(hg)))
        return True

    def knock(self, v):
        self.vel[0] += v[0]
        self.vel[1]  = max(float(self.vel[1]), v[1])
        self.vel[2] += v[2]
        self.knockt  = KNOCK_T
        self.on_ground = False


    def hurt(self, dmg):
        if dmg <= 0: return
        self.health = max(0, self.health - dmg)
        self.hurtt  = HURT_T
        self.world.onhurt(dmg)

    def swing(self, placing=False):
        if placing: self.is_placing  = True
        else:       self.is_breaking = True
        self.break_time = 0.0
        self.swseq      = (self.swseq + 1) & 3

    def setgmode(self, m):
        self.gmode = m
        if m == 0:
            self.fly    = False
            self.vel[1] = 0
            self.mtgt   = None
            self.mprog  = 0.0

    def togglegmode(self):
        self.setgmode(0 if self.gmode else 1)
        return self.gmode

    def toggleflight(self):
        if not self.gmode: return

        self.fly = not self.fly
        if self.fly:
            self.vel[1] = 0
            self.ui.chatmsg("Flight: ON", color=(200, 255, 200))
        else:
            self.ui.chatmsg("Flight: OFF", color=(200, 255, 200))

    def togglecam(self):
        self.cmode = (self.cmode + 1) % 4
        if self.cmode == 3:
            self.orb_yaw   = self.cam.yaw
            self.orb_pitch = 30.0

    def togglefreecam(self):
        self.freecam = not self.freecam
        if self.freecam:
            self.fcam = Camera(pos=self.cam.pos.copy())
            self.fcam.yaw = self.fcam.target_yaw = self.cam.yaw
            self.fcam.pitch = self.fcam.target_pitch = self.cam.pitch
            self.fcam.updatevecs()
            self.fcmove = True
            self.fcstick = False

    def togglefcctrl(self):
        self.fcmove = not self.fcmove

    def togglefcstick(self):
        self.fcstick = not self.fcstick

    def rcam(self):
        return self.fcam if self.freecam else self.cam

    def oninput(self, dt):
        if self.freecam and self.fcmove:
            self.fcam.oninput(dt)
            return

        if pygame.joystick.get_count() > 0:
            joystick = pygame.joystick.Joystick(0)

            jmx = joystick.get_axis(0)
            jmy = joystick.get_axis(1)
        else:
            jmx = 0.0
            jmy = 0.0
            
        keys = pygame.key.get_pressed()

        if keys[K_f]:
            if not self.on_toggleflight:
                self.toggleflight()
                self.on_toggleflight = True
        else:
            self.on_toggleflight = False

        self.sprint = keys[K_LSHIFT]

        if not self.fly:
            self.crouching = keys[K_LCTRL]
        else:
            self.crouching = False

        yr = math.radians(self.cam.yaw)

        fwd = np.array([math.cos(yr), 0.0, math.sin(yr)], dtype='f4')
        fn  = np.linalg.norm(fwd)
        if fn > 0: fwd /= fn

        rgt = np.array([math.cos(yr + math.pi/2), 0.0, math.sin(yr + math.pi/2)], dtype='f4')
        rn  = np.linalg.norm(rgt)
        if rn > 0: rgt /= rn

        md = np.array([0.0, 0.0, 0.0], dtype='f4')

        if keys[K_w] or (jmy >= -1.0 and jmy < -JS_SMOOTHING): md += fwd
        if keys[K_s] or (jmy <= 1.0 and jmy > JS_SMOOTHING): md -= fwd
        if keys[K_a] or (jmx >= -1.0 and jmx < -JS_SMOOTHING): md -= rgt
        if keys[K_d] or (jmx <= 1.0 and jmx > JS_SMOOTHING): md += rgt

        if self.fly:
            if keys[K_SPACE]: md[1] += 1.0
            if keys[K_LCTRL]: md[1] -= 1.0

        ispr = self.sprint and not self.crouching
        # print(md)
        # knock
        if self.knockt <= 0.0:
            self.vel = self.physics.apply_movinput(
                self.vel, md, self.on_ground, self.fly, ispr, dt
            )

            if self.crouching and not self.fly:
                self.vel[0] *= 0.3
                self.vel[2] *= 0.3

        if not self.fly:
            if keys[K_SPACE]:
                if not self.on_jump and self.on_ground:
                    self.vel = self.physics.apply_jump(self.vel, self.on_ground)
                    self.on_jump = True
            else:
                self.on_jump = False

    def update(self, dt):
        self._last_dt  = dt
        _grnd_prev     = self.on_ground
        # t0 = time.perf_counter()

        if not self.world_ready:
            if len(self.world.chunker.chunks) > 0:
                self.world_ready = True

        if not self.world_ready:
            ep    = self.pos.copy()
            ep[1] += self.physics.eye_h
            yr    = math.radians(self.cam.yaw)
            ep[0] += math.cos(yr) * self.physics.eye_f
            ep[2] += math.sin(yr) * self.physics.eye_f
            self.cam.pos = ep
            self.eye = ep.copy()
            return
            
            

        self.last_pos = self.pos.copy()

        self.vel, self.on_ground = self.physics.apply_physics(
            self.pos, self.vel, self.on_ground, self.fly, dt
        )
        # print(self.vel)

        if self.fly:
            self.pos += self.vel * dt
        else:
            mv = self.vel * dt
            np2, am, ghit, _ = self.physics.check_coll(self.pos, mv)
            self.pos = np2

            if ghit:
                self.on_ground = True
                self.vel[1] = 0
            else:
                self.on_ground = self.physics.grounded(self.pos)
                if self.on_ground and self.vel[1] < 0.5:
                    self.vel[1] = 0

            if dt > 0:
                for i in range(3):
                    if abs(mv[i]) > 0.0001 and abs(am[i]) < 0.0001:
                        self.vel[i] = 0

        self.onfall()

        ep   = self.pos.copy()
        coff = 0.125 if self.crouching else 0.0
        ep[1] += self.physics.eye_h - coff
        yr    = math.radians(self.cam.yaw)
        ep[0] += math.cos(yr) * self.physics.eye_f
        ep[2] += math.sin(yr) * self.physics.eye_f
        self.eye = ep.copy()

        speed = math.sqrt(self.vel[0]**2 + self.vel[2]**2)
        ta    = 0.05 if self.on_ground and speed > 0.1 and self.cmode == 0 else 0.0

        if self.on_ground and speed > 0.1 and self.cmode == 0:
            self.bob_time += speed * dt * 1.5

        if speed > 0.1:
            self.limb_swing += speed * dt * 3.0

        if self.cmode != 3:
            # follow head yaw, snap >= 45
            ydiff = self.cam.yaw - self.byaw
            while ydiff >  180: ydiff -= 360
            while ydiff < -180: ydiff += 360
            if speed > 0.1:
                self.byaw += ydiff * min(8.0 * dt, 1.0)
            elif abs(ydiff) > 45.0:
                exc = ydiff - (45.0 if ydiff > 0 else -45.0)
                self.byaw += exc * min(4.0 * dt, 1.0)
            self.headyawoff = self.cam.yaw - self.byaw
            while self.headyawoff >  180: self.headyawoff -= 360
            while self.headyawoff < -180: self.headyawoff += 360
            self.headyawoff = max(-70, min(70, self.headyawoff))

        self.bob_amp += (ta - self.bob_amp) * 10.0 * dt
        
        
        

        if self.cmode == 0 and self.bob_amp > 0.001:
            bob_x = math.sin(self.bob_time) * self.bob_amp
            bob_y = math.sin(self.bob_time * 2.0) * self.bob_amp
            ceil_y = self.pos[1] + self.physics.ph + 0.1
            if self.physics.isblocksolid(self.pos[0], ceil_y, self.pos[2]):
                if bob_y > 0: bob_y *= 0.2
            ep[0] += math.cos(yr) * bob_x
            ep[2] += math.sin(yr) * bob_x
            ep[1] += bob_y

        if self.cmode == 0:
            self.cam.pos = ep
            
            
        elif self.cmode in (1, 2):
            # pull back from wall
            td  = 4.0
            dir = -self.cam.front if self.cmode == 1 else self.cam.front
            ad  = td
            for d in np.arange(0, td, 0.1):
                chk = ep + dir * d
                if self.physics.isblocksolid(int(chk[0]), int(chk[1]), int(chk[2])):
                    ad = max(0.2, d - 0.2);  break
                    
            self.cam.pos = ep + dir * ad
            
            
            
            
            
        elif self.cmode == 3:
            oyr = math.radians(self.orb_yaw)
            opr = math.radians(self.orb_pitch)
            cp  = math.cos(opr)
            corb = np.array([
                -math.cos(oyr) * cp * self.orbital_distance,
                 math.sin(opr) * self.orbital_distance,
                -math.sin(oyr) * cp * self.orbital_distance
            ], dtype='f4')
            
            
            ad   = self.orbital_distance
            cdir = corb / np.linalg.norm(corb)
            
            for d in np.arange(0, self.orbital_distance, 0.1):
                chk = ep + cdir * d
                if self.physics.isblocksolid(int(chk[0]), int(chk[1]), int(chk[2])):
                    ad = max(1.0, d - 0.5);  break
                    
                    
                    
            self.cam.pos = ep + cdir * ad
            ld   = ep - self.cam.pos
            ldst = np.linalg.norm(ld)
            
            if ldst > 0.001:
                ld /= ldst
                self.cam.front = ld
                self.cam.pitch = math.degrees(math.asin(np.clip(ld[1], -1, 1)))
                self.cam.yaw   = math.degrees(math.atan2(ld[2], ld[0]))
                
                

        # drag freecam
        if self.freecam and self.fcstick:
            self.fcam.pos += self.pos - self.last_pos

        self.anim_time += dt
        if self.hurtt  > 0: self.hurtt  -= dt
        if self.knockt > 0: self.knockt -= dt

        self._smthcrouch = 1.0 if self.crouching else 0.0

        if self.is_breaking or self.is_placing:
            self.break_time += dt
            if self.break_time >= self.break_duration:
                self.is_breaking = False
                self.is_placing  = False
                self.break_time  = 0.0

    def animangles(self):
        # shader: left leg NEGATED -> pass SAME val for both legs to get opposition
        # r_arm(part2) = mcmodel leftArm
        # l_arm(part3) = mcmodel rightArm
        RAD2DEG = 180.0 / math.pi

        speed = math.sqrt(self.vel[0]**2 + self.vel[2]**2)
        lsw = self.limb_swing
        lsa = min(speed / 4.3, 1.0) if speed > 0.1 else 0.0

        """
        def animangles(self):
            speed = math.sqrt(self.vel[0]**2 + self.vel[2]**2)
            lsa   = min(speed / 4.3, 1.0) if speed > 0.1 else 0.0
            phase = self.limb_swing * 0.6662
            RAD2DEG = 180.0 / math.pi
            r_arm = math.cos(phase + math.pi) * 2.0 * lsa * 0.5 * RAD2DEG
            l_arm = math.cos(phase)            * 2.0 * lsa * 0.5 * RAD2DEG
            r_leg = math.cos(phase)            * 1.4 * lsa         * RAD2DEG
            return (r_arm, l_arm, r_leg, r_leg, 0.0, 0.0)
        """

        if not self.fly:
            phase = lsw * 0.6662
            r_arm = math.cos(phase + math.pi) * 2.0 * lsa * 0.5 * RAD2DEG
            l_arm = math.cos(phase)            * 2.0 * lsa * 0.5 * RAD2DEG
            r_leg = math.cos(phase)            * 1.4 * lsa * RAD2DEG
            l_leg = r_leg  # shader negates left leg
        else:
            cycle = self.anim_time * 3.0
            r_arm = math.sin(cycle) * 20.0
            l_arm = -math.sin(cycle) * 20.0
            r_leg = math.sin(cycle) * 25.0
            l_leg = r_leg

        r_arm_z = 0.0
        l_arm_z = 0.0

        
        
        # idle sway
        age = self.anim_time * 20.0
        l_arm += math.sin(age * 0.067) * 0.05 * RAD2DEG
        r_arm -= math.sin(age * 0.067) * 0.05 * RAD2DEG
        l_arm_z += (math.cos(age * 0.09) * 0.05 + 0.05) * RAD2DEG
        r_arm_z -= (math.cos(age * 0.09) * 0.05 + 0.05) * RAD2DEG
        
        
        

        
        if self._smthcrouch > 0.01:
            cac = self._smthcrouch * 0.2 * RAD2DEG
            # cac = math.sin(self._smthcrouch * math.pi * 0.5) * 25.0
            r_arm += cac;  l_arm += cac # crouch arm
            
            
            
            
            

        # punch arc 
        # part3 = mcmodel rightArm
        if self.is_breaking or self.is_placing:
            progress = min(self.break_time / self.break_duration, 1.0)
            inv  = 1.0 - progress
            var8 = 1.0 - (inv * inv * inv * inv)   # MC easing
            var9 = math.sin(var8 * math.pi)
            hpr  = math.radians(-self.cam.pitch)
            var10 = math.sin(progress * math.pi) * -(hpr - 0.7) * 0.75
            l_arm   -= (var9 * 1.2 + var10) * RAD2DEG
            l_arm_z += math.sin(progress * math.pi) * -0.4 * RAD2DEG

        # print(r_arm, l_arm, r_leg)
        return (r_arm, l_arm, r_leg, l_leg, r_arm_z, l_arm_z)




    def onmouse(self):
        if self.freecam and self.fcmove:
            self.fcam.onmouse()
            return
        if self.cmode == 3:
            from config import MS_SENSITIVITY
            dx, dy = pygame.mouse.get_rel()
            self.orb_yaw   += dx * MS_SENSITIVITY
            self.orb_pitch += dy * MS_SENSITIVITY
            self.orb_pitch = max(-89.0, min(89.0, self.orb_pitch))
        else:
            self.cam.onmouse()
            
    def onjoystick(self):
            if self.freecam and self.fcmove:
                self.fcam.onjoystick()
                return
            if self.cmode == 3:
                from config import JS_SENSITIVITY

                if pygame.joystick.get_count() > 0:
                    joystick = pygame.joystick.Joystick(0)

                    # look
                    self.orb_yaw += joystick.get_axis(2) * JS_SENSITIVITY
                    self.orb_pitch -= joystick.get_axis(3) * JS_SENSITIVITY
            else:
                self.cam.onjoystick()

    def onscroll(self, y):
        if self.cmode == 3:
            self.orbital_distance = max(2.0, min(20.0, self.orbital_distance - y * 0.5))

    def getpos(self): return self.pos.copy()

    def eyepos(self): return self.eye.copy()
    def getvel(self): return self.vel.copy()
    
    
    
    def chunkpos(self, chunk_size):
        return self.cam.chunkpos(chunk_size)
        

    def teleport(self, pos):
        self.pos = np.array(pos, dtype='f4')
        self.vel = np.array([0.0, 0.0, 0.0], dtype='f4')
        self.falld = 0.0
        ep    = self.pos.copy()
        ep[1] += self.physics.eye_h
        yr    = math.radians(self.cam.yaw)
        ep[0] += math.cos(yr) * self.physics.eye_f
        ep[2] += math.sin(yr) * self.physics.eye_f
        self.cam.pos = ep
        
        

    def setflying(self, fly):
        if fly != self.fly:
            self.toggleflight()
            

    def getsel(self):
        if 0 <= self._slot < 9:
            stack = self.inv.slots[self._slot]
            if stack:
                if stack.item.is_block:
                    return stack.item.itemId
                if stack.item.places_block is not None:
                    return stack.item.places_block
                return None

        """
        elif isinstance(self.inv, list):
            from items.registry import REGISTRY
            if 0 <= self._slot < len(self.inv):
                item = self.inv[self._slot]
                iid  = item.get('id', 1) if isinstance(item, dict) else item
                idef = REGISTRY.get(iid)
                if idef:
                    if idef.is_block: return iid
                    if idef.places_block is not None: return idef.places_block
            return None
        """

        return None

    def targetblock(self, max_dist=RAYCAST_DIST):
        start    = self.pos.copy()
        start[1] += self.physics.eye_h
        yr        = math.radians(self.cam.yaw)
        start[0] += math.cos(yr) * self.physics.eye_f
        start[2] += math.sin(yr) * self.physics.eye_f

        direction = self.cam.front
        step = 0.05
        dist = 0.0
        lb   = None

        while dist < max_dist:
            p     = start + direction * dist
            block = (int(math.floor(p[0])), int(math.floor(p[1])), int(math.floor(p[2])))

            if self.physics.isblocksolid(block[0], block[1], block[2]):
                face = None

                if lb is not None and lb != block:
                    dx = lb[0] - block[0]
                    dy = lb[1] - block[1]
                    dz = lb[2] - block[2]

                    if abs(dx) + abs(dy) + abs(dz) == 1:
                        face = (dx, dy, dz)

                if face is None:
                    ad = (abs(direction[0]), abs(direction[1]), abs(direction[2]))
                    mi = 0
                    if ad[1] > ad[mi]: mi = 1
                    if ad[2] > ad[mi]: mi = 2

                    face = [0, 0, 0]
                    face[mi] = -1 if direction[mi] > 0 else 1
                    face = tuple(face)

                # print(block, face)
                return block, face

            lb   = block
            dist += step

        return None, None

    def placepos(self, block_pos, face):
        if block_pos is None or face is None:
            return None

        px = block_pos[0] + face[0]
        py = block_pos[1] + face[1]
        pz = block_pos[2] + face[2]

        ep    = self.pos.copy()
        ep[1] += self.physics.eye_h

        fy = self.pos[1]
        hy = fy + self.physics.ph

        if (abs(px - ep[0]) < 0.6 and
            abs(pz - ep[2]) < 0.6 and
            py >= fy - 0.2 and py <= hy + 0.2):
            return None

        return (px, py, pz)


"""
def get_lookat(self, max_dist=8.0, step=0.05):
    pos = self.cam.pos.copy()
    d   = self.cam.front
    n   = int(max_dist / step)
    for i in range(n):
        pos += d * step
        bx, by, bz = int(pos[0]), int(pos[1]), int(pos[2])
        if self.physics.isblocksolid(bx, by, bz):
            return (bx, by, bz)
    return None
"""




# shims
Player.position  = property(lambda self: self.pos,       lambda self, v: setattr(self, 'pos', v))
Player.velocity  = property(lambda self: self.vel,       lambda self, v: setattr(self, 'vel', v))
Player.is_flying = property(lambda self: self.fly,       lambda self, v: setattr(self, 'fly', v))
Player.is_sprint = property(lambda self: self.sprint,    lambda self, v: setattr(self, 'sprint', v))
