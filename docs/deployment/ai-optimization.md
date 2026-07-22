# AI / resource optimization for the 4-vCPU/8GB CPU-only host

## Why

`v45264.1blu.de` (`178.254.22.178`), the current production host (see the
2026-07-22 server-migration note in project memory), is a 4-vCPU/8GB
CPU-only **OpenVZ** container -- noticeably smaller than the old, now-dead
host it replaced (8 vCPU/24GB). At the point this work started, `docker
stats` showed `collabrains-ollama-1` alone using **5.76GB / 8GB RAM and
377% CPU** (nearly all 4 cores) while serving `qwen3:8b` (5.2GB) with no
resource limits configured anywhere -- an active resource crisis, not a
theoretical risk. `free -h` showed 64MB free RAM at the time.

## What was tried and didn't work: swap

OpenVZ guests cannot create swap devices at all -- confirmed directly:
`swapon /swapfile` fails with `Operation not permitted` even after a
successful `mkswap`. This is the same class of host-level restriction
already documented for the old server (`vm.max_map_count` couldn't be
raised for Elasticsearch there either). **Do not spend time re-attempting
swap on this host or its replacement unless the hosting/virtualization
setup changes.** `deploy_collabrains.sh` still attempts it (harmless,
some future host might support it) but expects it to fail here and falls
back to Compose `mem_limit`s as the actual safety net: a container that
balloons gets OOM-killed and restarted (`restart: unless-stopped`) instead
of taking the whole host down.

## What changed

### 1. Ollama resource limits (Docker Compose, not systemd)

This app runs Ollama as a Compose service (`docker-compose.yml`, `full`
profile), not a bare-metal systemd unit -- there is no systemd override
file for it. Limits are on the `ollama` service block instead:

```yaml
mem_limit: 1536m
mem_reservation: 512m
cpus: "3.0"
environment:
  OLLAMA_NUM_PARALLEL: "1"
  OLLAMA_MAX_LOADED_MODELS: "1"
  OMP_NUM_THREADS: "3"
```

1 of the 4 cores stays free for the OS, `api`, and Postgres. Note
`OLLAMA_NUM_PARALLEL=1` was already the host's *computed default* in
practice (see `ai_gateway.py`'s existing client-side semaphore, which
serializes calls for exactly this reason) -- this makes it explicit rather
than relying on Ollama's own defaulting.

