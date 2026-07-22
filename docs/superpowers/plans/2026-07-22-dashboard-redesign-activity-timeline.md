# Dashboard Redesign + Activity Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a new `GET /dashboard/activity` endpoint that merges recent
documents/tasks/cases/entities (each scoped by that resource's own real
visibility rule) into one feed, surface it as a new `ActivityTimeline`
dashboard widget, and restyle the existing dashboard (hero banner, stat
tiles) with sub-project 1's design tokens.

**Architecture:** One new backend service function + router (FastAPI,
async SQLAlchemy, mirroring the exact scoping predicates already used by
`documents.py`/`tasks.py`/`cases.py`/`entities.py`'s own list endpoints —
not a new authorization scheme), one new frontend widget reusing the
existing `DashboardWidgetCard` shell as-is, and a token-only visual pass
on `Dashboard.tsx`'s existing hero/stat-tile markup.

**Tech Stack:** FastAPI + SQLAlchemy (async) + pytest (backend); React +
TypeScript + Vitest/Testing Library (frontend).

Full context: `docs/superpowers/specs/2026-07-22-dashboard-redesign-activity-timeline-design.md`.

## Global Constraints

- Reuse each resource's *existing real* scoping rule exactly — do not
  invent a simplified version. In particular, Task visibility is **not**
  just `created_by == user OR document owner == user`; it also includes
  tasks whose document belongs to a case the user has an *accepted*
  `CaseMember` row for (the exact predicate `tasks.py`'s `list_tasks`
  already uses) — verified by reading that function directly, not assumed.
- No new authorization abstraction — plain `select()` queries per model,
  same shape as `cases.py`'s existing `get_case_dashboard`.
- `DashboardWidgetCard` (the shared widget shell) is not modified — it
  already handles loading/empty/collapse correctly.
- Visual restyle is token-substitution only (`rounded-2xl` → `rounded-ds-lg`,
  the accent-to-accent-hover gradient → `bg-gradient-brand`) — same pixel
  values, no layout/structure changes to the existing hero or stat tiles.
- **Backend test execution requires the remote server** — this local
  checkout has no local Postgres/Redis/Docker. `services/api` is
  bind-mounted into the `api` container at `/opt/collabrains` on
  `178.254.22.178` (confirmed: `volumes: - ./services/api:/app` in
  `docker-compose.yml`), the same live-edit pattern already established
  for `apps/web`. Every backend test-run step below is an
  rsync-to-server-then-`docker compose exec`-pytest round trip. **This
  session's sandbox has blocked raw `rsync`/`ssh` commands with plaintext
  credentials or bulk remote writes before** (a safety classifier, not a
  real permissions issue) — if a step is blocked, ask the user to run it
  via a `!`-prefixed command instead of trying to route around the block.
- This project commits directly to `main` (no PR flow) — each task ends
  with a local commit. Do **not** `git push` or deploy as part of this
  plan; that's a separate, explicit step once everything is verified.

---

### Task 1: Backend — `GET /dashboard/activity`

**Files:**
- Create: `services/api/src/api/dashboard.py`
- Create: `services/api/src/api/dashboard_router.py`
- Modify: `services/api/src/api/main.py`
- Test: `services/api/tests/test_dashboard_router.py`

**Interfaces:**
- Produces: `get_user_activity(db: AsyncSession, *, user_id: UUID, limit: int = 15) -> list[ActivityItem]`
  (plain dataclass-like object: `type`, `id`, `title`, `created_at`, `link`).
  `GET /dashboard/activity` → `list[ActivityItemOut]` (Pydantic model, same
  four fields, JSON-serialized). Task 2's API client consumes this exact
  response shape.

- [ ] **Step 1: Write the failing tests**

Create `services/api/tests/test_dashboard_router.py`:

