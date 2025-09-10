import os, json, time
from typing import Dict, Any

REDIS_HOST = os.getenv("REDIS_HOST", "homelab.fortiguate.com")
REDIS_PORT = int(os.getenv("REDIS_PORT", "16379"))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "4YNydkHFPcayvlx7$zpKm")

TTL_DEFAULT = int(os.getenv("TTL_DEFAULT", "8"))
HELLO_INTERVAL = float(os.getenv("HELLO_INTERVAL", "5"))
INFO_INTERVAL  = float(os.getenv("INFO_INTERVAL",  "8"))

def now_ms() -> int:
    return int(time.time() * 1000)

def make_msg(proto:str, mtype:str, src:str, dst:str, ttl:int=None, headers=None, payload=None) -> Dict[str,Any]:
    return {
        "proto": proto,
        "type": mtype,
        "from": src,
        "to": dst,
        "ttl": TTL_DEFAULT if ttl is None else ttl,
        "headers": headers or [],
        "payload": payload or {}
    }

def pretty_table(table: Dict[str, dict]) -> str:
    lines = ["dest	cost	next"]
    for d, row in sorted(table.items()):
        lines.append(f"{d}	{row.get('cost', float('inf'))}	{row.get('next', '-')}")
    return "\n".join(lines)
