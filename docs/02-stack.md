# Stack decisions

Default choices, with the reason and the escape hatch. Pick one per row on Day 1
and write the date below so you do not re-litigate it in week three.

| Layer | Default | Why | Swap if |
| --- | --- | --- | --- |
| Language | Python 3.12+, `uv` for env/deps | ecosystem, typing, speed of iteration | you already live in TS |
| Model SDK | Anthropic Python SDK **or** OpenAI SDK — one, natively | learn request/response, streaming, tool schema, stop reasons before any abstraction | — |
| Models | one strong model + one cheap model | forces you to think about model routing and cost per task | — |
| Validation | Pydantic v2 | every boundary (tool args, API request, LLM output) validated | — |
| Config | env vars + `pydantic-settings` | no secrets in code; one config object | — |
| Logging | `structlog` (JSON) | inspect a request after the fact; greppable | `loguru` if you prefer |
| Storage | Postgres 18 | relational truth for leads/state/approvals | — |
| Retrieval | Postgres full-text first, `pgvector` when semantic is justified | prove the simpler thing fails before adding vectors | Pinecone/Qdrant if scale demands |
| Orchestration | hand-rolled loop, then **LangGraph**; study **Temporal** | you must feel why checkpoints exist before a framework hides them | Temporal if you need long-running durable processes |
| API | FastAPI | typed request/response, async, OpenAPI for free | — |
| Tests | pytest (+ `pytest-asyncio`), `respx` for HTTP mocks | deterministic tests for a probabilistic system | — |
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

Decisions made on: ____ (date). Changes after this require a note in the log.