```python
from unittest.mock import patch

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Case, CaseMember, Document, Entity, Task, User


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _user_id_for(username: str):
    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


async def _create_document(owner_id, title: str = "t") -> Document:
    async with async_session() as db:
        document = Document(owner_id=owner_id, title=title, filename="t.pdf", mime_type="application/pdf", status="ready")
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_task(*, created_by=None, document_id=None, title: str = "Do the thing") -> Task:
    async with async_session() as db:
        task = Task(title=title, source="manual", created_by=created_by, document_id=document_id)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def _create_case(user_id, name: str = "A case") -> Case:
    async with async_session() as db:
        case = Case(user_id=user_id, name=name)
        db.add(case)
        await db.commit()
        await db.refresh(case)
        return case


async def _create_entity(owner_id, name: str = "Acme Corp") -> Entity:
    async with async_session() as db:
        entity = Entity(owner_id=owner_id, name=name, entity_type="organization")
        db.add(entity)
        await db.commit()
        await db.refresh(entity)
        return entity


async def test_activity_excludes_another_users_document(client):
    await _login(client, "dashboarduser1")
    user_a_id = await _user_id_for("dashboarduser1")
    token_b = await _login(client, "dashboarduser2")

    await _create_document(user_a_id, title="User A's document")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token_b}"})
    assert response.status_code == 200
    assert "User A's document" not in [item["title"] for item in response.json()]


async def test_activity_includes_the_current_users_own_document(client):
    token = await _login(client, "dashboarduser3")
    user_id = await _user_id_for("dashboarduser3")
    await _create_document(user_id, title="My document")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    matching = [item for item in response.json() if item["title"] == "My document"]
    assert len(matching) == 1
    assert matching[0]["type"] == "document"
    assert matching[0]["link"] == f"/documents/{matching[0]['id']}"


async def test_activity_includes_a_case_only_after_membership_is_accepted(client):
    await _login(client, "dashboarduser4")
    owner_id = await _user_id_for("dashboarduser4")
    member_token = await _login(client, "dashboarduser5")
    member_id = await _user_id_for("dashboarduser5")

    case = await _create_case(owner_id, name="Shared case")
    async with async_session() as db:
        db.add(CaseMember(case_id=case.id, user_id=member_id, status="pending"))
        await db.commit()

    pending_response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {member_token}"})
    assert "Shared case" not in [item["title"] for item in pending_response.json()]

    async with async_session() as db:
        row = (
            await db.execute(select(CaseMember).where(CaseMember.case_id == case.id, CaseMember.user_id == member_id))
        ).scalar_one()
        row.status = "accepted"
        await db.commit()

    accepted_response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {member_token}"})
    assert "Shared case" in [item["title"] for item in accepted_response.json()]


async def test_activity_includes_an_unassigned_task_via_its_documents_owner(client):
    token = await _login(client, "dashboarduser6")
    user_id = await _user_id_for("dashboarduser6")
    document = await _create_document(user_id, title="Doc with a task")
    await _create_task(created_by=None, document_id=document.id, title="Extracted task")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    matching = [item for item in response.json() if item["type"] == "task" and item["title"] == "Extracted task"]
    assert len(matching) == 1
    assert matching[0]["link"] == f"/documents/{document.id}"


async def test_activity_merges_and_sorts_all_types_by_recency(client):
    token = await _login(client, "dashboarduser7")
    user_id = await _user_id_for("dashboarduser7")
    await _create_document(user_id, title="Oldest")
    await _create_task(created_by=user_id, title="Middle")
    await _create_case(user_id, name="Newest")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    ordered_titles = [item["title"] for item in response.json() if item["title"] in {"Oldest", "Middle", "Newest"}]
    assert ordered_titles == ["Newest", "Middle", "Oldest"]


async def test_activity_includes_the_current_users_entity_including_pending_review(client):
    token = await _login(client, "dashboarduser8")
    user_id = await _user_id_for("dashboarduser8")
    await _create_entity(user_id, name="Pending Co")

    response = await client.get("/dashboard/activity", headers={"Authorization": f"Bearer {token}"})
    matching = [item for item in response.json() if item["type"] == "entity" and item["title"] == "Pending Co"]
    assert len(matching) == 1
    assert matching[0]["link"] == f"/entities/{matching[0]['id']}"
```

- [ ] **Step 2: Sync to the server and run the tests to verify they fail**

```bash
rsync -az --exclude='__pycache__' --exclude='.venv' --exclude='*.egg-info' --exclude='.pytest_cache' \
  -e "ssh -o ConnectTimeout=8" \
  ~/dev/collabrains-next/services/api/ root@178.254.22.178:/opt/collabrains/services/api/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_dashboard_router.py -v"
```

