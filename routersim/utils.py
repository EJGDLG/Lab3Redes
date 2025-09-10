import logging, time, hashlib
def now_ms() -> int: return int(time.time()*1000)
def make_logger(name: str, level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s: %(message)s","%H:%M:%S"))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
def port_for_id(node_id: str, base: int = 50000) -> int:
    h = hashlib.sha256(node_id.encode("utf-8")).hexdigest()
    return base + (int(h[:6],16)%1000)
