"""Structured logging for the platform backend."""

import json
import logging
import sys


class JSONFormatter(logging.Formatter):
    """Format log records as single-line JSON for production parsing."""

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "msg": record.getMessage(),
            "module": record.module,
        }
        if record.exc_info and record.exc_info[1]:
            entry["error"] = str(record.exc_info[1])
        return json.dumps(entry)


def setup_logging(json_output: bool = False) -> logging.Logger:
    """Configure the platform logger."""
    logger = logging.getLogger("explorer")
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        if json_output:
            handler.setFormatter(JSONFormatter())
        else:
            handler.setFormatter(logging.Formatter(
                "[%(asctime)s] %(levelname)s %(module)s: %(message)s",
                datefmt="%H:%M:%S",
            ))
        logger.addHandler(handler)

    return logger


# Module-level logger for import convenience
logger = setup_logging()
