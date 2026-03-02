"""
Logging setup for the GenAIsummarizer app.
Logs include timestamp, user ID, action, and error details.
"""

import sys
from datetime import datetime, timezone

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


def audit_log(
    action: str,
    user_id: str = "anonymous",
    *,
    details: str = "",
    error: str = "",
    level: str = "INFO",
) -> None:
    """Write a structured audit log entry.

    Every audit entry includes:
      - timestamp  (ISO-8601 UTC)
      - user_id    (who triggered the action)
      - action     (what was attempted)
      - error      (empty on success, error description on failure)
      - details    (optional extra context)

    Parameters
    ----------
    action : str
        Short description of the action, e.g. ``"batch_upload"``.
    user_id : str
        Identifier for the user performing the action.
    details : str
        Additional human-readable context.
    error : str
        Error description when the action failed; empty string on success.
    level : str
        Log level – ``"INFO"`` for successes, ``"WARNING"`` or ``"ERROR"`` for failures.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    bound = logger.bind(user_id=user_id)
    msg = (
        f"AUDIT | timestamp={timestamp} | user_id={user_id} | "
        f"action={action}"
    )
    if details:
        msg += f" | details={details}"
    if error:
        msg += f" | error={error}"
    getattr(bound, level.lower(), bound.info)(msg)
