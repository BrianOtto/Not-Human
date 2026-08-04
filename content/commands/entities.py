class CommandEntity:
    def __init__(
        self, kind, nm, get_pos,
        source=None, teleport=None, give_item=None,
        set_hp=None, set_hunger=None
    ):
        self.kind      = kind        # player | item | ...
        self.nm        = nm
        self.get_pos   = get_pos
        self.source    = source
        self.teleport  = teleport
        self.give_item = give_item
        self.set_hp     = set_hp
        self.set_hunger = set_hunger

    def pos(self):
        return self.get_pos()
