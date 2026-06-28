-- Enable pgvector extension (already done, but idempotent)
CREATE EXTENSION IF NOT EXISTS vector;

-- ---------------------------------------------------------------------------
-- filings: one row per 10-K we ingest
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS filings (
    id              SERIAL PRIMARY KEY,
    company         TEXT NOT NULL,
    fiscal_year     INTEGER NOT NULL,
    accession_number TEXT NOT NULL,
    filing_date     DATE NOT NULL,
    report_date     DATE NOT NULL,
    char_count      INTEGER NOT NULL,
    ingested_at     TIMESTAMPTZ DEFAULT NOW(),

    -- A company shouldn't have two filings for the same fiscal year
    UNIQUE (company, fiscal_year)
);

-- ---------------------------------------------------------------------------
-- chunks: many rows per filing
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    id              SERIAL PRIMARY KEY,
    filing_id       INTEGER NOT NULL REFERENCES filings(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    text            TEXT NOT NULL,
    char_start      INTEGER NOT NULL,
    char_end        INTEGER NOT NULL,
    embedding       vector(1536),

    UNIQUE (filing_id, chunk_index)
);

-- Index for fast lookups by filing
CREATE INDEX IF NOT EXISTS idx_chunks_filing_id ON chunks(filing_id);