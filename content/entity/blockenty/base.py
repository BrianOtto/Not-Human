class BlockEntity:
    eid = None   # set when the server owns it

    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z
        self.alive = True

    def update(self, dt, world_ctx):
        pass

    def dbgtag(self):
        who = f"#{self.eid}" if self.eid is not None else "local"
        return f"{who} {type(self).__name__} {self.x} {self.y} {self.z}"

    def render(self, manager):
        pass
