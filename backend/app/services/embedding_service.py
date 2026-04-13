"""
Embedding service using OpenAI
"""
from typing import List, Dict
import openai
from openai import OpenAI
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class EmbeddingService:
    """Service for generating embeddings using OpenAI"""

    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = settings.EMBEDDING_MODEL
        self.batch_size = settings.EMBEDDING_BATCH_SIZE

    def generate_embeddings(
        self, chunks: List[Dict], document_id: str, fallback_on_error: bool = True
    ) -> tuple[List[Dict], bool]:
        """
        Generate embeddings for chunks in batches with optional fallback

        Args:
            chunks: List of chunk dicts with 'text' field
            document_id: UUID of the document
            fallback_on_error: If True, return chunks without embeddings on error
                              If False, raise exception on error

        Returns:
            tuple: (chunks_with_or_without_embeddings, has_embeddings)
                - chunks: List of chunks (with 'embedding' field if successful)
                - has_embeddings: True if embeddings were generated, False if fallback used
        """
        try:
            logger.info(
                "embedding_generation_started",
                document_id=document_id,
                chunk_count=len(chunks),
                batch_size=self.batch_size,
                fallback_enabled=fallback_on_error,
            )

            # Process in batches
            for i in range(0, len(chunks), self.batch_size):
                batch = chunks[i:i + self.batch_size]
                batch_texts = [chunk["text"] for chunk in batch]

                # Generate embeddings for batch
                response = self.client.embeddings.create(
                    model=self.model,
                    input=batch_texts,
                )

                # Add embeddings to chunks
                for j, embedding_data in enumerate(response.data):
                    batch[j]["embedding"] = embedding_data.embedding

                logger.info(
                    "embedding_batch_completed",
                    document_id=document_id,
                    batch_num=i // self.batch_size + 1,
                    batch_size=len(batch),
                )

            logger.info(
                "embedding_generation_completed",
                document_id=document_id,
                total_chunks=len(chunks),
            )

            return chunks, True

        except openai.OpenAIError as e:
            logger.error(
                "openai_embedding_failed",
                document_id=document_id,
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )

            if fallback_on_error:
                logger.warning(
                    "embedding_fallback_activated",
                    document_id=document_id,
                    message="Continuing without embeddings - BM25 search will still work",
                )
                # Return chunks without embeddings
                return chunks, False
            else:
                raise

        except Exception as e:
            logger.error(
                "embedding_generation_failed",
                document_id=document_id,
                error=str(e),
                exc_info=True,
            )

            if fallback_on_error:
                logger.warning(
                    "embedding_fallback_activated",
                    document_id=document_id,
                    message="Continuing without embeddings - BM25 search will still work",
                )
                return chunks, False
            else:
                raise

    def generate_single_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector)
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=[text],
            )
            return response.data[0].embedding

        except Exception as e:
            logger.error(
                "single_embedding_failed",
                error=str(e),
                exc_info=True,
            )
            raise
