"""
Unit tests for the summariser engine and text extraction utilities.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.app.summarizer.utils import (
    extract_text_from_file,
    extract_text_from_url,
    _get_extension,
)
from backend.app.summarizer.engine import summarize_text, _max_tokens_for_length
from backend.app.errors import FileFormatError, URLFetchError, SummarizationError


class TestGetExtension:
    def test_pdf(self):
        assert _get_extension("report.pdf") == ".pdf"

    def test_docx(self):
        assert _get_extension("doc.DOCX") == ".docx"

    def test_txt(self):
        assert _get_extension("notes.txt") == ".txt"

    def test_no_extension(self):
        assert _get_extension("README") == ""


class TestExtractTextFromFile:
    def test_txt_file(self):
        text = extract_text_from_file("test.txt", b"Hello, world!")
        assert text == "Hello, world!"

    def test_unsupported_format(self):
        with pytest.raises(FileFormatError):
            extract_text_from_file("image.png", b"\x89PNG")

    @patch("backend.app.summarizer.utils.PdfReader")
    def test_pdf_extraction(self, mock_reader_cls):
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "PDF content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_reader_cls.return_value = mock_reader

        text = extract_text_from_file("test.pdf", b"%PDF-fake")
        assert "PDF content" in text

    @patch("backend.app.summarizer.utils.Document")
    def test_docx_extraction(self, mock_doc_cls):
        mock_para = MagicMock()
        mock_para.text = "DOCX paragraph"
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_para]
        mock_doc_cls.return_value = mock_doc

        text = extract_text_from_file("test.docx", b"PK\x03\x04fake")
        assert "DOCX paragraph" in text


class TestExtractTextFromURL:
    @patch("backend.app.summarizer.utils.requests.get")
    def test_url_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = "<html><body><p>Hello from web</p></body></html>"
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        text = extract_text_from_url("https://example.com")
        assert "Hello from web" in text

    @patch("backend.app.summarizer.utils.requests.get")
    def test_url_fetch_error(self, mock_get):
        mock_get.side_effect = Exception("Connection error")
        with pytest.raises(URLFetchError):
            extract_text_from_url("https://invalid-url.com")


class TestMaxTokens:
    def test_short(self):
        assert _max_tokens_for_length("short") == 150

    def test_medium(self):
        assert _max_tokens_for_length("medium") == 400

    def test_long(self):
        assert _max_tokens_for_length("long") == 1000

    def test_default(self):
        assert _max_tokens_for_length("unknown") == 400


class TestSummarizeText:
    @pytest.mark.asyncio
    @patch("backend.app.summarizer.engine._get_client")
    async def test_summarize_success(self, mock_get_client):
        mock_choice = MagicMock()
        mock_choice.message.content = "  Generated summary  "
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_get_client.return_value = mock_client

        result = await summarize_text("Some text to summarize", "short")
        assert result == "Generated summary"

    @pytest.mark.asyncio
    async def test_summarize_empty_text(self):
        with pytest.raises(SummarizationError):
            await summarize_text("", "medium")

    @pytest.mark.asyncio
    async def test_summarize_whitespace_only(self):
        with pytest.raises(SummarizationError):
            await summarize_text("   ", "medium")
