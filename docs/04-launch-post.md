# Launch post — announcing the 30-day build

Repo: https://github.com/xshubhamg/agentic-engineering (public, CI green)

Three assets: a LinkedIn/X post, an infographic prompt, and fallbacks for when the
image generator cannot spell. Update the status line as you pass gates; do not
announce stages you have not built.

---

## Post (LinkedIn / long form)

Most people learning AI in 2026 collect tools. I'm trying to collect systems.

The trap is easy to fall into: learn LangGraph, learn pgvector, learn MCP, learn
Temporal — and still freeze when someone asks "what happens if the send step runs
twice?" or "how do you know that citation actually supports the claim?"

Tools don't answer those questions. Architecture does.

So for the next 30 days I'm building one system — not eight demos — and improving
it eight times. It's a sales research agent that has to earn each capability:

1. A model call you can trust — retries, timeouts, truncation, real cost
2. Evidence and citations — including the discipline to say "not enough evidence"
3. Tools with permissions — the model proposes, my code authorizes
4. Durable state — memory is rows in Postgres, not a context window
5. A durable workflow — pause for approval, crash, resume, send exactly once
6. Evals and traces — prove it works instead of asserting it
7. Production — auth, budget caps, monitoring, a runbook I've actually used
8. One consolidated repo worth showing

Same product every time. Each stage adds one capability and one class of failure
I have to handle.

Day 1 is done. First live call through OpenRouter, and behind it: typed errors
instead of one generic exception, jittered retries I can log and test, truncation
treated as a correctness failure rather than a formatting detail, and cost read
from the response instead of a hardcoded price table. 23 tests, none of which
touch the network.

The rule I'm holding myself to: no framework before the primitive. Hand-roll the
loop, feel exactly why it breaks, then let a framework hide it.

I'll post each gate as I pass it — including the ones I fail. If you're on a
similar path, build along: I'll share the repo structure, the eval numbers, and
the traces.

What should I break first, the retry logic or the approval gate?

#AgenticAI #AIEngineering #BuildInPublic #LLM #SoftwareEngineering

---

## Post (X / thread)

**1/**
Most people learning AI in 2026 collect tools. I'm collecting systems.

For 30 days I'm building ONE agent — not 8 demos — and improving it 8 times. It
has to earn each capability. Day 1 done. 🧵

**2/**
The 8 upgrades:
1. one model call you can trust
2. evidence + citations, or refuse
3. tools: propose ≠ permit
4. state: memory is rows, not context
5. workflow: pause, crash, resume, send once
6. evals: prove it
7. production: auth, budgets, alerts
8. one repo worth showing

**3/**
Rule: no framework before the primitive.

Hand-roll the retry loop. Watch a truncated answer look complete. Then let
LangGraph hide it — and be able to explain what it hid.

**4/**
Day 1: first live call, 23 tests, zero network in them.

Typed errors, jittered retries, truncation as a correctness bug, cost from the
response (not a stale price table).

**5/**
I'll post every gate, including the failures.

What should I break first: the retry logic, or the approval gate?

#AgenticAI #BuildInPublic

---

## Infographic prompt

Use a text-capable generator (Ideogram, Recraft, Canva Magic Media). Image models
still garble dense text — check every word before posting.

```
Design a 4:5 vertical infographic, 1080x1350, flat vector, no photography.

PURPOSE
Announce a 30-day build-in-public series: one AI agent, eight upgrades.
The visual must communicate "one system evolving", NOT "eight separate projects".

LAYOUT
- Top 20%: title block on a dark panel.
- Middle 66%: a single vertical spine running top to bottom with 8 nodes
  attached to it, alternating slightly left and right. One continuous line,
  like a circuit trace or a subway line. Numbered 01 to 08 top to bottom.
- Bottom 14%: a one-line footer with a small underline rule above it.

EXACT TEXT — render verbatim, no extra words, correct spelling
Title: ONE SYSTEM
Subtitle: EIGHT UPGRADES · 30 DAYS
Kicker (small, above title): AGENTIC ENGINEERING, BUILT IN PUBLIC

Node labels (big) with one short detail line (small):
01  MODEL CALL       retries · timeouts · cost
02  EVIDENCE         cite it or refuse
03  TOOLS            propose ≠ permit
04  STATE            memory is rows
05  WORKFLOW         pause · crash · resume
06  EVALS            prove, don't assert
07  PRODUCTION       auth · budgets · alerts
08  CAPSTONE         one repo, one demo

Footer: Signal — a sales research agent that earns each capability
Corner, small mono: DAY 01 / 30

STYLE
- Background #0E1116, node cards #161A22, primary text #F2F4F8
- Accent #F5A524 for the active node (01) and the spine; secondary #4FD1C5
- Monospace for numbers and the day counter; geometric sans for labels
- Left-aligned text inside each card, generous whitespace, 8px grid
- Node 01 visually highlighted, 02-08 slightly dimmed
- Crisp 2px strokes, no shadows, no gradients, no 3D, no glow

CONSTRAINTS
- All text exactly as written above; no lorem ipsum, no invented words
- No stock photos, no robots, no humanoid figures, no brain icons, no glowing orbs
- Must stay legible when scaled to a 400px-wide thumbnail
- Leave 64px safe margins
```

**Negative prompt:** `photorealistic, 3d render, neon glow, purple gradient, robot,
brain, humanoid, circuit board photo, cluttered, tiny unreadable text, lorem ipsum,
watermark, drop shadow, clip art`

**Formats:** 1080×1350 for LinkedIn/Instagram; re-export 1200×675 (16:9) for X by
moving the spine horizontal and keeping the same copy.

---

## If the generator can't spell

Midjourney and many diffusion models will mangle 40+ words. Two honest options:

1. **Generate the layout, add text yourself.** Prompt for "abstract vertical
   timeline, 8 nodes, dark UI style, no text" and set the copy in Canva or Figma.
2. **Build it in HTML/CSS and screenshot it.** 120 lines of flexbox beats an hour
   of rerolling. Ask me and I'll write it — it also gives you a version you can
   re-render for every stage gate (just change the highlighted node).

---

## Alt text

> Dark infographic titled "One System — Eight Upgrades, 30 Days". A single vertical
> line connects eight numbered stages: model call, evidence, tools, state,
> workflow, evals, production, capstone. Stage 1, model call, is highlighted with
> the note "retries, timeouts, cost". Footer reads: "Signal — a sales research
> agent that earns each capability."

---

## Before you post

- [ ] Replace `DAY 01 / 30` with the real day
- [ ] Confirm the test count and the milestone claim are still true
- [ ] Check spelling of every tool name you mention (LangGraph, pgvector, Temporal)
- [x] Repo is public: https://github.com/xshubhamg/agentic-engineering
- [ ] Have a reply ready for "which model?" — answer: `deepseek/deepseek-v4.1-flash`
      via OpenRouter, chosen for cost and tool-calling support, not hype
