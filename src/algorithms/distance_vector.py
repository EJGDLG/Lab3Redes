from typing import Dict

class DistanceVector:
    def __init__(self, node_id):
        self.node_id = node_id
        # table[dest] = {"cost": cost, "next": neighbor}
        self.table: Dict[str, Dict] = {node_id: {"cost": 0, "next": node_id}}
        self.cost_to_neighbor = {}  # neighbor -> cost
        self.vectors_from_neighbors = {}  # neighbor -> its vector

    def set_neighbor_cost(self, neigh, cost):
        self.cost_to_neighbor[neigh] = cost

    def ingest_vector(self, neigh, vector: Dict[str, float]):
        self.vectors_from_neighbors[neigh] = vector

    def recompute(self):
        # Bellman-Ford update
        changed = False
        nodes = set([self.node_id])
        for n,vec in self.vectors_from_neighbors.items():
            nodes.update(vec.keys())
        for dest in nodes:
            if dest == self.node_id: 
                continue
            best_cost = float('inf')
            best_next = None
            for n, vec in self.vectors_from_neighbors.items():
                if n not in self.cost_to_neighbor: 
                    continue
                c_n = self.cost_to_neighbor[n]
                c_d = vec.get(dest, float('inf'))
                c = c_n + c_d
                if c < best_cost:
                    best_cost = c
                    best_next = n
            # direct neighbor?
            if dest in self.cost_to_neighbor and self.cost_to_neighbor[dest] < best_cost:
                best_cost = self.cost_to_neighbor[dest]
                best_next = dest
            prev = self.table.get(dest, {"cost": float('inf'), "next": None})
            if best_cost != prev["cost"] or best_next != prev["next"]:
                self.table[dest] = {"cost": best_cost, "next": best_next}
                changed = True
        return changed

    def export_vector(self) -> Dict[str, float]:
        # distance vector: only cost to each destination
        return {dest: row["cost"] for dest,row in self.table.items()}
