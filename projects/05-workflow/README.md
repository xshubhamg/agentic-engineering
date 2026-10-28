# Stage 5 — Durable workflow

Days 13–15 · `stage-5` tag · Gate: pause for approval, crash, resume, no duplicate
side effects

## End goal

A workflow that can pause for a human, survive a deploy, retry a failed step, and
still send exactly one email. Steps: research → qualify → draft → await approval →
send. Each step has a timeout, a retry policy, and a recorded outcome.

## Why now

A sequence of function calls is not a workflow. The moment you add branching,
human interruption, retries, and recovery, you need explicit state transitions —
and you need to have felt that need before a framework hides it from you.

## Build

1. **Hand-rolled first (Day 13).** `runs` and `run_steps` with `state`,
   `attempt`, `deadline`, `output`. A runner that advances one step at a time and
   can be re-entered at any point. This is the version you must be able to explain.
2. **Gate the irreversible action.** `awaiting_approval` is a real state with an
   expiry. Approval transitions it; timeout escalates or cancels. No approval
   token, no send.
3. **Retries with a policy.** Per-step: max attempts, backoff, which errors are
   retryable. Distinguish transient (5xx, timeout) from permanent (validation,
   policy denial) — retrying a policy denial is a bug that looks like resilience.
4. **Idempotency everywhere it matters.** A key per side effect (e.g.
   `run_id:step:message_id`) recorded before the send, checked before the retry.
5. **Port to LangGraph (Day 14).** Same behavior, checkpointed. Write a
   comparison in the log: what the framework gave you (checkpointer, interrupts,
   graph visualization) and what it hid (retry semantics, state versioning).
   Study Temporal's model (workflow vs activity, deterministic replay, signals)
   even if you do not run it — it is the mental model for durable execution.
6. **Chaos day (Day 15).** Deploy mid-run, cancel mid-run, duplicate webhook,
   approval after expiry, provider outage across two retries.

## Concepts you must be able to explain

- checkpoint vs transaction vs log: which problem each solves
- why resuming requires deterministic replay or explicit step records — pick one and justify it
- at-least-once delivery and how idempotency keys give exactly-once *effects*
- approval expiry as a state machine, not an `if` in a route handler
- why retrying a permanent error makes systems less reliable
- what a workflow engine buys you versus a `runs` table (be honest: for one
  workflow, not much; for many, a lot)

## Definition of done

- [ ] every run is a row; every step transition is persisted with timestamp and attempt
- [ ] approval gate blocks the send; expiry is handled explicitly
- [ ] kill the worker at any step → resume completes the run exactly once
- [ ] permanent errors are not retried; transient ones are, with a ceiling
- [ ] one duplicate-send drill proves idempotency (send count stays 1)
- [ ] LangGraph version reaches feature parity with the hand-rolled one
- [ ] comparison of the two written in the log (5 bullets, no marketing)

## Failure drills

| Drill | How | Expected |
| --- | --- | --- |
| Deploy mid-run | restart the service while `awaiting_approval` | run survives, resumes, approval still valid |
| Duplicate webhook | replay the approval event twice | one send, second is a no-op |
| Approval after expiry | approve an expired run | rejected with a clear reason, no send |
| Provider outage | mock 500 ×3 on the send step | retries with backoff, respects ceiling, then terminal failure + alert |
| Cancel | user cancels while drafting | run reaches `cancelled`, no side effects after |
| Orphan worker | worker dies holding a claim | run becomes claimable again after lease expiry |

## Evidence to keep

- state diagram of the run lifecycle
- trace/log of a pause → crash → resume → single send
- LangGraph vs hand-rolled comparison table

## Stretch

- a real Temporal implementation of the same workflow, side by side
- compensation steps (undo a partial action)
- run-level cost budget enforced by the workflow, not the client
