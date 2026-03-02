"""
Unit tests for summary history tracking.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app import api

client = TestClient(app)


class TestHistoryTracking:
    """Test that summaries are recorded in history."""

    def setup_method(self):
        """Clear history before each test."""
        api.summary_history.clear()

    def test_history_empty_initially(self):
        response = client.get("/api/history?user_id=testuser")
        assert response.status_code == 200
        data = response.json()
        assert data["history"] == []

    @patch("backend.app.api.summarize_text", new_callable=AsyncMock)
    def test_history_populated_after_summarize(self, mock_summarize):
        mock_summarize.return_value = "A test summary."
        client.post(
            "/api/summarize/text",
            json={"text": "Some text.", "summary_length": "short"},
        )

        response = client.get("/api/history?user_id=anonymous")
        data = response.json()
        assert len(data["history"]) >= 1
        assert data["history"][-1]["summary"] == "A test summary."
        assert data["history"][-1]["summary_length"] == "short"

    @patch("backend.app.api.summarize_text", new_callable=AsyncMock)
    def test_history_records_multiple(self, mock_summarize):
        mock_summarize.side_effect = ["Summary 1", "Summary 2"]
        client.post("/api/summarize/text", json={"text": "Text 1", "summary_length": "short"})
        client.post("/api/summarize/text", json={"text": "Text 2", "summary_length": "long"})

        response = client.get("/api/history?user_id=anonymous")
        data = response.json()
        assert len(data["history"]) >= 2

    def test_history_different_users(self):
        response1 = client.get("/api/history?user_id=user_a")
        response2 = client.get("/api/history?user_id=user_b")
        assert response1.json()["history"] == []
        assert response2.json()["history"] == []
