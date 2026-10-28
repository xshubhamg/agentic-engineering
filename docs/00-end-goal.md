# The end goal

Read this once at the start, then again at every stage gate.

## What you are actually learning

Not "how to use an LLM API". Not "how to use LangGraph". The skill is
**composition under uncertainty**: a model is a probabilistic component inside a
deterministic system, and your job is to make the whole system dependable anyway.

That means four things, and every stage trains one of them:

| Axis | The question you must answer | Stages that train it |
| --- | --- | --- |
| Grounding | Is the output supported by evidence I can inspect? | 2, 6, 8 |
| Control | Who decides what the system is allowed to do? | 3, 5, 7 |
| Durability | What survives a crash, a timeout, a restart, a retry? | 1, 4, 5, 7 |
| Measurability | How do I know it got better, and at what cost? | 6, 7, 8 |

## What "done" means at the end of 30 days

You can sit someone down and demonstrate, on one running system:

1. A grounded answer with citations that resolve to real retrieved passages,
   including a case where the system correctly says "I don't have enough
   evidence".
2. A tool call that is proposed by the model, validated by your code, and
   blocked when it violates policy (no approval, wrong tenant, injected
   instruction).
3. A workflow that is paused waiting for approval, and resumes after a process
   restart at exactly the right step without repeating side effects.
4. An eval run that prints pass/fail per capability, with a baseline number and
   a delta from the previous stage.
5. A trace of one request showing model spans, retrieval spans, tool spans,
   tokens, latency, and cost.
6. A deployed service with auth, rate limits, budget caps, CI on push, and a
   documented incident playbook.
7. A README a stranger can follow to run it, plus 3 traces in `evidence/`:
   one success, one recovered failure, one blocked unauthorized action.

If you have those seven, you have a portfolio project that is genuinely rare.

## The rubric (grade yourself, 1–5 per row)

| Capability | 3 — working | 4 — defensible | 5 — production-shaped |
| --- | --- | --- | --- |
| Model integration | answers questions | handles timeouts, rate limits, truncation | cost/latency budgets, fallbacks |
| Retrieval | gets relevant text | citations, recency, "insufficient evidence" | measured recall/precision on a golden set |
| Tools | calls functions | argument validation + policy checks | injection-resistant, least-privilege, audited |
| State | persists rows | survives restart, resumable | idempotent side effects, migrations |
| Workflow | linear steps | retries, interrupts, approval gates | durable, observable, timeouts per step |
| Evaluation | manual checks | automated golden set, pass/fail | regression gate in CI, cost tracked |
| Production | runs locally | containerized, CI, auth | monitoring, budgets, runbook |

Aim for 4 on everything, 5 on two things that matter most to you. Chasing 5
everywhere in 30 days is how people end up with eight abandoned demos.

## Anti-goals — things that will waste your month

- Learning five agent frameworks. One is enough; the concepts transfer.
- Building a UI before the engine works.
- Adding a vector database because it is on the roadmap, when your corpus is
  small enough for Postgres full-text search.
- Optimizing cost before you can measure cost.
- Writing an eval that only tests the happy path.
- Rewriting from scratch at stage 5 because the code is ugly. Refactor instead.
- Kubernetes, Kafka, microservices. The brief asks for the simplest
  architecture that satisfies reliability, security, and scale.

## Time budget reality

Thirty days at ~2–3 focused hours on weekdays and one longer weekend block.
If you are behind, cut the *stretch* items in each stage brief, never the
definition of done. If you are more than two days behind by Day 15, drop stage 8
polish, not stage 6 (evaluation) — evaluation is the stage that makes everything
else credible.
