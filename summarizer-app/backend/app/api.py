"""
REST API endpoints for summarisation, batch processing, history, and auth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from jose import JWTError, jwt
from pydantic import BaseModel

from backend.app import config
from backend.app.errors import (
    AuthenticationError,
    BatchLimitError,
    FileSizeError,
)
from backend.app.logger import get_logger
from backend.app.summarizer.engine import summarize_text
from backend.app.summarizer.utils import extract_text_from_file, extract_text_from_url

router = APIRouter()

# ---------------------------------------------------------------------------
# In-memory stores (replace with a database for production)
# ---------------------------------------------------------------------------
summary_history: dict[str, list] = {}  # user_id -> [summaries]

logger = get_logger()


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class TextSummarizeRequest(BaseModel):
    text: str
    summary_length: str = config.DEFAULT_SUMMARY_LENGTH


class URLSummarizeRequest(BaseModel):
    url: str
    summary_length: str = config.DEFAULT_SUMMARY_LENGTH


class TokenRequest(BaseModel):
    username: str
    password: str


class SummaryResponse(BaseModel):
    summary: str
    summary_length: str
    timestamp: str
    success: bool = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def create_access_token(data: dict) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=config.JWT_EXPIRATION_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, config.JWT_SECRET_KEY, algorithm=config.JWT_ALGORITHM)


def verify_token(token: str) -> dict:
    """Verify and decode a JWT token."""
    try:
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise AuthenticationError()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/token", response_model=TokenResponse)
async def get_token(request: TokenRequest):
    """Issue a JWT token (demo – accepts any credentials)."""
    token = create_access_token({"sub": request.username})
    logger.info(f"Token issued for user: {request.username}")
    return TokenResponse(access_token=token)


@router.post("/summarize/text", response_model=SummaryResponse)
async def summarize_plain_text(request: TextSummarizeRequest):
    """Summarise plain text input."""
    if request.summary_length not in config.ALLOWED_SUMMARY_LENGTHS:
        raise HTTPException(status_code=400, detail="Invalid summary_length. Choose short, medium, or long.")

    summary = await summarize_text(request.text, request.summary_length)
    timestamp = datetime.utcnow().isoformat()

    # Store in history
    user_id = "anonymous"
    summary_history.setdefault(user_id, []).append(
        {"summary": summary, "summary_length": request.summary_length, "timestamp": timestamp}
    )

    return SummaryResponse(summary=summary, summary_length=request.summary_length, timestamp=timestamp)


@router.post("/summarize/url", response_model=SummaryResponse)
async def summarize_url(request: URLSummarizeRequest):
    """Summarise content from a web URL."""
    if request.summary_length not in config.ALLOWED_SUMMARY_LENGTHS:
        raise HTTPException(status_code=400, detail="Invalid summary_length. Choose short, medium, or long.")

    text = extract_text_from_url(request.url)
    summary = await summarize_text(text, request.summary_length)
    timestamp = datetime.utcnow().isoformat()

    user_id = "anonymous"
    summary_history.setdefault(user_id, []).append(
        {"summary": summary, "summary_length": request.summary_length, "timestamp": timestamp}
    )

    return SummaryResponse(summary=summary, summary_length=request.summary_length, timestamp=timestamp)


@router.post("/summarize/file", response_model=SummaryResponse)
async def summarize_file(
    file: UploadFile = File(...),
    summary_length: str = Form(config.DEFAULT_SUMMARY_LENGTH),
):
    """Summarise an uploaded file (PDF, DOCX, or TXT)."""
    if summary_length not in config.ALLOWED_SUMMARY_LENGTHS:
        raise HTTPException(status_code=400, detail="Invalid summary_length. Choose short, medium, or long.")

    contents = await file.read()
    if len(contents) > config.MAX_FILE_SIZE_MB * 1024 * 1024:
        raise FileSizeError()

    text = extract_text_from_file(file.filename or "file.txt", contents)
    summary = await summarize_text(text, summary_length)
    timestamp = datetime.utcnow().isoformat()

    user_id = "anonymous"
    summary_history.setdefault(user_id, []).append(
        {"summary": summary, "summary_length": summary_length, "timestamp": timestamp}
    )

    return SummaryResponse(summary=summary, summary_length=summary_length, timestamp=timestamp)


@router.post("/summarize/batch")
async def summarize_batch(
    files: List[UploadFile] = File(...),
    summary_length: str = Form(config.DEFAULT_SUMMARY_LENGTH),
):
    """Batch-summarise up to 10 files."""
    if len(files) > config.MAX_BATCH_FILES:
        raise BatchLimitError()

    results = []
    for file in files:
        contents = await file.read()
        if len(contents) > config.MAX_FILE_SIZE_MB * 1024 * 1024:
            results.append({"file": file.filename, "error": "File exceeds 10MB limit."})
            continue
        text = extract_text_from_file(file.filename or "file.txt", contents)
        summary = await summarize_text(text, summary_length)
        timestamp = datetime.utcnow().isoformat()
        results.append(
            {"file": file.filename, "summary": summary, "summary_length": summary_length, "timestamp": timestamp}
        )

    return {"results": results, "success": True}


@router.get("/history")
async def get_history(user_id: str = "anonymous"):
    """Retrieve summary history for a user."""
    history = summary_history.get(user_id, [])
    return {"user_id": user_id, "history": history, "success": True}