Expected: FAIL — `ModuleNotFoundError` / `ImportError` for `api.dashboard`
(doesn't exist yet), and/or 404s from `/dashboard/activity` (router not
registered yet).

- [ ] **Step 3: Write the service function**

Create `services/api/src/api/dashboard.py`:

```python
"""Dashboard aggregation queries (sub-project 2 of the app-shell redesign).

The Activity Timeline merges recent items across four resource types, each
scoped by that resource's own existing visibility rule -- not a new,
parallel authorization scheme. Every WHERE clause below mirrors the exact
predicate the corresponding list endpoint already uses (see the comment on
each block), verified by reading those functions directly rather than
assumed.
"""
from uuid import UUID

from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Case, CaseMember, Document, Entity, Task


class ActivityItem:
    def __init__(self, *, type: str, id: UUID, title: str, created_at, link: str) -> None:
        self.type = type
        self.id = id
        self.title = title
        self.created_at = created_at
        self.link = link


async def get_user_activity(db: AsyncSession, *, user_id: UUID, limit: int = 15) -> list[ActivityItem]:
    # Documents: same scoping as documents.py's list_documents (non-admin branch).
    documents = list(
        (
            await db.execute(
                select(Document).where(Document.owner_id == user_id).order_by(Document.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )

    # Tasks: same scoping as tasks.py's list_tasks (non-admin branch) --
    # created_by == user, OR the task's document is owned by the user, OR
    # the task's document belongs to a case the user has *accepted*
    # membership on.
    member_exists = exists(
        select(CaseMember.id).where(
            CaseMember.case_id == Document.case_id,
            CaseMember.user_id == user_id,
            CaseMember.status == "accepted",
        )
    )
    tasks = list(
        (
            await db.execute(
                select(Task)
                .outerjoin(Document, Task.document_id == Document.id)
                .where(or_(Task.created_by == user_id, Document.owner_id == user_id, member_exists))
                .order_by(Task.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    # Cases: same scoping as cases.py's list_cases -- owned, or *accepted* member.
    cases = list(
        (
            await db.execute(
                select(Case)
                .outerjoin(CaseMember, CaseMember.case_id == Case.id)
                .where(
                    or_(
                        Case.user_id == user_id,
                        (CaseMember.user_id == user_id) & (CaseMember.status == "accepted"),
                    )
                )
                .order_by(Case.created_at.desc())
                .distinct()
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    # Entities: same owner scoping as entities.py's list_entities, but
    # deliberately NOT filtered to status="confirmed" -- a newly-extracted
    # pending_review entity is legitimately recent activity here.
    entities = list(
        (
            await db.execute(
                select(Entity).where(Entity.owner_id == user_id).order_by(Entity.created_at.desc()).limit(limit)
            )
        )
        .scalars()
        .all()
    )

    items = (
        [
            ActivityItem(type="document", id=d.id, title=d.title, created_at=d.created_at, link=f"/documents/{d.id}")
            for d in documents
        ]
        + [
            ActivityItem(
                type="task",
                id=t.id,
                title=t.title,
                created_at=t.created_at,
                link=f"/documents/{t.document_id}" if t.document_id else "/tasks",
            )
            for t in tasks
        ]
        + [ActivityItem(type="case", id=c.id, title=c.name, created_at=c.created_at, link=f"/cases/{c.id}") for c in cases]
        + [
            ActivityItem(type="entity", id=e.id, title=e.name, created_at=e.created_at, link=f"/entities/{e.id}")
            for e in entities
        ]
    )
    items.sort(key=lambda item: item.created_at, reverse=True)
    return items[:limit]
```

- [ ] **Step 4: Write the router**

Create `services/api/src/api/dashboard_router.py`:

