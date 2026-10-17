# SEC-RAG-Bench: Failure Analysis

Deep dive into the 21 questions where hybrid retrieval scored
`recall@5 = 0` or `citation_accuracy = 0`. What the raw numbers
missed: about half of these are not failures at all. The real
failure rate is ~11%.

---

## Headline finding

**The benchmark's ground truth is too strict.** It credits recall
only when the exact labeled source chunk appears in the top-5. In
practice, SEC filings publish the same information in multiple
places (a 10-K often restates the prior year's figures in a
comparative column, and some facts like a company's HQ address are
identical across years). The model frequently answered correctly
using a legitimate alternative source and still scored 0.

Of 21 "failures":
- **10 are correct answers** scored as wrong because they came from
  a different legitimate source than the one I labeled
- **11 are real failures** where the model either refused or
  produced incomplete answers

**True failure rate: ~11%, not 21%.**

The methodology flaw is a finding, not a bug in the retriever. The
next benchmark iteration should accept multiple valid sources per
question and compute recall as "did ANY valid source make the
top-5", not "did THIS source make the top-5".

---

## Apparent-but-not-really failures (10 cases)

The model got the right answer from a different source. The
benchmark gave zero recall; the end user would be satisfied.

| ID | Question (short) | Expected source | Actually used | Was answer correct? |
|---|---|---|---|---|
| q_001 | Apple HQ address | apple 2023 | apple 2024 | **Yes** (same address) |
| q_009 | Tesla 2023 gross profit | tesla 2023 | tesla 2024 (comparative year) | **Yes** ($17,660M) |
| q_031 | Tesla auto sales change 2023→2024 | tesla multi-year | tesla 2024 (restates 2023) | **Yes** ($6.03B decline) |
| q_046 | Nvidia commercial paper | nvidia 2024 (specific line) | nvidia 2024 (different chunk) | **Yes** ($575M program) |
| q_049 | Nvidia workforce gender change | nvidia multi-year | nvidia 2024 (shows prior yr) | **Yes** (80%→79% male) |
| q_056 | Apple product growth/decline FY24 | apple 2024 | apple 2024 (different chunk) | **Yes** (Services up, W/H/A down) |
| q_057 | Apple EU recovery amount | apple 2023 | apple 2023 (different chunk) | **Yes** (€13.1B + €1.2B) |
| q_078 | Google trademark risk | google 2024 | google 2023 (same risk text) | **Yes** ("synonymous with search") |
| q_081 | YouTube ads growth 2022→2024 | google multi-year | google 2024 (has history) | **Yes** ($6.9B growth) |
| q_095 | Costco Executive cashback form | costco 2023 | costco 2024 (same policy) | **Yes** (reward certificates) |

Pattern: **comparative-year data in a newer filing is a legitimate
source for the prior year's facts.** My benchmark did not account
for this.

---

## Real failures (11 cases)

The model actually got it wrong or refused when the answer was
retrievable. These are what retrieval improvements should target.

### Pattern 1: Multi-filing / multi-company questions (4 cases)

Questions that require stitching information from two different
10-K filings in one answer. The single-shot retriever can bring
chunks from both companies in principle (hybrid did pull mixed
results in some cases), but the top-5 cutoff often holds only
chunks from one of the two filings.

| ID | Question | What went wrong |
|---|---|---|
| q_003 | Tesla indebtedness change 2023→2024 | Got the 2024 figure ($7.91B) but not 2023 ($4.68B) |
| q_055 | Nvidia vs Apple FY2024 revenue | Pulled 4 Nvidia chunks + 1 Apple, missed total revenue line for both |
| q_087 | Microsoft vs Netflix FY2024 EPS | Got Netflix 3-year EPS, Microsoft chunk had no EPS data |
| q_099 | Google YouTube vs Netflix streaming | All 5 chunks were Google, Netflix revenue missing entirely |

**Root cause**: single-shot retrieval cannot guarantee coverage of
both filings in top-5. **Fix**: query decomposition. Split the
question into "What was Nvidia's FY2024 revenue?" and "What was
Apple's FY2024 revenue?", retrieve for each sub-question, then merge
the contexts before generation.

### Pattern 2: Table-split chunking (4 cases)

