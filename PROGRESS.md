# Progress

Update this file at the end of every session. It is the only place that says what
is actually done.

## Stage tracker

| # | Stage | Days | Status | Gate date | Score /5 | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | Model-powered application | 1–3 | in progress | | | scaffolded, awaiting first live run |
| 2 | Evidence and retrieval | 4–7 | not started | | | |
| 3 | Tools and permissions | 8–10 | not started | | | |
| 4 | State and memory | 11–12 | not started | | | |
| 5 | Durable workflow | 13–15 | not started | | | |
| 6 | Evaluation and observability | 16–19 | not started | | | |
| 7 | Production service | 20–23 | not started | | | |
| 8 | Capstone | 24–28 | not started | | | |

Status values: `not started` · `in progress` · `blocked` · `gate passed`.

## Current focus

- Stage: 1 — model-powered application
- Day of plan: Day 1
- The one thing I am stuck on: nothing yet; run the drills
- Next single action: copy `.env.example` to `projects/01-model-app/.env`, paste the
  OpenRouter key, run `uv run signal ask "…"`

## Eval baseline history

Numbers only move forward if you measure them. Fill each row when the stage gate
passes; leave earlier rows untouched so you can show the trend.

| After stage | Golden cases | Answer correct | Citation supported | Refused correctly | Unsafe action blocked | p95 latency | Cost / run |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2 | 15 | | | | n/a | | |
| 3 | 20 | | | | | | |
| 5 | 25 | | | | | | |
| 6 | 30 | | | | | | |
| 8 | 30 | | | | | | |

## Gate log

Append a line per gate: date, pass/fail, the single biggest thing you learned,
and the link to evidence.

- _YYYY-MM-DD_ · Stage 1 · pass · …

## Parked ideas

Things you deliberately chose not to build (write them here so they stop
distracting you):

- UI — after stage 8, not before
- multi-agent orchestration — only if a single agent demonstrably fails
- fine-tuning — not before eval exists
