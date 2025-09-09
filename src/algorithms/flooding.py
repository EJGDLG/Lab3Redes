class Flooding:
    def __init__(self, node_id):
        self.node_id = node_id
        # cache to avoid loops: (msg_id)->ttl_seen
        self.seen = set()

    def should_forward(self, msg_id:str) -> bool:
        if msg_id in self.seen:
            return False
        self.seen.add(msg_id)
        return True

    def next_hops(self, neighbors, _dest):
        # flooding: send to all neighbors
        return list(neighbors)
