"""
Generation step: take a query + retrieved chunks, ask Claude to answer.

Implements the "grounded with citations" prompt pattern. If the retrieved
context doesn't contain the answer, the model is instructed to say so
rather than hallucinate.
"""
import os

from dotenv import load_dotenv

from src.retrieve import retrieve
from src.llm_gateway import generate as gateway_generate

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GENERATION_MODEL = "claude-haiku-4-5"
MAX_TOKENS = 1024


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def build_prompt(query: str, chunks: list[dict]) -> str:
    """
    Build a prompt with the retrieved chunks as context.

    Each chunk is labeled with a citation index [1], [2], etc.
    so the model can refer to them in its answer.
    """
    context_parts = []
    for i, chunk in enumerate(chunks, start=1):
        context_parts.append(
            f"[{i}] Source: {chunk['company']} {chunk['fiscal_year']} 10-K\n"
            f"{chunk['text']}"
        )
    context = "\n\n---\n\n".join(context_parts)

    prompt = f"""You are answering a question about SEC 10-K filings.

Use ONLY the context below to answer. If the context does not contain
enough information to answer, say "I don't have enough information in
the provided context to answer this question."

When you cite information, use the source numbers like [1], [2], etc.

Context:
{context}

Question: {query}

Answer:"""

    return prompt


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

def answer_question(query: str, top_k: int = 5, retriever=None) -> dict:
    """
    End-to-end: retrieve relevant chunks, ask Claude, return answer + sources.

    Pass retriever=retrieve_bm25 (or any function with the same signature)
    to swap in a different retrieval backend. Defaults to dense vector.

    Returns a dict with:
        answer: the model's response text
        sources: list of retrieved chunks (for citation display)
        model: the model used
    """
    if retriever is None:
        retriever = retrieve
    chunks = retriever(query, top_k)

    if not chunks:
        return {
            "answer": "No relevant context found.",
            "sources": [],
            "model": GENERATION_MODEL,
        }

    prompt = build_prompt(query, chunks)

    gateway_response = gateway_generate(prompt)

    return {
        "answer": gateway_response.text,
        "sources": chunks,
        "model": gateway_response.model,
        "provider": gateway_response.provider,
        "fallback_used": gateway_response.fallback_used,
    }


if __name__ == "__main__":
    result = answer_question(
        "What were Apple's main risk factors in 2023?",
        top_k=3,
    )
    print("ANSWER:")
    print(result["answer"])
    print("\nSOURCES:")
    for i, s in enumerate(result["sources"], start=1):
        print(f"  [{i}] {s['company']} {s['fiscal_year']} (distance={s['distance']:.4f})")