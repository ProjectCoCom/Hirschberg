"""
Structured logger setup.

Responsibilities:
- Configures structlog, console formatters, and outputs logs to server.log.

Coupling:
- Base utility used by every backend module.
"""


from __future__ import annotations

import logging
import re
import sys

SECRET_PATTERN = re.compile(r"(AQ[A-Za-z0-9_-]{20,}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{80,}|sb-[A-Za-z0-9]{20,}|eyJ[A-Za-z0-9_-]{50,})")


def _mask(text: str) -> str:
    return SECRET_PATTERN.sub(lambda m: m.group()[:6] + "***", text)


class MaskedFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return _mask(msg)


def setup_logging(level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("jat")
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    fmt = MaskedFormatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(fmt)
    logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger


log = setup_logging()
