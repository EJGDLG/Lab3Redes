from __future__ import annotations
from typing import Any, List
class BaseAlgorithm:
    name="base"
    def __init__(self, node_id: str): self.node_id=node_id
    def on_hello_rtt(self, neighbor_id: str, rtt_ms: float): ...
    def on_info(self, from_id: str, payload: Any): ...
    def choose_next_hop(self, dest_id: str) -> str | None: return None
    def build_info_payload(self) -> Any: return None
    def neighbors_updated(self, neighbors: List[str]): ...
