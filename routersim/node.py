from __future__ import annotations
import threading, queue, time
from typing import List, Optional
from .messages import Message, new_msg
from .transport.socket_transport import SocketTransport
from .transport.xmpp_transport import XMPPTransport
from .utils import make_logger, now_ms
from .algorithms.flooding import Flooding
from .algorithms.dvr import DistanceVector, INF
from .algorithms.lsr import LinkState
from .algorithms.dijkstra import DijkstraStatic
from .config import TopologyConfig, NamesConfig

class Node:
    def __init__(self, node_id: str, algo: str, topo: TopologyConfig, names: NamesConfig, transport: str="socket", log_level="INFO", xmpp_jid: str|None=None, xmpp_password: str|None=None, xmpp_host: str|None=None, xmpp_port: int=5222, xmpp_tls: bool=True):
        self.node_id=node_id; self.algo_name=algo; self.topo=topo; self.names=names
        self.neighbors: List[str]=self.topo.neighbors_of(node_id); self.log=make_logger(f"Node({node_id},{algo})",log_level)

        if algo=="flooding": self.algo=Flooding(node_id)
        elif algo=="dvr": self.algo=DistanceVector(node_id)
        elif algo=="lsr": self.algo=LinkState(node_id)
        elif algo=="dijkstra":
            graph={}
            for u, nbrs in self.topo.neighbors.items():
                graph.setdefault(u,{})
                for v in nbrs:
                    graph[u][v]=1.0; graph.setdefault(v,{}); graph[v].setdefault(u,1.0)
            self.algo=DijkstraStatic(node_id, graph)
        else: raise ValueError("Unknown algo")

        if transport=="socket":
            self.transport=SocketTransport(node_id, self._on_raw_message, log_level=log_level)
        else:
            jid=xmpp_jid or self.names.name_of(node_id)
            if not xmpp_password: raise ValueError("Falta --password para XMPP")
            self.transport=XMPPTransport(node_id, self._on_raw_message, jid=jid, password=xmpp_password, id_to_jid=self.names.names, host=xmpp_host, port=xmpp_port, use_tls=xmpp_tls, log_level=log_level)

        self.incoming=queue.Queue(); self._stop=threading.Event()
        self.forward_thread=threading.Thread(target=self._forwarding_loop, daemon=True)
        self.routing_thread=threading.Thread(target=self._routing_loop, daemon=True)
        self.hello_interval=2.0; self.info_interval=3.0
        self.last_hello=0.0; self.last_info=0.0
        self.algo.neighbors_updated(self.neighbors)

    def _on_raw_message(self, from_id: str, json_str: str):
        try: msg=Message.from_json(json_str); self.incoming.put((from_id, msg))
        except Exception as e: self.log.error(f"bad incoming: {e}")

    def start(self):
        self.transport.start(); self.forward_thread.start(); self.routing_thread.start(); self.log.info(f"Neighbors: {self.neighbors}")
    def stop(self):
        self._stop.set(); self.transport.stop()

    def _send_to(self, to_id: str, msg: Message):
        if msg.ttl <= 0: return
        self.transport.send(to_id, msg.to_json())

    def _neighbors_except(self, exclude: Optional[str]) -> List[str]:
        return [n for n in self.neighbors if n != exclude]

    def _routing_loop(self):
        while not self._stop.is_set():
            now=time.time()
            if now - self.last_hello >= self.hello_interval: self._send_hello(); self.last_hello = now
            if now - self.last_info >= self.info_interval: self._send_info(); self.last_info = now
            time.sleep(0.1)

    def _send_hello(self):
        for n in self.neighbors:
            m=new_msg(self.algo_name, "hello", self.node_id, n, ttl=8, hello_ts=now_ms()); self._send_to(n, m)

    def _send_info(self):
        payload=self.algo.build_info_payload()
        if payload is None: return
        if self.algo_name=="dvr":
            base_vec=payload["vector"]
            for n in self.neighbors:
                vec=dict(base_vec)
                if getattr(self.algo, "split_horizon_poison", False):
                    for dst, nh in list(getattr(self.algo, "next_hop", {}).items()):
                        if nh==n: vec[dst]=float('inf')
                m=new_msg(self.algo_name, "info", self.node_id, n, ttl=8, info_kind="DV"); m.payload={"kind":"DV","vector":vec}; self._send_to(n, m)
        else:
            for n in self.neighbors:
                m=new_msg(self.algo_name, "info", self.node_id, n, ttl=8, info_kind="LSP"); m.payload=payload; self._send_to(n, m)

    def _forwarding_loop(self):
        seen_flood=set()
        while not self._stop.is_set():
            try: from_id, msg = self.incoming.get(timeout=0.2)
            except queue.Empty: continue
            msg.ttl -= 1
            if msg.ttl < 0: continue
            if msg.type=="hello":
                echo=new_msg(self.algo_name, "echo", self.node_id, from_id, ttl=8, hello_ts=msg.headers.get("hello_ts")); self._send_to(from_id, echo); continue
            if msg.type=="echo":
                ts=msg.headers.get("hello_ts")
                if ts is not None: rtt_ms = now_ms() - int(ts); self.algo.on_hello_rtt(from_id, float(rtt_ms))
                continue
            if msg.type=="info":
                if self.algo_name=="lsr":
                    seen,_=self.algo.on_info(from_id, msg.payload)
                    if seen:
                        for n in self._neighbors_except(from_id):
                            fwd=new_msg(self.algo_name, "info", self.node_id, n, ttl=msg.ttl, relayed_from=from_id); fwd.payload=msg.payload; self._send_to(n, fwd)
                elif self.algo_name=="dvr":
                    updated=self.algo.on_info(from_id, msg.payload)
                    if updated: self._send_info()
                continue
            if msg.type=="message":
                if msg.to==self.node_id:
                    self.log.info(f" Si jalo, Recibído compa: {msg.payload} <- {msg.from_}"); continue
                if self.algo_name=="flooding":
                    mid=msg.headers.get("msg_id"); key=(mid,self.node_id)
                    if key in seen_flood: continue
                    seen_flood.add(key)
                    for n in self._neighbors_except(from_id):
                        fwd=new_msg(self.algo_name, "message", self.node_id, msg.to, ttl=msg.ttl, msg_id=mid); fwd.payload=msg.payload; self._send_to(n, fwd)
                else:
                    nh=self.algo.choose_next_hop(msg.to)
                    if nh is None:
                        for n in self._neighbors_except(from_id):
                            fwd=new_msg(self.algo_name, "message", self.node_id, msg.to, ttl=msg.ttl); fwd.payload=msg.payload; self._send_to(n, fwd)
                    else:
                        fwd=new_msg(self.algo_name, "message", self.node_id, msg.to, ttl=msg.ttl); fwd.payload=msg.payload; self._send_to(nh, fwd)
                continue

    def send_user_message(self, to_id: str, text: str):
        m=new_msg(self.algo_name, "message", self.node_id, to_id, ttl=16); m.payload=text
        nh=None
        if hasattr(self.algo, "choose_next_hop"): nh=self.algo.choose_next_hop(to_id)
        if nh: self._send_to(nh, m)
        else:
            for n in self.neighbors: self._send_to(n, m)
