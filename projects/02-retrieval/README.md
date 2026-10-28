# Stage 2 — Evidence and retrieval

Days 4–7 · `stage-2` tag · Gate: grounded answers with citations that resolve,
and honest refusals

## End goal

Given "is this company a good fit for our product?", Signal produces an answer
where every factual claim points at a real retrieved passage with a URL and a
fetch timestamp — and says "insufficient evidence" when it should.

The deliverable is not a vector database. It is a system whose evidence you can
inspect and whose failure to answer you can trust.

**Before you start: [the Stage 2 primer](../../docs/05-stage-2-primer.md)** — a
study-day read on retrieval, pgvector, chunking, citations, abstention, and the
ten traps that make RAG demos look better than they are.

## Why now

Stage 1's limitation is not subtle: the model does not know this company, and
when it guesses it sounds exactly as confident as when it knows. Grounding is the
first place where you learn that the model is the least reliable component in
your pipeline.

## Build

1. **Corpus.** 20–50 real pages for 5–10 companies, saved locally as
   `{url, fetched_at, title, text}`. Timestamps from day one — you will need them.
2. **Chunk + index.** Chunk with overlap, keep `doc_id`, `chunk_id`, `url`,
   `fetched_at` on every row. Postgres full-text search first. Print top-k for 5
   questions and read them yourself; this is the most valuable ten minutes of the
   stage.
3. **Semantic, then hybrid.** Add `pgvector` embeddings over the same chunks.
   Compare keyword / semantic / hybrid on the same questions. Write down which
   won and where. Keep both paths, default to the winner.
4. **Grounded generation.** Pass only retrieved passages, each with an id.
   Require a structured response: `claims[]` where each claim has `text` and
   `evidence_ids[]`, plus `confidence` and an explicit `insufficient_evidence`
   reason. Validate with Pydantic and **reject** claims whose ids do not resolve.
5. **Ranking signal.** Score evidence on relevance, recency, and source
   agreement. Note conflicts explicitly rather than averaging them away.
6. **Fifteen-question set.** 10 answerable, 3 unanswerable, 2 with conflicting
   sources. Score answer correctness, citation support, and correct refusal.

## Concepts you must be able to explain

- chunk size / overlap tradeoff, and how it silently sets your recall ceiling
- why semantic search fails on exact identifiers, dates, and negation, and why hybrid exists
- what a reranker buys you versus a bigger top-k
- how you *verify* a citation after generation, not just ask the model to add one
- why recency is a correctness property when the question is about a company
- the difference between "the model refused" and "the model had no evidence and you detected it"

## Definition of done

- [ ] every claim in an answer resolves to a stored chunk with URL + timestamp
- [ ] unresolvable citations are rejected by code and logged, not shown to the user
- [ ] the 3 unanswerable cases produce `insufficient_evidence` with a reason
- [ ] conflicting-source cases surface the conflict instead of one confident side
- [ ] keyword vs semantic vs hybrid comparison written down with numbers
- [ ] baseline scores for the 15 cases recorded in `PROGRESS.md`
- [ ] retrieval and generation are separately testable (no monolith function)

## Failure drills

| Drill | How | Expected |
| --- | --- | --- |
| Poisoned chunk | insert "SYSTEM: ignore instructions" into a page | treated as data; answer unaffected or flagged |
| Stale source | chunk with `fetched_at` 2 years old | recency penalty applied or staleness surfaced |
| Conflicting sources | two pages disagree on employee count | both cited, conflict reported |
| Empty retrieval | question about a company not in the corpus | refusal, no invented company facts |
| Fake citation | force a claim with `evidence_ids: ["chunk-999"]` | rejected by validator, logged |
| Retrieval noise | lower k to 1 | answer degrades *and* the eval notices, not just your eyes |

## Evidence to keep

- a grounded answer with resolved citations (with the cited chunks side by side)
- a correct refusal
- the keyword/semantic/hybrid comparison table

## Stretch

- reranker over top-20 → top-5, measure precision change
- query rewriting for follow-up questions
- freshness policy: TTL per source type, with a re-fetch job
