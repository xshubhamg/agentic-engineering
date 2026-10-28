# Stage 6 — Evaluation and observability

Days 16–19 · `stage-6` tag · Gate: one command proves the agent still works, and
CI fails when it stops

## End goal

A reproducible eval suite over a golden set that scores each capability
separately, plus traces good enough to answer "why was this run slow / wrong /
expensive?" without guessing. This is the stage that turns the previous four into
something you can defend.

## Why now

You have six moving parts and no way to know if a prompt change broke citations.
Every earlier stage was built on your judgment. From here on, it is built on
evidence.

## Build

1. **Golden set (30+ cases)** in the repo as YAML. Every case declares: input,
   tenant, expected capability, expected outcome, and which failure class it
   exercises. Cover easy, ambiguous, insufficient evidence, conflicting sources,
   invalid tool args, permission bypass, prompt injection, approval skipped,
   provider failure.
2. **Harness.** One command, deterministic, prints a table: case, capability,
   pass/fail, reason, latency, tokens, cost. Exit code non-zero on regression.
   Infrastructure errors fail loudly — never a silent "pass".
3. **Scorers, one per capability.** Deterministic where possible: did the right
   tool get called with the right args; was the unsafe action blocked; did
   citations resolve and entail the claim. Use an LLM judge only for fuzzy
   qualities, with a written rubric, calibrated on 5 hand-labeled cases. Report
   judge agreement so you know how much to trust it.
4. **Traces.** Retrieval spans, model spans (prompt version, tokens, cost),
   tool spans, step transitions, errors. Langfuse or equivalent. One trace id
   threaded through logs, DB rows, and the API response.
5. **Separate the clocks.** Measure retrieval time, model time, tool time, and
   queue time separately. "The agent is slow" is not a diagnosis.
6. **CI gate.** Eval on every PR with a small fast subset; full suite nightly.
   Store results so you can diff across commits.

## Concepts you must be able to explain

- per-capability scoring vs one aggregate score (and why aggregates hide regressions)
- why an LLM judge must be calibrated, and what its disagreement rate means
- the difference between a flaky eval and a flaky product, and how you tell them apart
- p50 vs p95 latency and why the tail is where agents hurt
- cost per successful run as the real unit economics, not cost per token
- what a trace must contain to debug a wrong answer without re-running it

## Definition of done

- [ ] golden set in the repo, versioned, with a written description of each failure class
- [ ] `uv run eval` prints a per-capability table with pass/fail and cost
- [ ] scores recorded in `PROGRESS.md` and diffable across stages
- [ ] every case produces a trace with model, retrieval, and tool spans
- [ ] CI fails on a deliberate regression (prove it by breaking a prompt on purpose)
- [ ] judge agreement measured on 5 hand-labeled cases
- [ ] latency and cost reported per stage of the pipeline, not just end-to-end

## Failure drills

| Drill | How | Expected |
| --- | --- | --- |
| Deliberate regression | weaken the grounding prompt | eval fails, cites the specific cases |
| Flaky case | run the suite 5× | variance reported; nondeterminism identified and fixed or quarantined |
| Provider outage | mock 500s across the suite | suite fails loudly, does not report 0% quality as a model regression |
| Cost spike | raise max iterations | cost column rises, per-run budget triggers |
| Judge drift | change judge model | agreement drops, you notice before trusting it |
| Missing evidence | delete a cited chunk | citation check fails |

## Evidence to keep

- the baseline table (this goes in the final README)
- a screenshot/link of one trace with spans
- the CI run that failed on purpose

## Stretch

- prompt versioning with A/B comparison on the golden set
- cost attribution per tenant
- a small human-review queue for judge-disagreed cases
