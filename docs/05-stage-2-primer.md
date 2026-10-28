# Stage 2 primer — study day before retrieval

Read this the day before Day 4. No code today. The goal is that when you open the
editor you are choosing between tradeoffs you already understand, not discovering
them by accident.

Stage 2's characteristic failure is building fast, judging on five queries, and
concluding "retrieval works". Everything below exists to prevent that.

---

## Session 1 (40 min) — lexical → semantic → hybrid

### Lexical retrieval

An inverted index maps token → documents containing it. Three ideas do the work:

- **Tokenization + normalization** — lowercase, split, stem (`companies` →
  `compani`), drop stopwords. Crude, fast, and it preserves exact identifiers.
- **IDF (inverse document frequency)** — rare terms carry more signal. "Acme"
  appearing in 1 of 50 documents is more discriminating than "the".
- **TF saturation + length normalization** — the 20th occurrence of a word
  shouldn't count 20×, and a 3000-word page shouldn't outrank a 200-word page
  just by volume.

That is BM25 in one paragraph. The formula, because you will see it:

```
score(D, Q) = Σ IDF(qi) · [ f(qi,D) · (k1 + 1) ] / [ f(qi,D) + k1 · (1 − b + b · |D|/avgdl) ]
```

`k1` ≈ 1.2–2.0 controls saturation, `b` ≈ 0.75 controls length normalization.

**Be aware:** Postgres `ts_rank` / `ts_rank_cd` are *not* BM25. They are
cover-density heuristics. Good enough to start, not comparable to a BM25 score.
If you later need real BM25 inside Postgres, that's an extension (ParadeDB), not
a config flag.

### Semantic retrieval

An embedding maps text to a vector so that "close in meaning" ≈ "close in space".
Practical truths:

- **Cosine similarity is the usual default.** If vectors are L2-normalized,
  cosine = dot product. Know which one your index uses, because mixing them
  silently changes ranking.
- **Similarity is not relevance.** A 0.82 score means nothing on its own; scores
  are not comparable across queries or across models.
- **Semantic search is bad at**: exact names, SKUs, dates, numbers, negation
  ("not a subsidiary of"), and rare jargon. It is good at paraphrase and synonymy.
- **Embeddings are not facts.** They encode distributional similarity, not truth.
  Two contradictory statements can embed near each other.

### Hybrid, and why it is the honest default

Run both, fuse the rankings. The standard fusion is **Reciprocal Rank Fusion**:

```
RRF(d) = Σ over lists 1 / (k + rank_list(d)),  k ≈ 60
```

It uses ranks, not scores, which sidesteps "how do I compare a cosine to a
ts_rank". You will implement this in about 15 lines.

**Reranking** is a second, slower, more accurate pass over the top-N (20–50)
candidates, usually a cross-encoder. It buys precision; it does not fix recall.
If the right chunk isn't in the top 50, no reranker saves you.

**MMR (maximal marginal relevance)** trades relevance for diversity — useful when
five chunks say the same thing.

Names you should recognize but not build today: BM25, RRF, MMR, cross-encoder,
ColBERT (late interaction), HyDE (embed a hypothetical answer instead of the
question), BEIR and MTEB (benchmarks/leaderboards).

---

## Session 2 (40 min) — Postgres as the retrieval engine

### Full-text search

```sql
SELECT id, ts_rank_cd(tsv, query) AS rank,
       ts_headline('english', body, query) AS snippet
FROM chunks, websearch_to_tsquery('english', $1) query
WHERE tsv @@ query
ORDER BY rank DESC
LIMIT 20;
```

- `tsvector` = normalized lexemes with positions; `tsquery` = the parsed query.
- `websearch_to_tsquery` accepts `"quoted phrases" -exclusions OR` the way a user
  types them. Use it instead of hand-building `to_tsquery`.
- **GIN index** on `tsv` for lookup speed; `ts_rank` still computes per row.
- `ts_headline` gives you the snippet — free evidence display in Stage 2.
- Gotchas: 1 MB limit per `tsvector`, so index *chunks*, not whole pages;
  stemmer language must match content; `unaccent` for names.

### pgvector

- Column type `vector(N)`; operators `<=>` cosine, `<#>` negative inner product,
  `<->` L2. Read the operator, not the docs summary — the sign conventions differ.
- **HNSW** = graph index, fast, builds slowly, uses memory. **IVFFlat** = cluster
  index, needs data present before building, tunable `lists`/`probes`.
- **Approximate** indexes trade recall for speed. For a 50-page corpus, a
  sequential scan is exact, instant, and correct. Do not add an index until you
  can show it is needed. "We use HNSW" is not an architecture.

### Practical setup for your machine

Verified today:

- `pgvector` is **not installed** and Postgres is **not running** — that's fine,
  it's a Day 4 task.
- Easiest path: Docker image `pgvector/pgvector:pg18`, one compose file, same as
  production later. Alternative: install `postgresql` + `pgvector` packages and
  `CREATE EXTENSION vector;`.

