"""
REST API endpoints for summarisation, batch processing, history, and auth.

Routing only – all business logic is delegated to the summarizer service.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from jose import JWTError, jwt
from pydantic import BaseModel

from backend.app import config
from backend.app.errors import AuthenticationError, SummarizerError
from backend.app.logger import get_logger, audit_log
from backend.app.summarizer import service as summarizer_service

router = APIRouter()
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
    try:
        result = await summarizer_service.summarize_from_text(
            text=request.text, summary_length=request.summary_length,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SummarizerError as exc:
        logger.error(f"API /summarize/text failed: {exc.message}")
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return SummaryResponse(**result)


@router.post("/summarize/url", response_model=SummaryResponse)
async def summarize_url(request: URLSummarizeRequest):
    """Summarise content from a web URL."""
    try:
        result = await summarizer_service.summarize_from_url(
            url=request.url, summary_length=request.summary_length,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SummarizerError as exc:
        logger.error(f"API /summarize/url failed: {exc.message}")
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return SummaryResponse(**result)


@router.post("/summarize/file", response_model=SummaryResponse)
async def summarize_file(
    file: UploadFile = File(...),
    summary_length: str = Form(config.DEFAULT_SUMMARY_LENGTH),
):
    """Summarise an uploaded file (PDF, DOCX, or TXT)."""
    contents = await file.read()
    try:
        result = await summarizer_service.summarize_from_file(
            filename=file.filename or "file.txt",
            contents=contents,
            summary_length=summary_length,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except SummarizerError as exc:
        logger.error(f"API /summarize/file failed: {exc.message}")
        raise HTTPException(status_code=exc.status_code, detail=exc.message)
    return SummaryResponse(**result)


@router.post("/summarize/batch")
async def summarize_batch(
    files: List[UploadFile] = File(...),
    summary_length: str = Form(config.DEFAULT_SUMMARY_LENGTH),
    user_id: str = Form("anonymous"),
):
    """Batch-summarise up to 10 files.

    All actions and errors are logged for audit and debugging.
    Returns per-file results with user-friendly error messages.
    """
    file_tuples = []
    filenames = []
    for file in files:
        contents = await file.read()
        fname = file.filename or "file.txt"
        file_tuples.append((fname, contents))
        filenames.append(fname)

    audit_log(
        action="api_batch_request",
        user_id=user_id,
        details=f"file_count={len(files)}, files={filenames}, summary_length={summary_length}",
    )

    try:
        results = await summarizer_service.summarize_batch(
            files=file_tuples, summary_length=summary_length, user_id=user_id,
        )
    except SummarizerError as exc:
        logger.error(f"API /summarize/batch failed: {exc.message}")
        audit_log(
            action="api_batch_error",
            user_id=user_id,
            error=exc.message,
            level="ERROR",
        )
        raise HTTPException(status_code=exc.status_code, detail=exc.message)

    succeeded = sum(1 for r in results if "error" not in r)
    failed = sum(1 for r in results if "error" in r)
    audit_log(
        action="api_batch_response",
        user_id=user_id,
        details=f"total={len(results)}, succeeded={succeeded}, failed={failed}",
    )
    return {
        "results": results,
        "total": len(results),
        "succeeded": succeeded,
        "failed": failed,
        "success": True,
    }


@router.get("/history")
async def get_history(user_id: str = "anonymous"):
    """Retrieve summary history for a user."""
    history = summarizer_service.get_history(user_id)
    return {"user_id": user_id, "history": history, "success": True}
