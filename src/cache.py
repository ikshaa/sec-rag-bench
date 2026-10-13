"""
Semantic cache for LLM responses.

Caches query-response pairs by query embedding. On each incoming query,
we embed it and compare against every stored embedding. If any cached
query has cosine similarity above the threshold, we return its response
instead of re-running the pipeline.

For small caches (<1000 entries), linear scan is fast enough (~5ms on CPU).
In production, you'd swap this for Redis Vector Search or a dedicated
vector DB. The interface stays the same, only the search changes.
"""

import json
import os
import uuid

import numpy as np
import redis
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

CACHE_KEYS_SET = "cache:keys"           # Redis set of all cache entry IDs
CACHE_ENTRY_PREFIX = "cache:entry:"     # Prefix for each stored entry
SIMILARITY_THRESHOLD = 0.95             # Cosine similarity to count as a hit
DEFAULT_TTL_SECONDS = 3600              # 1 hour

EMBEDDING_MODEL = "text-embedding-3-small"


# ---------------------------------------------------------------------------
# Lazy-loaded clients
# ---------------------------------------------------------------------------

_redis_client = None
_openai_client = None


def _redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    return _redis_client


def _openai() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = OpenAI()
    return _openai_client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _embed(query: str) -> list[float]:
    """Embed a query using the same model used for chunk embeddings."""
    client = _openai()
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=query)
    return response.data[0].embedding


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    a_arr = np.array(a)
    b_arr = np.array(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_cached(query: str) -> dict | None:
    """
    Check if a semantically similar query exists in cache.

    Returns None on miss. On hit, returns:
        {
            "response": the cached response dict,
            "matched_query": the original query that was cached,
            "similarity": cosine similarity score (0.0 - 1.0),
        }
    """
    r = _redis()
    query_embedding = _embed(query)

    best_similarity = 0.0
    best_response = None
    best_matched_query = None

    cache_keys = r.smembers(CACHE_KEYS_SET)
    for key in cache_keys:
        entry_json = r.get(CACHE_ENTRY_PREFIX + key)
        if entry_json is None:
            # TTL expired, clean up the orphaned key reference
            r.srem(CACHE_KEYS_SET, key)
            continue
        entry = json.loads(entry_json)
        similarity = _cosine_similarity(query_embedding, entry["embedding"])
        if similarity > best_similarity:
            best_similarity = similarity
            best_response = entry["response"]
            best_matched_query = entry["query"]

    if best_similarity >= SIMILARITY_THRESHOLD:
        return {
            "response": best_response,
            "matched_query": best_matched_query,
            "similarity": best_similarity,
        }
    return None


def set_cached(query: str, response: dict, ttl_seconds: int = DEFAULT_TTL_SECONDS) -> None:
    """Store a query-response pair in cache with a TTL."""
    r = _redis()
    query_embedding = _embed(query)
    key = str(uuid.uuid4())
    entry = {"query": query, "embedding": query_embedding, "response": response}
    r.setex(CACHE_ENTRY_PREFIX + key, ttl_seconds, json.dumps(entry))
    r.sadd(CACHE_KEYS_SET, key)


def cache_stats() -> dict:
    """Return cache size (count of live entries)."""
    r = _redis()
    # Clean up any stale key references (TTL expired)
    cache_keys = list(r.smembers(CACHE_KEYS_SET))
    live_keys = 0
    for key in cache_keys:
        if r.exists(CACHE_ENTRY_PREFIX + key):
            live_keys += 1
        else:
            r.srem(CACHE_KEYS_SET, key)
    return {"size": live_keys, "similarity_threshold": SIMILARITY_THRESHOLD}


def clear_cache() -> int:
    """Clear all cached entries. Returns count of entries cleared."""
    r = _redis()
    cache_keys = list(r.smembers(CACHE_KEYS_SET))
    count = 0
    for key in cache_keys:
        if r.delete(CACHE_ENTRY_PREFIX + key):
            count += 1
    r.delete(CACHE_KEYS_SET)
    return count


if __name__ == "__main__":
    stats = cache_stats()
    print(f"Cache size: {stats['size']} entries")
    print(f"Similarity threshold: {stats['similarity_threshold']}")