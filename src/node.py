import asyncio, json, uuid, time
from typing import Dict, Any
import redis.asyncio as redis
from .core.utils import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, HELLO_INTERVAL, INFO_INTERVAL, TTL_DEFAULT, now_ms, make_msg, pretty_table
from .core.protocol import encode, decode
from .algorithms.flooding import Flooding
from .algorithms.distance_vector import DistanceVector
from .algorithms.link_state import LinkState

class Node:
    def __init__(self, node_id:str, proto:str, neighbors:Dict[str,int], channel_map:Dict[str,str]):
        self.id = node_id
        self.proto = proto  # 'flooding' | 'dvr' | 'lsr'
        self.neighbors = dict(neighbors)  # neighbor -> cost
        self.channels = channel_map       # node_id -> redis channel

        # algorithms
        self.flood = Flooding(node_id)
        self.dv = DistanceVector(node_id)
        for n,c in neighbors.items():
            self.dv.set_neighbor_cost(n, c)
        self.ls = LinkState(node_id)

        # hello RTT memory
        self.hello_sent = {}  # id -> timestamp
        self.loop = asyncio.get_event_loop()

        self.r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD)
        self.pubsub = None

    async def start(self):
        # Siembra LSP local y tabla inicial
        self.ls.ingest_lsp({"src": self.id, "seq": 0, "links": self.neighbors})
        self._recompute_tables()

        self.pubsub = self.r.pubsub()
        # Suscripción a mi canal
        await self.pubsub.subscribe(self.channels[self.id])

        # (Opcional) suscribirse también a los canales de mis vecinos:
        neighbor_channels = [self.channels[n] for n in self.neighbors if n in self.channels]
        if neighbor_channels:
            await self.pubsub.subscribe(*neighbor_channels)

        asyncio.create_task(self._forwarding())
        asyncio.create_task(self._hello_loop())
        asyncio.create_task(self._info_loop())
        print(f"[{self.id}] up @ proto={self.proto} redis={REDIS_HOST}:{REDIS_PORT}")
        while True:
            await asyncio.sleep(3600)

    # -------- loops --------
    async def _forwarding(self):
        assert self.pubsub is not None
        while True:
            raw = await self.pubsub.get_message(ignore_subscribe_messages=True, timeout=None)
            if not raw: 
                continue
            try:
                msg = decode(raw["data"])
            except Exception as e:
                print(f"[{self.id}] decode error: {e}")
                continue
            await self._handle_message(msg)

    async def _hello_loop(self):
        while True:
            await asyncio.sleep(HELLO_INTERVAL)
            for neigh in self.neighbors:
                mid = str(uuid.uuid4())
                self.hello_sent[mid] = now_ms()
                m = make_msg(self.proto, "hello", self.id, neigh, headers=[{"id":mid}])
                await self._send(neigh, m)

    async def _info_loop(self):
        while True:
            await asyncio.sleep(INFO_INTERVAL)
            if self.proto == "dvr":
                vector = self.dv.export_vector()
                payload = {"vector": vector}
                for neigh in self.neighbors:
                    m = make_msg(self.proto, "info", self.id, neigh, payload=payload)
                    await self._send(neigh, m)
            elif self.proto == "lsr":
                lsp = self.ls.build_lsp(self.neighbors)
                # flood LSP to vecinos
                for neigh in self.neighbors:
                    m = make_msg(self.proto, "info", self.id, neigh, payload={"lsp": lsp})
                    await self._send(neigh, m)

    # -------- handlers --------
    async def _handle_message(self, msg:Dict[str,Any]):
        mtype = msg.get("type")
        src = msg.get("from"); dst = msg.get("to")
        if mtype == "hello" and dst == self.id:
            # respond echo
            mid = None
            for h in msg.get("headers", []):
                if "id" in h: mid = h["id"]
            echo = make_msg(self.proto, "echo", self.id, src, headers=[{"id": mid}])
            await self._send(src, echo)
            return
        if mtype == "echo" and dst == self.id:
            mid = None
            for h in msg.get("headers", []):
                if "id" in h: mid = h["id"]
            if mid in self.hello_sent:
                rtt = now_ms() - self.hello_sent.pop(mid)
                # update neighbor cost to simple RTT/2 rounded (keep min to stabilize)
                neigh = src
                cost = max(1, int(rtt/2))
                self.neighbors[neigh] = cost
                self.dv.set_neighbor_cost(neigh, cost)
                # also refresh our own LSP database entry
                self.ls.ingest_lsp({"src": self.id, "seq": 0, "links": self.neighbors})
                print(f"[{self.id}] RTT {src} ~{rtt}ms -> cost {cost}")
                self._recompute_tables()
            return
        if mtype == "info":
            if self.proto == "dvr" and dst == self.id:
                vec = msg.get("payload",{}).get("vector",{})
                self.dv.ingest_vector(src, vec)
                self._recompute_tables()
            elif self.proto == "lsr":
                lsp = msg.get("payload",{}).get("lsp")
                changed = self.ls.ingest_lsp(lsp)
                if changed:
                    # flood onwards except where it came from
                    for neigh in self.neighbors:
                        if neigh == src: 
                            continue
                        forward = msg.copy()
                        forward["to"] = neigh
                        await self._send(neigh, forward)
                    self._recompute_tables()
            return

        # data message
        if mtype == "message":
            if dst == self.id:
                text = msg.get("payload",{}).get("text")
                print(f"[{self.id}] <{src}> {text}")
                return
            # TTL check
            ttl = int(msg.get("ttl", 1))
            if ttl <= 0:
                print(f"[{self.id}] drop TTL0 {msg}")
                return
            msg["ttl"] = ttl - 1
            await self._route_and_forward(msg, src)
            return

    async def _route_and_forward(self, msg:Dict[str,Any], src:str):
        dst = msg["to"]
        if self.proto == "flooding":
            # dedup by id in headers; create if missing
            hid = None
            for h in msg.get("headers", []):
                if "id" in h: hid = h["id"]
            if hid is None:
                import uuid
                hid = str(uuid.uuid4())
                msg["headers"] = msg.get("headers", []) + [{"id":hid}]
            if not self.flood.should_forward(hid):
                return
            for n in self.neighbors:
                if n == src: 
                    continue
                fwd = msg.copy(); fwd["to"] = n
                await self._send(n, fwd)
        else:
            # table-based
            table = getattr(self, 'routing_table', {})
            nex = table.get(dst, {}).get("next")
            if not nex:
                # fallback: try flooding to discover
                for n in self.neighbors:
                    if n == src: 
                        continue
                    fwd = msg.copy(); fwd["to"] = n
                    await self._send(n, fwd)
            else:
                fwd = msg.copy(); fwd["to"] = nex
                await self._send(nex, fwd)

    def _recompute_tables(self):
        if self.proto == "dvr":
            if self.dv.recompute():
                self.routing_table = dict(self.dv.table)
                print(f"[{self.id}] DVR table:\n{pretty_table(self.routing_table)}")
        elif self.proto == "lsr":
            self.routing_table = self.ls.compute_spf()
            print(f"[{self.id}] LSR table:\n{pretty_table(self.routing_table)}")
        else:
            self.routing_table = {}

    async def _send(self, node_id:str, msg:Dict[str,Any]):
        ch = self.channels[node_id]
        await self.r.publish(ch, json.dumps(msg))
