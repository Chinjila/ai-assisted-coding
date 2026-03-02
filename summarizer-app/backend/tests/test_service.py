"""
Unit tests for the summarizer service layer.

Covers every feature from feature-request.md at the service boundary:
  1. Multi-format input parsing (text, PDF, DOCX, URL)
  2. Configurable summary length (short / medium / long + invalid)
  3. Retry logic pass-through & error handling
  4. Batch processing (success, partial failure, limit exceeded)
  5. History recording and isolation per user
  6. User-friendly error messages for every failure mode
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.app.summarizer import service as summarizer_service
from backend.app.errors import (
    BatchLimitError,
    FileFormatError,
    FileSizeError,
    SummarizationError,
    URLFetchError,
)


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
# 1. Multi-format input parsing – plain text
# ---------------------------------------------------------------------------

class TestSummarizeFromText:
    """Service: summarize_from_text – plain text input."""

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_text_returns_correct_keys(self, mock_engine):
        mock_engine.return_value = "Short summary."
        result = await summarizer_service.summarize_from_text(
            text="Hello world", summary_length="short", user_id="u1",
        )
        assert result["summary"] == "Short summary."
        assert result["summary_length"] == "short"
        assert "timestamp" in result

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_text_records_history(self, mock_engine):
        mock_engine.return_value = "A summary."
        await summarizer_service.summarize_from_text("Some text", "medium", user_id="u1")
        history = summarizer_service.get_history("u1")
        assert len(history) == 1
        assert history[0]["summary"] == "A summary."

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_text_propagates_summarization_error(self, mock_engine):
        """SummarizationError from the engine surfaces unchanged."""
        mock_engine.side_effect = SummarizationError("temporarily unavailable")
        with pytest.raises(SummarizationError, match="temporarily unavailable"):
            await summarizer_service.summarize_from_text("txt", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_text_wraps_unexpected_error(self, mock_engine):
        """Unexpected exceptions are wrapped in a user-friendly SummarizationError."""
        mock_engine.side_effect = RuntimeError("kaboom")
        with pytest.raises(SummarizationError, match="Something went wrong"):
            await summarizer_service.summarize_from_text("txt", "short")


# ---------------------------------------------------------------------------
# 1. Multi-format input parsing – URL
# ---------------------------------------------------------------------------

class TestSummarizeFromURL:
    """Service: summarize_from_url – web URL input."""

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_url")
    async def test_url_success(self, mock_extract, mock_engine):
        mock_extract.return_value = "Web page text."
        mock_engine.return_value = "URL summary."
        result = await summarizer_service.summarize_from_url(
            url="https://example.com", summary_length="medium",
        )
        assert result["summary"] == "URL summary."
        mock_extract.assert_called_once_with("https://example.com")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_url")
    async def test_url_records_history(self, mock_extract, mock_engine):
        mock_extract.return_value = "text"
        mock_engine.return_value = "sum"
        await summarizer_service.summarize_from_url("https://x.com", "short", user_id="u2")
        assert len(summarizer_service.get_history("u2")) == 1

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.extract_text_from_url")
    async def test_url_fetch_error_propagated(self, mock_extract):
        mock_extract.side_effect = URLFetchError("Failed to fetch URL: timeout")
        with pytest.raises(URLFetchError, match="Failed to fetch"):
            await summarizer_service.summarize_from_url("https://bad.url", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.extract_text_from_url")
    async def test_url_unexpected_extract_error_wrapped(self, mock_extract):
        """Non-URLFetchError during extraction is wrapped with a friendly message."""
        mock_extract.side_effect = RuntimeError("DNS failure")
        with pytest.raises(URLFetchError, match="Could not retrieve content"):
            await summarizer_service.summarize_from_url("https://bad.url", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_url")
    async def test_url_summarization_error_propagated(self, mock_extract, mock_engine):
        mock_extract.return_value = "page text"
        mock_engine.side_effect = SummarizationError("temporarily unavailable")
        with pytest.raises(SummarizationError, match="temporarily unavailable"):
            await summarizer_service.summarize_from_url("https://x.com", "short")


# ---------------------------------------------------------------------------
# 1. Multi-format input parsing – file (PDF, DOCX, TXT)
# ---------------------------------------------------------------------------

class TestSummarizeFromFile:
    """Service: summarize_from_file – uploaded file input."""

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_txt_file_success(self, mock_extract, mock_engine):
        mock_extract.return_value = "File text."
        mock_engine.return_value = "File summary."
        result = await summarizer_service.summarize_from_file(
            filename="notes.txt", contents=b"File text.",
            summary_length="short", user_id="u3",
        )
        assert result["summary"] == "File summary."
        mock_extract.assert_called_once_with("notes.txt", b"File text.")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_pdf_file_success(self, mock_extract, mock_engine):
        mock_extract.return_value = "PDF content."
        mock_engine.return_value = "PDF summary."
        result = await summarizer_service.summarize_from_file(
            filename="report.pdf", contents=b"%PDF-fake",
            summary_length="medium",
        )
        assert result["summary"] == "PDF summary."

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_docx_file_success(self, mock_extract, mock_engine):
        mock_extract.return_value = "DOCX content."
        mock_engine.return_value = "DOCX summary."
        result = await summarizer_service.summarize_from_file(
            filename="doc.docx", contents=b"PK\x03\x04fake",
            summary_length="long",
        )
        assert result["summary"] == "DOCX summary."

    @pytest.mark.asyncio
    async def test_unsupported_format_raises_file_format_error(self):
        """Unsupported file type raises FileFormatError with clear message."""
        with pytest.raises(FileFormatError):
            await summarizer_service.summarize_from_file(
                filename="image.png", contents=b"\x89PNG",
                summary_length="short",
            )

    @pytest.mark.asyncio
    async def test_oversized_file_raises_file_size_error(self):
        """File exceeding MAX_FILE_SIZE_MB raises FileSizeError."""
        huge = b"x" * (11 * 1024 * 1024)  # 11 MB
        with pytest.raises(FileSizeError):
            await summarizer_service.summarize_from_file(
                filename="big.txt", contents=huge, summary_length="short",
            )

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_corrupted_file_raises_file_format_error(self, mock_extract):
        """Corrupted file that passes extension check but fails parsing."""
        mock_extract.side_effect = FileFormatError("Error reading PDF file: ...")
        with pytest.raises(FileFormatError, match="Error reading PDF"):
            await summarizer_service.summarize_from_file(
                filename="corrupt.pdf", contents=b"not-a-pdf",
                summary_length="short",
            )

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_unexpected_extract_error_wrapped(self, mock_extract):
        """Non-FileFormatError during extraction is wrapped with friendly message."""
        mock_extract.side_effect = RuntimeError("out of memory")
        with pytest.raises(FileFormatError, match="Could not read the file"):
            await summarizer_service.summarize_from_file(
                filename="report.pdf", contents=b"%PDF",
                summary_length="short",
            )

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_file_records_history(self, mock_extract, mock_engine):
        mock_extract.return_value = "text"
        mock_engine.return_value = "summary"
        await summarizer_service.summarize_from_file(
            "f.txt", b"text", "short", user_id="u4",
        )
        assert len(summarizer_service.get_history("u4")) == 1

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_file_summarization_error_propagated(self, mock_extract, mock_engine):
        mock_extract.return_value = "text"
        mock_engine.side_effect = SummarizationError("API down")
        with pytest.raises(SummarizationError, match="API down"):
            await summarizer_service.summarize_from_file(
                "f.txt", b"text", "short",
            )


# ---------------------------------------------------------------------------
# 2. Configurable summary length
# ---------------------------------------------------------------------------

class TestConfigurableSummaryLength:
    """Service validates summary_length before calling the engine."""

    @pytest.mark.asyncio
    async def test_invalid_length_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid summary_length"):
            await summarizer_service.summarize_from_text("text", "extra_long")

    @pytest.mark.asyncio
    async def test_invalid_length_url(self):
        with pytest.raises(ValueError, match="Invalid summary_length"):
            await summarizer_service.summarize_from_url("https://x.com", "tiny")

    @pytest.mark.asyncio
    async def test_invalid_length_file(self):
        with pytest.raises(ValueError, match="Invalid summary_length"):
            await summarizer_service.summarize_from_file("f.txt", b"x", "huge")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_short_length_accepted(self, mock_engine):
        mock_engine.return_value = "Short."
        result = await summarizer_service.summarize_from_text("txt", "short")
        assert result["summary_length"] == "short"

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_medium_length_accepted(self, mock_engine):
        mock_engine.return_value = "Medium."
        result = await summarizer_service.summarize_from_text("txt", "medium")
        assert result["summary_length"] == "medium"

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_long_length_accepted(self, mock_engine):
        mock_engine.return_value = "Long."
        result = await summarizer_service.summarize_from_text("txt", "long")
        assert result["summary_length"] == "long"


# ---------------------------------------------------------------------------
# 3. Retry logic – service-level pass-through
# ---------------------------------------------------------------------------

class TestRetryPassThrough:
    """Verify the service propagates retry-related errors from engine."""

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_retries_exhausted_error_surfaces(self, mock_engine):
        """After engine exhausts retries, service re-raises the friendly error."""
        mock_engine.side_effect = SummarizationError(
            "The summarisation service is temporarily unavailable after 3 attempts. "
            "Please try again in a few moments."
        )
        with pytest.raises(SummarizationError, match="temporarily unavailable"):
            await summarizer_service.summarize_from_text("text", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_auth_error_surfaces(self, mock_engine):
        """Engine auth failure propagates as-is with user-friendly message."""
        mock_engine.side_effect = SummarizationError(
            "Authentication with Azure OpenAI failed. "
            "Please check your API key and endpoint configuration."
        )
        with pytest.raises(SummarizationError, match="Authentication.*failed"):
            await summarizer_service.summarize_from_text("text", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_no_history_recorded_on_failure(self, mock_engine):
        """Failed summarisation must not leave an entry in history."""
        mock_engine.side_effect = SummarizationError("fail")
        with pytest.raises(SummarizationError):
            await summarizer_service.summarize_from_text("text", "short", user_id="u1")
        assert summarizer_service.get_history("u1") == []

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_success_after_implicit_retries_records_history(self, mock_engine):
        """If engine succeeds (possibly after retries), history is recorded."""
        mock_engine.return_value = "OK after retry"
        await summarizer_service.summarize_from_text("text", "short", user_id="u1")
        assert len(summarizer_service.get_history("u1")) == 1


# ---------------------------------------------------------------------------
# 4. Batch processing
# ---------------------------------------------------------------------------

class TestSummarizeBatch:
    """Service: summarize_batch."""

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_success(self, mock_extract, mock_engine):
        mock_extract.return_value = "text"
        mock_engine.return_value = "batch sum"
        files = [("a.txt", b"a"), ("b.txt", b"b")]
        results = await summarizer_service.summarize_batch(files, "short")
        assert len(results) == 2
        assert all(r["summary"] == "batch sum" for r in results)
        assert results[0]["file"] == "a.txt"
        assert results[1]["file"] == "b.txt"

    @pytest.mark.asyncio
    async def test_batch_exceeds_limit_raises(self):
        files = [(f"f{i}.txt", b"x") for i in range(11)]
        with pytest.raises(BatchLimitError):
            await summarizer_service.summarize_batch(files, "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_partial_failure(self, mock_extract, mock_engine):
        """One bad file should not stop the rest – it gets an error entry."""
        def extract_side_effect(filename, contents):
            if filename == "bad.png":
                raise FileFormatError("Unsupported file format: .png")
            return "text"

        mock_extract.side_effect = extract_side_effect
        mock_engine.return_value = "summary"
        files = [("good.txt", b"ok"), ("bad.png", b"\x89PNG"), ("also_good.txt", b"ok")]
        results = await summarizer_service.summarize_batch(files, "short")
        assert len(results) == 3
        assert results[0]["summary"] == "summary"
        assert "error" in results[1]
        assert results[2]["summary"] == "summary"

    @pytest.mark.asyncio
    async def test_batch_oversized_file_gets_error_entry(self):
        """Oversized file in a batch gets an error entry, others continue."""
        huge = b"x" * (11 * 1024 * 1024)
        files = [("big.txt", huge)]

        # We need to mock engine since validation happens first, but for the
        # oversized file it will raise FileSizeError before reaching the engine.
        results = await summarizer_service.summarize_batch(files, "short")
        assert len(results) == 1
        assert "error" in results[0]
        assert "10 MB" in results[0]["error"]

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_records_history_per_file(self, mock_extract, mock_engine):
        mock_extract.return_value = "text"
        mock_engine.return_value = "sum"
        files = [("a.txt", b"a"), ("b.txt", b"b")]
        await summarizer_service.summarize_batch(files, "short", user_id="batch_user")
        assert len(summarizer_service.get_history("batch_user")) == 2

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_batch_engine_error_gives_friendly_message(self, mock_extract, mock_engine):
        """When the engine fails mid-batch, that file gets a friendly error."""
        mock_extract.return_value = "text"
        mock_engine.side_effect = SummarizationError("temporarily unavailable")
        files = [("f.txt", b"x")]
        results = await summarizer_service.summarize_batch(files, "short")
        assert "error" in results[0]
        assert "temporarily unavailable" in results[0]["error"]


# ---------------------------------------------------------------------------
# 5. History management
# ---------------------------------------------------------------------------

class TestHistoryManagement:
    """Service: get_history, clear_history, per-user isolation."""

    def test_empty_history_returns_empty_list(self):
        assert summarizer_service.get_history("new_user") == []

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_history_isolated_per_user(self, mock_engine):
        mock_engine.return_value = "s"
        await summarizer_service.summarize_from_text("t", "short", user_id="alice")
        await summarizer_service.summarize_from_text("t", "short", user_id="bob")
        assert len(summarizer_service.get_history("alice")) == 1
        assert len(summarizer_service.get_history("bob")) == 1

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_clear_history_removes_all(self, mock_engine):
        mock_engine.return_value = "s"
        await summarizer_service.summarize_from_text("t", "short", user_id="alice")
        summarizer_service.clear_history()
        assert summarizer_service.get_history("alice") == []

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_history_entry_contains_required_fields(self, mock_engine):
        mock_engine.return_value = "Some summary"
        await summarizer_service.summarize_from_text("txt", "long", user_id="u1")
        entry = summarizer_service.get_history("u1")[0]
        assert "summary" in entry
        assert "summary_length" in entry
        assert "timestamp" in entry
        assert entry["summary_length"] == "long"

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_history_default_user_is_anonymous(self, mock_engine):
        mock_engine.return_value = "s"
        await summarizer_service.summarize_from_text("t", "short")
        assert len(summarizer_service.get_history("anonymous")) == 1


# ---------------------------------------------------------------------------
# 6. User-friendly error messages
# ---------------------------------------------------------------------------

class TestUserFriendlyErrors:
    """Every failure mode returns a human-readable error message."""

    @pytest.mark.asyncio
    async def test_invalid_summary_length_message(self):
        with pytest.raises(ValueError, match="Choose one of"):
            await summarizer_service.summarize_from_text("txt", "xxx")

    @pytest.mark.asyncio
    async def test_file_size_error_message(self):
        huge = b"x" * (11 * 1024 * 1024)
        with pytest.raises(FileSizeError, match="10MB"):
            await summarizer_service.summarize_from_file("f.txt", huge, "short")

    @pytest.mark.asyncio
    async def test_batch_limit_error_message(self):
        files = [(f"f{i}.txt", b"x") for i in range(11)]
        with pytest.raises(BatchLimitError, match="10 files"):
            await summarizer_service.summarize_batch(files, "short")

    @pytest.mark.asyncio
    async def test_unsupported_format_error_message(self):
        with pytest.raises(FileFormatError, match="Unsupported"):
            await summarizer_service.summarize_from_file("img.bmp", b"\x00", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.extract_text_from_url")
    async def test_url_fetch_error_message(self, mock_extract):
        mock_extract.side_effect = URLFetchError("Failed to fetch URL: timeout")
        with pytest.raises(URLFetchError, match="Failed to fetch"):
            await summarizer_service.summarize_from_url("https://x.com", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    async def test_engine_unexpected_error_wrapped_text(self, mock_engine):
        mock_engine.side_effect = RuntimeError("segfault")
        with pytest.raises(SummarizationError, match="Something went wrong"):
            await summarizer_service.summarize_from_text("t", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_url")
    async def test_engine_unexpected_error_wrapped_url(self, mock_extract, mock_engine):
        mock_extract.return_value = "text"
        mock_engine.side_effect = RuntimeError("segfault")
        with pytest.raises(SummarizationError, match="Something went wrong"):
            await summarizer_service.summarize_from_url("https://x.com", "short")

    @pytest.mark.asyncio
    @patch("backend.app.summarizer.service.summarize_text", new_callable=AsyncMock)
    @patch("backend.app.summarizer.service.extract_text_from_file")
    async def test_engine_unexpected_error_wrapped_file(self, mock_extract, mock_engine):
        mock_extract.return_value = "text"
        mock_engine.side_effect = RuntimeError("segfault")
        with pytest.raises(SummarizationError, match="Something went wrong"):
            await summarizer_service.summarize_from_file("f.txt", b"x", "short")
