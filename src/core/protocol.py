import json
from typing import Dict, Any

def encode(msg: Dict[str, Any]) -> str:
    return json.dumps(msg, separators=(',',':'))

def decode(raw: bytes) -> Dict[str, Any]:
    if isinstance(raw, bytes):
        raw = raw.decode()
    return json.loads(raw)
