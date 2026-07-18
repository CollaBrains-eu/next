# Deadlines & reminders display polish — Design

## Status

Approved (brainstormed 2026-07-18)

## Context

A feature-parity check against the reference Codeberg v2 implementation
found the current Tasks page and Dashboard "My tasks" widget visually and
functionally thinner than v2's equivalent, despite the backend already
having full due-date/recurrence support (ADR 0064).

**Current state, confirmed by reading the live code:**

- `apps/web/src/routes/Tasks.tsx` renders a plain `divide-y` list. Each row
  has a checkbox, title (strikethrough when done), an inline recurrence
  marker (`↻ {cadence}`, plain text, no pill), description, and a due-date
  `Badge` computed by a local `dueBadge()` function (danger/warning/default
  variants for overdue/today/upcoming). No stats summary, no urgency color
  coding on the row itself, no relative-date phrasing ("tomorrow", "in 3
  days") — only "Overdue by N days", "Due today", or the fully formatted
  date.
- `apps/web/src/routes/Dashboard.tsx`'s "My tasks" `DashboardWidgetCard`
  lists the first 5 open tasks as bare `<li>{task.title}</li>` — no due
  date, no badge, no urgency signal at all, even though `TaskOut.due_date`
  and the exact same badge logic already exist one file away in Tasks.tsx.
- v2's `ActionItemsPage.tsx` (`~/Downloads/cbrains-v2/frontend/src/pages/`)
  has a 4-tile stats strip (open/overdue/urgent/total-€), urgency-colored
  card borders, and relative-date phrasing. Its `HomePage.tsx` has a
  dedicated "Urgente acties" card surfacing upcoming deadlines on the
  dashboard itself.
- `docs/design/violet-design-language.html`'s `#sec-deadlines-and-reminders`
  mockup additionally has a live-ticking countdown hero card — flagged in
  its own changelog as unaudited/aspirational, not itself production code.

Full investigation detail (exact file/line references for all of the
above) is in this session's transcript; not repeated here since the spec
only needs the resulting decisions.

## Goals

1. Tasks page: a stats strip (open / overdue / due-today counts) and
   per-row urgency color coding, so the page communicates urgency at a
   glance the way v2's does.
2. Tasks page: relative-date phrasing ("tomorrow", "in N days") alongside
   the existing overdue/today/formatted-date badge text.
3. Dashboard "My tasks" widget: show each task's due-date badge (currently
   shows none), plus a small overdue-count indicator in the widget header.
4. Zero duplicated urgency logic between Tasks.tsx and Dashboard.tsx — one
   shared helper, used by both.

## Non-goals

- v2's swipe-undo toast and bottom-sheet detail drawer — this app's
  existing `Modal`/inline-error patterns already cover edit/delete
  interactions adequately; porting v2's specific interaction chrome is a
  separate, much larger UI-pattern change not justified by this pass.
- v2's 4th stats tile (€-total) — that's v2's expense-tracking concept
  layered onto action items; no equivalent exists in this product.
- The Violet mockup's live-ticking countdown hero card — it's explicitly
  unaudited in its own source, and a stats strip + row coloring achieves
  the same "feels urgent" outcome without a per-second re-render.
- Framer-motion/animation — this app doesn't currently depend on an
  animation library anywhere; introducing one for this pass alone is out
  of scope. Color and layout carry the polish instead.
- Fixing the pre-existing quirk where a *done* task with a past due date
  still renders an "Overdue by N days" badge — unrelated to this pass,
  not touched.

## Design

### `apps/web/src/lib/taskUrgency.ts` (new file)

Single source of truth for urgency classification, extracted from
Tasks.tsx's current local `dueBadge()`:

```typescript
export type UrgencyVariant = "danger" | "warning" | "default";

export interface TaskUrgency {
  variant: UrgencyVariant;
  overdueDays: number | null; // set only when variant === "danger"
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
```

`daysUntil` is new (not in the current `dueBadge`) — it powers the
relative-date phrasing for upcoming (non-overdue, non-today) due dates.

### Relative-date label

