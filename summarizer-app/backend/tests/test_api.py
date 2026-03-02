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

    @patch("backend.app.api.summarize_text", new_callable=AsyncMock)
    def test_summarize_text_success(self, mock_summarize):
        mock_summarize.return_value = "This is a summary."
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

    @patch("backend.app.api.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.api.extract_text_from_url")
    def test_summarize_url_success(self, mock_extract, mock_summarize):
        mock_extract.return_value = "Extracted web text."
        mock_summarize.return_value = "URL summary."
        response = client.post(
            "/api/summarize/url",
            json={"url": "https://example.com", "summary_length": "medium"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "URL summary."


class TestSummarizeFileEndpoint:
    """Tests for /api/summarize/file."""

    @patch("backend.app.api.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.api.extract_text_from_file")
    def test_summarize_file_success(self, mock_extract, mock_summarize):
        mock_extract.return_value = "File content text."
        mock_summarize.return_value = "File summary."
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

    @patch("backend.app.api.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.api.extract_text_from_file")
    def test_batch_summarize_success(self, mock_extract, mock_summarize):
        mock_extract.return_value = "Extracted text."
        mock_summarize.return_value = "Batch summary."
        files = [
            ("files", ("file1.txt", b"Content 1", "text/plain")),
            ("files", ("file2.txt", b"Content 2", "text/plain")),
        ]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["results"]) == 2

    def test_batch_exceeds_limit(self):
        files = [("files", (f"file{i}.txt", b"Content", "text/plain")) for i in range(11)]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 400


class TestHistoryEndpoint:
    """Tests for /api/history."""

    def test_get_history(self):
        response = client.get("/api/history?user_id=anonymous")
        assert response.status_code == 200
        data = response.json()
        assert "history" in data
        assert data["success"] is True
