"""LDAP-backed authentication, plus admin-initiated user creation.

Verifies credentials by binding to the directory as the user (never reads
or stores the password) and separately checks admin-group membership using
the bind connection. Postgres remains the source of truth for role
thereafter -- see api.models.User.

`create_user` is a separate concern (Admin Dashboard's "add user" feature,
ADR TBD): it binds as the LDAP admin (cn=admin,{base_dn}) rather than as a
user, and only ever writes to the directory -- it does not create a
Postgres User row. That row appears the same way it does for every other
user, via the existing auto-provision-on-first-login path in api.auth.
"""
import secrets
from dataclasses import dataclass

from ldap3 import HASHED_SALTED_SHA, MODIFY_ADD, MODIFY_REPLACE, Connection, Server
from ldap3.utils.hashed import hashed

from api.config import settings


class LdapAdminError(Exception):
    """Raised when an admin-bind LDAP write fails (bind failure, entry
    already exists, or any other directory-reported error)."""


@dataclass
class LdapIdentity:
    username: str
    display_name: str
    email: str | None
    is_admin: bool


@dataclass
class LdapUserCreated:
    username: str
    temporary_password: str


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


def _add_ldap_person(conn: Connection, *, username: str, display_name: str, email: str, password_hash: str) -> str:
    """Shared by create_user (admin flow, random password) and register_user
    (self-service flow, ADR 0074, user-chosen password already hashed by
    the caller) -- both need the identical directory entry, differing only
    in where the password comes from. Returns the new entry's DN."""
    conn.search(
        search_base=f"ou=people,{settings.ldap_base_dn}",
        search_filter="(objectClass=posixAccount)",
        attributes=["uidNumber"],
    )
    existing_uid_numbers = [int(entry.uidNumber.value) for entry in conn.entries]
    next_uid = max(existing_uid_numbers, default=10000) + 1

    user_dn = settings.ldap_bind_dn_template.format(username=username)
    name_parts = display_name.strip().split(" ", 1)
    given_name = name_parts[0]
    surname = name_parts[1] if len(name_parts) > 1 else name_parts[0]

    added = conn.add(
        user_dn,
        ["inetOrgPerson", "posixAccount", "shadowAccount"],
        {
            "uid": username,
            "sn": surname,
            "givenName": given_name,
            "cn": display_name,
            "displayName": display_name,
            "uidNumber": next_uid,
            "gidNumber": next_uid,
            "homeDirectory": f"/home/{username}",
            "mail": email,
            "userPassword": password_hash,
        },
    )
    if not added:
        raise LdapAdminError(conn.result.get("description", "LDAP add failed"))
    return user_dn


def create_user(*, username: str, display_name: str, email: str, is_admin: bool) -> LdapUserCreated:
    """Create a new LDAP user (Admin Dashboard "add user"). Generates a
    temporary password and returns it -- there's no email-delivery
    mechanism, so the admin relays it out of band; it is never stored or
    logged. Raises LdapAdminError on any failure, including "username
    already exists"."""
    admin_dn = f"cn=admin,{settings.ldap_base_dn}"
    server = Server(settings.ldap_url)
    conn = Connection(server, user=admin_dn, password=settings.ldap_admin_password)

    if not conn.bind():
        raise LdapAdminError("could not bind as LDAP admin")

    try:
        temporary_password = secrets.token_urlsafe(12)
        user_dn = _add_ldap_person(
            conn,
            username=username,
            display_name=display_name,
            email=email,
            password_hash=hashed(HASHED_SALTED_SHA, temporary_password),
        )

        if is_admin:
            conn.modify(settings.ldap_admin_group_dn, {"member": [(MODIFY_ADD, [user_dn])]})
            if not conn.result.get("result") == 0:
                raise LdapAdminError(
                    f"user created but admin-group add failed: {conn.result.get('description')}"
                )

        return LdapUserCreated(username=username, temporary_password=temporary_password)
    finally:
        conn.unbind()


def register_user(*, username: str, display_name: str, email: str, password_hash: str) -> None:
    """Self-service signup (Priority 3, ADR 0074). The password is already
    chosen by the user and pre-hashed by the caller
    (registration_service.hash_password) at registration time, before the
    email is even confirmed reachable -- so there's no temporary password
    to generate, relay, or return here. Raises LdapAdminError on any
    directory failure, including "username already exists"."""
    admin_dn = f"cn=admin,{settings.ldap_base_dn}"
    server = Server(settings.ldap_url)
    conn = Connection(server, user=admin_dn, password=settings.ldap_admin_password)

    if not conn.bind():
        raise LdapAdminError("could not bind as LDAP admin")

    try:
        _add_ldap_person(conn, username=username, display_name=display_name, email=email, password_hash=password_hash)
    finally:
        conn.unbind()


def set_password(*, username: str) -> str:
    """Admin-bind password reset (Admin Dashboard). Generates a fresh
    temporary password -- never admin-typed, same rationale as
    create_user's password generation -- and overwrites userPassword.
    Returns the new password once; it is never stored or logged. Raises
    LdapAdminError if the user doesn't exist or the modify fails."""
    admin_dn = f"cn=admin,{settings.ldap_base_dn}"
    server = Server(settings.ldap_url)
    conn = Connection(server, user=admin_dn, password=settings.ldap_admin_password)

    if not conn.bind():
        raise LdapAdminError("could not bind as LDAP admin")

    try:
        user_dn = settings.ldap_bind_dn_template.format(username=username)
        conn.search(search_base=user_dn, search_filter="(objectClass=inetOrgPerson)", attributes=["uid"])
        if not conn.entries:
            raise LdapAdminError(f"user {username!r} does not exist")

        temporary_password = secrets.token_urlsafe(12)
        password_hash = hashed(HASHED_SALTED_SHA, temporary_password)
        modified = conn.modify(user_dn, {"userPassword": [(MODIFY_REPLACE, [password_hash])]})
        if not modified:
            raise LdapAdminError(conn.result.get("description", "LDAP password modify failed"))

        return temporary_password
    finally:
        conn.unbind()


def delete_user(*, username: str) -> None:
    """Admin-bind LDAP entry delete (Admin Dashboard "deactivate"). Does
    not touch Postgres -- callers pair this with User.is_active = False.
    Raises LdapAdminError (message containing "does not exist") if
    there's no such entry, or on any other directory-reported failure."""
    admin_dn = f"cn=admin,{settings.ldap_base_dn}"
    server = Server(settings.ldap_url)
    conn = Connection(server, user=admin_dn, password=settings.ldap_admin_password)

    if not conn.bind():
        raise LdapAdminError("could not bind as LDAP admin")

    try:
        user_dn = settings.ldap_bind_dn_template.format(username=username)
        conn.search(search_base=user_dn, search_filter="(objectClass=inetOrgPerson)", attributes=["uid"])
        if not conn.entries:
            raise LdapAdminError(f"user {username!r} does not exist")

        deleted = conn.delete(user_dn)
        if not deleted:
            raise LdapAdminError(conn.result.get("description", "LDAP delete failed"))
    finally:
        conn.unbind()

