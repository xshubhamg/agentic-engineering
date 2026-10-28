# Stack decisions

Default choices, with the reason and the escape hatch. Pick one per row on Day 1
and write the date below so you do not re-litigate it in week three.

| Layer | Default | Why | Swap if |
| --- | --- | --- | --- |
| Language | Python 3.12+, `uv` for env/deps | ecosystem, typing, speed of iteration | you already live in TS |
| Model access | **OpenRouter**, via the **OpenAI Python SDK** | one key, many models, OpenAI-compatible protocol — so everything you learn transfers to a direct OpenAI/Anthropic client later | direct provider SDK if you get a key |
| Models | **one model everywhere**: `deepseek/deepseek-v4.1-flash` | consistency makes eval numbers comparable across stages; one variable at a time | `SIGNAL_MODEL` env var, no code change |
| Validation | Pydantic v2 | every boundary (tool args, API request, LLM output) validated | — |
| Config | env vars + `pydantic-settings` | no secrets in code; one config object | — |
| Logging | `structlog` (JSON) | inspect a request after the fact; greppable | `loguru` if you prefer |
| Storage | Postgres 18 | relational truth for leads/state/approvals | — |
| Retrieval | Postgres full-text first, `pgvector` when semantic is justified | prove the simpler thing fails before adding vectors | Pinecone/Qdrant if scale demands |
| Orchestration | hand-rolled loop, then **LangGraph**; study **Temporal** | you must feel why checkpoints exist before a framework hides them | Temporal if you need long-running durable processes |
| API | FastAPI | typed request/response, async, OpenAPI for free | — |
| Tests | pytest, with a scripted `httpx2.MockTransport` | deterministic tests for a probabilistic system | `respx` if you stay on httpx 0.x |
| Lint/format | ruff | fast, one tool | — |
| Tracing | Langfuse (self-host or free cloud) | spans, tokens, cost, prompt versions; open source | LangSmith if you are OpenAI/Anthropic-native |
| Packaging | Docker (multi-stage) | one artifact, same everywhere | — |
| CI | GitHub Actions | tests on every push, eval gate | — |
| Email send | a sandbox/dev mailbox or a fake provider in tests | never test with real sends | real provider behind a feature flag |

## Non-negotiable conventions

- **Two model tiers.** `cheap` for extraction/classification/reranking, `strong`
  for reasoning and drafting. Log which tier served each span.
- **`temperature=0` for anything evaluated** unless randomness is the point.
- **Every model call goes through one client wrapper** so retries, timeouts,
  token accounting, tracing, and budget caps are implemented once.
- **Every tool goes through one registry** so validation, permission checks,
  audit logging, and tracing are implemented once.
- **Every secret from env**, never a default value that silently works.
- **No real side effects in tests.** Email/LinkedIn senders have fakes.

Decisions made on: 2026-10-28. Changes after this require a note in the log.

## Why OpenRouter, and what it costs you

OpenRouter is an OpenAI-compatible gateway: same request shape, same streaming
format, same tool-call schema. You learn the real protocol, not a vendor's
wrapper, and you can swap the model with one env var.

Two things it does not hide, and you should know:

- **Cost comes back on the response** (`usage.cost`) because the request asks for
  it (`extra_body={"usage": {"include": True}}`). No hardcoded price table, and
  no silent stale pricing.
- **`finish_reason` is the provider's, passed through.** `length` means
  truncation. Treat any unknown value as "not a clean stop" rather than assuming
  success.

## Trap worth remembering (2026)

`openai>=3` talks HTTP over **httpx2**, not httpx. Mocking libraries that patch
httpx (like `respx`) silently miss, and your "unit" tests hit the live API. The
fix used in `projects/01-model-app` is to inject a transport:

```python
httpx2.Client(transport=httpx2.MockTransport(handler))
```

If a test suite is suspiciously slow, or needs a key to pass, it is not a unit
test.
