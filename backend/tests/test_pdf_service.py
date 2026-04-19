"""
Unit tests for PDFService with PyMuPDF4LLM
"""
import pytest
from app.services.pdf_service import PDFService


@pytest.mark.unit
class TestPDFService:
    """Test suite for PDFService with Markdown extraction"""

    def test_extract_headings_from_markdown(self):
        """Test Markdown heading extraction"""
        md_text = """# Main Title

Some introductory text here.

## Section 1

Content for section 1.

### Subsection 1.1

More detailed content.

## Section 2

Another section with content.
"""
        headings = PDFService._extract_headings_from_markdown(md_text)

        # Should extract 4 headings
        assert len(headings) == 4

        # Check first heading
        assert headings[0]["text"] == "Main Title"
        assert headings[0]["level"] == 1

        # Check second heading
        assert headings[1]["text"] == "Section 1"
        assert headings[1]["level"] == 2

        # Check third heading
        assert headings[2]["text"] == "Subsection 1.1"
        assert headings[2]["level"] == 3

        # Check fourth heading
        assert headings[3]["text"] == "Section 2"
        assert headings[3]["level"] == 2

    def test_extract_headings_no_headers(self):
        """Test extraction when no headers present"""
        md_text = "Just plain text without any headers."
        headings = PDFService._extract_headings_from_markdown(md_text)

        assert headings == []

    def test_extract_headings_with_special_chars(self):
        """Test heading extraction with special characters"""
        md_text = "## Q1 2024 Results: Revenue & Expenses\n\nContent here."
        headings = PDFService._extract_headings_from_markdown(md_text)

        assert len(headings) == 1
        assert headings[0]["text"] == "Q1 2024 Results: Revenue & Expenses"
        assert headings[0]["level"] == 2

    def test_strip_markdown_headers(self):
        """Test Markdown header stripping"""
        text = "## Financial Report\n\nSome content here."
        stripped = PDFService.strip_markdown_syntax(text)

        # Headers should be removed
        assert "##" not in stripped
        assert "Financial Report" in stripped
        assert "Some content here." in stripped

    def test_strip_markdown_bold_italic(self):
        """Test bold/italic syntax removal"""
        text = "This is **bold** and *italic* and __underlined__ text."
        stripped = PDFService.strip_markdown_syntax(text)

        # Syntax should be removed, content preserved
        assert "**" not in stripped
        assert "*" not in stripped
        assert "__" not in stripped
        assert "bold" in stripped
        assert "italic" in stripped
        assert "underlined" in stripped

    def test_strip_markdown_links(self):
        """Test link syntax removal"""
        text = "Check out [this link](https://example.com) for more info."
        stripped = PDFService.strip_markdown_syntax(text)

        # Link syntax removed, text preserved
        assert "[" not in stripped
        assert "]" not in stripped
        assert "(" not in stripped
        assert "this link" in stripped
        assert "https://example.com" not in stripped

    def test_strip_markdown_tables(self):
        """Test table pipe removal"""
        text = """| Quarter | Revenue | Expenses |
|---------|---------|----------|
| Q1      | 100M    | 80M      |
| Q2      | 120M    | 85M      |"""

        stripped = PDFService.strip_markdown_syntax(text)

        # Pipes should be replaced with spaces
        assert "|" not in stripped
        # Content should be preserved
        assert "Quarter" in stripped
        assert "Revenue" in stripped
        assert "Q1" in stripped
        assert "100M" in stripped

    def test_strip_markdown_code(self):
        """Test code block and inline code removal"""
        text = """Here is some `inline code` and a block:

```python
def hello():
    return "world"
```

More text here."""

        stripped = PDFService.strip_markdown_syntax(text)

        # Code syntax removed
        assert "`" not in stripped
        assert "```" not in stripped
        # Content preserved
        assert "inline code" in stripped
        assert "def hello()" in stripped

    def test_strip_markdown_lists(self):
        """Test list marker removal"""
        text = """- Item 1
- Item 2
* Item 3
+ Item 4

1. Numbered item
2. Another numbered item"""

        stripped = PDFService.strip_markdown_syntax(text)

        # List markers should be removed
        # Content preserved
        assert "Item 1" in stripped
        assert "Item 2" in stripped
        assert "Numbered item" in stripped

    def test_strip_markdown_complex(self):
        """Test stripping complex Markdown document"""
        text = """# Financial Report Q1 2024

## Executive Summary

The **quarterly results** show significant growth:

- Revenue: **$120M** (+20% YoY)
- Expenses: $85M
- [View full report](https://example.com/report)

### Key Metrics

| Metric | Q1 2024 | Q1 2023 |
|--------|---------|---------|
| Revenue | 120M | 100M |

> This is a blockquote with important information.

```
Some code or data
```
"""

        stripped = PDFService.strip_markdown_syntax(text)

        # All Markdown syntax removed
        assert "#" not in stripped
        assert "**" not in stripped
        assert "*" not in stripped
        assert "-" not in stripped or stripped.count("-") < text.count("-")
        assert "|" not in stripped
        assert "[" not in stripped
        assert "]" not in stripped
        assert ">" not in stripped or stripped.count(">") < text.count(">")
        assert "```" not in stripped

        # Content preserved
        assert "Financial Report Q1 2024" in stripped
        assert "Executive Summary" in stripped
        assert "quarterly results" in stripped
        assert "Revenue" in stripped
        assert "120M" in stripped

    def test_strip_markdown_preserves_whitespace_structure(self):
        """Test that paragraph structure is somewhat preserved"""
        text = """# Title

Paragraph 1 with content.

Paragraph 2 with more content.

## Section

Another paragraph."""

        stripped = PDFService.strip_markdown_syntax(text)

        # Should have some paragraph separation (double newlines)
        assert "\n\n" in stripped
