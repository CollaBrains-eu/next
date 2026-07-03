# Case/Matter Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent `Case` that documents, tasks, and decisions can belong to, with a dashboard endpoint assembling all three, plus optional `case_id` support in Planning Engine's existing `summarize_case` goal.

**Architecture:** One new table (`Case`) and one new nullable column (`Document.case_id`) for the primary, most-queried link; Task/Decision link to a Case via the existing polymorphic `GraphEdge` table (Phase 10, ADR 0025) with no schema changes to `tasks`/`decisions`. All new HTTP surface lives in new files (`api/cases.py` domain logic, `api/cases_router.py` endpoints) — no existing file's responsibility is touched except `models.py` (new model + column), `planning_engine.py` (one new resolution step), and `main.py` (router registration).

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Alembic, pytest (async), Postgres. No new dependencies.

## Global Constraints

- Every new endpoint requires authentication via `api.auth.get_current_user` (no new auth pattern).
- Case ownership check pattern (copy exactly, matching `api/decisions.py`'s existing `decision.user_id != current_user.id and current_user.role != "admin"`): a case's `user_id` (or `admin` role) gates all read/write access to it.
- `Document.case_id` is nullable; every existing document has `case_id = NULL` and must continue to work unchanged. No backfill.
- `GraphEdge` rows have no DB-level cascade (ADR 0025's accepted tradeoff) — deleting a `Case` must explicitly delete its `GraphEdge` rows in application code before deleting the case itself.
- Match this codebase's existing test conventions exactly: `_unique(base)` helper (`f"{base}-{uuid4().hex[:8]}"`) for any username/name that could collide across reruns against the shared persistent test database; real Postgres in tests, no mocking of the DB layer.
- Run `~/.local/bin/uvx ruff check <changed files>` after every task; it must report "All checks passed!" before committing.

---

### Task 1: Data model — `Case` table and `Document.case_id`

**Files:**
- Modify: `services/api/src/api/models.py` (add `Case` class; add `case_id` column to `Document`)
- Create: `services/api/alembic/versions/a3f7c9e2b5d8_create_cases_table_and_document_case_id.py`
- Test: `services/api/tests/test_cases.py` (new file, this task only adds the first smoke test; more tests land in Task 2)

**Interfaces:**
- Produces: `Case` model with fields `id: UUID`, `user_id: UUID`, `name: str`, `description: str | None`, `status: str` (default `"open"`), `created_at: datetime`. `Document.case_id: UUID | None` (FK → `cases.id`, `ON DELETE SET NULL`).

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_cases.py`:

```python
from uuid import uuid4

from api.db import async_session
from api.models import Case, Document, User


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_case_can_be_created_and_defaults_to_open_status():
    user = await _create_user(_unique("caseuser"))

    async with async_session() as db:
        case = Case(user_id=user.id, name="Smith v. Jones")
        db.add(case)
        await db.commit()
        await db.refresh(case)

    assert case.status == "open"
    assert case.description is None


async def test_document_case_id_defaults_to_none():
    user = await _create_user(_unique("caseuser"))

    async with async_session() as db:
        document = Document(
            owner_id=user.id, title="t", filename="t.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

    assert document.case_id is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases.py -v`

Expected: FAIL with `ImportError: cannot import name 'Case' from 'api.models'` (or similar — `Case` doesn't exist yet).

- [ ] **Step 3: Add the `Case` model and `Document.case_id` column**

In `services/api/src/api/models.py`, find the `Document` class (currently ending with its `chunks` relationship line) and add `case_id` as the last column before the `chunks` relationship line:

```python
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
```

Add the new `Case` class immediately after the `GraphEdge` class (the last class in the file):

```python
class Case(Base):
    """A persistent case/matter that documents, tasks, and decisions can
    belong to (Phase 16). Membership is optional everywhere -- a document,
    task, or decision can exist with no case at all, same as before this
    phase. Documents link via a direct `case_id` FK (the most central,
    most-queried relationship); tasks and decisions link via the existing
    polymorphic `GraphEdge` table (Phase 10, ADR 0025) instead of new
    columns on their own tables.
    """

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

Note: `Case` must be defined in the file. Since `Document.case_id` has `ForeignKey("cases.id")` referenced by table name (a string), Python class definition order in the file does not matter for SQLAlchemy's FK resolution — but keep `Case` at the end of the file next to `GraphEdge` (the other Phase 10+ addition) for readability, matching this file's existing chronological-by-phase convention.

- [ ] **Step 4: Create the migration**

Check the current alembic head first:

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/alembic heads`

Expected: `f2a9c6d8b1e4 (head)`

Create `services/api/alembic/versions/a3f7c9e2b5d8_create_cases_table_and_document_case_id.py`:

```python
"""create cases table and document case_id

Revision ID: a3f7c9e2b5d8
Revises: f2a9c6d8b1e4
Create Date: 2026-07-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f7c9e2b5d8'
down_revision: Union[str, None] = 'f2a9c6d8b1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('cases',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=500), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=False, server_default='open'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_cases_user_id', 'cases', ['user_id'])

    op.add_column('documents', sa.Column('case_id', sa.UUID(), nullable=True))
    op.create_foreign_key('fk_documents_case_id', 'documents', 'cases', ['case_id'], ['id'], ondelete='SET NULL')
    op.create_index('ix_documents_case_id', 'documents', ['case_id'])


def downgrade() -> None:
    op.drop_index('ix_documents_case_id', table_name='documents')
    op.drop_constraint('fk_documents_case_id', 'documents', type_='foreignkey')
    op.drop_column('documents', 'case_id')
    op.drop_index('ix_cases_user_id', table_name='cases')
    op.drop_table('cases')
```

Apply it:

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/alembic upgrade head`

Expected: `Running upgrade f2a9c6d8b1e4 -> a3f7c9e2b5d8, create cases table and document case_id` with no errors.

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases.py -v`

Expected: `2 passed`

- [ ] **Step 6: Ruff check**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/api/models.py alembic/versions/a3f7c9e2b5d8_create_cases_table_and_document_case_id.py tests/test_cases.py`

Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
cd /opt/collabrains && git add services/api/src/api/models.py services/api/alembic/versions/a3f7c9e2b5d8_create_cases_table_and_document_case_id.py services/api/tests/test_cases.py
git commit -m "Phase 16 task 1: Case model, Document.case_id, migration"
```

---

### Task 2: Case domain logic (`api/cases.py`)

**Files:**
- Create: `services/api/src/api/cases.py`
- Modify: `services/api/tests/test_cases.py` (add domain-function tests)

**Interfaces:**
- Consumes: `Case`, `Document`, `Task`, `Decision`, `GraphEdge` from `api.models` (all already exist as of Task 1 / prior phases).
- Produces (used by Task 3/4's router):
  - `async def create_case(db: AsyncSession, *, user_id: UUID, name: str, description: str | None = None) -> Case`
  - `async def list_cases(db: AsyncSession, *, user_id: UUID) -> list[Case]`
  - `async def get_case_dashboard(db: AsyncSession, case_id: UUID) -> dict[str, Any] | None` — returns `None` if not found, else `{"case": Case, "documents": list[Document], "tasks": list[Task], "decisions": list[Decision]}`
  - `async def update_case(db: AsyncSession, *, case_id: UUID, name: str | None = None, description: str | None = None, status_value: str | None = None) -> Case | None`
  - `async def delete_case(db: AsyncSession, *, case_id: UUID) -> bool`
  - `async def attach_document_to_case(db: AsyncSession, *, document_id: UUID, case_id: UUID | None) -> Document | None`
  - `async def link_task_to_case(db: AsyncSession, *, case_id: UUID, task_id: UUID) -> bool`
  - `async def link_decision_to_case(db: AsyncSession, *, case_id: UUID, decision_id: UUID) -> bool`
  - None of these functions check ownership — that's the router's job (Task 3/4), matching the existing `api/knowledge_graph.py` / `api/decisions.py` split.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_cases.py` (after the two existing tests, before nothing — end of file):

```python
from api.cases import (
    attach_document_to_case,
    create_case,
    delete_case,
    get_case_dashboard,
    link_decision_to_case,
    link_task_to_case,
    list_cases,
    update_case,
)
from api.models import Decision, GraphEdge, Task


async def _create_document(owner_id) -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="t.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_task(created_by) -> Task:
    async with async_session() as db:
        task = Task(title="Do the thing", source="manual", created_by=created_by)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def _create_decision(user_id) -> Decision:
    async with async_session() as db:
        decision = Decision(user_id=user_id, summary="Approved something")
        db.add(decision)
        await db.commit()
        await db.refresh(decision)
        return decision


async def test_create_case_persists_it():
    user = await _create_user(_unique("caseuser"))
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="Smith v. Jones", description="A matter")
    assert case.name == "Smith v. Jones"
    assert case.description == "A matter"


async def test_list_cases_scoped_to_user():
    user = await _create_user(_unique("caseuser"))
    other = await _create_user(_unique("caseuser"))
    async with async_session() as db:
        await create_case(db, user_id=user.id, name="Mine")
        await create_case(db, user_id=other.id, name="Not mine")

    async with async_session() as db:
        cases = await list_cases(db, user_id=user.id)
    assert all(c.user_id == user.id for c in cases)
    assert any(c.name == "Mine" for c in cases)
    assert not any(c.name == "Not mine" for c in cases)


async def test_update_case_changes_only_given_fields():
    user = await _create_user(_unique("caseuser"))
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="Original", description="Orig desc")

    async with async_session() as db:
        updated = await update_case(db, case_id=case.id, status_value="closed")

    assert updated.name == "Original"
    assert updated.description == "Orig desc"
    assert updated.status == "closed"


async def test_update_case_returns_none_for_unknown_id():
    async with async_session() as db:
        result = await update_case(db, case_id=uuid4(), name="x")
    assert result is None


async def test_attach_document_to_case_sets_case_id():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")

    async with async_session() as db:
        updated = await attach_document_to_case(db, document_id=document.id, case_id=case.id)
    assert updated.case_id == case.id


async def test_attach_document_to_case_with_none_detaches():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)

    async with async_session() as db:
        updated = await attach_document_to_case(db, document_id=document.id, case_id=None)
    assert updated.case_id is None


async def test_link_task_to_case_creates_graph_edge():
    user = await _create_user(_unique("caseuser"))
    task = await _create_task(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        linked = await link_task_to_case(db, case_id=case.id, task_id=task.id)
    assert linked is True

    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(GraphEdge).where(
                GraphEdge.source_type == "task", GraphEdge.source_id == task.id,
                GraphEdge.target_type == "case", GraphEdge.target_id == case.id,
            )
        )
        edges = result.scalars().all()
    assert len(edges) == 1
    assert edges[0].relationship_type == "belongs_to"


async def test_link_decision_to_case_creates_graph_edge():
    user = await _create_user(_unique("caseuser"))
    decision = await _create_decision(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        linked = await link_decision_to_case(db, case_id=case.id, decision_id=decision.id)
    assert linked is True


async def test_get_case_dashboard_assembles_documents_tasks_decisions():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    task = await _create_task(user.id)
    decision = await _create_decision(user.id)

    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)
        await link_task_to_case(db, case_id=case.id, task_id=task.id)
        await link_decision_to_case(db, case_id=case.id, decision_id=decision.id)

    async with async_session() as db:
        dashboard = await get_case_dashboard(db, case.id)

    assert dashboard["case"].id == case.id
    assert [d.id for d in dashboard["documents"]] == [document.id]
    assert [t.id for t in dashboard["tasks"]] == [task.id]
    assert [dec.id for dec in dashboard["decisions"]] == [decision.id]


async def test_get_case_dashboard_returns_none_for_unknown_id():
    async with async_session() as db:
        dashboard = await get_case_dashboard(db, uuid4())
    assert dashboard is None


async def test_delete_case_removes_it_and_its_graph_edges():
    user = await _create_user(_unique("caseuser"))
    task = await _create_task(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await link_task_to_case(db, case_id=case.id, task_id=task.id)

    async with async_session() as db:
        deleted = await delete_case(db, case_id=case.id)
    assert deleted is True

    async with async_session() as db:
        from sqlalchemy import select
        remaining_edges = (
            await db.execute(select(GraphEdge).where(GraphEdge.target_type == "case", GraphEdge.target_id == case.id))
        ).scalars().all()
        remaining_case = await db.get(Case, case.id)
    assert remaining_edges == []
    assert remaining_case is None


async def test_delete_case_nulls_document_case_id():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)
        await delete_case(db, case_id=case.id)

    async with async_session() as db:
        refreshed = await db.get(Document, document.id)
    assert refreshed.case_id is None


async def test_delete_case_returns_false_for_unknown_id():
    async with async_session() as db:
        deleted = await delete_case(db, case_id=uuid4())
    assert deleted is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'api.cases'`

- [ ] **Step 3: Write `services/api/src/api/cases.py`**

```python
"""Case/Matter workspace domain logic (Phase 16).

Documents link to a Case via a direct case_id FK (the most central,
most-queried relationship); tasks and decisions link via the existing
polymorphic GraphEdge table (Phase 10, ADR 0025) rather than new columns
on their own tables. None of these functions check ownership -- that's
the router's job (api/cases_router.py), matching the existing split
between api/knowledge_graph.py (no ownership checks) and
api/decisions.py (checks ownership before calling it).
"""
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Case, Decision, Document, GraphEdge, Task


async def create_case(db: AsyncSession, *, user_id: UUID, name: str, description: str | None = None) -> Case:
    case = Case(user_id=user_id, name=name, description=description)
    db.add(case)
    await db.commit()
    await db.refresh(case)
    return case


async def list_cases(db: AsyncSession, *, user_id: UUID) -> list[Case]:
    result = await db.execute(select(Case).where(Case.user_id == user_id).order_by(Case.created_at.desc()))
    return list(result.scalars().all())


async def update_case(
    db: AsyncSession, *, case_id: UUID, name: str | None = None, description: str | None = None,
    status_value: str | None = None,
) -> Case | None:
    case = await db.get(Case, case_id)
    if case is None:
        return None
    if name is not None:
        case.name = name
    if description is not None:
        case.description = description
    if status_value is not None:
        case.status = status_value
    await db.commit()
    await db.refresh(case)
    return case


async def delete_case(db: AsyncSession, *, case_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    if case is None:
        return False

    edges_result = await db.execute(
        select(GraphEdge).where(GraphEdge.target_type == "case", GraphEdge.target_id == case_id)
    )
    for edge in edges_result.scalars().all():
        await db.delete(edge)

    await db.delete(case)
    await db.commit()
    return True


async def attach_document_to_case(db: AsyncSession, *, document_id: UUID, case_id: UUID | None) -> Document | None:
    document = await db.get(Document, document_id)
    if document is None:
        return None
    document.case_id = case_id
    await db.commit()
    await db.refresh(document)
    return document


async def link_task_to_case(db: AsyncSession, *, case_id: UUID, task_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    task = await db.get(Task, task_id)
    if case is None or task is None:
        return False
    db.add(GraphEdge(
        source_type="task", source_id=task.id, target_type="case", target_id=case.id,
        relationship_type="belongs_to",
    ))
    await db.commit()
    return True


async def link_decision_to_case(db: AsyncSession, *, case_id: UUID, decision_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    decision = await db.get(Decision, decision_id)
    if case is None or decision is None:
        return False
    db.add(GraphEdge(
        source_type="decision", source_id=decision.id, target_type="case", target_id=case.id,
        relationship_type="belongs_to",
    ))
    await db.commit()
    return True


async def get_case_dashboard(db: AsyncSession, case_id: UUID) -> dict[str, Any] | None:
    case = await db.get(Case, case_id)
    if case is None:
        return None

    documents_result = await db.execute(select(Document).where(Document.case_id == case_id))
    documents = list(documents_result.scalars().all())

    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.target_type == "case", GraphEdge.target_id == case_id,
            GraphEdge.relationship_type == "belongs_to",
        )
    )
    edges = list(edges_result.scalars().all())
    task_ids = [edge.source_id for edge in edges if edge.source_type == "task"]
    decision_ids = [edge.source_id for edge in edges if edge.source_type == "decision"]

    tasks: list[Task] = []
    if task_ids:
        tasks_result = await db.execute(select(Task).where(Task.id.in_(task_ids)))
        tasks = list(tasks_result.scalars().all())

    decisions: list[Decision] = []
    if decision_ids:
        decisions_result = await db.execute(select(Decision).where(Decision.id.in_(decision_ids)))
        decisions = list(decisions_result.scalars().all())

    return {"case": case, "documents": documents, "tasks": tasks, "decisions": decisions}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases.py -v`

Expected: all tests pass (16 total: 2 from Task 1 + 14 new).

- [ ] **Step 5: Ruff check**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/api/cases.py tests/test_cases.py`

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd /opt/collabrains && git add services/api/src/api/cases.py services/api/tests/test_cases.py
git commit -m "Phase 16 task 2: Case domain logic (api/cases.py)"
```

---

### Task 3: Case CRUD + dashboard HTTP endpoints (`api/cases_router.py`)

**Files:**
- Create: `services/api/src/api/cases_router.py`
- Modify: `services/api/src/api/main.py` (register the router)
- Test: `services/api/tests/test_cases_router.py` (new file)

**Interfaces:**
- Consumes: every function from Task 2's `api/cases.py`; `api.auth.get_current_user`; `api.db.get_db`.
- Produces: `POST /cases`, `GET /cases`, `GET /cases/{case_id}`, `PATCH /cases/{case_id}`, `DELETE /cases/{case_id}`.

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_cases_router.py`:

```python
from unittest.mock import patch
from uuid import uuid4

from api.ldap_auth import LdapIdentity


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_create_and_get_case(client):
    token = await _login(client, "caserouteruser1")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/cases", headers=headers, json={"name": "Smith v. Jones", "description": "A matter"}
    )
    assert create_response.status_code == 201
    case_id = create_response.json()["id"]
    assert create_response.json()["status"] == "open"

    get_response = await client.get(f"/cases/{case_id}", headers=headers)
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["name"] == "Smith v. Jones"
    assert body["documents"] == []
    assert body["tasks"] == []
    assert body["decisions"] == []


async def test_list_cases_only_shows_the_callers_own(client):
    token_a = await _login(client, "caserouteruser2")
    token_b = await _login(client, "caserouteruser3")

    await client.post("/cases", headers={"Authorization": f"Bearer {token_a}"}, json={"name": "A's case"})
    await client.post("/cases", headers={"Authorization": f"Bearer {token_b}"}, json={"name": "B's case"})

    response = await client.get("/cases", headers={"Authorization": f"Bearer {token_a}"})
    names = {c["name"] for c in response.json()}
    assert "A's case" in names
    assert "B's case" not in names


async def test_get_case_rejects_non_owner(client):
    owner_token = await _login(client, "caserouteruser4")
    intruder_token = await _login(client, "caserouteruser5")

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Owner's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.get(f"/cases/{case_id}", headers={"Authorization": f"Bearer {intruder_token}"})
    assert response.status_code == 403


async def test_get_case_returns_404_for_unknown_id(client):
    token = await _login(client, "caserouteruser6")
    response = await client.get(f"/cases/{uuid4()}", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


async def test_patch_case_updates_status(client):
    token = await _login(client, "caserouteruser7")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    patch_response = await client.patch(f"/cases/{case_id}", headers=headers, json={"status": "closed"})
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "closed"


async def test_patch_case_rejects_invalid_status(client):
    token = await _login(client, "caserouteruser8")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    response = await client.patch(f"/cases/{case_id}", headers=headers, json={"status": "bogus"})
    assert response.status_code == 400


async def test_patch_case_rejects_non_owner(client):
    owner_token = await _login(client, "caserouteruser9")
    intruder_token = await _login(client, "caserouteruser10")

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Owner's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.patch(
        f"/cases/{case_id}", headers={"Authorization": f"Bearer {intruder_token}"}, json={"name": "Hijacked"}
    )
    assert response.status_code == 403


async def test_delete_case(client):
    token = await _login(client, "caserouteruser11")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    delete_response = await client.delete(f"/cases/{case_id}", headers=headers)
    assert delete_response.status_code == 204

    get_response = await client.get(f"/cases/{case_id}", headers=headers)
    assert get_response.status_code == 404


async def test_delete_case_rejects_non_owner(client):
    owner_token = await _login(client, "caserouteruser12")
    intruder_token = await _login(client, "caserouteruser13")

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {owner_token}"}, json={"name": "Owner's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.delete(f"/cases/{case_id}", headers={"Authorization": f"Bearer {intruder_token}"})
    assert response.status_code == 403


async def test_create_case_rejects_missing_token(client):
    response = await client.post("/cases", json={"name": "x"})
    assert response.status_code == 401


async def test_create_case_rejects_empty_name(client):
    token = await _login(client, "caserouteruser21")
    response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {token}"}, json={"name": ""}
    )
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases_router.py -v`

Expected: FAIL — all requests to `/cases*` return 404 (no such route registered yet).

- [ ] **Step 3: Write `services/api/src/api/cases_router.py`**

```python
"""Case/Matter workspace CRUD + dashboard endpoints (Phase 16).

Ownership check pattern copied exactly from api/decisions.py: a case's
user_id (or admin role) gates all access to it. Document/task/decision
attach-to-case endpoints live in Task 4 of this same file.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.cases import create_case, delete_case, get_case_dashboard, list_cases, update_case
from api.db import get_db
from api.models import Case, User

router = APIRouter(tags=["cases"])


class CaseCreateRequest(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None


class CaseUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    status: str | None = None


class CaseOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime


class CaseDocumentOut(BaseModel):
    id: UUID
    title: str


class CaseTaskOut(BaseModel):
    id: UUID
    title: str
    status: str


class CaseDecisionOut(BaseModel):
    id: UUID
    summary: str


class CaseDashboardOut(CaseOut):
    documents: list[CaseDocumentOut]
    tasks: list[CaseTaskOut]
    decisions: list[CaseDecisionOut]


def _require_case_owner(case: Case, current_user: User) -> None:
    if case.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to access this case")


@router.post("/cases", response_model=CaseOut, status_code=status.HTTP_201_CREATED)
async def create_case_endpoint(
    request: CaseCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Case:
    return await create_case(db, user_id=current_user.id, name=request.name, description=request.description)


@router.get("/cases", response_model=list[CaseOut])
async def list_cases_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Case]:
    return await list_cases(db, user_id=current_user.id)


@router.get("/cases/{case_id}", response_model=CaseDashboardOut)
async def get_case_endpoint(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseDashboardOut:
    result: dict[str, Any] | None = await get_case_dashboard(db, case_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")

    case = result["case"]
    _require_case_owner(case, current_user)

    return CaseDashboardOut(
        id=case.id, name=case.name, description=case.description, status=case.status, created_at=case.created_at,
        documents=[CaseDocumentOut(id=doc.id, title=doc.title) for doc in result["documents"]],
        tasks=[CaseTaskOut(id=task.id, title=task.title, status=task.status) for task in result["tasks"]],
        decisions=[CaseDecisionOut(id=dec.id, summary=dec.summary) for dec in result["decisions"]],
    )


@router.patch("/cases/{case_id}", response_model=CaseOut)
async def update_case_endpoint(
    case_id: UUID,
    request: CaseUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Case:
    existing = await db.get(Case, case_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(existing, current_user)

    if request.status is not None and request.status not in ("open", "closed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be 'open' or 'closed'")

    updated = await update_case(
        db, case_id=case_id, name=request.name, description=request.description, status_value=request.status,
    )
    return updated


@router.delete("/cases/{case_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_case_endpoint(
    case_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    existing = await db.get(Case, case_id)
    if existing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(existing, current_user)
    await delete_case(db, case_id=case_id)
```

- [ ] **Step 4: Register the router in `services/api/src/api/main.py`**

Add the import (alphabetically, after `from api.auth import router as auth_router`, before `from api.chat import router as chat_router`):

```python
from api.cases_router import router as cases_router
```

Add the registration (anywhere in the `app.include_router(...)` block — add it right after `app.include_router(auth_router)`):

```python
app.include_router(cases_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases_router.py -v`

Expected: `11 passed`

- [ ] **Step 6: Ruff check**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/api/cases_router.py src/api/main.py tests/test_cases_router.py`

Expected: `All checks passed!`

- [ ] **Step 7: Commit**

```bash
cd /opt/collabrains && git add services/api/src/api/cases_router.py services/api/src/api/main.py services/api/tests/test_cases_router.py
git commit -m "Phase 16 task 3: Case CRUD + dashboard HTTP endpoints"
```

---

### Task 4: Document/Task/Decision linking endpoints

**Files:**
- Modify: `services/api/src/api/cases_router.py` (add three endpoints)
- Modify: `services/api/tests/test_cases_router.py` (add tests)

**Interfaces:**
- Consumes: `api.cases.attach_document_to_case`, `link_task_to_case`, `link_decision_to_case` (all exist as of Task 2).
- Produces: `PUT /documents/{document_id}/case`, `POST /cases/{case_id}/tasks/{task_id}`, `POST /cases/{case_id}/decisions/{decision_id}`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_cases_router.py`:

```python
from api.db import async_session
from api.models import Decision, Document, Task


async def _user_id_for(username: str):
    from sqlalchemy import select
    from api.models import User

    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def _create_document(owner_id) -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="t.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_task(created_by) -> Task:
    async with async_session() as db:
        task = Task(title="Do the thing", source="manual", created_by=created_by)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def _create_decision(user_id) -> Decision:
    async with async_session() as db:
        decision = Decision(user_id=user_id, summary="Approved something")
        db.add(decision)
        await db.commit()
        await db.refresh(decision)
        return decision


async def test_attach_document_to_case_via_put(client):
    token = await _login(client, "caserouteruser14")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for("caserouteruser14")
    document = await _create_document(user_id)

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    put_response = await client.put(
        f"/documents/{document.id}/case", headers=headers, json={"case_id": case_id}
    )
    assert put_response.status_code == 200

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [d["id"] for d in dashboard.json()["documents"]] == [str(document.id)]


async def test_attach_document_rejects_non_owner_document(client):
    owner_token = await _login(client, "caserouteruser15")
    intruder_token = await _login(client, "caserouteruser16")
    owner_id = await _user_id_for("caserouteruser15")
    document = await _create_document(owner_id)

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {intruder_token}"}, json={"name": "Intruder's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.put(
        f"/documents/{document.id}/case",
        headers={"Authorization": f"Bearer {intruder_token}"}, json={"case_id": case_id},
    )
    assert response.status_code == 403


async def test_link_task_to_case(client):
    token = await _login(client, "caserouteruser17")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for("caserouteruser17")
    task = await _create_task(user_id)

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    link_response = await client.post(f"/cases/{case_id}/tasks/{task.id}", headers=headers)
    assert link_response.status_code == 204

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [t["id"] for t in dashboard.json()["tasks"]] == [str(task.id)]


async def test_link_task_rejects_non_owner_task(client):
    owner_token = await _login(client, "caserouteruser18")
    intruder_token = await _login(client, "caserouteruser19")
    owner_id = await _user_id_for("caserouteruser18")
    task = await _create_task(owner_id)

    create_response = await client.post(
        "/cases", headers={"Authorization": f"Bearer {intruder_token}"}, json={"name": "Intruder's case"}
    )
    case_id = create_response.json()["id"]

    response = await client.post(
        f"/cases/{case_id}/tasks/{task.id}", headers={"Authorization": f"Bearer {intruder_token}"}
    )
    assert response.status_code == 403


async def test_link_decision_to_case(client):
    token = await _login(client, "caserouteruser20")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for("caserouteruser20")
    decision = await _create_decision(user_id)

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    link_response = await client.post(f"/cases/{case_id}/decisions/{decision.id}", headers=headers)
    assert link_response.status_code == 204

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [d["id"] for d in dashboard.json()["decisions"]] == [str(decision.id)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases_router.py -v`

Expected: FAIL — `PUT /documents/{id}/case` and `POST /cases/{id}/tasks/{id}` / `.../decisions/{id}` return 404 (not registered yet).

- [ ] **Step 3: Add the three endpoints to `services/api/src/api/cases_router.py`**

Add these imports to the top of the file (extend the existing `from api.cases import ...` line and add `Decision`, `Document`, `Task` to the existing `from api.models import ...` line):

```python
from api.cases import (
    attach_document_to_case,
    create_case,
    delete_case,
    get_case_dashboard,
    link_decision_to_case,
    link_task_to_case,
    list_cases,
    update_case,
)
```

```python
from api.models import Case, Decision, Document, Task, User
```

Add this new Pydantic model near the other `*Request` classes:

```python
class DocumentCaseRequest(BaseModel):
    case_id: UUID | None = None
```

Add these three endpoints at the end of the file:

```python
@router.put("/documents/{document_id}/case", response_model=CaseDocumentOut)
async def set_document_case_endpoint(
    document_id: UUID,
    request: DocumentCaseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CaseDocumentOut:
    document = await db.get(Document, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")
    if document.owner_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to modify this document")

    if request.case_id is not None:
        case = await db.get(Case, request.case_id)
        if case is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
        _require_case_owner(case, current_user)

    updated = await attach_document_to_case(db, document_id=document_id, case_id=request.case_id)
    return CaseDocumentOut(id=updated.id, title=updated.title)


@router.post("/cases/{case_id}/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_task_endpoint(
    case_id: UUID,
    task_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(case, current_user)

    task = await db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.created_by != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to link this task")

    await link_task_to_case(db, case_id=case_id, task_id=task_id)


@router.post("/cases/{case_id}/decisions/{decision_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_decision_endpoint(
    case_id: UUID,
    decision_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(case, current_user)

    decision = await db.get(Decision, decision_id)
    if decision is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Decision not found")
    if decision.user_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed to link this decision")

    await link_decision_to_case(db, case_id=case_id, decision_id=decision_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_cases_router.py -v`

Expected: `16 passed`

- [ ] **Step 5: Ruff check**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/api/cases_router.py tests/test_cases_router.py`

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd /opt/collabrains && git add services/api/src/api/cases_router.py services/api/tests/test_cases_router.py
git commit -m "Phase 16 task 4: document/task/decision case-linking endpoints"
```

---

### Task 5: Planning Engine `summarize_case` gains `case_id` support

**Files:**
- Modify: `services/api/src/api/planning_engine.py`
- Modify: `services/api/tests/test_planning_engine.py`

**Interfaces:**
- Consumes: `api.models.Document` (already imported in `planning_engine.py`).
- Produces: `create_plan(db, user_id=..., goal_type="summarize_case", goal_params={"case_id": ...})` now works in addition to the existing `goal_params={"document_ids": [...]}` form. `build_steps()` itself is **not** modified — it stays synchronous with its existing signature; the new resolution happens in `create_plan()`, which already has `db` access and is already `async`.

- [ ] **Step 1: Write the failing test**

Append to `services/api/tests/test_planning_engine.py` (after the existing `test_create_plan_honors_an_organization_level_approval_override` test):

```python
async def test_create_plan_resolves_case_id_to_its_documents_for_summarize_case(client):
    from api.cases import attach_document_to_case, create_case
    from api.models import Document

    token, username = await _login(client, "plan-case-user")
    user_id = await _user_id_for(username)

    async with async_session() as db:
        document_a = Document(
            owner_id=user_id, title="a", filename="a.pdf", mime_type="application/pdf", status="ready",
        )
        document_b = Document(
            owner_id=user_id, title="b", filename="b.pdf", mime_type="application/pdf", status="ready",
        )
        db.add_all([document_a, document_b])
        await db.commit()
        await db.refresh(document_a)
        await db.refresh(document_b)

        case = await create_case(db, user_id=user_id, name="A case")
        await attach_document_to_case(db, document_id=document_a.id, case_id=case.id)
        await attach_document_to_case(db, document_id=document_b.id, case_id=case.id)

    async with async_session() as db:
        plan = await create_plan(db, user_id=user_id, goal_type="summarize_case", goal_params={"case_id": str(case.id)})

    assert plan.status == "running"
    resolved_document_ids = set(plan.goal_params["document_ids"])
    assert resolved_document_ids == {str(document_a.id), str(document_b.id)}


async def test_create_plan_prefers_case_id_over_document_ids_when_both_given(client):
    from api.cases import attach_document_to_case, create_case
    from api.models import Document

    token, username = await _login(client, "plan-case-precedence-user")
    user_id = await _user_id_for(username)

    async with async_session() as db:
        document = Document(
            owner_id=user_id, title="a", filename="a.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        case = await create_case(db, user_id=user_id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user_id, goal_type="summarize_case",
            goal_params={"case_id": str(case.id), "document_ids": ["ignored-value"]},
        )

    assert plan.goal_params["document_ids"] == [str(document.id)]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_planning_engine.py -v -k case_id`

Expected: FAIL — `plan.goal_params["document_ids"]` raises `KeyError` (goal_params still only has `case_id`, never resolved).

- [ ] **Step 3: Modify `services/api/src/api/planning_engine.py`**

Add this new function immediately before `create_plan`:

```python
async def _resolve_case_id(db: AsyncSession, goal_type: str, goal_params: dict[str, Any]) -> dict[str, Any]:
    """If summarize_case is given a case_id, resolve it to that case's
    document_ids (Phase 16) -- case_id takes precedence over any
    document_ids also provided, since a caller giving both is ambiguous
    and case_id is the more specific signal.
    """
    if goal_type != "summarize_case" or "case_id" not in goal_params:
        return goal_params

    case_id = goal_params["case_id"]
    if isinstance(case_id, str):
        case_id = UUID(case_id)

    result = await db.execute(select(Document.id).where(Document.case_id == case_id))
    document_ids = [str(doc_id) for doc_id in result.scalars().all()]
    return {**goal_params, "document_ids": document_ids}
```

Modify `create_plan` to call it. Find this block:

```python
    step_specs = build_steps(goal_type, goal_params)
```

Replace it with:

```python
    goal_params = await _resolve_case_id(db, goal_type, goal_params)
    step_specs = build_steps(goal_type, goal_params)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_planning_engine.py -v`

Expected: all tests in the file pass (including the two new ones and every pre-existing one — `build_steps()` itself was not touched, so nothing else in this file should change behavior).

- [ ] **Step 5: Ruff check**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/api/planning_engine.py tests/test_planning_engine.py`

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd /opt/collabrains && git add services/api/src/api/planning_engine.py services/api/tests/test_planning_engine.py
git commit -m "Phase 16 task 5: summarize_case accepts a case_id"
```

---

### Task 6: ADR, full-suite verification, PR

**Files:**
- Create: `docs/adr/0031-phase16-case-workspace.md`

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0031-phase16-case-workspace.md` summarizing the decisions already made and approved in `docs/superpowers/specs/2026-07-03-case-workspace-design.md`: `Case` table + `Document.case_id` direct FK + `GraphEdge` reuse for Task/Decision links; optional membership, no migration/backfill risk; `summarize_case` `case_id` support with `case_id`-takes-precedence semantics; explicitly deferred items (case-level sharing/collaboration, automatic case detection, richer status workflow). Follow the exact style of `docs/adr/0025-phase10-knowledge-graph-2.md` (Status/Context/Decision/Consequences sections).

- [ ] **Step 2: Run the full test suite**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest -q`

Expected: all new tests pass; the same 6 pre-existing, unrelated failures (`test_chat_completion_sends_json_format_when_json_mode_enabled`, the two `on_behalf_of` tests in `test_chat.py`, the two in `test_documents.py`, and `test_entity_graph_returns_one_hop_neighbors_and_edges`) reproduce identically — verify with `git stash` against unmodified `main` if any doubt remains, matching this project's established verification discipline.

- [ ] **Step 3: Ruff check the whole codebase**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/ tests/`

Expected: `All checks passed!`

- [ ] **Step 4: Check for stray git artifacts**

Run: `cd /opt/collabrains && git status --short`

Expected: only the ADR file is untracked; no `uv.lock`/`.venv` artifacts anywhere.

- [ ] **Step 5: Commit the ADR, push, open the draft PR**

```bash
cd /opt/collabrains
git add docs/adr/0031-phase16-case-workspace.md
git commit -m "Phase 16: case/matter workspace"
git push -u origin phase-16-case-workspace
gh pr create --draft --base main --head phase-16-case-workspace \
  --title "Phase 16: Case/Matter Workspace" \
  --body "See docs/superpowers/specs/2026-07-03-case-workspace-design.md for the full design and docs/adr/0031-phase16-case-workspace.md for the final decisions. Adds a Case table, Document.case_id, GraphEdge-based Task/Decision linking, a case dashboard endpoint, and summarize_case case_id support."
```
