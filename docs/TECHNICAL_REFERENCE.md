# SEC-RAG-Bench: Complete Technical Reference

Everything you built, in plain language, with the reasoning behind
each choice and the alternatives you could have picked. This document
is designed to be your single source of truth for interview prep.

Read it top to bottom once. Then skim the glossary and design
decisions sections before any interview.

---

## 1. Project overview

**What it is**: An evaluation-driven RAG (Retrieval Augmented
Generation) system that answers questions about SEC 10-K filings
with cited sources.

**What makes it unusual**: Most RAG projects demo a chatbot and
stop. This project built a 100-question benchmark first, then
measured every retrieval and generation decision against it. Each
architectural choice is backed by a number.

**Scale**: 10,527 chunks from 15 filings (8 companies, fiscal
years 2022-2024).

**Headline numbers**:
- Recall@5: 68% baseline (dense vector) to 76% (hybrid)
- Faithfulness: 85% (model grounds in retrieved context)
- Semantic cache gives 12x latency reduction on repeated queries
- Refusal accuracy: 100% (model correctly says "I don't know" when answer isn't retrievable)

---

## 2. System architecture

```
                                  ┌─────────────────────────┐
   HTTP POST /query              │   FastAPI Service       │
   {question: "..."}        ───> │   (src/api.py)          │
                                  └──────────┬──────────────┘
                                             │
                                             ▼
                                  ┌─────────────────────────┐
                                  │  Semantic Cache Check   │
                                  │  (Redis via src/cache)  │
                                  └──────┬───────────┬──────┘
                                   HIT   │           │ MISS
                                  (return)           ▼
                                        ┌──────────────────────────┐
                                        │  Hybrid Retrieval        │
                                        │  (src/retrieve_hybrid)   │
                                        └──┬──────────────────┬────┘
                                           ▼                  ▼
                                  ┌────────────────┐  ┌──────────────┐
                                  │ Vector (dense) │  │ BM25 (sparse)│
                                  │ pgvector in    │  │ Elasticsearch│
                                  │ Postgres       │  │              │
                                  └────────┬───────┘  └──────┬───────┘
                                           │                 │
                                           ▼                 ▼
                                        ┌─────────────────────┐
                                        │ Reciprocal Rank     │
                                        │ Fusion (RRF)        │
                                        └──────────┬──────────┘
                                                   ▼
                                        ┌─────────────────────┐
                                        │ Grounded Generation │
                                        │ (LLM Gateway)       │
                                        │ Anthropic → OpenAI  │
                                        │ fallback            │
                                        └──────────┬──────────┘
                                                   ▼
                                        ┌─────────────────────┐
                                        │ Response + Metrics  │
                                        │ (Prometheus)        │
                                        │ + Structured Logs   │
                                        └──────────┬──────────┘
                                                   ▼
                                             (back to client)

                        Prometheus scrapes /metrics every 10s
                        Grafana queries Prometheus for dashboards
```

**Four services in docker-compose**:
- `postgres` with pgvector extension: stores chunks and their embeddings
- `elasticsearch`: BM25 keyword index on the same chunks
- `redis`: semantic cache for query responses
- `prometheus` + `grafana`: metrics scraping and visualization

**One FastAPI service** running on the host (not in a container,
so you can hot-reload during development).

---

## 3. End-to-end request flow

Walk through exactly what happens when someone sends a query.

### Request:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What were Tesla total revenues in 2023?", "top_k": 5}'
```

### Step 1: FastAPI receives it
- Uvicorn (ASGI server) accepts the TCP connection
- FastAPI matches the URL `/query` to the `query()` function in `src/api.py`
- Pydantic validates the JSON body against `QueryRequest`: checks `question` is 3-1000 chars, `top_k` is 1-20
- If validation fails, FastAPI returns 422 before your function runs

### Step 2: Observability setup
- `trace_request("/query")` context manager generates a trace_id (short UUID)
- Logs a JSON line: `{"event": "request_started", "trace_id": "a3b2c1d4", ...}`
- Starts a timer for latency measurement

### Step 3: Semantic cache check
- Call `get_cached(question)` in `src/cache.py`
- The function embeds the incoming question using OpenAI text-embedding-3-small (1536-dim vector)
- Scans every cached entry in Redis, computing cosine similarity between the new query embedding and each cached embedding
- If best match ≥ 0.95: cache HIT, return cached response (skip pipeline)
- If best match < 0.95: cache MISS, continue to pipeline

Say we have a MISS. Keep going.

### Step 4: Hybrid retrieval
- Call `retrieve_hybrid(question, top_k=5)` in `src/retrieve_hybrid.py`
- This fans out to two retrievers in parallel-ish calls:

  **4a. Vector retrieval** (`src/retrieve.py`):
  - Embeds the question with OpenAI text-embedding-3-small
  - Runs SQL in Postgres: `SELECT chunk_id, text, ... ORDER BY embedding <=> query_vector LIMIT 20`
  - The `<=>` is pgvector's cosine distance operator
  - Returns top 20 chunks by vector similarity

  **4b. BM25 retrieval** (`src/retrieve_bm25.py`):
  - Sends the question to Elasticsearch's `/sec_chunks/_search` endpoint with a `match` query
  - Elasticsearch tokenizes the query using the English analyzer (lowercase, stopword removal, stemming)
  - Scores each indexed chunk by BM25 (TF-IDF with length normalization and term saturation)
  - Returns top 20 chunks by BM25 score

- Reciprocal Rank Fusion combines them:
  - For each chunk, compute `score = sum over retrievers of 1/(60 + rank_in_that_retriever)`
  - A chunk ranked #1 in vector gets `1/61 = 0.0164`. If it's also #1 in BM25, it gets another `1/61`, total `0.0328`
  - A chunk ranked #1 in vector but not in BM25 top 20 gets only `0.0164`
  - Chunks that both retrievers rank highly bubble to the top
- Returns top 5 chunks sorted by RRF score

### Step 5: Grounded generation (LLM Gateway)
- Call `answer_question(question, top_k=5, retriever=retrieve_hybrid)` in `src/generate.py`
- Build a prompt with the 5 retrieved chunks numbered [1] through [5]:
  ```
  You are answering a question about SEC 10-K filings.
  Use ONLY the context below to answer. If the context does not
  contain enough information to answer, say "I don't have enough
  information in the provided context to answer this question."
  When you cite information, use the source numbers like [1], [2], etc.

  Context:
  [1] Source: tesla 2023 10-K
  <chunk 1 text>

  ---

  [2] Source: tesla 2024 10-K
  <chunk 2 text>

  (... etc for 5 chunks ...)

  Question: What were Tesla total revenues in 2023?

  Answer:
  ```
- Call the LLM Gateway (`src/llm_gateway.py`) which:
  1. Tries Anthropic Claude Haiku 4.5 first
  2. If Anthropic returns 429 (rate limit), 5xx (server error), or times out, falls back to OpenAI gpt-4o-mini
  3. Returns a `GatewayResponse` with the text, which provider served it, and whether fallback was used
- The LLM reads the prompt, generates an answer like "Tesla total revenues in 2023 were $96,773 million [2]"

### Step 6: Cache the response
- Call `set_cached(question, response, ttl=3600)` in `src/cache.py`
- Embed the question again (same model as before)
- Store entry in Redis: UUID key → JSON blob with query, embedding, response
- Entry expires after 1 hour (TTL)

### Step 7: Observability finalization
- Prometheus counters increment:
  - `secrag_queries_total{cache_hit="false", provider="anthropic", fallback_used="false"}` += 1
  - `secrag_query_latency_ms_bucket{cache_hit="false", le="5000"}` += 1 (or whichever bucket)
- Structured log: `{"event": "query_served", "trace_id": "a3b2c1d4", "cache_hit": false, "provider": "anthropic", "latency_ms": 4832}`
- `trace_request` context manager exits, logs `request_finished`

### Step 8: Response goes back to client
- FastAPI builds the response dict
- Pydantic validates it against `QueryResponse` schema
- Serializes to JSON, sets Content-Type header, returns 200 OK
- Client sees:
  ```json
  {
    "answer": "Tesla total revenues in 2023 were $96,773 million [2]",
    "sources": [...],
    "model": "claude-haiku-4-5",
    "latency_ms": 4832,
    "cache_hit": false,
    "matched_query": null,
    "provider": "anthropic",
    "fallback_used": false
  }
  ```

**Behind the scenes, every 10 seconds**, Prometheus hits
`/metrics`, reads the latest counter values, and stores them in its
time-series database. Grafana queries Prometheus every few seconds
to update your dashboard.

---

## 4. Technical glossary

Every term in your project, in plain language. Organized by subsystem.

### Data and retrieval

**SEC EDGAR**: The U.S. Securities and Exchange Commission's public
database of corporate filings. Free API with a required User-Agent
header. Returns filings in HTML with embedded financial data tags.

**10-K filing**: An annual report U.S. public companies must file
with the SEC. Contains income statements, balance sheets, cash flow,
risk factors, MD&A. Each one is 100-300 pages.

**Inline XBRL (iXBRL)**: The format SEC 10-Ks come in. HTML
documents with embedded financial data tags (`<ix:nonFraction>`,
`<ix:hidden>`, etc.). You strip these during ingestion to get
clean text.

**Chunking**: Splitting a long document into smaller pieces so
retrieval can target specific sections. You used fixed-size (500
characters with 50-character overlap). Alternatives include
semantic chunking (split on structural boundaries) and
parent-document retrieval.

**Embedding**: A dense vector representation of text, usually
~1536 numbers (dimensions). Semantically similar text produces
similar vectors. You used OpenAI's `text-embedding-3-small`
(1536 dims, $0.02 per 1M tokens).

**Vector database**: Database that stores vectors and supports
nearest-neighbor search. You used Postgres with the pgvector
extension. Alternatives: Pinecone (managed), Weaviate, Qdrant,
Milvus, Chroma.

**pgvector**: Postgres extension that adds a `vector` type and
distance operators. Lets you run `SELECT ... ORDER BY embedding
<=> query_vector LIMIT 5` as regular SQL.

**Cosine similarity / cosine distance**: Measures the angle
between two vectors. Range: -1 (opposite) to 1 (identical).
Cosine distance = 1 - cosine similarity. The `<=>` operator in
pgvector returns cosine distance.

**BM25**: A keyword search algorithm that scores documents by
how many query terms they contain, weighted by term rarity
(IDF: inverse document frequency), with saturation (10 mentions
isn't 10x better than 1) and length normalization (short
documents matching a term are more significant than long ones).

**TF-IDF (Term Frequency - Inverse Document Frequency)**: Older
cousin of BM25. TF = how often the term appears in this document.
IDF = log(total docs / docs containing term), so rare terms get
more weight.

**Elasticsearch**: An open-source search engine built on Lucene.
Industry standard for keyword search, log aggregation, and
analytics. You used it just for BM25.

**Analyzer / stemmer / stopwords**: Elasticsearch processing
steps. Analyzer breaks text into tokens. Stemmer reduces "running"
to "run" so searches match related word forms. Stopwords remove
common words like "the", "a", "is" that don't help ranking.

**Hybrid retrieval**: Combining dense (vector) and sparse (BM25)
retrievers. Captures both semantic similarity and exact keyword
matching.

**Reciprocal Rank Fusion (RRF)**: A simple algorithm to combine
rankings from multiple retrievers without needing to normalize
their scores. For each document, sum `1/(60 + rank)` across
retrievers. No training, no tuning. The constant 60 is from the
original paper (Cormack, Clarke, Buettcher 2009).

**Cross-encoder (reranker)**: A model that takes a query and a
document together as input and outputs a relevance score. Slower
than bi-encoders (full transformer forward pass per pair) but
more accurate. You tried `ms-marco-MiniLM-L-6-v2` and
`BAAI/bge-reranker-base`. Both underperformed hybrid alone.

**Bi-encoder**: A model that encodes query and document
separately into embeddings, then compares via cosine similarity.
Fast because document embeddings are pre-computed. This is what
your vector retrieval uses.

**Reranking**: The two-stage pattern where a fast retriever
pulls many candidates (say 20), then a slower cross-encoder
rescales them to pick the top 5. Standard production practice.
Your measurements showed it didn't help your workload.

**Recall@K**: Fraction of questions where the correct source
chunk appears in the top K retrieved results. Your main
retrieval metric. Hybrid gave 76% Recall@5.

**Precision@K**: Fraction of the top K retrieved chunks that
are relevant. Lower bar than Recall@K because only one chunk
usually contains the answer.

### Generation and evaluation

**RAG (Retrieval Augmented Generation)**: Give the LLM retrieved
context plus the question, so it answers from the context instead
of from its training. Prevents hallucination and keeps answers
tied to a source.

**Grounded generation**: The LLM is instructed to answer only
from the provided context. If the context doesn't contain the
answer, it must say "I don't know" rather than make something up.

**Citation**: The LLM references its sources inline as [1], [2],
etc. Your prompt tells it to use these citations and your retrieved
chunks are numbered in the prompt accordingly.

**Refusal accuracy**: Fraction of unanswerable questions where
the LLM correctly says "I don't know" instead of fabricating.
Hybrid achieved 100%.

**RAGAS**: A framework for evaluating RAG systems with LLM
judges. Specifically faithfulness and answer relevancy.

**Faithfulness**: Does every claim in the answer trace back to
the retrieved context? Measured by an LLM judge. Your system
scored 82-85% depending on retriever.

**Answer relevancy**: Does the answer actually address what was
asked? Also LLM-judged. Hybrid scored 69%.

**LLM-as-judge**: Using one LLM to evaluate another LLM's output.
Not perfect but much cheaper than human annotation.

### Service and infrastructure

**FastAPI**: A modern Python web framework. Type-hint-driven,
Pydantic-validated, async-by-default, auto-generates OpenAPI
docs at `/docs`.

**Pydantic**: Python library for data validation using type hints.
Define a class with field types, Pydantic validates incoming data
and converts it. Powers FastAPI's request/response validation.

**Uvicorn**: ASGI server. Runs FastAPI applications. ASGI is the
async successor to WSGI (which runs Flask/Django).

**ASGI vs WSGI**: WSGI is the synchronous Python web server
protocol (one request at a time per worker). ASGI is the async
version (one worker can handle many concurrent requests).

**Health check (`/health`)**: An endpoint that returns 200 as long
as the server process is running. Used by load balancers and
orchestrators to detect if a container is alive.

**Readiness check (`/ready`)**: An endpoint that also verifies
downstream dependencies (Postgres, Elasticsearch). Returns 503
if anything is broken, so orchestrators don't route traffic to
a container that can't actually serve requests.

**Docker Compose**: YAML file that defines multi-container
applications. Your `docker-compose.yml` has postgres,
elasticsearch, redis, prometheus, grafana. `docker compose up -d`
starts them all.

### Caching

**Semantic cache**: Cache entries are matched by embedding
similarity, not string equality. Rephrasings of the same question
hit the same cache entry.

**Similarity threshold**: The cosine similarity cutoff for a
cache hit. You use 0.95. Lower threshold = more cache hits but
higher risk of returning the wrong answer. Higher threshold =
safer but fewer hits.

**TTL (time to live)**: How long an entry lives in cache before
expiring. You use 3600 seconds (1 hour). Prevents stale data
from accumulating.

**Redis**: In-memory data store, often used as a cache or
message broker. Fast key-value access. You store cache entries
as JSON blobs.

### Multi-provider gateway

**LLM Gateway**: An abstraction layer between your code and the
actual LLM provider. Lets you swap providers without changing
caller code.

**Fallback**: If the primary provider fails with a retryable
error, try the backup. You fall back from Anthropic to OpenAI.

**Retryable error**: An error you can recover from by retrying,
usually with a different provider: rate limit (429), server
error (5xx), timeout, overloaded (529). Auth errors (401) and
bad requests (400) are NOT retryable.

### Observability

**Observability**: The ability to understand what's happening
inside a running system. Three pillars: logs, metrics, traces.

**Prometheus**: Open-source metrics collection and time-series
database. Scrapes a `/metrics` endpoint on each target every N
seconds. You configured it to scrape your API every 10 seconds.

**Grafana**: Open-source dashboard tool. Connects to Prometheus
(and many other data sources) and visualizes queries as charts.

**Counter**: A metric that only goes up. Example:
`secrag_queries_total` counts total requests served.

**Histogram**: A metric that tracks the distribution of values
in buckets. Example: `secrag_query_latency_ms_bucket{le="5000"}
= 10` means 10 requests completed in <=5000ms. Histograms are
what you compute percentiles from.

**Gauge**: A metric that can go up or down. Example:
`secrag_cache_size` is the current number of cache entries.

**Label**: Key-value tags on a metric that let you slice it.
Example: `secrag_queries_total{cache_hit="true", provider="anthropic"}`.
Grafana queries filter and group by labels.

**PromQL**: Prometheus's query language. Examples:
- `rate(secrag_queries_total[1m])` = requests per second over last minute
- `histogram_quantile(0.95, rate(secrag_query_latency_ms_bucket[5m]))` = p95 latency
- `secrag_cache_size` = current gauge value

**p50, p95, p99 (percentile)**: pNN is the latency below which NN%
of requests fall. p95 = 5000ms means 95% of requests finish in
<=5000ms. The slowest 5% take longer.

**SLO (Service Level Objective)**: A commitment to a performance
target. Example: "p95 latency for /query stays under 2000ms, 99%
of the time, measured monthly."

**Structured logging**: Logs emitted as JSON instead of plain
text. Makes them parseable by tools like Loki, Datadog, Splunk.
Each log event has fields you can filter and query by.

**Trace ID**: A unique ID attached to every log line from one
request. Lets you grep by trace_id to see every log for one
specific request. Standard distributed-tracing pattern.

---

## 5. Design decisions with alternatives

For each major decision: what you chose, why, and what else
you could have picked. These are the "trade-off" questions
interviewers love.

### Decision 1: Postgres + pgvector vs dedicated vector DB

**Chose**: Postgres with pgvector extension.

**Why**:
- One database for both chunks (text + metadata) and embeddings
- Standard SQL joins between filings table and chunks table
- Local dev is trivial (just docker compose up)
- Free and open source
- Scales to millions of vectors with proper indexing (HNSW)

**Alternatives**:
- **Pinecone**: Managed service, scales well, costs money per
  million vectors stored. Great if you don't want to run anything.
- **Weaviate**: Open source, standalone vector DB with GraphQL
  interface. Good for production at scale.
- **Qdrant**: Fast, Rust-based, built specifically for vectors.
  Simpler than Weaviate.
- **Milvus**: Large-scale enterprise-grade vector DB. Overkill for
  your 10K chunks.
- **Chroma**: Lightweight, embedded, good for prototypes.

**Interview talking point**: "I kept everything in Postgres
because the project has <1M chunks and I value one less moving
part. For a 100M-chunk corpus I'd move to a dedicated vector DB
for the better index structures and sharding support."

### Decision 2: Fixed-size vs semantic chunking

**Chose**: Fixed-size 500 characters, 50-character overlap.

**Why**:
- Simplest possible baseline
- Deterministic and reproducible
- Fast to implement
- Gave a clear floor to measure improvements against

**Alternatives**:
- **Semantic chunking**: Split on structural boundaries (markdown
  headers, paragraph breaks, section endings). Better preserves
  context (an income statement stays in one chunk) but harder
  to implement and depends on document format.
- **Parent-document retrieval**: Index small chunks for retrieval
  precision but return the whole surrounding "parent" document at
  generation time. Best of both worlds but more complex.
- **Recursive chunking**: Split on paragraphs first, then
  sentences if too long, then characters. Pragmatic middle ground.

**What you discovered**: Your Tesla revenue question exposed the
weakness of fixed-size chunking. The income statement got split
mid-table, so the chunk containing "Total revenues" was separate
from the chunk containing "Automotive revenues". Semantic chunking
would have kept the whole table in one chunk.

**Interview talking point**: "I started with fixed-size because
it gave a clear baseline to measure against. My Tesla revenue
case showed exactly where it breaks: tables getting split across
chunks. Semantic chunking is the next experiment."

### Decision 3: BM25 + vector hybrid vs vector alone

**Chose**: Hybrid via Reciprocal Rank Fusion.

**Why** (backed by measurements):
- BM25 beat vector on negation (+14pp recall) and numerical (+6pp)
- Vector beat BM25 on multi-hop (+7pp) and comparison (+12pp)
- Hybrid captured both wins: Recall@5 jumped from 68% to 76%

**Alternatives**:
- **Vector only**: Most popular choice, simpler. Loses the
  exact-match wins.
- **BM25 only**: Classic search engines. Misses semantic matches.
- **Weighted score fusion**: Normalize scores to [0,1] and
  compute weighted average. Requires tuning the weights.
- **Learning-to-rank**: Train a model to combine signals.
  Requires labeled training data.

**Interview talking point**: "I benchmarked each retriever
independently before combining them. The complementary category
wins made hybrid the right call, and RRF requires no tuning or
training."

### Decision 4: RRF vs weighted score fusion

**Chose**: Reciprocal Rank Fusion with K=60.

**Why**:
- Zero hyperparameters to tune (K=60 is standard, works out of box)
- Score-agnostic: works with any pair of retrievers without
  normalization
- No training data required
- Well-known baseline in information retrieval literature

**Alternatives**:
- **Weighted score fusion**: `0.6 * cosine_sim + 0.4 * bm25_score`.
  Requires normalizing scores to the same range and tuning weights.
- **Learned fusion**: Train a model on query-document pairs with
  relevance labels. Best quality but requires labeled data.

**Interview talking point**: "RRF was the right call because I
didn't have training data for learned fusion, and weighted score
fusion would have required normalizing cosine distance against
BM25 scores, which live in different ranges."

### Decision 5: Cross-encoder reranker (and why NOT shipped)

**Chose**: Tested both ms-marco and BGE rerankers, shipped neither.

**Why** (backed by measurements):
- ms-marco reranker: Recall@5 dropped to 74% (from 76% hybrid)
- BGE reranker: Recall@5 dropped to 75% (still below hybrid)
- Both lifted Precision@5 by ~0.5pp (tiny)
- Both regressed on multi-hop (reranker promotes single most-relevant
  chunk, pushes bridge chunks out of top-5)

**Alternatives**:
- **Ship reranking anyway**: "It's industry standard". This would
  have been worse than hybrid alone. The data showed it.
- **Fine-tune the reranker on your domain**: Would require creating
  training pairs from your benchmark. High effort, uncertain payoff.
- **Larger top-k after rerank**: Keep top-10 instead of top-5.
  Preserves recall but changes the metric definition.

**Interview talking point**: "This is the most important finding
in the project. I tested two rerankers, both underperformed hybrid
alone, and I had the data to prove it. If I'd shipped reranking
because it's the default recommendation, my system would have been
worse and I wouldn't have known."

### Decision 6: Claude Haiku 4.5 vs other LLMs

**Chose**: Claude Haiku 4.5 as primary, GPT-4o-mini as fallback.

**Why**:
- Haiku 4.5 is cheap (~$0.80 per 1M input tokens) and fast
- Grounded answering with citations doesn't need top-tier reasoning
- Haiku 4.5 is well-calibrated for refusal (knows when it doesn't know)

**Alternatives**:
- **Claude Opus**: Overkill for grounded summarization, 15x more
  expensive
- **GPT-4o**: Comparable quality but more expensive than Haiku
- **GPT-4o-mini**: What you're using as fallback. Cheap, fast,
  slightly less reliable on refusal in testing
- **Llama 3 70B via Groq**: Fast, cheap, requires more prompt
  engineering for grounding

**Interview talking point**: "I chose Haiku because grounded
answering is a comprehension task, not a reasoning task. Reasoning
models like Opus or o1 would be overkill and 10-20x more expensive."

### Decision 7: FastAPI vs Flask or Django

**Chose**: FastAPI.

**Why**:
- Pydantic schema validation (free input/output validation)
- Async by default (one worker handles many concurrent requests)
- Auto-generated OpenAPI docs at `/docs`
- Type-hint driven (IDE autocomplete and type checking)

**Alternatives**:
- **Flask**: Older, more manual. Would require writing all the
  validation code yourself.
- **Django**: Comes with ORM, admin, auth. Overkill for a RAG API
  with no users.
- **Starlette**: FastAPI is built on top of Starlette. You could
  go lower-level but you'd lose the Pydantic integration.
- **Node/Express**: Great if the rest of your stack is JS.
  Python ecosystem is better for ML.

**Interview talking point**: "FastAPI gave me validation, type
safety, and auto-generated docs for free. The ML libraries are all
Python, so staying in Python avoided a context switch."

### Decision 8: Redis vs in-memory Python dict for caching

**Chose**: Redis.

**Why**:
- Survives server restarts (in-memory dict is lost on restart)
- Shareable across multiple API workers if you scale horizontally
- Standard tool, well-understood operationally
- TTL support out of the box

**Alternatives**:
- **In-memory dict**: Simplest. Lost on restart. Doesn't scale
  past one worker.
- **Memcached**: Older, simpler than Redis. Fewer features.
- **DynamoDB / Firestore**: Managed, cloud-native. Overkill for a
  side project.

**Interview talking point**: "Redis gave me persistence across
restarts and horizontal scaling for free. If I scaled to multiple
API replicas tomorrow, the cache just works."

### Decision 9: Semantic cache vs string-match cache

**Chose**: Semantic (embedding similarity with 0.95 threshold).

**Why**:
- Real users rephrase questions constantly
- String match would miss "Tesla 2023 revenue" vs "What was
  Tesla's revenue in 2023"
- Measured 12x latency reduction on cache hits
- Threshold tuning gives explicit control over hit/miss tradeoff

**Alternatives**:
- **String match**: 0% hit rate for real traffic. Only works for
  bots repeating identical queries.
- **Normalized string match**: Lowercase, strip punctuation.
  Marginally better than pure string match. Still misses rephrases.
- **Prompt hash**: Hash the full prompt (including context) and
  cache by that. Doesn't help with query rephrasing.

**Interview talking point**: "Semantic cache was the only option
that would meaningfully hit real traffic. String match would be
near-useless."

### Decision 10: Similarity threshold of 0.95

**Chose**: 0.95 cosine similarity.

**Why**:
- Tight enough that different intents don't collide (your
  "Tesla earn" vs "Tesla revenue" test showed this works)
- Loose enough that normal rephrases hit (your "revenue" vs
  "revenues" test confirmed this)
- Empirically tuned on your own benchmark

**Alternatives**:
- **0.98**: Very safe, nearly string-match. Minimal hits.
- **0.90**: More hits, risk of returning wrong answers for
  semantically similar but different questions.
- **Adaptive threshold**: Learn the right threshold per query
  type. Complex, requires training data.

**Interview talking point**: "I picked 0.95 by testing explicit
rephrases. Lower would have risked serving the wrong answer when
'revenues' and 'earnings' collide. Higher would have missed
normal paraphrasing."

### Decision 11: Prometheus + Grafana vs cloud monitoring

**Chose**: Prometheus + Grafana, both self-hosted via Docker.

**Why**:
- Free and open source
- Industry standard (every ops engineer knows them)
- Runs locally for development, same stack scales to production
- No vendor lock-in

**Alternatives**:
- **Datadog**: Managed, polished UI, expensive. Great for teams
  that want managed observability.
- **New Relic**: Similar to Datadog, slightly cheaper.
- **CloudWatch (AWS) / Stackdriver (GCP)**: Cloud-native,
  tightly integrated with the cloud provider.
- **Honeycomb**: Great for distributed tracing specifically.

**Interview talking point**: "Prometheus + Grafana is the open
source standard. Running it locally means my dev environment
mirrors what I'd deploy to Kubernetes."

### Decision 12: Multi-provider LLM gateway

**Chose**: Primary Anthropic, fallback OpenAI, same prompt to
both, retryable-error detection.

**Why**:
- Single-provider dependency = your service is down when they're
  down
- Both providers charge pay-per-use, no commitment
- Both support the same conversational chat format

**Alternatives**:
- **Single provider**: Simpler but fragile
- **LiteLLM library**: Does what your gateway does but as a
  dependency. Fine choice. You built your own to understand
  the mechanics.
- **Full retry logic with exponential backoff**: More robust.
  Your version is simple on purpose.

**Interview talking point**: "The gateway was 100 lines of code
and gave me vendor independence. If Anthropic has an outage,
users don't notice because OpenAI serves the fallback."

---

## 6. The "I understand this completely" test

Can you answer these without looking at anything?

1. What's the difference between a bi-encoder and a cross-encoder?
2. Why does BM25 beat vector search on negation questions?
3. What does `1/(60 + rank)` represent in RRF?
4. Why did you choose 0.95 as the cache similarity threshold?
5. Why did you fall back to OpenAI from Anthropic, not the reverse?
6. What is the difference between `/health` and `/ready`?
7. What's the difference between a Prometheus counter, histogram, and gauge?
8. What is p95 and why do we care about it instead of mean?
9. Why do multi-hop questions sit at 50% recall across every retriever you tested?
10. How does the semantic cache distinguish between semantically different queries that happen to share words?

If any of these feel shaky, re-read the matching section above.
That's your interview prep plan right there.

---

## 7. One-sentence summary for every subsystem

Memorize these. They're what you say when someone asks "what did
you build for X?".

- **Ingestion**: Downloaded 15 SEC 10-K filings from EDGAR, stripped XBRL tags, extracted clean text, saved to Postgres filings table.
- **Chunking**: Split each filing into 500-character chunks with 50-character overlap, stored in Postgres chunks table.
- **Embedding**: Generated OpenAI text-embedding-3-small vectors (1536-dim) for each chunk, stored as pgvector columns.
- **Benchmark**: Hand-wrote 100 questions across 6 categories, anchored to specific source chunks, with Pydantic schema validation.
- **Vector retrieval**: Cosine similarity search over pgvector embeddings using the `<=>` operator.
- **BM25 retrieval**: Indexed all chunks in Elasticsearch with an English analyzer, retrieve via match query.
- **Hybrid retrieval**: Reciprocal Rank Fusion over top-20 from each retriever, keep top-5.
- **Reranking (tested, not shipped)**: Cross-encoder rerankers on hybrid candidates. Both reduced recall, so I kept hybrid alone.
- **Generation**: Grounded prompt with numbered sources, LLM instructed to cite [1][2] and refuse when context is insufficient.
- **API**: FastAPI service with Pydantic schemas, /query /health /ready /cache /metrics endpoints.
- **Caching**: Redis semantic cache keyed by query embedding, 0.95 cosine threshold, 1-hour TTL, 12x latency reduction on hits.
- **LLM Gateway**: Anthropic Claude Haiku 4.5 primary, OpenAI gpt-4o-mini fallback on retryable errors.
- **Observability**: Prometheus metrics (counters, histograms, gauges) scraped every 10 seconds, Grafana dashboard with 4 panels, structured JSON logging with per-request trace IDs.

---

## 8. If asked "walk me through this project"

Lead with the thesis, then architecture, then one proud finding,
then one honest limitation.

> "SEC-RAG-Bench is an evaluation-driven RAG system over SEC
> 10-K filings. The core idea was to build a 100-question
> benchmark before writing any retrieval code, so every
> architectural decision could be measured. My baseline dense
> retriever hit 68% Recall@5. I added BM25 as a complementary
> keyword retriever, measured where each one won by category,
> and combined them via Reciprocal Rank Fusion. Hybrid lifted
> Recall@5 to 76%. The service runs behind FastAPI with Redis
> semantic caching that cuts repeat-query latency by 12x, a
> multi-provider LLM gateway that falls back from Anthropic to
> OpenAI on retryable errors, and full Prometheus/Grafana
> observability. The thing I'm most proud of is testing two
> cross-encoder rerankers and finding they both hurt recall for
> this workload, which is counterintuitive since reranking is
> standard practice. The limitation I'd call out is that
> multi-hop and comparison questions sit at exactly 50% recall
> across every retriever I tested, because they need
> information from two filings in one answer. The next step is
> query decomposition."

That's 180 words, hits every important beat, and gives the
interviewer three natural follow-up directions (the benchmark
methodology, the reranker finding, the multi-hop ceiling).
