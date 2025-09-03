from __future__ import annotations
from typing import Dict, List, Tuple
import heapq, time
from .base import BaseAlgorithm
class LinkState(BaseAlgorithm):
    name="lsr"
    def __init__(self, node_id: str):
        super().__init__(node_id); self.seq=0; self.lsdb: Dict[str,Dict[str,float]]={}; self.seen_lsp: Dict[Tuple[str,int],float]={}
        self.costs: Dict[str,float]={}; self.next_hop: Dict[str,str]={}
    def on_hello_rtt(self, neighbor_id: str, rtt_ms: float): self.costs[neighbor_id]=max(1.0,rtt_ms)
    def neighbors_updated(self, neighbors: List[str]):
        for n in list(self.costs.keys()):
            if n not in neighbors: self.costs.pop(n,None)
        for n in neighbors: self.costs.setdefault(n,1.0)
    def build_info_payload(self):
        self.seq+=1; return {"kind":"LSP","origin":self.node_id,"seq":self.seq,"links":dict(self.costs)}
    def on_info(self, from_id: str, payload):
        if not isinstance(payload,dict) or payload.get("kind")!="LSP": return False,[]
        origin=payload["origin"]; seq=payload["seq"]; key=(origin,seq)
        if key in self.seen_lsp: return False,[]
        self.seen_lsp[key]=time.time(); self.lsdb[origin]=dict(payload.get("links",{})); self._recompute(); return True,[]
    def _recompute(self):
        graph: Dict[str,Dict[str,float]]={}
        for u,nbrs in self.lsdb.items():
            graph.setdefault(u,{})
            for v,w in nbrs.items():
                graph[u][v]=float(w); graph.setdefault(v,{}); graph[v].setdefault(u,float(w))
        graph.setdefault(self.node_id,{})
        for v,w in self.costs.items():
            graph[self.node_id][v]=float(w); graph.setdefault(v,{}); graph[v].setdefault(self.node_id,float(w))
        src=self.node_id; dist={v:float('inf') for v in graph}; prev={v:None for v in graph}; dist[src]=0.0
        pq=[(0.0,src)]
        while pq:
            d,u=heapq.heappop(pq)
            if d!=dist[u]: continue
            for v,w in graph[u].items():
                nd=d+w
                if nd<dist[v]: dist[v]=nd; prev[v]=u; heapq.heappush(pq,(nd,v))
        nh={}
        for dst in graph:
            if dst==src: continue
            cur=dst; p=prev[cur]
            if p is None: continue
            while p!=src:
                cur=p; p=prev[cur]
                if p is None: break
            if p==src: nh[dst]=cur
        self.next_hop=nh
    def choose_next_hop(self, dest_id: str) -> str | None: return self.next_hop.get(dest_id)