```python
"""Dashboard aggregation endpoints (sub-project 2 of the app-shell redesign)."""
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.dashboard import get_user_activity
from api.db import get_db
from api.models import User

router = APIRouter(tags=["dashboard"])


class ActivityItemOut(BaseModel):
    type: Literal["document", "task", "case", "entity"]
    id: UUID
    title: str
    created_at: datetime
    link: str


@router.get("/dashboard/activity", response_model=list[ActivityItemOut])
async def get_dashboard_activity(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ActivityItemOut]:
    items = await get_user_activity(db, user_id=current_user.id)
    return [
        ActivityItemOut(type=item.type, id=item.id, title=item.title, created_at=item.created_at, link=item.link)
        for item in items
    ]
```

- [ ] **Step 5: Register the router in `main.py`**

In `services/api/src/api/main.py`, add the import after `from api.chat import
router as chat_router` and before `from api.db import engine`:

```python
from api.dashboard_router import router as dashboard_router
```

And add the registration after the last `app.include_router(...)` line
(`app.include_router(appointments_router)`):

```python
app.include_router(dashboard_router)
```

- [ ] **Step 6: Sync to the server and run the tests to verify they pass**

```bash
rsync -az --exclude='__pycache__' --exclude='.venv' --exclude='*.egg-info' --exclude='.pytest_cache' \
  -e "ssh -o ConnectTimeout=8" \
  ~/dev/collabrains-next/services/api/ root@178.254.22.178:/opt/collabrains/services/api/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_dashboard_router.py -v"
```

Expected: PASS (6/6).

- [ ] **Step 7: Run the full backend suite as a regression check**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T api pytest"
```

Expected: no new failures introduced by this task. (This backend suite is
**not** test-isolated — per this project's own documented history it
shares one live Postgres with no per-test transaction rollback, so some
pre-existing failures unrelated to this change may already be present;
compare against a baseline run if unsure whether a failure is new.)

- [ ] **Step 8: Commit**

```bash
git add services/api/src/api/dashboard.py services/api/src/api/dashboard_router.py services/api/src/api/main.py services/api/tests/test_dashboard_router.py
git commit -m "feat(dashboard): add GET /dashboard/activity aggregation endpoint"
```

---

### Task 2: Frontend — `ActivityTimeline` widget (+ API client)

**Note on scope, resolved during plan self-review:** originally planned as
two tasks (a standalone API-client task, then the widget). Checked
`apps/web/src/lib/api.test.ts` first — **none** of the existing `list*`
wrapper functions (`listCases`, `listDocuments`, `listTasks`,
`listEntities`) have a dedicated test there (confirmed: `grep` for each
name in that file returns nothing); it only tests the generic `request()`
wrapper's cross-cutting behavior (Content-Type handling, FormData, etc.)
plus functions with real extra logic. Adding a dedicated test for
`listDashboardActivity` — a thin one-line wrapper with no logic of its own
— would be inconsistent with that established convention. Folded into this
task instead: the API client addition is Step 1 here, with no separate
red/green cycle of its own; its correctness is exercised by this task's
widget test (Step 3 mocks and calls it) same as every other `list*`
function in this codebase.

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/components/ActivityTimeline.tsx`
- Test: `apps/web/src/components/ActivityTimeline.test.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`

**Interfaces:**
- Consumes: `GET /dashboard/activity` (Task 1's response shape),
  `DashboardWidgetCard` (existing, unmodified).
- Produces: `ActivityItemOut` type + `listDashboardActivity(): Promise<ActivityItemOut[]>`
  in `api.ts`; `ActivityTimeline(): JSX.Element` — a self-contained widget
  (fetches its own data, like the pattern `AlertsBell` already uses,
  rather than receiving data as props) so `Dashboard.tsx` only needs to
  render `<ActivityTimeline />` in Task 3, no new state wiring there.

- [ ] **Step 1: Add the API client type and function**

In `apps/web/src/lib/api.ts`, add near the other `*Out` interfaces (e.g.
next to `CaseOut`):

```ts
export interface ActivityItemOut {
  type: "document" | "task" | "case" | "entity";
  id: string;
  title: string;
  created_at: string;
  link: string;
}
```

And near the other `list*` functions (e.g. next to `listCases`):

```ts
export function listDashboardActivity(): Promise<ActivityItemOut[]> {
  return request<ActivityItemOut[]>("/dashboard/activity");
}
```

- [ ] **Step 2: Add the i18n keys**

In `apps/web/src/locales/en.json`, inside the `"dashboard"` object, after
`"recentCasesEmpty": "No cases yet.",`:

```json
    "activityTimelineTitle": "Recent activity",
    "activityTimelineEmpty": "No recent activity.",
```

In `apps/web/src/locales/nl.json`, same position:

```json
    "activityTimelineTitle": "Recente activiteit",
    "activityTimelineEmpty": "Geen recente activiteit.",
```

In `apps/web/src/locales/de.json`, same position:

```json
    "activityTimelineTitle": "Letzte Aktivität",
    "activityTimelineEmpty": "Keine aktuelle Aktivität.",
```

- [ ] **Step 2: Write the failing test**

Create `apps/web/src/components/ActivityTimeline.test.tsx`:

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ActivityTimeline } from "./ActivityTimeline";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listDashboardActivity: vi.fn() };
});

