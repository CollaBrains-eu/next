#!/bin/sh
set -e
set -x

: "${LDAP_BASE_DN:?LDAP_BASE_DN is required}"
: "${LDAP_ADMIN_PASSWORD:?LDAP_ADMIN_PASSWORD is required}"

mkdir -p /var/run/slapd /var/lib/ldap
chown -R openldap:openldap /var/run/slapd /var/lib/ldap

ADMIN_HASH=$(slappasswd -s "$LDAP_ADMIN_PASSWORD")
sed -e "s|__BASE_DN__|$LDAP_BASE_DN|g" \
    -e "s|__ADMIN_PW_HASH__|$ADMIN_HASH|g" \
    /etc/ldap/slapd.conf.template > /etc/ldap/slapd.conf

FIRST_BOOT=0
if [ -z "$(ls -A /var/lib/ldap 2>/dev/null)" ]; then
  FIRST_BOOT=1
fi

if [ "$FIRST_BOOT" = "1" ]; then
  echo "[entrypoint] first boot: starting slapd (classic config) to seed data"
  # -d 0: without any -d flag, slapd daemonizes itself (double-forks and
  # detaches) by default -- confirmed as the actual root cause of the
  # kill/bind races below, live in CI: `$!` was capturing the PID of the
  # short-lived parent that forked and exited, not the real detached
  # daemon, so `kill "$SLAPD_PID"` never touched the process actually
  # holding port 389, which was consequently still running (and still
  # bound) when the foreground instance below tried to bind the same
  # port. -d (any level, including 0) keeps slapd in the foreground like
  # the real instance's `-d 256` already does, so `$!` tracks the process
  # that actually needs killing.
  slapd -d 0 -h "ldap:///" -u openldap -g openldap -f /etc/ldap/slapd.conf &
  SLAPD_PID=$!

  for i in $(seq 1 30); do
    if ldapsearch -x -H ldap:/// -s base -b "" >/dev/null 2>&1; then
      break
    fi
    sleep 0.5
  done

  if [ -d /ldifs ]; then
    for f in /ldifs/*.ldif; do
      [ -e "$f" ] || continue
      echo "[entrypoint] seeding $f"
      ldapadd -x -D "cn=admin,$LDAP_BASE_DN" -w "$LDAP_ADMIN_PASSWORD" -H ldap:/// -f "$f" || \
        echo "[entrypoint] WARNING: $f failed to apply (may already exist)"
    done
  fi

  # Tolerant even though -d 0 above means $SLAPD_PID should now be the real,
  # still-running process (before that fix, $! tracked a parent that had
  # already self-daemonized and exited, so kill silently missed the actual
  # daemon entirely -- `set -e` turned any leftover failure here into a
  # hard crash regardless).
  kill "$SLAPD_PID" 2>/dev/null || true
  wait "$SLAPD_PID" 2>/dev/null || true
  # Small residual margin for the kernel to release the just-killed
  # process's bound TCP port before the foreground instance below tries
  # to bind the same one.
  sleep 1
  echo "[entrypoint] seeding complete"
fi

echo "[entrypoint] starting slapd in foreground"
exec slapd -d 256 -h "ldap:///" -u openldap -g openldap -f /etc/ldap/slapd.conf
