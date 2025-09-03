from __future__ import annotations
import argparse, time, sys
from routersim.node import Node
from routersim.config import TopologyConfig, NamesConfig

def main():
    p = argparse.ArgumentParser(description="RouterSim node")
    p.add_argument("--id", required=True)
    p.add_argument("--algo", required=True, choices=["flooding","dvr","lsr","dijkstra"])
    p.add_argument("--config-dir", required=True)
    p.add_argument("--transport", default="socket", choices=["socket","xmpp"])
    p.add_argument("--jid")
    p.add_argument("--password")
    p.add_argument("--xmpp-host")
    p.add_argument("--xmpp-port", type=int, default=5222)
    p.add_argument("--hello-interval", type=float, default=2.0)
    p.add_argument("--info-interval", type=float, default=3.0)
    p.add_argument("--log", default="INFO")
    p.add_argument("--send")
    p.add_argument("message", nargs="?")
    args = p.parse_args()

    topo = TopologyConfig.load(f"{args.config_dir}/topo-sample.txt")
    names = NamesConfig.load(f"{args.config_dir}/names-sample.txt")

    node = Node(
        args.id, args.algo, topo, names,
        transport=args.transport, log_level=args.log,
        xmpp_jid=args.jid, xmpp_password=args.password,
        xmpp_host=args.xmpp_host, xmpp_port=args.xmpp_port
    )
    node.hello_interval = args.hello_interval
    node.info_interval = args.info_interval
    node.start()

    if args.send:
        if not args.message:
            print("Falta el mensaje a enviar"); sys.exit(1)
        time.sleep(0.5); node.send_user_message(args.send, args.message); time.sleep(1.0); return

    try:
        while True: time.sleep(0.5)
    except KeyboardInterrupt: node.stop()

if __name__ == "__main__": main()
