# Deadlines & reminders display polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Tasks page and Dashboard "My tasks" widget the urgency-at-a-glance polish the Codeberg v2 reference has (stats strip, urgency color coding, relative-date phrasing), reusing one shared urgency helper so the logic exists exactly once.

**Architecture:** One new pure-function module (`apps/web/src/lib/taskUrgency.ts`) replaces Tasks.tsx's local `dueBadge()` and becomes the single source of truth for urgency classification; Dashboard.tsx imports the same module rather than re-deriving urgency logic.

**Tech Stack:** React + TypeScript, Vitest + Testing Library, react-i18next, existing Violet Design System primitives (`Badge`, `Card`).

## Global Constraints

- No new dependencies (no animation library) — polish comes from color/layout, per the approved design spec's explicit non-goal.
- All new user-facing copy is added to `en.json`, `nl.json`, `de.json` in the same task that introduces the copy — tests render the real i18next instance, so a missing key breaks the test, not just the UI.
- "Open" for the stats strip means `status !== "done"` (open + in_progress combined), not the narrower `status === "open"` the List view's filter tab uses.
- Dashboard's "My tasks" widget shows the existing short badge labels (overdue/today/date) — never the new `relativeDueLabel` "tomorrow"/"in N days" phrasing, which is Tasks-page-only.
- Every new/changed frontend interaction gets a test in the relevant existing test file (`Tasks.test.tsx`, `Dashboard.test.tsx`), following those files' existing `vi.mock("../lib/api")` pattern. Frontend tests run via `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run'`.
- Full design rationale lives in `docs/superpowers/specs/2026-07-18-deadlines-reminders-polish-design.md` — this plan implements it; consult it only if a step here is ambiguous, don't re-derive decisions already made there.

---

### Task 1: Shared urgency helper module

**Files:**
- Create: `apps/web/src/lib/taskUrgency.ts`
- Test: `apps/web/src/lib/taskUrgency.test.ts`

**Interfaces:**
- Produces: `taskUrgency(dueDate: string): TaskUrgency` where `TaskUrgency = { variant: "danger" | "warning" | "default"; overdueDays: number | null }`; `daysUntil(dueDate: string): number`; `relativeDueLabel(dueDate: string, t: (key: string, opts?: Record<string, unknown>) => string, formatDate: (value: string) => string): string`. Later tasks import all three from this file.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/lib/taskUrgency.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";
import { taskUrgency, daysUntil, relativeDueLabel } from "./taskUrgency";

function isoDate(offsetDays: number): string {
  return new Date(Date.now() + offsetDays * 86400000).toISOString().slice(0, 10);
}

describe("taskUrgency", () => {
  it("returns danger with overdueDays for a past due date", () => {
    expect(taskUrgency(isoDate(-3))).toEqual({ variant: "danger", overdueDays: 3 });
  });

  it("returns warning with null overdueDays for today's due date", () => {
    expect(taskUrgency(isoDate(0))).toEqual({ variant: "warning", overdueDays: null });
  });

  it("returns default with null overdueDays for a future due date", () => {
    expect(taskUrgency(isoDate(5))).toEqual({ variant: "default", overdueDays: null });
  });
});

describe("daysUntil", () => {
  it("returns a positive count for a future date", () => {
    expect(daysUntil(isoDate(4))).toBe(4);
  });

  it("returns 0 for today", () => {
    expect(daysUntil(isoDate(0))).toBe(0);
  });

  it("returns a negative count for a past date", () => {
    expect(daysUntil(isoDate(-2))).toBe(-2);
  });
});

describe("relativeDueLabel", () => {
  const t = vi.fn((key: string, opts?: Record<string, unknown>) => {
    if (key === "tasks.dueOverdue") return `Overdue by ${opts?.count} days`;
    if (key === "tasks.dueToday") return "Due today";
    if (key === "tasks.dueTomorrow") return "Due tomorrow";
    if (key === "tasks.dueInDays") return `Due in ${opts?.count} days`;
    if (key === "tasks.due") return `Due ${opts?.date}`;
    return key;
  });
  const formatDate = (value: string) => value;

  it("labels an overdue date", () => {
    expect(relativeDueLabel(isoDate(-2), t, formatDate)).toBe("Overdue by 2 days");
  });

  it("labels today", () => {
    expect(relativeDueLabel(isoDate(0), t, formatDate)).toBe("Due today");
  });

  it("labels tomorrow distinctly from other near-future days", () => {
    expect(relativeDueLabel(isoDate(1), t, formatDate)).toBe("Due tomorrow");
  });

  it("labels a date within a week as 'in N days'", () => {
    expect(relativeDueLabel(isoDate(5), t, formatDate)).toBe("Due in 5 days");
  });

  it("falls back to the formatted date beyond a week out", () => {
    expect(relativeDueLabel(isoDate(10), t, formatDate)).toBe(`Due ${isoDate(10)}`);
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/lib/taskUrgency.test.ts'`
Expected: FAIL — module `./taskUrgency` does not exist

