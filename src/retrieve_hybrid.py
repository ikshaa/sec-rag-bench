"""
Hybrid retrieval via Reciprocal Rank Fusion (RRF).

Runs both the dense vector retriever and the BM25 retriever,
pulls a larger candidate pool from each (default 20), then fuses
their rankings. Each chunk gets a score of:

    sum over retrievers of 1 / (K_RRF + rank_in_that_retriever)

where K_RRF=60 is the constant from the original RRF paper
(Cormack, Clarke, Buettcher 2009). Chunks ranked high in either
list bubble up; chunks ranked high in both float to the top.
No training required.

Returns the top-k by RRF score, in the same shape as the other
retrievers so eval code can swap it in.
"""

from src.retrieve import retrieve
from src.retrieve_bm25 import retrieve_bm25

K_RRF = 60
CANDIDATE_POOL = 20


def retrieve_hybrid(query: str, top_k: int = 5) -> list[dict]:
    """
    Fuse dense vector + BM25 rankings via Reciprocal Rank Fusion.

    Pulls CANDIDATE_POOL results from each retriever, scores each
    unique chunk by its RRF score, returns the top-k.
    """
    vector_hits = retrieve(query, CANDIDATE_POOL)
    bm25_hits = retrieve_bm25(query, CANDIDATE_POOL)

    # chunk_id -> {chunk data, rrf_score}
    scores: dict[int, dict] = {}

    for rank, hit in enumerate(vector_hits, start=1):
        cid = hit["chunk_id"]
        scores.setdefault(cid, {"chunk": hit, "rrf_score": 0.0})
        scores[cid]["rrf_score"] += 1.0 / (K_RRF + rank)

    for rank, hit in enumerate(bm25_hits, start=1):
        cid = hit["chunk_id"]
        # If chunk is already in scores from vector, keep that chunk payload
        # (both have the same fields we need, so either works).
        scores.setdefault(cid, {"chunk": hit, "rrf_score": 0.0})
        scores[cid]["rrf_score"] += 1.0 / (K_RRF + rank)

    # Sort by RRF score, descending, take top-k
    ranked = sorted(scores.values(), key=lambda x: x["rrf_score"], reverse=True)
    top = ranked[:top_k]

    results = []
    for item in top:
        chunk = item["chunk"]
        results.append({
            "chunk_id": chunk["chunk_id"],
            "text": chunk["text"],
            "company": chunk["company"],
            "fiscal_year": chunk["fiscal_year"],
            "rrf_score": item["rrf_score"],
        })
    return results


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "What were Tesla's total revenues in 2023?"
    print(f"Query: {q}\n")
    for i, r in enumerate(retrieve_hybrid(q, top_k=5), 1):
        print(f"[{i}] rrf={r['rrf_score']:.4f}  {r['company']} FY{r['fiscal_year']}  (chunk_id={r['chunk_id']})")
        print(f"    {r['text'][:180]}...\n")