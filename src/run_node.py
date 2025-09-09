import argparse, json, asyncio
from pathlib import Path
from .node import Node

def load_json(p):
    return json.loads(Path(p).read_text(encoding='utf-8'))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="Node ID: N1..N11")
    ap.add_argument("--proto", required=True, choices=["flooding","dvr","lsr"], help="Routing algorithm")
    ap.add_argument("--topo", required=True, help="Path to topology JSON")
    ap.add_argument("--names", required=True, help="Path to names JSON")
    args = ap.parse_args()

    topo = load_json(args.topo)["config"]
    names = load_json(args.names)["config"]
    neighbors = topo.get(args.id, {})
    node = Node(args.id, args.proto, neighbors, names)
    asyncio.run(node.start())

if __name__ == "__main__":
    main()
