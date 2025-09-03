from __future__ import annotations
from typing import Dict, List
from .base import BaseAlgorithm
INF = 1e12
class DistanceVector(BaseAlgorithm):
    name="dvr"
    def __init__(self, node_id: str):
        super().__init__(node_id); self.costs: Dict[str,float]={}; self.dv: Dict[str,float]={node_id:0.0}
        self.next_hop: Dict[str,str]={}; self.neighbor_vectors: Dict[str,Dict[str,float]]={}; self.split_horizon_poison=True
    def neighbors_updated(self, neighbors: List[str]):
        for n in list(self.costs.keys()):
            if n not in neighbors: self.costs.pop(n,None); self.neighbor_vectors.pop(n,None)
        for n in neighbors: self.costs.setdefault(n,1.0)
    def on_hello_rtt(self, neighbor_id: str, rtt_ms: float): self.costs[neighbor_id]=max(1.0,rtt_ms)
    def bellman_ford(self):
        updated=False; all_dests=set(self.dv.keys())
        for vec in self.neighbor_vectors.values(): all_dests.update(vec.keys())
        all_dests.add(self.node_id)
        for dst in all_dests:
            if dst==self.node_id:
                if self.dv.get(dst,INF)!=0.0: self.dv[dst]=0.0; self.next_hop.pop(dst,None); updated=True
                continue
            best_cost=INF; best_nh=None
            for n,c_xn in self.costs.items():
                vec_n=self.neighbor_vectors.get(n,{}); d_ny=vec_n.get(dst,INF); cand=c_xn+d_ny
                if cand<best_cost: best_cost=cand; best_nh=n
            if best_cost < self.dv.get(dst,INF)-1e-9 or (best_nh and self.next_hop.get(dst)!=best_nh):
                self.dv[dst]=best_cost; 
                if best_nh: self.next_hop[dst]=best_nh
                updated=True
        return updated
    def build_info_payload(self): return {"kind":"DV","vector":dict(self.dv)}
    def on_info(self, from_id: str, payload):
        if not isinstance(payload,dict) or payload.get("kind")!="DV": return False
        vec=payload.get("vector",{}); self.neighbor_vectors[from_id]=dict(vec); return self.bellman_ford()
    def choose_next_hop(self, dest_id: str) -> str | None: return self.next_hop.get(dest_id)
