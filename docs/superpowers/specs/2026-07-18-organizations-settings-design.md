# Organizations Settings Page — Design

## Status
Proposed

## Context

The entire backend surface today is two endpoints: `GET /organizations/me` and `PUT /organizations/me/policies` (wholesale-replaces one JSONB blob), with exactly one real policy consumed anywhere (`approval_required_goals`, read by `planning_engine.py`). ADR 0029 explicitly defers org creation, membership management, and multi-org support to future "RBAC 2.0" work — there is one `Organization` row in the whole database, every user hardcoded to `DEFAULT_ORGANIZATION_ID`. There is zero frontend today (grepped: only false-positive hits on the unrelated Entity-extraction type `"organization"`).

Building a full multi-tenancy UI would mean designing and building org CRUD + membership endpoints from scratch first — a large, multi-week project with nothing to build against today. Building nothing but a single policy toggle undersells what's cheaply available: `users.organization_id` already exists on every user row, so "who's in my organization" is a one-query answer even though no membership-*management* endpoint exists. Landing on: ship the real, useful thing that's cheap today (policy control + a member roster), explicitly not the big thing that isn't (org switching, invites, multi-org).

## Goals

1. A Settings page section showing the organization's name and its one real policy (`approval_required_goals`), editable by admins.
2. A read-only member roster — who's in this organization — visible to any member, backed by one new cheap query against existing data (`users.organization_id`), not a new membership model.
3. Org rename, since it's a one-field, zero-risk addition once a settings page exists to put it on, and `Organization.name` already exists and is currently unset-and-unsettable from anywhere.

## Non-goals

- Org creation, org switching, multi-org support, invite-to-org flows — no backend exists for any of this, and building it is explicitly deferred by ADR 0029 to future RBAC work, not reconsidered here.
- Removing a user from an org, or moving a user between orgs — no such operation exists server-side (a user's `organization_id` is set once at provisioning); not adding one here.
- Any new policy beyond `approval_required_goals` — the `policies` JSONB is free-form, but inventing new policy keys with no consumer anywhere in the planning engine or elsewhere is pure speculation; only surface what's actually read today.

## Design

### Backend: two small additions

```python
# services/api/src/api/organizations_router.py

class OrganizationMemberOut(BaseModel):
    id: UUID
    username: str
    display_name: str
    role: str

@router.get("/me/members", response_model=list[OrganizationMemberOut])
async def list_organization_members(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    result = await db.execute(select(User).where(User.organization_id == current_user.organization_id).order_by(User.username))
    return list(result.scalars().all())


class OrganizationRenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)

@router.put("/me", response_model=OrganizationOut)
async def rename_organization(
    body: OrganizationRenameIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Organization:
    _require_admin(current_user)  # reuse the existing local helper already in this file
    org = await get_organization_for_user(db, current_user)
    org.name = body.name
    await db.commit()
    await db.refresh(org)
    return org
```

Member list is any authenticated org member (visibility, not a privileged action); rename stays admin-gated like the existing policy endpoint.

### Frontend

New `apps/web/src/routes/Settings.tsx` section (this file already exists and has sectioned settings — see existing dark-mode/date-format sections for the pattern to match), gated to render only when `current_user.role === "admin"` for the editable parts, always visible for the roster:

- Org name: text field, admin-editable, `PUT /organizations/me` on save (reuse the existing inline-edit pattern already in the design system — `.editable`/`edit-btn` — rather than a full form).
- Policy: `approval_required_goals` rendered as a multi-select `Combobox` (component already exists, used elsewhere for multi-value pickers) over the known goal-type vocabulary read from `planning_engine.py`'s existing default list; `PUT /organizations/me/policies` on save, admin-only.
- Member roster: a simple list (username, display name, role badge) from `GET /organizations/me/members` — no actions, just visibility, available to every member.

`apps/web/src/lib/api.ts` gains: `getOrganization()`, `renameOrganization(name)`, `listOrganizationMembers()`, `setOrganizationPolicies(policies)` (the last two may already partially exist given the backend endpoints predate this design — check before adding duplicates).

## Testing

- Backend `test_organizations_router.py` (existing): `GET /organizations/me/members` returns all users sharing the caller's `organization_id`, ordered by username; 401 unauthenticated. `PUT /organizations/me` renames for admin, 403 for non-admin, 400/422 on empty name.
- Frontend `Settings.test.tsx` (existing): org section renders name + roster for a non-admin (read-only, no edit controls); admin sees editable name field and policy picker; saving calls the right endpoints and shows a success toast.
