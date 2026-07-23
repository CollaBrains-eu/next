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
  slapd -h "ldap:///" -u openldap -g openldap -f /etc/ldap/slapd.conf &
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

  # Tolerant of the seeding slapd having already exited on its own by this
  # point (observed live in CI: sh's `&`/`$!` can track a PID that's gone
  # by the time kill runs, e.g. if slapd double-forks internally) --
  # `set -e` turned that into a hard crash before, right after seeding
  # had already succeeded. If it's already gone, the goal (stop it) is
  # already met.
  kill "$SLAPD_PID" 2>/dev/null || true
  wait "$SLAPD_PID" 2>/dev/null || true
  # Killing/reaping the process doesn't guarantee the kernel has released
  # its bound TCP port yet -- observed live in CI: the foreground slapd
  # below failed with "bind(6) failed errno=98 (Address already in use)"
  # immediately after `wait` returned. A short settle delay avoids the race.
  sleep 1
  echo "[entrypoint] seeding complete"
fi

echo "[entrypoint] starting slapd in foreground"
exec slapd -d 256 -h "ldap:///" -u openldap -g openldap -f /etc/ldap/slapd.conf
