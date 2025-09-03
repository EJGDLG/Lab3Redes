from __future__ import annotations
from typing import Callable, Optional
class XMPPTransport:
    """Stub XMPP con host/port/jid/password parametrizables."""
    def __init__(self, node_id: str, on_message: Callable[[str,str],None], jid: str, password: str, host: Optional[str]=None, port: int=5222):
        self.node_id=node_id; self.jid=jid; self.password=password; self.host=host; self.port=port; self.on_message=on_message
    def start(self): raise NotImplementedError(f"Implementar con slixmpp/sleekxmpp (host={self.host or 'auto'}, port={self.port}).")
    def stop(self): pass
    def send(self, to_id: str, json_str: str): raise NotImplementedError("Implementar envío XMPP del JSON en el cuerpo del mensaje.")
