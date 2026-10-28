# Stage 1 code tour

How to read the code you just ran. ~90 minutes end to end, and you should have
the terminal open while you read — every claim below is checkable in one command.

Suggested order: run the drills first (10 min), then read this top to bottom.
Read the source in dependency order: `config.py` → `errors.py` → `client.py` →
`prompts/` → `cli.py`.

---

## 1. Before: the 20-line version

This is what almost everyone writes first:

```python
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENROUTER_API_KEY"], base_url="https://openrouter.ai/api/v1")
r = client.chat.completions.create(model="deepseek/deepseek-v4.1-flash", messages=[...])
print(r.choices[0].message.content)
```

It works, then five concrete pains arrive:

| Pain | What it looks like |
| --- | --- |
| Can't answer "where did the money go?" | No tokens, no cost, no per-request record |
| Can't tell a slow call from four retries | The SDK retries silently inside `create()` |
| A truncated answer looks finished | `content` is a string either way |
| The key leaks into a traceback or a debug log | It's a plain `str` |
| The 40th call site retries differently | Copy-paste; no choke point |

None of these are model problems. They are boundary problems.

## 2. Assumptions vs truths

| Assumption | Status |
| --- | --- |
| "A model call returns a string or raises" | **False.** It returns a string *plus* metadata (stop reason, tokens, cost) that changes what you should do |
| "More retries means more reliability" | **False.** Retrying a 401 or a policy denial is slower *and* less reliable |
| "The SDK's retries are good enough" | **Half true.** Competent, but invisible: you can't log attempts or test the backoff |

## 3. Root cause

The naive version collapses three unrelated failure modes into one `str | Exception`:

- **transport** — network, rate limits, timeouts
- **correctness** — a partial or malformed answer
- **money** — tokens and cost

Ask *why* twice: why does collapsing them matter? Because a partial answer that
looks complete gets shipped. Why is that worse than an error? Because it is
silent — you hear about it from a customer, not from a log.

So the root cause is: **there is no single checkpoint where a failure can be
classified, counted, and either retried or refused.**

## 4. Pivot

> So what if every model call passed through one checkpoint that classifies the
> failure, counts the money, and refuses to call a partial answer "done"?

That checkpoint is `ModelClient`. Every other file in `src/` exists to support it.

---

## 5. pyproject.toml: the environment contract

The file has three audiences. Read it that way, not as one config blob.

| Section | Audience | What it controls |
| --- | --- | --- |
| `[project]` | uv / pip | name, Python floor, runtime dependencies |
| `[dependency-groups]` | uv | dev-only tools, never shipped in the wheel |
| `[project.scripts]` | your shell | the `signal` command |
| `[build-system]` | hatchling | how the package is built |
| `[tool.hatch.build.targets.wheel]` | hatchling | where the package lives (`src/` layout) |
| `[tool.pytest.ini_options]` | pytest | where tests are, default flags |
| `[tool.ruff]`, `[tool.ruff.lint]` | ruff | line length, syntax floor, rule families |

Five things worth internalizing:

1. **`[project.scripts]` is why `uv run signal` exists.**
   `signal = "signal_agent.cli:main"` generates a launcher that imports the
   module and calls `main()`. The `return EXIT_AUTH` value becomes the process
   exit code. Remove the table and the command vanishes.

2. **`src/` layout is discipline.** `import signal_agent` works only because
   `uv sync` *installed* the package. In a flat layout, imports succeed from the
   repo directory even when packaging is broken, so you find out at deploy time
   instead of on day one.

3. **`[dependency-groups]` ≠ `[project.optional-dependencies]`.** The dev group
   never enters the wheel metadata; `uv sync --no-dev` is the production install.
   That's why `pytest` and `httpx2` are down there and `openai` is above.

4. **`target-version = "py312"`** stops ruff's pyupgrade rules from suggesting
   syntax newer than your floor (`X | None` is allowed; 3.13-only features are
   not).

5. **`uv.lock` is the reproducibility contract.** CI runs `uv sync --frozen`,
   which fails when the lock is stale instead of silently resolving something
   new. "It worked yesterday" becomes checkable.

Lint rule families in `select`: `E` pycodestyle, `F` pyflakes (real defects like
unused variables), `I` import order, `UP` pyupgrade, `B` bugbear (mutable
defaults, shadowed loop vars), `SIM` simplifications. `F` and `B` are the ones
that catch bugs; the rest are consistency.

---

## 6. The request path

