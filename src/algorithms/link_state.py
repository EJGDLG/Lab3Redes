from typing import Dict, Any
from .dijkstra import dijkstra

class LinkState:
    def __init__(self, node_id):
        self.node_id = node_id
        self.seq = 0
        # database of LSPs: lspdb[src] = {"seq": int, "links": {neigh:cost,...}}
        self.lspdb: Dict[str, Dict[str, Any]] = {}

    def build_lsp(self, local_links: Dict[str,int]) -> Dict[str, Any]:
        self.seq += 1
        return {"src": self.node_id, "seq": self.seq, "links": dict(local_links)}

    def ingest_lsp(self, lsp: Dict[str,Any]) -> bool:
        src = lsp["src"]; seq = lsp["seq"]
        cur = self.lspdb.get(src)
        if cur is None or seq > cur["seq"]:
            self.lspdb[src] = {"seq": seq, "links": dict(lsp["links"])}
            return True
        return False

    def compute_spf(self):
        # Build graph
        graph = {}
        for n, rec in self.lspdb.items():
            graph.setdefault(n, {})
            for m,w in rec["links"].items():
                graph.setdefault(m, {})
                graph[n][m] = w
                graph[m][n] = w
        if self.node_id not in graph:
            graph[self.node_id] = {}
        dist, nexthop = dijkstra(graph, self.node_id)
        # build table like DVR
        table = {}
        for d,c in dist.items():
            if d == self.node_id or c == float('inf'): 
                continue
            table[d] = {"cost": c, "next": nexthop.get(d)}
        return table
