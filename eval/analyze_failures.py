"""
Pull failed questions from the hybrid baseline results and classify them.

For each question, we report:
    - category
    - the question text
    - what the correct source was (company + year + snippet)
    - what we actually retrieved
    - what the model generated
    - a guess at why it failed

Writes:
    docs/failure_analysis_raw.md with the full failure list
    plus prints a summary to stdout
"""

import json
from collections import Counter, defaultdict
from pathlib import Path

from eval.benchmark import load_benchmark


RESULTS_PATH = Path("results/hybrid_v1.json")
OUTPUT_PATH = Path("docs/failure_analysis_raw.md")


def classify_failure(q, result) -> str:
    """Make a best guess at why this question failed."""
    recall = result.get("recall_at_5")
    citation = result.get("citation_accuracy")
    faith = result.get("faithfulness")
    relevancy = result.get("answer_relevancy")

    # Unanswerable gets its own bucket
    if q.category == "unanswerable":
        if result.get("refusal_accuracy") == 0:
            return "FABRICATED (should have refused but answered)"
        return "CORRECT REFUSAL"

    if recall == 0:
        return "RETRIEVAL MISS (correct chunk not in top-5)"
    if recall == 1 and citation == 0:
        return "RETRIEVED BUT NOT CITED (right chunk pulled, model cited wrong source)"
    if recall == 1 and (faith is not None and faith < 0.5):
        return "LOW FAITHFULNESS (answer not grounded in retrieved chunks)"
    if recall == 1 and (relevancy is not None and relevancy < 0.4):
        return "LOW RELEVANCY (answer off-topic even with right chunk)"
    return "PARTIAL SUCCESS (retrieved but weak answer)"


def main():
    questions_by_id = {q.id: q for q in load_benchmark()}
    data = json.loads(RESULTS_PATH.read_text())
    per_question = data["per_question"]

    failures = []
    for result in per_question:
        qid = result["question_id"]
        q = questions_by_id.get(qid)
        if q is None:
            continue

        # Only treat as "failure" if retrieval or something materially broke
        recall = result.get("recall_at_5")
        refusal = result.get("refusal_accuracy")

        is_failure = False
        if q.category == "unanswerable":
            if refusal == 0:
                is_failure = True
        else:
            if recall == 0 or (recall == 1 and result.get("citation_accuracy") == 0):
                is_failure = True

        if is_failure:
            classification = classify_failure(q, result)
            failures.append({
                "question_id": qid,
                "category": q.category,
                "question": q.question,
                "expected_company": q.source_company,
                "expected_year": q.source_year,
                "expected_snippet": q.source_snippet[:300] if q.source_snippet else None,
                "retrieved": result.get("retrieved_company_year", []),
                "generated_answer": result.get("generated_answer", "")[:500],
                "recall": recall,
                "citation": result.get("citation_accuracy"),
                "faithfulness": result.get("faithfulness"),
                "relevancy": result.get("answer_relevancy"),
                "classification": classification,
            })

    # Print summary to stdout
    print(f"Total questions: {len(per_question)}")
    print(f"Failures: {len(failures)}\n")

    by_class = Counter(f["classification"] for f in failures)
    print("Failures by classification:")
    for cls, n in by_class.most_common():
        print(f"  {n:3d}  {cls}")
    print()

    by_cat = defaultdict(list)
    for f in failures:
        by_cat[f["category"]].append(f)
    print("Failures by category:")
    for cat, lst in sorted(by_cat.items()):
        print(f"  {cat}: {len(lst)}")
    print()

    # Write detailed markdown
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Failure Analysis Raw Dump\n"]
    lines.append(f"Total questions: {len(per_question)}  |  Failures: {len(failures)}\n")
    lines.append("## Failures by classification\n")
    for cls, n in by_class.most_common():
        lines.append(f"- **{cls}**: {n}")
    lines.append("")
    lines.append("## Each failure\n")
    for f in failures:
        lines.append(f"### {f['question_id']} ({f['category']}) — {f['classification']}\n")
        lines.append(f"**Question**: {f['question']}\n")
        lines.append(f"**Expected source**: {f['expected_company']} FY{f['expected_year']}\n")
        if f["expected_snippet"]:
            lines.append(f"**Expected snippet**: {f['expected_snippet']}...\n")
        lines.append(f"**Retrieved** (company_year): {', '.join(f['retrieved'][:5])}\n")
        lines.append(f"**Metrics**: recall@5={f['recall']}, citation={f['citation']}, "
                     f"faithfulness={f['faithfulness']}, relevancy={f['relevancy']}\n")
        lines.append(f"**Model answer**:\n```\n{f['generated_answer']}\n```\n")
        lines.append("---\n")

    OUTPUT_PATH.write_text("\n".join(lines))
    print(f"Wrote detailed dump to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()