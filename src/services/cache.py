"""Simple in-memory caching layer for query results."""

from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A single cache entry with expiration."""

    value: Any
    created_at: float
    ttl_seconds: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if the entry has expired."""
        return time.time() > (self.created_at + self.ttl_seconds)


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    size: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0


class QueryCache:
    """
    Simple in-memory cache for query results.

    Features:
    - TTL-based expiration
    - Size-based eviction (LRU-like)
    - Separate caches for logs and metrics
    - Thread-safe (using simple dict, Python's GIL provides basic safety)
    """

    def __init__(
        self,
        max_entries: int = 1000,
        default_ttl_seconds: float = 300,  # 5 minutes
    ):
        """
        Initialize the cache.

        Args:
            max_entries: Maximum number of entries per cache type
            default_ttl_seconds: Default time-to-live for entries
        """
        self.max_entries = max_entries
        self.default_ttl = default_ttl_seconds

        # Separate caches for different query types
        self._loki_cache: dict[str, CacheEntry] = {}
        self._cortex_cache: dict[str, CacheEntry] = {}

        # Statistics
        self._loki_stats = CacheStats()
        self._cortex_stats = CacheStats()

    def _generate_key(self, query: str, start: str, end: str, **kwargs) -> str:
        """Generate a cache key from query parameters."""
        key_data = f"{query}|{start}|{end}|{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _cleanup_expired(self, cache: dict[str, CacheEntry], stats: CacheStats) -> None:
        """Remove expired entries from a cache."""
        expired_keys = [k for k, v in cache.items() if v.is_expired]
        for key in expired_keys:
            del cache[key]
            stats.evictions += 1
        stats.size = len(cache)

    def _evict_if_needed(self, cache: dict[str, CacheEntry], stats: CacheStats) -> None:
        """Evict entries if cache is at capacity (remove oldest)."""
        if len(cache) >= self.max_entries:
            # Remove oldest entries (by creation time)
            sorted_entries = sorted(cache.items(), key=lambda x: x[1].created_at)
            to_remove = len(cache) - self.max_entries + 1
            for key, _ in sorted_entries[:to_remove]:
                del cache[key]
                stats.evictions += 1
        stats.size = len(cache)

    # Loki cache methods
    def get_loki(
        self,
        query: str,
        start: str,
        end: str,
        **kwargs,
    ) -> dict | None:
        """Get a cached Loki query result."""
        self._cleanup_expired(self._loki_cache, self._loki_stats)

        key = self._generate_key(query, start, end, **kwargs)
        entry = self._loki_cache.get(key)

        if entry and not entry.is_expired:
            entry.hit_count += 1
            self._loki_stats.hits += 1
            logger.debug(f"Loki cache hit for key {key[:8]}...")
            return entry.value

        self._loki_stats.misses += 1
        return None

    def set_loki(
        self,
        query: str,
        start: str,
        end: str,
        value: dict,
        ttl_seconds: float | None = None,
        **kwargs,
    ) -> None:
        """Cache a Loki query result."""
        self._evict_if_needed(self._loki_cache, self._loki_stats)

        key = self._generate_key(query, start, end, **kwargs)
        self._loki_cache[key] = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl_seconds or self.default_ttl,
        )
        self._loki_stats.size = len(self._loki_cache)
        logger.debug(f"Cached Loki result for key {key[:8]}...")

    # Cortex cache methods
    def get_cortex(
        self,
        query: str,
        start: str,
        end: str,
        **kwargs,
    ) -> dict | None:
        """Get a cached Cortex query result."""
        self._cleanup_expired(self._cortex_cache, self._cortex_stats)

        key = self._generate_key(query, start, end, **kwargs)
        entry = self._cortex_cache.get(key)

        if entry and not entry.is_expired:
            entry.hit_count += 1
            self._cortex_stats.hits += 1
            logger.debug(f"Cortex cache hit for key {key[:8]}...")
            return entry.value

        self._cortex_stats.misses += 1
        return None

    def set_cortex(
        self,
        query: str,
        start: str,
        end: str,
        value: dict,
        ttl_seconds: float | None = None,
        **kwargs,
    ) -> None:
        """Cache a Cortex query result."""
        self._evict_if_needed(self._cortex_cache, self._cortex_stats)

        key = self._generate_key(query, start, end, **kwargs)
        self._cortex_cache[key] = CacheEntry(
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl_seconds or self.default_ttl,
        )
        self._cortex_stats.size = len(self._cortex_cache)
        logger.debug(f"Cached Cortex result for key {key[:8]}...")

    # Statistics and management
    def get_stats(self) -> dict:
        """Get cache statistics."""
        return {
            "loki": {
                "hits": self._loki_stats.hits,
                "misses": self._loki_stats.misses,
                "hit_rate": round(self._loki_stats.hit_rate, 3),
                "size": self._loki_stats.size,
                "evictions": self._loki_stats.evictions,
            },
            "cortex": {
                "hits": self._cortex_stats.hits,
                "misses": self._cortex_stats.misses,
                "hit_rate": round(self._cortex_stats.hit_rate, 3),
                "size": self._cortex_stats.size,
                "evictions": self._cortex_stats.evictions,
            },
        }

    def clear(self) -> None:
        """Clear all cached entries."""
        self._loki_cache.clear()
        self._cortex_cache.clear()
        self._loki_stats.size = 0
        self._cortex_stats.size = 0
        logger.info("Query cache cleared")

    def invalidate_loki(self, query_pattern: str | None = None) -> int:
        """
        Invalidate Loki cache entries.

        Args:
            query_pattern: Optional pattern to match (invalidates all if None)

        Returns:
            Number of entries invalidated
        """
        if query_pattern is None:
            count = len(self._loki_cache)
            self._loki_cache.clear()
            self._loki_stats.size = 0
            return count

        # Pattern-based invalidation
        to_remove = [
            k for k, v in self._loki_cache.items()
            if query_pattern in str(v.value.get("query", ""))
        ]
        for key in to_remove:
            del self._loki_cache[key]
        self._loki_stats.size = len(self._loki_cache)
        return len(to_remove)

    def invalidate_cortex(self, query_pattern: str | None = None) -> int:
        """
        Invalidate Cortex cache entries.

        Args:
            query_pattern: Optional pattern to match (invalidates all if None)

        Returns:
            Number of entries invalidated
        """
        if query_pattern is None:
            count = len(self._cortex_cache)
            self._cortex_cache.clear()
            self._cortex_stats.size = 0
            return count

        # Pattern-based invalidation
        to_remove = [
            k for k, v in self._cortex_cache.items()
            if query_pattern in str(v.value.get("query", ""))
        ]
        for key in to_remove:
            del self._cortex_cache[key]
        self._cortex_stats.size = len(self._cortex_cache)
        return len(to_remove)


# Global cache instance
_cache: QueryCache | None = None


def get_cache() -> QueryCache:
    """Get or create the global cache instance."""
    global _cache
    if _cache is None:
        _cache = QueryCache()
    return _cache


def reset_cache() -> None:
    """Reset the global cache (for testing)."""
    global _cache
    if _cache:
        _cache.clear()
    _cache = None