```
main()                        cli.py
 ├─ Settings()                config.py     ← fail here, at startup, not at 2am
 ├─ configure_logging()       logging.py    ← logs to stderr, answer to stdout
 ├─ ModelClient(settings)     client.py     ← builds OpenAI client, max_retries=0
 ├─ load_prompt("answer")     prompts/      ← file + sha256 → answer@320c4397
 └─ client.complete(messages)
     ├─ _check_budget()                     ← refuse before spending
     ├─ _payload()                          ← ONE place that defines request shape
     ├─ _with_retries(create)               ← classify → backoff → log each attempt
     ├─ response.model_dump()               ← pydantic → dict, extras survive
     ├─ Completion(...)                     ← immutable record of what happened
     ├─ _record()                           ← spend += cost, emit one model_call event
     └─ if truncated → ModelTruncated
```

### config.py — one object, loaded once

```python
api_key: SecretStr = Field(
    validation_alias=AliasChoices("OPENROUTER_API_KEY", "SIGNAL_OPENROUTER_API_KEY")
)
```

Four decisions in one line:

- `env_prefix="SIGNAL_"` means `model` reads `SIGNAL_MODEL`. The key is the
  exception: `validation_alias` **bypasses the prefix**, which is why the env var
  is `OPENROUTER_API_KEY` and not `SIGNAL_OPENROUTER_API_KEY`.
- `SecretStr` makes `repr(settings)` print `**********`. The real value needs
  `.get_secret_value()`, which appears exactly once in the codebase
  ([client.py](src/signal_agent/client.py)). That single call site is your audit
  surface for "where can the key escape?".
- **No default** is deliberate: a missing key fails at `Settings()` with exit 7,
  before any request. A default of `""` fails later, deeper, as a 401.
- `extra="ignore"` means unrelated env vars don't crash startup.

### errors.py — the type system is the policy

| Family | Classes | Caller's move |
| --- | --- | --- |
| Transport (`ModelError`) | `ModelTimeout`, `ModelRateLimited`, `ModelUnavailable`, `ModelAuthError`, `ModelBadRequest` | retry, surface, or fix config |
| Correctness (`SignalError`) | `ModelTruncated`, `BudgetExceeded` | do not retry; do something different |

Why classes instead of `ModelError(kind="RATE_LIMITED")`? Because `except
ModelAuthError` cannot accidentally catch a `BudgetExceeded`. With string kinds,
one typo silently routes a budget failure into a retry path.

`ModelTruncated` carrying `.completion` is the other important move: the caller
gets the partial text *and* the failure, so it can log what happened without
being able to mistake it for success.

### client.py — structure

- `Usage` / `Completion` are frozen dataclasses: a completion is a historical
  fact, and mutating it corrupts the log that describes it.
- `truncated` is a **property derived from `stop_reason`**, never a stored
  boolean — a stored flag can drift out of sync with the thing it describes.
- `_classify` is the only place that knows provider failure semantics.
- `_with_retries` is the only place that knows retry policy.
- `_payload` is the only place that knows the request shape.
- `_record` is the only place that knows accounting and logging.

Four separate "only places" is the whole design. Deep dives below cover the two
that take real thought.

### prompts/ — file plus hash

A prompt is source code that changes model behaviour but doesn't look like code,
so it escapes review. Three consequences, handled:

- it lives in a file → diffable in a PR
- it gets a content hash → `answer@320c4397` appears in logs and traces, so a
  regression is attributable to exact text
- it's read with `importlib.resources`, not `open("prompts/answer.md")` — a
  relative open works in the repo and breaks once the package is installed,
  because the process CWD is no longer the package root

Try it: edit a word in `answer.md`, rerun, and watch the prompt version change in
the `model_call` log line. That is your primitive for prompt-level attribution in
stage 6.

### logging.py — two streams, on purpose

Answer → stdout. Logs → stderr. So `signal ask "..." > answer.txt` captures prose
only and `2> log.jsonl` captures machine data only. Most CLIs get this wrong, and
then every consumer parses around it.

The noisy-logger block is subtler than it looks:

```python
for noisy in ("openai", "httpx", "httpx2", "httpcore"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
```

The SDK logs full request payloads at DEBUG. Harmless on day 1; in stage 3 those
payloads contain retrieved company text and lead records. That's a data leak into
logs, one config line away.

### cli.py — exit codes are an API

`EXIT_TRUNCATED=2`, `EXIT_AUTH=3`, `EXIT_UNAVAILABLE=4`, `EXIT_BUDGET=5`,
`EXIT_BAD_REQUEST=6`, `EXIT_CONFIG=7`. A shell script or CI job branches on those
without parsing prose.

