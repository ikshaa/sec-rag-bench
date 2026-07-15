"""
Generate embeddings for all chunks in the database.

Reads chunks whose embedding column is NULL, batches them through
OpenAI's text-embedding-3-small, and updates the database in place.

Idempotent: re-running only embeds chunks that don't have an embedding yet.
"""
import os

import psycopg
from dotenv import load_dotenv
from openai import OpenAI
from pgvector.psycopg import register_vector
from tqdm import tqdm

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
BATCH_SIZE = 100  # chunks per API call

DB_CONFIG = {
    "host":     os.environ["POSTGRES_HOST"],
    "port":     os.environ["POSTGRES_PORT"],
    "user":     os.environ["POSTGRES_USER"],
    "password": os.environ["POSTGRES_PASSWORD"],
    "dbname":   os.environ["POSTGRES_DB"],
}


# ---------------------------------------------------------------------------
# Step 1: Embed a batch of strings
# ---------------------------------------------------------------------------

def embed_batch(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """
    Call OpenAI to embed a list of texts.

    Returns a list of 1536-dim vectors (one per input).
    Order is preserved: output[i] corresponds to input[i].
    """
    response = client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=texts,
    )
    return [item.embedding for item in response.data]


# ---------------------------------------------------------------------------
# Step 2: Find chunks that still need embedding
# ---------------------------------------------------------------------------

def fetch_unembedded_chunks(conn: psycopg.Connection,
                            limit: int = BATCH_SIZE) -> list[tuple[int, str]]:
    """
    Return up to `limit` chunks whose embedding is NULL.

    Returns list of (id, text) tuples.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, text
            FROM chunks
            WHERE embedding IS NULL
            ORDER BY id
            LIMIT %s
            """,
            (limit,),
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Step 3: Update chunks with their embeddings
# ---------------------------------------------------------------------------

def update_embeddings(conn: psycopg.Connection,
                      rows: list[tuple[int, list[float]]]) -> None:
    """
    Update the embedding column for a batch of chunks.
    rows is a list of (chunk_id, embedding_vector) tuples.
    """
    with conn.cursor() as cur:
        cur.executemany(
            "UPDATE chunks SET embedding = %s WHERE id = %s",
            [(embedding, chunk_id) for chunk_id, embedding in rows],
        )


# ---------------------------------------------------------------------------
# Step 4: Orchestrator
# ---------------------------------------------------------------------------

def embed_all_chunks() -> None:
    """
    Embed every chunk in the database that doesn't already have an embedding.
    Processes in batches, commits after each batch.
    """
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    with psycopg.connect(**DB_CONFIG) as conn:
        # Register pgvector type adapter so Python lists ↔ pgvector vectors
        register_vector(conn)

        # Count how much work we have to do (for the progress bar)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM chunks WHERE embedding IS NULL")
            total = cur.fetchone()[0]

        if total == 0:
            print("All chunks already have embeddings. Nothing to do.")
            return

        print(f"Embedding {total} chunks in batches of {BATCH_SIZE}...\n")

        pbar = tqdm(total=total, desc="Chunks embedded")

        while True:
            batch = fetch_unembedded_chunks(conn, limit=BATCH_SIZE)
            if not batch:
                break

            chunk_ids = [row[0] for row in batch]
            texts = [row[1] for row in batch]

            embeddings = embed_batch(client, texts)

            rows_to_update = list(zip(chunk_ids, embeddings))
            update_embeddings(conn, rows_to_update)
            conn.commit()

            pbar.update(len(batch))

        pbar.close()
        print("\nDone.")


if __name__ == "__main__":
    embed_all_chunks()