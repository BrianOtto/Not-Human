MOVE = 1
LOOK = 2




class Goal:
    prio  = 10 # fav lower
    slots = 0

    def canstart(self, e, w): return False
    def running(self, e, w):  return self.canstart(e, w)
    def start(self, e, w):    pass
    def stop(self, e, w):     pass
    def tick(self, e, w, dt): pass




class Controller:
    def __init__(self, goals=[]):
        self.goals  = sorted(goals, key=lambda g: g.prio)
        self.active = []


        


    def tick(self, e, w, dt):
        used = 0



        for g in self.goals:
            on = g in self.active

            # better goal already in
            if used & g.slots:
                if on:
                    g.stop(e, w)
                    self.active.remove(g)
                continue


            ok = g.running(e, w) if on else g.canstart(e, w)
            if not ok:
                if on:
                    g.stop(e, w)
                    self.active.remove(g)
                continue

            if not on:
                g.start(e, w)
                self.active.append(g)

            used |= g.slots



        for g in list(self.active):
            g.tick(e, w, dt)


    def names(self):
        return [type(g).__name__.lower() for g in self.active]














