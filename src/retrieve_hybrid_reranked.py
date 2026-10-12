"""
Hybrid retrieval + cross-encoder reranking.

Pipeline:
    1. Hybrid RRF retrieves top-20 fused candidates from vector + BM25
    2. Cross-encoder reranks each (query, chunk) pair
    3. Return top-5 by rerank score

This is the "two-stage retrieval" pattern that most production RAG
systems settle on: fast recall-oriented retrieval first, then slow
precision-oriented reranking.
"""

from src.retrieve_hybrid import retrieve_hybrid
from src.rerank import rerank

CANDIDATE_POOL = 20


def retrieve_hybrid_reranked(query: str, top_k: int = 5) -> list[dict]:
    """Retrieve top-20 with hybrid, rerank with cross-encoder, keep top-k."""
    candidates = retrieve_hybrid(query, top_k=CANDIDATE_POOL)
    return rerank(query, candidates, top_k=top_k)


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "What were Tesla's total revenues in 2023?"
    print(f"Query: {q}\n")
    for i, r in enumerate(retrieve_hybrid_reranked(q, top_k=5), 1):
        print(f"[{i}] rerank={r['rerank_score']:.4f}  {r['company']} FY{r['fiscal_year']}  (chunk_id={r['chunk_id']})")
        print(f"    {r['text'][:180]}...\n")