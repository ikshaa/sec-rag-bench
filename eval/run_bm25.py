"""
Run the baseline RAG system against the full benchmark and save metrics.

Usage:
    python -m eval.run_baseline

Writes results/baseline_v1.json with per-question metrics and aggregates.
"""
import json
import math
import time
from pathlib import Path
from statistics import mean

from tqdm import tqdm

from eval.benchmark import load_benchmark
from eval.metrics import (
    QuestionResult,
    recall_at_k,
    precision_at_k,
    citation_accuracy,
    refusal_accuracy,
    ragas_scores,
)
from src.retrieve import retrieve
from src.retrieve_bm25 import retrieve_bm25
from src.generate import answer_question

RESULTS_PATH = Path("results/bm25_v1.json")
TOP_K = 5


def evaluate_question(q) -> QuestionResult:
    """Run one benchmark question end-to-end and compute all metrics."""
    answerable = q.category != "unanswerable"

    # Retrieve + generate (reuses existing pipeline)
    result = answer_question(q.question, top_k=TOP_K, retriever=retrieve_bm25)
    retrieved = result["sources"]
    generated_answer = result["answer"]

    # Retrieval metrics (NaN for unanswerable)
    if answerable:
        recall = recall_at_k(retrieved, q.source_snippet, k=TOP_K)
        precision = precision_at_k(retrieved, q.source_snippet, k=TOP_K)
        citation = citation_accuracy(generated_answer, retrieved, q.source_snippet)
    else:
        recall = float("nan")
        precision = float("nan")
        citation = float("nan")

    # Refusal accuracy (only for unanswerable)
    refusal = refusal_accuracy(generated_answer) if not answerable else float("nan")

    # RAGAS metrics — only for answerable
    if answerable:
        contexts = [c["text"] for c in retrieved]
        ragas = ragas_scores(
            question=q.question,
            answer=generated_answer,
            contexts=contexts,
            reference=q.answer,
        )
        faith = ragas["faithfulness"]
        relevancy = ragas["answer_relevancy"]
    else:
        faith = float("nan")
        relevancy = float("nan")

    return QuestionResult(
        question_id=q.id,
        category=q.category,
        answerable=answerable,
        recall_at_5=recall,
        precision_at_5=precision,
        citation_accuracy=citation,
        faithfulness=faith,
        answer_relevancy=relevancy,
        refusal_accuracy=refusal,
        retrieved_company_year=[f"{c['company']}_{c['fiscal_year']}" for c in retrieved],
        generated_answer=generated_answer,
    )


def aggregate(results: list[QuestionResult]) -> dict:
    """Compute mean metrics across all questions and per-category."""

    def nanmean(xs):
        clean = [x for x in xs if not math.isnan(x)]
        return mean(clean) if clean else float("nan")

    def summarize(subset):
        return {
            "n": len(subset),
            "recall_at_5": nanmean([r.recall_at_5 for r in subset]),
            "precision_at_5": nanmean([r.precision_at_5 for r in subset]),
            "citation_accuracy": nanmean([r.citation_accuracy for r in subset]),
            "faithfulness": nanmean([r.faithfulness for r in subset]),
            "answer_relevancy": nanmean([r.answer_relevancy for r in subset]),
            "refusal_accuracy": nanmean([r.refusal_accuracy for r in subset]),
        }

    overall = summarize(results)
    by_category = {}
    categories = {r.category for r in results}
    for cat in sorted(categories):
        subset = [r for r in results if r.category == cat]
        by_category[cat] = summarize(subset)

    return {"overall": overall, "by_category": by_category}


def main():
    questions = load_benchmark()
    print(f"Running baseline against {len(questions)} questions\n")

    results: list[QuestionResult] = []
    start_time = time.time()

    for q in tqdm(questions, desc="Evaluating"):
        try:
            r = evaluate_question(q)
            results.append(r)
        except Exception as e:
            tqdm.write(f"  [FAIL] {q.id}: {type(e).__name__}: {e}")

    elapsed = time.time() - start_time
    print(f"\nCompleted in {elapsed/60:.1f} minutes\n")

    # Aggregate
    summary = aggregate(results)

    # Save results
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "config": {
            "chunking": "fixed_500_overlap_50",
            "embedding_model": "text-embedding-3-small",
            "retrieval": "bm25_elasticsearch",
            "top_k": TOP_K,
            "generation_model": "claude-haiku-4-5",
        },
        "summary": summary,
        "per_question": [
            {
                "question_id": r.question_id,
                "category": r.category,
                "answerable": r.answerable,
                "recall_at_5": r.recall_at_5,
                "precision_at_5": r.precision_at_5,
                "citation_accuracy": r.citation_accuracy,
                "faithfulness": r.faithfulness,
                "answer_relevancy": r.answer_relevancy,
                "refusal_accuracy": r.refusal_accuracy,
                "retrieved_company_year": r.retrieved_company_year,
                "generated_answer": r.generated_answer,
            }
            for r in results
        ],
    }

    # Convert NaN to null for valid JSON
    def nan_to_null(obj):
        if isinstance(obj, float) and math.isnan(obj):
            return None
        if isinstance(obj, dict):
            return {k: nan_to_null(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [nan_to_null(x) for x in obj]
        return obj

    out = nan_to_null(out)
    RESULTS_PATH.write_text(json.dumps(out, indent=2))
    print(f"Saved results to {RESULTS_PATH}\n")

    # Print summary
    overall = summary["overall"]
    print("=== BASELINE SUMMARY ===")
    print(f"  Recall@5:         {overall['recall_at_5']:.2%}")
    print(f"  Precision@5:      {overall['precision_at_5']:.2%}")
    print(f"  Citation accuracy:{overall['citation_accuracy']:.2%}")
    print(f"  Faithfulness:     {overall['faithfulness']:.2%}")
    print(f"  Answer relevancy: {overall['answer_relevancy']:.2%}")
    print(f"  Refusal accuracy: {overall['refusal_accuracy']:.2%}")
    print()
    print("=== BY CATEGORY ===")
    for cat, s in summary["by_category"].items():
        print(f"\n  {cat} (n={s['n']}):")
        for k, v in s.items():
            if k == "n" or (isinstance(v, float) and math.isnan(v)):
                continue
            print(f"    {k}: {v:.2%}")


if __name__ == "__main__":
    main()