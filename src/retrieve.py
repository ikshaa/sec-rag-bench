import os

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector

from src.embed import embed_batch

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_CONFIG = {
    "host":     os.environ["POSTGRES_HOST"],
    "port":     os.environ["POSTGRES_PORT"],
    "user":     os.environ["POSTGRES_USER"],
    "password": os.environ["POSTGRES_PASSWORD"],
    "dbname":   os.environ["POSTGRES_DB"],
}


# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------

def retrieve(query: str, top_k: int = 5) -> list[dict]:
    """
    Find the top_k most semantically similar chunks to the query.

    Returns a list of dicts with keys: chunk_id, text, company,
    fiscal_year, distance (lower = more similar).
    """
    # Step 1: Create OpenAI client
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    # Step 2: Embed the query (embed_batch takes a list, returns a list)
    query_embedding = embed_batch(client, [query])[0]

    # Step 3: Open DB connection, register pgvector adapter
    with psycopg.connect(**DB_CONFIG) as conn:
        register_vector(conn)

        with conn.cursor() as cur:
            # Step 4: SQL with JOIN and cosine distance
            cur.execute(
                """
                SELECT
                    chunks.id,
                    chunks.text,
                    filings.company,
                    filings.fiscal_year,
                    chunks.embedding <=> %s::vector AS distance
                FROM chunks
                JOIN filings ON chunks.filing_id = filings.id
                ORDER BY chunks.embedding <=> %s::vector
                LIMIT %s
                """,
                (query_embedding, query_embedding, top_k),
            )
            rows = cur.fetchall()

    # Step 5: Convert rows to dicts
    results = []
    for row in rows:
        results.append({
            "chunk_id":    row[0],
            "text":        row[1],
            "company":     row[2],
            "fiscal_year": row[3],
            "distance":    float(row[4]),
        })

    return results


if __name__ == "__main__":
    # Quick smoke test
    import json
    results = retrieve("What were Apple's main risk factors?", top_k=3)
    for r in results:
        print(f"\n--- {r['company']} {r['fiscal_year']} (distance={r['distance']:.4f}) ---")
        print(r['text'][:200])