### Schema you will want

```
documents(id, url, title, fetched_at, content_hash, raw_html?, text)
chunks(id, document_id, chunk_index, text, tsv, embedding, token_count)
queries(id, run_id, question, created_at)
retrievals(id, query_id, chunk_id, method, score, rank)
```

That fourth table is the one people skip. Without it you cannot answer "why did
the model say that?" three days later.

Ingestion rules: upsert by `content_hash` (idempotent re-fetch), keep
`fetched_at` per document, store the extractor version, never overwrite a chunk
without recording that you did.

---

## Session 3 (40 min) — evidence discipline

This is the part that separates Stage 2 from a RAG tutorial.

### Chunking

- 200–400 tokens with 10–20% overlap is a sane start; measure before tuning.
- Preserve the **heading path** in the chunk (`"Acme › Leadership › CFO"`); it
  often carries more signal than the body text.
- Store character offsets so a citation can point at an exact span.
- **Chunk boundaries set your recall ceiling.** If the answer spans two chunks and
  neither contains it whole, no model can cite it. This is the single most common
  silent failure.

### Citations that can be checked

Two separate mechanisms, often conflated:

1. **Structural** — every claim carries `evidence_ids`; your code rejects any id
   that does not resolve to a stored chunk. Cheap, deterministic, catches
   hallucinated references.
2. **Semantic** — the cited chunk actually *supports* the claim (entailment). Needs
   an NLI model or a rubric-driven judge. This is where "the citation resolves but
   is irrelevant" gets caught.

Asking the model to "include citations" gives you neither. Both must be enforced
after generation, in code.

### Abstention

`insufficient_evidence` is a product feature, not an error path.

- Define a coverage rule (e.g. at least one high-rank chunk above a score floor,
  and at least one claim-level citation per assertion).
- Write the refusal template once, so refusals are consistent and testable.
- Test it with questions whose answers are deliberately absent from the corpus.
  If you never test refusal, you don't have it.

### Conflict and recency

- **Conflict**: two sources disagree (employee count 40 vs 120). Detect it, cite
  both, report the disagreement with dates. Do not average, do not let the model
  pick silently.
- **Recency**: `fetched_at` is a first-class signal. A 2023 page about a 2026
  company is a stale claim, even if it is well-written. Decide a TTL per source
  type and surface staleness in the answer.

### Context assembly

- Budget the context: system + question + N chunks must fit with room for output.
- Ordering matters — models attend best to the start and end of long contexts
  ("lost in the middle", Liu et al. 2023). Put the strongest evidence first,
  and don't pad with 40 mediocre chunks.
- Deduplicate near-identical chunks before spending tokens on them.

### Retrieval evaluation (separate from answer evaluation)

| Metric | Question it answers |
| --- | --- |
| recall@k | Is the right chunk anywhere in the top k? |
| precision@k | How much of the top k is relevant? |
| MRR | How high is the first relevant result? |
| nDCG | Is the *ordering* good, not just the set? |

You need human judgments on a small set: for 15 questions, mark the chunks that
are actually relevant. That is ~45 minutes of work and it is the only way to know
whether your "improvement" improved anything.

Then, separately, answer-level checks: correct, every claim cited, cited chunk
supports it, refused when it should. Stage 6 formalizes this; Stage 2 just needs
the habit.

---

## Cross-cutting: cost, latency, provenance

- **Embedding cost is trivial at your scale.** 50 pages × ~500 tokens = 25k
  tokens. Even at $0.02/M that is $0.0005. Cost is not the constraint; quality is.
- **Re-embedding is the real cost.** Store `embedding_model` and `dim` alongside
  the vector. Swapping models later means re-embedding the whole corpus — plan for
  it or you will discover it mid-demo.
- **Latency split**: query embedding (one network call) + ANN/FTS lookup + LLM
  generation. Measure each; "retrieval is slow" is not a diagnosis.
- **Provenance**: url, title, fetched_at, content_hash, extractor version. Without
  these a citation is a string, not evidence.
- **Legality/etiquette**: robots.txt, ToS, rate limits, user-agent. Scraping for a
  personal learning corpus is normal; republishing someone's content is not.

---

## Your setup, verified today

| Fact | Implication |
| --- | --- |
| OpenRouter exposes `/embeddings` and `/embeddings/models` (38 models) | One key for chat **and** embeddings — keeps the single-provider story |
| `nvidia/nemotron-3-embed-1b:free` (32k ctx), `voyage-4-lite` ($0.02/M) | Free tier to start; Voyage as the cheap paid step-up |
| `pgvector` not installed, Postgres not running | Day 4 includes environment setup; use the `pgvector/pgvector:pg18` image |
| Corpus ~50 pages | No ANN index. Sequential scan is exact and faster than you think |
| One chat model fixed | Keep embedding model fixed too, or your eval baseline moves under you |

