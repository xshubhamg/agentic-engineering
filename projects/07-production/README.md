# Stage 7 — Production service

Days 20–23 · `stage-7` tag · Gate: deployed, authenticated, budget-capped,
monitored, and boring to operate

## End goal

Signal runs as a service real users could touch: an HTTP API with auth and tenant
isolation, containers, CI/CD, SLOs with alerts, hard budget caps, and a runbook
you have actually used once.

## Why now

Everything so far assumed a trusted single user on your laptop. Production is a
different threat model, not a different product.

## Build

1. **API.** `POST /runs` (create), `GET /runs/{id}` (status + evidence),
   `POST /runs/{id}/approve`, `GET /health`. Async where it helps, sync where it
   does not. Idempotency key on create.
2. **AuthN/AuthZ.** Tokens or sessions, tenant resolved from the credential and
   never from the request body. Every query scoped by tenant at the data layer.
   Separate the approver role from the requester role.
3. **Limits.** Per-tenant rate limit, per-run token budget, per-tenant daily
   spend cap, max runtime per run, max input size. Enforced in code with a typed
   "budget exceeded" outcome, plus a metric.
4. **Secrets.** Env injected by the platform; no defaults; rotated once to prove
   the process works.
5. **Container.** Multi-stage build, non-root user, health check, no dev deps,
   one command (compose) to bring up app + Postgres locally.
6. **CI/CD.** Lint → typecheck → unit → integration → eval gate → build → deploy.
   A red eval blocks the deploy.
7. **Observability.** p95 latency, error rate, cost per run, queue depth,
   approval wait time. Alert on each with a threshold you can justify. Sentry or
   structured error logs with trace ids.
8. **Runbook + drill.** Three most likely incidents, each with detection, triage,
   mitigation, rollback. Then break one for real (kill DB connections, exhaust a
   budget, revoke a token) and follow your own runbook.

## Concepts you must be able to explain

- why tenant id must come from the credential, never the payload
- authN vs authZ here, and why the approver is a different role
- why a budget cap must be enforced server-side and per tenant
- what an SLO is, what an error budget is, and what you do when it is spent
- the difference between graceful degradation and silent failure (fallback model,
  cached evidence — and when each is dishonest)
- why the simplest deployable architecture wins over a sophisticated one you cannot operate

## Definition of done

- [ ] deployed and reachable over HTTPS with auth; unauthenticated calls rejected
- [ ] cross-tenant access attempt fails in a test and in the live service
- [ ] budget/rate/time limits enforced, with a metric for each trigger
- [ ] Docker build reproducible; local `compose up` gives a working stack in one command
- [ ] CI blocks merge on failing eval; deploy is automated from main
- [ ] dashboard or alert covers p95 latency, error rate, cost per run
- [ ] runbook written and used once during a real drill
- [ ] secrets only from the platform store; no key in image, repo, or logs

## Failure drills

| Drill | How | Expected |
| --- | --- | --- |
| DB down | stop Postgres | 503 with retry-after, health check red, alert fires |
| Budget exhaustion | set a $0.01 tenant cap | run terminates with a typed budget error, no partial send |
| Token revoked | rotate the API key | clean 401 path, no crash loop, alert |
| Tenant probe | request another tenant's run id | 404/403, no existence leak, audit row |
| Latency regression | add 2s to retrieval | p95 alert fires before a user complains |
| Model provider outage | block the provider host | retries then graceful failure; no duplicate sends on recovery |

## Evidence to keep

- the deployed URL (or a screenshot of it running) and an auth-rejected response
- a CI run that blocked a bad deploy
- the incident drill: alert, timeline, what the runbook said, what you changed

## Stretch

- canary or blue/green deploy for the worker
- per-tenant cost report
- load test at 10× expected traffic, with the first bottleneck identified
