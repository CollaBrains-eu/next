# ADR 0015: Phase 6d — Load Testing & Capacity Documentation

## Status
Accepted

## Context
Final slice of Phase 6 (production readiness, split per ADR 0012). This
host is CPU-only (8 vCPU / 24GB RAM, OpenVZ) for Ollama inference —
`qwen2.5:3b-instruct` for chat/legal-draft/task-extraction/entity-
extraction, `nomic-embed-text` for embeddings. "Production ready" here
does not mean hitting some specific throughput number that was never a
stated requirement — nobody has asked this platform to serve thousands
of concurrent users, and pretending otherwise would just produce a
number that doesn't answer any real question. What it does mean: know
and write down the actual ceiling, so a real decision (more concurrent
users than expected, whether to move to a GPU host) can be made from
data instead of a guess.

## Decisions

**No load-testing framework.** k6/Locust/JMeter are the standard answer,
but they're built for testing throughput at a scale (hundreds to
thousands of virtual users) this deployment will never see, and adding
one would mean learning/maintaining a whole tool for a handful of
capacity data points. A short Python `asyncio`+`httpx` script
(`infra/loadtest/loadtest.py` — `httpx` is already a dependency of
`services/api`) that fires N concurrent requests and reports latency
percentiles is enough, same "no infra beyond what's needed" reasoning as
every other phase in this project.

**What gets tested**: `POST /chat` (the realistic worst case —
retrieval + a full LLM generation) and `GET /search` (DB-only, no LLM,
included as a baseline to show the AI Gateway is the actual bottleneck,
not the database or network) at increasing concurrency (1, 2, 4, 8
simultaneous requests). Each level uses distinct pre-provisioned test
users so the per-user rate limiter (30/min, Phase 2a) doesn't distort
the results — this test measures the AI Gateway/Ollama's real ceiling,
not the rate limiter's configured one, which is a separate and already
deliberate limit.

**What "capacity" means for this specific question**: Ollama's own
concurrent-request behavior (`OLLAMA_NUM_PARALLEL`) was never explicitly
configured — it's running on whatever this Ollama version's computed
default is on this hardware, which is itself useful information to
surface empirically rather than assume. The test reports raw numbers
(p50/p95/max latency, error rate per concurrency level) and a plain-
language capacity statement in `docs/runbooks/capacity.md`, not a
synthetic score.

**Test data cleanup**: any users/documents created purely to run this
test are deleted afterward, same as every other phase's live-testing
cleanup discipline (Phase 4's entity-graph tests, Phase 5a's upload
test, etc.) — this is a one-time capacity measurement, not a permanent
fixture, and the shared dev database shouldn't accumulate load-test
debris.

## Why not more in 6d
No automated regression testing of capacity over time (e.g., re-running
this on every deploy and failing a threshold) — this is a one-time
"what does this host actually support" question for a single-VM
deployment with one real operator, not a CI gate. If this becomes a
recurring need (e.g., after a hardware change), the script here is
reusable as-is; a scheduled/automated version would be a separate,
later decision once there's an actual reason to want one.
