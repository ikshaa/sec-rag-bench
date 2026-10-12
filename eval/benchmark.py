"""
Loader and validator for the SEC-RAG-Bench benchmark dataset.

Each question is stored as a JSON object per line in a .jsonl file.
This module provides a Pydantic model for schema enforcement and
a load function that returns validated question objects.
"""
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, field_validator

BENCHMARK_PATH = Path("data/benchmark/benchmark_v1.jsonl")

Category = Literal[
    "factual", "multi_hop", "numerical",
    "negation", "comparison", "unanswerable"
]


class BenchmarkQuestion(BaseModel):
    """
    A single benchmark question.

    - source_company and source_year are None for unanswerable questions.
    - source_year can be an integer or "multiple" for multi-hop / comparison.
    - source_snippet is the exact ground-truth passage (None for unanswerable).
    """
    id: str = Field(..., pattern=r"^q_\d{3}$")
    category: Category
    question: str
    answer: str
    source_company: str | None = None
    source_year: int | str | None = None
    source_snippet: str | None = None

    @field_validator("source_year")
    @classmethod
    def validate_source_year(cls, v):
        if v is None or v == "multiple":
            return v
        if isinstance(v, int) and 2020 <= v <= 2025:
            return v
        raise ValueError(f"source_year must be int in range 2020-2025, 'multiple', or None; got {v!r}")


def load_benchmark(path: Path = BENCHMARK_PATH) -> list[BenchmarkQuestion]:
    """
    Load the benchmark from a JSONL file. Validates each entry via Pydantic.
    Raises if any entry fails schema validation.
    """
    if not path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {path}")

    questions = []
    with path.open("r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                questions.append(BenchmarkQuestion(**data))
            except Exception as e:
                raise ValueError(
                    f"Error at line {line_num} of {path}:\n  {line}\n  {type(e).__name__}: {e}"
                )

    return questions


def summarize_benchmark(questions: list[BenchmarkQuestion]) -> dict:
    """
    Return counts by category and by company for quick sanity checks.
    """
    by_category = {}
    by_company = {}
    for q in questions:
        by_category[q.category] = by_category.get(q.category, 0) + 1
        if q.source_company:
            by_company[q.source_company] = by_company.get(q.source_company, 0) + 1
    return {
        "total": len(questions),
        "by_category": by_category,
        "by_company": by_company,
    }


if __name__ == "__main__":
    questions = load_benchmark()
    summary = summarize_benchmark(questions)
    print(f"Loaded {summary['total']} questions")
    print("\nBy category:")
    for cat, count in sorted(summary["by_category"].items()):
        print(f"  {cat:15s} {count}")
    print("\nBy company (excluding unanswerable):")
    for company, count in sorted(summary["by_company"].items()):
        print(f"  {company:12s} {count}")