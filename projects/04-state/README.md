# Stage 4 — State and memory

Days 11–12 · `stage-4` tag · Gate: kill the process mid-run and continue where
it stopped

## End goal

The agent remembers what happened yesterday because it is written down in
Postgres — not because it is in a context window. Restart the process and it
knows which leads were researched, which messages were approved, and what is
still pending.

## Why now

You cannot trust an agent that forgets. And you cannot debug one either. This
stage also fixes a common confusion: vector search is a retrieval mechanism, not
memory. Memory is a query over durable business rows.

## Build

1. **Schema.** `company`, `lead`, `evidence`, `decision`, `message`, `approval`,
   `run`, `run_step`. Foreign keys, timestamps, one migration tool (Alembic or
   plain SQL files with a version table).
2. **Transactions.** A decision and the evidence it cites are written together or
   not at all. Approval and the message it authorizes are written together.
3. **Typed boundaries.** Pydantic models for everything crossing a module
   boundary; the DB row is not your API contract.
4. **Memory as queries.** "What did I do last time for this lead?" = select from
   `run_step` / `message` / `approval`. Add vector search only if a semantic
   recall need appears — and label it retrieval, not memory.
5. **Session context builder.** Before each model call, assemble context from
   rows: recent interactions for this lead, prior decisions, pending approvals.
   Cap it; state lives in the DB, context is a projection of it.
6. **Crash test.** Hard-kill between drafting and sending. On restart, resume
   must skip completed steps and not double-write.

## Concepts you must be able to explain

- business state vs agent memory vs model context — three different things
- why "the context window is the state" fails across sessions and across crashes
- idempotent writes and why a retry after a crash is the normal case, not the edge case
- transactions and what invariant each one protects
- migrations: why a schema you cannot evolve is a schema you cannot ship
- why a `run` row with an explicit step is worth more than a clever prompt

## Definition of done

- [ ] schema with migrations, applied from scratch on a clean DB in one command
- [ ] a run is resumable: kill -9 mid-run, restart, it continues at the right step
- [ ] re-running a completed step does not duplicate messages or decisions
- [ ] context for a model call is built from rows, with an explicit size cap
- [ ] at least one test proves transaction rollback leaves no partial state
- [ ] `evidence/` has the before/after of a crash-restart run

## Failure drills

| Drill | How | Expected |
| --- | --- | --- |
| Kill mid-run | `kill -9` after draft, before send | restart resumes at approval/send, no duplicate draft |
| Double delivery | call the resume endpoint twice | second call is a no-op, or idempotent |
| Partial write | force an exception after the decision insert | transaction rolls back both rows |
| Context bloat | 200 prior interactions for one lead | context builder truncates by relevance, cost stays bounded |
| Stale lock | simulate a worker that died holding a lock | run is recoverable, not permanently stuck |

## Evidence to keep

- schema diagram
- crash-restart log excerpt
- one transaction rollback test output

## Stretch

- background worker with a simple job queue (Postgres `SKIP LOCKED` is enough)
- retention policy for old runs
- per-tenant constraints enforced at the DB level, not only in code
