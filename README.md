# Agentic Engineering — one system, eight upgrades, thirty days

[![ci](https://github.com/xshubhamg/agentic-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/xshubhamg/agentic-engineering/actions/workflows/ci.yml)

This repo is a 30-day build plan for agentic engineering. It is not eight demos.
It is one product — **Signal**, an AI sales research and outreach agent — that you
rebuild and harden eight times. Each stage adds one capability and one class of
failure you learn to handle.

```
P1 model call ──► P2 evidence ──► P3 tools ──► P4 state ──► P5 durability
                                                                  │
        P8 capstone ◄── P7 deploy ◄── P6 evaluation ◄─────────────┘
```

The point is not to finish fast. The point is that at the end you can explain,
for every layer, what it does, why it exists, and how it fails.

## The product

> A user enters a company (or a list of companies). Signal researches it,
> collects evidence, decides whether it fits the target customer profile,
> drafts a personalized outreach message, waits for human approval, then sends
> it — and can resume, retry, or refuse at any step.

Every stage keeps that same user story. Stage 1 answers from model knowledge.
Stage 8 answers from evidence, takes actions, survives restarts, and runs as a
monitored service.

## How to use this repo

| File | Purpose |
| --- | --- |
| `ROADMAP-30-DAYS.md` | Day-by-day plan with gates. Your default view. |
| `PROGRESS.md` | Single source of truth for what is done. Update daily. |
| `docs/00-end-goal.md` | What "done" actually means, and the rubric you grade yourself against. |
| `docs/01-glossary.md` | Precise definitions. If you cannot define a term, you do not know it. |
| `docs/02-stack.md` | Stack decisions with reasons and swap options. |
| `docs/03-engineering-log.md` | Daily log template. This becomes your portfolio narrative. |
| `projects/01…08/README.md` | Stage brief: goal, concepts, done criteria, failure drills. |

## Rules that make this work

1. **One repo, eight stages.** Do not start a new project folder to escape
   messy code. Refactor forward. The mess is the lesson.
2. **Commit at every gate.** Tag each stage `stage-1` … `stage-8`. The history
   is your proof of progression.
3. **Failure before feature.** Every stage has failure drills. If you have not
   broken it, you do not understand it.
4. **No framework before the primitive.** Do it by hand once (a loop, a retry,
   a checkpoint) before you let LangGraph or Temporal do it.
5. **Explain it out loud.** At each gate, write 5 sentences in the log as if
   explaining to a skeptical senior engineer. If you cannot, you are not done.
6. **Evidence over claims.** Every stage keeps artifacts in `evidence/`:
   traces, failing test output, screenshots, eval results.

## Getting started

```bash
cd ~/code/Projects/ai/agentic-engineering
cat docs/00-end-goal.md
sed -n '1,40p' ROADMAP-30-DAYS.md      # read Day 1 only

cd projects/01-model-app
cp ../../.env.example .env             # paste your OpenRouter key
uv sync
uv run signal ask "What does a healthy sales pipeline look like for a B2B SaaS company?"
```

The answer prints on stdout; one metadata line and one JSON log line print on
stderr. Then read `projects/01-model-app/CODE-TOUR.md` with the code open, and
work the failure drills — the scaffold is the starting point, not the assignment.

Do not read all eight briefs up front; the later ones will not make sense yet,
and that is fine.
