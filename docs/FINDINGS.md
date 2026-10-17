# SEC-RAG-Bench: Findings Journal

Living log of experiments, numbers, and insights. Entries newest-first.
Each entry: what we measured, what we found, why it matters.

---

## 2026-10-12 · BGE Reranker (second reranker attempt)

**Setup**: Replaced ms-marco-MiniLM-L-6-v2 with BAAI/bge-reranker-base.
Same pipeline otherwise: hybrid retrieves top-20, reranker scores
each (query, chunk) pair, keep top-5.

**Headline**:
- Recall@5: 75.29% (-1.2 vs hybrid, +1.2 vs ms-marco)
- Precision@5: 28.71%
- Citation accuracy: 71.76%
- Faithfulness: 84.25% (recovered toward baseline)
- Answer relevancy: 64.05%

**By category (Recall@5)**:

| Category | Hybrid | ms-marco | BGE | Note |
|---|---|---|---|---|
| factual | 87.50% | 84.38% | 87.50% | BGE recovered |
| negation | 100% | 92.86% | 92.86% | Neither recovered |
| numerical | 70.59% | 76.47% | 76.47% | Both rerankers help |
| multi_hop | 50.00% | 50.00% | 42.86% | BGE regressed |
| comparison | 50.00% | 37.50% | 50.00% | BGE recovered |

### Insights

1. **BGE is better than ms-marco for this domain** (75.29% vs 74.12%),
   confirming the domain-mismatch hypothesis. ms-marco's training on
   web Q&A didn't transfer well to financial filings. BGE's broader
   training recovered the factual and comparison losses.

2. **But BGE still cannot beat hybrid overall** (75.29% vs 76.47%).
   Switching models didn't fix the structural problem. This elevates
   the finding from "we picked the wrong reranker" to "reranking
   itself trades recall for precision in a top-5 setting".

3. **The multi-hop regression is diagnostic.** When a question needs
   two chunks from different filings, reranker scores favor whichever
   chunk is most directly relevant to the question, pushing the
   "bridge" chunk out of the top-5. This is a reranking artifact, not
   a model bug.

4. **Precision gain is tiny** (~0.5-0.7pp across both rerankers).
   Real, but not worth the recall loss for a benchmark where
   recall is the primary success metric.

### Decision

**Hybrid without reranking is the champion.** Final Week 2
configuration. The reranker is kept in the codebase as a comparison
baseline but not shipped as the default.

### Why this matters more than if reranking had won

Shipping the "obvious" best practice without measurement is how
systems end up worse than they should be. We measured five
configurations: vector, BM25, hybrid, hybrid+ms-marco, hybrid+BGE.
Four of them look reasonable in isolation. Only the full comparison
shows that reranking in this setting underperforms hybrid alone.
That's the whole case for evaluation-driven development.

---

## 2026-10-12 · Cross-encoder Reranker (ms-marco)

**Setup**: Hybrid retrieves top-20 fused candidates, cross-encoder
`ms-marco-MiniLM-L-6-v2` scores each (query, chunk) pair, keep
top-5 by reranker score.

**Headline**:
- Recall@5: 74.12% (-2.4 vs hybrid)
- Precision@5: 28.94% (+0.7 vs hybrid)
- Faithfulness: 84.09% (recovered toward vector baseline)
- Answer relevancy: 65.38% (-4.1 vs hybrid)

