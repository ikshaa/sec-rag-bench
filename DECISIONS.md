# Design Decisions

This document records significant engineering decisions and the reasoning
behind them. The goal is to capture the *why*, not just the *what*, so
future-me (or anyone reviewing the code) understands the tradeoffs.

---

## Storage

### Why pgvector instead of a dedicated vector database

We use Postgres with the pgvector extension instead of Pinecone, Qdrant,
Weaviate, or another vector-specific database. Reasoning:

- **Operational simplicity**: one database to run, monitor, and back up.
  Our infrastructure stack is already Postgres + Elasticsearch + Redis;
  adding a fourth data store has real maintenance cost.
- **Single-query joins**: pgvector allows joining vector search with
  relational metadata in one SQL statement
  (`JOIN filings ON ... ORDER BY embedding <=> query`). With a separate
  vector DB we'd need two round trips and application-level joining.
- **Scale**: at ~10K chunks, even the simplest vector search is fast.
  Dedicated vector DBs win at hundreds of millions of vectors. We're
  three orders of magnitude below that.

If the project grew to 100M+ vectors, I'd reconsider — Qdrant or
Pinecone would be reasonable next steps.

### Why 16 filings (8 companies × 2 years)

A deliberate scope choice:

- Enough data that retrieval quality actually matters
- Small enough to ingest in minutes
- Two consecutive years (2023, 2024) enables multi-hop comparison
  questions in the benchmark (e.g. "how did Tesla's risk factors change
  between 2023 and 2024?")

Companies chosen to be a mix of recognizable names with varied business
models: Apple, Microsoft, Google, Amazon, Nvidia, Tesla, Costco, Netflix.
We initially included Meta and JPMorgan but their high filing volume
pushed our target years out of EDGAR's `recent` window. Replaced with
Costco and Netflix to keep all 16 retrievals reliable.

---

## Chunking

### Naive fixed-size chunking (500 chars, 50 overlap)

This is intentionally the simplest possible chunker. It cuts through
sentences, splits paragraphs awkwardly, and produces chunks of mixed
semantic quality.

**Why start here**: the project's headline story is "I measured a
baseline and systematically improved it." A bad baseline is essential
to that story. In Week 2 we'll compare this against:
- Semantic chunking (split on topic boundaries)
- Sentence-window chunking (embed sentences, retrieve with context)
- Parent-document chunking (embed small, return large)

Each will be measured against the same benchmark. The 500/50 baseline
is the floor.

### Why 50-character overlap

Consecutive chunks overlap by 50 characters. This means sentences
near chunk boundaries appear in two chunks, at least one of which
will have enough context. Without overlap, retrieval would systematically
fail on content split exactly at boundaries.

---

## Schema

### Why `filings` and `chunks` are separate tables

Standard normalization. A chunk's metadata (company, fiscal year, etc.)
belongs to the parent filing, not duplicated per chunk. With ~7000 chunks,
denormalization would waste storage and create update anomalies.

### Why `ON DELETE CASCADE` on the foreign key

Reprocessing convenience. To re-ingest a filing with different chunking,
we delete the parent row in `filings` and all dependent chunks vanish
automatically. Cleaner than manual cleanup.

### Why a separate `idx_chunks_filing_id` index

The primary-key index covers `id` lookups, but most of our queries
filter by `filing_id` (e.g., "give me all chunks from Apple 2023").
Without an explicit index, those queries would scan the entire chunks
table.

---

## Known shortcuts / TODOs

### Placeholder metadata in `filings` table

The `ingest_chunks_to_db` script in `src/chunk.py` populates `filings`
with placeholder values for `accession_number` (`"unknown-{company}-{year}"`)
and dates (`{year}-01-01`, `{year}-12-31`). This is because the original
`src/ingest.py` saved only text, not metadata.

**Plan**: refactor `ingest.py` to save metadata alongside text (either
as JSON sidecar files or by inserting into the database directly during
download). Target: Day 4.

---

## Tooling

### Why psycopg v3 instead of v2

Psycopg v3 (released 2021) has cleaner async support, better type
inference, and modern Python conventions. v2 is still maintained but
in legacy mode. New code should use v3.

### Why Docker for Postgres / Elasticsearch / Redis

- **Reproducibility**: `docker compose up` produces an identical stack
  on any developer's machine
- **Isolation**: no risk of polluting the host with database services
  or version conflicts with other projects
- **Clean teardown**: `docker compose down -v` wipes everything

Tradeoff: Docker Desktop uses ~2GB of RAM on Mac. Worth it for the
isolation properties.