New helper, same file, used only by Tasks.tsx (Dashboard's compact widget
keeps the existing overdue/today/badge-only treatment — a "tomorrow"/"in 3
days" phrase is verbose for a 5-item sidebar list):

```typescript
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

### Tasks.tsx changes

- Delete the local `dueBadge()` function; import `taskUrgency` and
  `relativeDueLabel` from `../lib/taskUrgency`. The existing badge render
  call `dueBadge(task.due_date, t, formatDate)` becomes:
  `{ variant: taskUrgency(task.due_date).variant, label: relativeDueLabel(task.due_date, t, formatDate) }`.
- New stats strip, rendered above the filter/view controls (inside the
  existing header `div`, as a second row) when the list view is active
  (board view already shows status visually via its columns, so the strip
  is list-view-only, matching where the per-row badges also live):
  a dedicated `useEffect` fetches `listTasks()` (no filter, independent of
  the page's own `filter`/`view` state) once on mount into a new
  `allTasks` state, so counts are always correct regardless of which tab
  the user has selected — same "separate targeted fetch per need" pattern
  Dashboard.tsx already uses for its own widgets.
  ```typescript
  const openTasks = allTasks.filter((t) => t.status !== "done");
  const overdueCount = openTasks.filter((t) => t.due_date && taskUrgency(t.due_date).variant === "danger").length;
  const dueTodayCount = openTasks.filter((t) => t.due_date && taskUrgency(t.due_date).variant === "warning").length;
  ```
  Three small stat tiles (reusing the existing `Card` component at a
  smaller scale, `flex gap-3` row): Open (`openTasks.length`), Overdue
  (`overdueCount`, only rendered with `danger` emphasis if > 0), Due today
  (`dueTodayCount`, `warning` emphasis if > 0).
- Row-level urgency color coding: each row `div` gets a left border keyed
  to the task's urgency variant, added alongside the existing classes:
  `border-l-2 ${task.due_date && task.status !== "done" ? { danger: "border-l-danger", warning: "border-l-warning", default: "border-l-transparent" }[taskUrgency(task.due_date).variant] : "border-l-transparent"}`.
  Done tasks and tasks with no due date get `border-l-transparent` (no
  color), keeping the existing "no due date, no badge" behavior consistent
  for the border too.

### Dashboard.tsx changes

- "My tasks" widget's `<li>` gains the due-date badge, reusing
  `taskUrgency` + the *existing* short-form labels (not `relativeDueLabel`,
  which is Tasks-page-only per the non-goal above — the widget shows the
  same overdue/today/date `Badge` Tasks.tsx already renders, just without
  the "tomorrow"/"in N days" phrasing):
  ```tsx
  <li key={task.id} className="flex items-center justify-between gap-2 text-sm">
    <span className="text-ink">{task.title}</span>
    {task.due_date && (
      <Badge variant={taskUrgency(task.due_date).variant}>
        {taskUrgency(task.due_date).variant === "danger"
          ? t("tasks.dueOverdue", { count: taskUrgency(task.due_date).overdueDays })
          : taskUrgency(task.due_date).variant === "warning"
            ? t("tasks.dueToday")
            : formatDate(task.due_date)}
      </Badge>
    )}
  </li>
  ```
  (`formatDate` from `useDateFormat`, already available via the same hook
  Tasks.tsx uses — Dashboard.tsx does not currently import it, so this adds
  one new import.)
- Widget header gets an overdue-count indicator: the existing `actions`
  prop (currently just the "View all" `Link`) becomes a fragment with a
  small danger `Badge` prepended when any of the loaded tasks are overdue:
  ```tsx
  actions={
    <>
      {recentTasks.some((t) => t.due_date && taskUrgency(t.due_date).variant === "danger") && (
        <Badge variant="danger">{t("dashboard.myTasksOverdue")}</Badge>
      )}
      <Link to="/tasks" className="text-xs text-accent hover:underline">{t("dashboard.viewAll")}</Link>
    </>
  }
  ```
  This reads from `recentTasks` (the existing `tasks.slice(0, 5)`, already
  fetched via `listTasks("open")`) — no new fetch needed for the Dashboard
  widget, unlike Tasks.tsx's stats strip which needs the full unfiltered
  set.

### New locale keys

`en.json`, after the existing `tasks.dueOverdue_other` key:

```json
"dueTomorrow": "Due tomorrow",
"dueInDays_one": "Due in {{count}} day",
"dueInDays_other": "Due in {{count}} days",
"statsOpenLabel": "Open",
"statsOverdueLabel": "Overdue",
"statsDueTodayLabel": "Due today"
```

`dashboard.json` section, after `myTasksEmpty`:

```json
"myTasksOverdue": "Overdue"
```

`nl.json`/`de.json` get the same keys with translated values, following
this file's existing tone (matches the neighboring `dueOverdue`/`dueToday`
translations already present in both).

## Testing

- `taskUrgency`/`daysUntil`/`relativeDueLabel` get direct unit tests in a
  new `apps/web/src/lib/taskUrgency.test.ts` — pure functions, no
  component rendering needed, following the existing pattern of
  `apps/web/src/lib/dateFormat.test.ts`.
- `Tasks.test.tsx` (existing file) gains: stats-strip renders correct
  counts given a mix of overdue/today/upcoming/done tasks; row border
  class reflects urgency; relative-date phrasing renders "tomorrow"/"in N
  days" for the appropriate due dates.
- `Dashboard.test.tsx` (existing file) gains: "My tasks" widget renders a
  badge per task with a due date; overdue indicator appears in the widget
  header only when at least one loaded task is overdue, absent otherwise.
- Full suite (`pnpm vitest run`) green, then a live-browser pass on
  `/tasks` and `/` (Dashboard) against real due-date data (today's already
  -cleaned dev DB has real tasks from the 3 genuine pilot users — no new
  disposable test data needed for this visual check, unlike the LDAP-bind
  admin work).

## Open questions resolved during brainstorming

- **Scope**: both Tasks-page polish and Dashboard-widget enhancement,
  together — user confirmed, since the widget change reuses the exact
  urgency logic the Tasks-page change builds, doing them separately would
  mean writing (or duplicating) that logic twice.
- **v2 fidelity**: adapt the *spirit* of v2's `ActionItemsPage.tsx` (stats
  strip, urgency coloring, relative dates) to this app's existing Violet
  Design System conventions, not a pixel-for-pixel port — v2's specific
  interaction chrome (swipe-undo, bottom-sheet drawer, animations) is
  explicitly excluded.
- **"Open" definition for the stats strip**: status `!== "done"` (i.e.
  `open` + `in_progress` combined), not the narrower `status === "open"`
  the List view's own filter tab uses — chosen because a task sitting in
  the Kanban board's "in progress" column is still outstanding and should
  count toward "how many things need attention," even though the page's
  existing filter tabs don't expose an "in_progress" option.
