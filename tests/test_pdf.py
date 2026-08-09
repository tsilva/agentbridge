"""PDF conversion and text-normalization tests for AgentBridge."""

import pytest

from agentbridge.models import (
    ImageUrl,
    ImageUrlContent,
    TextContent,
)
from agentbridge.server import (
    extract_text_from_content,
    openai_content_to_claude,
    openai_image_to_claude,
    parse_data_url,
)

from .test_utils import slugify_text, text_similarity

pytestmark = pytest.mark.unit


class TestPdfUtils:
    """Unit tests for PDF handling in image_utils."""

    def test_parse_data_url_pdf(self):
        """Parse PDF data URL."""
        url = "data:application/pdf;base64,JVBERi0xLjQK"
        media_type, data = parse_data_url(url)

        assert media_type == "application/pdf"
        assert data == "JVBERi0xLjQK"

    def test_openai_pdf_to_claude_document(self):
        """Convert PDF data URL to Claude document format."""
        pdf_content = ImageUrlContent(
            type="image_url",
            image_url=ImageUrl(url="data:application/pdf;base64,JVBERi0xLjQK")
        )
        result = openai_image_to_claude(pdf_content)

        assert result == {
            "type": "document",
            "source": {
                "type": "base64",
                "media_type": "application/pdf",
                "data": "JVBERi0xLjQK",
            }
        }

    def test_openai_content_with_pdf(self):
        """Convert mixed content with PDF to Claude format."""
        content = [
            TextContent(type="text", text="Extract text from this PDF:"),
            ImageUrlContent(
                type="image_url",
                image_url=ImageUrl(url="data:application/pdf;base64,JVBERi0xLjQK")
            ),
        ]
        result = openai_content_to_claude(content)

        assert result == [
            {"type": "text", "text": "Extract text from this PDF:"},
            {
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": "application/pdf",
                    "data": "JVBERi0xLjQK",
                }
            },
        ]

    def test_extract_text_pdf_placeholder(self):
        """Extract text shows PDF placeholder for logging."""
        content = [
            TextContent(type="text", text="Extract this:"),
            ImageUrlContent(
                type="image_url",
                image_url=ImageUrl(url="data:application/pdf;base64,JVBERi0xLjQK")
            ),
        ]
        result = extract_text_from_content(content)

        assert "Extract this:" in result
        assert "[document: PDF base64 data]" in result

    def test_image_still_produces_image_block(self):
        """Verify images still produce image blocks, not document blocks."""
        image_content = ImageUrlContent(
            type="image_url",
            image_url=ImageUrl(url="data:image/png;base64,iVBORw0KGgo=")
        )
        result = openai_image_to_claude(image_content)

        assert result["type"] == "image"
        assert result["source"]["media_type"] == "image/png"


class TestSlugification:
    """Unit tests for text slugification and similarity functions."""

    def test_slugify_basic(self):
        """Slugify removes punctuation and lowercases."""
        assert slugify_text("Hello, World!") == "hello world"
        assert slugify_text("Test: 123") == "test 123"
        assert slugify_text("UPPERCASE") == "uppercase"

    def test_slugify_multiline(self):
        """Slugify normalizes whitespace including newlines."""
        text = "Line 1\n\nLine 2\tLine 3"
        assert slugify_text(text) == "line 1 line 2 line 3"

    def test_slugify_unicode(self):
        """Slugify handles unicode characters."""
        assert slugify_text("café") == "cafe"
        assert slugify_text("naïve") == "naive"

    def test_text_similarity_exact_match(self):
        """Exact match returns 1.0 similarity."""
        assert text_similarity("hello world", "hello world") == 1.0

    def test_text_similarity_case_insensitive(self):
        """Similarity is case insensitive."""
        assert text_similarity("Hello World", "hello world") == 1.0

    def test_text_similarity_partial_match(self):
        """Partial match returns proportional similarity."""
        # 2 of 4 words match
        assert text_similarity("a b c d", "a b x y") == 0.5

    def test_text_similarity_no_match(self):
        """No matching words returns 0.0."""
        assert text_similarity("hello world", "foo bar") == 0.0

    def test_text_similarity_empty_expected(self):
        """Empty expected text returns 1.0."""
        assert text_similarity("", "anything") == 1.0

    def test_text_similarity_superset(self):
        """Actual text containing all expected words returns 1.0."""
        assert text_similarity("a b", "a b c d e f") == 1.0
