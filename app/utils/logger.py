"""
Logging configuration module
"""
import logging
import sys
from typing import Optional
from app.core.config import settings


def setup_logging(name: Optional[str] = None) -> logging.Logger:
    """
    Setup and return a logger instance

    Args:
        name: Logger name, typically __name__ of the module

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name or settings.APP_NAME)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))

    # Formatter
    formatter = logging.Formatter(settings.LOG_FORMAT)
    console_handler.setFormatter(formatter)

    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with the given name

    Args:
        name: Logger name

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
