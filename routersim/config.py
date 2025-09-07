from __future__ import annotations
import json
from typing import Dict, List
class TopologyConfig:
    def __init__(self, neighbors: Dict[str, List[str]]): self.neighbors=neighbors
    @staticmethod
    def load(path: str) -> "TopologyConfig":
        data=json.load(open(path,"r",encoding="utf-8")); assert data["type"]=="topo"; return TopologyConfig(neighbors=data["config"])
    def neighbors_of(self, node_id: str) -> List[str]: return list(self.neighbors.get(node_id,[]))
class NamesConfig:
    def __init__(self, names: Dict[str,str]): self.names=names
    @staticmethod
    def load(path: str) -> "NamesConfig":
        data=json.load(open(path,"r",encoding="utf-8")); assert data["type"]=="names"; return NamesConfig(names=data["config"])
    def name_of(self, node_id: str) -> str: return self.names.get(node_id,node_id)
    def all_ids(self): return list(self.names.keys())
