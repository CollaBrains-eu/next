# Phase 17b — Case Workspace UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Phase 16 Case Workspace backend (Case CRUD, document/task/decision linking, dashboard endpoint) a real UI: a case list, case creation, and a detail dashboard with attach flows for documents, tasks, and decisions.

**Architecture:** One small backend addition (`GET /decisions`, needed because no list endpoint exists yet for the Decisions attach-picker) plus two new frontend pages (`Cases.tsx`, `CaseDetail.tsx`) built on Phase 17a's `Layout`/`Sidebar`/`Card`/`EmptyState` shell.

**Tech Stack:** FastAPI/SQLAlchemy (backend addition), React + TypeScript + Vite + Tailwind (frontend, existing stack, no new dependencies).

## Global Constraints

- Backend: no new migration needed — `GET /decisions` is a pure read query against the existing `decisions` table.
- Frontend: no new npm dependencies; reuse `UploadDialog.tsx`'s inline-toggle pattern for "New case" and each attach control, not a new modal/dialog primitive.
- This sub-phase depends on Phase 17a having merged (`Layout`, `Sidebar`, `Card`, `EmptyState` must already exist in `main`).
- No new frontend test pattern — this codebase has no React component testing library; verification is `tsc -b` typecheck plus a final live browser check (matching 17a and Phases 5a-5c).

---

### Task 1: Backend — `GET /decisions` list endpoint

**Files:**
- Modify: `services/api/src/api/decisions.py`
- Test: `services/api/tests/test_decisions.py`

**Interfaces:**
- Produces: `GET /decisions` → `list[DecisionListItemOut]` where `DecisionListItemOut = { id: UUID, summary: str }`. Scoped to the caller's own decisions (`Decision.user_id == current_user.id`), admin sees all — same ownership pattern as the existing `GET /decisions/{id}`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_decisions.py` (after the existing `test_get_decision_returns_supporting_documents` test, before `test_get_decision_rejects_non_owner`):

```python
async def test_list_decisions_scoped_to_user(client):
    owner_token, owner_username = await _login(client, "decisionlistuser")
    owner_id = await _user_id_for(owner_username)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=owner_id, goal_type="draft_legal_document", goal_params={"instruction": "Draft a notice."},
        )
        decision = await create_decision_from_plan(db, plan=plan, user_id=owner_id)

    other_token, other_username = await _login(client, "decisionlistother")
    other_id = await _user_id_for(other_username)
    async with async_session() as db:
        other_plan = await create_plan(
            db, user_id=other_id, goal_type="draft_legal_document",
            goal_params={"instruction": "Draft another notice."},
        )
        await create_decision_from_plan(db, plan=other_plan, user_id=other_id)

    response = await client.get("/decisions", headers={"Authorization": f"Bearer {owner_token}"})
    assert response.status_code == 200
    ids = [d["id"] for d in response.json()]
    assert ids == [str(decision.id)]


async def test_list_decisions_rejects_missing_token(client):
    response = await client.get("/decisions")
    assert response.status_code == 401
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_decisions.py -v -k list_decisions`

