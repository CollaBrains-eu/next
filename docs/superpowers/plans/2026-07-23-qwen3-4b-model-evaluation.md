# Switch chat_model to qwen3:4b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `qwen3:8b` (5.2GB, the current default `chat_model`) with `qwen3:4b` (~half the size) on the production host `178.254.22.178`, but only if it survives the exact live-verification that already caught two broken smaller-model attempts today — otherwise stop and report, don't ship a regression.

**Architecture:** No code architecture changes. This is a config value (`chat_model` in `services/api/src/api/config.py` + `CHAT_MODEL` in `.env`/`.env.example`) plus an Ollama model swap on the server. The gate is entirely behavioral: does `qwen3:4b` correctly perform `manager_agent`'s multi-round tool-calling and answer in a non-English language, using the same two prompts that already exposed `qwen2.5-coder:1.5b` and `qwen2.5:3b-instruct` as broken today.

**Tech Stack:** Ollama (model pull/rm), FastAPI (`services/api`), Docker Compose (`docker-compose.yml`, no changes needed — `mem_limit: 6656m` on `ollama` already comfortably covers a smaller model too).

## Global Constraints

- Server: `root@178.254.22.178` (`/opt/collabrains`). SSH key auth only (no password).
- Never remove `qwen3:8b` from the Ollama volume until `qwen3:4b` has passed **both** verification prompts below — it's the only proven-working rollback target from today's earlier work.
- Both verification prompts are required, not one: a trivial greeting alone is exactly what made `qwen2.5-coder:1.5b` look safe before it broke on real use today (see `docs/deployment/ai-optimization.md`).
- `api` runs `uvicorn --reload` against a bind mount — code changes apply automatically, but `.env` changes need `docker compose up -d api` to take effect (env vars are only read at container start).
- Editing `.env`/running `docker compose up -d api` on this server is a live, user-facing action (real people use this app) — run it as one atomic step, don't leave the container in a half-recreated state, and confirm `docker inspect collabrains-api-1 --format '{{.State.Running}}'` says `true` and `curl -s -o /dev/null -w '%{http_code}' https://collabrains.eu/` says `200` immediately after any restart, every time.
- Client-side `curl -m N` timing out does **not** cancel the server-side request (confirmed today — orphaned `manager_agent` loops kept running and piled up on the shared semaphore). If a verification call needs to be retried, restart `collabrains-api-1` first to clear any orphaned task before retrying, don't just re-run the same curl.

---

### Task 1: Pull qwen3:4b and live-verify it against the two known failure prompts

**Files:** None (server-side model pull + manual verification, no code touched yet).

**Interfaces:**
- Consumes: nothing new.
- Produces: a pass/fail verdict that Task 2 is gated on. Record the actual response text for both prompts in the task's commit-equivalent (a short note in this plan file's checklist, see Step 5).

- [ ] **Step 1: Pull the model**

Run:
```bash
ssh root@178.254.22.178 "docker exec collabrains-ollama-1 ollama pull qwen3:4b"
```
Expected: ends with `success`.

- [ ] **Step 2: Mint a disposable test user + JWT (member role, not admin)**

Run (inside the `api` container):
```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api python3 -c \"
import asyncio
from api.db import async_session
from api.models import User
from api.auth import create_access_token

async def main():
    async with async_session() as db:
        u = User(username='qwen4b-eval', display_name='qwen4b-eval', role='member')
        db.add(u)
        await db.commit()
    print(create_access_token('qwen4b-eval', 'member'))

asyncio.run(main())
\""
```
Expected: prints a JWT string. Save it as `$TOKEN` for the next steps.

- [ ] **Step 3: Temporarily point CHAT_MODEL at qwen3:4b and restart api (single atomic command)**

