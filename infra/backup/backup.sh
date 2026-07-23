#!/usr/bin/env bash
# Daily backup of Postgres, LDAP, and Signal registration keys. See
# docs/adr/0013-phase6b-backups.md and docs/runbooks/backup-restore.md.
#
# ADR 0066 (Priority 1): all three dumps used to land on disk as plaintext,
# with no offsite copy -- given ADR 0047's prior root compromise, a repeat
# compromise would take every backup generation (LDAP password hashes and
# Signal's encryption keys included) with it. Each dump is now piped
# straight into `gpg --symmetric` so plaintext never touches disk at all,
# not even transiently.
set -euo pipefail

REPO_DIR="/opt/collabrains"
BACKUP_DIR="/opt/collabrains-backups"
RETENTION_DAYS=14
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
cd "$REPO_DIR"

source .env

: "${BACKUP_ENCRYPTION_PASSPHRASE:?BACKUP_ENCRYPTION_PASSPHRASE is required (see .env.example) -- refusing to write an unencrypted backup}"

echo "[$(date -Iseconds)] Starting backup $TIMESTAMP"

gpg_encrypt() {
  # Passphrase via process substitution, not --passphrase/argv, so it never
  # appears in `ps`. --pinentry-mode loopback + --batch keeps this
  # non-interactive for cron.
  gpg --batch --yes --pinentry-mode loopback \
    --passphrase-file <(printf '%s' "$BACKUP_ENCRYPTION_PASSPHRASE") \
    --symmetric --cipher-algo AES256 -o "$1"
}

docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
  | gpg_encrypt "$BACKUP_DIR/postgres-$TIMESTAMP.dump.gpg"
echo "  postgres dump: $(du -h "$BACKUP_DIR/postgres-$TIMESTAMP.dump.gpg" | cut -f1)"

docker compose exec -T openldap slapcat \
  | gpg_encrypt "$BACKUP_DIR/ldap-$TIMESTAMP.ldif.gpg"
echo "  ldap dump: $(du -h "$BACKUP_DIR/ldap-$TIMESTAMP.ldif.gpg" | cut -f1)"

tar czf - -C "$REPO_DIR" infra/signal-cli \
  | gpg_encrypt "$BACKUP_DIR/signal-cli-$TIMESTAMP.tar.gz.gpg"
echo "  signal-cli archive: $(du -h "$BACKUP_DIR/signal-cli-$TIMESTAMP.tar.gz.gpg" | cut -f1)"

find "$BACKUP_DIR" -type f -mtime "+$RETENTION_DAYS" -print -delete

echo "[$(date -Iseconds)] Backup $TIMESTAMP complete"
