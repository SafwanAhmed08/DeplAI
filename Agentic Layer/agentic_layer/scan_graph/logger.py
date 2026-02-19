from __future__ import annotations

import logging
import os


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("deplai.scan")
    if logger.handlers:
        return logger

    level_name = os.getenv("SCAN_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(level)
    logger.propagate = False
    return logger


scan_logger = _build_logger()


def log_agent(scan_id: str, agent: str, message: str) -> None:
    scan_logger.info("[scan:%s] [%s] %s", scan_id, agent, message)
