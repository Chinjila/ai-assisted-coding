"""
Web UI backend – serves the dashboard, upload forms, and history views
using Jinja2 templates. Communicates with the summariser engine directly.
"""

from __future__ import annotations

import os
from datetime import datetime

from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from backend.app import config
from backend.app.errors import FileSizeError
from backend.app.logger import get_logger
from backend.app.summarizer.engine import summarize_text
from backend.app.summarizer.utils import extract_text_from_file, extract_text_from_url

router = APIRouter()
logger = get_logger()

# Jinja2 template directory
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "templates")
templates = Jinja2Templates(directory=TEMPLATE_DIR)

# In-memory history for the UI (shared with the demo)
ui_history: list[dict] = []


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Render the main dashboard."""
    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "history": ui_history, "summary": None, "error": None},
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

    try:
        if file and file.filename:
            contents = await file.read()
            if len(contents) > config.MAX_FILE_SIZE_MB * 1024 * 1024:
                raise FileSizeError()
            extracted = extract_text_from_file(file.filename, contents)
        elif url:
            extracted = extract_text_from_url(url)
        elif text:
            extracted = text
        else:
            error = "Please provide text, a URL, or upload a file."
            return templates.TemplateResponse(
                "dashboard.html",
                {"request": request, "history": ui_history, "summary": None, "error": error},
            )

        summary = await summarize_text(extracted, summary_length)
        ui_history.insert(
            0,
            {
                "summary": summary,
                "summary_length": summary_length,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )
        logger.info(f"UI summarisation completed – length={summary_length}")
    except Exception as exc:
        error = str(exc)
        logger.error(f"UI summarisation error: {error}")

    return templates.TemplateResponse(
        "dashboard.html",
        {"request": request, "history": ui_history, "summary": summary, "error": error},
    )


@router.get("/history", response_class=HTMLResponse)
async def ui_history_page(request: Request):
    """Render the history page."""
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "history": ui_history},
    )
