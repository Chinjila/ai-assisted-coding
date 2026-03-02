"""
Custom error classes and handlers for GenAIsummarizer.
Provides user-friendly error messages for API and UI.
"""

from fastapi import Request
from fastapi.responses import JSONResponse


class SummarizerError(Exception):
    """Base exception for GenAIsummarizer."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class FileFormatError(SummarizerError):
    """Raised when an unsupported or corrupted file is uploaded."""

    def __init__(self, message: str = "Unsupported or corrupted file format."):
        super().__init__(message=message, status_code=400)


class FileSizeError(SummarizerError):
    """Raised when an uploaded file exceeds the maximum size."""

    def __init__(self, message: str = "File size exceeds the 10MB limit."):
        super().__init__(message=message, status_code=413)


class BatchLimitError(SummarizerError):
    """Raised when batch processing limit is exceeded."""

    def __init__(self, message: str = "Batch processing limit is 10 files per request."):
        super().__init__(message=message, status_code=400)


class SummarizationError(SummarizerError):
    """Raised when summarization fails."""

    def __init__(self, message: str = "Summarization failed. Please try again."):
        super().__init__(message=message, status_code=500)


class AuthenticationError(SummarizerError):
    """Raised for authentication / JWT errors."""

    def __init__(self, message: str = "Authentication failed. Please provide a valid token."):
        super().__init__(message=message, status_code=401)


class URLFetchError(SummarizerError):
    """Raised when fetching a URL fails."""

    def __init__(self, message: str = "Failed to fetch content from the provided URL."):
        super().__init__(message=message, status_code=400)


# FastAPI exception handlers
async def summarizer_error_handler(request: Request, exc: SummarizerError):
    """Handle custom SummarizerError exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "success": False},
    )


async def generic_error_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "An unexpected error occurred. Please try again later.",
            "success": False,
        },
    )
