"""
Command-line interface for the SEC RAG system.

Usage:
    python -m src.cli "What were Apple's main risk factors?"
    python -m src.cli "What does Tesla say about battery cell supply?"
"""
import sys

from src.generate import answer_question


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m src.cli \"your question here\"")
        sys.exit(1)

    query = " ".join(sys.argv[1:])

    print(f"\nQuestion: {query}\n")
    print("Searching...\n")

    result = answer_question(query, top_k=5)

    print("=" * 70)
    print("ANSWER")
    print("=" * 70)
    print(result["answer"])
    print()
    print("=" * 70)
    print("SOURCES")
    print("=" * 70)
    for i, s in enumerate(result["sources"], start=1):
        print(f"[{i}] {s['company']} {s['fiscal_year']} (distance={s['distance']:.4f})")
        preview = s["text"][:150].replace("\n", " ")
        print(f"    {preview}...")
        print()


if __name__ == "__main__":
    main()