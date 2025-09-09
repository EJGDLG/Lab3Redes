import argparse, json, asyncio
import redis.asyncio as redis
import os
from ..core.utils import REDIS_HOST, REDIS_PORT, REDIS_PASSWORD, TTL_DEFAULT
from ..core.protocol import encode

async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="src", required=True)
    ap.add_argument("--to", dest="dst", required=True)
    ap.add_argument("--text", required=True)
    ap.add_argument("--proto", default="lsr")
    ap.add_argument("--names", required=True)
    ap.add_argument("--ttl", type=int, default=TTL_DEFAULT)
    args = ap.parse_args()

    names = json.loads(open(args.names, "r", encoding="utf-8").read())["config"]
    ch = names[args.src]

    msg = {
        "proto": args.proto,
        "type": "message",
        "from": args.src,
        "to": args.dst,
        "ttl": args.ttl,
        "headers": [],
        "payload": {"text": args.text}
    }

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD)
    await r.publish(ch, json.dumps(msg))
    await r.close()

if __name__ == "__main__":
    asyncio.run(main())
