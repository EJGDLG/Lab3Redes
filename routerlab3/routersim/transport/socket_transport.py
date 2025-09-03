from __future__ import annotations
import socket, threading, json
from typing import Callable
from ..utils import make_logger, port_for_id
class SocketTransport:
    def __init__(self, node_id: str, on_message: Callable[[str,str],None], log_level="INFO"):
        self.node_id=node_id; self.host="127.0.0.1"; self.port=port_for_id(node_id)
        self.on_message=on_message; self.log=make_logger(f"Socket({node_id})",log_level)
        self._stop=threading.Event(); self._server_thread=threading.Thread(target=self._serve,daemon=True)
    def start(self):
        self._server_thread.start(); self.log.info(f"Listening on {self.host}:{self.port}")
    def stop(self): self._stop.set()
    def _serve(self):
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR,1); s.bind((self.host,self.port)); s.listen()
            while not self._stop.is_set():
                try:
                    s.settimeout(1.0); conn, addr = s.accept()
                except socket.timeout: continue
                with conn:
                    data = conn.recv(65536)
                    try:
                        obj = json.loads(data.decode("utf-8")); from_id = obj.get("from","?")
                        self.on_message(from_id, json.dumps(obj))
                    except Exception as e: self.log.error(f"Bad packet: {e}")
    def send(self, to_id: str, json_str: str):
        host, port = self.host, port_for_id(to_id)
        try:
            with socket.create_connection((host,port),timeout=1.0) as c: c.sendall(json_str.encode("utf-8"))
        except Exception as e: self.log.warning(f"send to {to_id} failed: {e}")