The `web` Compose service also got `mem_limit: 2g` and
`NODE_OPTIONS=--max-old-space-size=2048`, for the same no-swap reason: a
runaway `vite build`/`tsc -b` (both do run in that container -- see
`package.json`'s `build` script) shouldn't be able to starve everything
else.

### 2. Lighter default models

`qwen3:8b` (5.2GB) is replaced as the default chat model by
**`qwen2.5-coder:1.5b`** (`CHAT_MODEL` in `.env`/`.env.example`,
`chat_model` in `services/api/src/api/config.py`). `nomic-embed-text`
(embeddings) is unchanged.

**Caveat worth watching**: `qwen2.5-coder:1.5b` is a code-specialized
model, and this app is a legal/document assistant (`/chat`, `/legal/draft`,
task/entity extraction), not a coding tool -- there's a real risk this
underperforms on legal drafting or nuanced document Q&A compared to a
general-instruct model. `qwen2.5:3b-instruct` is already pulled in
production and is the documented one-env-var fallback
(`CHAT_MODEL=qwen2.5:3b-instruct` in `.env`, restart `api`) if answer
quality regresses. Watch `ai_call_log` and real usage, not just that the
endpoint responds.

`qwen3:8b` was **not** deleted from the Ollama volume (in case it's
wanted back) -- `OLLAMA_MAX_LOADED_MODELS=1` means it costs disk only, not
RAM, unless something explicitly requests it again. Remove with `docker
compose exec ollama ollama rm qwen3:8b` if disk hygiene is ever wanted (83G
free at time of writing, not urgent).

### 3. `num_predict` cap (real gap closed)

Before this change, no Ollama call anywhere in `ai_gateway.py` set
`num_predict` -- generation length was unbounded. `_call_ollama` now always
sends `options.num_predict`, defaulting to `settings.chat_num_predict`
(512), overridable per-call via the `options` param.

### 4. DeepSeek-R1 reasoning path

New in `services/api/src/api/ai_gateway.py`:

- **`execute_complex_reasoning(prompt, *, user_id, endpoint)`** -- calls
  `settings.reasoning_model` (`deepseek-r1:1.5b`) with `think=True`,
  `temperature=0.4`, `num_predict=settings.reasoning_num_predict` (1024,
  double chat's cap so the chain-of-thought has room to finish before a
  truncation would otherwise strip the final answer).
- **`_split_thinking(content, message)`** -- deepseek-r1 emits its
  chain-of-thought inline as a `<think>...</think>` block at the start of
  `message.content` by default; this regex-splits it into `thinking`
  (everything inside the block) and `solution` (everything after). Falls
  back to `message.thinking` (some Ollama versions return it as a separate
  field instead) and then to "no thinking captured, full content is the
  solution" if neither shape is present -- never errors just because a
  response didn't think out loud.

New endpoint: **`POST /manager/reason`** (`services/api/src/api/manager_router.py`),
same auth as `/manager/ask` (`get_effective_user` -- JWT bearer token,
also usable by the signal-bot service account via
`X-On-Behalf-Of-Phone`). Deliberately bypasses `manager_agent`'s
tool-calling loop -- this is for reasoning/logic prompts, not
document-grounded or tool-driven requests.

```
POST /manager/reason
{"prompt": "..."}
->
{"thinking": "...", "solution": "..."}
```

`thinking` is for admin/debug visibility only -- it carries the same
hallucination risk as any unvetted model output, just not yet cleaned up
into a final answer. Frontend/Signal callers should show `solution`.

### What was deliberately *not* built

The original request specified a Next.js app (`src/lib/ai.ts`,
`src/app/api/ai/route.ts`, `npm install ollama`, PM2, `llms-ctx.txt`
context injection). **This codebase is Vite + React (`apps/web`), not
Next.js** -- there is no Next.js anywhere in the repo, no server-side API
routes on the frontend at all (it's a pure SPA), and no `llms-ctx.txt`
file exists. Building fake Next.js API routes calling Ollama directly from
the frontend would have created a second, ungoverned path to the model
that bypasses everything `ai_gateway.py` already does (per-user rate
limiting, the `ai_call_log` audit trail, permission-filtered tool access
via `manager_agent.py`) -- a regression, not an optimization. The
equivalent capability (a governed endpoint hitting Ollama with a capped,
timeout-protected request) was instead added to the existing FastAPI AI
Gateway, which is the app's real single chokepoint for LLM calls (see ADR
0003). PM2 wasn't added either: production's `web` Compose container is a
dev server, not in the public traffic path at all -- Caddy serves the
static `vite build` output directly, so there's no persistent Node
process to manage.

## Testing

Backend (run inside the live `api` container, since this dev environment
has no local Postgres/Docker -- see `services/api/tests/test_ai_gateway.py`
and `test_manager_router.py`):

```
docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_ai_gateway.py tests/test_manager_router.py -v
```

Covers: `num_predict` defaults onto every request, `execute_complex_reasoning`
sends the right model/temperature/options and correctly splits a `<think>`
block, and falls back gracefully when a response has no `<think>` block at
all. `/manager/reason` tests mirror the existing `/manager/ask` auth
pattern (200 with a valid token, 401 without).

Manual smoke test against the live endpoints:

```
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/token -d 'username=admin1&password=...' | jq -r .access_token)

curl -s -X POST http://127.0.0.1:8000/manager/ask \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"message": "hello"}'

curl -s -X POST http://127.0.0.1:8000/manager/reason \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"prompt": "If a train travels 60km in 40 minutes, what is its speed in km/h?"}'
```

Verify stability, not just a single request: watch `docker stats
collabrains-ollama-1` during and after a few real requests -- it should
settle back down between calls and never exceed the 1536m `mem_limit`
(a limit breach kills and restarts the container rather than hanging, per
`restart: unless-stopped`, so a crash-loop there is the signal something's
still off).

## Deploying this

`deploy_collabrains.sh` (repo root) automates: swap attempt (expected to
no-op on this OpenVZ host), bringing up `ollama` with its new limits,
pulling the three light models, rebuilding `api`/`web`, applying, and a
smoke-check via `docker compose ps` + `docker stats`. Run it from
`/opt/collabrains` on the server after `git pull`.
