#!/usr/bin/env bash
# Daily backup of Postgres, LDAP, and Signal registration keys. See
# docs/adr/0013-phase6b-backups.md and docs/runbooks/backup-restore.md.
set -euo pipefail

REPO_DIR="/opt/collabrains"
BACKUP_DIR="/opt/collabrains-backups"
RETENTION_DAYS=14
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

mkdir -p "$BACKUP_DIR"
cd "$REPO_DIR"

source .env

echo "[$(date -Iseconds)] Starting backup $TIMESTAMP"

docker compose exec -T postgres pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB" \
  > "$BACKUP_DIR/postgres-$TIMESTAMP.dump"
echo "  postgres dump: $(du -h "$BACKUP_DIR/postgres-$TIMESTAMP.dump" | cut -f1)"

docker compose exec -T openldap slapcat > "$BACKUP_DIR/ldap-$TIMESTAMP.ldif"
echo "  ldap dump: $(du -h "$BACKUP_DIR/ldap-$TIMESTAMP.ldif" | cut -f1)"

tar czf "$BACKUP_DIR/signal-cli-$TIMESTAMP.tar.gz" -C "$REPO_DIR" infra/signal-cli
echo "  signal-cli archive: $(du -h "$BACKUP_DIR/signal-cli-$TIMESTAMP.tar.gz" | cut -f1)"

find "$BACKUP_DIR" -type f -mtime "+$RETENTION_DAYS" -print -delete

echo "[$(date -Iseconds)] Backup $TIMESTAMP complete"
