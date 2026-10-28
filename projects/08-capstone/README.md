# Stage 8 — Capstone: ship Signal

Days 24–30 · `stage-8` tag · Gate: one repo a stranger can run and a demo you can
defend

## End goal

One repository that does the whole thing: a list of companies in, evidence-backed
qualification and personalized outreach out, human approval before any send,
resumable after failure, measured by an eval suite, deployed and monitored.

Not a demo. A small, honest, working system with its seams visible.

## Why this stage exists

Stages 1–7 each optimized one axis and left scar tissue. This stage is the
refactor that turns seven layers into one coherent product — and the write-up
that makes the work legible to someone who was not there.

## Build

1. **Consolidate.** One entrypoint, one config, one client wrapper, one tool
   registry, one workflow definition, one eval command. Delete dead ends; the git
   tags keep the history. Refactor, do not rewrite.
2. **End-to-end.** 5 companies → research → evidence → qualify → draft →
   approve → send. Every decision row links to the evidence rows that justify it.
3. **README as a product.** What it does, architecture diagram, the 8 stages as a
   short narrative, setup in under 10 commands, sample `.env`, eval results
   table, known limitations, what you would do next. Honest limitations are more
   impressive than claims.
4. **Evidence pack.** Three annotated traces: success, recovered failure, blocked
   unauthorized action. Each with 3 sentences on what it proves.
5. **Demo.** 5 minutes: the happy path, the refusal, the blocked injection, the
   crash-resume. No slides needed.
6. **Gate re-run.** Full eval, all stages' definitions of done re-checked, costs
   recorded.

## Definition of done

- [ ] one repo, one command to run locally, one command to run the eval
- [ ] all 8 stage gates re-verified against the consolidated code
- [ ] README: architecture, setup ≤10 commands, eval table, limitations, next steps
- [ ] 3 evidence traces, annotated, in `evidence/`
- [ ] 5-minute demo recorded or live
- [ ] eval baseline published with p95 latency, cost per run, pass rate per capability
- [ ] deployed and monitored, with the incident runbook linked
- [ ] retrospective in the log: keep / rebuild / still cannot explain

## The portfolio story (write this in the README)

A short paragraph per stage: the limitation, the change, the failure you handled,
the evidence. Six lines total. This is what turns a repo into a narrative:

1. Started with one SDK call — learned stop reasons, tokens, retries, truncation.
2. Added retrieval and citations — learned that evidence quality bounds answers.
3. Added tools with a policy layer — learned the model proposes, code authorizes.
4. Added Postgres state — learned that memory is rows, not context.
5. Added durable workflow with approval gates — learned idempotency and resume.
6. Added a golden set and traces — learned to prove it instead of assert it.
7. Deployed with auth, limits, alerts — learned to operate what I built.
8. Consolidated into one system — learned to make it legible.

## What graders and interviewers actually ask

- "Show me a case where the agent refused, and why that was correct."
- "How do you know a citation supports the claim?"
- "What happens if the send step runs twice?"
- "Where could a prompt injection get through?"
- "What is your p95 latency, and which span dominates it?"
- "What did the framework do for you, and what did you have to understand anyway?"

Have a concrete answer for each, with a trace or a test to point at.

## Stretch (post-30-days, not before)

- a thin UI for the approval queue
- multi-agent (researcher + writer) only if a single agent measurably fails
- fine-tuned classifier for qualification, compared against the prompt baseline
