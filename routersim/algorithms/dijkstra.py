from __future__ import annotations
from typing import Dict
import heapq
class DijkstraStatic:
    name="dijkstra"
    def __init__(self, node_id: str, graph: Dict[str,Dict[str,float]]):
        self.node_id=node_id; self.graph=graph; self.next_hop=self._compute_all_pairs_from(node_id)
    def _compute_all_pairs_from(self, src: str) -> Dict[str,str]:
        dist={v:float('inf') for v in self.graph}; prev={v:None for v in self.graph}; dist[src]=0.0; pq=[(0.0,src)]
        while pq:
            d,u=heapq.heappop(pq)
            if d!=dist[u]: continue
            for v,w in self.graph[u].items():
                nd=d+w
                if nd<dist[v]: dist[v]=nd; prev[v]=u; heapq.heappush(pq,(nd,v))
        nh={}
        for dst in self.graph:
            if dst==src: continue
            cur=dst; p=prev[cur]
            if p is None: continue
            while p!=src:
                cur=p; p=prev[cur]
                if p is None: break
            if p==src: nh[dst]=cur
        return nh
    def choose_next_hop(self, dest_id: str) -> str | None: return self.next_hop.get(dest_id)
