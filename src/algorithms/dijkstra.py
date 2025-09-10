import heapq

def dijkstra(graph, start):
    # graph: dict[node] -> dict[neighbor] = weight
    dist = {v: float('inf') for v in graph}
    prev = {v: None for v in graph}
    dist[start] = 0
    pq = [(0, start)]
    while pq:
        d,u = heapq.heappop(pq)
        if d!=dist[u]: 
            continue
        for v,w in graph[u].items():
            nd = d + w
            if nd < dist[v]:
                dist[v] = nd
                prev[v] = u
                heapq.heappush(pq, (nd, v))
    # Build next-hop table from prev
    nexthop = {}
    for dest in graph:
        if dest == start or dist[dest] == float('inf'):
            continue
        # walk back from dest to neighbor after start
        u = dest
        while prev[u] and prev[u] != start:
            u = prev[u]
        if prev[u] == start:
            nexthop[dest] = u
    return dist, nexthop
