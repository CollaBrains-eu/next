# Runbook: Capacity & Load Test Results

Measured 2026-07-03 against the live production stack on
`v78281.1blu.de` (8 vCPU / 24GB RAM, OpenVZ, CPU-only — no GPU). Run
with `infra/loadtest/loadtest.py` (see ADR 0015 for why this script and
not a load-testing framework). Re-run the same way after any hardware
change or before raising expected concurrent-user counts.

## Results

`/search` (Postgres hybrid search, no LLM — baseline):

| concurrency | p50   | p95   | max   | errors |
|-------------|-------|-------|-------|--------|
| 1           | 0.59s | 0.59s | 0.59s | 0      |
| 2           | 0.10s | 0.10s | 0.10s | 0      |
| 4           | 0.25s | 0.29s | 0.29s | 0      |
| 8           | 0.43s | 0.54s | 0.54s | 0      |

`/chat` (retrieval + `qwen2.5:3b-instruct` generation):

| concurrency | p50    | p95    | max    | errors |
|-------------|--------|--------|--------|--------|
| 1           | 27.03s | 27.03s | 27.03s | 0      |
| 2           | 8.27s  | 8.27s  | 8.27s  | 0      |
| 4           | 22.91s | 26.33s | 26.33s | 0      |
| 8           | 55.05s | 84.36s | 84.36s | 0      |

(The concurrency=1 result includes model cold-load time — Ollama's
`OLLAMA_KEEP_ALIVE` unloads an idle model after 5 minutes, and this was
the first chat request of the run. Treat 6-9s as the realistic
already-warm single-request latency, per the concurrency=2 result,
not the 27s figure.)

## What this means

**The database and search layer are not the bottleneck.** `/search`
stays well under a second even at 8 simultaneous requests — Postgres
hybrid search (tsvector + pgvector HNSW, ADR 0002) has substantial
headroom left on this host.

**Ollama is the ceiling, and it fully serializes generation requests on
this host.** Confirmed directly in the Ollama server startup log:
`OLLAMA_NUM_PARALLEL:1` — this is Ollama's own computed default here,
never explicitly configured either way. With `NUM_PARALLEL=1`, N
concurrent chat requests don't run in parallel at all; they queue and
run one at a time, so total wall-clock time for a batch is
approximately N × (single-request latency), which is exactly the
pattern in the numbers above (p50 roughly doubles from concurrency=4 to
concurrency=8, and the max/p95 gap widens sharply — later requests in
the queue wait for everyone ahead of them). This is also consistent
with `docker stats` showing Ollama at **752% CPU** (of 800% available on
this 8-vCPU host) during the concurrency=8 run — a single generation
already uses nearly the whole machine, which is also *why*
`NUM_PARALLEL=1` is probably the right default here: raising it would
mean multiple generations competing for the same nearly-saturated CPU
pool, likely making every individual request slower rather than
increasing real throughput. This wasn't tested directly (see "Not
covered" below) — it's the load-bearing reason not to reach for
`OLLAMA_NUM_PARALLEL=2` as a quick fix without first confirming it
actually helps rather than just redistributing the same bottleneck.

## Practical capacity guidance

- **1-2 people using chat/legal-draft/task-extraction at the exact same
  moment**: acceptable — worst case around the concurrency=2 numbers
  (single digit seconds once the model is warm).
- **4 people at once**: still works, but each of them waits ~20-25
  seconds for a reply — noticeable but tolerable for occasional
  overlap.
- **8 people at once**: real degradation — worst-case wait climbs to
  84 seconds. This is the point where "production ready" starts to mean
  "usable, not comfortable" for this specific host.
- Search, document upload, and browsing the document library are
  unaffected by chat/draft load — those paths don't touch Ollama's
  generation queue at all (only the embedding call during
  upload/OCR does, which is far cheaper than generation).

If concurrent chat/draft usage regularly exceeds ~4 people at once, the
options are (in order of how much they actually address the bottleneck
identified above): move Ollama to a host with a GPU (the `ollama-gpu`
Compose profile already exists for this, unused today for lack of GPU
hardware — see `docker-compose.yml`), or reduce per-request cost — e.g.
lowering `ai_max_context_chunks` — as a smaller, immediate lever if a
GPU host isn't available yet.

## Not covered by this test

- Whether raising `OLLAMA_NUM_PARALLEL` actually improves *throughput*
  (as opposed to just changing how the same CPU-bound work is
  scheduled) — the CPU-saturation evidence above is a strong signal it
  wouldn't help without more cores, but wasn't tested directly since
  changing that setting requires a container restart the ADR judged
  wasn't worth doing for a one-time capacity measurement (this is a
  natural first experiment for whoever picks this back up if concurrent
  load becomes a real, not hypothetical, problem).
- Signal-bot-driven load (the bot forwards to the same `/chat` endpoint,
  so the numbers above apply, but weren't tested via that specific
  path).
- Sustained/soak load over time (this test is a snapshot, not a
  duration test) — not relevant yet for a single-operator deployment.
