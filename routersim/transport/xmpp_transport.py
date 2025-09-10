from __future__ import annotations
import asyncio, json, threading, logging
from typing import Callable, Optional, Dict
from slixmpp import ClientXMPP

class _SlixClient(ClientXMPP):
    def __init__(self, jid: str, password: str, on_text: Callable[[str, str], None]):
        super().__init__(jid, password)
        self._on_text = on_text
        self.add_event_handler("session_start", self._on_session_start)
        self.add_event_handler("message", self._on_message)
    async def _on_session_start(self, event):
        self.send_presence(); await self.get_roster()
    def _on_message(self, msg):
        if msg['type'] in ('chat','normal'):
            body = str(msg['body']) if msg['body'] else ""
            from_jid = str(msg['from']).bare
            self._on_text(from_jid, body)

class XMPPTransport:
    def __init__(self, node_id: str, on_message: Callable[[str,str],None], jid: str, password: str, id_to_jid: Optional[Dict[str,str]]=None, host: Optional[str]=None, port: int=5222, use_tls: bool=True, log_level: str="INFO"):
        self.node_id=node_id; self.jid=jid; self.password=password; self.on_message=on_message
        self.id_to_jid=id_to_jid or {}; self.host=host; self.port=port; self.use_tls=use_tls
        self._loop=None; self._thread=None; self._client=None
        logging.getLogger("slixmpp").setLevel(getattr(logging, log_level.upper(), logging.INFO))
    def start(self):
        if self._thread and self._thread.is_alive(): return
        self._thread=threading.Thread(target=self._run_loop, daemon=True); self._thread.start()
    def stop(self):
        if self._client and self._loop:
            try: asyncio.run_coroutine_threadsafe(self._client.disconnect(), self._loop).result(timeout=3)
            except Exception: pass
        if self._loop:
            try: self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception: pass
        if self._thread: self._thread.join(timeout=3)
    def _run_loop(self):
        self._loop=asyncio.new_event_loop(); asyncio.set_event_loop(self._loop)
        self._client=_SlixClient(self.jid, self.password, self.on_message)
        self._client.use_tls=self.use_tls; self._client.use_ipv6=False
        connected = self._client.connect(address=(self.host, self.port)) if self.host else self._client.connect()
        if not connected: return
        try: self._client.process(forever=True)
        finally:
            try: self._client.disconnect()
            except Exception: pass
    def send(self, to_id: str, json_str: str):
        to_jid = self.id_to_jid.get(to_id, to_id)
        if not (self._client and self._loop): return
        async def _send(): self._client.send_message(mto=to_jid, mbody=json_str, mtype='chat')
        try: asyncio.run_coroutine_threadsafe(_send(), self._loop).result(timeout=2)
        except Exception: pass
