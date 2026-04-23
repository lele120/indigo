"""
Cross-Encoder Reranking Service

Note: Requires sentence-transformers package (optional dependency).
Install with: pip install sentence-transformers
Or: pip install -r requirements-optional.txt
"""
from typing import List, Dict, Optional
import structlog

from app.core.config import settings

logger = structlog.get_logger()

# Optional import - only needed if ENABLE_RERANKING=true
try:
    from sentence_transformers import CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    CrossEncoder = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning(
        "sentence_transformers_not_installed",
        message="Cross-encoder reranking disabled. Install with: pip install sentence-transformers"
    )


class RerankingService:
    """Service for reranking search results using cross-encoder models.

    The cross-encoder model is loaded once per process and cached at class
    level. Creating multiple RerankingService instances is cheap — they
    share the same model, which avoids paying the ~10s load cost per
    request under FastAPI's per-request dependency injection.
    """

    # Lightweight cross-encoder model for reranking
    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Process-wide cache: one entry per model_name. Keeps the reranker
    # warm across requests so we don't reload a ~90MB model each time.
    _model_cache: Dict[str, object] = {}

    def __init__(self, model_name: str = None):
        """
        Initialize reranking service with cross-encoder model

        Args:
            model_name: Optional custom model name (defaults to DEFAULT_MODEL)
        """
        self.model_name = model_name or self.DEFAULT_MODEL

    @property
    def _model(self):
        return RerankingService._model_cache.get(self.model_name)

    def _load_model(self):
        """Load cross-encoder model into the process-wide cache (idempotent)."""
        if self.model_name in RerankingService._model_cache:
            return
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )
        logger.info("loading_cross_encoder_model", model=self.model_name)
        RerankingService._model_cache[self.model_name] = CrossEncoder(
            self.model_name, max_length=512
        )
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

        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            logger.warning(
                "reranking_unavailable",
                reason="sentence-transformers not installed"
            )
            return results

        try:
            # Ensure model is in the process-wide cache (no-op after first call)
            self._load_model()
            model = self._model

            # Prepare query-document pairs
            pairs = []
            for result in results:
                # Use full text if available, otherwise preview
                text = result.get("text", result.get("text_preview", ""))
                pairs.append([query, text])

            # Score with cross-encoder. Explicit batch_size gives better
            # CPU utilization than the default batch of 1.
            logger.info("reranking_started", query=query, num_results=len(results))
            scores = model.predict(pairs, batch_size=32, show_progress_bar=False)

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
