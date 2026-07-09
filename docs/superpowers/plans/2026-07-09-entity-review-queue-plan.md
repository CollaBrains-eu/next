# Entity Review Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a human-in-the-loop approve/reject step for AI-extracted entities, so a wrong extraction never silently becomes ground truth in a legal/insurance-adjacent product.

**Architecture:** A `status` field (`pending_review` / `confirmed` / `rejected`) is added to the existing `Entity` model, reusing the `pending_approval` → `approve` pattern already used by `Plan.status` elsewhere in this codebase. Extraction (`entity_agent.py`) creates new entities as `pending_review` instead of committing them as immediately-trusted rows; every existing entity consumer (list, case-linking, graph) defaults its query to `confirmed`-only so today's behavior is unchanged except at the one new review surface. A new frontend route (`/entities/review`) presents pending entities one at a time with keyboard-shortcut approve/reject.

**Tech Stack:** FastAPI + SQLAlchemy 2.0 async + Alembic (backend), React 18 + TypeScript + Vite + Vitest + Testing Library (frontend), pytest + httpx `AsyncClient` (backend tests).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-09-entity-review-queue-design.md` — follow it exactly; this plan implements it task-by-task.
- Environment: SSH-only, no local clone. `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "<command>"` for every command. Repo root `/opt/collabrains`. Frontend at `apps/web`, backend at `services/api`.
- Branch: work happens on `phase-21-plan-entity-review-queue`, branched off `phase-21-entity-review-queue-spec` (PR #43, not yet merged) — already checked out on the server before this plan starts.
- Frontend package manager is pnpm; every `pnpm`/`npx` command must be run with cwd `apps/web` on the server.
- Frontend verification: `npx vite build` + `pnpm test -- --run`, **not** full `pnpm build` (pre-existing `apps/mobile` `@types/react` hoisting conflict, documented in every prior phase's PR — out of scope to fix here).
- Backend verification: `pytest` inside the `api` container — run via `docker compose exec -T api pytest <path> -v` from `/opt/collabrains`, matching how backend tests are already run in this project (real Postgres, no DB mocking — see `services/api/tests/test_entities.py`'s existing style, which this plan's backend tests must match).
- `status` is a plain `String(20)` column, matching the existing convention (`Document.status`, `Plan.status`, `Task.status`, `Case.status`) — do not introduce a Postgres enum type.
- Vehicles are explicitly out of scope — do not touch `vehicle_agent.py` or the `vehicles` table.
- Alembic migration chain: current head is `c48f1e7a92d3` (`create_vehicles_table`) — confirmed via `docker compose exec -T api alembic heads` on the server, not by reading file contents (this repo's migration files have `down_revision` values that don't all resolve by simple grep). This plan's migration must set `down_revision = 'c48f1e7a92d3'`.
- At the end of the plan (after all tasks), push the branch and open a PR against `main` (do not merge) using this project's established heredoc-to-file pattern: write the PR body to a local file, `scp` it to the server as `/tmp/pr44-body.md`, then `gh pr create --body-file /tmp/pr44-body.md --base main --head phase-21-plan-entity-review-queue`.

---

### Task 1: `Entity.status` field, migration, and backfill

**Files:**
- Modify: `services/api/src/api/models.py` (the `Entity` class, currently at line 184)
- Create: `services/api/alembic/versions/<new_revision>_add_entity_status.py`
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Produces: `Entity.status: str`, one of `"pending_review" | "confirmed" | "rejected"`, `server_default="pending_review"`. Every later task in this plan reads/writes this field.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_entities.py` (this test exercises the model+migration together via the real extraction flow, matching this file's existing integration-test style):

```python
async def test_new_entities_are_created_as_pending_review(client):
    token = await _login(client, "entityuser5")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Nadia Petrov works at Fenwick LLC.")

    fake = (
        '{"entities": [{"name": "Nadia Petrov", "type": "person"}], "relationships": []}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json()[0]["status"] == "pending_review"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py::test_new_entities_are_created_as_pending_review -v"`
Expected: FAIL with `KeyError: 'status'` (the field doesn't exist on `EntityOut` yet)

- [ ] **Step 3: Add the `status` column to the `Entity` model**

In `services/api/src/api/models.py`, modify the `Entity` class (currently lines 184-197):

```python
class Entity(Base):
    """A person, organization, location, or other named thing extracted from documents.

    Deduplicated by exact case-insensitive (name, entity_type) match only
    -- see docs/adr/0008-phase4-entity-graph.md for why fuzzy/LLM-based
    resolution is deliberately out of scope for now.

    `status` gates whether an extracted entity is trusted: new entities
    start `pending_review` and must be explicitly approved before they
    appear in normal listings, case linking, or the entity graph -- see
    docs/superpowers/specs/2026-07-09-entity-review-queue-design.md.
    """

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 4: Generate and edit the migration**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api alembic revision -m 'add entity status'"`

This prints the generated file path and a fresh revision id (e.g. `services/api/alembic/versions/<newid>_add_entity_status.py`). Read that generated file, then replace its contents with:

```python
"""add entity status

Revision ID: <newid>
Revises: c48f1e7a92d3
Create Date: 2026-07-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '<newid>'
down_revision: Union[str, None] = 'c48f1e7a92d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'entities',
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending_review'),
    )
    # Every entity that existed before this migration is already relied on
    # throughout the app (case linking, the entity graph, search) -- treat
    # all of them as already-reviewed so nothing currently visible
    # disappears behind the new review gate.
    op.execute("UPDATE entities SET status = 'confirmed'")


def downgrade() -> None:
    op.drop_column('entities', 'status')
```

Replace `<newid>` in both the header comment and the `revision` field with the actual id Alembic generated (leave `down_revision` as the literal string `'c48f1e7a92d3'`).

- [ ] **Step 5: Add `status` to `EntityOut` and apply the migration**

In `services/api/src/api/entities.py`, modify `EntityOut` (currently lines 18-22):

```python
class EntityOut(BaseModel):
    id: UUID
    name: str
    entity_type: str
    status: str
    created_at: datetime
```

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api alembic upgrade head"`
Expected: no errors, ends at the new revision.

- [ ] **Step 6: Run test to verify it passes**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py -v"`
Expected: all tests in the file PASS, including the new one. (The pre-existing tests must still pass — they don't reference `status`, but the response now includes an extra field, which is compatible with dict equality checks already in the file since none of them assert on the full response shape.)

- [ ] **Step 7: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add services/api/src/api/models.py services/api/src/api/entities.py services/api/alembic/versions/ services/api/tests/test_entities.py && git commit -m 'Add Entity.status field with pending_review/confirmed/rejected states'"
```

---

### Task 2: Extraction-matching logic (confirmed-reuse / pending-reuse / rejected-suppress)

**Files:**
- Modify: `services/api/src/api/entity_agent.py:34-43` (`_get_or_create_entity`)
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `Entity.status` (Task 1).
- Produces: `_get_or_create_entity(db, name, entity_type) -> Entity | None`. Returns `None` when the match is `rejected` (signals the caller to skip creating a mention for a suppressed entity) instead of the previous unconditional `Entity` return.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_entities.py`:

```python
async def test_extraction_reuses_confirmed_entity_without_creating_pending_row(client):
    token = await _login(client, "entityuser6")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "Omar Reyes signed the lease.")
    doc_b = await _upload_ready_document(client, headers, "Omar Reyes called again today.")

    fake = '{"entities": [{"name": "Omar Reyes", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        first = await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    entity_id = first.json()[0]["id"]

    # Manually confirm it, the way the approve endpoint will in Task 4.
    from api.models import Entity
    from api.db import async_session
    async with async_session() as db:
        entity = await db.get(Entity, entity_id)
        entity.status = "confirmed"
        await db.commit()

    with patch("api.entity_agent.chat_completion", return_value=fake):
        second = await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    assert len(second.json()) == 1
    assert second.json()[0]["id"] == entity_id
    assert second.json()[0]["status"] == "confirmed"

    listing = await client.get("/entities", headers=headers, params={"q": "Omar", "status": "all"})
    assert len(listing.json()) == 1  # still exactly one row, not a duplicate pending one


async def test_extraction_attaches_new_mention_to_existing_pending_entity(client):
    token = await _login(client, "entityuser7")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "Priya Nair filed a claim.")
    doc_b = await _upload_ready_document(client, headers, "Priya Nair called the adjuster.")

    fake = '{"entities": [{"name": "Priya Nair", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        first = await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    with patch("api.entity_agent.chat_completion", return_value=fake):
        second = await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    assert first.json()[0]["id"] == second.json()[0]["id"]
    listing = await client.get("/entities", headers=headers, params={"q": "Priya", "status": "all"})
    assert len(listing.json()) == 1  # one pending row shared by both mentions, not two


async def test_extraction_suppresses_rejected_entity(client):
    token = await _login(client, "entityuser8")
    headers = {"Authorization": f"Bearer {token}"}
    doc_a = await _upload_ready_document(client, headers, "088 227 77 00 is listed.")

    fake = '{"entities": [{"name": "088 227 77 00", "type": "other"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        first = await client.post(f"/documents/{doc_a}/extract-entities", headers=headers)
    entity_id = first.json()[0]["id"]

    from api.models import Entity
    from api.db import async_session
    async with async_session() as db:
        entity = await db.get(Entity, entity_id)
        entity.status = "rejected"
        await db.commit()

    doc_b = await _upload_ready_document(client, headers, "Call 088 227 77 00 for support.")
    with patch("api.entity_agent.chat_completion", return_value=fake):
        second = await client.post(f"/documents/{doc_b}/extract-entities", headers=headers)

    assert second.json() == []  # suppressed, not recreated
    listing = await client.get("/entities", headers=headers, params={"q": "088", "status": "all"})
    assert len(listing.json()) == 1  # still just the original rejected row
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py -k 'reuses_confirmed or attaches_new_mention or suppresses_rejected' -v"`
Expected: FAIL — `test_extraction_reuses_confirmed_entity_without_creating_pending_row` and `test_extraction_attaches_new_mention_to_existing_pending_entity` fail because `GET /entities` doesn't accept a `status` query param yet (400 or ignored, causing the count assertion to fail since duplicates aren't yet prevented for the pending case); `test_extraction_suppresses_rejected_entity` fails because the rejected entity gets recreated instead of suppressed.

- [ ] **Step 3: Implement the matching logic**

Replace `_get_or_create_entity` in `services/api/src/api/entity_agent.py` (currently lines 34-43):

```python
async def _get_or_create_entity(db: AsyncSession, name: str, entity_type: str) -> Entity | None:
    """Look up an existing entity by case-insensitive (name, entity_type).

    Returns the existing row if it is `confirmed` or `pending_review`
    (reusing it rather than creating a duplicate pending row), `None` if
    it is `rejected` (permanently suppressed -- see
    docs/superpowers/specs/2026-07-09-entity-review-queue-design.md), or
    creates a new `pending_review` row if there is no match at all.
    """
    result = await db.execute(
        select(Entity).where(func.lower(Entity.name) == name.lower().strip(), Entity.entity_type == entity_type)
    )
    entity = result.scalar_one_or_none()
    if entity is not None:
        if entity.status == "rejected":
            return None
        return entity
    entity = Entity(name=name.strip(), entity_type=entity_type)
    db.add(entity)
    await db.flush()
    return entity
```

Then update `extract_entities`'s loop over `raw_entities` (currently lines 68-80 of `entity_agent.py`) to skip suppressed entities:

```python
    entities_by_name: dict[str, Entity] = {}
    persisted: list[Entity] = []
    for item in raw_entities:
        if not isinstance(item, dict) or not item.get("name"):
            continue
        entity_type = item.get("type") if item.get("type") in VALID_ENTITY_TYPES else "other"
        entity = await _get_or_create_entity(db, item["name"], entity_type)
        if entity is None:
            continue  # rejected entity, permanently suppressed
        entities_by_name[item["name"].strip().lower()] = entity
        persisted.append(entity)

        existing = await db.execute(
            select(EntityMention).where(EntityMention.entity_id == entity.id, EntityMention.document_id == document_id)
        )
        if existing.scalar_one_or_none() is None:
            db.add(EntityMention(entity_id=entity.id, document_id=document_id))
```

This still leaves `GET /entities` without a `status` query parameter, which Task 3 adds — the tests in this task that query `?status=all` will still fail until Task 3 lands; that's expected and is why Task 3 comes immediately next, not because this task is incomplete on its own terms (the extraction-matching behavior itself is fully correct and independently testable via the `response.json()` assertions in this task's tests, which do not depend on the `status` query param).

- [ ] **Step 4: Run tests to verify they pass**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py -k 'reuses_confirmed or attaches_new_mention or suppresses_rejected' -v"`
Expected: still FAIL on the `?status=all` listing assertions (3 failures, down from a full-file failure) — this is expected per Step 3's note. Confirm the failure output specifically points at the `status` query param / count assertions, not at entity creation or mention logic, before moving to Task 3.

- [ ] **Step 5: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add services/api/src/api/entity_agent.py services/api/tests/test_entities.py && git commit -m 'Match extraction against confirmed/pending/rejected entities instead of always creating new rows'"
```

---

### Task 3: `GET /entities` status filter

**Files:**
- Modify: `services/api/src/api/entities.py:42-57` (`list_entities`)
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `Entity.status` (Task 1).
- Produces: `GET /entities?status=pending_review|confirmed|rejected|all`, defaulting to `confirmed` when the parameter is omitted. This is what Task 2's tests (`?status=all`) and Task 7's frontend review queue (`?status=pending_review`) both call.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_entities.py`:

```python
async def test_list_entities_defaults_to_confirmed_only(client):
    token = await _login(client, "entityuser9")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Karl Zimmer is a witness.")

    fake = '{"entities": [{"name": "Karl Zimmer", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    default_listing = await client.get("/entities", headers=headers, params={"q": "Karl"})
    assert default_listing.json() == []  # pending_review entities are hidden by default

    pending_listing = await client.get("/entities", headers=headers, params={"q": "Karl", "status": "pending_review"})
    assert len(pending_listing.json()) == 1

    all_listing = await client.get("/entities", headers=headers, params={"q": "Karl", "status": "all"})
    assert len(all_listing.json()) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py::test_list_entities_defaults_to_confirmed_only -v"`
Expected: FAIL — `default_listing.json()` is not `[]` (the pending entity is currently returned since there's no filter yet).

- [ ] **Step 3: Implement the status filter**

Replace `list_entities` in `services/api/src/api/entities.py` (currently lines 42-57):

```python
@router.get("/entities", response_model=list[EntityOut])
async def list_entities(
    q: str | None = Query(None, description="Filter by name (case-insensitive substring)"),
    entity_type: str | None = Query(None),
    status: str = Query("confirmed", description="pending_review | confirmed | rejected | all"),
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[Entity]:
    query = select(Entity).order_by(Entity.name).limit(limit).offset(offset)
    if q:
        query = query.where(Entity.name.ilike(f"%{q}%"))
    if entity_type:
        query = query.where(Entity.entity_type == entity_type)
    if status != "all":
        query = query.where(Entity.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py -v"`
Expected: all tests in the file PASS, including Task 2's three tests (which depend on this `status` param) and this task's new test.

- [ ] **Step 5: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add services/api/src/api/entities.py services/api/tests/test_entities.py && git commit -m 'Add status filter to GET /entities, defaulting to confirmed-only'"
```

---

### Task 4: Approve / reject / bulk-review endpoints

**Files:**
- Modify: `services/api/src/api/entities.py` (add new endpoints after `list_entities`)
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `Entity.status` (Task 1), `GET /entities?status=` (Task 3, used by tests to verify state after review actions).
- Produces: `POST /entities/{entity_id}/approve`, `POST /entities/{entity_id}/reject` (both `response_model=EntityOut`, 404 if missing, 409 if not currently `pending_review`), `POST /entities/bulk-review` (`response_model=list[EntityOut]`, body is a list of `{entity_id, action}`). Task 6's frontend `api.ts` wraps these three endpoints.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_entities.py`:

```python
async def test_approve_entity_transitions_pending_to_confirmed(client):
    token = await _login(client, "entityuser10")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Liu Wei is a party.")
    fake = '{"entities": [{"name": "Liu Wei", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    entity_id = extracted.json()[0]["id"]

    response = await client.post(f"/entities/{entity_id}/approve", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    listing = await client.get("/entities", headers=headers, params={"q": "Liu"})
    assert len(listing.json()) == 1  # now visible in the default (confirmed-only) listing


async def test_reject_entity_transitions_pending_to_rejected(client):
    token = await _login(client, "entityuser11")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "23.10.2025 appears here.")
    fake = '{"entities": [{"name": "23.10.2025", "type": "other"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    entity_id = extracted.json()[0]["id"]

    response = await client.post(f"/entities/{entity_id}/reject", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


async def test_approve_nonexistent_entity_returns_404(client):
    token = await _login(client, "entityuser12")
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.post("/entities/00000000-0000-0000-0000-000000000000/approve", headers=headers)
    assert response.status_code == 404


async def test_approve_already_confirmed_entity_returns_409(client):
    token = await _login(client, "entityuser13")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Second approve attempt.")
    fake = '{"entities": [{"name": "Rosa Diaz", "type": "person"}], "relationships": []}'
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    entity_id = extracted.json()[0]["id"]

    await client.post(f"/entities/{entity_id}/approve", headers=headers)
    second = await client.post(f"/entities/{entity_id}/approve", headers=headers)
    assert second.status_code == 409


async def test_bulk_review_approves_and_rejects_in_one_request(client):
    token = await _login(client, "entityuser14")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Two entities appear.")
    fake = (
        '{"entities": [{"name": "Tom Baker", "type": "person"}, {"name": "14 februari 2024", "type": "other"}], '
        '"relationships": []}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    ids_by_name = {e["name"]: e["id"] for e in extracted.json()}

    response = await client.post(
        "/entities/bulk-review",
        headers=headers,
        json=[
            {"entity_id": ids_by_name["Tom Baker"], "action": "approve"},
            {"entity_id": ids_by_name["14 februari 2024"], "action": "reject"},
        ],
    )
    assert response.status_code == 200
    results = {r["id"]: r["status"] for r in response.json()}
    assert results[ids_by_name["Tom Baker"]] == "confirmed"
    assert results[ids_by_name["14 februari 2024"]] == "rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py -k 'approve or reject or bulk_review' -v"`
Expected: FAIL with 404s (routes don't exist yet).

- [ ] **Step 3: Implement the endpoints**

Add to `services/api/src/api/entities.py`, immediately after `list_entities` (after the current line 57, before the `GraphNode` class):

```python
class BulkReviewItem(BaseModel):
    entity_id: UUID
    action: str  # "approve" | "reject"


async def _transition_entity(db: AsyncSession, entity_id: UUID, new_status: str) -> Entity:
    entity = await db.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")
    if entity.status != "pending_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Entity is not pending review (status: {entity.status})",
        )
    entity.status = new_status
    await db.commit()
    await db.refresh(entity)
    return entity


@router.post("/entities/{entity_id}/approve", response_model=EntityOut)
async def approve_entity(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Entity:
    return await _transition_entity(db, entity_id, "confirmed")


@router.post("/entities/{entity_id}/reject", response_model=EntityOut)
async def reject_entity(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> Entity:
    return await _transition_entity(db, entity_id, "rejected")


@router.post("/entities/bulk-review", response_model=list[EntityOut])
async def bulk_review_entities(
    items: list[BulkReviewItem],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[Entity]:
    results: list[Entity] = []
    for item in items:
        new_status = "confirmed" if item.action == "approve" else "rejected"
        results.append(await _transition_entity(db, item.entity_id, new_status))
    return results
```

`status` (the FastAPI module import, `from fastapi import ... status`) already exists at the top of `entities.py` (line 5). Task 3's `list_entities` has a local parameter also named `status`, which shadows the module import *only inside that one function's body* — standard Python scoping, not a bug. It's safe there because `list_entities`'s body never needs `status.HTTP_...`. `_transition_entity`, `approve_entity`, `reject_entity`, and `bulk_review_entities` (this task) have no `status`-named parameter, so `status.HTTP_404_NOT_FOUND` and `status.HTTP_409_CONFLICT` resolve to the module as normal inside them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py -v"`
Expected: all tests in the file PASS.

- [ ] **Step 5: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add services/api/src/api/entities.py services/api/tests/test_entities.py && git commit -m 'Add approve/reject/bulk-review endpoints for pending entities'"
```

---

### Task 5: Entity graph confirmed-only filtering

**Files:**
- Modify: `services/api/src/api/entities.py:79-120` (`get_entity_graph`)
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `Entity.status` (Task 1).
- Produces: `GET /entities/{entity_id}/graph` now excludes non-confirmed neighbors as nodes, and excludes any edge where either endpoint is non-confirmed. No signature change — same `EntityGraphOut` shape as before.

- [ ] **Step 1: Write the failing test**

Add to `services/api/tests/test_entities.py`:

```python
async def test_entity_graph_excludes_non_confirmed_neighbors(client):
    token = await _login(client, "entityuser15")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Elena Kravitz represents Vantage Group.")

    fake = (
        '{"entities": [{"name": "Elena Kravitz", "type": "person"}, {"name": "Vantage Group", "type": "organization"}], '
        '"relationships": [{"source": "Elena Kravitz", "target": "Vantage Group", "type": "represents"}]}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake):
        extracted = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)
    ids_by_name = {e["name"]: e["id"] for e in extracted.json()}
    center_id = ids_by_name["Elena Kravitz"]

    # Center confirmed, neighbor still pending_review (default post-extraction state).
    await client.post(f"/entities/{center_id}/approve", headers=headers)

    graph = await client.get(f"/entities/{center_id}/graph", headers=headers)
    assert graph.json()["nodes"] == []  # Vantage Group is still pending, so it's excluded
    assert graph.json()["edges"] == []  # the edge to a non-confirmed neighbor is excluded too
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py::test_entity_graph_excludes_non_confirmed_neighbors -v"`
Expected: FAIL — `nodes` and `edges` are non-empty (the pending neighbor and its edge are still included).

- [ ] **Step 3: Implement confirmed-only filtering**

Replace `get_entity_graph` in `services/api/src/api/entities.py` (currently lines 79-120):

```python
@router.get("/entities/{entity_id}/graph", response_model=EntityGraphOut)
async def get_entity_graph(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> EntityGraphOut:
    """One-hop neighborhood of an entity: itself, its direct confirmed neighbors, and the
    confirmed-to-confirmed edges between them. Non-confirmed neighbors/edges are excluded --
    see docs/superpowers/specs/2026-07-09-entity-review-queue-design.md."""
    center = await db.get(Entity, entity_id)
    if center is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found")

    edges_result = await db.execute(
        select(EntityRelationship).where(
            or_(EntityRelationship.source_entity_id == entity_id, EntityRelationship.target_entity_id == entity_id)
        )
    )
    all_edges = list(edges_result.scalars().all())

    neighbor_ids = {
        eid
        for edge in all_edges
        for eid in (edge.source_entity_id, edge.target_entity_id)
        if eid != entity_id
    }
    neighbors: list[Entity] = []
    if neighbor_ids:
        neighbors_result = await db.execute(
            select(Entity).where(Entity.id.in_(neighbor_ids), Entity.status == "confirmed")
        )
        neighbors = list(neighbors_result.scalars().all())
    confirmed_neighbor_ids = {n.id for n in neighbors}

    edges = [
        edge
        for edge in all_edges
        for other_id in [edge.target_entity_id if edge.source_entity_id == entity_id else edge.source_entity_id]
        if other_id in confirmed_neighbor_ids
    ]

    return EntityGraphOut(
        center=GraphNode(id=center.id, name=center.name, entity_type=center.entity_type),
        nodes=[GraphNode(id=n.id, name=n.name, entity_type=n.entity_type) for n in neighbors],
        edges=[
            GraphEdge(
                source=edge.source_entity_id,
                target=edge.target_entity_id,
                relationship_type=edge.relationship_type,
                document_id=edge.document_id,
            )
            for edge in edges
        ],
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_entities.py -v"`
Expected: all tests PASS, including the pre-existing `test_extract_entities_skips_relationships_referencing_unknown_entities` (its assertion `graph.json()["edges"] == []` still holds — that test's entity is never confirmed, so it now hits the *new* filtering path instead of the old empty-neighbor-list path, but the assertion is unchanged).

- [ ] **Step 5: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add services/api/src/api/entities.py services/api/tests/test_entities.py && git commit -m 'Exclude non-confirmed entities and edges from the entity graph'"
```

---

### Task 6: Frontend `api.ts` additions

**Files:**
- Modify: `apps/web/src/lib/api.ts:184-220` (`EntityOut`, `listEntities`)
- Test: `apps/web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: the backend endpoints from Tasks 3 and 4 (by URL/shape, not by import — frontend and backend are separate processes).
- Produces: `EntityOut.status: string`, `listEntities(q?, entityType?, status?)`, `approveEntity(id: string): Promise<EntityOut>`, `rejectEntity(id: string): Promise<EntityOut>`, `bulkReviewEntities(items: {entity_id: string; action: "approve" | "reject"}[]): Promise<EntityOut[]>`. Tasks 7, 8, and 9 all import these.

- [ ] **Step 1: Write the failing test**

`apps/web/src/lib/api.test.ts` tests `request()`-based functions by stubbing the global `fetch` with `vi.stubGlobal("fetch", vi.fn())` in a `beforeEach` and returning a real `Response` object (see the file's existing `describe("api request()", ...)` block) — it does not mock the `./api` module itself, since this is the file that defines it. Add a new `describe` block to `apps/web/src/lib/api.test.ts` matching that exact pattern:

Change the existing top-of-file import (currently line 2: `import { ApiError, clearToken, login, request, setToken } from "./api";`) to also bring in `approveEntity`:

```typescript
import { ApiError, approveEntity, clearToken, login, request, setToken } from "./api";
```

Then add the new block:

```typescript
describe("approveEntity", () => {
  beforeEach(() => {
    clearToken();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts to /entities/:id/approve and returns the updated entity", async () => {
    const mockEntity = { id: "e1", name: "Test", entity_type: "person", status: "confirmed", created_at: "2026-01-01T00:00:00Z" };
    (fetch as ReturnType<typeof vi.fn>).mockResolvedValue(
      new Response(JSON.stringify(mockEntity), { status: 200 }),
    );

    const result = await approveEntity("e1");

    expect(result.status).toBe("confirmed");
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(url).toContain("/entities/e1/approve");
    expect(init.method).toBe("POST");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run src/lib/api.test.ts"`
Expected: FAIL with `approveEntity is not defined` (or a TypeScript compile error to the same effect).

- [ ] **Step 3: Implement the additions**

In `apps/web/src/lib/api.ts`, modify `EntityOut` (currently lines 184-189):

```typescript
export interface EntityOut {
  id: string;
  name: string;
  entity_type: string;
  status: string;
  created_at: string;
}
```

Replace `listEntities` (currently lines 191-197):

```typescript
export function listEntities(q?: string, entityType?: string, status?: string): Promise<EntityOut[]> {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (entityType) params.set("entity_type", entityType);
  if (status) params.set("status", status);
  const query = params.toString();
  return request<EntityOut[]>(`/entities${query ? `?${query}` : ""}`);
}

export function approveEntity(id: string): Promise<EntityOut> {
  return request<EntityOut>(`/entities/${id}/approve`, { method: "POST" });
}

export function rejectEntity(id: string): Promise<EntityOut> {
  return request<EntityOut>(`/entities/${id}/reject`, { method: "POST" });
}

export interface BulkReviewItem {
  entity_id: string;
  action: "approve" | "reject";
}

export function bulkReviewEntities(items: BulkReviewItem[]): Promise<EntityOut[]> {
  return request<EntityOut[]>("/entities/bulk-review", {
    method: "POST",
    body: JSON.stringify(items),
  });
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run"`
Expected: all tests PASS except one TypeScript compile error: `Entities.test.tsx`'s `ENTITIES` fixture (currently lines 15-18) constructs `EntityOut` object literals without the new required `status` field:

```typescript
const ENTITIES: api.EntityOut[] = [
  { id: "e1", name: "Jane Smith", entity_type: "person", created_at: "2026-01-01T00:00:00Z" },
  { id: "e2", name: "Acme Corp", entity_type: "organization", created_at: "2026-01-02T00:00:00Z" },
];
```

Fix by adding `status: "confirmed"` to both entries (they represent already-listed entities on the default confirmed-only view):

```typescript
const ENTITIES: api.EntityOut[] = [
  { id: "e1", name: "Jane Smith", entity_type: "person", status: "confirmed", created_at: "2026-01-01T00:00:00Z" },
  { id: "e2", name: "Acme Corp", entity_type: "organization", status: "confirmed", created_at: "2026-01-02T00:00:00Z" },
];
```

`EntityGraph.test.tsx`'s `GRAPH` fixture needs no change — its `GraphNode`/`EntityGraphOut` types don't gain a `status` field (the graph endpoint already filters to confirmed-only server-side in Task 5, so there's nothing for the frontend type to carry).

- [ ] **Step 5: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts apps/web/src/routes/Entities.test.tsx && git commit -m 'Add status field and approve/reject/bulk-review API functions'"
```

---

### Task 7: `EntityReview.tsx` review queue page

**Files:**
- Create: `apps/web/src/routes/EntityReview.tsx`
- Create: `apps/web/src/routes/EntityReview.test.tsx`
- Modify: `apps/web/src/App.tsx` (add the `/entities/review` route)
- Modify: `apps/web/src/lib/navigation.ts` — **not modified**: the review queue is reached via the Sidebar badge (Task 8) and a link from `/entities`, not a top-level nav item, matching the spec's "no blocking modal or forced navigation" framing. (No file change here; listed to make the decision explicit for whoever reads this plan next.)

**Interfaces:**
- Consumes: `listEntities`, `approveEntity`, `rejectEntity`, `bulkReviewEntities`, `EntityOut` (Task 6).
- Produces: the `EntityReview` default export, mounted at `/entities/review`. Task 8's Sidebar badge links here.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/routes/EntityReview.test.tsx`:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EntityReview from "./EntityReview";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listEntities: vi.fn(),
    approveEntity: vi.fn(),
    rejectEntity: vi.fn(),
    bulkReviewEntities: vi.fn(),
  };
});

const PENDING: api.EntityOut[] = [
  { id: "p1", name: "Nadia Petrov", entity_type: "person", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
  { id: "p2", name: "Fenwick LLC", entity_type: "organization", status: "pending_review", created_at: "2026-01-02T00:00:00Z" },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <EntityReview />
    </MemoryRouter>
  );
}

describe("EntityReview", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listEntities).mockResolvedValue(PENDING);
  });

  it("shows the first pending entity with a counter", async () => {
    renderPage();
    expect(await screen.findByText("Nadia Petrov")).toBeInTheDocument();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
  });

  it("approving advances to the next card", async () => {
    vi.mocked(api.approveEntity).mockResolvedValue({ ...PENDING[0], status: "confirmed" });
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.click(screen.getByRole("button", { name: /approve/i }));
    await waitFor(() => expect(api.approveEntity).toHaveBeenCalledWith("p1"));
    expect(await screen.findByText("Fenwick LLC")).toBeInTheDocument();
  });

  it("rejecting advances to the next card", async () => {
    vi.mocked(api.rejectEntity).mockResolvedValue({ ...PENDING[0], status: "rejected" });
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.click(screen.getByRole("button", { name: /reject/i }));
    await waitFor(() => expect(api.rejectEntity).toHaveBeenCalledWith("p1"));
    expect(await screen.findByText("Fenwick LLC")).toBeInTheDocument();
  });

  it("J approves via keyboard, K rejects via keyboard", async () => {
    vi.mocked(api.approveEntity).mockResolvedValue({ ...PENDING[0], status: "confirmed" });
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.keyDown(window, { key: "j" });
    await waitFor(() => expect(api.approveEntity).toHaveBeenCalledWith("p1"));
  });

  it("shows an empty state once the queue is cleared", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("Nothing to review")).toBeInTheDocument();
  });

  it("bulk-approve clears the whole queue", async () => {
    vi.mocked(api.bulkReviewEntities).mockResolvedValue(PENDING.map((e) => ({ ...e, status: "confirmed" })));
    renderPage();
    await screen.findByText("Nadia Petrov");
    fireEvent.click(screen.getByRole("button", { name: /approve all/i }));
    await waitFor(() =>
      expect(api.bulkReviewEntities).toHaveBeenCalledWith([
        { entity_id: "p1", action: "approve" },
        { entity_id: "p2", action: "approve" },
      ])
    );
    expect(await screen.findByText("Nothing to review")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run src/routes/EntityReview.test.tsx"`
Expected: FAIL — `Cannot find module './EntityReview'`.

- [ ] **Step 3: Implement `EntityReview.tsx`**

Create `apps/web/src/routes/EntityReview.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { approveEntity, bulkReviewEntities, listEntities, rejectEntity, type EntityOut } from "../lib/api";
import { Button } from "../components/ui/Button";

export default function EntityReview() {
  const [queue, setQueue] = useState<EntityOut[] | null>(null);
  const [index, setIndex] = useState(0);

  useEffect(() => {
    listEntities(undefined, undefined, "pending_review").then(setQueue);
  }, []);

  const current = queue?.[index];

  async function handleApprove() {
    if (!current) return;
    await approveEntity(current.id);
    setIndex((i) => i + 1);
  }

  async function handleReject() {
    if (!current) return;
    await rejectEntity(current.id);
    setIndex((i) => i + 1);
  }

  async function handleApproveAll() {
    if (!queue || queue.length === 0) return;
    await bulkReviewEntities(queue.map((e) => ({ entity_id: e.id, action: "approve" as const })));
    setQueue([]);
    setIndex(0);
  }

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (!current) return;
      if (e.key === "j" || e.key === "ArrowRight") handleApprove();
      if (e.key === "k" || e.key === "ArrowLeft") handleReject();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  });

  if (queue === null) return <p className="text-ink-3">Loading…</p>;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <Link to="/entities" className="text-sm text-ink-2 hover:text-ink">
            ← Back to entities
          </Link>
          <h1 className="mt-2 text-2xl font-semibold text-ink">Review entities</h1>
        </div>
        {queue.length > 0 && (
          <Button variant="secondary" size="sm" onClick={handleApproveAll}>
            Approve all
          </Button>
        )}
      </div>

      {!current ? (
        <p className="text-ink-3">Nothing to review</p>
      ) : (
        <div className="flex flex-col gap-4 rounded-2xl border border-edge bg-surface p-6">
          <p className="text-sm text-ink-3">
            {index + 1} of {queue.length}
          </p>
          <div>
            <p className="text-lg font-semibold text-ink">{current.name}</p>
            <p className="text-sm text-ink-2">{current.entity_type}</p>
          </div>
          <div className="flex gap-2">
            <Button variant="danger" onClick={handleReject}>
              Reject
            </Button>
            <Button variant="primary" onClick={handleApprove}>
              Approve
            </Button>
          </div>
          <p className="text-xs text-ink-3">Keyboard: J or → to approve, K or ← to reject</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Wire the route**

In `apps/web/src/App.tsx`, add the import alongside the existing `EntityGraph` import (currently line 15):

```typescript
import EntityReview from "./routes/EntityReview";
```

Add the route immediately after the `/entities` route and before the `/entities/:id` route (currently lines 91-97):

```tsx
                <Route
                  path="/entities/review"
                  element={
                    <ProtectedRoute>
                      <EntityReview />
                    </ProtectedRoute>
                  }
                />
```

- [ ] **Step 5: Run test to verify it passes**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run"`
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add apps/web/src/routes/EntityReview.tsx apps/web/src/routes/EntityReview.test.tsx apps/web/src/App.tsx && git commit -m 'Add EntityReview queue page with keyboard-shortcut approve/reject'"
```

---

### Task 8: Sidebar pending-count badge

**Files:**
- Modify: `apps/web/src/components/Sidebar.tsx`
- Test: `apps/web/src/components/Sidebar.test.tsx`

**Interfaces:**
- Consumes: `listEntities` (Task 6, called with `status="pending_review"`).
- Produces: a visible pending-count indicator next to the "Entities" nav link, linking to `/entities/review` (Task 7).

- [ ] **Step 1: Write the failing test**

`apps/web/src/components/Sidebar.test.tsx` currently mocks only `../lib/auth` and has no `../lib/api` mock at all, plus a `renderAt(path)` helper wrapping `render` in a `MemoryRouter`. Modify its imports (currently lines 1-8) to add the `api` mock and `waitFor`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listEntities: vi.fn() };
});
```

Then add two new tests inside the existing `describe("Sidebar", ...)` block, using the file's existing `renderAt` helper, with a `beforeEach` to reset the mock between tests (the file has no `beforeEach` yet — add one):

```tsx
describe("Sidebar", () => {
  beforeEach(() => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
  });

  // ...existing 3 tests unchanged...

  it("shows a pending-review count badge on Entities when there are pending entities", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([
      { id: "p1", name: "X", entity_type: "person", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
      { id: "p2", name: "Y", entity_type: "person", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderAt("/");
    expect(await screen.findByText("2")).toBeInTheDocument();
  });

  it("shows no badge when there are no pending entities", async () => {
    renderAt("/");
    await waitFor(() => expect(api.listEntities).toHaveBeenCalled());
    expect(screen.queryByTestId("entities-pending-badge")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run src/components/Sidebar.test.tsx"`
Expected: FAIL — no badge is rendered at all yet.

- [ ] **Step 3: Implement the badge**

Modify `apps/web/src/components/Sidebar.tsx`. Add the import and state (near the top, alongside the existing imports at lines 1-6):

```typescript
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { Button } from "./ui/Button";
import { NAV_ITEMS } from "../lib/navigation";
import { listEntities } from "../lib/api";
```

Inside the `Sidebar` component, add a new state and effect (alongside the existing `pillStyle` state at lines 13-21):

```typescript
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    listEntities(undefined, undefined, "pending_review").then((entities) => setPendingCount(entities.length));
  }, []);
```

Modify the nav item rendering (currently lines 33-49) to render a badge next to the "Entities" link specifically:

```tsx
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              ref={(el) => {
                itemRefs.current[item.to] = el;
              }}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `relative z-10 flex items-center justify-between rounded-lg px-3 py-2 transition-colors duration-fast ${
                  isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                }`
              }
            >
              <span>{item.label}</span>
              {item.to === "/entities" && pendingCount > 0 && (
                <span
                  data-testid="entities-pending-badge"
                  className="rounded-full bg-accent px-1.5 py-0.5 text-[10px] font-semibold text-white"
                >
                  {pendingCount}
                </span>
              )}
            </NavLink>
          ))}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run"`
Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add apps/web/src/components/Sidebar.tsx apps/web/src/components/Sidebar.test.tsx && git commit -m 'Add pending-review count badge to the Entities nav link'"
```

---

### Task 9: `Entities.tsx` status filter dropdown

**Files:**
- Modify: `apps/web/src/routes/Entities.tsx`
- Test: `apps/web/src/routes/Entities.test.tsx`

**Interfaces:**
- Consumes: `listEntities(q, entityType, status)` (Task 6).
- Produces: a `status` filter dropdown on the Entities list page, defaulting to `"confirmed"` (today's unchanged default behavior), plus a link to `/entities/review` (Task 7).

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/Entities.test.tsx` (the existing `ENTITIES` fixture at lines 15-18 needs `status: "confirmed"` added to each object first, per Task 6 Step 4's note, if that hasn't already been done):

```typescript
it("defaults the status filter to confirmed and re-queries when it changes", async () => {
  renderPage();
  await screen.findByText("Jane Smith");
  expect(api.listEntities).toHaveBeenLastCalledWith(undefined, undefined, "confirmed");

  fireEvent.change(screen.getByDisplayValue("Confirmed"), { target: { value: "pending_review" } });
  await waitFor(() => expect(api.listEntities).toHaveBeenLastCalledWith(undefined, undefined, "pending_review"));
});

it("links to the review queue", async () => {
  renderPage();
  await screen.findByText("Jane Smith");
  expect(screen.getByRole("link", { name: /review pending/i })).toHaveAttribute("href", "/entities/review");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run src/routes/Entities.test.tsx"`
Expected: FAIL — `listEntities` is currently called with only 2 arguments, and there is no "Confirmed" `<select>` value or "Review pending" link yet.

- [ ] **Step 3: Implement the status filter**

Modify `apps/web/src/routes/Entities.tsx`. Update the imports (currently line 1-3):

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { listEntities, type EntityOut } from "../lib/api";
```

Update the component state and effect (currently lines 20-31):

```tsx
export default function Entities() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [q, setQ] = useState("");
  const [entityType, setEntityType] = useState("");
  const [statusFilter, setStatusFilter] = useState("confirmed");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listEntities(q || undefined, entityType || undefined, statusFilter)
      .then(setEntities)
      .finally(() => setLoading(false));
  }, [q, entityType, statusFilter]);
```

Update the form (currently lines 47-65) to add the status `<select>` and the review-queue link:

```tsx
      <div className="flex items-center justify-between">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search entities…"
            className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
          />
          <select
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            <option value="">All types</option>
            <option value="person">Person</option>
            <option value="organization">Organization</option>
            <option value="location">Location</option>
            <option value="other">Other</option>
          </select>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
          >
            <option value="confirmed">Confirmed</option>
            <option value="pending_review">Pending review</option>
            <option value="rejected">Rejected</option>
            <option value="all">All</option>
          </select>
        </form>
        <Link to="/entities/review" className="text-sm text-accent hover:underline">
          Review pending →
        </Link>
      </div>
```

(This replaces the standalone `<form>` at lines 47-65 with the same form wrapped in a `flex items-center justify-between` container alongside the new link — the `handleSubmit` function at lines 33-35 and the results list below are unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && pnpm test -- --run"`
Expected: all tests PASS.

- [ ] **Step 5: Run the full verification suite**

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains/apps/web && npx vite build && pnpm test -- --run"`
Expected: build succeeds, all tests pass.

Run: `sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && docker compose exec -T api pytest tests/ -v"`
Expected: full backend suite passes (not just `test_entities.py` — confirms nothing in Tasks 1-5 broke an unrelated test, e.g. any other test that lists entities or reads `EntityOut`).

- [ ] **Step 6: Commit**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git add apps/web/src/routes/Entities.tsx apps/web/src/routes/Entities.test.tsx && git commit -m 'Add status filter dropdown and review-queue link to Entities page'"
```

---

### Final Step: Manual verification, push, and PR

- [ ] **Manual verification against real production data**, following this project's established pattern from every prior phase: SSH-tunnel local ports to the server's `web` (5173) and `api` (8000) containers, temporarily widen CORS in `services/api/src/api/main.py` to the tunnel's local origin, restart the `api` container, verify via a real browser (upload a document, confirm it appears as pending in `/entities/review`, approve it, confirm it now appears in the default `/entities` list and its graph), then **immediately revert the CORS change** and restart `api` again.

- [ ] **Push and open the PR**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git push -u origin phase-21-plan-entity-review-queue"
```

Write the PR body to a local file, then:

```bash
sshpass -p 'Qa266466#02' scp -o StrictHostKeyChecking=no <local-pr-body-file> root@195.90.216.230:/tmp/pr44-body.md
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && gh pr create --title 'Phase 21: entity review queue (AI-confidence confirmation)' --body-file /tmp/pr44-body.md --base main --head phase-21-plan-entity-review-queue"
```

- [ ] **Return the server to `main`**

```bash
sshpass -p 'Qa266466#02' ssh -o StrictHostKeyChecking=no root@195.90.216.230 "cd /opt/collabrains && git checkout main --quiet && git status --short"
```

Expected: clean working tree, on `main`.
