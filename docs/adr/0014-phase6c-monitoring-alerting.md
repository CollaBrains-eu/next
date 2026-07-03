# ADR 0014: Phase 6c — Monitoring & Alerting

## Status
Accepted

## Context
Third slice of Phase 6 (production readiness, split per ADR 0012).
`/health` and `/health/ready` have existed since Phase 0/1b, but nothing
ever checks them — if the site went down at 3am, nobody would know until
someone happened to try loading it. This phase closes that gap.

## Decisions

**No new monitoring infrastructure.** Prometheus/Grafana (or any
metrics stack) is the standard answer for "monitoring," but this is a
single VM running a bounded, known set of services — the actual
requirement is "tell a human when something breaks," not dashboards or
historical metrics nobody's asked for. A cron-run shell script doing
HTTP checks and alerting is enough, same "no infra beyond what's needed"
reasoning used everywhere else in this project (Postgres-native search
over Elasticsearch, Caddy over nginx+certbot, cron over a new
scheduler service for backups in Phase 6b).

**What gets checked, every 5 minutes**:
- Every currently-running `docker compose` service is still running
  (checked dynamically against whatever's actually up, not a hardcoded
  list — the deployment's enabled profiles can change).
- `GET /health/ready` on the API directly (`127.0.0.1:8000`, the
  host-local binding from Phase 6a) — validates DB connectivity from
  inside the deployment.
- `GET /health` through the *public* HTTPS path
  (`https://v78281.1blu.de/health`) — validates the thing an actual
  user would hit: TLS, Caddy routing, and the API all working together.
  This is deliberately not redundant with the check above: Phase 6a's
  own testing found a real Caddy routing bug that the internal
  `127.0.0.1:8000` check alone would never have caught, since it only
  exercises the reverse proxy, not the app directly.
- Disk usage on `/` — backups (Phase 6b) accumulate over time even with
  retention, so this is the guard against silently filling the disk.

**Alert channel: the Signal bot, not a new one.** `POST /v2/send`
against signal-cli directly (`127.0.0.1:8011`, the host-local binding —
this script runs on the host via cron, not inside a container, so it
can't reach `signal-cli` by Docker service name the way `api` does), the
same call `services/api/src/api/signal_client.py` already makes.
Recipient is a new `ALERT_PHONE_NUMBER` setting in `.env` (defaults to
the number currently linked to `admin1`) — standing up a second
notification channel (email, a paging service) for a single-operator
deployment would be pure overhead when a channel that's already proven
to work end-to-end (Phase 3) exists.

**Alert on transitions, not every failure.** A state file
(`/opt/collabrains-backups/../monitoring-state`, i.e. a sibling of the
backup directory, for the same "outside the git tree" reasoning as
Phase 6b) records the last known overall status. An alert only fires
when status *changes* — healthy→unhealthy (with which specific check(s)
failed) or unhealthy→healthy (a "recovered" message). Without this, a
real outage would page every 5 minutes for its entire duration, which
trains the one human who'd act on it to ignore the channel — worse than
no alerting at all.

## Why not more in 6c
No historical retention of check results, no dashboard, no alerting for
individual container restarts that self-heal within one check interval
(Docker's own `restart: unless-stopped` already handles transient
crashes — alerting on every restart would be noise, not signal). If
uptime history or trend visibility becomes an actual need later, that's
new information this ADR doesn't have yet.