Expected: FAIL with 404 (no `/decisions` list route registered yet — only `/decisions/{decision_id}` exists, and `list_decisions` currently isn't a valid `decision_id`... actually the request `GET /decisions` with no ID will 404 against the path-param route, since `/decisions` alone doesn't match `/decisions/{decision_id}`'s pattern).

- [ ] **Step 3: Add the endpoint to `services/api/src/api/decisions.py`**

Add `select` to the sqlalchemy import and `Decision` to the models import:

```python
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
```

```python
from api.models import Decision, User
```

Add this new response model and endpoint, placed before `get_decision` (list before detail):

```python
class DecisionListItemOut(BaseModel):
    id: UUID
    summary: str


@router.get("/decisions", response_model=list[DecisionListItemOut])
async def list_decisions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Decision]:
    query = select(Decision).order_by(Decision.created_at.desc())
    if current_user.role != "admin":
        query = query.where(Decision.user_id == current_user.id)
    result = await db.execute(query)
    return list(result.scalars().all())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest tests/test_decisions.py -v`

Expected: all 6 tests pass (4 existing + 2 new).

- [ ] **Step 5: Ruff check**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/api/decisions.py tests/test_decisions.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
cd /opt/collabrains
git add services/api/src/api/decisions.py services/api/tests/test_decisions.py
git commit -m "Phase 17b task 1: GET /decisions list endpoint"
```

---

### Task 2: `api.ts` additions for Cases

**Files:**
- Modify: `apps/web/src/lib/api.ts`

**Interfaces:**
- Produces: `CaseOut`, `CaseDashboardOut`, `DecisionListItemOut` interfaces; `listCases`, `createCase`, `getCase`, `updateCaseStatus`, `listDecisions`, `attachDocumentToCase`, `linkTaskToCase`, `linkDecisionToCase` functions. Consumed by `Cases.tsx`/`CaseDetail.tsx` in Tasks 3-4.

- [ ] **Step 1: Append to `apps/web/src/lib/api.ts`**

Add at the end of the file:

```ts
export interface CaseOut {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
}

export interface CaseDashboardOut extends CaseOut {
  documents: { id: string; title: string }[];
  tasks: { id: string; title: string; status: string }[];
  decisions: { id: string; summary: string }[];
}

export interface DecisionListItemOut {
  id: string;
  summary: string;
}

export function listCases(): Promise<CaseOut[]> {
  return request<CaseOut[]>("/cases");
}

export function createCase(name: string, description?: string): Promise<CaseOut> {
  return request<CaseOut>("/cases", {
    method: "POST",
    body: JSON.stringify({ name, description: description || null }),
  });
}

export function getCase(id: string): Promise<CaseDashboardOut> {
  return request<CaseDashboardOut>(`/cases/${id}`);
}

export function updateCaseStatus(id: string, status: "open" | "closed"): Promise<CaseOut> {
  return request<CaseOut>(`/cases/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function listDecisions(): Promise<DecisionListItemOut[]> {
  return request<DecisionListItemOut[]>("/decisions");
}

export function attachDocumentToCase(documentId: string, caseId: string | null): Promise<{ id: string; title: string }> {
  return request<{ id: string; title: string }>(`/documents/${documentId}/case`, {
    method: "PUT",
    body: JSON.stringify({ case_id: caseId }),
  });
}

export function linkTaskToCase(caseId: string, taskId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/tasks/${taskId}`, { method: "POST" });
}

export function linkDecisionToCase(caseId: string, decisionId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/decisions/${decisionId}`, { method: "POST" });
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 3: Run the existing frontend test suite**

Run: `cd /opt/collabrains && docker compose exec web pnpm test`
Expected: `5 passed` (this task only adds new exports to `api.ts`, doesn't touch `request()` or anything the existing tests cover).

- [ ] **Step 4: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/lib/api.ts
git commit -m "Phase 17b task 2: api.ts additions for Cases"
```

---

### Task 3: `Cases.tsx` (list + create)

**Files:**
- Create: `apps/web/src/routes/Cases.tsx`

**Interfaces:**
- Consumes: `listCases`, `createCase`, `CaseOut` (Task 2); `Card`, `EmptyState` (Phase 17a).
- Produces: `export default function Cases()`, wired into routing in Task 5.

- [ ] **Step 1: Write `Cases.tsx`**

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { ApiError, createCase, listCases, type CaseOut } from "../lib/api";

export default function Cases() {
  const [cases, setCases] = useState<CaseOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [submitting, setSubmitting] = useState(false);

  function refresh() {
    setLoading(true);
    listCases()
      .then(setCases)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load cases"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim() || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await createCase(name.trim(), description.trim() || undefined);
      setName("");
      setDescription("");
      setCreating(false);
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create case");
    } finally {
      setSubmitting(false);
    }
  }

  const newCaseButton = !creating && (
    <button
      onClick={() => setCreating(true)}
      className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700"
    >
      New case
    </button>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Cases</h1>
        {cases.length > 0 && newCaseButton}
      </div>

      {creating && (
        <Card>
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium">New case</span>
              <button
                type="button"
                onClick={() => setCreating(false)}
                className="text-sm text-slate-500 hover:text-slate-900"
              >
                Cancel
              </button>
            </div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Case name"
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
              className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
            />
            <button
              type="submit"
              disabled={submitting || !name.trim()}
              className="self-start rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
            >
              Create
            </button>
          </form>
        </Card>
      )}

      {error && <p className="text-sm text-red-600">{error}</p>}

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : cases.length === 0 && !creating ? (
        <EmptyState message="No cases yet." action={newCaseButton} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cases.map((c) => (
            <Link key={c.id} to={`/cases/${c.id}`}>
              <Card className="flex h-full flex-col gap-2 hover:border-slate-400">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{c.name}</span>
                  <span
                    className={`rounded px-2 py-0.5 text-xs ${
                      c.status === "open" ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-600"
                    }`}
                  >
                    {c.status}
                  </span>
                </div>
                {c.description && <p className="text-sm text-slate-500">{c.description}</p>}
                <span className="mt-auto text-xs text-slate-400">
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/routes/Cases.tsx
git commit -m "Phase 17b task 3: Cases list + create page"
```

---

### Task 4: `CaseDetail.tsx` (dashboard + attach flows)

**Files:**
- Create: `apps/web/src/routes/CaseDetail.tsx`

**Interfaces:**
- Consumes: `getCase`, `updateCaseStatus`, `listDocuments`, `listTasks`, `listDecisions`, `attachDocumentToCase`, `linkTaskToCase`, `linkDecisionToCase`, `CaseDashboardOut` (Task 2, plus existing `listDocuments`/`listTasks` from `api.ts`); `Card` (Phase 17a).
- Produces: `export default function CaseDetail()`, wired into routing in Task 5.

- [ ] **Step 1: Write `CaseDetail.tsx`**

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Card from "../components/Card";
import {
  ApiError,
  attachDocumentToCase,
  getCase,
  linkDecisionToCase,
  linkTaskToCase,
  listDecisions,
  listDocuments,
  listTasks,
  updateCaseStatus,
  type CaseDashboardOut,
  type DecisionListItemOut,
  type DocumentOut,
  type TaskOut,
} from "../lib/api";

type AttachSection = "documents" | "tasks" | "decisions";

export default function CaseDetail() {
  const { id } = useParams<{ id: string }>();
  const [caseData, setCaseData] = useState<CaseDashboardOut | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [attaching, setAttaching] = useState<AttachSection | null>(null);
  const [selected, setSelected] = useState("");
  const [allDocuments, setAllDocuments] = useState<DocumentOut[]>([]);
  const [allTasks, setAllTasks] = useState<TaskOut[]>([]);
  const [allDecisions, setAllDecisions] = useState<DecisionListItemOut[]>([]);

  function refresh() {
    if (!id) return;
    setLoading(true);
    getCase(id)
      .then(setCaseData)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load case"))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    refresh();
    listDocuments().then(setAllDocuments).catch(() => undefined);
    listTasks().then(setAllTasks).catch(() => undefined);
    listDecisions().then(setAllDecisions).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  async function toggleStatus() {
    if (!caseData) return;
    try {
      await updateCaseStatus(caseData.id, caseData.status === "open" ? "closed" : "open");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update case");
    }
  }

  async function handleAttach() {
    if (!caseData || !selected) return;
    try {
      if (attaching === "documents") await attachDocumentToCase(selected, caseData.id);
      if (attaching === "tasks") await linkTaskToCase(caseData.id, selected);
      if (attaching === "decisions") await linkDecisionToCase(caseData.id, selected);
      setAttaching(null);
      setSelected("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to attach item");
    }
  }

  if (loading) return <p className="text-slate-500">Loading…</p>;
  if (error && !caseData) return <p className="text-sm text-red-600">{error}</p>;
  if (!caseData) return null;

  const linkedDocumentIds = new Set(caseData.documents.map((d) => d.id));
  const linkedTaskIds = new Set(caseData.tasks.map((t) => t.id));
  const linkedDecisionIds = new Set(caseData.decisions.map((d) => d.id));

  const attachOptions: Record<AttachSection, { id: string; label: string }[]> = {
    documents: allDocuments.filter((d) => !linkedDocumentIds.has(d.id)).map((d) => ({ id: d.id, label: d.title })),
    tasks: allTasks.filter((t) => !linkedTaskIds.has(t.id)).map((t) => ({ id: t.id, label: t.title })),
    decisions: allDecisions.filter((d) => !linkedDecisionIds.has(d.id)).map((d) => ({ id: d.id, label: d.summary })),
  };

  function AttachControl({ section }: { section: AttachSection }) {
    if (attaching !== section) {
      return (
        <button
          onClick={() => {
            setAttaching(section);
            setSelected("");
          }}
          className="text-xs text-slate-500 hover:text-slate-900"
        >
          + Attach
        </button>
      );
    }
    const options = attachOptions[section];
    return (
      <div className="flex items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded border border-slate-300 px-2 py-1 text-xs"
        >
          <option value="">Select…</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        <button onClick={handleAttach} disabled={!selected} className="text-xs text-slate-900 disabled:opacity-50">
          Attach
        </button>
        <button onClick={() => setAttaching(null)} className="text-xs text-slate-500 hover:text-slate-900">
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{caseData.name}</h1>
          {caseData.description && <p className="mt-1 text-sm text-slate-500">{caseData.description}</p>}
        </div>
        <button
          onClick={toggleStatus}
          className={`rounded px-3 py-1 text-xs ${
            caseData.status === "open" ? "bg-green-100 text-green-800" : "bg-slate-100 text-slate-600"
          }`}
        >
          {caseData.status}
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Documents</span>
          <AttachControl section="documents" />
        </div>
        {caseData.documents.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.documents.map((d) => (
              <li key={d.id}>
                <Link to={`/documents/${d.id}`} className="text-sm hover:underline">
                  {d.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Tasks</span>
          <AttachControl section="tasks" />
        </div>
        {caseData.tasks.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.tasks.map((t) => (
              <li key={t.id} className="text-sm">
                {t.title} <span className="text-xs text-slate-400">({t.status})</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Decisions</span>
          <AttachControl section="decisions" />
        </div>
        {caseData.decisions.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.decisions.map((d) => (
              <li key={d.id} className="text-sm">
                {d.summary}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/routes/CaseDetail.tsx
git commit -m "Phase 17b task 4: CaseDetail dashboard with attach flows"
```

---

### Task 5: Wire into Sidebar and routing

**Files:**
- Modify: `apps/web/src/components/Sidebar.tsx`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: `Cases`, `CaseDetail` (Tasks 3-4).

- [ ] **Step 1: Add the "Cases" nav item to `Sidebar.tsx`**

In `apps/web/src/components/Sidebar.tsx`, change the `NAV_ITEMS` array:

```ts
const NAV_ITEMS = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
  { to: "/cases", label: "Cases" },
];
```

- [ ] **Step 2: Add routes to `App.tsx`**

In `apps/web/src/App.tsx`, add the imports (after the `EntityGraph` import):

```tsx
import EntityGraph from "./routes/EntityGraph";
import Cases from "./routes/Cases";
import CaseDetail from "./routes/CaseDetail";
```

Add the routes (after the `/entities/:id` route, before the `*` catch-all):

```tsx
            <Route
              path="/cases"
              element={
                <ProtectedRoute>
                  <Cases />
                </ProtectedRoute>
              }
            />
            <Route
              path="/cases/:id"
              element={
                <ProtectedRoute>
                  <CaseDetail />
                </ProtectedRoute>
              }
            />
```

- [ ] **Step 3: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 4: Run the existing frontend test suite**

Run: `cd /opt/collabrains && docker compose exec web pnpm test`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/components/Sidebar.tsx apps/web/src/App.tsx
git commit -m "Phase 17b task 5: wire Cases into sidebar and routing"
```

---

### Task 6: ADR, rebuild, live verification, PR

**Files:**
- Create: `docs/adr/0033-phase17b-case-workspace-ui.md`

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0033-phase17b-case-workspace-ui.md`, same Status/Context/Decision/Consequences style as `docs/adr/0025-phase10-knowledge-graph-2.md`. Cover: the `GET /decisions` list-endpoint addition and why (no existing list endpoint, needed to make all three attach-pickers symmetric); the attach-flow UI design (inline `<select>` + Attach button per section, filtered to not-yet-linked items, reusing `UploadDialog.tsx`'s inline-toggle convention rather than a new dialog primitive); that this sub-phase adds exactly one nav item (Cases) to the sidebar Phase 17a built.

- [ ] **Step 2: Run the full backend test suite**

Run: `cd /opt/collabrains/services/api && DATABASE_URL='postgresql+asyncpg://collabrains:7cb6c2123a68b3ebfe91ead6f0e1e5ca@localhost:5432/collabrains' REDIS_URL='redis://localhost:6379/0' OLLAMA_URL='http://localhost:11434' LDAP_URL='ldap://localhost:389' .venv/bin/pytest -q 2>&1 | tail -10`
Expected: 224 passed (222 prior + 2 new), same 6 pre-existing unrelated failures.

- [ ] **Step 3: Ruff check the whole backend**

Run: `cd /opt/collabrains/services/api && ~/.local/bin/uvx ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 4: Rebuild the production frontend bundle**

Run: `cd /opt/collabrains && docker compose exec -e VITE_API_URL='' web pnpm build`
Expected: builds successfully with no errors.

- [ ] **Step 5: Live verification**

Use the Playwright MCP against `https://v78281.1blu.de`: log in, click "Cases" in the sidebar, create a new case, confirm it appears in the grid, open it, attach a real existing document/task/decision to it via each section's Attach control, confirm each appears in its section afterward, and toggle the open/closed status button.

- [ ] **Step 6: Commit the ADR, push, open the draft PR**

```bash
cd /opt/collabrains
git add docs/adr/0033-phase17b-case-workspace-ui.md
git commit -m "Phase 17b: Case Workspace UI"
git push -u origin phase-17b-case-workspace-ui
gh pr create --draft --base main --head phase-17b-case-workspace-ui \
  --title "Phase 17b: Case Workspace UI" \
  --body "See docs/superpowers/specs/2026-07-04-frontend-catchup-design.md for the full Phase 17 design and docs/adr/0033-phase17b-case-workspace-ui.md for this sub-phase's decisions. Adds GET /decisions, Cases list+create page, CaseDetail dashboard with attach flows for documents/tasks/decisions, wired into the Phase 17a sidebar shell."
```

## Self-Review Notes

**Spec coverage**: covers every item in the spec's "Architecture: Case Workspace UI (17b)" section — the `api.ts` additions, the `GET /decisions` backend addition, `Cases.tsx`, and `CaseDetail.tsx` with attach flows for all three link types.

**Placeholder scan**: no TBD/TODO; every step has complete code or an exact command.

**Type consistency**: `CaseDashboardOut`'s `documents`/`tasks`/`decisions` array shapes (Task 2) match exactly what `CaseDetail.tsx` (Task 4) destructures (`d.id`/`d.title`, `t.id`/`t.title`/`t.status`, `d.id`/`d.summary`). `attachDocumentToCase`/`linkTaskToCase`/`linkDecisionToCase`'s parameter order and names match how `CaseDetail.tsx`'s `handleAttach` calls them.
