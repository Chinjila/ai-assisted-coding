"""
Unit tests for REST API endpoints.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


class TestTokenEndpoint:
    """Tests for /api/token."""

    def test_get_token_success(self):
        response = client.post("/api/token", json={"username": "testuser", "password": "testpass"})
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"


class TestSummarizeTextEndpoint:
    """Tests for /api/summarize/text."""

    @patch("backend.app.summarizer.service.summarize_from_text", new_callable=AsyncMock)
    def test_summarize_text_success(self, mock_service):
        mock_service.return_value = {
            "summary": "This is a summary.",
            "summary_length": "short",
            "timestamp": "2025-01-01T00:00:00",
        }
        response = client.post(
            "/api/summarize/text",
            json={"text": "Some long text to summarize.", "summary_length": "short"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["summary"] == "This is a summary."
        assert data["summary_length"] == "short"

    def test_summarize_text_invalid_length(self):
        response = client.post(
            "/api/summarize/text",
            json={"text": "Some text.", "summary_length": "extra_long"},
        )
        assert response.status_code == 400


class TestSummarizeURLEndpoint:
    """Tests for /api/summarize/url."""

    @patch("backend.app.summarizer.service.summarize_from_url", new_callable=AsyncMock)
    def test_summarize_url_success(self, mock_service):
        mock_service.return_value = {
            "summary": "URL summary.",
            "summary_length": "medium",
            "timestamp": "2025-01-01T00:00:00",
        }
        response = client.post(
            "/api/summarize/url",
            json={"url": "https://example.com", "summary_length": "medium"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "URL summary."


class TestSummarizeFileEndpoint:
    """Tests for /api/summarize/file."""

    @patch("backend.app.summarizer.service.summarize_from_file", new_callable=AsyncMock)
    def test_summarize_file_success(self, mock_service):
        mock_service.return_value = {
            "summary": "File summary.",
            "summary_length": "short",
            "timestamp": "2025-01-01T00:00:00",
        }
        response = client.post(
            "/api/summarize/file",
            files={"file": ("test.txt", b"Some file content", "text/plain")},
            data={"summary_length": "short"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "File summary."


class TestBatchEndpoint:
    """Tests for /api/summarize/batch."""

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_summarize_success(self, mock_service):
        mock_service.return_value = [
            {"file": "file1.txt", "summary": "Summary 1", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
            {"file": "file2.txt", "summary": "Summary 2", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
        ]
        files = [
            ("files", ("file1.txt", b"Content 1", "text/plain")),
            ("files", ("file2.txt", b"Content 2", "text/plain")),
        ]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["results"]) == 2

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_exceeds_limit(self, mock_service):
        from backend.app.errors import BatchLimitError
        mock_service.side_effect = BatchLimitError()
        files = [("files", (f"file{i}.txt", b"Content", "text/plain")) for i in range(11)]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 400


class TestHistoryEndpoint:
    """Tests for /api/history."""

    @patch("backend.app.summarizer.service.get_history")
    def test_get_history(self, mock_history):
        mock_history.return_value = []
        response = client.get("/api/history?user_id=anonymous")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert data["success"] is True


class TestAPIErrorResponses:
    """Tests that API returns user-friendly error messages."""

    @patch("backend.app.summarizer.service.summarize_from_text", new_callable=AsyncMock)
    def test_summarization_error_returns_friendly_message(self, mock_service):
        from backend.app.errors import SummarizationError
        mock_service.side_effect = SummarizationError(
            "The summarisation service is temporarily unavailable after 3 attempts. "
            "Please try again in a few moments."
        )
        response = client.post(
            "/api/summarize/text",
            json={"text": "Some text.", "summary_length": "short"},
        )
        assert response.status_code == 500
        data = response.json()
        assert "temporarily unavailable" in data["detail"]

    @patch("backend.app.summarizer.service.summarize_from_url", new_callable=AsyncMock)
    def test_url_fetch_error_returns_friendly_message(self, mock_service):
        from backend.app.errors import URLFetchError
        mock_service.side_effect = URLFetchError(
            "Could not retrieve content from 'https://bad.url'. "
            "Please check the URL and try again."
        )
        response = client.post(
            "/api/summarize/url",
            json={"url": "https://bad.url", "summary_length": "short"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "Could not retrieve" in data["detail"]

    @patch("backend.app.summarizer.service.summarize_from_file", new_callable=AsyncMock)
    def test_file_format_error_returns_friendly_message(self, mock_service):
        from backend.app.errors import FileFormatError
        mock_service.side_effect = FileFormatError(
            "Could not read the file 'image.png'. "
            "Please ensure it is a valid PDF, DOCX, or TXT file."
        )
        response = client.post(
            "/api/summarize/file",
            files={"file": ("image.png", b"\x89PNG", "image/png")},
            data={"summary_length": "short"},
        )
        assert response.status_code == 400
        data = response.json()
        assert "Could not read the file" in data["detail"]
