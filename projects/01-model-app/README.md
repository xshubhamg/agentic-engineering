# Stage 1 — Model-powered application

Days 1–3 · `stage-1` tag · Gate: a single-call app you would trust with a
stranger's question

## End goal

You can explain, from the wire up, what happens when your code talks to a model:
the request shape, the response shape, why it stopped, what it cost, and what
happens when it fails. No framework, no abstraction you did not write.

Signal at this stage: a research assistant. User asks a question, the model
answers from its own knowledge. It will be wrong about real companies, and that
is the point — it sets up Stage 2.

## Why this comes first

Every later bug — a tool call that never fires, a citation that does not resolve,
a workflow that loops — is eventually debugged at this layer. People who skip it
spend months reading framework docs to understand a payload they have never seen.

## Build

1. One script, one call. Print `stop_reason`, input/output tokens, latency.
2. One `ModelClient` wrapper class. Everything goes through it — later stages
   will add tracing, budgets, and retries, and there must be exactly one place
   to put them.
3. Config from env via `pydantic-settings`. Fail loudly if a key is missing; no
   silent defaults.
4. Structured JSON logs: request id, model, token counts, latency, stop reason,
   error type. One log line per call, readable by a machine.
5. Streaming mode behind a flag. Handle a disconnect mid-stream.
6. Prompt as a versioned file, not an inline string. System instructions
   separate from user content — that separation matters in Stage 3.

Suggested shape:

```
src/signal/
  config.py        # env → typed settings
  client.py        # ModelClient: call, stream, retry, account
  prompts/answer.md
  logging.py
  cli.py
tests/test_client.py
```

## Concepts you must be able to explain

- system vs user vs assistant messages, and why retrieved text is never a system message
- `stop_reason` values and what each implies for your code
- temperature / top_p / max_tokens — what you actually change and why, and why
  anything evaluated should be deterministic
- input vs output tokens, and how prompt caching would change your cost model
- why retries need jitter and a ceiling, and which errors are *not* retryable
- why `max_tokens` truncation is a correctness bug, not a cosmetic one

## Definition of done

- [ ] `uv run signal ask "…"` works from a clean shell with only `.env` present
- [ ] streaming works and a killed connection produces a typed error, not a traceback
- [ ] timeout, 429, 5xx, and invalid key each map to a distinct, logged error
- [ ] truncated output is detected via `stop_reason` and surfaced to the caller
- [ ] every call emits one JSON log line with tokens, latency, cost estimate
- [ ] 3+ tests using a mocked HTTP layer (no live API in tests)
- [ ] `ruff check` and `pytest` pass
- [ ] log entry written: what you can now explain that you could not on Day 1

## Failure drills

| Drill | How | Expected |
| --- | --- | --- |
| Timeout | point base URL at a blackhole, 5s timeout | typed timeout error, one log line, no retry storm |
| Rate limit | mock 429 ×3 then 200 | backoff with jitter, succeeds, attempts logged |
| Truncation | `max_tokens=5` on a long question | detected, reported as incomplete, not returned as an answer |
| Bad key | unset the env var | startup validation error naming the variable |
| Huge input | 200k-token prompt | clear context-limit error before the request is sent |

## Evidence to keep in `evidence/`

- one success log line
- one truncation log line
- `pytest -q` output

## Stretch (only if the gate is passed early)

- model routing: cheap model for extraction, strong model for answers, log which
  served each request
- prompt-cache the system prompt and show the cost delta
- a 10-case smoke test with pass/fail, which becomes the seed of Stage 6
