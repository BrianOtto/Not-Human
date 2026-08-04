import os
import random
import pygame
import numpy as np
import _respath


HEAR_DIST = 24.0


class SoundManager:
    def __init__(self):
        self.snds = {}
        self.ok   = False

        
        if pygame.mixer.get_init(): pygame.mixer.quit()
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(16)
        self.ok = True

        d = _respath.dir_sounds()
        for i in sorted(os.listdir(d)):
            if not i.endswith(".mp3"): continue
            self.snds[i[:-4]] = pygame.mixer.Sound(os.path.join(d, i))


    def get(self, nm):
        return self.snds.get(nm)


    def play(self, nm, vol=1.0):
        if not self.ok: return
        s = self.snds.get(nm)
        if not s: return

        ch = pygame.mixer.find_channel(True)
        ch.set_volume(max(0.0, min(1.0, vol)))
        ch.play(s)


    def playrand(self, nms, vol=1.0):
        self.play(random.choice(nms), vol)


    # linear rolloff
    def playat(self, nm, pos, lpos, vol=1.0):
        d = float(np.linalg.norm(np.asarray(pos, dtype='f4') - np.asarray(lpos, dtype='f4')))
        if d >= HEAR_DIST: return
        self.play(nm, vol * (1.0 - d / HEAR_DIST))


    def playrandat(self, nms, pos, lpos, vol=1.0):
        self.playat(random.choice(nms), pos, lpos, vol)


    def release(self):
        self.snds.clear()
        pygame.mixer.quit()
        self.ok = False




SND_HURT = "classic_hurt"