`main()` returns an int instead of calling `sys.exit()` itself — an int is
testable, a `SystemExit` is not (see `tests/test_cli.py`).

Note the chicken-and-egg: `Settings()` is loaded *before* `configure_logging()`,
because you need settings to know the log level. Config errors are therefore
printed with `print`, not `log`.

And the message split that stage 3 depends on:

```python
messages = [
    {"role": "system", "content": prompt.text},
    {"role": "user", "content": question},
]
```

Retrieved text goes in a `user` (or `tool`) message, never `system`. A web page is
data; in the system slot it becomes instructions.

---

## 7. Deep dive A — the retry state machine

### Timeline with the defaults

`max_retries=3`, `retry_base_delay_s=0.5`, `retry_max_delay_s=8`:

```
t=0.0   attempt 1 ── 503
        sleep 0.25–0.75s        base 0.5  × jitter(0.5–1.5)
t≈0.5   attempt 2 ── 503
        sleep 0.50–1.50s        base 1.0  × jitter
t≈1.5   attempt 3 ── 503
        sleep 1.00–3.00s        base 2.0  × jitter
t≈3.5   attempt 4 ── 503
        give up → ModelUnavailable, one model_call_failed line
```

Total requests: **4**. Total log lines: **4** (3 × `model_call_retry` at warning,
1 × `model_call_failed` at error). If you ever see 1 log line and assumed 1
request, check `attempts=`.

### Classification table

`_classify` is a lookup from provider exception to (typed error, retryable):

| Exception | Typical status | Typed error | Retry? |
| --- | --- | --- | --- |
| `APITimeoutError` | — | `ModelTimeout` | yes |
| `RateLimitError` | 429 | `ModelRateLimited` (+ Retry-After) | yes |
| `APIConnectionError` | — | `ModelUnavailable` | yes |
| `APIStatusError` | 408/409/425/429/500/502/503/504/529 | `ModelUnavailable` | yes |
| `AuthenticationError` | 401 | `ModelAuthError` | **no** |
| `PermissionDeniedError` | 403 | `ModelAuthError` | **no** |
| `BadRequestError` | 400/422 | `ModelBadRequest` | **no** |
| `NotFoundError` | 404 | `ModelBadRequest` (unknown model/route) | **no** |
| `APIStatusError` | 402 | `ModelError` (out of credits) | **no** |
| anything else | — | `ModelError` | **no** |

**Order matters.** `APITimeoutError` subclasses `APIConnectionError`, and
`RateLimitError` / `AuthenticationError` / `BadRequestError` all subclass
`APIStatusError`. If you checked `APIStatusError` first, every failure would
collapse into one generic error and you would lose the ability to branch.

### The off-by-one people get wrong

```python
for attempt in range(1, self._s.max_retries + 2):   # 1 initial + N retries
```

`max_retries=3` → attempts 1, 2, 3, 4. If you wrote `range(max_retries)`, you
would get 3 total attempts and call it "3 retries" — a 25% budget error that
nobody notices until an incident review.

### Jitter: why, and which kind

```python
jittered = base * (0.5 + random.random())  # factor 0.5 … 1.5
```

Pure exponential backoff synchronizes clients: everyone who got a 429 at
`t=0` retries at exactly `t=1`, producing a second spike. Jitter spreads them.

This is "equal jitter" (half fixed, half random), so the wait never collapses
to ~0 and never doubles. Full jitter (`random() * base`) spreads better but can
retry almost immediately.

The cap applies to the **result**, not the base:

```python
return min(jittered, self._s.retry_max_delay_s)
```

If you cap the base and then multiply by up to 1.5, your "8 second maximum" is
really 12. The scaffold did that until this tour was written; there is now a test
(`test_backoff_result_never_exceeds_the_cap`) that would have caught it.

`Retry-After` bypasses the formula and is hard-capped:

```python
return min(float(retry_after), self._s.retry_max_delay_s)
```

The server knows when its window reopens; your exponent does not. No jitter here,
because retrying earlier re-triggers the limit and retrying later is just slower.

### The budget you did not know you had

`request_timeout_s=60` is **per attempt**, not per request. With 3 retries the
worst case is `4 × 60s + ~5s of backoff ≈ 245 seconds`. A caller that assumed
"60 second timeout" will be surprised.

This is why stage 5 adds a deadline *per workflow step*: a per-call timeout
bounds one socket, not the user's wait.

### What must never be wrapped in a retry

- **Side effects** — sending the email, writing to the CRM. Retrying without an
  idempotency key turns one send into three.
- **Policy denials** — a blocked action is not a transient failure; retrying it
  is an attempt to bypass the policy.
