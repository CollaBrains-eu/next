# 0047 — Cryptominer incident on v78281.1blu.de, and a chat model upgrade found along the way

## Status

Accepted (incident response + resulting infra change)

## Context

While investigating an unrelated report that Ollama's `/api/chat` was
returning `500 Internal Server Error` ("make sure Signal and other
services are fully running"), the root cause turned out to be a live
cryptomining compromise of the production host itself, not an Ollama bug.

## What was found

- `/usr/local/bin/systemd` — a 3.1MB dropped binary (XMRig-family Monero
  miner), disguised with a legitimate-sounding name. Real systemd lives
  in `/usr/lib/systemd/systemd`, not `/usr/local/bin/`.
- `/etc/systemd/system/systemd.service` ("System Proxy Service") — ran
  the miner as root, `Restart=always`, enabled via
  `multi-user.target.wants` (survives reboot). Command line pointed at
  `xmr.kryptex.network:8029` with an embedded Monero wallet address.
- `/etc/systemd/system/observed.service` ("System Observer Service") —
  ran `/usr/local/bin/free_proc.sh` in a 2-second loop:
  `ps -eo pid,pcpu,args | awk '$2 > 200 && !/systemd/ {print $1}' | xargs -r kill -9`
  — SIGKILLs any process over 200% CPU whose name doesn't contain
  "systemd". This was the *actual* cause of the Ollama `/api/chat` 500s:
  `llama-server`'s multi-threaded model loading routinely exceeds 200%
  CPU on this 8-core host, so the watchdog was killing it mid-load every
  time, which Ollama surfaced as `"llama-server process has terminated:
  signal: killed"`.
- Both dropped files and both unit files carried matching timestamps
  (2026-07-09 10:50–10:51 UTC), consistent with a single automated
  deployment, not manual interactive access.

## What was ruled out as the entry vector

- `root`'s `~/.ssh/authorized_keys` contains only the key added earlier
  this session for passwordless access — no unauthorized second key.
- `last -20` shows no unfamiliar source IP around the infection window.
- `/var/log/auth.log` has no entries for that window at all.
- Caddy's logs for that window are empty (no request activity captured
  by the query used).

This points toward a web-facing service exploit (Caddy fronts
Paperless-ngx and this app's own API on 80/443, both public) rather than
SSH credential compromise, but the exact vector was not conclusively
identified — a deeper audit of what's actually exposed on 80/443, and
of Paperless/other services' patch levels, is a follow-up this ADR does
NOT close out.

## Remediation performed

1. `systemctl stop` + `disable` both fake units.
2. Deleted `/etc/systemd/system/systemd.service`,
   `/etc/systemd/system/observed.service`, and their
   `multi-user.target.wants` symlinks.
3. Deleted `/usr/local/bin/systemd` and `/usr/local/bin/free_proc.sh`.
4. `systemctl daemon-reload` + `reset-failed`.
5. Verified: no `xmr`/`kryptex` process remains; `systemctl status` on
   both unit names reports "could not be found"; load average dropped
   from ~11-13 to normal; `llama-server` completed a model load without
   being killed for the first time; `/api/chat` returned `200` again.

A second server (`178.254.22.178` / `v45264.1blu.de`, the separate
"secondary Ollama host") was checked for the same pattern as a
precaution — clean, idle load average, no dropped files, legitimate
services only.

## Follow-up NOT done in this pass (explicitly deferred)

- Identifying and closing the actual entry vector (likely a public
  80/443-facing service). Without this, reinfection is possible.
- A broader compromise audit: other dropped binaries, modified
  crontabs beyond what was checked, outbound firewall rules, other
  `system.slice` units, changed SSH `sshd_config`, etc. — only the
  specific persistence mechanism found was investigated, not an
  exhaustive sweep.
- Rotating credentials as a precaution (LDAP admin, Postgres, any
  secrets that were in environment/config files readable by a root-level
  compromise).

## Chat model upgrade (found while re-verifying Ollama post-remediation)

With the miner gone and CPU no longer being starved, `qwen3:8b` was
pulled and load-tested against the currently-configured `qwen2.5:3b-
instruct`. Default Ollama behavior for `qwen3:8b` emits a full
chain-of-thought before every answer — **32 seconds** for the trivial
prompt "say ok" on this CPU-only 8-core host, vs. `qwen2.5:3b-instruct`'s
~3.6s for the same prompt. Sending `"think": false` in the request body
(Qwen3-specific, silently ignored by non-thinking models — confirmed
against `qwen2.5:3b-instruct`) cut this to **1.8 seconds**, faster than
the smaller model.

Given `think:false` qwen3:8b is both faster and a larger/more capable
model than the previous default, `config.py`'s `chat_model` default was
changed from `"qwen2.5:3b-instruct"` to `"qwen3:8b"`, and
`ai_gateway.py::_call_ollama` now always sends `"think": false` in the
request body (single global default per ADR 0003 — no per-model config
surface added).

## Verification

- `test_ai_gateway.py`: 4 passed, 1 failed (the same pre-existing
  baseline failure, unrelated to this change).
- Deployed live; confirmed via the API's reload log and a `200` health
  check.
- `qwen2.5:3b-instruct` remains pulled on the host (not deleted) as a
  fallback if `qwen3:8b` proves problematic under real production load.
