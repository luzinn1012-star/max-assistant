"""Metadados de desempenho sem textos de conversa, tokens ou stderr bruto."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.observability import RequestIdFilter


def setup_logging(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("max")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if logger.handlers:
        return
    handler = RotatingFileHandler(
        directory / "max.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s request_id=%(request_id)s %(message)s")
    )
    logger.addHandler(handler)
