"""
Metrics for evaluating the SEC-RAG-Bench RAG system.

Computes:
  - Recall@K and Precision@K (retrieval metrics)
  - Citation accuracy (grounded generation metric)
  - RAGAS faithfulness (did the model hallucinate?)
  - RAGAS answer relevance (did the answer address the question?)
  - Refusal accuracy (for unanswerable questions)
"""
import re
from dataclasses import dataclass
from typing import Optional

from eval.benchmark import BenchmarkQuestion


# ---------------------------------------------------------------------------
# Helper: normalize text for matching
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Collapse whitespace and lowercase for lenient matching."""
    return re.sub(r"\s+", " ", text).strip().lower()


# ---------------------------------------------------------------------------
# Retrieval metrics
# ---------------------------------------------------------------------------

def snippet_in_chunk(snippet: str, chunk_text: str, min_overlap_chars: int = 50) -> bool:
    """
    Check if a source snippet is (approximately) contained in a chunk.

    Uses normalized substring matching with a minimum overlap requirement
    to be robust against chunk boundary cuts and whitespace variations.
    """
    if not snippet or not chunk_text:
        return False

    norm_snippet = normalize(snippet)
    norm_chunk = normalize(chunk_text)

    # Try the whole snippet first
    if norm_snippet in norm_chunk:
        return True

    # If snippet is longer than typical chunk, try matching the first portion
    if len(norm_snippet) > min_overlap_chars:
        prefix = norm_snippet[:min_overlap_chars]
        if prefix in norm_chunk:
            return True

    # Try the last portion too (in case chunk starts partway through snippet)
    if len(norm_snippet) > min_overlap_chars:
        suffix = norm_snippet[-min_overlap_chars:]
        if suffix in norm_chunk:
            return True

    return False


def recall_at_k(retrieved_chunks: list[dict], source_snippet: str, k: int = 5) -> float:
    """
    Did any of the top-K retrieved chunks contain the source snippet?
    Returns 1.0 (hit) or 0.0 (miss).

    retrieved_chunks is the list of dicts returned by retrieve().
    """
    if source_snippet is None:
        return float("nan")  # Not applicable (unanswerable question)

    top_k = retrieved_chunks[:k]
    for chunk in top_k:
        if snippet_in_chunk(source_snippet, chunk["text"]):
            return 1.0
    return 0.0


def precision_at_k(retrieved_chunks: list[dict], source_snippet: str, k: int = 5) -> float:
    """
    What fraction of the top-K retrieved chunks are relevant (contain the snippet)?
    """
    if source_snippet is None:
        return float("nan")

    top_k = retrieved_chunks[:k]
    if not top_k:
        return 0.0

    relevant = sum(1 for c in top_k if snippet_in_chunk(source_snippet, c["text"]))
    return relevant / len(top_k)


# ---------------------------------------------------------------------------
# Citation accuracy
# ---------------------------------------------------------------------------

def citation_accuracy(
    generated_answer: str,
    retrieved_chunks: list[dict],
    source_snippet: str,
) -> float:
    """
    When the model cited a source like [1], did it cite the chunk that contains
    the ground-truth snippet?

    Returns 1.0 if at least one correct citation, 0.0 if no citations or wrong
    citations, NaN if source_snippet is None.
    """
    if source_snippet is None:
        return float("nan")

    # Extract citation indices from the generated answer, e.g. [1], [2]
    citations = [int(m) for m in re.findall(r"\[(\d+)\]", generated_answer)]
    if not citations:
        return 0.0  # No citations attempted

    # Find which chunk indices contain the ground truth
    truth_chunk_indices = set()
    for i, chunk in enumerate(retrieved_chunks, start=1):  # 1-indexed to match prompt
        if snippet_in_chunk(source_snippet, chunk["text"]):
            truth_chunk_indices.add(i)

    if not truth_chunk_indices:
        return 0.0  # Ground truth isn't in retrieved context at all

    # Did at least one citation point to a correct chunk?
    cited_correctly = any(c in truth_chunk_indices for c in citations)
    return 1.0 if cited_correctly else 0.0


# ---------------------------------------------------------------------------
# Refusal accuracy (unanswerable questions)
# ---------------------------------------------------------------------------

REFUSAL_PHRASES = [
    "don't have enough information",
    "do not have enough information",
    "cannot answer",
    "can't answer",
    "not available in the provided context",
    "not disclosed",
    "insufficient information",
    "no information",
]


def refusal_accuracy(generated_answer: str) -> float:
    """
    For unanswerable questions, did the system correctly refuse?
    Returns 1.0 if answer contains a refusal phrase, 0.0 otherwise.
    """
    norm = normalize(generated_answer)
    return 1.0 if any(phrase in norm for phrase in REFUSAL_PHRASES) else 0.0


# ---------------------------------------------------------------------------
# RAGAS wrapper (faithfulness + answer relevance)
# ---------------------------------------------------------------------------

def ragas_scores(
    question: str,
    answer: str,
    contexts: list[str],
    reference: Optional[str] = None,
) -> dict:
    """
    Compute RAGAS faithfulness and answer relevancy for a single sample.

    Returns dict with keys: faithfulness, answer_relevancy.
    Returns NaN values if RAGAS fails on this sample.
    """
    try:
        from ragas import SingleTurnSample
        from ragas.metrics import Faithfulness, ResponseRelevancy
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from langchain_openai import ChatOpenAI, OpenAIEmbeddings
        import asyncio

        # Set up judge LLM and embeddings (RAGAS needs both)
        judge_llm = LangchainLLMWrapper(ChatOpenAI(model="gpt-4o-mini", temperature=0))
        judge_emb = LangchainEmbeddingsWrapper(OpenAIEmbeddings(model="text-embedding-3-small"))

        sample = SingleTurnSample(
            user_input=question,
            response=answer,
            retrieved_contexts=contexts,
            reference=reference or "",
        )

        faithfulness = Faithfulness(llm=judge_llm)
        relevancy = ResponseRelevancy(llm=judge_llm, embeddings=judge_emb)

        # RAGAS metrics are async
        loop = asyncio.new_event_loop()
        try:
            faith_score = loop.run_until_complete(faithfulness.single_turn_ascore(sample))
            rel_score = loop.run_until_complete(relevancy.single_turn_ascore(sample))
        finally:
            loop.close()

        return {"faithfulness": float(faith_score), "answer_relevancy": float(rel_score)}

    except Exception as e:
        print(f"  [RAGAS error: {type(e).__name__}: {e}]")
        return {"faithfulness": float("nan"), "answer_relevancy": float("nan")}


# ---------------------------------------------------------------------------
# Per-question result container
# ---------------------------------------------------------------------------

@dataclass
class QuestionResult:
    """Metrics for a single benchmark question."""
    question_id: str
    category: str
    answerable: bool

    # Retrieval metrics (NaN for unanswerable)
    recall_at_5: float
    precision_at_5: float

    # Generation metrics
    citation_accuracy: float  # NaN for unanswerable
    faithfulness: float  # NaN for unanswerable
    answer_relevancy: float
    refusal_accuracy: float  # NaN for answerable

    # Raw outputs for later inspection
    retrieved_company_year: list[str]
    generated_answer: str