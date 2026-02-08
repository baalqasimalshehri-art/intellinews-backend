"""
Caching utilities for IntelliNews API

Provides in-memory caching with TTL support to reduce database queries
and improve API response times.
"""

from functools import wraps
from typing import Optional, Any, Callable
from cachetools import TTLCache
import hashlib
import json
import time


# In-memory caches with different TTLs
# Notifications: 30 seconds (frequent updates)
notifications_cache = TTLCache(maxsize=1000, ttl=30)

# User profiles: 5 minutes (rarely change)
profile_cache = TTLCache(maxsize=500, ttl=300)

# Articles: 10 minutes (content doesn't change often)
articles_cache = TTLCache(maxsize=2000, ttl=600)

# Article stats: 5 minutes
stats_cache = TTLCache(maxsize=100, ttl=300)

# Scraping history: 30 seconds
history_cache = TTLCache(maxsize=500, ttl=30)


def generate_cache_key(*args, **kwargs) -> str:
    """
    Generate a unique cache key from function arguments

    Args:
        *args: Positional arguments
        **kwargs: Keyword arguments

    Returns:
        MD5 hash of the arguments as cache key
    """
    # Convert args and kwargs to a stable string representation
    key_data = {
        'args': str(args),
        'kwargs': str(sorted(kwargs.items()))
    }
    key_string = json.dumps(key_data, sort_keys=True)
    return hashlib.md5(key_string.encode()).hexdigest()


def cached(cache: TTLCache, key_prefix: str = ""):
    """
    Decorator for caching function results

    Args:
        cache: TTLCache instance to use
        key_prefix: Optional prefix for cache keys

    Usage:
        @cached(notifications_cache, "notifications")
        async def get_notifications(user_id: int):
            return await fetch_from_db(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key from arguments
            cache_key = f"{key_prefix}:{generate_cache_key(*args, **kwargs)}"

            # Try to get from cache
            if cache_key in cache:
                print(f"[Cache] HIT: {key_prefix} - {cache_key[:16]}...")
                return cache[cache_key]

            # Cache miss - execute function
            print(f"[Cache] MISS: {key_prefix} - {cache_key[:16]}...")
            result = await func(*args, **kwargs)

            # Store in cache
            cache[cache_key] = result
            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key from arguments
            cache_key = f"{key_prefix}:{generate_cache_key(*args, **kwargs)}"

            # Try to get from cache
            if cache_key in cache:
                print(f"[Cache] HIT: {key_prefix} - {cache_key[:16]}...")
                return cache[cache_key]

            # Cache miss - execute function
            print(f"[Cache] MISS: {key_prefix} - {cache_key[:16]}...")
            result = func(*args, **kwargs)

            # Store in cache
            cache[cache_key] = result
            return result

        # Return appropriate wrapper based on function type
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def invalidate_cache(cache: TTLCache, pattern: Optional[str] = None):
    """
    Invalidate cache entries

    Args:
        cache: TTLCache instance to invalidate
        pattern: Optional pattern to match keys (None = clear all)
    """
    if pattern is None:
        cache.clear()
        print(f"[Cache] Cleared all entries")
    else:
        keys_to_delete = [k for k in cache.keys() if pattern in k]
        for key in keys_to_delete:
            del cache[key]
        print(f"[Cache] Invalidated {len(keys_to_delete)} entries matching '{pattern}'")


def get_cache_stats() -> dict:
    """
    Get statistics for all caches

    Returns:
        Dictionary with cache statistics
    """
    return {
        "notifications": {
            "size": len(notifications_cache),
            "maxsize": notifications_cache.maxsize,
            "ttl": notifications_cache.ttl
        },
        "profiles": {
            "size": len(profile_cache),
            "maxsize": profile_cache.maxsize,
            "ttl": profile_cache.ttl
        },
        "articles": {
            "size": len(articles_cache),
            "maxsize": articles_cache.maxsize,
            "ttl": articles_cache.ttl
        },
        "stats": {
            "size": len(stats_cache),
            "maxsize": stats_cache.maxsize,
            "ttl": stats_cache.ttl
        },
        "history": {
            "size": len(history_cache),
            "maxsize": history_cache.maxsize,
            "ttl": history_cache.ttl
        }
    }