function renderWidget() {
  return render(
    <MemoryRouter>
      <ActivityTimeline />
    </MemoryRouter>
  );
}

describe("ActivityTimeline", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders each activity item as a link with its title", async () => {
    vi.mocked(api.listDashboardActivity).mockResolvedValue([
      { type: "document", id: "d1", title: "Invoice Q3", created_at: "2026-07-22T10:00:00Z", link: "/documents/d1" },
      { type: "case", id: "c1", title: "Verhuizing Jansen", created_at: "2026-07-21T10:00:00Z", link: "/cases/c1" },
    ]);
    renderWidget();
    expect(await screen.findByRole("link", { name: /Invoice Q3/ })).toHaveAttribute("href", "/documents/d1");
    expect(screen.getByRole("link", { name: /Verhuizing Jansen/ })).toHaveAttribute("href", "/cases/c1");
  });

  it("shows the empty message when there is no activity", async () => {
    vi.mocked(api.listDashboardActivity).mockResolvedValue([]);
    renderWidget();
    expect(await screen.findByText("No recent activity.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/components/ActivityTimeline.test.tsx`
Expected: FAIL — `Cannot find module './ActivityTimeline'`.

- [ ] **Step 4: Write the implementation**

Create `apps/web/src/components/ActivityTimeline.tsx`:

```tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { FileText, CheckSquare, FolderOpen, Users, type LucideIcon } from "lucide-react";
import { listDashboardActivity, type ActivityItemOut } from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";
import { DashboardWidgetCard } from "./DashboardWidgetCard";

const TYPE_ICON: Record<ActivityItemOut["type"], LucideIcon> = {
  document: FileText,
  task: CheckSquare,
  case: FolderOpen,
  entity: Users,
};

export function ActivityTimeline() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
  const [items, setItems] = useState<ActivityItemOut[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listDashboardActivity()
      .then(setItems)
      .catch(() => {
        // Same degrade-to-empty-state pattern as every other Dashboard widget.
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <DashboardWidgetCard
      title={t("dashboard.activityTimelineTitle")}
      loading={loading}
      isEmpty={items.length === 0}
      emptyMessage={t("dashboard.activityTimelineEmpty")}
    >
      <ul className="flex flex-col gap-2">
        {items.map((item) => {
          const Icon = TYPE_ICON[item.type];
          return (
            <li key={`${item.type}-${item.id}`} className="flex items-center gap-2 text-sm">
              <Icon className="h-4 w-4 shrink-0 text-ink-3" aria-hidden="true" />
              <Link to={item.link} className="flex-1 truncate text-ink hover:text-accent">
                {item.title}
              </Link>
              <span className="shrink-0 text-xs text-ink-3">{formatDate(item.created_at)}</span>
            </li>
          );
        })}
      </ul>
    </DashboardWidgetCard>
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/components/ActivityTimeline.test.tsx`
Expected: PASS (2/2).

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/ActivityTimeline.tsx apps/web/src/components/ActivityTimeline.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(dashboard): add ActivityTimeline widget"
```

---

### Task 3: Frontend — wire `ActivityTimeline` into `Dashboard.tsx` + visual restyle

**Files:**
- Modify: `apps/web/src/routes/Dashboard.tsx`
- Modify: `apps/web/src/routes/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `ActivityTimeline` (Task 2).
- Produces: no new exports — `Dashboard`'s default export is unchanged.

- [ ] **Step 1: Write the failing test**

In `apps/web/src/routes/Dashboard.test.tsx`, add to the `vi.mock("../lib/api", ...)`
mock object: `listDashboardActivity: vi.fn(),` — and to the `beforeEach`:
`vi.mocked(api.listDashboardActivity).mockResolvedValue([]);`. Then add a
new test:

```tsx
  it("renders the activity timeline widget", async () => {
    renderPage();
    expect(await screen.findByText("Recent activity")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/routes/Dashboard.test.tsx`
Expected: FAIL — "Recent activity" not found (widget not wired in yet).

- [ ] **Step 3: Wire in the widget and restyle**

In `apps/web/src/routes/Dashboard.tsx`:

1. Add the import: `import { ActivityTimeline } from "../components/ActivityTimeline";`
2. Add `<ActivityTimeline />` as a new child inside the existing
   `<div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">`
   widget grid (alongside the existing `DashboardWidgetCard` entries — any
   position in that grid is fine, it's a CSS grid with no order dependency).
3. Change the hero banner's className from
   `"rounded-2xl bg-gradient-to-br from-accent to-accent-hover p-5 text-white shadow-raised"`
   to `"rounded-ds-lg bg-gradient-brand p-5 text-white shadow-raised"`.
4. Change each of the 4 stat-tile `<Link>` elements' className from
   `"rounded-2xl border border-edge bg-surface p-4 shadow-raised transition-colors duration-fast hover:border-accent"`
   to `"rounded-ds-lg border border-edge bg-surface p-4 shadow-raised transition-colors duration-fast hover:border-accent"`
   (radius token swap only — `rounded-2xl` is 16px, `--radius-lg` is also
   16px, so this is visually identical, just named consistently with the
   sidebar's chrome from sub-project 1).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/routes/Dashboard.test.tsx`
Expected: PASS (all tests, including the new one).

- [ ] **Step 5: Run the full frontend suite and a production build as a regression check**

Run: `cd apps/web && pnpm exec vitest run && pnpm exec vite build`
Expected: all tests pass app-wide; build succeeds. (Not `tsc -b` — see
sub-project 1's plan for the pre-existing, unrelated 106-error finding;
`vite build` is this project's actual working build gate. Similarly,
`pnpm exec eslint .` is confirmed unrunnable here — `eslint` isn't
installed anywhere in this checkout — skip it.)

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/Dashboard.tsx apps/web/src/routes/Dashboard.test.tsx
git commit -m "feat(dashboard): wire in ActivityTimeline, restyle hero/stat tiles with design tokens"
```

---

### Task 4: Final verification

**Files:** none (verification only).

- [ ] **Step 1: Full backend suite on the server**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T api pytest"
```

Expected: no new failures beyond any pre-existing baseline (see Task 1
Step 7's note).

- [ ] **Step 2: Full frontend suite + build, locally**

Run: `cd apps/web && pnpm exec vitest run && pnpm exec vite build`
Expected: 100% pass; build succeeds.

- [ ] **Step 3: Live-browser check**

Same standing convention as sub-project 1 (this project's history has
repeatedly found real bugs that automated checks alone missed — e.g. the
header-clipping bug found live-checking the sidebar). Since this touches
authenticated pages, use the same standalone-preview technique from
sub-project 1's Task 7 if no other logged-in path is available locally
(temporarily override `useAuth` in `apps/web/src/lib/auth.tsx` to return a
fixed fake user, `git checkout` it back immediately after — never commit
that override). Check:
- The Activity Timeline widget renders real items with correct icons,
  titles, links, and relative dates (needs real seeded data — e.g. the
  disposable users/documents/tasks/cases from Task 1's tests, or your own
  account's real data).
- Clicking an activity item's link navigates to the right page for each
  type (document/task/case/entity).
- The hero banner and stat tiles still look correct in both light and dark
  mode — the token swap should be visually identical to before, confirm
  it actually is.
- Empty state (a fresh user with no activity) shows the empty message, not
  a broken/blank widget.

**Do not push to `origin/main` or deploy to the live server as part of
this task** — tell the user it's ready and ask whether to push/deploy,
per this plan's Global Constraints.
