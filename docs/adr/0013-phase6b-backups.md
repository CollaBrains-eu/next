# ADR 0013: Phase 6b — Automated Backups & Restore Procedure

## Status
Accepted

## Context
Second slice of Phase 6 (production readiness, split per ADR 0012).
There are no backups of anything on this host today. Three things hold
state that would be genuinely costly or impossible to reconstruct if
lost:

1. **Postgres** (`postgres_data` volume) — every user, document, chunk,
   task, entity, relationship, and audit log row. The obvious one.
2. **LDAP** (`ldap_data`/`ldap_config` volumes) — not just the seeded
   bootstrap data (`infra/ldap/bootstrap/01-users.ldif`, already in
   git): confirmed directly that live LDAP state has already diverged
   from that seed (`admin1`'s password was reset via `ldappasswd` in
   Phase 5a for browser-testing purposes and is not the bootstrap
   value), so restoring from the git-tracked LDIF alone would not
   reproduce the current directory.
3. **Signal registration** (`infra/signal-cli/`, bind-mounted,
   gitignored) — the encryption/session keys for the registered number
   `+4949534254784`. This is the highest-value target of the three:
   Postgres and LDAP data loss is bad but recoverable-in-principle;
   losing this means re-doing Phase 3a's registration from scratch,
   which needs a human to solve an hCaptcha and relay an SMS/voice code
   — not something that can be automated or done unattended.

## Decisions

**What backs each one up**: `pg_dump -Fc` (Postgres's custom format —
compressed, restorable with `pg_restore`, and unlike a raw volume copy
it's portable across Postgres point releases) for Postgres; `slapcat`
(produces a standard LDIF) for LDAP; a plain `tar czf` of
`infra/signal-cli/` for the Signal keys. All three run via
`docker compose exec` against the already-running containers — no
downtime, no stopping services to get a consistent snapshot (pg_dump and
slapcat are both safe to run against a live server).

**Where backups live**: `/opt/collabrains-backups/`, deliberately
*outside* `/opt/collabrains` (the git working tree). Both the Postgres
dump and the LDAP LDIF can contain personal data (documents, user
records) and the Signal tarball is explicitly security-sensitive —
keeping backups in a sibling directory means a future `git add -A` (or
any tooling that operates on the repo tree) can never accidentally stage
or leak them, rather than relying solely on a `.gitignore` entry to keep
that from happening.

**Retention**: daily backups, 14-day retention (deleted by the same
script that creates new ones). No tiered/weekly/monthly retention
scheme — this is a single-host deployment without the operational
history to know what retention policy it actually needs yet; 14 days is
enough to recover from "something broke and nobody noticed for a few
days" without unbounded disk growth, and can be widened later if a real
need shows up.

**Scheduling**: a root crontab entry running the backup script daily at
03:00 server time (Ollama/Paperless are idle overnight, so pg_dump
running concurrently has no contention to worry about). Not added to
Docker Compose as a service — this is host-level (needs `docker compose
exec` against several services plus a plain filesystem tar), not
something that fits the container-per-service model the rest of this
stack uses, and cron is the simplest tool that does the job (same
"no infra beyond what's needed" reasoning used everywhere else in this
project).

**Restore procedure**: documented in `docs/runbooks/backup-restore.md`
rather than only in this ADR — a restore is an operational runbook
someone reaches for under time pressure during an actual incident, not
a design decision to be re-derived from architecture notes. Verified by
actually performing a full round-trip (backup, then a scratch
schema/database restore) rather than just confirming a file was
created, since "a dump file exists" and "a dump file is restorable" are
not the same claim.

## Why not more in 6b
No off-host/off-site replication (e.g. shipping backups to S3 or another
server) — this is a single-VM deployment with no second host to send
backups to yet, and inventing one wouldn't be a real safeguard, just
motion. If a second host or object storage becomes available, extending
this script to `rclone`/`rsync` the backup directory there is a small
addition on top of what's built here, not a redesign.
