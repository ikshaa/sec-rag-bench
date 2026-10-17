# SEC-RAG-Bench: Interview Talking Points

Quotable insights from building this project, organized by the
interview question they answer. First person, specific numbers,
honest about limits.

---

## "Tell me about this project"

I built an evaluation-driven RAG platform over SEC 10-K filings.
Instead of just shipping another chatbot, I started by building a
100-question benchmark across six categories: factual, numerical,
multi-hop, negation, comparison, and unanswerable. That let me
measure every retrieval and generation decision against real numbers
rather than vibes.

My baseline dense retriever hit 68% Recall@5. I then tested BM25
alone, hybrid retrieval via Reciprocal Rank Fusion, and two
different cross-encoder rerankers. Hybrid won: 76% Recall@5 with
100% recall on negation questions. The rerankers underperformed
hybrid, which was a surprising finding worth its own story. Every
architecture decision is backed by a measurement.

---

## "When did you choose NOT to adopt a popular technique?"

Cross-encoder reranking. Reranking is standard practice in production
RAG, so I expected it to be my precision lift for Week 2. I tested
two different rerankers: ms-marco-MiniLM-L-6-v2 and BAAI/bge-reranker-base.
Both underperformed hybrid retrieval alone on Recall@5 (74% and 75%
vs hybrid's 76%).

The structural reason: reranking in a top-20 to top-5 funnel
sacrifices recall for precision. For multi-hop questions that need
two chunks from different filings, the reranker promotes the single
most-relevant chunk and demotes the "bridge" chunk past the top-5
cutoff. The precision gain was 0.5 points. The recall loss was 1
to 2 points. Not worth it.

The lesson I'd share with any team: "industry standard" is not
evidence. If I'd shipped reranking because it's the default
recommendation, my system would have been worse than hybrid alone,
and I wouldn't have known.

---

## "Show me a trade-off decision backed by data"

I benchmarked three retrievers: dense vectors, BM25, and hybrid via
Reciprocal Rank Fusion. BM25 alone barely moved overall Recall@5
over vector (69% vs 68%), which could look like a null result if
you only read the headline. But the per-category breakdown showed
each retriever winning different categories by 7 to 14 points:
BM25 crushed negation and numerical, vector won multi-hop and
comparison. The complementary pattern made hybrid the right call.

The payoff: hybrid lifted Recall@5 from 68% to 76%, and negation
hit 100% because both retrievers rank the same chunk highly for
keyword-heavy questions. The lesson is that aggregate metrics hide
architectural trade-offs. If I'd stopped at "BM25 doesn't help",
I'd have missed the hybrid win entirely.

---

## "What problem did measurement reveal that you didn't expect?"

Multi-hop and comparison questions sat at exactly 50% Recall@5
across vector, BM25, and hybrid retrievers. Not within margin of
error, identical. That told me the ceiling on these categories isn't
a retrieval-quality problem, it's an architectural one. Single-shot
retrieval cannot combine information from two different filings when
the second one isn't semantically adjacent to the question. No
amount of better embeddings or better fusion fixes that. The next
move is query decomposition: break the question into sub-questions,
retrieve for each, then merge the contexts.

---

## "Why did you benchmark BM25 and vector separately before combining?"

Because I wanted to understand each retriever's failure modes before
assuming hybrid would win. The numbers made the case:

- BM25 beat vector by 14 points on negation questions and 6 points
  on numerical questions, because exact token matching matters when
  the question hinges on a specific number or the word "not".
- Vector beat BM25 by 7 to 12 points on multi-hop and comparison
  questions, because those need semantic bridging between different
  phrasings of the same concept.

That told me hybrid isn't just a nice-to-have, it's complementary.
Each retriever covers the other's weakness.

---

## "What's the most surprising thing you learned?"

BM25 got 100% refusal accuracy on unanswerable questions, versus 93%
for vector. The reason is counterintuitive: when the keywords don't
match, BM25 returns weak, obviously irrelevant chunks and the LLM
correctly says "I don't have enough information." Vector always
returns something that looks semantically close, which occasionally
tempts the model to fabricate.

The lesson is that dense retrievers are harder to make honest when
the answer isn't in the corpus. For production systems where
hallucination is the biggest risk, this matters a lot.

---

## "How did you design the benchmark?"

Ground truth by construction. Every question is anchored to a
specific passage in a real 10-K, with the source company, fiscal
year, and exact snippet recorded. I enforced a paraphrase rule so
the question wording doesn't trivially overlap with the chunk
wording, otherwise retrieval looks better than it is.

Six categories chosen to stress different failure modes: factual
for the easy case, numerical to test exact matching, multi-hop and
comparison to test semantic bridging across filings, negation to
test precision, and unanswerable to test refusal behavior.

100 questions is the sweet spot: enough for category-level
breakdowns with meaningful signal, small enough to iterate quickly.

---

## "Walk me through your retrieval evaluation metrics"

Four metrics per question:

- Recall@5: did the correct source chunk appear in the top 5?
- Precision@5: what fraction of the top 5 were relevant?
- Citation accuracy: did the generated answer cite the right source?
- Faithfulness and answer relevancy via RAGAS, which uses an LLM
  judge to score whether the answer is grounded in the retrieved
  context and actually addresses the question.

For unanswerable questions, I measure refusal accuracy separately,
because retrieval metrics don't apply when there's no correct source.

---

## "Explain Reciprocal Rank Fusion in simple terms"

RRF combines rankings from multiple retrievers without needing to
normalize their scores. For each chunk, you look at its rank in
each retriever's output and compute 1 divided by (60 plus that
rank). You sum those contributions across retrievers. Chunks that
rank high in either list get a boost; chunks that rank high in
both float to the very top. The constant 60 is from the original
paper and works well out of the box.

