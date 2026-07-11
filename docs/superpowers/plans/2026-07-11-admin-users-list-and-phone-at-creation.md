# Admin: user list + phone-at-creation — Implementation Plan

## Context

Live review of the Admin/Beheer "Users" tab surfaced two real gaps:

1. **No way to see existing users.** `POST /admin/users` (create) is the
   only user-management endpoint on the backend — there is no `GET`. The
   tab has always been add-only (ADR 0048), with 794 real users and no
   way to browse them.
2. **No phone number at creation.** `AdminUserCreate` has no
   `phone_number` field. This half is not a fresh idea — it is Phase 4
   of `docs/superpowers/specs/2026-07-10-unified-chat-consolidation-design.md`
   ("Phone-at-creation + onboarding"), already fully designed and marked
   independent of that spec's other phases, just never built.

This plan implements both: the list view is new design (below); the
phone-at-creation/onboarding piece follows the existing spec's Phase 4
verbatim.

## Global Constraints

- Follow existing patterns: functional components, `useTranslation()`/`t()`
  for all copy, Tailwind design tokens, no new dependencies.
- Every new user-facing string needs matching keys in `en.json`, `nl.json`,
  `de.json` (see this project's own established i18n discipline).
- LDAP is the identity source; Postgres is the authorization source
  (`auth.py`'s own stated division). The phone-at-creation table stays a
  Postgres-only concern — the LDAP entry is untouched.
- Run the full test suite (backend + frontend) before considering any
  task done.

## Task 1: Migration — `pending_user_phone_numbers` table + `phone_prompt_dismissed` column

New Alembic migration (inline SQL, no app-code imports, matching every
prior migration's own stated reason: `alembic heads`/`upgrade head`
resolves the whole revision graph before `env.py`'s `sys.path` hack runs):

```sql
CREATE TABLE pending_user_phone_numbers (
    username VARCHAR(255) PRIMARY KEY,
    phone_number VARCHAR(32) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE users ADD COLUMN phone_prompt_dismissed BOOLEAN NOT NULL DEFAULT false;
```

Add both to `services/api/src/api/models.py`:
- `PendingUserPhoneNumber` model (`username` PK, `phone_number`, `created_at`).
- `User.phone_prompt_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)`.

## Task 2: Backend — phone-at-creation (spec Phase 4, verbatim)

`services/api/src/api/auth.py`:
- Extract the E.164 check already in `link_phone_number` (lines 156-159)
  into a shared `validate_phone_number(phone: str) -> str` (strip +
  validate, raise `HTTPException(400, ...)` on failure, return the
  cleaned value) — call it from both `link_phone_number` and the new
  admin path, so the rule exists once.
- `_get_or_provision_user`: when creating a brand-new `User` row, query
  `PendingUserPhoneNumber` by `identity.username` first. If found, set
  `phone_number` on the new `User` from it and delete the pending row in
  the same transaction (read + consume, not just read).
- New endpoint `PATCH /auth/me/dismiss-phone-prompt` — no request body,
  sets `current_user.phone_prompt_dismissed = True`, commits, returns
  `UserOut` (same shape as `GET /auth/me` / `PUT /auth/me/phone`).
- `UserOut` gains `phone_prompt_dismissed: bool` so the frontend knows
  whether to show the onboarding prompt without a second round trip.

`services/api/src/api/admin_router.py`:
- `AdminUserCreate` gains `phone_number: str | None = None`.
- `admin_create_user` gains `db: AsyncSession = Depends(get_db)` (it
  currently only touches LDAP, never Postgres). After a successful
  `ldap_create_user` call, if `body.phone_number` was given: validate it
  (shared validator), insert a `PendingUserPhoneNumber` row for
  `body.username`. Wrap in try/except for `IntegrityError` (phone already
  pending/linked elsewhere) → 409, matching `link_phone_number`'s own
  conflict handling.

## Task 3: Backend — `GET /admin/users` list endpoint (new design, not in the spec)

`services/api/src/api/admin_router.py`:

```python
class AdminUserOut(BaseModel):
    id: UUID
    username: str
    display_name: str
    email: str | None
    role: str
    phone_number: str | None
    created_at: datetime
    last_login_at: datetime | None

@router.get("/users", response_model=list[AdminUserOut])
async def admin_list_users(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[User]:
    _require_admin(current_user)
    result = await db.execute(
        select(User).order_by(User.created_at.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())
```

Mirrors `list_documents`' own limit/offset/ordering shape exactly — no
new pagination pattern invented. 794 rows means the frontend needs at
least a "load more" affordance (see Task 5), not a single unpaginated
fetch.

## Task 4: Frontend — API client + phone field on the create form

`apps/web/src/lib/api.ts`: add `AdminUserOut` type, `listAdminUsers(limit?, offset?)`,
extend `createAdminUser`'s request type with optional `phone_number`,
add `dismissPhonePrompt()` calling the new `PATCH` endpoint.

`apps/web/src/routes/AdminDashboard.tsx` (`UsersTab`): add a phone-number
`TextField` (reuse the shared `apps/web/src/components/ui/form.tsx`
component, optional field, E.164 placeholder) to the existing add-user
form, submitted as part of the same request.

## Task 5: Frontend — user list table

`AdminDashboard.tsx` (`UsersTab`): below the add-user button, a
`DataTable` (reuse the shared component, same one `Workspace.tsx` uses)
listing username / display name / email / role / phone / created date,
with a "Load more" button appending the next page (`offset += limit`)
rather than a full pager, given the mostly-append-only, rarely-searched
nature of this data. Fetch on mount and after a successful create (new
user should appear without a manual refresh).

## Task 6: Frontend — onboarding prompt

New `apps/web/src/components/PhonePromptModal.tsx`: reuses the shared
`Modal` + `TextField` + `Button` components. Shown from `App.tsx`
(alongside the existing top-level providers) when
`user.phone_number == null && !user.phone_prompt_dismissed` — two
actions: "Set phone number" (calls existing `PUT /auth/me/phone`,
reusing its E.164 validation error display) or "Skip" (calls the new
`dismissPhonePrompt()`). Users who already have a phone number, or who
already dismissed the prompt, never see it — driven directly off the
`UserOut` fields already returned by `GET /auth/me`, no extra request.

## Testing

- **Task 1**: migration applies cleanly on top of the current head;
  verified via a real `alembic upgrade head` against the local Postgres.
- **Task 2**: extend `test_auth.py` — dismiss-phone-prompt sets the flag
  and returns it in the response; `_get_or_provision_user` consumes a
  pending phone number on first login and deletes the row (a second
  login for the same username must not re-apply it); admin-create with a
  phone creates the pending row; admin-create with a duplicate/invalid
  phone number 409s/400s.
- **Task 3**: new `test_admin_router.py` case — list returns users
  ordered newest-first, respects limit/offset, 403s for non-admin.
- **Task 4/5/6**: component tests following this session's established
  pattern (mock the API client, assert on rendered text/behavior, not
  implementation details). Real local-Postgres verification for the
  full create→appears-in-list→first-login→phone-attached round trip
  where practical (matches ADR 0061's own stated lesson: "verified via
  live testing, not just unit tests" is the standard for this exact bug
  class in this project).

## Verification

Full backend + frontend suite green, zero non-test typecheck errors
(both languages), full three-locale i18n key parity, and — since this
touches first-login provisioning, a security-adjacent path already
fixed once this session (ADR 0062) — a real live smoke test: create a
user with a phone via the admin form, confirm it appears in the list
immediately, log in as that user for the first time, confirm the phone
number attached automatically and the onboarding prompt does NOT show
(since a phone is already set), then separately create a user with no
phone and confirm the prompt DOES show and both its actions work.
