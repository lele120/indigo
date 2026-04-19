"""
PDF parsing service using PyMuPDF4LLM for Markdown extraction
"""
import fitz  # PyMuPDF
import pymupdf4llm
from typing import List, Dict
import structlog
import re

logger = structlog.get_logger()


class PDFService:
    """Service for PDF parsing and Markdown extraction optimized for LLM/RAG"""

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> tuple[str, int, List[Dict]]:
        """
        Extract text from PDF file as Markdown with semantic structure

        Uses PyMuPDF4LLM for:
        - Markdown-formatted output (headers, tables, lists)
        - Multi-column layout handling
        - Automatic TOC/heading detection
        - Table structure preservation

        Args:
            file_path: Path to PDF file

        Returns:
            tuple: (full_text, page_count, pages_data)
                - full_text: All text concatenated in Markdown format
                - page_count: Number of pages
                - pages_data: List of dicts with page-level data including headings
        """
        try:
            # Get page count first
            doc = fitz.open(file_path)
            page_count = len(doc)
            doc.close()

            # Extract as Markdown with page chunks
            md_pages = pymupdf4llm.to_markdown(
                doc=file_path,
                page_chunks=True,
                write_images=False,  # We'll handle images separately if needed
                show_progress=False,
            )

            pages_data = []
            full_text_parts = []

            for page_data in md_pages:
                page_num = page_data["metadata"]["page"] + 1  # pymupdf4llm uses 0-based indexing
                md_text = page_data["text"]

                # Extract headings from Markdown text
                headings = PDFService._extract_headings_from_markdown(md_text)

                pages_data.append({
                    "page_number": page_num,
                    "text": md_text,
                    "char_count": len(md_text),
                    "headings": headings,
                    "toc_items": page_data["metadata"].get("toc_items", []),
                })

                full_text_parts.append(md_text)

            full_text = "\n\n".join(full_text_parts)

            logger.info(
                "pdf_extracted_markdown",
                file_path=file_path,
                page_count=page_count,
                total_chars=len(full_text),
                total_headings=sum(len(p["headings"]) for p in pages_data),
                format="markdown",
            )

            return full_text, page_count, pages_data

        except Exception as e:
            logger.error(
                "pdf_extraction_failed",
                file_path=file_path,
                error=str(e),
                exc_info=True,
            )
            raise

    @staticmethod
    def _extract_headings_from_markdown(md_text: str) -> List[Dict[str, any]]:
        """
        Extract headings from Markdown text.

        Args:
            md_text: Markdown-formatted text

        Returns:
            List of dicts with heading information (text, level)
        """
        headings = []

        # Regex to match Markdown headers: ## Heading Text
        # Matches from # to ###### (levels 1-6)
        header_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)

        for match in header_pattern.finditer(md_text):
            level = len(match.group(1))  # Count # symbols
            text = match.group(2).strip()

            headings.append({
                "text": text,
                "level": level,
                "position": match.start(),
            })

        return headings

    @staticmethod
    def get_pdf_metadata(file_path: str) -> Dict:
        """
        Get PDF metadata

        Args:
            file_path: Path to PDF file

        Returns:
            dict: PDF metadata (title, author, subject, etc.)
        """
        try:
            doc = fitz.open(file_path)
            metadata = doc.metadata
            page_count = len(doc)
            doc.close()

            return {
                "title": metadata.get("title", ""),
                "author": metadata.get("author", ""),
                "subject": metadata.get("subject", ""),
                "creator": metadata.get("creator", ""),
                "producer": metadata.get("producer", ""),
                "page_count": page_count,
            }

        except Exception as e:
            logger.error(
                "pdf_metadata_extraction_failed",
                file_path=file_path,
                error=str(e),
            )
            return {}

    @staticmethod
    def strip_markdown_syntax(text: str) -> str:
        """
        Remove Markdown syntax for BM25 indexing while preserving content.

        Used by SearchService to clean Markdown text for keyword search.

        Args:
            text: Markdown-formatted text

        Returns:
            Plain text without Markdown syntax
        """
        # Remove headers (# Header)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)

        # Remove bold/italic (**bold**, *italic*, __bold__, _italic_)
        text = re.sub(r'\*\*([^\*]+)\*\*', r'\1', text)
        text = re.sub(r'\*([^\*]+)\*', r'\1', text)
        text = re.sub(r'__([^_]+)__', r'\1', text)
        text = re.sub(r'_([^_]+)_', r'\1', text)

        # Remove links [text](url) -> text
        text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)

        # Remove images ![alt](url) -> alt
        text = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', r'\1', text)

        # Remove code blocks ```code```
        text = re.sub(r'```[^\n]*\n(.*?)```', r'\1', text, flags=re.DOTALL)

        # Remove inline code `code`
        text = re.sub(r'`([^`]+)`', r'\1', text)

        # Replace table pipes with spaces
        text = re.sub(r'\|', ' ', text)

        # Remove horizontal rules (---, ***)
        text = re.sub(r'^[\-\*]{3,}$', '', text, flags=re.MULTILINE)

        # Remove list markers (-, *, +, 1.)
        text = re.sub(r'^[\s]*[\-\*\+]\s+', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[\s]*\d+\.\s+', '', text, flags=re.MULTILINE)

        # Remove blockquote markers (>)
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)

        # Clean up extra whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = text.strip()

        return text
