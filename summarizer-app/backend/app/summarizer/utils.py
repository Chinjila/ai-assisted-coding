"""
Text extraction utilities – parse PDF, DOCX, plain text, and web URLs.
"""

from __future__ import annotations

import io
import requests
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader
from docx import Document

from backend.app.errors import FileFormatError, URLFetchError
from backend.app.logger import get_logger

logger = get_logger()

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".docx"}


def extract_text_from_file(filename: str, contents: bytes) -> str:
    """Extract text from an uploaded file based on its extension."""
    ext = _get_extension(filename)

    if ext == ".pdf":
        return _extract_pdf(contents)
    elif ext == ".docx":
        return _extract_docx(contents)
    elif ext == ".txt":
        return contents.decode("utf-8", errors="replace")
    else:
        raise FileFormatError(f"Unsupported file format: {ext}. Supported formats: PDF, DOCX, TXT.")


def extract_text_from_url(url: str) -> str:
    """Fetch and extract readable text from a web URL."""
    try:
        logger.info(f"Fetching URL: {url}")
        response = requests.get(url, timeout=15, headers={"User-Agent": "GenAIsummarizer/1.0"})
        response.raise_for_status()
    except requests.RequestException as exc:
        raise URLFetchError(f"Failed to fetch URL: {exc}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove scripts and styles
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator="\n", strip=True)
    if not text:
        raise URLFetchError("No readable text found at the provided URL.")
    return text


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _get_extension(filename: str) -> str:
    """Return the lowercase file extension."""
    import os
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _extract_pdf(contents: bytes) -> str:
    """Extract text from PDF bytes."""
    try:
        reader = PdfReader(io.BytesIO(contents))
        pages_text = [page.extract_text() or "" for page in reader.pages]
        text = "\n".join(pages_text).strip()
        if not text:
            raise FileFormatError("Could not extract text from the PDF. The file may be scanned or corrupted.")
        return text
    except FileFormatError:
        raise
    except Exception as exc:
        raise FileFormatError(f"Error reading PDF file: {exc}")


def _extract_docx(contents: bytes) -> str:
    """Extract text from DOCX bytes."""
    try:
        doc = Document(io.BytesIO(contents))
        text = "\n".join(para.text for para in doc.paragraphs).strip()
        if not text:
            raise FileFormatError("Could not extract text from the DOCX file.")
        return text
    except FileFormatError:
        raise
    except Exception as exc:
        raise FileFormatError(f"Error reading DOCX file: {exc}")
