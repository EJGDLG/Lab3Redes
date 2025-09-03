from __future__ import annotations
import json, time, uuid
from dataclasses import dataclass, field
from typing import Any, Dict

@dataclass
class Message:
    proto: str
    type: str
    from_: str
    to: str
    ttl: int = 8
    headers: Dict[str, Any] = field(default_factory=dict)
    payload: Any = None
    def to_json(self) -> str:
        return json.dumps({"proto":self.proto,"type":self.type,"from":self.from_,"to":self.to,"ttl":self.ttl,"headers":self.headers,"payload":self.payload}, ensure_ascii=False)
    @staticmethod
    def from_json(s: str) -> "Message":
        obj = json.loads(s)
        return Message(proto=obj["proto"], type=obj["type"], from_=obj["from"], to=obj["to"], ttl=obj.get("ttl",8), headers=obj.get("headers",{}), payload=obj.get("payload"))
def new_msg(proto: str, mtype: str, from_id: str, to_id: str, ttl: int = 8, **headers) -> Message:
    h = {"msg_id": headers.pop("msg_id", str(uuid.uuid4())), "ts": time.time()}
    h.update(headers)
    return Message(proto=proto, type=mtype, from_=from_id, to=to_id, ttl=ttl, headers=h)
