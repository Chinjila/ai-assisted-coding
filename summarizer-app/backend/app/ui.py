"""
Web UI backend – serves the dashboard, upload forms, and history views
using Jinja2 templates.

Routing only – all business logic is delegated to the summarizer service.
"""

from __future__ import annotations

import os
from typing import List

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.app import config
from backend.app.errors import SummarizerError
from backend.app.logger import get_logger, audit_log
from backend.app.summarizer import service as summarizer_service

router = APIRouter()
logger = get_logger()

# Jinja2 template directory
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard."""
    history = summarizer_service.get_history("ui_user")
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "history": history, "summary": None, "error": None, "batch_results": None},
    )


@router.post("/summarize", response_class=HTMLResponse)
async def ui_summarize(
    request: Request,
    text: str = Form(None),
    url: str = Form(None),
    file: UploadFile = File(None),
    summary_length: str = Form(config.DEFAULT_SUMMARY_LENGTH),
):
    """Handle summarisation from the web UI form."""
    error = None
    summary = None
    user_id = "ui_user"

    try:
        if file and file.filename:
            contents = await file.read()
            result = await summarizer_service.summarize_from_file(
                filename=file.filename,
                contents=contents,
                summary_length=summary_length,
                user_id=user_id,
            )
        elif url:
            result = await summarizer_service.summarize_from_url(
                url=url,
                summary_length=summary_length,
                user_id=user_id,
            )
        elif text:
            result = await summarizer_service.summarize_from_text(
                text=text,
                summary_length=summary_length,
                user_id=user_id,
            )
        else:
            error = "Please provide text, a URL, or upload a file."
            history = summarizer_service.get_history(user_id)
            return templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "history": history, "summary": None, "error": error, "batch_results": None},
            )

        summary = result["summary"]
        logger.info(f"UI summarisation completed – length={summary_length}")
    except SummarizerError as exc:
        error = exc.message
        logger.error(f"UI summarisation error: {error}")
    except ValueError as exc:
        error = str(exc)
        logger.warning(f"UI validation error: {error}")
    except Exception as exc:
        error = "An unexpected error occurred. Please try again later."
        logger.error(f"UI unexpected error: {type(exc).__name__}: {exc}")

    history = summarizer_service.get_history(user_id)
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "history": history, "summary": summary, "error": error, "batch_results": None},
    )


@router.get("/history", response_class=HTMLResponse)
async def ui_history_page(request: Request):
    """Render the history page."""
    history = summarizer_service.get_history("ui_user")
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "history": history},
    )


@router.post("/batch", response_class=HTMLResponse)
async def ui_batch_upload(
    request: Request,
    files: List[UploadFile] = File(...),
    summary_length: str = Form(config.DEFAULT_SUMMARY_LENGTH),
):
    """Handle batch file upload from the web UI.

    All actions and errors are logged for audit and debugging.
    Returns results per file with user-friendly error messages.
    """
    user_id = "ui_user"
    batch_results = []
    error = None

    audit_log(
        action="ui_batch_request",
        user_id=user_id,
        details=f"file_count={len(files)}, summary_length={summary_length}",
    )

    # Read all uploaded files
    file_tuples = []
    for f in files:
        if f and f.filename:
            contents = await f.read()
            file_tuples.append((f.filename, contents))

    if not file_tuples:
        error = "Please upload at least one file for batch processing."
        audit_log(
            action="ui_batch_error",
            user_id=user_id,
            error=error,
            level="WARNING",
        )
        history = summarizer_service.get_history(user_id)
        return templates.TemplateResponse(
            "dashboard.html",
            {
                "request": request,
                "history": history,
                "summary": None,
                "error": error,
                "batch_results": None,
            },
        )

    try:
        batch_results = await summarizer_service.summarize_batch(
            files=file_tuples,
            summary_length=summary_length,
            user_id=user_id,
        )
        succeeded = sum(1 for r in batch_results if "error" not in r)
        failed = sum(1 for r in batch_results if "error" in r)
        audit_log(
            action="ui_batch_complete",
            user_id=user_id,
            details=f"total={len(batch_results)}, succeeded={succeeded}, failed={failed}",
        )
        logger.info(
            f"UI batch completed – {succeeded} succeeded, {failed} failed, "
            f"length={summary_length}"
        )
    except SummarizerError as exc:
        error = exc.message
        audit_log(
            action="ui_batch_error",
            user_id=user_id,
            error=error,
            level="ERROR",
        )
        logger.error(f"UI batch error: {error}")
    except Exception as exc:
        error = "An unexpected error occurred during batch processing. Please try again later."
        audit_log(
            action="ui_batch_error",
            user_id=user_id,
            error=f"{type(exc).__name__}: {exc}",
            level="ERROR",
        )
        logger.error(f"UI batch unexpected error: {type(exc).__name__}: {exc}")

    history = summarizer_service.get_history(user_id)
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "history": history,
            "summary": None,
            "error": error,
            "batch_results": batch_results if batch_results else None,
        },
    )