- **Validation failures** — the payload will be identically wrong next time.

An LLM completion is safe to repeat because it's a read. That property is what
makes this retry loop legitimate, and it stops being true in stage 3.

### Which test proves which transition

| Behaviour | Test |
| --- | --- |
| 429 then success, exactly one backoff | `test_retries_on_429_then_succeeds` |
| Server's Retry-After wins | `test_honours_retry_after_header` |
| 401 is not retried | `test_does_not_retry_authentication_failure` |
| 5xx stops after the ceiling | `test_gives_up_after_max_retries_on_5xx` |
| Timeout maps to a typed error | `test_timeout_maps_to_model_timeout` |
| 402 is not retried | `test_out_of_credits_is_not_retried` |

---

## 8. Deep dive B — streaming and the commit point

### The wire format

Streaming is server-sent events: a sequence of `data: {json}\n\n` frames, ended
by `data: [DONE]`.

```
data: {"choices":[{"delta":{"role":"assistant","content":"Hel"}}]}
data: {"choices":[{"delta":{"content":"lo"}}]}
data: {"choices":[{"delta":{},"finish_reason":"stop"}],"usage":{"prompt_tokens":10,...}}
data: [DONE]
```

`content-type: text/event-stream` is what makes httpx hand you lines as they
arrive instead of buffering the whole body. Without it, the SDK reads a body at
the end and "streaming" is an illusion.

Chunk lifecycle: the first chunk carries `delta.role`, middle chunks carry
`delta.content`, one chunk carries `finish_reason`, and — only when you send
`stream_options={"include_usage": True}` — a final chunk carries `usage`.

That flag is not cosmetic. Without it, `usage` is absent, `cost_usd` becomes
`None`, and the budget guard silently stops working. The `cost_unknown` warning
exists precisely so this failure is loud.

### Why a wrapper class instead of a plain generator

A generator cannot return a value. `for delta in client.stream(...)` gives you
text, but you also need `usage` and `stop_reason` *after* iteration. Options:

- out-parameter (mutable dict) — ugly, easy to forget
- callback — awkward at every call site
- an object that is iterable and holds the result

```python
stream = client.stream(messages)
for delta in stream:
    print(delta, end="")
print(stream.completion.usage)  # filled in when iteration finished
```

`__next__` exists so `next(stream)` works as well. Small thing, but the difference
between a Pythonic object and a thing you have to wrap.

### The commit point: first token

```
attempt 1 ── request ──┬─ fails before any token ── retryable? ── yes ──> retry (safe)
                       └─ first token delivered ── any failure now ──> terminal
```

```python
emitted = False
...
if delta:
    emitted = True
    yield delta
...
retryable = retryable and not emitted
```

Before the first token, a failure is invisible to the user, so retrying is
honest. After the first token, a retry duplicates output:

```
The company was founded in The company was founded in 1998
```

There is no "continue from token 500" in this protocol. Some providers offer
continuation via prefill, but relying on it couples you to a vendor and still
doesn't fix the UI that already rendered text.

So the rule is: **the first token is a commit point.** Same principle shows up
later as the approval gate (stage 3–5) and as idempotency keys (stage 5): once a
side effect is observable, you cannot pretend it didn't happen.

### Truncation while streaming

`finish_reason="length"` arrives in the last chunk, *after* you have already
delivered the text. So the raise happens after the user has seen a partial
answer. The CLI prints it, then warns and exits 2 — you cannot un-print.

That's an honest design tension worth naming: a CLI shows and warns; an HTTP API
would either buffer (losing the streaming benefit) or mark the response as
incomplete in its own protocol. Stage 7 has to decide.

### Known limitation: an abandoned stream is invisible spending

```python
stream = client.stream(...)
for delta in stream:
    break  # user disconnected, client gave up, etc.
```

Breaking out raises `GeneratorExit` at the `yield`. `GeneratorExit` inherits from
`BaseException`, so `except Exception` does **not** catch it. The `with` block
closes the HTTP connection, and the code after the loop — including `_record` —
never runs. Result: no `completion`, no cost, no log line. The money was spent
and your accounting never saw it.

`test_abandoning_a_stream_early_skips_accounting` pins this behavior so it can't
change silently. Three possible fixes, for stage 7 to choose:

