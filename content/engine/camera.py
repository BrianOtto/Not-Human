
import numpy as np
import pygame
from pygame.locals import *
import math
from pyrr import Matrix44

from config import (
    FOV, N_PLANE, F_PLANE, MS_SENSITIVITY, MS_SMOOTHING, JS_SENSITIVITY, JS_SMOOTHING,
    WIN_W, WIN_H
)


class Camera:
    def __init__(self, pos=None):
        self.pos   = pos if pos is not None else np.array([0.0, 80.0, 0.0], dtype='f4')
        self.front = np.array([0.0, 0.0, -1.0], dtype='f4')
        self.up    = np.array([0.0, 1.0,  0.0], dtype='f4')

        self.yaw   = -90.0
        self.pitch = -20.0

        self.target_yaw   = self.yaw
        self.target_pitch = self.pitch

        self._proj = None

        self.updatevecs()
        
        

    def updatevecs(self):
        front = np.array([
            math.cos(math.radians(self.yaw)) * math.cos(math.radians(self.pitch)),
            math.sin(math.radians(self.pitch)),
            math.sin(math.radians(self.yaw)) * math.cos(math.radians(self.pitch))
        ], dtype='f4')
        self.front = front / np.linalg.norm(front)
        
        

    def mvpmat(self, inverted=False):
        # inverted=True : flip view dir
        target = self.pos - self.front if inverted else self.pos + self.front
        view   = Matrix44.look_at(self.pos, target, self.up)

        if self._proj is None:
            self._proj = Matrix44.perspective_projection(
                FOV, WIN_W / WIN_H, N_PLANE, F_PLANE
            )

        return self._proj * view
        
        
        
        
        

    def invalidproj(self):
        self._proj = None

    def oninput(self, dt):
        if pygame.joystick.get_init():
            joystick = pygame.joystick.Joystick(0)

            jmx = joystick.get_axis(0)
            jmy = joystick.get_axis(1)
        else:
            jmx = 0.0
            jmy = 0.0
            
        keys  = pygame.key.get_pressed()
        spd   = 25.0 * dt
        right = np.cross(self.front, self.up)
        right = right / np.linalg.norm(right)

        if keys[K_LSHIFT] and keys[K_w]: spd *= 3.0

        if keys[K_w] or (jmy > -1.0 and jmy < -JS_SMOOTHING): self.pos += self.front * spd
        if keys[K_s] or (jmy < 1.0 and jmy > JS_SMOOTHING): self.pos -= self.front * spd
        if keys[K_a] or (jmx > -1.0 and jmx < -JS_SMOOTHING): self.pos -= right * spd
        if keys[K_d] or (jmx < 1.0 and jmx > JS_SMOOTHING): self.pos += right * spd
        if keys[K_SPACE]: self.pos[1] += spd
        if keys[K_LCTRL]: self.pos[1] -= spd

    def onmouse(self):
        dx, dy = pygame.mouse.get_rel()

        self.target_yaw   +=  dx * MS_SENSITIVITY
        self.target_pitch  = max(-89.0, min(89.0, self.target_pitch - dy * MS_SENSITIVITY))

        sf = 1.0 - MS_SMOOTHING
        self.yaw   += (self.target_yaw   - self.yaw)   * sf
        self.pitch += (self.target_pitch - self.pitch) * sf

        self.updatevecs()

    def onjoystick(self):
            # left axis movement is handled in oninput()

            if pygame.joystick.get_init():
                joystick = pygame.joystick.Joystick(0)

                # TODO: detect controller type and switch
                jvx = joystick.get_axis(2)
                jvy = joystick.get_axis(3)

                # look up (-1) / down (1)
                if abs(jvy) > JS_SMOOTHING:
                    self.target_pitch -= jvy * JS_SENSITIVITY

                # look left (-1) / right (1)
                if abs(jvx) > JS_SMOOTHING:
                    self.target_yaw += jvx * JS_SENSITIVITY
    
                self.pitch += (self.target_pitch - self.pitch)
                self.yaw += (self.target_yaw - self.yaw)
        
                self.updatevecs()
    
    def chunkpos(self, chunk_sz):
        return (
            int(self.pos[0] // chunk_sz), 
            int(self.pos[2] // chunk_sz)
        )

















