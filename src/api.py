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
def query(req: QueryRequest):
    """
    Run a question through the hybrid retrieve + generate pipeline.
    Returns the generated answer, the source chunks it was grounded in,
    and total latency.
    """
    start = time.time()
    try:
        result = answer_question(
            req.question,
            top_k=req.top_k,
            retriever=retrieve_hybrid,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline error: {type(e).__name__}: {e}")

    latency_ms = int((time.time() - start) * 1000)

    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "model": result["model"],
        "latency_ms": latency_ms,
    }