**By category (Recall@5)**:
- factual: 84.38% (dropped from hybrid's 87.5%)
- negation: 92.86% (dropped from hybrid's 100%)
- numerical: 76.47% (gained from hybrid's 70.59%)
- multi_hop: 50.00% (unchanged)
- comparison: 37.50% (dropped from hybrid's 50%)

### Insights

1. **Reranker made overall numbers worse, not better.** This was
   unexpected and the finding is the point.

2. **Only numerical improved.** MS MARCO training includes a lot of
   numerical Q&A patterns, so the reranker is well-calibrated for
   that category. Everything else regressed or held.

3. **Comparison dropped 12.5 points.** For questions needing chunks
   from two filings, the reranker promotes one chunk to #1 and
   demotes the "bridge" chunk to #6+, pushing it past the top-5
   cutoff.

4. **Negation dropped 7 points.** The reranker treats "excludes X"
   and "includes X" as semantic neighbors, undoing hybrid's
   exact-match discipline from BM25.

5. **Faithfulness recovered (82 → 84%).** Fewer candidates in the
   context window means less opportunity for the model to fabricate.

### Hypothesis

MS MARCO was trained on web search Q&A, not financial text. The
domain mismatch is pushing the reranker to favor chunks that look
like web-answer prose over chunks that look like 10-K boilerplate,
even when the boilerplate contains the actual answer.

**Next experiment**: Try BAAI/bge-reranker-base, which was trained
on more diverse data. If domain mismatch is the issue, BGE should
recover the recall. If BGE still underperforms hybrid, the problem
is structural (reranking shrinks the pool and hurts recall).

---

## 2026-10-12 · Hybrid RRF (vector + BM25)

**Setup**: Reciprocal Rank Fusion over top-20 candidates from each
retriever, K_RRF=60, top-5 final chunks.

**Headline**:
- Recall@5: 76.47% (+8.2 vs vector, +7.1 vs BM25)
- Precision@5: 28.24%
- Citation accuracy: 75.29%
- Faithfulness: 81.82% (-3.0 vs vector)
- Answer relevancy: 69.47% (+9.1 vs vector)
- Refusal accuracy: 100.00%

**By category (Recall@5)**:
- factual: 87.50% (+9.4 vs vector)
- negation: 100.00% (+21.4 vs vector)
- numerical: 70.59% (+5.9 vs vector)
- multi_hop: 50.00% (unchanged)
- comparison: 50.00% (unchanged)

### Insights

1. **Hybrid delivered the predicted lift.** The per-category wins
   from BM25 and vector stacked instead of canceling. Factual
   jumped 9 points even though both retrievers tied individually,
   because RRF rewards chunks both retrievers agree on.

2. **Negation hit 100%.** This is the strongest signal in the
   whole experiment: when exact tokens and semantic context both
   matter, RRF nails it. BM25 was already at 93%, and the vector
   retriever filled the last 7%.

3. **Multi-hop and comparison stayed at exactly 50%.** This is an
   architectural ceiling. Both categories need information from
   two filings in one answer. Single-shot retrieval, no matter
   how good, cannot bridge filings that aren't semantically
   adjacent to the question. The fix is query decomposition, not
   better retrieval math.

4. **Faithfulness dropped 3 points.** More diverse candidates means
   the model occasionally paraphrases one chunk while citing
   another. Still high overall (82%), but worth watching when we
   add reranking.

5. **Precision@5 moved less than Recall@5.** We're pulling the
   right chunks into the top 5 but they're surrounded by
   near-misses. Reranking is the next lever.

### Implication

Hybrid search solves exact-match categories (factual, negation,
numerical). It does NOT solve bridging categories (multi-hop,
comparison). Those need query decomposition, which is a Week 3+
investment.

---

## 2026-10-12 · BM25 vs Dense Vector Baseline

**Setup**: Same 100-question benchmark, same chunks, same generation
model (Claude Haiku 4.5), top-k=5. Only the retriever changed.

**Headline comparison**:

| Metric            | Vector  | BM25    | Delta |
|-------------------|---------|---------|-------|
| Recall@5          | 68.24%  | 69.41%  | +1.2  |
| Precision@5       | 23.76%  | 26.35%  | +2.6  |
| Citation accuracy | 68.24%  | 68.24%  | tie   |
| Faithfulness      | 84.79%  | 84.54%  | tie   |
| Answer relevancy  | 60.35%  | 57.08%  | -3.3  |
| Refusal accuracy  | 93.33%  | 100.00% | +6.7  |

Overall numbers are nearly identical. The real story is per-category.

**Recall@5 by category**:

| Category       | Vector | BM25   | Winner             |
|----------------|--------|--------|--------------------|
| factual        | 78.12% | 78.12% | tie                |
| negation       | 78.57% | 92.86% | BM25 (+14.3)       |
| numerical      | 64.71% | 70.59% | BM25 (+5.9)        |
| multi_hop      | 50.00% | 42.86% | Vector (+7.1)      |
| comparison     | 50.00% | 37.50% | Vector (+12.5)     |
| unanswerable   | 93.33% | 100%   | BM25 refusal (+6.7)|

### Insights

1. **BM25 wins negation and numerical because exact tokens matter.**
   Dollar amounts, line-item names, and words like "not", "excludes",
   "other than" need exact matches.

2. **Vector wins multi-hop and comparison because semantic bridging
   matters.** A question about change year-over-year needs the
   retriever to understand two years are both relevant.

3. **BM25 refuses correctly 100% of the time on unanswerable
   questions.** When nothing matches the keywords, BM25 returns
   weak irrelevant chunks and the LLM correctly says "I don't know".

4. **Answer relevancy dropped slightly for BM25 (-3.3 pp).**
   Keyword-aligned chunks are less semantically complete.

### Implication

Neither retriever dominates. The complementary category wins are
the empirical justification for hybrid.

---

## 2026-10-11 · Dense Vector Baseline

**Setup**: text-embedding-3-small (1536-dim), cosine similarity over
pgvector, fixed-size chunks of 500 chars with 50-char overlap, top-k=5.

**Overall**:
- Recall@5: 68.24%
- Precision@5: 23.76%
- Citation accuracy: 68.24%
- Faithfulness: 84.79%
- Answer relevancy: 60.35%
- Refusal accuracy: 93.33%

**By category (Recall@5)**:
- factual: 78.12% (n=32)
- negation: 78.57% (n=14)
- numerical: 64.71% (n=17)
- multi_hop: 50.00% (n=14)
- comparison: 50.00% (n=8)
- unanswerable: 93.33% refusal (n=15)

### Insights

1. **Factual is the easy case.** Answer in one chunk, question uses
   similar wording, cosine similarity nails it.
2. **Multi-hop and comparison at 50% confirm the architectural
   ceiling of single-shot retrieval.**
3. **High faithfulness (85%) with modest relevancy (60%) means the
   model grounds correctly but sometimes answers off-target.**
4. **Precision@5 at 24% is expected for broad financial text.**

### Baseline role

This is the floor every subsequent experiment must beat.
