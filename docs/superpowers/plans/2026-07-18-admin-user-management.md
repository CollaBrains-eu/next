# Admin User-Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give admins the ability to change a user's role, reset their password, deactivate them, and set/clear their linked Signal phone number from the Admin Dashboard's Users tab — closing the gap against the v2 reference implementation identified in `docs/superpowers/specs/2026-07-18-admin-user-management-design.md`.

**Architecture:** Four new admin-only FastAPI endpoints on the existing `/admin/users/{user_id}` resource, backed by two new LDAP admin-bind functions (mirroring the existing `create_user`) and one new `users.is_active` Postgres column. The frontend adds a per-row action menu to the existing `DataTable` in `AdminDashboard.tsx`'s `UsersTab`, reusing existing UI primitives (`Dropdown`, `Modal`, `Button`, `TextField`) — no new components except a small extraction of the existing one-time-password display into a shared piece reused by both create-user and reset-password.

**Tech Stack:** FastAPI + SQLAlchemy (async) + Alembic + `python-ldap3` (backend), React + TypeScript + Vitest (frontend), pytest + `httpx.AsyncClient` (backend tests).

## Global Constraints

- All four new endpoints require `current_user.role == "admin"` (`_require_admin`, already defined in `admin_router.py`) and refuse to act on `role == "service"` target users (403).
- Role changes and phone changes are Postgres-only (no LDAP write). Password reset and deactivate are LDAP-bind writes via `ldap_auth.py`, mirroring `create_user`'s existing admin-bind pattern exactly (bind as `cn=admin,{base_dn}`, `unbind()` in `finally`).
- Deactivation never deletes a Postgres `User` row or their content — only `is_active` flips to `false` plus the LDAP entry is removed. `owner_id`/`user_id`/`created_by` are `NOT NULL` FKs elsewhere; a hard delete is out of scope (see spec).
- Every new backend endpoint gets a pytest test in `services/api/tests/test_admin_router.py` following the file's existing `_login`/`_unique` helper pattern — do not invent new test scaffolding.
- Every new frontend interaction gets a test in `apps/web/src/routes/AdminDashboard.test.tsx` following the file's existing `vi.mock("../lib/api")` pattern.
- All new user-facing copy is added to all three locale files (`apps/web/src/locales/en.json`, `nl.json`, `de.json`) in the same task that introduces the copy — tests render the real i18next instance, so a missing key breaks the test, not just the UI.
- Backend tests run via `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -v` (pytest isn't in the built image — installed once per container lifetime with `docker compose exec -T api uv pip install --system --no-cache pytest pytest-asyncio`). Frontend tests run via `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run'`.
- Migrations chain onto the current head, `d3f8a1c6b9e4`.

---

### Task 1: `users.is_active` column + exposed in `AdminUserOut`

**Files:**
- Create: `services/api/alembic/versions/f4b8e2a6c9d1_add_is_active_to_users.py`
- Modify: `services/api/src/api/models.py` (`User` class)
- Modify: `services/api/src/api/admin_router.py` (`AdminUserOut`)
- Test: `services/api/tests/test_admin_router.py`

**Interfaces:**
- Produces: `User.is_active: bool` (default `True`), `AdminUserOut.is_active: bool` — every later task that reads/writes a user's active state depends on this column existing.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_admin_router.py` (after `test_admin_list_users_respects_limit`):

```python
async def test_admin_list_users_returns_is_active_true_for_new_users(client):
    username = _unique("activedefaultuser")
    await _login(client, username, is_admin=False)

    admin_token = await _login(client, _unique("activedefaultadmin"), is_admin=True)
    response = await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )
    assert response.status_code == 200
    row = next(r for r in response.json() if r["username"] == username)
    assert row["is_active"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k is_active_true_for_new_users -v`
Expected: FAIL with `KeyError: 'is_active'`

- [ ] **Step 3: Add the migration**

Create `services/api/alembic/versions/f4b8e2a6c9d1_add_is_active_to_users.py`:

```python
"""add is_active to users

Revision ID: f4b8e2a6c9d1
Revises: d3f8a1c6b9e4
Create Date: 2026-07-18

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4b8e2a6c9d1'
down_revision: Union[str, None] = 'd3f8a1c6b9e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    op.drop_column('users', 'is_active')
```

- [ ] **Step 4: Add the model field**

In `services/api/src/api/models.py`, in the `User` class, after the `phone_prompt_dismissed` line:

```python
    phone_prompt_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
```

- [ ] **Step 5: Expose it on `AdminUserOut`**

In `services/api/src/api/admin_router.py`, in the `AdminUserOut` class:

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
    is_active: bool

    class Config:
        from_attributes = True
```

- [ ] **Step 6: Apply the migration and run the test**

Run: `docker compose exec api alembic upgrade head`
Expected: `Running upgrade d3f8a1c6b9e4 -> f4b8e2a6c9d1, add is_active to users`

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k is_active_true_for_new_users -v`
Expected: PASS

- [ ] **Step 7: Run the full admin router test file to check nothing else broke**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -v`
Expected: all pass (existing tests build `AdminUserOut` fixtures in the frontend, not here — this file's own tests hit the real endpoint and don't hardcode the full response shape, so no other test should need changes)

- [ ] **Step 8: Commit**

```bash
git add services/api/alembic/versions/f4b8e2a6c9d1_add_is_active_to_users.py services/api/src/api/models.py services/api/src/api/admin_router.py services/api/tests/test_admin_router.py
git commit -m "feat(admin): add users.is_active column, expose on AdminUserOut"
```

---

### Task 2: LDAP admin-bind functions — `set_password` and `delete_user`

**Files:**
- Modify: `services/api/src/api/ldap_auth.py`

**Interfaces:**
- Consumes: nothing new (same `settings.ldap_*` config `create_user` already uses).
- Produces: `set_password(*, username: str) -> str` (returns the new temporary password), `delete_user(*, username: str) -> None`. Both raise `LdapAdminError` — Task 4/5 depend on catching this exact exception type, and on `delete_user`'s message containing `"does not exist"` when the entry is already gone (mirrors `create_user`'s own `"already exists"` string convention, which `admin_router.py` already string-matches on).

No dedicated pytest unit test for this task: the existing test suite never unit-tests `ldap_auth.py`'s raw `ldap3.Connection` calls directly (`create_user` itself has none — `test_admin_router.py` only ever mocks `api.admin_router.ldap_create_user` at the import boundary). Task 4 and Task 5's router tests provide that coverage the same way. Instead, this task is verified with a real smoke test against the actual `openldap` container already running in this stack — more rigorous than a mock, consistent with this project's live-verification bias (see ADR 0064).

- [ ] **Step 1: Add the two functions**

In `services/api/src/api/ldap_auth.py`, after the existing `create_user` function:

```python
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
```

- [ ] **Step 2: Add the one new import**

In `services/api/src/api/ldap_auth.py`, the existing import line is:

```python
from ldap3 import HASHED_SALTED_SHA, MODIFY_ADD, Connection, Server
```

Change it to:

```python
from ldap3 import HASHED_SALTED_SHA, MODIFY_ADD, MODIFY_REPLACE, Connection, Server
```

- [ ] **Step 3: Smoke-test against the real LDAP container**

Run this from the repo root on the server (creates a disposable LDAP user via the existing, already-proven `create_user`, exercises both new functions against it, cleans up):

```bash
docker compose exec -T -e PYTHONPATH=/app/src api python -c "
from api.ldap_auth import create_user, set_password, delete_user, LdapAdminError, authenticate

created = create_user(username='smoketest-adminmgmt', display_name='Smoke Test', email='smoke@collabrains.eu', is_admin=False)
assert authenticate('smoketest-adminmgmt', created.temporary_password) is not None, 'initial password does not work'

new_pw = set_password(username='smoketest-adminmgmt')
assert authenticate('smoketest-adminmgmt', new_pw) is not None, 'new password does not work'
assert authenticate('smoketest-adminmgmt', created.temporary_password) is None, 'old password still works'

delete_user(username='smoketest-adminmgmt')
assert authenticate('smoketest-adminmgmt', new_pw) is None, 'user still exists after delete'

try:
    delete_user(username='smoketest-adminmgmt')
    raise AssertionError('expected LdapAdminError on double-delete')
except LdapAdminError as e:
    assert 'does not exist' in str(e)

print('SMOKE TEST PASSED')
"
```

Expected: `SMOKE TEST PASSED` with no assertion errors.

- [ ] **Step 4: Commit**

```bash
git add services/api/src/api/ldap_auth.py
git commit -m "feat(admin): add set_password/delete_user LDAP admin-bind functions"
```

---

### Task 3: `PUT /admin/users/{user_id}/role`

**Files:**
- Modify: `services/api/src/api/admin_router.py`
- Test: `services/api/tests/test_admin_router.py`

**Interfaces:**
- Produces: `PUT /admin/users/{user_id}/role` accepting `{"role": "member" | "admin"}`, returns updated `AdminUserOut`. Frontend Task 9 depends on this exact path/body/response shape.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_admin_router.py`:

```python
async def test_set_role_requires_admin_role(client):
    # a random uuid is fine here -- the 403 for a non-admin caller must fire
    # before any user lookup happens
    token = await _login(client, _unique("setrolemember"), is_admin=False)
    response = await client.put(
        f"/admin/users/{uuid4()}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 403


async def test_set_role_updates_member_to_admin(client):
    username = _unique("promoteuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("promoteadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    response = await client.put(
        f"/admin/users/{target['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "admin"


async def test_set_role_unknown_user_returns_404(client):
    admin_token = await _login(client, _unique("rolenotfoundadmin"), is_admin=True)
    response = await client.put(
        f"/admin/users/{uuid4()}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "admin"},
    )
    assert response.status_code == 404


async def test_set_role_refuses_service_account(client):
    admin_token = await _login(client, _unique("rolesvcadmin"), is_admin=True)
    # signal-bot is a fixed service account seeded elsewhere in this suite's
    # shared dev DB; if it's ever absent this test is a no-op-safe skip.
    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    service_user = next((u for u in users if u["role"] == "service"), None)
    if service_user is None:
        return
    response = await client.put(
        f"/admin/users/{service_user['id']}/role",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"role": "member"},
    )
    assert response.status_code == 403
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k set_role -v`
Expected: FAIL with 404 (route not found) for all three

- [ ] **Step 3: Implement the endpoint**

In `services/api/src/api/admin_router.py`, add after `admin_resend_welcome` (end of file):

```python
class AdminUserRoleUpdate(BaseModel):
    role: Literal["member", "admin"]


@router.put("/users/{user_id}/role", response_model=AdminUserOut)
async def admin_set_user_role(
    user_id: UUID,
    body: AdminUserRoleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Change a user's role. Postgres-only -- role is documented (auth.py)
    as the authorization source of truth after first-login provisioning,
    not re-synced from LDAP group membership."""
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "service":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service accounts cannot be modified")

    user.role = body.role
    await db.commit()
    await db.refresh(user)
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k set_role -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/admin_router.py services/api/tests/test_admin_router.py
git commit -m "feat(admin): PUT /admin/users/{id}/role"
```

---

### Task 4: `PUT /admin/users/{user_id}/password`

**Files:**
- Modify: `services/api/src/api/admin_router.py`
- Test: `services/api/tests/test_admin_router.py`

**Interfaces:**
- Consumes: `ldap_auth.set_password` (Task 2), imported as `ldap_set_password` (matching the existing `create_user as ldap_create_user` import style, since `test_admin_router.py`'s established mocking convention patches at `api.admin_router.<imported-name>`).
- Produces: `PUT /admin/users/{user_id}/password` (no body), returns `AdminUserCreated` (`{username, temporary_password}` — reusing the existing schema, not a new one). Frontend Task 11 depends on this shape.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_admin_router.py`:

```python
async def test_reset_password_requires_admin_role(client):
    token = await _login(client, _unique("resetpwmember"), is_admin=False)
    response = await client.put(
        f"/admin/users/{uuid4()}/password", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


async def test_reset_password_returns_new_temporary_password(client):
    username = _unique("resetpwuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("resetpwadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    with patch("api.admin_router.ldap_set_password", return_value="a-new-temp-pw-999") as mock_reset:
        response = await client.put(
            f"/admin/users/{target['id']}/password", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["username"] == username
    assert body["temporary_password"] == "a-new-temp-pw-999"
    mock_reset.assert_called_once_with(username=username)


async def test_reset_password_unknown_user_returns_404(client):
    admin_token = await _login(client, _unique("resetpw404admin"), is_admin=True)
    response = await client.put(
        f"/admin/users/{uuid4()}/password", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k reset_password -v`
Expected: FAIL with 404 (route not found)

- [ ] **Step 3: Implement the endpoint**

In `services/api/src/api/admin_router.py`:

Change the import line:
```python
from api.ldap_auth import LdapAdminError
from api.ldap_auth import create_user as ldap_create_user
```
to:
```python
from api.ldap_auth import LdapAdminError
from api.ldap_auth import create_user as ldap_create_user
from api.ldap_auth import delete_user as ldap_delete_user
from api.ldap_auth import set_password as ldap_set_password
```

Add after the `admin_set_user_role` endpoint from Task 3:

```python
@router.put("/users/{user_id}/password", response_model=AdminUserCreated)
async def admin_reset_user_password(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AdminUserCreated:
    """Generate and return a new one-time temporary password for a user,
    same UX as user creation."""
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "service":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service accounts cannot be modified")

    try:
        new_password = ldap_set_password(username=user.username)
    except LdapAdminError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    return AdminUserCreated(username=user.username, temporary_password=new_password)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k reset_password -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/admin_router.py services/api/tests/test_admin_router.py
git commit -m "feat(admin): PUT /admin/users/{id}/password"
```

---

### Task 5: `DELETE /admin/users/{user_id}` (deactivate)

**Files:**
- Modify: `services/api/src/api/admin_router.py`
- Test: `services/api/tests/test_admin_router.py`

**Interfaces:**
- Consumes: `ldap_delete_user` (imported in Task 4).
- Produces: `DELETE /admin/users/{user_id}` → 204, sets `User.is_active = False`. Task 7 (`get_current_user`) and Task 12 (frontend deactivate UI) depend on this behavior.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_admin_router.py`:

```python
async def test_deactivate_requires_admin_role(client):
    token = await _login(client, _unique("deactivatemember"), is_admin=False)
    response = await client.delete(f"/admin/users/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_deactivate_sets_is_active_false(client):
    username = _unique("deactivateuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("deactivateadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    with patch("api.admin_router.ldap_delete_user") as mock_delete:
        response = await client.delete(
            f"/admin/users/{target['id']}", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 204
    mock_delete.assert_called_once_with(username=username)

    users_after = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    assert next(u for u in users_after if u["id"] == target["id"])["is_active"] is False


async def test_deactivate_is_idempotent_when_ldap_entry_already_gone(client):
    username = _unique("doubledeactivateuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("doubledeactivateadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    with patch(
        "api.admin_router.ldap_delete_user",
        side_effect=LdapAdminError(f"user {username!r} does not exist"),
    ):
        response = await client.delete(
            f"/admin/users/{target['id']}", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert response.status_code == 204


async def test_deactivate_unknown_user_returns_404(client):
    admin_token = await _login(client, _unique("deactivate404admin"), is_admin=True)
    response = await client.delete(f"/admin/users/{uuid4()}", headers={"Authorization": f"Bearer {admin_token}"})
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k deactivate -v`
Expected: FAIL with 404 (route not found)

- [ ] **Step 3: Implement the endpoint**

In `services/api/src/api/admin_router.py`, add after the Task 4 endpoint:

```python
@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def admin_deactivate_user(
    user_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    """Deactivate a user: removes their LDAP entry (so they can never log
    in again) and flips is_active so get_current_user rejects any
    still-unexpired JWT immediately. Does not touch their Postgres row or
    any content they created."""
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.role == "service":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Service accounts cannot be modified")

    try:
        ldap_delete_user(username=user.username)
    except LdapAdminError as exc:
        if "does not exist" not in str(exc).lower():
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc

    user.is_active = False
    await db.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k deactivate -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/admin_router.py services/api/tests/test_admin_router.py
git commit -m "feat(admin): DELETE /admin/users/{id} (deactivate)"
```

---

### Task 6: `PUT /admin/users/{user_id}/phone`

**Files:**
- Modify: `services/api/src/api/admin_router.py`
- Test: `services/api/tests/test_admin_router.py`

**Interfaces:**
- Consumes: `validate_phone_number` (already imported from `api.auth` in `admin_router.py`).
- Produces: `PUT /admin/users/{user_id}/phone` accepting `{"phone_number": str | None}`, returns `AdminUserOut`.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_admin_router.py`:

```python
async def test_set_phone_requires_admin_role(client):
    token = await _login(client, _unique("setphonemember"), is_admin=False)
    response = await client.put(
        f"/admin/users/{uuid4()}/phone",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone_number": "+15551234567"},
    )
    assert response.status_code == 403


async def test_set_phone_updates_number(client):
    username = _unique("setphoneuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("setphoneadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    response = await client.put(
        f"/admin/users/{target['id']}/phone",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "+15559998888"},
    )
    assert response.status_code == 200
    assert response.json()["phone_number"] == "+15559998888"


async def test_set_phone_clears_number_with_null(client):
    username = _unique("clearphoneuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("clearphoneadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    await client.put(
        f"/admin/users/{target['id']}/phone",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "+15550001111"},
    )
    response = await client.put(
        f"/admin/users/{target['id']}/phone",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": None},
    )
    assert response.status_code == 200
    assert response.json()["phone_number"] is None


async def test_set_phone_invalid_format_returns_400(client):
    username = _unique("badphoneadminsetuser")
    await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("badphoneadminset"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    response = await client.put(
        f"/admin/users/{target['id']}/phone",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "0491511234567"},
    )
    assert response.status_code == 400


async def test_set_phone_duplicate_returns_409(client):
    admin_token = await _login(client, _unique("dupphonesetadmin"), is_admin=True)

    username1 = _unique("dupphonesetuser1")
    await _login(client, username1, is_admin=False)
    username2 = _unique("dupphonesetuser2")
    await _login(client, username2, is_admin=False)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target1 = next(u for u in users if u["username"] == username1)
    target2 = next(u for u in users if u["username"] == username2)

    first = await client.put(
        f"/admin/users/{target1['id']}/phone",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "+15557778888"},
    )
    assert first.status_code == 200

    second = await client.put(
        f"/admin/users/{target2['id']}/phone",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "+15557778888"},
    )
    assert second.status_code == 409


async def test_set_phone_unknown_user_returns_404(client):
    admin_token = await _login(client, _unique("setphone404admin"), is_admin=True)
    response = await client.put(
        f"/admin/users/{uuid4()}/phone",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"phone_number": "+15551234567"},
    )
    assert response.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k set_phone -v`
Expected: FAIL with 404 (route not found)

- [ ] **Step 3: Implement the endpoint**

In `services/api/src/api/admin_router.py`, add after the Task 5 endpoint:

```python
class AdminUserPhoneUpdate(BaseModel):
    phone_number: str | None


@router.put("/users/{user_id}/phone", response_model=AdminUserOut)
async def admin_set_user_phone(
    user_id: UUID,
    body: AdminUserPhoneUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    """Admin override of the self-service /auth/me/phone endpoint --
    same validation and uniqueness rule, applied to a different user."""
    _require_admin(current_user)
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.phone_number = validate_phone_number(body.phone_number) if body.phone_number else None
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This phone number is already linked to another account",
        )

    await db.refresh(user)
    return user
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k set_phone -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/admin_router.py services/api/tests/test_admin_router.py
git commit -m "feat(admin): PUT /admin/users/{id}/phone"
```

---

### Task 7: `get_current_user` rejects deactivated users

**Files:**
- Modify: `services/api/src/api/auth.py`
- Test: `services/api/tests/test_admin_router.py`

**Interfaces:**
- Consumes: `User.is_active` (Task 1), `admin_deactivate_user` (Task 5).
- Produces: a deactivated user's existing JWT is rejected on their very next request, not just on future logins.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_admin_router.py`:

```python
async def test_deactivated_user_is_rejected_on_next_request(client):
    username = _unique("rejectedafterdeactivate")
    token = await _login(client, username, is_admin=False)
    admin_token = await _login(client, _unique("rejectdeactivateadmin"), is_admin=True)

    users = (await client.get(
        "/admin/users", headers={"Authorization": f"Bearer {admin_token}"}, params={"limit": 200}
    )).json()
    target = next(u for u in users if u["username"] == username)

    # sanity check: the token works before deactivation
    before = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert before.status_code == 200

    with patch("api.admin_router.ldap_delete_user"):
        deactivate_response = await client.delete(
            f"/admin/users/{target['id']}", headers={"Authorization": f"Bearer {admin_token}"}
        )
    assert deactivate_response.status_code == 204

    # the SAME still-unexpired token must now be rejected
    after = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert after.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k rejected_after_deactivate -v`
Expected: FAIL (`before.status_code == 200` passes, `after.status_code == 401` fails — the token still works)

- [ ] **Step 3: Implement the check**

In `services/api/src/api/auth.py`, in `get_current_user`, change:

```python
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_error
    return user
```

to:

```python
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise credentials_error
    return user
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests/test_admin_router.py -k rejected_after_deactivate -v`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests -v 2>&1 | tail -40`
Expected: all pass except the two pre-existing, unrelated failures already documented in ADR 0061 (`test_upload_triggers_vehicle_detection_and_creates_entity`, `test_extract_entities_deduplicates_by_case_insensitive_name_and_type`) — if any *other* test fails, stop and investigate before continuing.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/auth.py services/api/tests/test_admin_router.py
git commit -m "fix(auth): reject deactivated users in get_current_user"
```

---

### Task 8: Frontend API client — four new functions + `is_active`

**Files:**
- Modify: `apps/web/src/lib/api.ts`

**Interfaces:**
- Produces: `setUserRole(id: string, role: "member" | "admin"): Promise<AdminUserOut>`, `resetUserPassword(id: string): Promise<AdminUserCreatedOut>`, `deactivateUser(id: string): Promise<void>`, `setUserPhone(id: string, phoneNumber: string | null): Promise<AdminUserOut>`. Tasks 9-12 depend on these exact names/signatures. `AdminUserOut.is_active: boolean` — Tasks 9-12 depend on this field.

- [ ] **Step 1: Add `is_active` to the existing type**

In `apps/web/src/lib/api.ts`, change:

```typescript
export interface AdminUserOut {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  phone_number: string | null;
  created_at: string;
  last_login_at: string | null;
}
```

to:

```typescript
export interface AdminUserOut {
  id: string;
  username: string;
  display_name: string;
  email: string | null;
  role: string;
  phone_number: string | null;
  created_at: string;
  last_login_at: string | null;
  is_active: boolean;
}
```

- [ ] **Step 2: Add the four functions**

In `apps/web/src/lib/api.ts`, immediately after `listAdminUsers`:

```typescript
export function setUserRole(userId: string, role: "member" | "admin"): Promise<AdminUserOut> {
  return request<AdminUserOut>(`/admin/users/${userId}/role`, {
    method: "PUT",
    body: JSON.stringify({ role }),
  });
}

export function resetUserPassword(userId: string): Promise<AdminUserCreatedOut> {
  return request<AdminUserCreatedOut>(`/admin/users/${userId}/password`, { method: "PUT" });
}

export function deactivateUser(userId: string): Promise<void> {
  return request<void>(`/admin/users/${userId}`, { method: "DELETE" });
}

export function setUserPhone(userId: string, phoneNumber: string | null): Promise<AdminUserOut> {
  return request<AdminUserOut>(`/admin/users/${userId}/phone`, {
    method: "PUT",
    body: JSON.stringify({ phone_number: phoneNumber }),
  });
}
```

- [ ] **Step 3: Update existing test fixtures to include `is_active`**

In `apps/web/src/routes/AdminDashboard.test.tsx`, every hand-written `AdminUserOut`-shaped object literal needs `is_active: true` added (there are three: the `it("lists existing users", ...)` test's single-user array, and the two arrays in the `it("shows a load-more button...")` test). For example, change:

```typescript
      {
        id: "u1", username: "alice", display_name: "Alice", email: "alice@collabrains.eu",
        role: "member", phone_number: "+15551230001", created_at: "2026-01-01T00:00:00Z", last_login_at: null,
      },
```

to:

```typescript
      {
        id: "u1", username: "alice", display_name: "Alice", email: "alice@collabrains.eu",
        role: "member", phone_number: "+15551230001", created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
```

Do the same for the `fullPage` array (`Array.from({ length: 50 }, (_, i) => ({ ... }))`) and the trailing single-item array in the same test — add `is_active: true` to each object literal.

- [ ] **Step 4: Run the frontend suite**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx'`
Expected: all existing tests still pass (this task only adds fields/functions, no behavior change yet)

Run: `docker compose exec web sh -c 'cd /app/apps/web && npx tsc --noEmit'`
Expected: no new type errors

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/routes/AdminDashboard.test.tsx
git commit -m "feat(admin): add is_active field and 4 new admin-users API client functions"
```

---

### Task 9: Row-action menu + role change

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`
- Test: `apps/web/src/routes/AdminDashboard.test.tsx`

**Interfaces:**
- Consumes: `setUserRole` (Task 8), `Dropdown`/`DropdownOption` (`components/ui/Dropdown`, existing).
- Produces: a `<Dropdown>` per row in the Users table, with a "Change role" option. Tasks 10-12 each add one more option to this same dropdown.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/AdminDashboard.test.tsx`, extend the `vi.mock` block's function list:

```typescript
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getAdminStats: vi.fn(),
    getAdminAiUsage: vi.fn(),
    getAdminHealth: vi.fn(),
    listBugReports: vi.fn(),
    createAdminUser: vi.fn(),
    listAdminUsers: vi.fn(),
    setUserRole: vi.fn(),
    resetUserPassword: vi.fn(),
    deactivateUser: vi.fn(),
    setUserPhone: vi.fn(),
  };
});
```

Add a new test:

```typescript
  it("changes a member's role to admin via the row action menu", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserRole).mockResolvedValue({
      id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
      role: "admin", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
      is_active: true,
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Make admin" }));

    await waitFor(() => expect(api.setUserRole).toHaveBeenCalledWith("u1", "admin"));
  });

  it("shows an inline error when role change fails", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserRole).mockRejectedValue(new api.ApiError(500, "boom"));
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Make admin" }));

    expect(await screen.findByText("Failed to update role")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx -t "role"'`
Expected: FAIL — no "Actions" button exists yet

- [ ] **Step 3: Add locale keys**

In `apps/web/src/locales/en.json`, in the `admin` object, after `"loadMore": "Load more"`:

```json
  "loadMore": "Load more",
  "rowActions": "Actions",
  "makeAdmin": "Make admin",
  "makeMember": "Make member",
  "roleUpdateError": "Failed to update role"
```

In `apps/web/src/locales/nl.json`, same position:

```json
  "loadMore": "Meer laden",
  "rowActions": "Acties",
  "makeAdmin": "Beheerder maken",
  "makeMember": "Lid maken",
  "roleUpdateError": "Kon rol niet bijwerken"
```

In `apps/web/src/locales/de.json`, same position:

```json
  "loadMore": "Mehr laden",
  "rowActions": "Aktionen",
  "makeAdmin": "Zum Administrator machen",
  "makeMember": "Zum Mitglied machen",
  "roleUpdateError": "Rolle konnte nicht aktualisiert werden"
```

(Remember to add a trailing comma after `"loadMore"`'s value in each file since more keys follow, and remove the trailing comma from whichever key was previously last if these are appended at the true end of the `admin` object — check the file to place correctly.)

- [ ] **Step 4: Implement the row-action column**

In `apps/web/src/routes/AdminDashboard.tsx`:

Add to the imports:

```typescript
import { Dropdown, type DropdownOption } from "../components/ui/Dropdown";
```

and add `setUserRole` to the `../lib/api` import list (alongside `createAdminUser`, `listAdminUsers`, etc.).

In the `UsersTab` function, add state for a per-row error message, right after the existing `usersError` state:

```typescript
  const [rowError, setRowError] = useState<string | null>(null);
```

Add a handler function inside `UsersTab`, before the `columns` array:

```typescript
  async function handleRoleChange(user: AdminUserOut, role: "member" | "admin") {
    setRowError(null);
    try {
      const updated = await setUserRole(user.id, role);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : t("admin.roleUpdateError"));
    }
  }
```

Add a new column to the `columns` array, after the `created_at` column:

```typescript
    {
      key: "actions",
      header: "",
      render: (row) => {
        if (row.role === "service") return null;
        const options: DropdownOption[] = [
          {
            label: row.role === "admin" ? t("admin.makeMember") : t("admin.makeAdmin"),
            onSelect: () => handleRoleChange(row, row.role === "admin" ? "member" : "admin"),
          },
        ];
        return (
          <Dropdown
            trigger={
              <span className="rounded-lg px-2 py-1 text-xs text-ink-3 hover:bg-hover hover:text-ink">
                {t("admin.rowActions")}
              </span>
            }
            options={options}
          />
        );
      },
    },
```

Render `rowError` just above the `DataTable` (after the `usersError`/`usersLoading` conditional block that wraps the table, right before `<DataTable ...>`):

```typescript
          {rowError && <p className="text-sm text-danger">{rowError}</p>}
          <DataTable columns={columns} rows={users} rowKey={(row) => row.id} pageSize={Math.max(users.length, 1)} />
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx'`
Expected: all pass, including the two new role tests

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): row-action menu with role change on Users tab"
```

---

### Task 10: Set-phone action

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`
- Test: `apps/web/src/routes/AdminDashboard.test.tsx`

**Interfaces:**
- Consumes: `setUserPhone` (Task 8), `Modal`, `TextField` (existing).
- Produces: a "Set phone" option added to the same `Dropdown` from Task 9, opening a small modal.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/AdminDashboard.test.tsx`:

```typescript
  it("sets a user's phone number via the row action menu", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserPhone).mockResolvedValue({
      id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
      role: "member", phone_number: "+15551239999", created_at: "2026-01-01T00:00:00Z", last_login_at: null,
      is_active: true,
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Set phone" }));

    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+15551239999" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(api.setUserPhone).toHaveBeenCalledWith("u1", "+15551239999"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("shows an error inside the phone modal when the save fails", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.setUserPhone).mockRejectedValue(new api.ApiError(409, "Already linked"));
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Set phone" }));
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "+15551239999" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Already linked")).toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx -t "phone"'`
Expected: FAIL — no "Set phone" menu item exists yet

- [ ] **Step 3: Add locale keys**

In `apps/web/src/locales/en.json`, `admin` object, after the Task 9 keys:

```json
  "roleUpdateError": "Failed to update role",
  "setPhone": "Set phone",
  "phoneModalTitle": "Set phone number",
  "save": "Save",
  "phoneUpdateError": "Failed to update phone number"
```

`nl.json`:

```json
  "roleUpdateError": "Kon rol niet bijwerken",
  "setPhone": "Telefoon instellen",
  "phoneModalTitle": "Telefoonnummer instellen",
  "save": "Opslaan",
  "phoneUpdateError": "Kon telefoonnummer niet bijwerken"
```

`de.json`:

```json
  "roleUpdateError": "Rolle konnte nicht aktualisiert werden",
  "setPhone": "Telefon festlegen",
  "phoneModalTitle": "Telefonnummer festlegen",
  "save": "Speichern",
  "phoneUpdateError": "Telefonnummer konnte nicht aktualisiert werden"
```

- [ ] **Step 4: Implement the phone modal**

In `apps/web/src/routes/AdminDashboard.tsx`, add `setUserPhone` to the `../lib/api` import list.

In `UsersTab`, add state after `rowError`:

```typescript
  const [phoneModalUser, setPhoneModalUser] = useState<AdminUserOut | null>(null);
  const [phoneInput, setPhoneInput] = useState("");
  const [phoneError, setPhoneError] = useState<string | null>(null);
  const [phoneSaving, setPhoneSaving] = useState(false);
```

Add a handler, next to `handleRoleChange`:

```typescript
  async function handleSavePhone() {
    if (!phoneModalUser) return;
    setPhoneSaving(true);
    setPhoneError(null);
    try {
      const updated = await setUserPhone(phoneModalUser.id, phoneInput.trim() || null);
      setUsers((prev) => prev.map((u) => (u.id === updated.id ? updated : u)));
      setPhoneModalUser(null);
    } catch (err) {
      setPhoneError(err instanceof ApiError ? err.message : t("admin.phoneUpdateError"));
    } finally {
      setPhoneSaving(false);
    }
  }
```

In the `columns` array's `actions` column `render`, add a second option to the `options` array (after the role-change option):

```typescript
          {
            label: t("admin.setPhone"),
            onSelect: () => {
              setPhoneModalUser(row);
              setPhoneInput(row.phone_number ?? "");
              setPhoneError(null);
            },
          },
```

Add the modal in the JSX, right after the existing `<Modal open={formOpen} ...>` block (the create-user modal):

```typescript
      <Modal
        open={phoneModalUser !== null}
        onClose={() => setPhoneModalUser(null)}
        title={t("admin.phoneModalTitle")}
      >
        <div className="flex flex-col gap-3">
          {phoneError && <p className="text-sm text-danger">{phoneError}</p>}
          <TextField label={t("admin.phoneColumn")} value={phoneInput} onChange={setPhoneInput} placeholder="+491511234567" />
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setPhoneModalUser(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="button" size="sm" disabled={phoneSaving} onClick={handleSavePhone}>
              {t("admin.save")}
            </Button>
          </div>
        </div>
      </Modal>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx'`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): set-phone action on Users tab"
```

---

### Task 11: Reset-password action (shared temp-password display)

**Files:**
- Create: `apps/web/src/components/TempPasswordCard.tsx`
- Create: `apps/web/src/components/TempPasswordCard.test.tsx`
- Modify: `apps/web/src/routes/AdminDashboard.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`
- Test: `apps/web/src/routes/AdminDashboard.test.tsx`

**Interfaces:**
- Produces: `TempPasswordCard({ message, password, onDismiss }: { message: string; password: string; onDismiss: () => void })` — a extraction of the existing inline create-user temp-password `Card`, reused by both create-user and reset-password.

- [ ] **Step 1: Write the failing test for the extracted component**

Create `apps/web/src/components/TempPasswordCard.test.tsx`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { TempPasswordCard } from "./TempPasswordCard";

describe("TempPasswordCard", () => {
  it("renders the message and password, and calls onDismiss", () => {
    const onDismiss = vi.fn();
    render(<TempPasswordCard message="User bob created." password="a-temp-pw" onDismiss={onDismiss} />);

    expect(screen.getByText("User bob created.")).toBeInTheDocument();
    expect(screen.getByTestId("temp-password")).toHaveTextContent("a-temp-pw");

    fireEvent.click(screen.getByRole("button"));
    expect(onDismiss).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/components/TempPasswordCard.test.tsx'`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Extract the component**

Create `apps/web/src/components/TempPasswordCard.tsx` (this is the exact markup currently inline in `AdminDashboard.tsx`'s `UsersTab`, generalized to take `message` instead of hardcoding the create-user copy):

```typescript
import { useTranslation } from "react-i18next";
import Card from "./Card";
import { Button } from "./ui/Button";

export function TempPasswordCard({
  message,
  password,
  onDismiss,
}: {
  message: string;
  password: string;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  return (
    <Card className="flex flex-col gap-2 border-accent">
      <p className="text-sm font-medium text-ink">{message}</p>
      <p className="text-xs text-ink-3">{t("admin.tempPasswordHint")}</p>
      <code className="rounded-lg bg-accent-soft px-3 py-2 text-sm text-ink" data-testid="temp-password">
        {password}
      </code>
      <div>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          {t("admin.dismiss")}
        </Button>
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/components/TempPasswordCard.test.tsx'`
Expected: PASS

- [ ] **Step 5: Write the failing tests for the reset-password action**

Add to `apps/web/src/routes/AdminDashboard.test.tsx`:

```typescript
  it("resets a user's password via the row action menu and shows it once", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.resetUserPassword).mockResolvedValue({
      username: "bob", temporary_password: "reset-pw-456",
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Reset password" }));

    await waitFor(() => expect(api.resetUserPassword).toHaveBeenCalledWith("u1"));
    expect(await screen.findByTestId("temp-password")).toHaveTextContent("reset-pw-456");
    expect(screen.getByText("Password reset for bob.")).toBeInTheDocument();
  });

  it("shows an inline error when password reset fails", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.resetUserPassword).mockRejectedValue(new api.ApiError(502, "LDAP unreachable"));
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Reset password" }));

    expect(await screen.findByText("LDAP unreachable")).toBeInTheDocument();
  });
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx -t "password"'`
Expected: FAIL — no "Reset password" menu item exists yet

- [ ] **Step 7: Add locale keys**

`en.json`, after the Task 10 keys:

```json
  "phoneUpdateError": "Failed to update phone number",
  "resetPassword": "Reset password",
  "passwordReset": "Password reset for {{username}}.",
  "resetPasswordError": "Failed to reset password"
```

`nl.json`:

```json
  "phoneUpdateError": "Kon telefoonnummer niet bijwerken",
  "resetPassword": "Wachtwoord resetten",
  "passwordReset": "Wachtwoord gereset voor {{username}}.",
  "resetPasswordError": "Kon wachtwoord niet resetten"
```

`de.json`:

```json
  "phoneUpdateError": "Telefonnummer konnte nicht aktualisiert werden",
  "resetPassword": "Passwort zurücksetzen",
  "passwordReset": "Passwort zurückgesetzt für {{username}}.",
  "resetPasswordError": "Passwort konnte nicht zurückgesetzt werden"
```

- [ ] **Step 8: Wire up reset-password, and switch the existing create-user card to `TempPasswordCard`**

In `apps/web/src/routes/AdminDashboard.tsx`, add `resetUserPassword` to the `../lib/api` import list, and add the new import:

```typescript
import { TempPasswordCard } from "../components/TempPasswordCard";
```

Replace the existing `created` state's rendering. Currently:

```typescript
  const [created, setCreated] = useState<AdminUserCreatedOut | null>(null);
```

Change to hold both the credential and a display message:

```typescript
  const [tempPassword, setTempPassword] = useState<{ message: string; password: string } | null>(null);
```

Update `handleSubmit` (create-user form) — change:

```typescript
      setFormOpen(false);
      resetForm();
      setCreated(result);
      loadUsers(0);
```

to:

```typescript
      setFormOpen(false);
      resetForm();
      setTempPassword({ message: t("admin.userCreated", { username: result.username }), password: result.temporary_password });
      loadUsers(0);
```

Replace the existing inline `{created && (<Card>...)}` block:

```typescript
      {created && (
        <Card className="flex flex-col gap-2 border-accent">
          <p className="text-sm font-medium text-ink">
            {t("admin.userCreated", { username: created.username })}
          </p>
          <p className="text-xs text-ink-3">{t("admin.tempPasswordHint")}</p>
          <code className="rounded-lg bg-accent-soft px-3 py-2 text-sm text-ink" data-testid="temp-password">
            {created.temporary_password}
          </code>
          <div>
            <Button size="sm" variant="ghost" onClick={() => setCreated(null)}>
              {t("admin.dismiss")}
            </Button>
          </div>
        </Card>
      )}
```

with:

```typescript
      {tempPassword && (
        <TempPasswordCard
          message={tempPassword.message}
          password={tempPassword.password}
          onDismiss={() => setTempPassword(null)}
        />
      )}
```

Now `Card` may be unused elsewhere in this file — check with a quick `grep -n '<Card' apps/web/src/routes/AdminDashboard.tsx`; the `OverviewTab` and `HealthTab` functions still use it, so keep the import.

Add a handler next to `handleSavePhone`:

```typescript
  async function handleResetPassword(user: AdminUserOut) {
    setRowError(null);
    try {
      const result = await resetUserPassword(user.id);
      setTempPassword({ message: t("admin.passwordReset", { username: result.username }), password: result.temporary_password });
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : t("admin.resetPasswordError"));
    }
  }
```

Add a third option to the `options` array in the `actions` column (after "Set phone"):

```typescript
          {
            label: t("admin.resetPassword"),
            onSelect: () => handleResetPassword(row),
          },
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx src/components/TempPasswordCard.test.tsx'`
Expected: all pass (including the pre-existing create-user temp-password tests, now exercising the shared component)

- [ ] **Step 10: Commit**

```bash
git add apps/web/src/components/TempPasswordCard.tsx apps/web/src/components/TempPasswordCard.test.tsx apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): reset-password action, extract shared TempPasswordCard"
```

---

### Task 12: Deactivate action

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`
- Test: `apps/web/src/routes/AdminDashboard.test.tsx`

**Interfaces:**
- Consumes: `deactivateUser` (Task 8), `Modal` (existing).
- Produces: a "Deactivate" option on the row menu, a confirm modal, and deactivated rows rendered grayed-out with a badge instead of being removed.

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/src/routes/AdminDashboard.test.tsx`:

```typescript
  it("deactivates a user via the row action menu after confirming", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    vi.mocked(api.deactivateUser).mockResolvedValue(undefined);
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Deactivate" }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("Deactivate Bob? They will be signed out immediately and can no longer log in. Their documents and cases are kept.")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));

    await waitFor(() => expect(api.deactivateUser).toHaveBeenCalledWith("u1"));
    expect(await screen.findByText("Deactivated")).toBeInTheDocument();
  });

  it("does not deactivate when the confirm dialog is cancelled", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "bob", display_name: "Bob", email: "bob@collabrains.eu",
        role: "member", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("bob");
    fireEvent.click(screen.getByRole("button", { name: "Actions" }));
    fireEvent.click(screen.getByRole("menuitem", { name: "Deactivate" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(api.deactivateUser).not.toHaveBeenCalled();
  });

  it("hides the action menu for service accounts", async () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    vi.mocked(api.listAdminUsers).mockResolvedValue([
      {
        id: "u1", username: "signal-bot", display_name: "CollaBrains Signal Bot", email: null,
        role: "service", phone_number: null, created_at: "2026-01-01T00:00:00Z", last_login_at: null,
        is_active: true,
      },
    ]);
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("button", { name: "Users" }));

    await screen.findByText("signal-bot");
    expect(screen.queryByRole("button", { name: "Actions" })).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx -t "eactivat"'`
Expected: FAIL — no "Deactivate" menu item exists yet (third test currently passes already since the service-account guard was added in Task 9 — that's fine, it's re-asserting existing behavior in this task's context)

- [ ] **Step 3: Add locale keys**

`en.json`:

```json
  "resetPasswordError": "Failed to reset password",
  "deactivate": "Deactivate",
  "deactivateConfirmTitle": "Deactivate user?",
  "deactivateConfirmBody": "Deactivate {{displayName}}? They will be signed out immediately and can no longer log in. Their documents and cases are kept.",
  "deactivateError": "Failed to deactivate user",
  "deactivatedBadge": "Deactivated"
```

`nl.json`:

```json
  "resetPasswordError": "Kon wachtwoord niet resetten",
  "deactivate": "Deactiveren",
  "deactivateConfirmTitle": "Gebruiker deactiveren?",
  "deactivateConfirmBody": "{{displayName}} deactiveren? Deze persoon wordt direct uitgelogd en kan niet meer inloggen. Diens documenten en zaken blijven bewaard.",
  "deactivateError": "Kon gebruiker niet deactiveren",
  "deactivatedBadge": "Gedeactiveerd"
```

`de.json`:

```json
  "resetPasswordError": "Passwort konnte nicht zurückgesetzt werden",
  "deactivate": "Deaktivieren",
  "deactivateConfirmTitle": "Benutzer deaktivieren?",
  "deactivateConfirmBody": "{{displayName}} deaktivieren? Diese Person wird sofort abgemeldet und kann sich nicht mehr anmelden. Ihre Dokumente und Fälle bleiben erhalten.",
  "deactivateError": "Benutzer konnte nicht deaktiviert werden",
  "deactivatedBadge": "Deaktiviert"
```

- [ ] **Step 4: Implement the deactivate flow**

In `apps/web/src/routes/AdminDashboard.tsx`, add `deactivateUser` to the `../lib/api` import list.

In `UsersTab`, add state after `phoneSaving`:

```typescript
  const [deactivateTarget, setDeactivateTarget] = useState<AdminUserOut | null>(null);
  const [deactivating, setDeactivating] = useState(false);
```

Add a handler next to `handleResetPassword`:

```typescript
  async function handleDeactivate() {
    if (!deactivateTarget) return;
    setDeactivating(true);
    setRowError(null);
    try {
      await deactivateUser(deactivateTarget.id);
      setUsers((prev) => prev.map((u) => (u.id === deactivateTarget.id ? { ...u, is_active: false } : u)));
      setDeactivateTarget(null);
    } catch (err) {
      setRowError(err instanceof ApiError ? err.message : t("admin.deactivateError"));
    } finally {
      setDeactivating(false);
    }
  }
```

Update the `role` column's `render` to show a "Deactivated" badge alongside the role badge when `!row.is_active`:

```typescript
    {
      key: "role",
      header: t("admin.roleColumn"),
      render: (row) => (
        <div className="flex items-center gap-1.5">
          <Badge variant={row.role === "admin" ? "warning" : "default"}>{row.role}</Badge>
          {!row.is_active && <Badge variant="danger">{t("admin.deactivatedBadge")}</Badge>}
        </div>
      ),
    },
```

Update the `actions` column's `render` to hide the menu for already-deactivated rows too (nothing left to do once deactivated), and add the fourth option:

```typescript
      render: (row) => {
        if (row.role === "service" || !row.is_active) return null;
        const options: DropdownOption[] = [
          {
            label: row.role === "admin" ? t("admin.makeMember") : t("admin.makeAdmin"),
            onSelect: () => handleRoleChange(row, row.role === "admin" ? "member" : "admin"),
          },
          {
            label: t("admin.setPhone"),
            onSelect: () => {
              setPhoneModalUser(row);
              setPhoneInput(row.phone_number ?? "");
              setPhoneError(null);
            },
          },
          {
            label: t("admin.resetPassword"),
            onSelect: () => handleResetPassword(row),
          },
          {
            label: t("admin.deactivate"),
            danger: true,
            onSelect: () => setDeactivateTarget(row),
          },
        ];
        return (
          <Dropdown
            trigger={
              <span className="rounded-lg px-2 py-1 text-xs text-ink-3 hover:bg-hover hover:text-ink">
                {t("admin.rowActions")}
              </span>
            }
            options={options}
          />
        );
      },
```

Add the confirm modal in the JSX, after the phone modal added in Task 10:

```typescript
      <Modal
        open={deactivateTarget !== null}
        onClose={() => setDeactivateTarget(null)}
        title={t("admin.deactivateConfirmTitle")}
      >
        <div className="flex flex-col gap-3">
          <p className="text-sm text-ink">
            {deactivateTarget && t("admin.deactivateConfirmBody", { displayName: deactivateTarget.display_name })}
          </p>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" size="sm" onClick={() => setDeactivateTarget(null)}>
              {t("common.cancel")}
            </Button>
            <Button type="button" variant="danger" size="sm" disabled={deactivating} onClick={handleDeactivate}>
              {t("admin.deactivate")}
            </Button>
          </div>
        </div>
      </Modal>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/AdminDashboard.test.tsx'`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): deactivate action with confirm dialog, deactivated-row badge"
```

---

### Task 13: Full verification, deploy, live browser check

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `docker compose exec -T -e PYTHONPATH=/app/src api python -m pytest tests -v 2>&1 | tail -60`
Expected: all pass except the two pre-existing unrelated failures noted in Task 7 Step 5. If any new test fails, stop and fix before proceeding.

- [ ] **Step 2: Full frontend suite + typecheck**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run'`
Expected: all pass, count higher than the 346 baseline from the earlier session's ADR 0063 re-verification by at least the ~14 new tests this plan adds.

Run: `docker compose exec web sh -c 'cd /app/apps/web && npx tsc --noEmit'`
Expected: no new errors.

- [ ] **Step 3: Rebuild and deploy**

```bash
docker compose build api
docker compose exec api alembic upgrade head   # should be a no-op if Task 1 already applied it live; confirms idempotency
docker compose up -d api
docker compose exec web sh -c 'cd /app/apps/web && npx vite build'
```

Confirm all containers healthy: `docker compose ps -a --format '{{.Service}} {{.Status}}'`

- [ ] **Step 4: Live browser verification**

Using a disposable test user (create one via the existing Admin "Add user" flow, or the `create_user` smoke-test pattern from Task 2):

1. Log in as `admin1`, navigate to `/admin` → Users tab.
2. Confirm the row-action "Actions" menu appears for every non-service row, and is absent for `signal-bot`.
3. Exercise **role change** on the disposable test user: promote to admin, confirm the badge updates without a page reload.
4. Exercise **set phone**: set a phone number, confirm it appears in the Phone column; clear it, confirm it's blank again.
5. Exercise **reset password**: confirm the one-time password card appears with the new password, dismiss it.
6. Exercise **deactivate**: confirm the dialog copy, confirm, confirm the row shows the "Deactivated" badge and the action menu disappears from that row.
7. **Critical check**: before deactivating, capture the test user's JWT (log in as them in a second browser tab or via `curl -X POST .../auth/token`). After deactivating from the admin tab, immediately retry a request with that same JWT (e.g. `GET /auth/me`) and confirm it now returns 401 — proving Task 7's immediate-session-kill actually works against the live stack, not just the test suite.
8. Check the browser console for errors throughout (`read_console_messages`, `onlyErrors: true`).
9. Delete the disposable test user's residual data if any was created (matches this project's established test-user cleanup discipline).

- [ ] **Step 5: Update the ADR**

Write `docs/adr/<next-number>-admin-user-management.md` documenting what shipped, following the existing ADR format (Status/Context/Decision/Consequences) — check `docs/adr/` for the current highest number before assigning.

```bash
git add docs/adr/<next-number>-admin-user-management.md
git commit -m "docs: ADR for admin user-management (role/password/deactivate/phone)"
git push origin main
```