1. wrap the body in `try/finally` and record partial usage (usually unknown, so
   you'd get `cost_unknown` rather than a number)
2. reserve an estimated cost before the call, reconcile after
3. drain the stream in the background with a size/time cap

Naming a limitation precisely is worth more than a fix you can't justify yet.

---

## 9. Invariants

What must stay true for this design to keep working, and how each one dies:

| Invariant | How it breaks |
| --- | --- |
| One log line per call | A second `create()` call site outside `ModelClient` |
| Partial answers never returned as complete | Catching `ModelTruncated` broadly and using `.completion.text` |
| Retries stop at the first token | Deleting the `emitted` check "because it looks redundant" |
| Cost is measured, not guessed | Treating `cost_usd is None` as `0.0` |
| The key never reaches logs | `print(settings)` once `api_key` stops being `SecretStr` |
| Retry only idempotent operations | Reusing `_with_retries` around `send_email` in stage 3 |
| One client per run | Sharing a `ModelClient` across threads: `_spend_usd += ` is not atomic |

That last one is not theoretical: a module-level singleton client in FastAPI
(stage 7) makes every request share one spend counter and one budget. One client
per run, or a lock plus per-tenant counters.

---

## 10. Warts and exercises

Fixed while writing this tour (so the doc matches the code):

- dead branch in `cli.py` — `if not raise_on_truncation: pass` in the truncation
  handler could never be true
- `max_tokens or default` treated `max_tokens=0` as "not provided"
- the jitter cap was applied to the base delay, not the final delay

Still open, deliberately:

| Open item | Why it's open |
| --- | --- |
| Abandoned stream skips accounting | Fix requires a policy decision (reserve vs drain); stage 7 |
| `spent_usd` is not thread-safe | Becomes real when the service is concurrent; stage 7 |
| `messages` are unvalidated dicts | Stage 3 needs a schema at the tool boundary |
| Sync client only | Fine for a CLI; FastAPI needs async |

Your exercises, in increasing difficulty:

1. Add `--temperature` to the CLI and pass it through. Cheap, and it proves you
   followed the data path.
2. Add a test that forces a 500 on attempt 1, a 429 on attempt 2, and success on
   attempt 3. Assert both the attempt count and the fact that two backoffs
   happened.
3. Write `complete_async()` and make the existing tests run against both. Watch
   which parts were easy (payload, classification) and which were not (retry loop,
   stream wrapper) — that tells you what is actually coupled.
4. Change the backoff to full jitter and re-run `test_backoff_result_never_exceeds_the_cap`.
   Convince yourself the cap still holds and that a test can express "spread"
   only statistically, never exactly. That's the boundary of unit testing.

## 11. Check yourself

Answers below; cover them first.

1. `SIGNAL_MAX_RETRIES=3`, provider 503s forever. How many HTTP requests, how
   many log lines, which types?
2. Why does a 429 sometimes produce a shorter wait than your exponential formula
   predicts?
3. `usage.cost` is missing from the response. Which guarantee did you lose, and
   what does the log say?
4. Why is `truncated` a property instead of a stored field?
5. A caller passes `max_tokens=0`. What did the old code do, and why is that
   worse than an error?
6. Two requests share one `ModelClient`. What breaks first?

<details>
<summary>Answers</summary>

1. 4 requests. 4 log lines: three `model_call_retry` (warning) then one
   `model_call_failed` (error). `attempts=4` appears on the failure line.
2. The server sent `Retry-After`. `_backoff` prefers the header and caps it,
   skipping the exponent entirely.
3. Budget enforcement. `_record` logs `cost_unknown` and does not add to
   `_spend_usd`, so `_check_budget` keeps allowing calls. You still see tokens
   and latency; you just cannot price them.
4. `stop_reason` is the single source of truth. A stored boolean can drift if a
   provider introduces a new non-clean stop reason; a property cannot.
5. It silently fell back to the 1024 default. Silent fallbacks are worse than
   errors because the request succeeds with the wrong shape and nobody learns.
   Now `is None` is the only "not provided" signal.
6. The spend counter: `+=` on a shared float loses updates, so the budget
   under-counts and allows more spend than intended. Latency and logging stay
   correct; money drifts.

</details>

## 12. A 90-minute plan

| Minutes | Do |
| --- | --- |
| 0–10 | Run the five drill commands from the README. Note each exit code. |
| 10–30 | `pyproject.toml`, then `config.py` → `errors.py`, then `client.py` along the request path. |
| 30–50 | Deep dive A. Re-read `_with_retries` and predict the log lines for the 503 drill before running it. |
| 50–70 | Deep dive B. Reproduce the abandoned-stream behavior with the characterization test, then read `_stream_impl` again. |
| 70–85 | Exercise 1 or 2. |
| 85–90 | Write the Day 1–3 entry in `docs/03-engineering-log.md`. |

If you can do all of that without the source open, stage 1 is genuinely done and
you can tag it `stage-1`.