What I like about RRF: no training, no hyperparameter search, no
score normalization between a cosine distance and a BM25 score.
Just ranks. And it worked: Recall@5 jumped from 68% to 76% with no
machine learning involved.

---

## "What would you do differently?"

Three things:

1. I'd start with multi-step retrieval earlier. A single-shot
   retriever has a hard ceiling on multi-hop questions no matter
   how good your embeddings are.
2. I'd add a chunking experiment before locking in fixed-size 500.
   Semantic chunking or parent-document retrieval might lift
   precision without touching the retriever.
3. I'd invest more upfront in question diversity. My comparison
   category only has 8 questions, which gives noisy per-category
   numbers.

---

## "How do you think about faithfulness vs relevancy?"

They measure different things. Faithfulness asks "is every claim in
the answer supported by the retrieved context?" Relevancy asks "does
the answer actually address what was asked?"

My baseline hit 85% faithfulness but only 60% relevancy. That told
me the model wasn't hallucinating much, it was answering off-target.
That's a retrieval problem, not a generation problem. After hybrid
retrieval, relevancy jumped to 69% because the model had better
context to work with.

---

## "How would you take this to production?"

Three concerns I'd address beyond what's here:

1. **Latency**: cosine similarity over 10K chunks is fine, but at a
   million chunks you need an approximate index like HNSW.
2. **Freshness**: SEC filings arrive quarterly. The ingestion
   pipeline needs to be scheduled, idempotent, and able to handle
   amended filings without duplicating chunks.
3. **Observability**: every query needs a trace with retrieval
   latency, which chunks came back, the generated answer, and
   downstream feedback.

---

## Numbers to memorize

- Baseline Recall@5: 68%
- Hybrid Recall@5: 76% (+8 points, the Week 2 headline)
- Baseline Faithfulness: 85%
- Hybrid negation recall: 100%
- BM25 refusal accuracy: 100% vs Vector 93%
- Multi-hop recall: 50% across every retriever tested (the ceiling)
- Reranker configurations tested: ms-marco and BGE, both underperformed hybrid
- Benchmark size: 100 questions, 6 categories, 8 companies, 10,527 chunks
