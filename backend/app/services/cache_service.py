"""
Redis cache service for search results
"""
import json
import hashlib
from typing import Optional, Any
import redis
import structlog

from app.core.config import settings

logger = structlog.get_logger()


class CacheService:
    """Redis cache service for search results and other data"""

    def __init__(self):
        """Initialize Redis client"""
        self.redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        self.default_ttl = settings.SEARCH_CACHE_TTL  # seconds

    def _generate_key(self, prefix: str, **kwargs) -> str:
        """
        Generate cache key from parameters

        Args:
            prefix: Key prefix (e.g., "search", "document")
            **kwargs: Key parameters

        Returns:
            Hash-based cache key
        """
        # Sort kwargs for consistent hashing
        params_str = json.dumps(kwargs, sort_keys=True)
        params_hash = hashlib.md5(params_str.encode()).hexdigest()
        return f"{prefix}:{params_hash}"

    def get(self, prefix: str, **kwargs) -> Optional[Any]:
        """
        Get value from cache

        Args:
            prefix: Key prefix
            **kwargs: Key parameters

        Returns:
            Cached value or None if not found
        """
        try:
            key = self._generate_key(prefix, **kwargs)
            value = self.redis_client.get(key)

            if value:
                logger.debug("cache_hit", key=key)
                return json.loads(value)
            else:
                logger.debug("cache_miss", key=key)
                return None

        except Exception as e:
            logger.warning("cache_get_failed", error=str(e))
            return None

    def set(
        self,
        prefix: str,
        value: Any,
        ttl: Optional[int] = None,
        **kwargs
    ) -> bool:
        """
        Set value in cache

        Args:
            prefix: Key prefix
            value: Value to cache (must be JSON serializable)
            ttl: Time-to-live in seconds (default: from config)
            **kwargs: Key parameters

        Returns:
            True if successful
        """
        try:
            key = self._generate_key(prefix, **kwargs)
            value_json = json.dumps(value)
            ttl = ttl or self.default_ttl

            self.redis_client.setex(key, ttl, value_json)
            logger.debug("cache_set", key=key, ttl=ttl)
            return True

        except Exception as e:
            logger.warning("cache_set_failed", error=str(e))
            return False

    def delete(self, prefix: str, **kwargs) -> bool:
        """
        Delete value from cache

        Args:
            prefix: Key prefix
            **kwargs: Key parameters

        Returns:
            True if successful
        """
        try:
            key = self._generate_key(prefix, **kwargs)
            self.redis_client.delete(key)
            logger.debug("cache_delete", key=key)
            return True

        except Exception as e:
            logger.warning("cache_delete_failed", error=str(e))
            return False

    def clear_pattern(self, pattern: str) -> int:
        """
        Clear all keys matching pattern

        Args:
            pattern: Redis key pattern (e.g., "search:*")

        Returns:
            Number of keys deleted
        """
        try:
            keys = list(self.redis_client.scan_iter(match=pattern))
            if keys:
                count = self.redis_client.delete(*keys)
                logger.info("cache_cleared", pattern=pattern, count=count)
                return count
            return 0

        except Exception as e:
            logger.warning("cache_clear_failed", error=str(e))
            return 0
