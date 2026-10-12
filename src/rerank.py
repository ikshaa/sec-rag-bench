"""
Cross-encoder reranking for retrieval candidates.

Uses ms-marco-MiniLM-L-6-v2, trained specifically for passage
relevance ranking. Much slower per-pair than bi-encoders (full
transformer forward pass per candidate instead of a dot product)
but dramatically more accurate.

Standard two-stage retrieval pattern: retrieve many candidates
with a fast method (hybrid), then rerank with cross-encoder to
pick the best few.
"""

from sentence_transformers import CrossEncoder

MODEL_NAME = "BAAI/bge-reranker-base"

_model = None


def _get_model() -> CrossEncoder:
    """Lazy-load the model so imports stay cheap."""
    global _model
    if _model is None:
        _model = CrossEncoder(MODEL_NAME)
    return _model


def rerank(query: str, candidates: list[dict], top_k: int = 5) -> list[dict]:
    """
    Rerank candidate chunks by cross-encoder relevance score.

    Each candidate must have a 'text' field. Adds 'rerank_score' to
    each candidate dict and returns the top-k, sorted descending by
    rerank score.
    """
    if not candidates:
        return []

    model = _get_model()
    pairs = [(query, c["text"]) for c in candidates]
    scores = model.predict(pairs)

    for c, s in zip(candidates, scores):
        c["rerank_score"] = float(s)

    reranked = sorted(candidates, key=lambda x: x["rerank_score"], reverse=True)
    return reranked[:top_k]