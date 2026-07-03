# Runbook: Backup & Restore

Backups run automatically every day at 03:00 server time via root's
crontab (`infra/backup/backup.sh`), writing to `/opt/collabrains-backups/`
(outside the git repo — see ADR 0013 for why). 14 days of backups are
kept; older ones are deleted automatically by the same script. Logs go
to `/var/log/collabrains-backup.log`.

Each run produces three files, all timestamped the same way
(`YYYYMMDD-HHMMSS`):

- `postgres-<timestamp>.dump` — full database, `pg_dump -Fc` custom format
- `ldap-<timestamp>.ldif` — full directory, `slapcat` output
- `signal-cli-<timestamp>.tar.gz` — the registered Signal number's
  encryption/session keys and any stored attachments

## Restoring Postgres

Restoring into a **new/empty** database (safest — verify first, then
decide whether to promote it):

```bash
cd /opt/collabrains
docker compose exec -T postgres psql -U collabrains -d collabrains \
  -c "CREATE DATABASE collabrains_restored;"
docker compose exec -T postgres psql -U collabrains -d collabrains_restored \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose cp /opt/collabrains-backups/postgres-<timestamp>.dump \
  postgres:/tmp/restore.dump
docker compose exec -T postgres pg_restore -U collabrains \
  -d collabrains_restored /tmp/restore.dump
```

Spot-check row counts against what you expect, then either point
`DATABASE_URL` in `.env` at `collabrains_restored` and restart `api`, or
(to overwrite the live database in place instead of switching to a new
one — only do this once you've confirmed the dump is good):

```bash
docker compose stop api
docker compose exec -T postgres psql -U collabrains -d postgres \
  -c "DROP DATABASE collabrains;"
docker compose exec -T postgres psql -U collabrains -d postgres \
  -c "CREATE DATABASE collabrains;"
docker compose exec -T postgres psql -U collabrains -d collabrains \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
docker compose exec -T postgres pg_restore -U collabrains \
  -d collabrains /tmp/restore.dump
docker compose start api
```

(`docker compose cp` is used instead of piping the dump through
`docker compose exec -T ... < file`, since piping a binary file through
`exec`'s stdin was unreliable when this was tested — `pg_restore`
reported "did not find magic string in file header" even though the
dump itself was valid. Always copy the file into the container first.)

## Restoring LDAP

**Do not restore by dropping the LDIF into `/ldifs` and letting the
container's normal bootstrap flow seed it.** That flow uses `ldapadd`
(an online LDAP protocol operation), and `slapcat` output (what the
backup contains) includes operational attributes (`entryUUID`,
`entryCSN`, `creatorsName`, `modifyTimestamp`, etc.) that `ldapadd`
rejects — the container's entrypoint swallows that failure as a
non-fatal warning per file, so it *looks* like it worked but silently
restores nothing. Confirmed by actually attempting this: it produced an
empty directory with only a "WARNING: ... failed to apply (may already
exist)" log line as the sole evidence anything went wrong. A `slapcat`
dump must be restored with `slapadd` (offline, direct database load),
not `ldapadd`.

```bash
cd /opt/collabrains

# 1. Capture the container's currently-rendered slapd.conf (it's
#    generated from a template + .env values at container start, not
#    baked into the image, so grab it from a running container first).
docker compose exec -T openldap cat /etc/ldap/slapd.conf > /tmp/slapd.conf.rendered

# 2. Stop the service (slapadd needs exclusive access to the database
#    files — it can't run alongside a live slapd process).
docker compose stop openldap

# 3. Offline-load the backup LDIF directly into the volume via a
#    one-off container, bypassing the entrypoint's ldapadd-based
#    bootstrap flow entirely.
docker compose run --rm --entrypoint sh \
  -v /tmp/slapd.conf.rendered:/etc/ldap/slapd.conf:ro \
  -v /opt/collabrains-backups/ldap-<timestamp>.ldif:/tmp/restore.ldif:ro \
  openldap -c '
    set -e
    rm -rf /var/lib/ldap/*
    slapadd -f /etc/ldap/slapd.conf -l /tmp/restore.ldif
    chown -R openldap:openldap /var/lib/ldap
  '

# 4. Bring the real service back up on the restored data.
docker compose up -d openldap
```

Verified with a real round-trip: recorded `admin1`'s password hash
before deliberately wiping the LDAP volume, restored from a backup taken
minutes earlier, and confirmed login with the pre-wipe password
succeeded again afterward — not just that entries existed, but that the
exact prior state (including a password changed after the original
git-tracked bootstrap seed) came back correctly.

## Restoring Signal registration

```bash
cd /opt/collabrains
docker compose stop signal-cli signal-bot
rm -rf infra/signal-cli
tar xzf /opt/collabrains-backups/signal-cli-<timestamp>.tar.gz -C /opt/collabrains
docker compose --profile signal up -d signal-cli signal-bot
```

If this is being restored onto a *different* host than where the backup
was taken, double check `infra/signal-cli` file ownership matches what
the `signal-cli` container expects (it runs as a non-root user — see the
`1000 1000` ownership on that directory) before starting the container.

## Verifying a backup is good without doing a full restore

```bash
# Postgres: lists the dump's table of contents without restoring anything
docker compose cp /opt/collabrains-backups/postgres-<timestamp>.dump postgres:/tmp/check.dump
docker compose exec -T postgres pg_restore --list /tmp/check.dump | head -20

# LDAP: count directory entries
grep -c '^dn:' /opt/collabrains-backups/ldap-<timestamp>.ldif

# Signal: list archive contents, confirm account.db is present
tar tzf /opt/collabrains-backups/signal-cli-<timestamp>.tar.gz | grep account.db
```

## Manual backup (outside the daily schedule)

```bash
/opt/collabrains/infra/backup/backup.sh
```
