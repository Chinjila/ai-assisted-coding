"""
Summarizer Service – single entry point for all summarisation business logic.

This service orchestrates:
  • Multi-format input parsing (plain text, PDF, DOCX, web URL)
  • File-size and batch-limit validation
  • AI summarisation via Azure OpenAI
  • Summary history management

The routing layers (api.py, ui.py) delegate to this service so they only
handle HTTP concerns and user interaction.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from backend.app import config
from backend.app.errors import (
    BatchLimitError,
    FileSizeError,
    FileFormatError,
    SummarizationError,
    URLFetchError,
)
from backend.app.logger import get_logger
from backend.app.summarizer.engine import summarize_text
from backend.app.summarizer.utils import extract_text_from_file, extract_text_from_url

logger = get_logger()


# ---------------------------------------------------------------------------
# In-memory history store (replace with a database for production)
# ---------------------------------------------------------------------------
_summary_history: dict[str, list] = {}  # user_id -> [summaries]


# ---------------------------------------------------------------------------
# History helpers
# ---------------------------------------------------------------------------

def get_history(user_id: str = "anonymous") -> list[dict]:
    """Return the summary history for *user_id*."""
    return _summary_history.get(user_id, [])


def _record_history(
    user_id: str,
    summary: str,
    summary_length: str,
    timestamp: str,
) -> None:
    """Append a summary record to the user's history."""
    _summary_history.setdefault(user_id, []).append(
        {
            "summary": summary,
            "summary_length": summary_length,
            "timestamp": timestamp,
        }
    )


def clear_history() -> None:
    """Clear all history (useful for tests)."""
    _summary_history.clear()


def _build_result(
    summary_result: str,
    summary_length: str,
    user_id: str,
) -> dict:
    """Create a standardised result dict and record history."""
    timestamp = datetime.utcnow().isoformat()
    _record_history(user_id, summary_result, summary_length, timestamp)
    return {
        "summary": summary_result,
        "summary_length": summary_length,
        "timestamp": timestamp,
    }


# ---------------------------------------------------------------------------
# Core service methods
# ---------------------------------------------------------------------------

async def summarize_from_text(
    text: str,
    summary_length: str,
    user_id: str = "anonymous",
) -> dict:
    """Summarise plain text input.

    Returns a dict with keys: summary, summary_length, timestamp.
    """
    logger.info(f"Service: summarize_from_text called – length={summary_length}, user={user_id}")
    _validate_summary_length(summary_length)

    try:
        summary_result = await summarize_text(text, summary_length)
    except SummarizationError:
        raise  # already user-friendly
    except Exception as exc:
        logger.error(f"Service: unexpected error during text summarisation – user={user_id}: {exc}")
        raise SummarizationError(
            "Something went wrong while summarising your text. Please try again."
        )

    result = _build_result(summary_result, summary_length, user_id)
    logger.info(f"Service: text summarised – length={summary_length}, user={user_id}")
    return result


async def summarize_from_url(
    url: str,
    summary_length: str,
    user_id: str = "anonymous",
) -> dict:
    """Fetch a web page, extract its text, and summarise it."""
    logger.info(f"Service: summarize_from_url called – url='{url}', length={summary_length}, user={user_id}")
    _validate_summary_length(summary_length)

    try:
        extracted_text = extract_text_from_url(url)
    except URLFetchError:
        raise  # already user-friendly
    except Exception as exc:
        logger.error(f"Service: failed to fetch URL '{url}' – user={user_id}: {exc}")
        raise URLFetchError(
            f"Could not retrieve content from '{url}'. "
            "Please check the URL and try again."
        )

    try:
        summary_result = await summarize_text(extracted_text, summary_length)
    except SummarizationError:
        raise
    except Exception as exc:
        logger.error(f"Service: unexpected error summarising URL '{url}' – user={user_id}: {exc}")
        raise SummarizationError(
            "Something went wrong while summarising the web page. Please try again."
        )

    result = _build_result(summary_result, summary_length, user_id)
    logger.info(f"Service: URL summarised – length={summary_length}, user={user_id}")
    return result


async def summarize_from_file(
    filename: str,
    contents: bytes,
    summary_length: str,
    user_id: str = "anonymous",
) -> dict:
    """Validate file size, extract text, and summarise a single file."""
    logger.info(f"Service: summarize_from_file called – file='{filename}', length={summary_length}, user={user_id}")
    _validate_summary_length(summary_length)
    _validate_file_size(contents)

    try:
        extracted_text = extract_text_from_file(filename, contents)
    except FileFormatError:
        raise  # already user-friendly
    except Exception as exc:
        logger.error(f"Service: failed to extract text from '{filename}' – user={user_id}: {exc}")
        raise FileFormatError(
            f"Could not read the file '{filename}'. "
            "Please ensure it is a valid PDF, DOCX, or TXT file."
        )

    try:
        summary_result = await summarize_text(extracted_text, summary_length)
    except SummarizationError:
        raise
    except Exception as exc:
        logger.error(
            f"Service: unexpected error summarising file '{filename}' – user={user_id}: {exc}"
        )
        raise SummarizationError(
            f"Something went wrong while summarising '{filename}'. Please try again."
        )

    result = _build_result(summary_result, summary_length, user_id)
    logger.info(f"Service: file '{filename}' summarised – length={summary_length}, user={user_id}")
    return result


async def summarize_batch(
    files: List[tuple[str, bytes]],
    summary_length: str,
    user_id: str = "anonymous",
) -> list[dict]:
    """Batch-summarise a list of (filename, contents) tuples.

    Returns a list of result dicts – each has either a summary or an error key.
    """
    if len(files) > config.MAX_BATCH_FILES:
        raise BatchLimitError()

    results: list[dict] = []
    for filename, contents in files:
        try:
            result = await summarize_from_file(filename, contents, summary_length, user_id)
            result["file"] = filename
            results.append(result)
        except FileSizeError:
            logger.warning(f"Service: batch – file '{filename}' exceeds size limit – user={user_id}")
            results.append({"file": filename, "error": "File exceeds 10 MB limit."})
        except FileFormatError as exc:
            logger.warning(f"Service: batch – unsupported file '{filename}' – user={user_id}: {exc}")
            results.append({"file": filename, "error": str(exc.message)})
        except SummarizationError as exc:
            logger.error(f"Service: batch – summarisation failed for '{filename}' – user={user_id}: {exc}")
            results.append({"file": filename, "error": str(exc.message)})
        except Exception as exc:
            logger.error(f"Service: batch – unexpected error for '{filename}' – user={user_id}: {exc}")
            results.append({"file": filename, "error": f"Failed to process '{filename}'. Please try again."})

    logger.info(f"Service: batch of {len(files)} files processed – user={user_id}")
    return results


# ---------------------------------------------------------------------------
# Private validation helpers
# ---------------------------------------------------------------------------

def _validate_summary_length(summary_length: str) -> None:
    """Raise ValueError if *summary_length* is not allowed."""
    if summary_length not in config.ALLOWED_SUMMARY_LENGTHS:
        raise ValueError(
            f"Invalid summary_length '{summary_length}'. "
            f"Choose one of: {', '.join(config.ALLOWED_SUMMARY_LENGTHS)}."
        )


def _validate_file_size(contents: bytes) -> None:
    """Raise FileSizeError if *contents* exceed the configured limit."""
    if len(contents) > config.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise FileSizeError()
