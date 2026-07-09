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

## Entry vector: confirmed

`/var/log/auth.log` had no entries for the infection window (log
rotation or a gap, not evidence of anything), which initially pointed
the investigation toward a web-facing service exploit instead. Checking
`journalctl -u ssh` for the same window found the real answer:

```
Jul 09 10:50:49 v78281.1blu.de sshd[643196]: Accepted password for root from 165.154.169.239 port 38980 ssh2
```

**A successful root password login, one second before the malware drop
began.** The same journal window shows this host under constant,
heavy SSH brute-force scanning from dozens of unrelated IPs (normal
background internet noise for any public IPv4 address) — this attacker
simply had the correct root password where the others didn't. Three
contributing misconfigurations, all confirmed:

- `PasswordAuthentication` was enabled (commented out in
  `sshd_config`, which defaults to `yes`) — SSH accepted password auth
  at all, not just keys.
- `PermitRootLogin yes` — direct root login over SSH, no separate
  unprivileged-user-then-`sudo` step required.
- `fail2ban` was not installed — nothing throttled or banned repeated
  failed attempts, so brute-forcing was unrate-limited.

`root`'s `~/.ssh/authorized_keys` containing only the key added earlier
this session (no unauthorized second key) is consistent with this: the
attacker never needed a key at all.

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

## Entry vector closed

- `PasswordAuthentication no` set in `/etc/ssh/sshd_config` (was a
  commented-out `#PasswordAuthentication yes`, i.e. the compiled-in
  default). Config validated with `sshd -t` before reload; key-based
  access re-verified in a fresh connection immediately after; a
  deliberate password-only auth attempt afterward confirmed rejection
  (`Permission denied (publickey)`, no password prompt offered at all).
  `sshd_config` backed up before editing
  (`/etc/ssh/sshd_config.bak-<timestamp>`).
- `fail2ban` installed and enabled with an `sshd` jail
  (`/etc/fail2ban/jail.local`: `maxretry=4`, `findtime=600`,
  `bantime=3600`, `backend=systemd`) — defense-in-depth in case password
  auth is ever mistakenly re-enabled, and reduces log noise from the
  constant background scanning either way.
- The root password itself was **not** rotated in this pass (explicit
  user decision) — with password auth disabled it's no longer a usable
  credential over SSH, but it should still be treated as burned/known to
  at least one attacker if it's reused anywhere else.

## Follow-up NOT done in this pass (explicitly deferred)

- Rotating the root password, and any other credentials that were
  readable by a root-level compromise (LDAP admin, Postgres, secrets in
  environment/config files) — the attacker had full root access for
  roughly an hour before remediation.
- A broader compromise audit beyond the specific persistence mechanism
  found: other possibly-dropped binaries, modified crontabs beyond what
  was checked, outbound firewall rules, other `system.slice` units,
  whether the attacker read/exfiltrated anything before the miner was
  even the visible symptom.
- Whether `165.154.169.239`'s successful login means the password was
  weak/guessed, leaked from a breach, or obtained some other way — not
  investigated, since disabling password auth entirely makes the
  specific answer less urgent (it closes the door regardless of how the
  key was obtained).

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