Run:
```bash
ssh root@178.254.22.178 "cd /opt/collabrains && sed -i 's/^CHAT_MODEL=.*/CHAT_MODEL=qwen3:4b/' .env && docker compose up -d api"
```
Then immediately confirm the container actually came back up (do not proceed to Step 4 until both of these pass):
```bash
ssh root@178.254.22.178 "docker inspect collabrains-api-1 --format 'Running: {{.State.Running}}'"
curl -s -o /dev/null -w 'collabrains.eu -> %{http_code}\n' https://collabrains.eu/
```
Expected: `Running: true` and `-> 200`. If either fails, immediately run Step 6's revert command before doing anything else.

- [ ] **Step 4: Run both verification prompts, one at a time (not concurrently)**

Tool-calling scenario (the `qwen2.5-coder:1.5b` failure mode: fake tool call printed as text, `tools_called: []`):
```bash
ssh root@178.254.22.178 "curl -s -m 280 -X POST http://127.0.0.1:8000/manager/ask -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' -d '{\"message\": \"What documents do I have uploaded?\"}'"
```
Pass criteria: response is coherent English. If it decides to call a tool, `tools_called` must contain a real entry (e.g. `["search"]`) — not an empty list with a fake JSON blob embedded in `answer`.

Wait for that to fully return before running the second one (shared global semaphore — see Global Constraints). Non-English scenario (the `qwen2.5-coder:1.5b` failure mode: hallucinated, incoherent, unrelated content):
```bash
ssh root@178.254.22.178 "curl -s -m 280 -X POST http://127.0.0.1:8000/manager/ask -H 'Authorization: Bearer $TOKEN' -H 'Content-Type: application/json' -d '{\"message\": \"Kun je in het Nederlands uitleggen wat je kunt doen?\"}'"
```
Pass criteria: fluent, coherent Dutch, describing this app's actual capabilities (documents/search/tasks/entities/legal drafts/vehicle lookup) — not English, not hallucinated/unrelated content, no fake tool-call JSON printed as text.

- [x] **Step 5: Verdict — FAIL.** Only ran the tool-calling prompt ("What documents do I have uploaded?") since it failed clearly enough to stop there per Step 6, without spending a second ~3min call on the Dutch prompt. Result: `tools_called: []` (no real tool call, same failure as qwen2.5-coder:1.5b) **and** the `answer` field contained qwen3:4b's raw internal chain-of-thought leaked verbatim into user-facing text ("Okay, the user is asking... Let me think about the tools provided... Hmm... Wait...", cut off mid-sentence by the num_predict cap) despite `think: false` being sent in the request. This is a new, distinct failure mode from either smaller model tried earlier today — worse, since qwen2.5-coder:1.5b at least produced grammatically finished (if fake) text. Hypothesis, not confirmed: smaller Qwen3 variants may not honor `think: false` as reliably as qwen3:8b does. **qwen3:4b does not pass. qwen3:8b remains the only model that has passed this verification.**

- [x] **Step 6: Reverted and stopped the plan here.** `CHAT_MODEL` back to `qwen3:8b` in `.env`, `docker compose up -d api`, confirmed `Running: true` and `https://collabrains.eu/` back to 200. Disposable test user deleted. `qwen3:4b` removed from the Ollama volume (`ollama rm`) since it's proven inadequate — Ollama now holds only the 3 models actually used: `qwen3:8b`, `deepseek-r1:1.5b`, `nomic-embed-text`. **Tasks 2 and 3 do not run** (both gated on Task 1 passing). This plan is closed as "evaluated, rejected" rather than executed further.

Run:
```bash
ssh root@178.254.22.178 "cd /opt/collabrains && sed -i 's/^CHAT_MODEL=.*/CHAT_MODEL=qwen3:8b/' .env && docker compose up -d api"
ssh root@178.254.22.178 "docker inspect collabrains-api-1 --format 'Running: {{.State.Running}}'"
curl -s -o /dev/null -w 'collabrains.eu -> %{http_code}\n' https://collabrains.eu/
```
Then delete the disposable test user (Step 8) and stop — do not proceed to Task 2. Report the failure mode back before trying any other model.

