# Glossary

If you cannot explain a term to someone else in one sentence, plus one example
of how it breaks, you do not know it yet. Add to this file as you go — your own
definitions, not copied ones.

## Model interaction

**Context window** — the total tokens the model can see at once (system prompt +
history + documents + output). Exceeding it means truncation, not an error you
can ignore.
*Breaks when:* retrieved documents silently push out the system prompt.

**Token budget** — an explicit, enforced cap on tokens per request/task. Cost
control starts here, not in a dashboard.
*Breaks when:* an agent loop appends history forever and cost grows quadratically.

**Stop reason** — why generation ended (`end_turn`, `max_tokens`, `tool_use`,
refusal). Reading it is how you detect truncation instead of guessing.
*Breaks when:* you treat a `max_tokens` stop as a complete answer.

**Streaming** — receiving output incrementally. Matters for perceived latency;
complicates error handling because failures can arrive mid-stream.
*Breaks when:* the connection drops after you already rendered half an answer.

**Structured output** — constraining the model to a schema (tool/JSON schema).
Replaces "please respond in JSON" plus prayer.
*Breaks when:* you parse unvalidated JSON and trust the fields.

**Rate limit / backoff** — provider-imposed request caps; handle with
exponential backoff + jitter and a retry ceiling.
*Breaks when:* retries pile up and turn a 429 into an outage.

## Agents

**Agent loop** — model proposes → your code validates and executes → result is
appended → repeat until a stop condition, with a max-iteration guard.
*Breaks when:* no iteration cap, no cost cap, no exit condition.

**Tool (function) calling** — the model emits a structured request to run a
named function with arguments; your application decides whether and how to run it.
The model never executes anything.

**Tool schema** — the name, description, and argument schema you expose. The
description is prompt engineering; the schema is validation. Both matter.

**MCP (Model Context Protocol)** — a standard for exposing tools/resources to
AI clients so they are discoverable and reusable across applications, instead of
being hard-wired per app.

**Approval gate (HITL)** — a hard stop before an irreversible action, where a
human (or a deterministic policy) must authorize. Implemented as a state the
workflow waits in, not a `print("approve?")`.

**Prompt injection** — untrusted content (a web page, an email) containing
instructions the model may follow. Retrieved text is *data*, never instructions.
*Breaks when:* you paste scraped content into the system prompt, or let a tool
take its arguments from page text.

**Least privilege** — every tool gets the narrowest scope that does the job
(send to one approved recipient, not "send email"), and credentials are scoped
per tenant.

## Retrieval and evidence

**RAG** — retrieve relevant passages, put them in context, generate from them.
Retrieval quality bounds answer quality; a better model cannot fix bad evidence.

**Chunking** — splitting documents into retrievable units. Chunk size and
overlap determine what can be found and what context survives the cut.

**Embedding / semantic search** — vector similarity for meaning-based matching.
Good for paraphrase, bad for exact identifiers, dates, and negation.

**Hybrid search** — combine keyword (BM25/full-text) with vector, then fuse.
Usually beats either alone, and is the honest default.

**Reranking** — a second, more precise pass over top-N candidates. Cheap way to
buy precision.

**Grounding** — every factual claim traceable to a specific retrieved passage.
Not "the answer sounds right".

**Citation** — a machine-checkable pointer (source URL + passage id + timestamp)
attached to a claim, verifiable *after* generation.

**Insufficient evidence** — a first-class outcome. The system must be able to
refuse, and you must test that it does.

## State and durability

**Business state** — the durable facts (leads, evidence, decisions, approvals).
Lives in Postgres. Not in the model's context.

**Memory** — what the agent recalls between sessions. A view over business state,
not a separate magic store. Vector search is a retrieval mechanism, not memory.

**Checkpoint** — a persisted snapshot of workflow position and accumulated
state, so execution can resume after a crash.

**Idempotency** — retrying an action does not duplicate its effect (send the
email once even if the step runs twice). Requires an idempotency key on the side
effect, not just on the retry logic.

**Durable execution** — a runtime (Temporal-style) that replays history so
in-progress work survives process death, deploys, and long waits.

**At-least-once vs exactly-once** — distributed systems give you at-least-once
delivery; exactly-once *effects* are something you engineer with idempotency.

## Evaluation and operations

**Golden set** — a fixed, versioned dataset of cases with expected outcomes:
easy, ambiguous, insufficient evidence, conflicting sources, hostile input.

**Eval harness** — code that runs the system over the golden set and reports
pass/fail per capability with reproducible output.

**LLM-as-judge** — using a model to grade outputs. Useful for fuzzy qualities
(citation support, tone); must be calibrated against human labels, and never the
only signal.

**Regression gate** — a CI check that fails the build when eval scores drop
below baseline.

**Trace / span** — a trace is one end-to-end request; spans are its nested
operations (retrieval, model call, tool call) with duration, tokens, cost, errors.

**SLO** — a target you promise (p95 latency < 8s, error rate < 1%) with an error
budget. Monitoring exists to tell you when you are spending it.

**Tenant isolation** — one customer's data cannot appear in another's request,
tool call, vector search, or log. Tested, not assumed.

**Budget cap** — a hard per-task and per-tenant ceiling on tokens/spend that
terminates the run rather than billing the user.
