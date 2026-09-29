"""Logging setup. Root stays at INFO so ORM/aiosqlite don't spam; app loggers can go deeper."""
import logging
import sys


def configure_logging(debug: bool = True) -> None:
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(name)s | %(message)s", "%H:%M:%S"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()
    root.addHandler(handler)
    for noisy in ("sqlalchemy.engine", "aiosqlite", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
