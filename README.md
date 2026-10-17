# SEC-RAG-Bench

An evaluation-driven RAG platform for querying SEC 10-K filings
with cited answers. Every architecture decision is backed by a
measurement.

📊 **Benchmark published on HuggingFace**: [neharanii/sec-rag-bench](https://huggingface.co/datasets/neharanii/sec-rag-bench)

**Status:** Core system complete. Benchmarked, load-tested,
observable.

---

## Headline results

| Metric | Baseline (dense vector) | Final (hybrid RRF) |
|---|---|---|
| Recall@5 | 68.24% | **76.47%** |
| Negation recall | 78.57% | **100%** |
| Precision@5 | 23.76% | 28.24% |
| Faithfulness | 84.79% | 81.82% |
| Answer relevancy | 60.35% | 69.47% |
| Refusal accuracy | 93.33% | **100%** |

**Load test:** scales linearly to 200 concurrent users, 23.4 RPS,
zero failures across 2,827 requests. Semantic cache delivers 12x
latency reduction on repeated queries.

**Benchmark:** 100 hand-written questions across 6 categories
(factual, numerical, multi-hop, comparison, negation, unanswerable)
over 15 10-K filings from 8 companies.

---

## What it does

Point it at an SEC 10-K question like "What were Tesla's total
revenues in 2023?" and it returns a grounded, cited answer sourced
from the actual filing. If the answer isn't retrievable, it says
so instead of fabricating.

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What were Tesla total revenues in 2023?", "top_k": 5}'
```

```json
{
  "answer": "Tesla's total revenues in 2023 were $96,773 million [2].",
  "sources": [...],
  "model": "claude-haiku-4-5",
  "latency_ms": 587,
  "cache_hit": false,
  "provider": "anthropic"
}
```

---

## Architecture

```
   Client
     │
     ▼
┌──────────────────────────┐
│   FastAPI Service        │
│   /query /health /ready  │
│   /metrics /cache        │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│   Semantic Cache (Redis) │  ← 0.95 cosine similarity threshold
│   HIT → return cached    │
│   MISS → run pipeline    │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│   Hybrid Retrieval       │
│   via Reciprocal Rank    │
│   Fusion (RRF)           │
└───┬──────────────────┬───┘
    │                  │
    ▼                  ▼
┌─────────┐      ┌──────────────┐
│ Vector  │      │ BM25         │
│ pgvector│      │ Elasticsearch│
└─────────┘      └──────────────┘
           │
           ▼
┌──────────────────────────┐
│   LLM Gateway            │
│   Anthropic → OpenAI     │
│   fallback on errors     │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│   Prometheus + Grafana   │
│   (observability)        │
└──────────────────────────┘
```

**Infrastructure services** (docker-compose):
`postgres` (pgvector) · `elasticsearch` · `redis` · `prometheus` · `grafana`

**Application services**: FastAPI running on host for hot-reload during dev.

---

## Quickstart

### Prerequisites
- Docker Desktop
- Python 3.12+
- Anthropic API key, OpenAI API key

### Setup

```bash
# Clone and enter the repo
git clone https://github.com/neharanii/sec-rag-bench.git
cd sec-rag-bench

# Create venv and install dependencies
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start infrastructure
docker compose up -d

# Wait ~30 seconds for services to be healthy
docker compose ps
```

### Ingest filings

```bash
# Download 10-Ks from SEC EDGAR
python -m src.ingest

# Chunk and embed
python -m src.chunk
python -m src.embed

# Build BM25 index
python -m src.index_bm25
```

### Run

```bash
# Start the API
uvicorn src.api:app --port 8000

# Test it
curl http://localhost:8000/health
curl http://localhost:8000/docs  # interactive API docs
```

### Evaluate

```bash
# Run the full benchmark against each retriever
python -m eval.run_baseline     # dense vector only
python -m eval.run_bm25         # BM25 only
python -m eval.run_hybrid       # vector + BM25 via RRF (the champion)
python -m eval.run_reranked     # with cross-encoder reranker

# Analyze failures
python -m eval.analyze_failures
```

Results land in `results/*.json`. Dashboards in Grafana at
http://localhost:3000.

---

## Benchmark methodology

**Ground truth by construction.** Every question is anchored to a
specific passage in a real 10-K, with company, fiscal year, and
exact snippet recorded. Paraphrase rule enforced so questions don't
trivially overlap the source wording.

The benchmark is published as a public HuggingFace dataset:
[neharanii/sec-rag-bench](https://huggingface.co/datasets/neharanii/sec-rag-bench)

**Six categories, chosen to stress different failure modes:**

| Category | Count | What it tests |
|---|---|---|
| Factual | 32 | Single-chunk fact retrieval |
| Numerical | 17 | Exact-match numbers and dollar amounts |
| Multi-hop | 14 | Information spanning two filings |
| Comparison | 8 | Cross-filing or cross-year comparisons |
| Negation | 14 | "Not", "excludes", precision-sensitive language |
| Unanswerable | 15 | Model should refuse rather than fabricate |

**Four metrics per question:** Recall@5, Precision@5, Citation
Accuracy, plus RAGAS Faithfulness and Answer Relevancy. Refusal
accuracy measured separately on unanswerable questions.

See `docs/FAILURE_ANALYSIS.md` for the methodology finding that
emerged from reading the 21 benchmark failures.

---

## Project structure

```
sec-rag-bench/
├── src/
│   ├── api.py                      FastAPI service
│   ├── ingest.py                   SEC EDGAR downloader
│   ├── chunk.py                    Fixed-size chunking
│   ├── embed.py                    OpenAI embedding generation
│   ├── retrieve.py                 Dense vector retrieval (pgvector)
│   ├── retrieve_bm25.py            BM25 retrieval (Elasticsearch)
│   ├── retrieve_hybrid.py          RRF fusion
│   ├── retrieve_hybrid_reranked.py Hybrid + cross-encoder (not shipped as default)
│   ├── rerank.py                   Cross-encoder reranker
│   ├── generate.py                 Grounded generation with citations
│   ├── llm_gateway.py              Anthropic → OpenAI fallback
│   ├── cache.py                    Redis semantic cache
│   ├── observability.py            Prometheus metrics + JSON logging
│   ├── index_bm25.py               Build ES index from Postgres chunks
│   └── cli.py                      CLI for ad-hoc queries
├── eval/
│   ├── benchmark.py                Pydantic schema + loader
│   ├── metrics.py                  Recall, precision, citation, RAGAS
│   ├── run_baseline.py             Dense vector eval
│   ├── run_bm25.py                 BM25 eval
│   ├── run_hybrid.py               Hybrid eval
│   ├── run_reranked.py             Reranked eval
│   └── analyze_failures.py         Failure classification
├── data/benchmark/benchmark_v1.jsonl   100 benchmark questions
├── results/                        Per-retriever eval outputs
├── docs/
│   ├── TECHNICAL_REFERENCE.md      Every term, every decision
│   ├── FINDINGS.md                 Experiment log (newest first)
│   ├── DECISIONS.md                Why each architectural choice
│   ├── FAILURE_ANALYSIS.md         Deep dive on the 21 failures
│   ├── INTERVIEW_TALKING_POINTS.md Quotable insights
│   └── LOAD_TEST_RESULTS.xlsx      Locust results, 5 to 200 users
├── prometheus/prometheus.yml       Scrape config
├── grafana/provisioning/           Auto-provisioned datasource
├── docker-compose.yml              All infrastructure
├── locustfile.py                   Load test definition
└── README.md                       You are here
```

---

## Experiments summary

Five retrievers benchmarked end-to-end on the same 100 questions:

| Retriever | Recall@5 | Precision@5 | Faithfulness | Shipped? |
|---|---|---|---|---|
| Dense vector | 68.24% | 23.76% | 84.79% | baseline |
| BM25 | 69.41% | 26.35% | 84.54% | combined via hybrid |
| **Hybrid RRF (vector + BM25)** | **76.47%** | 28.24% | 81.82% | **yes** |
| Hybrid + ms-marco reranker | 74.12% | 28.94% | 84.09% | no |
| Hybrid + BGE reranker | 75.29% | 28.71% | 84.25% | no |

**Key finding on reranking:** Both cross-encoder rerankers reduced
Recall@5 for this workload. Reranking promotes a single
highly-relevant chunk and demotes "bridge" chunks past the top-5
cutoff, which hurts multi-hop and comparison questions. The small
precision gain wasn't worth the recall loss. Shipped hybrid alone.

Full experiment log: `docs/FINDINGS.md`.

---

## Observability

Prometheus metrics at `/metrics`:
- `secrag_queries_total{cache_hit, provider, fallback_used}` (counter)
- `secrag_query_latency_ms_bucket{cache_hit}` (histogram)
- `secrag_cache_size` (gauge)
- `secrag_errors_total{error_type}` (counter)

Grafana dashboard shows queries per minute, cache hit rate, p95
latency by cache status, and cache size over time.

Structured JSON logs with per-request `trace_id` so you can grep
one request end to end.

---

## Load test

| Users | RPS | p50 | p95 | p99 | Failures |
|---|---|---|---|---|---|
| 5 | 1.8 | 550ms | 3900ms | 4500ms | 0 |
| 10 | 3.8 | 530ms | 2500ms | 3600ms | 0 |
| 20 | 8.0 | 590ms | 2000ms | 3300ms | 0 |
| 50 | 18.2 | 640ms | 820ms | 3300ms | 0 |
| 200 | 23.4 | 580ms | 700ms | 2900ms | 0 |

Zero failures across all tests. Cache warming compounds under
sustained load: p95 fell from 3900ms (cold) to 700ms (warm at 200
users). The RPS plateau at 200 users was the test client's limit,
not the service's.

Full breakdown: `docs/LOAD_TEST_RESULTS.xlsx`.

---

## What's next

Ranked by expected lift (see `docs/FAILURE_ANALYSIS.md` for
reasoning):

1. **Fix benchmark methodology**: accept multiple valid sources per
   question. Expected to lift measured Recall@5 from 76% to ~85%+
   without changing the retriever.
2. **Semantic chunking**: split on paragraph/table boundaries
   instead of character count. Expected lift on numerical and
   table-heavy questions.
3. **Query decomposition**: break multi-hop questions into
   sub-questions, retrieve for each, merge contexts. Expected lift
   on multi_hop and comparison from 50% to 70%+.
4. **Query rewriting**: LLM rewrites user question into alternative
   phrasings before retrieval. Expected lift on specific-phrase
   misses.

---

## Documentation

- [`docs/TECHNICAL_REFERENCE.md`](docs/TECHNICAL_REFERENCE.md) — every technical term, system design, 12 design decisions with alternatives, end-to-end request flow
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — architectural choices and why
- [`docs/FINDINGS.md`](docs/FINDINGS.md) — experiment log, newest first
- [`docs/FAILURE_ANALYSIS.md`](docs/FAILURE_ANALYSIS.md) — the 21 failures classified
- [`docs/INTERVIEW_TALKING_POINTS.md`](docs/INTERVIEW_TALKING_POINTS.md) — quotable insights

---

## Tech stack

**Data**: SEC EDGAR API · BeautifulSoup for XBRL stripping · PostgreSQL + pgvector · Elasticsearch 8.13

**ML / retrieval**: OpenAI text-embedding-3-small · BM25 via Elasticsearch English analyzer · Reciprocal Rank Fusion · cross-encoder/ms-marco-MiniLM-L-6-v2 and BAAI/bge-reranker-base (tested, not shipped)

**Generation**: Anthropic Claude Haiku 4.5 (primary) · OpenAI gpt-4o-mini (fallback) · Grounded prompt with citation format

**Evaluation**: Pydantic schema validation · RAGAS (Faithfulness, Answer Relevancy)

**Service**: FastAPI · Uvicorn · Pydantic · psycopg3 · redis-py · anthropic SDK · openai SDK

**Infrastructure**: Docker Compose · Prometheus · Grafana · Locust

---

## License

MIT

---

Built by Neha Rani · [HuggingFace](https://huggingface.co/neharanii) · [GitHub](https://github.com/neharanii)
