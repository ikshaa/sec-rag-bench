"""
BM25 keyword retrieval over the Elasticsearch index built by index_bm25.py.
Returns the same shape as retrieve.py so eval code can swap retrievers.
"""

import os
from dotenv import load_dotenv
from elasticsearch import Elasticsearch

load_dotenv()

INDEX_NAME = "sec_chunks"
ES_HOST = os.getenv("ELASTICSEARCH_HOST", "localhost")
ES_PORT = os.getenv("ELASTICSEARCH_PORT", "9200")
ES_URL = f"http://{ES_HOST}:{ES_PORT}"

_es = None


def _client() -> Elasticsearch:
    global _es
    if _es is None:
        _es = Elasticsearch(ES_URL)
    return _es


def retrieve_bm25(query: str, k: int = 5) -> list[dict]:
    """Return the top-k chunks ranked by BM25 against the query."""
    es = _client()
    response = es.search(
        index=INDEX_NAME,
        query={"match": {"text": query}},
        size=k,
    )
    results = []
    for hit in response["hits"]["hits"]:
        source = hit["_source"]
        results.append({
            "chunk_id": int(hit["_id"]),
            "text": source["text"],
            "company": source["company"],
            "fiscal_year": source["fiscal_year"],
            "score": hit["_score"],
        })
    return results


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "What were Tesla's total revenues in 2023?"
    print(f"Query: {q}\n")
    for i, r in enumerate(retrieve_bm25(q, k=5), 1):
        print(f"[{i}] score={r['score']:.3f}  {r['company']} FY{r['fiscal_year']}  (chunk_id={r['chunk_id']})")
        print(f"    {r['text'][:200]}...\n")