Financial tables longer than 500 characters got split across
chunks. The chunk containing one row of the table is separate from
the chunk containing another, so retrieval might pull the first
half when the question needs the second.

| ID | Question | What went wrong |
|---|---|---|
| q_002 | Tesla long-term debt EOY 2023 | Debt section was in a chunk BM25 scored below top-5 |
| q_042 | Nvidia 5-year shareholder return | Numeric table split across chunks |
| q_043 | Nvidia revenue growth % + gross margin change | Growth-rate table landed in a chunk retriever missed |
| q_044 | Nvidia cost structure as % of revenue | Percentage-of-revenue table split |

**Root cause**: fixed-size 500-character chunking doesn't respect
semantic boundaries like table ends.
**Fix**: semantic chunking (split on markdown table boundaries or
paragraph ends), or parent-document retrieval (index small chunks
for retrieval precision, return the full containing section at
generation time).

### Pattern 3: Specific-phrase retrieval misses (3 cases)

The answer exists in a single chunk but uses specific marketing or
legal language the retriever's semantic/keyword blend didn't rank
highly.

| ID | Question | What went wrong |
|---|---|---|
| q_039 | Nvidia competitors in both GPU AND networking | Competitor list was in a chunk retriever ranked low |
| q_065 | Microsoft product "at forefront of AI software development" | GitHub Copilot described in a chunk retriever missed |
| q_088 | Netflix segment count | "one operating segment" phrase in different chunk than retrieved |

**Root cause**: the semantic retriever matched on topic
(competitors, AI, segments) but the specific phrasing of the
answer was in a sibling chunk the retriever down-ranked.
**Fix**: query rewriting (an LLM rewrites the question into
alternative phrasings before retrieval), or increase candidate pool
from 20 to 50 before reranking.

---

## Where to invest next, ranked by expected lift

1. **Fix the benchmark methodology** (easy, 1-2 hours). Add an
   `alternative_sources` field to each question. Re-compute recall
   to credit any valid source. Expected: real Recall@5 jumps from
   76% to ~85%+ without changing the retriever at all.

2. **Semantic chunking** (medium, half a day). Split on structural
   boundaries like paragraphs and tables instead of character
   count. Expected lift on q_002, q_042, q_043, q_044.

3. **Query decomposition for multi-hop/comparison** (medium, 1 day).
   LLM-rewrite questions into sub-questions, retrieve for each,
   merge contexts. Expected lift on q_003, q_055, q_087, q_099 and
   the broader multi_hop/comparison categories (currently stuck at
   50% recall across all retrievers).

4. **Query rewriting for specific-phrase retrieval** (medium, half
   a day). LLM rewrites the user's question into 3-5 alternative
   phrasings, retrieves top-10 for each, fuses with RRF. Expected
   lift on q_039, q_065, q_088.

5. **Larger candidate pool before rerank** (easy, 30 min, previously
   tested as not helpful but worth revisiting with semantic
   chunking in place).

---

## Interview talking points this failure analysis produced

### "Tell me about a time you discovered a problem with your own methodology"

> "When I did failure analysis on my 21 benchmark failures, I
> noticed about half of them were cases where the model actually
> got the right answer, just from a different source than the one
> I labeled. My ground truth was overly strict: SEC filings
> publish the same information in multiple places, and I only
> credited one. The real failure rate was closer to 11%, not 21%.
> This is a methodology finding I would never have caught without
> actually reading the failure cases one by one. Automated metrics
> flagged them as wrong; the human read-through said otherwise."

### "What's the most common failure mode of your system?"

> "Multi-filing questions. If the question requires chunks from
> two different 10-Ks to answer, my top-5 retrieval often has room
> for only one. The fix is query decomposition: split the question
> into sub-questions, retrieve for each, merge the contexts. It
> adds latency but should lift the multi_hop and comparison
> categories from 50% recall to the 70s."

### "How would you fix the benchmark?"

> "Three changes. First, allow multiple valid sources per
> question. Second, add questions that specifically test
> cross-filing synthesis. Third, add an evaluator that doesn't
> penalize legitimate rephrasings of the same correct answer.
> The current RAGAS-based judge is good but it still can't tell
> when a different source produced an equivalent answer."
