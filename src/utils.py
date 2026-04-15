from __future__ import annotations

import logging


DEFAULT_LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def configure_logging(level: str = "INFO") -> None:
    resolved_level = getattr(logging, level.upper(), None)
    if resolved_level is None:
        raise ValueError(f"Unsupported log level: {level}")

    root_logger = logging.getLogger()
    if root_logger.handlers:
        root_logger.setLevel(resolved_level)
        for handler in root_logger.handlers:
            handler.setFormatter(logging.Formatter(DEFAULT_LOG_FORMAT, datefmt=DEFAULT_DATE_FORMAT))
        return

    logging.basicConfig(
        level=resolved_level,
        format=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)