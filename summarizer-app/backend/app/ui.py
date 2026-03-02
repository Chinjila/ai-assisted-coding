"""
Web UI backend – serves the dashboard, upload forms, and history views
using Jinja2 templates.

Routing only – all business logic is delegated to the summarizer service.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.app import config
from backend.app.errors import SummarizerError
from backend.app.logger import get_logger
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
        {"request": request, "history": history, "summary": None, "error": None},
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
                {"request": request, "history": history, "summary": None, "error": error},
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
        {"request": request, "history": history, "summary": summary, "error": error},
    )


@router.get("/history", response_class=HTMLResponse)
async def ui_history_page(request: Request):
    """Render the history page."""
    history = summarizer_service.get_history("ui_user")
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "history": history},
    )
