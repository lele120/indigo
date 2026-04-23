"""
Qdrant vector storage service
"""
from typing import List, Dict, Optional
from uuid import UUID
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class QdrantService:
    """Service for interacting with Qdrant vector database"""

    def __init__(self):
        """Initialize Qdrant client"""
        self.client = QdrantClient(
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_HTTP_PORT,
        )
        self.collection_name = settings.QDRANT_COLLECTION_NAME
        self.vector_size = 1536  # OpenAI text-embedding-3-small dimension

    def ensure_collection_exists(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections().collections
            collection_names = [c.name for c in collections]

            if self.collection_name not in collection_names:
                logger.info(
                    "creating_qdrant_collection",
                    collection_name=self.collection_name,
                )

                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_size,
                        distance=Distance.COSINE,
                    ),
                )

                logger.info(
                    "qdrant_collection_created",
                    collection_name=self.collection_name,
                )
            else:
                logger.info(
                    "qdrant_collection_exists",
                    collection_name=self.collection_name,
                )

        except Exception as e:
            logger.error(
                "qdrant_collection_creation_failed",
                error=str(e),
                exc_info=True,
            )
            raise

    def upsert_chunks(
        self, document_id: UUID, chunks: List[Dict], chunk_db_ids: List[UUID]
    ) -> int:
        """
        Upsert chunks to Qdrant

        Args:
            document_id: UUID of the document
            chunks: List of chunk dicts with 'embedding' field
            chunk_db_ids: List of chunk database IDs (UUIDs)

        Returns:
            Number of chunks upserted
        """
        try:
            # Ensure collection exists
            self.ensure_collection_exists()

            # Prepare points for upsert
            points = []
            for i, (chunk, chunk_db_id) in enumerate(zip(chunks, chunk_db_ids)):
                # Use chunk DB ID as Qdrant point ID
                point_id = str(chunk_db_id)

                # Prepare payload (metadata)
                payload = {
                    "document_id": str(document_id),
                    "chunk_id": str(chunk_db_id),
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"][:1000],  # Store preview (limit to 1000 chars)
                    "text_preview": chunk["text"][:200],  # Short preview
                    "page_number": chunk.get("page_number"),
                    "section_heading": chunk.get("section_heading"),
                    "chunk_type": chunk.get("chunk_type", "text"),
                    "token_count": chunk.get("token_count", 0),
                    "char_count": chunk.get("char_count", 0),
                }

                point = PointStruct(
                    id=point_id,
                    vector=chunk["embedding"],
                    payload=payload,
                )
                points.append(point)

            # Upsert in batches
            batch_size = 100
            for i in range(0, len(points), batch_size):
                batch = points[i:i + batch_size]
                self.client.upsert(
                    collection_name=self.collection_name,
                    points=batch,
                )

                logger.info(
                    "qdrant_batch_upserted",
                    document_id=str(document_id),
                    batch_num=i // batch_size + 1,
                    batch_size=len(batch),
                )

            logger.info(
                "qdrant_upsert_completed",
                document_id=str(document_id),
                total_chunks=len(points),
            )

            return len(points)

        except Exception as e:
            logger.error(
                "qdrant_upsert_failed",
                document_id=str(document_id),
                error=str(e),
                exc_info=True,
            )
            raise

    def search(
        self,
        query_vector: List[float],
        limit: int = 10,
        document_id: Optional[str] = None,
        score_threshold: Optional[float] = None,
    ) -> List[Dict]:
        """
        Search for similar chunks

        Args:
            query_vector: Query embedding vector
            limit: Maximum number of results
            document_id: Optional document ID to filter by
            score_threshold: Optional minimum score threshold

        Returns:
            List of search results with metadata
        """
        try:
            # Prepare filter
            query_filter = None
            if document_id:
                query_filter = Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id),
                        )
                    ]
                )

            # Search using query_points
            results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                limit=limit,
                query_filter=query_filter,
                score_threshold=score_threshold,
            ).points

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "chunk_id": result.payload.get("chunk_id"),
                    "document_id": result.payload.get("document_id"),
                    "text": result.payload.get("text"),
                    "text_preview": result.payload.get("text_preview"),
                    "page_number": result.payload.get("page_number"),
                    "chunk_index": result.payload.get("chunk_index"),
                    "section_heading": result.payload.get("section_heading"),
                    "chunk_type": result.payload.get("chunk_type"),
                    "score": result.score,
                })

            return formatted_results

        except Exception as e:
            logger.error(
                "qdrant_search_failed",
                error=str(e),
                exc_info=True,
            )
            raise

    def delete_by_document(self, document_id: UUID) -> bool:
        """
        Delete all chunks for a document

        Args:
            document_id: UUID of the document

        Returns:
            True if successful
        """
        try:
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=str(document_id)),
                        )
                    ]
                ),
            )

            logger.info(
                "qdrant_document_deleted",
                document_id=str(document_id),
            )

            return True

        except Exception as e:
            logger.error(
                "qdrant_delete_failed",
                document_id=str(document_id),
                error=str(e),
                exc_info=True,
            )
            raise

    def get_collection_info(self) -> Dict:
        """Get collection information"""
        try:
            info = self.client.get_collection(
                collection_name=self.collection_name
            )
            return {
                "name": self.collection_name,
                "vectors_count": info.vectors_count,
                "points_count": info.points_count,
                "status": info.status,
            }
        except Exception as e:
            logger.error(
                "qdrant_collection_info_failed",
                error=str(e),
            )
            return {}
