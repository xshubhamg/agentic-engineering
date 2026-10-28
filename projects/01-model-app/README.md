# Stage 1 — Model-powered application

Days 1–3 · `stage-1` tag · Gate: a single-call app you would trust with a
stranger's question

**Read [CODE-TOUR.md](CODE-TOUR.md) alongside the code** — it explains why each
file exists, with deep dives on the retry state machine and the streaming commit
point.

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

Suggested shape (this is what is scaffolded below):

```
src/signal_agent/
  config.py            # env → typed settings
  client.py            # ModelClient: call, stream, retry, account, budget
  errors.py            # typed failures
  prompts/answer.md    # prompt, versioned by content hash
  logging.py
  cli.py
tests/                 # scripted provider, no network
```

Note: the package is `signal_agent`, not `signal` — `signal` is a stdlib module
and would shadow the package at import time.

## Run it

```bash
cp ../../.env.example .env      # paste your OpenRouter key
uv sync
uv run signal ask "What does a healthy sales pipeline look like for a B2B SaaS company?"
```

Expected: the answer on stdout, then on stderr one metadata line
(`stop=stop tokens=.../... cost=$... latency=...ms attempts=1 id=req_...`) and one
JSON `model_call` log line.

```bash
uv run signal ask "…" --stream     # token by token; same metadata at the end
uv run pytest                       # 23 tests, no key, no network
uv run ruff check . && uv run ruff format --check .
```

## What is scaffolded, and what is yours

Already here — read it, then verify it, do not trust it:

| File | What it gives you |
| --- | --- |
| `src/signal_agent/config.py` | env → typed settings; a missing key fails at startup, not mid-request |
| `src/signal_agent/client.py` | `complete` / `stream`, own retries with jitter, budget guard, one log line per call |
| `src/signal_agent/errors.py` | typed failures, each mapping to exactly one recovery strategy |
| `src/signal_agent/prompts/answer.md` | prompt versioned by content hash, so logs say `answer@320c4397` |
| `src/signal_agent/cli.py` | exit codes per failure kind: 2 truncated, 3 auth, 4 provider, 5 budget, 7 config |
| `tests/` | 23 tests against a scripted provider transport (fake, fast, no key) |

Yours — this is the actual work of days 1–3:

- Draw the request path from CLI to wire and back, from memory, before you edit
  anything.
- Run every failure drill below against the live API and read the log line and
  exit code for each. If reality disagrees with the table, that is a bug: fix it
  or write down why the behavior is acceptable.
- Add the async path (`complete_async` or an async client class). The sync client
  blocks, and FastAPI at stage 7 will need this. Do it now, while the surface is
  small.
- Write the Day 1–3 log entry and the 5-sentence explanation from
  `docs/03-engineering-log.md`.

## Drill commands (run these, do not read them)

```bash
# truncation → exit 2, partial text preserved in the error
uv run signal ask "Explain retrieval augmented generation in detail" --max-tokens 6

# timeout → exit 4 after retries
SIGNAL_REQUEST_TIMEOUT_S=0.001 uv run signal ask "hello"

# auth failure → exit 3, no retries, no cost
# (OpenRouter also answers "Missing Authentication header" for an invalid key,
#  so do not go hunting for a missing header — check the key itself.)
OPENROUTER_API_KEY=sk-or-invalid uv run signal ask "hello"

# config failure → exit 7, names the missing variable
env -u OPENROUTER_API_KEY uv run signal ask "hello"

# streaming: watch tokens arrive, then check usage on the final line
uv run signal ask "Count to five, one word per line" --stream
```

Rate limits and 5xx are hard to force against a live provider; the tests in
`tests/test_client.py` force them deterministically. That asymmetry is the
lesson: mocks are for failure modes you cannot schedule.

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
- [ ] every call emits one JSON log line with tokens, latency, cost
- [ ] the scaffolded tests pass, plus at least one test you wrote for a bug you found
- [ ] `ruff check` and `pytest` pass on a clean checkout
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
