"""LDAP-backed authentication.

Verifies credentials by binding to the directory as the user (never reads
or stores the password) and separately checks admin-group membership using
the bind connection. Postgres remains the source of truth for role
thereafter -- see api.models.User.
"""
from dataclasses import dataclass

from ldap3 import Connection, Server

from api.config import settings


@dataclass
class LdapIdentity:
    username: str
    display_name: str
    email: str | None
    is_admin: bool


def authenticate(username: str, password: str) -> LdapIdentity | None:
    if not username or not password:
        return None

    user_dn = settings.ldap_bind_dn_template.format(username=username)
    server = Server(settings.ldap_url)
    conn = Connection(server, user=user_dn, password=password)

    if not conn.bind():
        return None

    try:
        conn.search(
            search_base=user_dn,
            search_filter="(objectClass=inetOrgPerson)",
            attributes=["cn", "mail"],
        )
        if not conn.entries:
            return None
        entry = conn.entries[0]
        display_name = str(entry.cn) if "cn" in entry else username
        email = str(entry.mail) if "mail" in entry and entry.mail else None

        conn.search(
            search_base=settings.ldap_admin_group_dn,
            search_filter="(objectClass=groupOfNames)",
            attributes=["member"],
        )
        is_admin = any(
            user_dn.lower() == str(m).lower()
            for entry in conn.entries
            for m in entry.member
        )

        return LdapIdentity(username=username, display_name=display_name, email=email, is_admin=is_admin)
    finally:
        conn.unbind()
