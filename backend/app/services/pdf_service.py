"""
PDF parsing service
"""
import fitz  # PyMuPDF
from typing import List, Dict
import structlog

logger = structlog.get_logger()


class PDFService:
    """Service for PDF parsing and text extraction"""

    @staticmethod
    def extract_text_from_pdf(file_path: str) -> tuple[str, int, List[Dict]]:
        """
        Extract text from PDF file with section headings detection

        Args:
            file_path: Path to PDF file

        Returns:
            tuple: (full_text, page_count, pages_data)
                - full_text: All text concatenated
                - page_count: Number of pages
                - pages_data: List of dicts with page-level data including headings
        """
        try:
            doc = fitz.open(file_path)
            page_count = len(doc)
            pages_data = []
            full_text = []

            for page_num, page in enumerate(doc, start=1):
                # Extract text from page
                text = page.get_text("text")

                # Extract headings based on font size
                headings = PDFService._extract_headings_from_page(page)

                pages_data.append({
                    "page_number": page_num,
                    "text": text,
                    "char_count": len(text),
                    "headings": headings,  # List of detected headings on this page
                })

                full_text.append(text)

            doc.close()

            logger.info(
                "pdf_extracted",
                file_path=file_path,
                page_count=page_count,
                total_chars=sum(p["char_count"] for p in pages_data),
                total_headings=sum(len(p["headings"]) for p in pages_data),
            )

            return "\n\n".join(full_text), page_count, pages_data

        except Exception as e:
            logger.error(
                "pdf_extraction_failed",
                file_path=file_path,
                error=str(e),
                exc_info=True,
            )
            raise

    @staticmethod
    def _extract_headings_from_page(page) -> List[Dict[str, any]]:
        """
        Extract section headings from a PDF page based on font size and style.

        Args:
            page: PyMuPDF page object

        Returns:
            List of dicts with heading information (text, font_size, position)
        """
        headings = []
        blocks = page.get_text("dict")["blocks"]

        # Calculate average font size to detect headings
        font_sizes = []
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_sizes.append(span.get("size", 0))

        if not font_sizes:
            return headings

        avg_font_size = sum(font_sizes) / len(font_sizes)
        threshold = avg_font_size * 1.2  # Headings are typically 20% larger

        # Extract headings (text with larger font size)
        for block in blocks:
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_size = span.get("size", 0)
                        text = span.get("text", "").strip()

                        # Consider it a heading if:
                        # 1. Font size is larger than threshold
                        # 2. Text is not too long (< 100 chars)
                        # 3. Text is not empty
                        if font_size > threshold and text and len(text) < 100:
                            headings.append({
                                "text": text,
                                "font_size": font_size,
                                "position": span.get("origin", (0, 0))[1],  # y-coordinate
                            })

        # Sort by vertical position (top to bottom)
        headings.sort(key=lambda h: h["position"])

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
