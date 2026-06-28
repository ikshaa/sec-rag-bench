"""
Chunk SEC filing text and ingest into the database.

Reads files from data/filings/, splits each into ~500-character chunks
with overlap, and inserts both filing metadata and chunks into Postgres.
"""
import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from tqdm import tqdm

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FILINGS_DIR = Path("data/filings")
CHUNK_SIZE = 500       # characters per chunk
CHUNK_OVERLAP = 50     # overlap between consecutive chunks

# Build a database connection string from .env
DB_CONFIG = {
    "host":     os.environ["POSTGRES_HOST"],
    "port":     os.environ["POSTGRES_PORT"],
    "user":     os.environ["POSTGRES_USER"],
    "password": os.environ["POSTGRES_PASSWORD"],
    "dbname":   os.environ["POSTGRES_DB"],
}


# ---------------------------------------------------------------------------
# Step 1: Pure chunking function (no DB)
# ---------------------------------------------------------------------------

def chunk_text(text: str, chunk_size: int = CHUNK_SIZE,
               overlap: int = CHUNK_OVERLAP) -> list[dict]:
    """
    Split text into overlapping fixed-size chunks.

    Returns a list of dicts: {chunk_index, text, char_start, char_end}
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks = []
    stride = chunk_size - overlap  # how far we advance between chunks
    start = 0
    chunk_index = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append({
            "chunk_index": chunk_index,
            "text": text[start:end],
            "char_start": start,
            "char_end": end,
        })
        chunk_index += 1
        if end == len(text):
            break  # last chunk reached the end of text
        start += stride

    return chunks


# ---------------------------------------------------------------------------
# Step 2: Parse filename → (company, fiscal_year)
# ---------------------------------------------------------------------------

def parse_filename(path: Path) -> tuple[str, int]:
    """
    Parse 'apple_2023.txt' → ('apple', 2023).
    """
    stem = path.stem  # 'apple_2023'
    company, year_str = stem.rsplit("_", 1)
    return company, int(year_str)


# ---------------------------------------------------------------------------
# Step 3: Database insert logic
# ---------------------------------------------------------------------------

def insert_filing_and_chunks(
    conn: psycopg.Connection,
    company: str,
    fiscal_year: int,
    text: str,
) -> tuple[int, int] | None:
    """
    Insert a filing and all its chunks into the database.

    Returns (filing_id, chunk_count), or None if the filing already exists.
    """
    with conn.cursor() as cur:
        # Check if this filing was already ingested
        cur.execute(
            "SELECT id FROM filings WHERE company = %s AND fiscal_year = %s",
            (company, fiscal_year),
        )
        existing = cur.fetchone()
        if existing:
            return None  # already ingested

        # Insert the filing.
        # We don't have accession_number/dates available here cheaply,
        # so we use placeholder values. We'll improve this in a moment.
        cur.execute(
            """
            INSERT INTO filings
                (company, fiscal_year, accession_number, filing_date,
                 report_date, char_count)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
                company,
                fiscal_year,
                f"unknown-{company}-{fiscal_year}",
                f"{fiscal_year}-01-01",
                f"{fiscal_year}-12-31",
                len(text),
            ),
        )
        filing_id = cur.fetchone()[0]

        # Chunk the text and insert all chunks
        chunks = chunk_text(text)
        chunk_rows = [
            (
                filing_id,
                c["chunk_index"],
                c["text"],
                c["char_start"],
                c["char_end"],
            )
            for c in chunks
        ]
        cur.executemany(
            """
            INSERT INTO chunks
                (filing_id, chunk_index, text, char_start, char_end)
            VALUES (%s, %s, %s, %s, %s)
            """,
            chunk_rows,
        )

        return filing_id, len(chunks)


# ---------------------------------------------------------------------------
# Step 4: Orchestrator
# ---------------------------------------------------------------------------

def ingest_chunks_to_db() -> None:
    """
    Read every .txt file in data/filings/, chunk it, and insert into the DB.
    """
    files = sorted(FILINGS_DIR.glob("*.txt"))
    if not files:
        print("No filings found in", FILINGS_DIR)
        return

    print(f"Found {len(files)} filings to process\n")

    with psycopg.connect(**DB_CONFIG) as conn:
        for path in tqdm(files, desc="Filings"):
            company, year = parse_filename(path)
            text = path.read_text(encoding="utf-8")

            result = insert_filing_and_chunks(conn, company, year, text)
            if result is None:
                tqdm.write(f"  ✓ {company} {year} already ingested, skipping")
            else:
                filing_id, chunk_count = result
                tqdm.write(
                    f"  ✓ {company} {year}: filing_id={filing_id}, "
                    f"{chunk_count} chunks"
                )
        conn.commit()


if __name__ == "__main__":
    ingest_chunks_to_db()