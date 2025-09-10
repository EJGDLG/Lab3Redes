from __future__ import annotations
from .base import BaseAlgorithm
class Flooding(BaseAlgorithm):
    name="flooding"
    def __init__(self, node_id: str):
        super().__init__(node_id); self.seen=set()
    def seen_before(self, msg_id: str) -> bool:
        if msg_id in self.seen: return True
        self.seen.add(msg_id)
        if len(self.seen)>10000: self.seen=set(list(self.seen)[-5000:])
        return False
    def choose_next_hop(self, dest_id: str) -> str | None: return None
