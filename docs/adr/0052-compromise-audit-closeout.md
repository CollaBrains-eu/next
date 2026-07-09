# 0052 — Compromise audit closeout (ADR 0047 follow-up)

## Status

Accepted

## Context

ADR 0047 documented finding and removing a cryptomining compromise on
`v78281.1blu.de`, closed the confirmed entry vector (SSH password
brute-force — disabled password auth, installed fail2ban), but
explicitly deferred a broader audit: *"other dropped binaries, modified
crontabs beyond what was checked, outbound firewall rules, other
`system.slice` units, whether the attacker read/exfiltrated anything
before the miner was even the visible symptom."* This closes that out.

## What was checked

- **Systemd units**: no files under `/etc/systemd/system` modified in
  the last 14 days (the removal of the two fake units — `systemd.
  service`, `observed.service` — is itself within that window, so this
  confirms nothing *else* was dropped alongside them).
- **Cron, every user**: iterated every account in `/etc/passwd`: only
  `root` has a crontab, and it contains only the two known, legitimate
  CollaBrains scripts (backup, watchdog). `/etc/cron.d`, `cron.daily`,
  `cron.hourly`, `cron.weekly`, `cron.monthly`: nothing modified in 14
  days.
- **Accounts**: `/etc/passwd` has exactly one real login account
  (`root`); the only other non-`nologin`/non-`false` shell entry is
  `sync` (`/bin/sync`, a standard Debian/Ubuntu system account, not a
  real shell).
- **SSH keys, every user**: only `/root/.ssh/authorized_keys`, only
  one key (the one added earlier this session for passwordless access).
- **Listening ports, all interfaces including localhost-bound**: every
  entry maps to a known service (the CollaBrains Docker stack, sshd,
  exim4 on localhost:25, systemd-resolved's DNS stub). Nothing
  unexplained.
- **Established outbound connections**: at audit time, only this SSH
  session itself. No connections to mining pools or anything else
  unexpected.
- **`/etc/ld.so.preload`**: does not exist. This is the classic
  LD_PRELOAD rootkit vector (a shared object forced into every
  process to hook/hide syscalls) — a clean miss here is a meaningfully
  positive signal, not just a formality.
- **Docker images and containers**: every image matches an expected
  service (the CollaBrains stack's own images, their base images, plus
  `hello-world` and an unused `osixia/openldap` base image left over
  from earlier setup — neither is a runtime container, both inert).
  Every running/stopped container maps to a known service.
- **Package integrity (`debsums -c`)**: flagged exactly 2 files across
  the entire installed package set, neither a binary in a
  security-sensitive path (`/bin`, `/usr/bin`, `/usr/sbin`, `/sbin` —
  the classic rootkit target list for trojanizing `ps`/`ls`/`ss`/`top`
  to hide a miner process — came back completely clean). Both flagged
  files inspected directly: a udev rule customized for `ploop` device
  naming and a postinst script creating `vzfifo.service` — both
  legitimate OpenVZ/Virtuozzo platform customizations specific to this
  hosting provider's container template, not attacker modifications.
- **`apt`/`dpkg` history, full log**: found what the earlier pass
  missed — `apt-get -y install msr-tools` at **10:51:03**, the same
  minute as the systemd units and dropped binaries. `msr-tools`
  provides `rdmsr`/`wrmsr`, used by some XMRig-family miners to tune
  CPU Model-Specific Registers for a hashrate boost. This is a
  well-known, publicly-documented pattern for this exact family of
  automated miner-deployment script — not a novel technique, but a
  concrete piece of evidence the deployment was scripted, not manual
  (binary + two systemd units + this package install, all within
  roughly two minutes).
- **`apt` sources**: only the official Ubuntu `noble` repos plus
  expected legitimate third-party lists (Docker, GitHub CLI,
  NodeSource, and the hosting provider's own `ct-preset`). No rogue or
  unofficial repository was added.

## Remediation from this pass

- `apt-get remove --purge -y msr-tools`. Checked first whether it had
  actually been used: the `msr` kernel module was not loaded and
  `/dev/cpu/*/msr` doesn't exist — consistent with this being an
  unprivileged OpenVZ/Virtuozzo container, which cannot load arbitrary
  kernel modules at all (a host-level operation). The attacker's
  MSR-tuning attempt almost certainly failed outright; the miner still
  ran, just without whatever hashrate boost it was meant to provide.
  Removed anyway as an attacker-installed artifact with no remaining
  purpose, not because it was doing anything.
- `debsums` was installed to run the integrity check above and left in
  place — a genuinely useful diagnostic tool for any future audit, not
  an attacker-installed artifact.

## What was not exhaustively verified (residual risk, explicitly named)

- Whether the attacker read or exfiltrated anything during the roughly
  one-hour window between the compromise (10:50 UTC) and remediation
  (per ADR 0047's timeline) — no log source checked here could answer
  that definitively (a determined attacker with an hour of root access
  could have read anything on disk without leaving an audit trail this
  kind of check would catch).
- The root password itself remains un-rotated (explicit user decision,
  documented in ADR 0047) — with password auth now disabled it's not a
  usable SSH credential, but should still be treated as burned if
  reused anywhere else.
- No memory-resident/fileless-malware check was performed (e.g.
  inspecting process memory for injected code) — the process list,
  systemd units, and package integrity checks above would not
  necessarily catch a purely in-memory implant that never wrote a file
  a debsums/find-mtime sweep could see.

## Verification

- Every check in this ADR was run directly against the live host over
  SSH and its actual output is what's summarized above — this is a
  record of what was found, not a plan for what to check.
- `debsums -c` exit code `0` (no packages missing checksum data to
  compare against — a partial/broken run would have looked different).
- `msr-tools` removal confirmed via `dpkg -l msr-tools` (no packages
  found) and `which wrmsr rdmsr` (both exit non-zero).