- [ ] **Step 3: Write the implementation**

Create `apps/web/src/lib/taskUrgency.ts`:

```typescript
export type UrgencyVariant = "danger" | "warning" | "default";

export interface TaskUrgency {
  variant: UrgencyVariant;
  overdueDays: number | null;
}

export function taskUrgency(dueDate: string): TaskUrgency {
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) {
    const days = Math.round((new Date(today).getTime() - new Date(dueDate).getTime()) / 86400000);
    return { variant: "danger", overdueDays: days };
  }
  if (dueDate === today) {
    return { variant: "warning", overdueDays: null };
  }
  return { variant: "default", overdueDays: null };
}

export function daysUntil(dueDate: string): number {
  const today = new Date().toISOString().slice(0, 10);
  return Math.round((new Date(dueDate).getTime() - new Date(today).getTime()) / 86400000);
}

export function relativeDueLabel(
  dueDate: string,
  t: (key: string, opts?: Record<string, unknown>) => string,
  formatDate: (value: string) => string,
): string {
  const urgency = taskUrgency(dueDate);
  if (urgency.variant === "danger") return t("tasks.dueOverdue", { count: urgency.overdueDays });
  if (urgency.variant === "warning") return t("tasks.dueToday");
  const days = daysUntil(dueDate);
  if (days === 1) return t("tasks.dueTomorrow");
  if (days <= 7) return t("tasks.dueInDays", { count: days });
  return t("tasks.due", { date: formatDate(dueDate) });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/lib/taskUrgency.test.ts'`
Expected: PASS, 11/11 tests

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/taskUrgency.ts apps/web/src/lib/taskUrgency.test.ts
git commit -m "feat(tasks): add shared taskUrgency helper module"
```

---

### Task 2: Tasks.tsx uses the shared helper (relative-date phrasing)

**Files:**
- Modify: `apps/web/src/routes/Tasks.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`
- Test: `apps/web/src/routes/Tasks.test.tsx`

**Interfaces:**
- Consumes: `taskUrgency`, `relativeDueLabel` from `../lib/taskUrgency` (Task 1).

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/src/routes/Tasks.test.tsx`, after the existing `"shows a due-today badge for today's due date"` test:

```typescript
  it("shows 'Due tomorrow' for a task due the next day", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(1) }]);
    renderPage();
    expect(await screen.findByText("Due tomorrow")).toBeInTheDocument();
  });

  it("shows 'Due in N days' for a task due within a week", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(4) }]);
    renderPage();
    expect(await screen.findByText("Due in 4 days")).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx -t "Due tomorrow|Due in"'`
Expected: FAIL — current `dueBadge` has no "tomorrow"/"in N days" branch, so both render the far-future formatted-date form instead

- [ ] **Step 3: Add the new locale keys**

`en.json`, immediately after the existing `"dueOverdue_other": "Overdue by {{count}} days"` line (inside the `tasks` section):

```json
    "dueTomorrow": "Due tomorrow",
    "dueInDays_one": "Due in {{count}} day",
    "dueInDays_other": "Due in {{count}} days",
```

`nl.json`, same position in its `tasks` section:

```json
    "dueTomorrow": "Morgen te doen",
    "dueInDays_one": "Over {{count}} dag",
    "dueInDays_other": "Over {{count}} dagen",
```

`de.json`, same position in its `tasks` section:

```json
    "dueTomorrow": "Fällig morgen",
    "dueInDays_one": "Fällig in {{count}} Tag",
    "dueInDays_other": "Fällig in {{count}} Tagen",
```

- [ ] **Step 4: Replace the local `dueBadge` function with the shared helper**

In `apps/web/src/routes/Tasks.tsx`, remove the local `dueBadge` function entirely (the `function dueBadge(...)` block near the top of the file, right after the type declarations). Add the import:

```typescript
import { taskUrgency, relativeDueLabel } from "../lib/taskUrgency";
```

