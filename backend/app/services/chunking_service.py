"""
Text chunking service using LangChain
"""
from typing import List, Dict
from langchain_text_splitters import RecursiveCharacterTextSplitter
import tiktoken
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class ChunkingService:
    """Service for chunking text into smaller pieces"""

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """
        Initialize chunking service with tiktoken encoding

        Args:
            chunk_size: Optional custom chunk size (defaults to settings.CHUNK_SIZE)
            chunk_overlap: Optional custom chunk overlap (defaults to settings.CHUNK_OVERLAP)
        """
        self.encoding = tiktoken.get_encoding("cl100k_base")

        # Use custom values or defaults from settings
        self.chunk_size = chunk_size or settings.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or settings.CHUNK_OVERLAP

        # Initialize text splitter
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=self._token_length,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def _token_length(self, text: str) -> int:
        """Calculate token length of text"""
        return len(self.encoding.encode(text))

    def chunk_text(
        self, text: str, document_id: str, pages_data: List[Dict] = None
    ) -> List[Dict]:
        """
        Chunk text into smaller pieces

        Args:
            text: Full text to chunk
            document_id: UUID of the document
            pages_data: Optional list of page-level data

        Returns:
            List of chunk dicts with metadata
        """
        try:
            # Split text into chunks
            chunks = self.text_splitter.split_text(text)

            logger.info(
                "text_chunked",
                document_id=document_id,
                chunk_count=len(chunks),
                avg_chunk_size=sum(len(c) for c in chunks) / len(chunks) if chunks else 0,
            )

            # Create chunk metadata. Chunks are produced in document order
            # by the splitter, so we can propagate the last-seen heading
            # forward: mid-section chunks (tables, continuations) inherit
            # the heading from their enclosing section instead of getting None.
            chunk_data = []
            last_heading = None
            for i, chunk_text in enumerate(chunks):
                # Try to determine page number for this chunk
                page_number = self._estimate_page_number(
                    chunk_text, pages_data
                ) if pages_data else None

                local_heading = self._find_section_heading(
                    chunk_text, pages_data, page_number
                ) if pages_data else None

                if local_heading:
                    last_heading = local_heading
                section_heading = local_heading or last_heading

                chunk_data.append({
                    "chunk_index": i,
                    "text": chunk_text,
                    "token_count": self._token_length(chunk_text),
                    "char_count": len(chunk_text),
                    "page_number": page_number,
                    "section_heading": section_heading,
                    "chunk_type": "text",  # Default to text (could be extended for tables/images)
                })

            return chunk_data

        except Exception as e:
            logger.error(
                "chunking_failed",
                document_id=document_id,
                error=str(e),
                exc_info=True,
            )
            raise

    def _estimate_page_number(self, chunk_text: str, pages_data: List[Dict]) -> int:
        """
        Estimate which page a chunk belongs to
        Simple heuristic: find page with most matching text
        """
        if not pages_data:
            return None

        best_page = 1
        max_match = 0

        # Take first 100 chars of chunk for matching
        chunk_sample = chunk_text[:100].lower()

        for page_data in pages_data:
            page_text = page_data.get("text", "").lower()
            if chunk_sample in page_text:
                return page_data["page_number"]

            # Count matching words as fallback
            chunk_words = set(chunk_sample.split())
            page_words = set(page_text.split())
            match_count = len(chunk_words & page_words)

            if match_count > max_match:
                max_match = match_count
                best_page = page_data["page_number"]

        return best_page

    def _find_section_heading(
        self, chunk_text: str, pages_data: List[Dict], page_number: int
    ) -> str:
        """
        Find the most relevant section heading for a chunk.

        For Markdown text, extracts the first heading that appears in the chunk.

        Args:
            chunk_text: The text of the chunk (may be Markdown)
            pages_data: List of page data with headings
            page_number: Page number where the chunk is located

        Returns:
            Section heading text or None
        """
        if not pages_data or not page_number:
            return None

        # First, try to extract heading directly from chunk text (Markdown format)
        import re
        header_pattern = re.compile(r'^#{1,6}\s+(.+)$', re.MULTILINE)
        match = header_pattern.search(chunk_text)
        if match:
            return match.group(1).strip()

        # Fallback: Find the page data for this chunk
        page_data = next(
            (p for p in pages_data if p["page_number"] == page_number), None
        )

        if not page_data or not page_data.get("headings"):
            return None

        headings = page_data["headings"]

        # If only one heading on page, use it
        if len(headings) == 1:
            return headings[0]["text"]

        # Try to find the heading in the chunk text
        for heading in headings:
            heading_text = heading["text"]
            # Check both with and without Markdown syntax
            if heading_text in chunk_text or f"# {heading_text}" in chunk_text:
                return heading_text

        # Fallback: return first heading on the page
        return headings[0]["text"] if headings else None

    def chunk_by_page(
        self, pages_data: List[Dict], document_id: str
    ) -> List[Dict]:
        """
        Chunk text page by page (alternative method)

        Args:
            pages_data: List of page-level data
            document_id: UUID of the document

        Returns:
            List of chunk dicts
        """
        try:
            all_chunks = []
            chunk_index = 0

            for page_data in pages_data:
                page_text = page_data["text"]
                page_number = page_data["page_number"]

                # Split page text into chunks
                page_chunks = self.text_splitter.split_text(page_text)

                for chunk_text in page_chunks:
                    all_chunks.append({
                        "chunk_index": chunk_index,
                        "text": chunk_text,
                        "token_count": self._token_length(chunk_text),
                        "char_count": len(chunk_text),
                        "page_number": page_number,
                        "chunk_type": "text",
                    })
                    chunk_index += 1

            logger.info(
                "page_based_chunking_completed",
                document_id=document_id,
                chunk_count=len(all_chunks),
            )

            return all_chunks

        except Exception as e:
            logger.error(
                "page_based_chunking_failed",
                document_id=document_id,
                error=str(e),
                exc_info=True,
            )
            raise
