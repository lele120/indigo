"""
Cross-Encoder Reranking Service
"""
from typing import List, Dict
import structlog
from sentence_transformers import CrossEncoder

from app.core.config import settings

logger = structlog.get_logger()


class RerankingService:
    """Service for reranking search results using cross-encoder models"""

    # Lightweight cross-encoder model for reranking
    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: str = None):
        """
        Initialize reranking service with cross-encoder model

        Args:
            model_name: Optional custom model name (defaults to DEFAULT_MODEL)
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self._model = None  # Lazy loading

    def _load_model(self):
        """Lazy load cross-encoder model"""
        if self._model is None:
            logger.info("loading_cross_encoder_model", model=self.model_name)
            self._model = CrossEncoder(self.model_name, max_length=512)
            logger.info("cross_encoder_model_loaded", model=self.model_name)

    def rerank(
        self,
        query: str,
        results: List[Dict],
        top_k: int = None,
    ) -> List[Dict]:
        """
        Rerank search results using cross-encoder

        Args:
            query: Original search query
            results: List of search results from hybrid search
            top_k: Optional number of top results to return (default: all)

        Returns:
            Reranked list of results with cross_encoder_score added
        """
        if not results:
            return results

        if not settings.ENABLE_RERANKING:
            logger.info("reranking_disabled")
            return results

        try:
            # Lazy load model
            self._load_model()

            # Prepare query-document pairs
            pairs = []
            for result in results:
                # Use full text if available, otherwise preview
                text = result.get("text", result.get("text_preview", ""))
                pairs.append([query, text])

            # Score with cross-encoder
            logger.info("reranking_started", query=query, num_results=len(results))
            scores = self._model.predict(pairs)

            # Add cross-encoder scores to results
            for i, result in enumerate(results):
                result["cross_encoder_score"] = float(scores[i])

            # Sort by cross-encoder score
            reranked_results = sorted(
                results,
                key=lambda x: x.get("cross_encoder_score", 0),
                reverse=True
            )

            # Limit to top_k if specified
            if top_k:
                reranked_results = reranked_results[:top_k]

            logger.info(
                "reranking_completed",
                query=query,
                original_count=len(results),
                final_count=len(reranked_results),
            )

            return reranked_results

        except Exception as e:
            logger.error("reranking_failed", error=str(e), exc_info=True)
            # Return original results if reranking fails
            return results