Change the row-rendering call site — currently:

```typescript
            const badge = task.due_date ? dueBadge(task.due_date, t, formatDate) : null;
```

to:

```typescript
            const badge = task.due_date
              ? { variant: taskUrgency(task.due_date).variant, label: relativeDueLabel(task.due_date, t, formatDate) }
              : null;
```

No other lines in the render body change — `badge.variant` and `badge.label` are consumed the same way as before.

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx'`
Expected: PASS, all existing tests plus the 2 new ones (14/14 — the file has 12 tests before this task)

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/Tasks.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json apps/web/src/routes/Tasks.test.tsx
git commit -m "feat(tasks): use shared taskUrgency helper, add relative-date phrasing"
```

---

### Task 3: Tasks.tsx stats strip

**Files:**
- Modify: `apps/web/src/routes/Tasks.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`
- Test: `apps/web/src/routes/Tasks.test.tsx`

**Interfaces:**
- Consumes: `taskUrgency` from `../lib/taskUrgency` (Task 1), `listTasks` from `../lib/api` (existing).
- Produces: a new `allTasks` state, local to this component, used only by the stats strip this task adds. Task 4 (row coloring) does not consume it — Task 4 computes urgency per-row directly from the already-rendered `tasks` array instead.

**Important — this task's mount-time fetch changes two existing tests' assertions.** Adding a second, unconditional `listTasks()` call on mount (for the stats strip) means the component now issues 2 API calls on initial render instead of 1. Two pre-existing tests assert exact call timing/count and must be updated in this same task, or they will fail:

- [ ] **Step 1: Write the failing test for the stats strip**

Add to `apps/web/src/routes/Tasks.test.tsx`, after the `"shows a recurrence marker..."` test:

```typescript
  it("shows open/overdue/due-today counts in the stats strip, independent of the active filter tab", async () => {
    vi.mocked(api.listTasks).mockImplementation((statusFilter?: string) => {
      if (statusFilter === "open") return Promise.resolve([OPEN_TASKS[0]]);
      // unfiltered call (for the stats strip) sees the full mixed set
      return Promise.resolve([
        { ...OPEN_TASKS[0], id: "t1", status: "open", due_date: isoDate(-1) }, // overdue
        { ...OPEN_TASKS[0], id: "t2", status: "open", due_date: isoDate(0) }, // due today
        { ...OPEN_TASKS[0], id: "t3", status: "in_progress", due_date: isoDate(10) }, // open, not urgent
        { ...OPEN_TASKS[0], id: "t4", status: "done", due_date: isoDate(-5) }, // done, excluded
      ]);
    });
    renderPage();
    await screen.findByText("Review lease");
    // wait for the allTasks fetch to resolve and re-render before asserting counts
    await waitFor(() => expect(screen.getByTestId("stat-open-count")).toHaveTextContent("3"));
    expect(screen.getByTestId("stat-overdue-count")).toHaveTextContent("1");
    expect(screen.getByTestId("stat-due-today-count")).toHaveTextContent("1");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx -t "stats strip"'`
Expected: FAIL — no stats strip exists yet

- [ ] **Step 3: Add the new locale keys**

`en.json`, `tasks` section, after the `dueInDays_other` key added in Task 2:

```json
    "statsOpenLabel": "Open",
    "statsOverdueLabel": "Overdue",
    "statsDueTodayLabel": "Due today",
```

`nl.json`:

```json
    "statsOpenLabel": "Open",
    "statsOverdueLabel": "Te laat",
    "statsDueTodayLabel": "Vandaag",
```

`de.json`:

```json
    "statsOpenLabel": "Offen",
    "statsOverdueLabel": "Überfällig",
    "statsDueTodayLabel": "Heute fällig",
```

- [ ] **Step 4: Add the `allTasks` fetch and stats strip**

In `apps/web/src/routes/Tasks.tsx`, add the import (alongside the Task 2 import):

```typescript
import { taskUrgency, relativeDueLabel } from "../lib/taskUrgency";
```

(already present from Task 2 — no change here, just confirming it covers `taskUrgency` which this task also needs).

Add new state, alongside the existing `tasks`/`filter`/`view` state declarations:

```typescript
  const [allTasks, setAllTasks] = useState<TaskOut[]>([]);
```

Add a new, separate `useEffect` (mount-only, empty deps array) — place it directly after the existing `useEffect(() => { refresh(view, filter); }, [view, filter, refresh]);` block:

```typescript
  useEffect(() => {
    listTasks().then(setAllTasks).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
```

Add the stats computation right before the `return (` statement:

```typescript
  const openTasks = allTasks.filter((task) => task.status !== "done");
  const overdueCount = openTasks.filter((task) => task.due_date && taskUrgency(task.due_date).variant === "danger").length;
  const dueTodayCount = openTasks.filter((task) => task.due_date && taskUrgency(task.due_date).variant === "warning").length;
```

Render the stats strip as a new row inside the existing header `div`, right after the closing `</div>` of the current filter/view/new-task-button row and before the `{error && ...}` line:

Note: `Card` (`apps/web/src/components/Card.tsx`) only accepts `children`/`className` — it does not forward arbitrary props like `data-testid` to the underlying DOM element. Put `data-testid` on the inner `<span>` instead, which is a plain element and forwards it normally.

```tsx
      <div className="flex flex-wrap gap-3">
        <Card className="flex flex-col gap-0.5 px-4 py-2.5">
          <span className="text-xs text-ink-3">{t("tasks.statsOpenLabel")}</span>
          <span data-testid="stat-open-count" className="text-lg font-semibold text-ink">{openTasks.length}</span>
        </Card>
        <Card className="flex flex-col gap-0.5 px-4 py-2.5">
          <span className="text-xs text-ink-3">{t("tasks.statsOverdueLabel")}</span>
          <span data-testid="stat-overdue-count" className={`text-lg font-semibold ${overdueCount > 0 ? "text-danger" : "text-ink"}`}>{overdueCount}</span>
        </Card>
        <Card className="flex flex-col gap-0.5 px-4 py-2.5">
          <span className="text-xs text-ink-3">{t("tasks.statsDueTodayLabel")}</span>
          <span data-testid="stat-due-today-count" className={`text-lg font-semibold ${dueTodayCount > 0 ? "text-warning" : "text-ink"}`}>{dueTodayCount}</span>
        </Card>
      </div>
```

- [ ] **Step 5: Fix the two existing tests broken by the new mount-time fetch**

In `apps/web/src/routes/Tasks.test.tsx`, the test `"defaults to the open filter and re-queries when a different tab is clicked"` currently asserts:

```typescript
    expect(api.listTasks).toHaveBeenLastCalledWith("open");
```

Change this line to:

```typescript
    expect(api.listTasks).toHaveBeenCalledWith("open");
```

(`toHaveBeenCalledWith` instead of `toHaveBeenLastCalledWith` — the stats strip's own unconditional `listTasks()` mount call means "open" is no longer necessarily the *last* call after mount, but it must still have been called at some point. The test's second assertion, `toHaveBeenLastCalledWith("done")` after the tab click, needs no change — that fetch happens well after both mount-time calls have already resolved, so it's unambiguously last.)

The test `"opens the new-task form, disables recurrence chips until a due date is set, and submits"` currently asserts:

```typescript
    expect(api.listTasks).toHaveBeenCalledTimes(2);
```

Change this to:

```typescript
    expect(api.listTasks).toHaveBeenCalledTimes(3);
```

(mount now fires 2 calls — the filtered list fetch and the stats strip's unfiltered fetch — and the successful create adds a 3rd.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx'`
Expected: PASS, all tests (15/15)

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/routes/Tasks.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json apps/web/src/routes/Tasks.test.tsx
git commit -m "feat(tasks): add open/overdue/due-today stats strip"
```

---

### Task 4: Tasks.tsx row-level urgency color coding

**Files:**
- Modify: `apps/web/src/routes/Tasks.tsx`
- Test: `apps/web/src/routes/Tasks.test.tsx`

**Interfaces:**
- Consumes: `taskUrgency` from `../lib/taskUrgency` (Task 1, already imported from Task 3).

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/Tasks.test.tsx`, after the stats-strip test added in Task 3:

```typescript
  it("gives an overdue task's row a danger-colored left border", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(-1) }]);
    renderPage();
    const row = (await screen.findByText("Review lease")).closest("[data-testid='task-row']");
    expect(row).toHaveClass("border-l-danger");
  });

  it("gives a task with no due date a transparent left border", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: null }]);
    renderPage();
    const row = (await screen.findByText("Review lease")).closest("[data-testid='task-row']");
    expect(row).toHaveClass("border-l-transparent");
  });

  it("gives a done task a transparent left border even with a past due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([{ ...OPEN_TASKS[0], due_date: isoDate(-1), status: "done" }]);
    renderPage();
    const row = (await screen.findByText("Review lease")).closest("[data-testid='task-row']");
    expect(row).toHaveClass("border-l-transparent");
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx -t "left border"'`
Expected: FAIL — rows have no `data-testid="task-row"` and no border classes yet

- [ ] **Step 3: Add the row border and test id**

In `apps/web/src/routes/Tasks.tsx`, find the row's `<div>`:

```tsx
              <div key={task.id} className="flex items-start gap-3 px-4 py-3">
```

Replace with:

```tsx
              <div
                key={task.id}
                data-testid="task-row"
                className={`flex items-start gap-3 border-l-2 px-4 py-3 ${
                  task.due_date && task.status !== "done"
                    ? { danger: "border-l-danger", warning: "border-l-warning", default: "border-l-transparent" }[taskUrgency(task.due_date).variant]
                    : "border-l-transparent"
                }`}
              >
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx'`
Expected: PASS, all tests (18/18)

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/Tasks.tsx apps/web/src/routes/Tasks.test.tsx
git commit -m "feat(tasks): color-code each row's left border by urgency"
```

---

### Task 5: Dashboard "My tasks" widget shows due-date badges

**Files:**
- Modify: `apps/web/src/routes/Dashboard.tsx`
- Test: `apps/web/src/routes/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `taskUrgency` from `../lib/taskUrgency` (Task 1), `useDateFormat` from `../hooks/useDateFormat` (existing, not currently imported in Dashboard.tsx).

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/src/routes/Dashboard.test.tsx`, after the existing `"shows open tasks"` test:

```typescript
  it("shows an overdue badge next to a task with a past due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      { id: "t1", document_id: null, title: "Review lease", description: null, due_date: "2020-01-01", assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(screen.getByText(/Overdue by/)).toBeInTheDocument();
  });

  it("shows a formatted-date badge next to a task with a far-future due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      { id: "t1", document_id: null, title: "Review lease", description: null, due_date: "2099-06-15", assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(screen.getByText("Due 15/06/2099")).toBeInTheDocument();
  });

  it("shows no badge next to a task with no due date", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      { id: "t1", document_id: null, title: "Review lease", description: null, due_date: null, assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(screen.queryByText(/Due|Overdue/)).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Dashboard.test.tsx -t "badge"'`
Expected: FAIL — the widget currently renders bare `<li>{task.title}</li>`, no badge

- [ ] **Step 3: Add the badge to the widget**

In `apps/web/src/routes/Dashboard.tsx`, add the import:

```typescript
import { useDateFormat } from "../hooks/useDateFormat";
import { taskUrgency } from "../lib/taskUrgency";
```

Inside the `Dashboard` component function, add near the top (alongside the existing `const { t } = useTranslation();` / `const { user } = useAuth();` lines):

```typescript
  const { formatDate } = useDateFormat();
```

Replace the "My tasks" widget's list body — currently:

```tsx
          <ul className="flex flex-col gap-2">
            {recentTasks.map((task) => (
              <li key={task.id} className="text-sm text-ink">
                {task.title}
              </li>
            ))}
          </ul>
```

with:

```tsx
          <ul className="flex flex-col gap-2">
            {recentTasks.map((task) => (
              <li key={task.id} className="flex items-center justify-between gap-2 text-sm">
                <span className="text-ink">{task.title}</span>
                {task.due_date && (
                  <Badge variant={taskUrgency(task.due_date).variant}>
                    {taskUrgency(task.due_date).variant === "danger"
                      ? t("tasks.dueOverdue", { count: taskUrgency(task.due_date).overdueDays })
                      : taskUrgency(task.due_date).variant === "warning"
                        ? t("tasks.dueToday")
                        : t("tasks.due", { date: formatDate(task.due_date) })}
                  </Badge>
                )}
              </li>
            ))}
          </ul>
```

(`Badge` is already imported in this file for the system-status widget — no new import needed for it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Dashboard.test.tsx'`
Expected: PASS, all tests (16/16 — the file has 13 tests before this task, across both its `describe` blocks)

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/Dashboard.tsx apps/web/src/routes/Dashboard.test.tsx
git commit -m "feat(dashboard): show due-date badge on each My-tasks item"
```

---

### Task 6: Dashboard "My tasks" widget overdue-count header indicator

**Files:**
- Modify: `apps/web/src/routes/Dashboard.tsx`
- Modify: `apps/web/src/locales/en.json`, `nl.json`, `de.json`
- Test: `apps/web/src/routes/Dashboard.test.tsx`

**Interfaces:**
- Consumes: `taskUrgency` from `../lib/taskUrgency` (Task 1, already imported from Task 5).

- [ ] **Step 1: Write the failing tests**

Add to `apps/web/src/routes/Dashboard.test.tsx`, after the tests added in Task 5:

```typescript
  it("shows an overdue indicator in the My-tasks widget header when a loaded task is overdue", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      { id: "t1", document_id: null, title: "Review lease", description: null, due_date: "2020-01-01", assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(screen.getByTestId("my-tasks-overdue-indicator")).toHaveTextContent("Overdue");
  });

  it("hides the overdue indicator when no loaded task is overdue", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      { id: "t1", document_id: null, title: "Review lease", description: null, due_date: "2099-06-15", assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(screen.queryByTestId("my-tasks-overdue-indicator")).not.toBeInTheDocument();
  });
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Dashboard.test.tsx -t "overdue indicator"'`
Expected: FAIL — no such indicator exists yet

- [ ] **Step 3: Add the new locale key**

`en.json`, `dashboard` section, immediately after `"myTasksEmpty": "No open tasks."`:

```json
    "myTasksOverdue": "Overdue",
```

`nl.json`, `dashboard` section:

```json
    "myTasksOverdue": "Te laat",
```

`de.json`, `dashboard` section:

```json
    "myTasksOverdue": "Überfällig",
```

- [ ] **Step 4: Add the indicator to the widget header**

In `apps/web/src/routes/Dashboard.tsx`, the "My tasks" `DashboardWidgetCard`'s `actions` prop is currently:

```tsx
          actions={
            <Link to="/tasks" className="text-xs text-accent hover:underline">
              {t("dashboard.viewAll")}
            </Link>
          }
```

Replace with:

```tsx
          actions={
            <>
              {recentTasks.some((task) => task.due_date && taskUrgency(task.due_date).variant === "danger") && (
                <Badge variant="danger" data-testid="my-tasks-overdue-indicator">
                  {t("dashboard.myTasksOverdue")}
                </Badge>
              )}
              <Link to="/tasks" className="text-xs text-accent hover:underline">
                {t("dashboard.viewAll")}
              </Link>
            </>
          }
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run src/routes/Dashboard.test.tsx'`
Expected: PASS, all tests (18/18)

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/Dashboard.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json apps/web/src/routes/Dashboard.test.tsx
git commit -m "feat(dashboard): overdue indicator on the My-tasks widget header"
```

---

### Task 7: Full verification and deploy

**Files:** none (verification only)

- [ ] **Step 1: Full frontend suite + typecheck**

Run: `docker compose exec web sh -c 'cd /app/apps/web && pnpm exec vitest run'`
Expected: all pass, count higher than the pre-change baseline by the 22 new tests this plan adds (11 in `taskUrgency.test.ts` + 2 in Task 2 + 1 in Task 3 + 3 in Task 4 + 3 in Task 5 + 2 in Task 6).

Run: `docker compose exec web sh -c 'cd /app/apps/web && npx tsc --noEmit'`
Expected: no new errors beyond the pre-existing jest-dom-matcher-type-declaration errors already present project-wide (confirmed harmless in this session's earlier work — every `.test.tsx` file shows these, including files this plan never touches).

- [ ] **Step 2: Deploy**

```bash
docker compose exec web sh -c 'cd /app/apps/web && npx vite build'
```

Confirm the container is healthy: `docker compose ps web --format '{{.Service}} {{.Status}}'`

- [ ] **Step 3: Live browser verification**

1. Navigate to `/tasks`. Confirm the stats strip renders three tiles (Open/Overdue/Due today) with real counts matching the live task data.
2. Confirm at least one row (if any task is overdue or due today) shows a colored left border matching its badge variant.
3. Create a test task due tomorrow; confirm its badge reads "Due tomorrow" not a formatted date.
4. Navigate to `/` (Dashboard). Confirm the "My tasks" widget shows a due-date badge per task.
5. If any loaded task is overdue, confirm the widget header shows the "Overdue" indicator next to "View all".
6. Check the browser console for errors throughout (`read_console_messages`, `onlyErrors: true`).

- [ ] **Step 4: Commit and push**

```bash
git push origin main
```
