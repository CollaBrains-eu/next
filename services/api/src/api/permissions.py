"""Role -> permission mapping (Phase 9c, ADR 0023).

Reuses the existing User.role field (ADR 0001) rather than introducing
a new authorization model -- no new tables, no per-user overrides.

member and admin currently grant identical permission sets: none of the
five existing tools' equivalent HTTP endpoints are role-gated today, so
this mapping exists for future differentiation, not because these two
roles need different scopes for the tools that exist now. service gets
zero permissions -- service accounts have never called any of these
tools directly (see ADR 0023).
"""

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "member": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write", "vehicles.write"}),
    "admin": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write", "vehicles.write"}),
    "service": frozenset(),
}


def has_permission(role: str, required_permissions: list[str]) -> bool:
    granted = ROLE_PERMISSIONS.get(role, frozenset())
    return set(required_permissions) <= granted
