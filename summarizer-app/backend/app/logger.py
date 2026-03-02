"""
Logging setup for the GenAIsummarizer app.
Logs include timestamp, user ID, action, and error details.
"""

import sys
from loguru import logger

# Remove default logger
logger.remove()

# Console logging
logger.add(
    sys.stdout,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | {message}",
    level="INFO",
    colorize=True,
)

# File logging for audit
logger.add(
    "logs/app.log",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | user={extra[user_id]} | {message}",
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    compression="zip",
    serialize=False,
)


def get_logger(user_id: str = "system"):
    """Return a logger instance bound with user context."""
    return logger.bind(user_id=user_id)
