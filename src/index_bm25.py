"""
Index all chunks from Postgres into Elasticsearch with BM25 scoring.
Mirrors the Postgres chunk table so we can retrieve the same chunk_ids
via keyword search instead of vector similarity.
"""

import os
import psycopg
from dotenv import load_dotenv
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk

load_dotenv()

INDEX_NAME = "sec_chunks"

ES_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
ES_PORT = os.getenv("ELASTICSEARCH_PORT", "9200")
ES_URL = f"http://{ES_HOST}:{ES_PORT}"

PG_HOST = os.getenv("POSTGRES_HOST", "localhost")
PG_PORT = os.getenv("POSTGRES_PORT", "5432")
PG_USER = os.getenv("POSTGRES_USER")
PG_PASSWORD = os.getenv("POSTGRES_PASSWORD")
PG_DB = os.getenv("POSTGRES_DB")
DB_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"


def create_index(es: Elasticsearch) -> None:
    """Drop and recreate the index with an English analyzer tuned for filings."""
    if es.indices.exists(index=INDEX_NAME):
        es.indices.delete(index=INDEX_NAME)
        print(f"Deleted existing index: {INDEX_NAME}")

    es.indices.create(
        index=INDEX_NAME,
        settings={
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "english_financial": {
                        "type": "custom",
                        "tokenizer": "standard",
                        "filter": ["lowercase", "english_stop", "english_stemmer"],
                    }
                },
                "filter": {
                    "english_stop": {"type": "stop", "stopwords": "_english_"},
                    "english_stemmer": {"type": "stemmer", "language": "english"},
                },
            },
        },
        mappings={
            "properties": {
                "text": {"type": "text", "analyzer": "english_financial"},
                "company": {"type": "keyword"},
                "fiscal_year": {"type": "integer"},
                "chunk_index": {"type": "integer"},
            }
        },
    )
    print(f"Created index: {INDEX_NAME}")


def fetch_chunks(db_url: str):
    """Pull every chunk with its filing metadata from Postgres."""
    sql = """
        SELECT c.id AS chunk_id, c.text, c.chunk_index, f.company, f.fiscal_year
        FROM chunks c
        JOIN filings f ON c.filing_id = f.id
        ORDER BY c.id
    """
    with psycopg.connect(db_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)
            for chunk_id, text, chunk_index, company, fiscal_year in cur:
                yield {
                    "_index": INDEX_NAME,
                    "_id": str(chunk_id),
                    "_source": {
                        "text": text,
                        "chunk_index": chunk_index,
                        "company": company,
                        "fiscal_year": fiscal_year,
                    },
                }


def main() -> None:
    es = Elasticsearch(ES_URL)
    if not es.ping():
        raise RuntimeError(f"Could not connect to Elasticsearch at {ES_URL}")

    create_index(es)

    print("Indexing chunks...")
    success, failed = bulk(es, fetch_chunks(DB_URL), chunk_size=500)
    print(f"Indexed {success} chunks")
    if failed:
        print(f"Failed on {len(failed)} chunks")

    es.indices.refresh(index=INDEX_NAME)
    count = es.count(index=INDEX_NAME)["count"]
    print(f"Index now contains {count} documents")


if __name__ == "__main__":
    main()