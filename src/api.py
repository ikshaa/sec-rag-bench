"""
FastAPI service wrapping the SEC-RAG-Bench pipeline.

Endpoints:
    GET  /health   - liveness check (always returns 200 if the server is up)
    GET  /ready    - readiness check (verifies DB and Elasticsearch are reachable)
    POST /query    - run a question through the hybrid retrieve + generate pipeline

Run locally:
    uvicorn src.api:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive API docs.
"""

import os
import time
from typing import Literal

import psycopg
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from src.generate import answer_question
from src.retrieve_hybrid import retrieve_hybrid
from src.cache import get_cached, set_cached, cache_stats, clear_cache

from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from src.observability import (
    QUERIES_TOTAL, QUERY_LATENCY_MS, CACHE_SIZE, ERRORS_TOTAL,
    log, trace_request,
)

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ES_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
ES_PORT = os.getenv("ELASTICSEARCH_PORT", "9200")
ES_URL = f"http://{ES_HOST}:{ES_PORT}"

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")
PG_DB = os.getenv("POSTGRES_DB")
DB_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"

# ---------------------------------------------------------------------------
# Pydantic schemas (request / response contracts)
# ---------------------------------------------------------------------------

class QueryRequest(BaseModel):
    """Shape of the POST /query body."""
    question: str = Field(..., min_length=3, max_length=1000, description="Natural language question")
    top_k: int = Field(5, ge=1, le=20, description="Number of chunks to retrieve")


class SourceChunk(BaseModel):
    chunk_id: int
    company: str
    fiscal_year: int
    text: str
    rrf_score: float | None = None


class QueryResponse(BaseModel):
    """Shape of the response to POST /query."""
    answer: str
    sources: list[SourceChunk]
    model: str
    latency_ms: int
    cache_hit: bool
    matched_query: str | None = None
    provider: str | None = None
    fallback_used: bool | None = None


class HealthResponse(BaseModel):
    status: Literal["ok"]


class ReadyResponse(BaseModel):
    status: Literal["ready", "not_ready"]
    checks: dict


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SEC-RAG-Bench API",
    description="Hybrid retrieval + grounded generation over SEC 10-K filings.",
    version="0.1.0",
)


@app.get("/health", response_model=HealthResponse)
def health():
    """Simple liveness probe. Does not check downstream dependencies."""
    return {"status": "ok"}


@app.get("/ready", response_model=ReadyResponse)
def ready():
    """
    Readiness probe. Verifies the service can reach its dependencies.
    Returns 503 if anything is unreachable so Kubernetes/Docker can
    route traffic away until it recovers.
    """
    checks = {}

    # Postgres check
    try:
        with psycopg.connect(DB_URL, connect_timeout=2) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {type(e).__name__}"

    # Elasticsearch check
    try:
        es = Elasticsearch(ES_URL, request_timeout=2)
        if es.ping():
            checks["elasticsearch"] = "ok"
        else:
            checks["elasticsearch"] = "unreachable"
    except Exception as e:
        checks["elasticsearch"] = f"error: {type(e).__name__}"

    all_ok = all(v == "ok" for v in checks.values())
    if not all_ok:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "checks": checks})
    return {"status": "ready", "checks": checks}


@app.post("/query", response_model=QueryResponse)
@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest):
    """
    Run a question through hybrid retrieve + generate, with cache check.
    Records Prometheus metrics and structured logs for every request.
    """
    with trace_request("/query") as trace_id:
        start = time.time()

        # Cache check
        cached = get_cached(req.question)
        if cached is not None:
            latency_ms = int((time.time() - start) * 1000)
            cached_provider = cached["response"].get("provider") or "unknown"
            cached_fallback = str(cached["response"].get("fallback_used", False)).lower()

            QUERIES_TOTAL.labels(cache_hit="true", provider=cached_provider, fallback_used=cached_fallback).inc()
            QUERY_LATENCY_MS.labels(cache_hit="true").observe(latency_ms)
            log.info("query_served", extra={
                "trace_id": trace_id,
                "cache_hit": True,
                "matched_query": cached["matched_query"],
                "similarity": cached["similarity"],
                "latency_ms": latency_ms,
            })
            return {
                **cached["response"],
                "latency_ms": latency_ms,
                "cache_hit": True,
                "matched_query": cached["matched_query"],
            }

        # Cache miss: run pipeline
        try:
            result = answer_question(req.question, top_k=req.top_k, retriever=retrieve_hybrid)
        except Exception as e:
            ERRORS_TOTAL.labels(error_type=type(e).__name__).inc()
            log.error("query_failed", extra={
                "trace_id": trace_id,
                "error_type": type(e).__name__,
                "error": str(e),
            })
            raise HTTPException(status_code=500, detail=f"Pipeline error: {type(e).__name__}: {e}")

        response = {
            "answer": result["answer"],
            "sources": result["sources"],
            "model": result["model"],
            "provider": result.get("provider"),
            "fallback_used": result.get("fallback_used"),
        }

        try:
            set_cached(req.question, response)
        except Exception as e:
            log.warning("cache_write_failed", extra={"trace_id": trace_id, "error": str(e)})

        latency_ms = int((time.time() - start) * 1000)
        provider = result.get("provider") or "unknown"
        fallback = str(result.get("fallback_used", False)).lower()

        QUERIES_TOTAL.labels(cache_hit="false", provider=provider, fallback_used=fallback).inc()
        QUERY_LATENCY_MS.labels(cache_hit="false").observe(latency_ms)
        log.info("query_served", extra={
            "trace_id": trace_id,
            "cache_hit": False,
            "provider": provider,
            "fallback_used": result.get("fallback_used"),
            "latency_ms": latency_ms,
        })

        return {**response, "latency_ms": latency_ms, "cache_hit": False, "matched_query": None}
@app.get("/cache/stats")
def get_cache_stats():
    """Return current cache size and configuration."""
    return cache_stats()


@app.delete("/cache")
def clear_cache_endpoint():
    """Clear all cached entries."""
    cleared = clear_cache()
    return {"cleared": cleared}

@app.get("/metrics")
def prometheus_metrics():
    """Expose Prometheus metrics for scraping."""
    CACHE_SIZE.set(cache_stats()["size"])
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)