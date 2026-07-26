import pygame
from items.registry import REGISTRY, ItemStack


class Inventory:
    def __init__(self, size=36):
        self.size   = size
        self.slots  = [None] * size
        self._held  = None
        self._hslot = -1
        self.slotsz = 18

        self.spos = []
        sx = 8

        for i in range(9):
            self.spos.append((sx + i * 18, 142))

        for row in range(3):
            for col in range(9):
                self.spos.append((sx + col * 18, 84 + row * 18))
                
                
                
                

    def updatehov(self, mx, my, inv_x, inv_y, scale):
        lx = (mx - inv_x) / scale
        ly = (my - inv_y) / scale

        self._hslot = -1
        for i, (sx, sy) in enumerate(self.spos):
            if sx <= lx < sx + 18 and sy <= ly < sy + 18:
                self._hslot = i
                break
                
                

    def hovitem(self):
        if 0 <= self._hslot < self.size:
            return self.slots[self._hslot]
        return None
        
        

    def add(self, itemId, count=1):
        rem  = count
        idef = REGISTRY.get(itemId)
        if not idef:
            return False

        for i, j in enumerate(self.slots):
            if j and j.item.itemId == itemId:
                if not j.isfull():
                    rem = j.add(rem)
                    if rem == 0:
                        return True

        if rem > 0:
            for i, j in enumerate(self.slots):
                if j is None:
                    ns = ItemStack(idef, count=rem)
                    
                    if rem > idef.max_stack:
                        ns.count = idef.max_stack
                        rem -= idef.max_stack
                        self.slots[i] = ns
                        
                    else:
                        self.slots[i] = ns
                        rem = 0
                        return True

        return rem == 0
        
        
        
        

    def remove(self, si, count=1):
        if 0 <= si < self.size and self.slots[si]:
            stack = self.slots[si]
            stack.count -= count
            if stack.count <= 0:
                self.slots[si] = None
                
            return True
            
        return False

    def clear(self):
        self.slots = [None] * self.size
        self._held = None

    def drop(self, si, count=1):
        if 0 <= si < self.size and self.slots[si]:
            stack  = self.slots[si]
            itemId = stack.item.itemId
            td     = min(count, stack.count)
            stack.count -= td
            if stack.count <= 0:
                self.slots[si] = None
                
            return (itemId, td)
            
        return (None, 0)
        
        
        
        

    def onclick(self, mx, my, inv_x, inv_y, scale, button):
        if self._hslot >= 0:
            self.slotclick(self._hslot, button)
            return True

        lx = (mx - inv_x) / scale
        ly = (my - inv_y) / scale

        for i, (sx, sy) in enumerate(self.spos):
            if sx <= lx < sx + 18 and sy <= ly < sy + 18:
                self.slotclick(i, button)
                return True

        return False
        
        
        
        

    def slotclick(self, si, button):
        ss  = self.slots[si]
        cur = self._held

        if button == 1:
            if cur is None:
                if ss is not None:
                    self._held = ss
                    self.slots[si] = None
                    
                    
            else:
                if ss is None:
                    self.slots[si] = cur
                    self._held = None
                elif ss.item.itemId == cur.item.itemId:
                    rem = ss.add(cur.count)
                    
                    if rem > 0: cur.count = rem
                    else: self._held = None
                    
                    
                    
                else:
                    self.slots[si] = cur
                    self._held = ss
                    
                    
                    
                    
                    

        elif button == 3:
            if cur is None:
                if ss is not None:
                    if ss.count == 1:
                        self._held = ss
                        self.slots[si] = None
                        
                    else:
                        tt = (ss.count + 1) // 2
                        ns = ItemStack(ss.item, tt)
                        ss.count -= tt
                        self._held = ns
                        if ss.count <= 0:
                            self.slots[si] = None
                            
                            
                            
                            
            else:
                if ss is None:
                    self.slots[si] = ItemStack(cur.item, 1)
                    cur.count -= 1
                    if cur.count <= 0:
                        self._held = None
                        
                        
                elif ss.item.itemId == cur.item.itemId:
                    if not ss.isfull():
                        ss.count += 1
                        cur.count -= 1
                        if cur.count <= 0:
                            self._held = None
                            
                            
                else:
                    self.slots[si] = cur
                    self._held = ss



