Add to `.env` when you start:

```
SIGNAL_EMBEDDING_MODEL=nvidia/nemotron-3-embed-1b:free
SIGNAL_EMBEDDING_DIM=...
```

Pin the dimension explicitly. Silent dimension changes are a classic way to
corrupt a vector column.

---

## Ten traps

1. **Judging retrieval on 5 queries.** You will tune to those 5 and call it done.
2. **Adding a vector index for 50 pages.** Slower to build, approximate, no win.
3. **Comparing scores across queries or models.** Meaningless; use ranks.
4. **Letting chunking be an afterthought.** It caps recall more than the model does.
5. **Asking for citations in the prompt and trusting them.** Verify structurally.
6. **Treating a resolved citation as a supported claim.** Check entailment.
7. **One "no answer" test.** Refusal is a feature; test it like one.
8. **Averaging conflicting sources.** Surface the conflict, with dates.
9. **Putting retrieved text anywhere near the system prompt.** It's data, not
   instructions — Stage 3 turns this into a security incident if ignored.
10. **Forgetting `fetched_at`.** You cannot recover provenance later, and recency
    is part of correctness.

---

## Self-check before Day 4

Answer these out loud; if any answer is vague, reread that session.

1. Why does keyword search beat embeddings on "Acme Corp Q3 2025 revenue"?
2. What does RRF fuse, and why ranks instead of scores?
3. When is a sequential scan better than HNSW?
4. What is the difference between `<=>`, `<#>`, and `<->` in pgvector?
5. What sets the recall ceiling in a RAG pipeline?
6. Name the two independent checks a citation must pass.
7. How do you test that the system refuses correctly?
8. What do you store so that a citation is evidence rather than a string?
9. Which metric tells you the ordering is good, not just the set?
10. What breaks when you change embedding models in production?
11. Why is `ts_rank` not BM25, and does it matter at your scale?
12. Where does prompt injection enter a retrieval system?

<details>
<summary>Short answers</summary>

1. Exact rare tokens and numbers: embeddings blur them into a general "financial"
   direction; IDF makes the rare token dominate.
2. Ordered result lists from multiple retrievers, using `1/(k+rank)`; ranks are
   comparable across systems whose scores are not.
3. Small corpora (thousands of rows) where exactness matters and latency is fine.
4. Cosine distance, negative inner product, L2 distance — with different sign
   conventions, so read the operator.
5. Chunk boundaries: if the answer spans a boundary, no chunk contains it.
6. Structural resolution (id → stored chunk) and semantic support (the chunk
   entails the claim).
7. Ask questions whose answers are deliberately absent, plus near-miss questions
   where a plausible but wrong chunk exists.
8. url, title, fetched_at, content_hash, chunk offsets, extractor version.
9. nDCG (or MRR if you only care about the first hit).
10. Every stored vector becomes incomparable; the corpus must be re-embedded and
    old eval numbers stop meaning anything.
11. `ts_rank` uses cover density, not BM25's saturating TF/IDF; at 50 pages the
    ranking differences are small, so it matters less than chunking.
12. Through retrieved text itself — a page that says "ignore previous instructions"
    is now inside the context window. Data must never reach the system slot.

</details>

---

## Reading list (titles, search them)

- PostgreSQL docs — *Full Text Search* chapter (the `tsvector`/`tsquery` pages are
  enough; skip the rest)
- pgvector README — read the index sections and the operator table
- Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (2020)
- Liu et al., *Lost in the Middle: How Language Models Use Long Contexts* (2023)
- Barnett et al., *Seven Failure Points When Engineering RAG Systems* (2024)
- Anthropic, *Contextual Retrieval* (2024) — chunk-level context before embedding
- BEIR (zero-shot retrieval benchmark) and MTEB (embedding leaderboard) — skim
- RAGAS docs — skim the metric definitions, not the framework

---

## A 3-hour schedule

| Time | Session | Output |
| --- | --- | --- |
| 0:00–0:40 | Lexical → semantic → hybrid | Can explain BM25, RRF, when each wins |
| 0:40–1:20 | Postgres FTS + pgvector | Know the SQL you'll write on Day 4 |
| 1:20–2:00 | Evidence discipline | Chunking, citations, abstention rules |
| 2:00–2:20 | Evaluation | Draft the 15-question set on paper |
| 2:20–2:50 | Self-check | Answer all 12 without notes |
| 2:50–3:00 | Decisions | Fill the block below |

## Decisions to record before Day 4

```
Embedding model:            (pin id + dimension)
Corpus:                     (how many companies, which page types)
Chunk size / overlap:       (starting point, to be measured)
Retrieval default:          (hybrid; k = ?)
Refusal rule:               (score floor + coverage condition)
What counts as evidence:    (url + fetched_at + chunk id)
```

Write these into `docs/03-engineering-log.md` under a "Stage 2 plan" entry. A
decision you cannot restate next week is a decision you did not make.
