"""Standard RotatingFileHandler logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from it_rpa_suite.adapters.paths import get_app_paths

LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


PACKAGE_LOGGER_NAME = "it_rpa_suite"


def _ensure_rotating_handler(
    target_logger: logging.Logger,
    target_path: Path,
    level: int,
) -> None:
    """Attach a single RotatingFileHandler for target_path if not already present."""
    for handler in target_logger.handlers:
        if (
            isinstance(handler, RotatingFileHandler)
            and Path(handler.baseFilename).resolve() == target_path
        ):
            return

    target_path.parent.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)
    file_handler = RotatingFileHandler(
        filename=str(target_path),
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(formatter)
    target_logger.addHandler(file_handler)


def get_logger(
    name: str = __name__,
    level: int = logging.INFO,
    log_file: str | Path | None = None,
) -> logging.Logger:
    """Return a configured logger writing to data/logs/app.log using a shared RotatingFileHandler."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if log_file is not None:
        target_path = Path(log_file).resolve()
        _ensure_rotating_handler(logger, target_path, level)
        logger.propagate = False
        return logger

    target_path = get_app_paths().log_file.resolve()
    root_pkg_logger = logging.getLogger(PACKAGE_LOGGER_NAME)
    root_pkg_logger.setLevel(level)
    _ensure_rotating_handler(root_pkg_logger, target_path, level)
    root_pkg_logger.propagate = False

    if name == PACKAGE_LOGGER_NAME or name.startswith(f"{PACKAGE_LOGGER_NAME}."):
        logger.propagate = True
        return logger

    # External/standalone logger names outside the package namespace
    _ensure_rotating_handler(logger, target_path, level)
    logger.propagate = False
    return logger
