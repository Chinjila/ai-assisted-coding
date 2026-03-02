"""
Unit tests for the Batch Processing feature.

Covers:
  - API batch endpoint with audit logging and user-friendly errors
  - UI batch upload route
  - Service-layer batch orchestration with structured audit logs
  - Audit log output (timestamp, user_id, action, error details)
  - Edge cases: empty batch, limit exceeded, partial failures
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.summarizer import service as summarizer_service
from backend.app.errors import (
    BatchLimitError,
    FileFormatError,
    FileSizeError,
    SummarizationError,
)

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_history():
    """Ensure every test starts with a clean history store."""
    summarizer_service.clear_history()
    yield
    summarizer_service.clear_history()


# ---------------------------------------------------------------------------
# API Batch Endpoint Tests
# ---------------------------------------------------------------------------

class TestAPIBatchEndpoint:
    """Tests for POST /api/summarize/batch."""

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_success_returns_counts(self, mock_batch):
        """Successful batch returns results with succeeded/failed counts."""
        mock_batch.return_value = [
            {"file": "a.txt", "summary": "Sum A", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
            {"file": "b.txt", "summary": "Sum B", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
        ]
        files = [
            ("files", ("a.txt", b"Content A", "text/plain")),
            ("files", ("b.txt", b"Content B", "text/plain")),
        ]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["total"] == 2
        assert data["succeeded"] == 2
        assert data["failed"] == 0
        assert len(data["results"]) == 2

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_partial_failure_counts(self, mock_batch):
        """Partial failure returns correct succeeded/failed counts."""
        mock_batch.return_value = [
            {"file": "good.txt", "summary": "Summary", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
            {"file": "bad.png", "error": "Unsupported file format: .png"},
        ]
        files = [
            ("files", ("good.txt", b"Content", "text/plain")),
            ("files", ("bad.png", b"\x89PNG", "image/png")),
        ]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        data = response.json()
        assert data["succeeded"] == 1
        assert data["failed"] == 1
        assert data["total"] == 2

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_limit_exceeded_returns_friendly_error(self, mock_batch):
        """Exceeding batch limit returns user-friendly error."""
        mock_batch.side_effect = BatchLimitError()
        files = [("files", (f"file{i}.txt", b"x", "text/plain")) for i in range(11)]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 400
        data = response.json()
        assert "10 files" in data["detail"]

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_accepts_user_id(self, mock_batch):
        """Batch endpoint passes user_id to service layer."""
        mock_batch.return_value = [
            {"file": "a.txt", "summary": "Sum", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
        ]
        files = [("files", ("a.txt", b"Content", "text/plain"))]
        response = client.post(
            "/api/summarize/batch",
            files=files,
            data={"summary_length": "short", "user_id": "testuser"},
        )
        assert response.status_code == 200
        mock_batch.assert_called_once()
        _, kwargs = mock_batch.call_args
        assert kwargs.get("user_id") == "testuser" or mock_batch.call_args[1].get("user_id") == "testuser"

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_all_files_fail(self, mock_batch):
        """When all files fail, response still succeeds with error entries."""
        mock_batch.return_value = [
            {"file": "bad1.png", "error": "Unsupported format"},
            {"file": "bad2.bmp", "error": "Unsupported format"},
        ]
        files = [
            ("files", ("bad1.png", b"\x89PNG", "image/png")),
            ("files", ("bad2.bmp", b"\x00", "image/bmp")),
        ]
        response = client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        data = response.json()
        assert data["succeeded"] == 0
        assert data["failed"] == 2


# ---------------------------------------------------------------------------
# API Batch Audit Logging Tests
# ---------------------------------------------------------------------------

class TestAPIBatchAuditLogging:
    """Tests that API batch endpoint emits audit logs."""

    @patch("backend.app.api.audit_log")
    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_request_audit_logged(self, mock_batch, mock_audit):
        """Batch request emits audit log with action and user_id."""
        mock_batch.return_value = [
            {"file": "a.txt", "summary": "Sum", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
        ]
        files = [("files", ("a.txt", b"Content", "text/plain"))]
        client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        audit_calls = [c for c in mock_audit.call_args_list if c[1].get("action", c[0][0] if c[0] else "") == "api_batch_request"]
        assert len(audit_calls) >= 1

    @patch("backend.app.api.audit_log")
    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_response_audit_logged(self, mock_batch, mock_audit):
        """Batch response emits audit log with success/failure counts."""
        mock_batch.return_value = [
            {"file": "a.txt", "summary": "Sum", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
        ]
        files = [("files", ("a.txt", b"Content", "text/plain"))]
        client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        audit_calls = [c for c in mock_audit.call_args_list if c[1].get("action", c[0][0] if c[0] else "") == "api_batch_response"]
        assert len(audit_calls) >= 1

    @patch("backend.app.api.audit_log")
    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_batch_error_audit_logged(self, mock_batch, mock_audit):
        """Batch error emits audit log with error details."""
        mock_batch.side_effect = BatchLimitError()
        files = [("files", (f"f{i}.txt", b"x", "text/plain")) for i in range(11)]
        client.post("/api/summarize/batch", files=files, data={"summary_length": "short"})
        audit_calls = [c for c in mock_audit.call_args_list if c[1].get("action", c[0][0] if c[0] else "") == "api_batch_error"]
        assert len(audit_calls) >= 1


# ---------------------------------------------------------------------------
# Service Batch Audit Logging Tests
# ---------------------------------------------------------------------------

class TestServiceBatchAuditLogging:
    """Tests that service-layer batch processing emits structured audit logs."""

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.audit_log")
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_start_audit(self, mock_extract, mock_engine, mock_audit):
        """Batch start emits audit log with file_count and user_id."""
        mock_extract.return_value = "text"
        mock_engine.return_value = "summary"
        await summarizer_service.summarize_batch(
            [("a.txt", b"a")], "short", user_id="u1"
        )
        start_calls = [
            c for c in mock_audit.call_args_list
            if c[1].get("action", c[0][0] if c[0] else "") == "batch_start"
        ]
        assert len(start_calls) == 1
        assert start_calls[0][1]["user_id"] == "u1"

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.audit_log")
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_complete_audit(self, mock_extract, mock_engine, mock_audit):
        """Batch complete emits audit log with success/error counts."""
        mock_extract.return_value = "text"
        mock_engine.return_value = "summary"
        await summarizer_service.summarize_batch(
            [("a.txt", b"a"), ("b.txt", b"b")], "short", user_id="u1"
        )
        complete_calls = [
            c for c in mock_audit.call_args_list
            if c[1].get("action", c[0][0] if c[0] else "") == "batch_complete"
        ]
        assert len(complete_calls) == 1
        assert "success=2" in complete_calls[0][1].get("details", "")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.audit_log")
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_per_file_audit(self, mock_extract, mock_engine, mock_audit):
        """Each file in batch emits process and success audit logs."""
        mock_extract.return_value = "text"
        mock_engine.return_value = "summary"
        await summarizer_service.summarize_batch(
            [("a.txt", b"a"), ("b.txt", b"b")], "short"
        )
        process_calls = [
            c for c in mock_audit.call_args_list
            if c[1].get("action", c[0][0] if c[0] else "") == "batch_file_process"
        ]
        success_calls = [
            c for c in mock_audit.call_args_list
            if c[1].get("action", c[0][0] if c[0] else "") == "batch_file_success"
        ]
        assert len(process_calls) == 2
        assert len(success_calls) == 2

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.audit_log")
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_file_error_audit(self, mock_extract, mock_engine, mock_audit):
        """Failed files in batch emit error audit logs."""
        def extract_side_effect(filename, contents):
            if filename == "bad.png":
                raise FileFormatError("Unsupported file format: .png")
            return "text"

        mock_extract.side_effect = extract_side_effect
        mock_engine.return_value = "summary"
        await summarizer_service.summarize_batch(
            [("good.txt", b"ok"), ("bad.png", b"\x89PNG")], "short", user_id="u1"
        )
        error_calls = [
            c for c in mock_audit.call_args_list
            if c[1].get("action", c[0][0] if c[0] else "") == "batch_file_error"
        ]
        assert len(error_calls) == 1
        assert "bad.png" in error_calls[0][1].get("error", "")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.audit_log")
    async def test_batch_rejected_audit(self, mock_audit):
        """Exceeding batch limit emits rejection audit log."""
        files = [(f"f{i}.txt", b"x") for i in range(11)]
        with pytest.raises(BatchLimitError):
            await summarizer_service.summarize_batch(files, "short", user_id="u1")
        rejected_calls = [
            c for c in mock_audit.call_args_list
            if c[1].get("action", c[0][0] if c[0] else "") == "batch_rejected"
        ]
        assert len(rejected_calls) == 1
        assert "u1" in rejected_calls[0][1].get("user_id", "")


# ---------------------------------------------------------------------------
# UI Batch Upload Tests
# ---------------------------------------------------------------------------

class TestUIBatchUpload:
    """Tests for POST /batch (UI batch upload route)."""

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_ui_batch_success(self, mock_batch):
        """UI batch upload returns HTML with results."""
        mock_batch.return_value = [
            {"file": "a.txt", "summary": "Sum A", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
        ]
        files = [("files", ("a.txt", b"Content A", "text/plain"))]
        response = client.post("/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        assert "Sum A" in response.text

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_ui_batch_error_shows_message(self, mock_batch):
        """UI batch error shows user-friendly message in HTML."""
        mock_batch.side_effect = BatchLimitError()
        files = [("files", (f"f{i}.txt", b"x", "text/plain")) for i in range(11)]
        response = client.post("/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        assert "10 files" in response.text

    @patch("backend.app.summarizer.service.summarize_batch", new_callable=AsyncMock)
    def test_ui_batch_partial_failure_shows_errors(self, mock_batch):
        """Partial batch failure shows per-file errors in HTML."""
        mock_batch.return_value = [
            {"file": "good.txt", "summary": "Summary", "summary_length": "short", "timestamp": "2025-01-01T00:00:00"},
            {"file": "bad.png", "error": "Unsupported file format: .png"},
        ]
        files = [
            ("files", ("good.txt", b"Content", "text/plain")),
            ("files", ("bad.png", b"\x89PNG", "image/png")),
        ]
        response = client.post("/batch", files=files, data={"summary_length": "short"})
        assert response.status_code == 200
        assert "Summary" in response.text
        assert "Unsupported file format" in response.text


# ---------------------------------------------------------------------------
# Audit Log Function Tests
# ---------------------------------------------------------------------------

class TestAuditLogFunction:
    """Tests for the audit_log utility in logger.py."""

    @patch("backend.app.logger.logger")
    def test_audit_log_info(self, mock_logger):
        """audit_log emits an INFO-level log with correct structure."""
        from backend.app.logger import audit_log
        bound = MagicMock()
        mock_logger.bind.return_value = bound

        audit_log(
            action="batch_start",
            user_id="test_user",
            details="file_count=2",
        )

        mock_logger.bind.assert_called_with(user_id="test_user")
        bound.info.assert_called_once()
        log_msg = bound.info.call_args[0][0]
        assert "AUDIT" in log_msg
        assert "batch_start" in log_msg
        assert "test_user" in log_msg
        assert "file_count=2" in log_msg

    @patch("backend.app.logger.logger")
    def test_audit_log_error(self, mock_logger):
        """audit_log emits an ERROR-level log when level='ERROR'."""
        from backend.app.logger import audit_log
        bound = MagicMock()
        mock_logger.bind.return_value = bound

        audit_log(
            action="batch_file_error",
            user_id="u1",
            error="File exceeds limit",
            level="ERROR",
        )

        bound.error.assert_called_once()
        log_msg = bound.error.call_args[0][0]
        assert "AUDIT" in log_msg
        assert "batch_file_error" in log_msg
        assert "File exceeds limit" in log_msg

    @patch("backend.app.logger.logger")
    def test_audit_log_contains_timestamp(self, mock_logger):
        """audit_log message includes a timestamp field."""
        from backend.app.logger import audit_log
        bound = MagicMock()
        mock_logger.bind.return_value = bound

        audit_log(action="test_action", user_id="u1")

        bound.info.assert_called_once()
        log_msg = bound.info.call_args[0][0]
        assert "timestamp=" in log_msg

    @patch("backend.app.logger.logger")
    def test_audit_log_warning_level(self, mock_logger):
        """audit_log emits a WARNING-level log when level='WARNING'."""
        from backend.app.logger import audit_log
        bound = MagicMock()
        mock_logger.bind.return_value = bound

        audit_log(
            action="batch_rejected",
            user_id="u1",
            error="Limit exceeded",
            level="WARNING",
        )

        bound.warning.assert_called_once()
