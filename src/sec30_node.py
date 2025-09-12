import argparse, asyncio, json, os, time, math
from typing import Dict, Any, Tuple, Optional
import redis.asyncio as redis

REDIS_HOST = os.getenv("REDIS_HOST", "homelab.fortiguate.com")
REDIS_PORT = int(os.getenv("REDIS_PORT", "16379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "4YNydkHFPcayvlx7$zpKm")

HELLO_INTERVAL = float(os.getenv("HELLO_INTERVAL", "3"))
DECAY_INTERVAL = float(os.getenv("DECAY_INTERVAL", "1"))
NEIGHBOR_TTL  = int(os.getenv("TTL_DEFAULT", "6"))  # segundos

def now_ms() -> int:
    return int(time.time()*1000)

def log(id, *a):
    print(f"[{id}]", " ".join(str(x) for x in a), flush=True)

def is_valid_id(x:str)->bool:
    return x.startswith("sec30.grupo") and ".nodo" in x

class Sec30Node:
    def __init__(self, node_id:str, topology:Dict[str, Dict[str,int]]):
        assert is_valid_id(node_id), "El --id debe ser del tipo sec30.grupoX.nodoY"
        self.id = node_id
        self.topology = topology
        self.neighbors: Dict[str,int] = dict(topology.get(node_id, {}))

        self.G: Dict[str, Dict[str, Dict[str,int]]] = {}   # G[U][V] = {"weight":w, "time"?:int}
        self.edge_cache: Dict[Tuple[str,str], int] = {}     # (u,v)->w
        self._stop = asyncio.Event()

        # meta: first_seen y último hello (solo vecinos)
        self.node_meta = {}  # node_id -> {"first_seen_ms": int, "last_hello_ms": int|None}

        self.r: Optional[redis.Redis] = None
        self.pubsub = None

    # ---------- tabla interna ----------
    def _ensure_node(self, u:str):
        if u not in self.G:
            self.G[u] = {}

    def _set_edge(self, u:str, v:str, w:int, with_timer:bool=False):
        self._ensure_node(u)
        entry = {"weight": int(w)}
        if with_timer:
            entry["time"] = NEIGHBOR_TTL
        self.G[u][v] = entry

    def _del_edge(self, u:str, v:str):
        if u in self.G and v in self.G[u]:
            del self.G[u][v]
            if not self.G[u]:
                del self.G[u]

    # ---------- meta ----------
    def _touch_first_seen(self, node_id:str):
        if node_id not in self.node_meta:
            self.node_meta[node_id] = {"first_seen_ms": now_ms(), "last_hello_ms": None}

    def _uptime_str(self, node_id:str) -> str:
        meta = self.node_meta.get(node_id)
        if not meta: return "-"
        dt = max(0, now_ms() - meta["first_seen_ms"]) // 1000
        m, s = divmod(dt, 60)
        return f"{m:02d}:{s:02d}"

    # ---------- redis helpers ----------
    def _channel_for(self, node_id:str) -> str:
        return node_id

    async def send(self, dst:str, msg:Dict[str,Any]):
        await self.r.publish(self._channel_for(dst), json.dumps(msg))

    # ---------- mensajes ----------
    def _build_hello(self, to:str, hops:int)->Dict[str,Any]:
        return {"type":"hello","from": self.id,"to": to, "hops": int(hops)}

    def _build_message(self, u:str, v:str, w:int)->Dict[str,Any]:
        return {"type":"message","from": u,"to": v,"hops": int(w)}

    async def _hello_loop(self):
        while not self._stop.is_set():
            await asyncio.sleep(HELLO_INTERVAL)
            for v,w in list(self.neighbors.items()):
                try:
                    await self.send(v, self._build_hello(v,w))
                except Exception as e:
                    log(self.id, "error hello->", v, e)

    async def _decay_loop(self):
        """
        Recalcula time_left en base al último hello recibido (last_hello_ms),
        en vez de decrementar un contador por tick. Esto evita falsos "caídos"
        cuando hay jitter o atrasos del event loop.
        """
        grace = 1.0  # segundos extra de gracia sobre TTL para eliminar
        while not self._stop.is_set():
            await asyncio.sleep(DECAY_INTERVAL)

            changed = False
            now = now_ms()

            # 🔹 Saneo: cualquier entrada en G[self.id] sin 'time' no es vecino real
            phantoms = []
            for v, ent in list(self.G.get(self.id, {}).items()):
                if "time" not in ent:
                    phantoms.append(v)
            for v in phantoms:
                self._del_edge(self.id, v)
                changed = True

            # 🔹 Recalcular time_left usando last_hello_ms
            for v in list(self.neighbors.keys()):
                ent = self.G.get(self.id, {}).get(v)
                if not ent:
                    continue  # aún no hay entrada (no ha llegado el primer hello)

                meta = self.node_meta.get(v, {})
                last = meta.get("last_hello_ms")
                if last is None:
                    ent["time"] = ent.get("time", NEIGHBOR_TTL)
                    continue

                elapsed = (now - last) / 1000.0
                time_left = int(max(0, NEIGHBOR_TTL - elapsed))
                ent["time"] = time_left

                if elapsed > (NEIGHBOR_TTL + grace):
                    self._del_edge(self.id, v)
                    log(self.id, f"vecino caído {v} (elapsed={elapsed:.1f}s), se elimina y se propaga")
                    changed = True

            if changed:
                await self._propagate_local_links()

    async def _propagate_local_links(self):
        for v,ent in self.G.get(self.id, {}).items():
            w = ent["weight"]
            msg = self._build_message(self.id, v, w)
            await self._flood(msg, prev_hop=None)

    async def _flood(self, msg:Dict[str,Any], prev_hop:Optional[str]):
        for n in self.neighbors:
            if n == prev_hop:
                continue
            try:
                await self.send(n, msg)
            except Exception as e:
                log(self.id, "error flood->", n, e)

    # ---------- ingesta ----------
    async def _on_hello(self, m:Dict[str,Any]):
        # Acepta solo HELLO dirigido a mí
        src = m.get("from"); dst = m.get("to")
        if dst != self.id or not src:
            return
        if not is_valid_id(src):
            return
        # Acepta HELLO solo de un vecino REAL (según la topología local)
        if src not in self.neighbors:
            # log(self.id, f"HELLO ignorado de no-vecino {src}")
            return

        # Tolerante con 'hops'
        w_raw = m.get("hops")
        if w_raw is None:
            w = int(self.neighbors[src])
        else:
            try:
                w = int(w_raw)
            except Exception:
                w = int(self.neighbors[src])

        log(self.id, f"[HELLO] de {src} (w={w})")

        # Actualiza/crea el enlace propio con timer
        self._touch_first_seen(src)
        self.node_meta[src]["last_hello_ms"] = now_ms()
        self._set_edge(self.id, src, w, with_timer=True)

    async def _on_message(self, m:Dict[str,Any], prev_hop:Optional[str]):
        # 1) Validar formato
        u = m.get("from")
        v = m.get("to")
        w = m.get("hops")
        if not u or not v or w is None:
            return
        if not (is_valid_id(u) and is_valid_id(v)):
            return

        # 2) No aceptar ningún 'message' que involucre a 'self.id'
        #    (para no crear/alterar enlaces propios; eso solo lo maneja HELLO)
        if u == self.id or v == self.id:
            return

        # 3) Normalizar tipos
        try:
            w = int(w)
        except Exception:
            return

        key_uv = (u, v)
        key_vu = (v, u)

        # 4) Supresión de duplicados (para ambos sentidos)
        if self.edge_cache.get(key_uv) == w and self.edge_cache.get(key_vu) == w:
            return

        # 5) Aprender arista como NO dirigida (u<->v) para Dijkstra
        self._touch_first_seen(u)
        self._touch_first_seen(v)
        self.edge_cache[key_uv] = w
        self.edge_cache[key_vu] = w
        self._set_edge(u, v, w, with_timer=False)
        self._set_edge(v, u, w, with_timer=False)

        # 6) Re-flood si pasó los filtros
        await self._flood(m, prev_hop=prev_hop)

    # ---------- SPF ----------
    def _build_graph(self) -> Dict[str, Dict[str,int]]:
        G2: Dict[str,Dict[str,int]] = {}
        for u, nbrs in self.G.items():
            for v, ent in nbrs.items():
                w = int(ent["weight"])
                G2.setdefault(u, {})[v] = w
        return G2

    def dijkstra(self, src:str):
        G = self._build_graph()
        nodes = set(G.keys())
        for u in list(G.keys()):
            nodes.update(G[u].keys())
        dist = {n: math.inf for n in nodes}
        prev = {n: None for n in nodes}
        dist[src] = 0.0
        unvisited = set(nodes)
        while unvisited:
            u = min(unvisited, key=lambda n: dist.get(n, math.inf))
            unvisited.remove(u)
            for v,w in G.get(u, {}).items():
                alt = dist[u] + w
                if alt < dist.get(v, math.inf):
                    dist[v] = alt
                    prev[v] = u
        return dist, prev

    def _path_info(self, target:str):
        """
        Calcula ruta más corta desde self.id hasta target.
        Devuelve: hops, cost, first_hop, path
        """
        # construir grafito directo (por si alguien llama antes)
        G = self._build_graph()
        if self.id not in G:
            return None, None, None, []
        # Dijkstra manual con heap
        import heapq
        dist = {self.id: 0}
        prev = {}
        Q = [(0, self.id)]

        visited = set()
        while Q:
            d,u = heapq.heappop(Q)
            if u in visited:
                continue
            visited.add(u)
            if u == target:
                break
            for v,ent in self.G.get(u, {}).items():
                w = ent.get("weight", 1)
                nd = d + w
                if nd < dist.get(v, 1e18):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(Q, (nd, v))

        if target not in dist:
            return None, None, None, []

        # reconstruir path
        path = []
        u = target
        while True:
            path.append(u)
            if u == self.id:
                break
            u = prev.get(u)
            if u is None:
                # no hay cadena completa
                return None, None, None, []
        path.reverse()

        hops = len(path)-1
        cost = dist[target]
        first = path[1] if hops >= 1 else None
        return hops, cost, first, path

    # ---------- start ----------
    async def start(self):
        self.r = await redis.from_url(
            f"redis://{REDIS_HOST}:{REDIS_PORT}",
            password=REDIS_PASSWORD, decode_responses=True
        )
        self.pubsub = self.r.pubsub()
        channels = [self._channel_for(self.id)] + [self._channel_for(v) for v in self.neighbors]
        await self.pubsub.subscribe(*channels)
        log(self.id, f"up @ redis={REDIS_HOST}:{REDIS_PORT} | neighbors={list(self.neighbors.items())}")
        for v,w in self.neighbors.items():
            self._touch_first_seen(v)
            # inicializa last_hello para no “cortar” al arranque
            self.node_meta[v]["last_hello_ms"] = now_ms()
            self._set_edge(self.id, v, w, with_timer=True)
        await self._propagate_local_links()

        loops = [
            asyncio.create_task(self._hello_loop()),
            asyncio.create_task(self._decay_loop()),
            asyncio.create_task(self._recv_loop())
        ]
        try:
            await asyncio.gather(*loops)
        finally:
            await self.pubsub.close()
            await self.r.aclose()

    async def _recv_loop(self):
        while not self._stop.is_set():
            try:
                msg = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if not msg:
                    await asyncio.sleep(0.1); continue
                data = json.loads(msg["data"])
                mtype = data.get("type")
                prev_hop = data.get("prev_hop")
                if mtype == "hello":
                    await self._on_hello(data)
                elif mtype == "message":
                    await self._on_message(data, prev_hop=prev_hop)
            except Exception as e:
                log(self.id, "recv error:", e)
                await asyncio.sleep(0.2)

# CLI
def load_json(p):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="ID: sec30.grupoX.nodoY")
    ap.add_argument("--topo", required=True, help="Archivo JSON de topología")
    ap.add_argument("--show-table", action="store_true", help="Imprime tabla enriquecida")
    ap.add_argument("--dijkstra", default=None, help="Destino para mostrar costo/primer salto")
    args = ap.parse_args()

    topo = load_json(args.topo)["config"]
    node = Sec30Node(args.id, topo)

    async def runner():
        if args.show_table:
            async def printer():
                while True:
                    await asyncio.sleep(5)
                    lines = []
                    lines.append("==== VECINOS (hello) ====")
                    for v, ent in sorted(node.G.get(node.id, {}).items()):
                        w = ent["weight"]
                        time_left = ent.get("time", None)
                        hops, total_cost, first, path = node._path_info(v)
                        path_str = "->".join(path) if path else "-"
                        uptime = node._uptime_str(v)
                        lines.append(
                            f"{v:28} edge_cost={w:>3}  "
                            f"hops={hops if hops is not None else '-':>2}  "
                            f"total_cost={total_cost if total_cost is not None else '-':>4}  "
                            f"time_left={time_left if time_left is not None else '-':>2}  "
                            f"path={path_str}  up={uptime}"
                        )
                    # no vecinos
                    known = set()
                    for u,nbrs in node.G.items():
                        known.add(u); known.update(nbrs.keys())
                    others = []
                    for d in known:
                        if d == node.id: 
                            continue
                        if d in node.G.get(node.id, {}): 
                            continue
                        hops, total_cost, first, path = node._path_info(d)
                        path_str = "->".join(path) if path else "-"
                        uptime = node._uptime_str(d)
                        others.append(
                            f"{d:28} edge_cost= -   "
                            f"hops={hops if hops is not None else '-':>2}  "
                            f"total_cost={total_cost if total_cost is not None else '-':>4}  "
                            f"path={path_str}  up={uptime}"
                        )
                    lines.append("==== NO VECINOS (vía flooding) ====")
                    lines.extend(sorted(others))
                    print("[" + node.id + "]\n" + "\n".join(lines), flush=True)
            asyncio.create_task(printer())

        if args.dijkstra:
            async def dij():
                while True:
                    await asyncio.sleep(10)
                    dest = args.dijkstra
                    hops, total_cost, first, path = node._path_info(dest)
                    if total_cost is None:
                        log(node.id, f"SPF to {dest}: sin ruta conocida (aún)")
                    else:
                        path_str = "->".join(path) if path else "-"
                        log(node.id, f"SPF to {dest}: hops={hops}, cost={total_cost}, next={first}, path={path_str}")
            asyncio.create_task(dij())

        await node.start()

    asyncio.run(runner())

if __name__ == "__main__":
    main()