- [ ] **Step 7: If both prompts passed, leave CHAT_MODEL=qwen3:4b as-is and proceed to Task 2**

No command — this is just the branch point. `.env` already has the right value from Step 3.

- [ ] **Step 8: Delete the disposable test user either way**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api python3 -c \"
import asyncio
from sqlalchemy import delete, select
from api.db import async_session
from api.models import User, AiCallLog

async def main():
    async with async_session() as db:
        result = await db.execute(select(User).where(User.username=='qwen4b-eval'))
        u = result.scalar_one()
        await db.execute(delete(AiCallLog).where(AiCallLog.user_id==u.id))
        await db.execute(delete(User).where(User.id==u.id))
        await db.commit()
    print('cleaned up')

asyncio.run(main())
\""
```

---

### Task 2: Make qwen3:4b the committed default (only runs if Task 1 passed)

**Files:**
- Modify: `services/api/src/api/config.py` (`chat_model` default + comment)
- Modify: `.env.example` (`CHAT_MODEL`)
- Modify: `docs/deployment/ai-optimization.md` ("Model downsizing" section)

**Interfaces:**
- Consumes: Task 1's PASS verdict.
- Produces: `chat_model` default matches what's already live in `.env` from Task 1 Step 3/7 — no further server-side `.env` change needed in this task.

- [ ] **Step 1: Update the config default**

In `services/api/src/api/config.py`, replace the `chat_model` field and its comment:
```python
    # qwen3:4b replaces qwen3:8b as of 2026-07-23 -- live-verified against
    # manager_agent's tool-calling path and a Dutch-language prompt (see
    # docs/deployment/ai-optimization.md), unlike qwen2.5-coder:1.5b and
    # qwen2.5:3b-instruct which both failed the same two checks. Do not
    # downsize further without running both checks again -- that failure
    # mode is invisible on a trivial greeting.
    chat_model: str = "qwen3:4b"
```

- [ ] **Step 2: Update .env.example**

In `.env.example`, replace the `CHAT_MODEL` line and its comment block similarly, pointing at `qwen3:4b` and referencing the same verification.

- [ ] **Step 3: Update docs/deployment/ai-optimization.md**

In the "2. Model downsizing -- attempted, live-tested, reverted" section, add a dated follow-up subsection recording that `qwen3:4b` was tried next, what the two live prompts returned, and that it's now the default — keep the existing qwen2.5-coder:1.5b/qwen2.5:3b-instruct failure writeup intact (still true, still the reason smaller models need this exact gate).

- [ ] **Step 4: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/config.py .env.example docs/deployment/ai-optimization.md docs/superpowers/plans/2026-07-23-qwen3-4b-model-evaluation.md
git commit -m "Switch default chat_model to qwen3:4b after live-verifying tool-calling + Dutch prompt

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 3: Remove qwen3:8b from the Ollama volume (only after Task 2 is committed and deployed)

**Files:** None (server-side only).

**Interfaces:**
- Consumes: Task 2 committed and `.env`/`config.py` agree on `qwen3:4b` in production.
- Produces: disk freed, no config still pointing at `qwen3:8b` anywhere.

- [ ] **Step 1: Double-check nothing still references qwen3:8b before deleting it**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && grep -rn 'qwen3:8b' .env services/api/src/api/config.py"
```
Expected: no matches. If there's a match, stop and fix it first — do not delete the model while something still points at it.

- [ ] **Step 2: Remove it**

```bash
ssh root@178.254.22.178 "docker exec collabrains-ollama-1 ollama rm qwen3:8b"
ssh root@178.254.22.178 "docker exec collabrains-ollama-1 ollama list"
```
Expected: only `qwen3:4b`, `deepseek-r1:1.5b`, `nomic-embed-text` remain.

- [ ] **Step 3: Final live smoke check**

```bash
curl -s -o /dev/null -w 'collabrains.eu -> %{http_code}\n' https://collabrains.eu/
```
Expected: `200`.
