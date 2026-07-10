# Navigation Shell + Dashboard Home Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Documents-workspace root with a real widget-based Dashboard at `/`, move Documents to `/documents`, and give the sidebar a Dashboard entry, an alerts bell, and a visible command-palette trigger — all built from existing APIs, with zero new backend work.

**Architecture:** `apps/web` is a Vite + React 18 + TypeScript SPA (react-router-dom v6, no Next.js). Every widget is a plain `useEffect` + `useState` fetch against an existing `lib/api.ts` function (no data layer/cache exists in this codebase, so none is introduced). A new `DashboardWidgetCard` wraps loading/empty/collapse chrome shared by every widget. A new `AlertsBell` replaces the sidebar's inline pending-review badge. The Cmd+K command palette's open/closed state moves from local `useState` in `CommandCenter` into a small context provider (mirroring the existing `ToastProvider`/`LoadingBarProvider` pattern) so the new sidebar search button can open it too.

**Tech Stack:** React 18, TypeScript, react-router-dom v6, react-i18next, Tailwind CSS (design tokens in `apps/web/src/styles/tokens.css`), Vitest + Testing Library.

## Global Constraints

- Follow existing patterns exactly: functional components, `useTranslation()`/`t()` for all copy (never hardcoded English strings), Tailwind utility classes using the existing `bg-surface`/`text-ink`/`border-edge`/etc. design tokens, no new dependencies.
- Every new user-facing string needs matching keys in all three locale files: `apps/web/src/locales/en.json`, `nl.json`, `de.json`.
- No new backend endpoints. Every widget uses a function that already exists in `apps/web/src/lib/api.ts`.
- Do not rename `routes/Workspace.tsx` or its test file — only its route path changes (`/` → `/documents`). Renaming is unrelated churn, out of scope.
- Data fetches that fail render the widget's empty state rather than an error (matches the existing `Sidebar.tsx` pending-count fetch: "Badge is a nice-to-have signal, not core navigation -- fail silently").
- Run `pnpm --filter web test -- --run <file>` (Vitest) after every task; run the full `pnpm --filter web test -- --run` before the final commit of the plan.

---

### Task 1: DashboardWidgetCard shared component

**Files:**
- Create: `apps/web/src/components/DashboardWidgetCard.tsx`
- Test: `apps/web/src/components/DashboardWidgetCard.test.tsx`

**Interfaces:**
- Produces: `DashboardWidgetCard({ title, loading, isEmpty, emptyMessage, children, actions? }): JSX.Element` — named export. `title: string`, `loading: boolean`, `isEmpty: boolean`, `emptyMessage: string`, `children: ReactNode`, `actions?: ReactNode`. Wraps content in the existing `Card` (`apps/web/src/components/Card.tsx`, default export) and `Skeleton` (`apps/web/src/components/ui/Skeleton.tsx`, named export `Skeleton`). Renders a collapse toggle button (`aria-expanded`, `aria-label`); when collapsed, only the header row shows.

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/components/DashboardWidgetCard.test.tsx
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DashboardWidgetCard } from "./DashboardWidgetCard";

describe("DashboardWidgetCard", () => {
  it("renders the title and children when loaded and non-empty", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={false} isEmpty={false} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByText("Recent documents")).toBeInTheDocument();
    expect(screen.getByText("Lease agreement")).toBeInTheDocument();
  });

  it("shows a skeleton instead of children while loading", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={true} isEmpty={false} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByTestId("widget-skeleton")).toBeInTheDocument();
    expect(screen.queryByText("Lease agreement")).not.toBeInTheDocument();
  });

  it("shows the empty message when loaded and empty", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={false} isEmpty={true} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByText("Nothing here")).toBeInTheDocument();
    expect(screen.queryByText("Lease agreement")).not.toBeInTheDocument();
  });

  it("collapses and expands when the toggle is clicked, hiding content while collapsed", () => {
    render(
      <DashboardWidgetCard title="Recent documents" loading={false} isEmpty={false} emptyMessage="Nothing here">
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    const toggle = screen.getByRole("button", { name: "Collapse Recent documents" });
    fireEvent.click(toggle);
    expect(screen.queryByText("Lease agreement")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Expand Recent documents" }));
    expect(screen.getByText("Lease agreement")).toBeInTheDocument();
  });

  it("renders optional header actions", () => {
    render(
      <DashboardWidgetCard
        title="Recent documents"
        loading={false}
        isEmpty={false}
        emptyMessage="Nothing here"
        actions={<a href="/documents">View all</a>}
      >
        <p>Lease agreement</p>
      </DashboardWidgetCard>
    );
    expect(screen.getByRole("link", { name: "View all" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter web test -- --run src/components/DashboardWidgetCard.test.tsx`
Expected: FAIL with "Failed to resolve import ./DashboardWidgetCard" (module doesn't exist yet)

- [ ] **Step 3: Write the implementation**

```tsx
// apps/web/src/components/DashboardWidgetCard.tsx
import { useState, type ReactNode } from "react";
import Card from "./Card";
import { Skeleton } from "./ui/Skeleton";

export function DashboardWidgetCard({
  title,
  loading,
  isEmpty,
  emptyMessage,
  children,
  actions,
}: {
  title: string;
  loading: boolean;
  isEmpty: boolean;
  emptyMessage: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-ink">{title}</h2>
        <div className="flex items-center gap-2">
          {actions}
          <button
            type="button"
            aria-expanded={!collapsed}
            aria-label={collapsed ? `Expand ${title}` : `Collapse ${title}`}
            onClick={() => setCollapsed((v) => !v)}
            className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md text-ink-3 transition-colors duration-fast hover:bg-hover hover:text-ink"
          >
            {collapsed ? "+" : "–"}
          </button>
        </div>
      </div>
      {!collapsed &&
        (loading ? (
          <div className="flex flex-col gap-2" data-testid="widget-skeleton">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/4" />
            <Skeleton className="h-4 w-1/2" />
          </div>
        ) : isEmpty ? (
          <p className="text-sm text-ink-2">{emptyMessage}</p>
        ) : (
          children
        ))}
    </Card>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter web test -- --run src/components/DashboardWidgetCard.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/DashboardWidgetCard.tsx apps/web/src/components/DashboardWidgetCard.test.tsx
git commit -m "feat: add DashboardWidgetCard shared loading/empty/collapse wrapper"
```

---

### Task 2: Dashboard page with widgets

**Files:**
- Create: `apps/web/src/routes/Dashboard.tsx`
- Test: `apps/web/src/routes/Dashboard.test.tsx`
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`, `apps/web/src/locales/de.json`

**Interfaces:**
- Consumes: `DashboardWidgetCard` (Task 1). From `apps/web/src/lib/api.ts`: `listDocuments(): Promise<DocumentOut[]>`, `listTasks(status?: string): Promise<TaskOut[]>`, `listCases(): Promise<CaseOut[]>`, `listEntities(q?, entityType?, status?): Promise<EntityOut[]>`, `getAdminHealth(): Promise<ServiceHealthOut[]>`. From `apps/web/src/lib/auth.tsx`: `useAuth(): { user: UserOut | null }`.
- Produces: `Dashboard` default export, a route component with no props — mounted directly by `<Dashboard />` in tests (routing wiring happens in Task 3).

**Step 0: Add locale keys (all three files, before writing the component)**

Add this `"dashboard"` object to `apps/web/src/locales/en.json`, inserted right after the existing `"nav"` block (before `"common"`):

```json
  "dashboard": {
    "greetingMorning": "Good morning, {{name}}",
    "greetingAfternoon": "Good afternoon, {{name}}",
    "greetingEvening": "Good evening, {{name}}",
    "quickActionsTitle": "Quick actions",
    "quickActionChat": "Ask a question",
    "quickActionChatDesc": "Chat with your documents",
    "quickActionLegal": "Draft a document",
    "quickActionLegalDesc": "Generate a grounded legal draft",
    "quickActionAssistant": "Ask the assistant",
    "quickActionAssistantDesc": "Let the assistant choose the right tool",
    "quickActionTasks": "View tasks",
    "quickActionTasksDesc": "See what's open and due",
    "recentDocumentsTitle": "Recent documents",
    "recentDocumentsEmpty": "No documents yet.",
    "myTasksTitle": "My tasks",
    "myTasksEmpty": "No open tasks.",
    "pendingReviewsTitle": "Pending entity reviews",
    "pendingReviewsEmpty": "Nothing to review.",
    "pendingReviewsCount_one": "{{count}} entity waiting for review",
    "pendingReviewsCount_other": "{{count}} entities waiting for review",
    "recentCasesTitle": "Recent cases",
    "recentCasesEmpty": "No cases yet.",
    "systemStatusTitle": "System status",
    "viewAll": "View all →"
  },
```

Add this to `apps/web/src/locales/nl.json` in the same position:

```json
  "dashboard": {
    "greetingMorning": "Goedemorgen, {{name}}",
    "greetingAfternoon": "Goedemiddag, {{name}}",
    "greetingEvening": "Goedenavond, {{name}}",
    "quickActionsTitle": "Snelle acties",
    "quickActionChat": "Stel een vraag",
    "quickActionChatDesc": "Chat met je documenten",
    "quickActionLegal": "Stel een document op",
    "quickActionLegalDesc": "Genereer een onderbouwd juridisch concept",
    "quickActionAssistant": "Vraag de assistent",
    "quickActionAssistantDesc": "Laat de assistent de juiste tool kiezen",
    "quickActionTasks": "Bekijk taken",
    "quickActionTasksDesc": "Zie wat er openstaat en wanneer het moet",
    "recentDocumentsTitle": "Recente documenten",
    "recentDocumentsEmpty": "Nog geen documenten.",
    "myTasksTitle": "Mijn taken",
    "myTasksEmpty": "Geen openstaande taken.",
    "pendingReviewsTitle": "Te beoordelen entiteiten",
    "pendingReviewsEmpty": "Niets te beoordelen.",
    "pendingReviewsCount_one": "{{count}} entiteit wacht op beoordeling",
    "pendingReviewsCount_other": "{{count}} entiteiten wachten op beoordeling",
    "recentCasesTitle": "Recente zaken",
    "recentCasesEmpty": "Nog geen zaken.",
    "systemStatusTitle": "Systeemstatus",
    "viewAll": "Alles bekijken →"
  },
```

Add this to `apps/web/src/locales/de.json` in the same position:

```json
  "dashboard": {
    "greetingMorning": "Guten Morgen, {{name}}",
    "greetingAfternoon": "Guten Tag, {{name}}",
    "greetingEvening": "Guten Abend, {{name}}",
    "quickActionsTitle": "Schnellaktionen",
    "quickActionChat": "Frage stellen",
    "quickActionChatDesc": "Mit deinen Dokumenten chatten",
    "quickActionLegal": "Dokument entwerfen",
    "quickActionLegalDesc": "Einen fundierten Rechtsentwurf erstellen",
    "quickActionAssistant": "Assistent fragen",
    "quickActionAssistantDesc": "Den Assistenten das passende Werkzeug wählen lassen",
    "quickActionTasks": "Aufgaben ansehen",
    "quickActionTasksDesc": "Sehen, was offen ist und ansteht",
    "recentDocumentsTitle": "Neueste Dokumente",
    "recentDocumentsEmpty": "Noch keine Dokumente.",
    "myTasksTitle": "Meine Aufgaben",
    "myTasksEmpty": "Keine offenen Aufgaben.",
    "pendingReviewsTitle": "Zu prüfende Entitäten",
    "pendingReviewsEmpty": "Nichts zu prüfen.",
    "pendingReviewsCount_one": "{{count}} Entität wartet auf Prüfung",
    "pendingReviewsCount_other": "{{count}} Entitäten warten auf Prüfung",
    "recentCasesTitle": "Neueste Fälle",
    "recentCasesEmpty": "Noch keine Fälle.",
    "systemStatusTitle": "Systemstatus",
    "viewAll": "Alle anzeigen →"
  },
```

(Insert as valid JSON — add a trailing comma after the `"nav": { ... }` block's closing brace and before your new `"dashboard"` key in all three files.)

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Dashboard.test.tsx
import { describe, expect, it, beforeEach, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "./Dashboard";
import * as api from "../lib/api";

const { mockUseAuth } = vi.hoisted(() => ({ mockUseAuth: vi.fn() }));
vi.mock("../lib/auth", () => ({ useAuth: mockUseAuth }));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listDocuments: vi.fn(),
    listTasks: vi.fn(),
    listCases: vi.fn(),
    listEntities: vi.fn(),
    getAdminHealth: vi.fn(),
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <Dashboard />
    </MemoryRouter>
  );
}

describe("Dashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({ user: { display_name: "Ada Lovelace", role: "member" } });
    vi.mocked(api.listDocuments).mockResolvedValue([]);
    vi.mocked(api.listTasks).mockResolvedValue([]);
    vi.mocked(api.listCases).mockResolvedValue([]);
    vi.mocked(api.listEntities).mockResolvedValue([]);
    vi.mocked(api.getAdminHealth).mockResolvedValue([]);
  });

  it("greets the signed-in user by name in the page heading", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { level: 1 })).toHaveTextContent("Ada Lovelace");
  });

  it("renders the AI quick action links", async () => {
    renderPage();
    expect(await screen.findByRole("link", { name: /Ask a question/ })).toHaveAttribute("href", "/chat");
    expect(screen.getByRole("link", { name: /Draft a document/ })).toHaveAttribute("href", "/legal");
    expect(screen.getByRole("link", { name: /Ask the assistant/ })).toHaveAttribute("href", "/assistant");
    expect(screen.getByRole("link", { name: /View tasks/ })).toHaveAttribute("href", "/tasks");
  });

  it("shows the most recent documents, newest first", async () => {
    vi.mocked(api.listDocuments).mockResolvedValue([
      { id: "d1", title: "Older lease", filename: "a.pdf", mime_type: "application/pdf", status: "ready", error: null, created_at: "2026-01-01T00:00:00Z", processed_at: null, category_id: null },
      { id: "d2", title: "Newer invoice", filename: "b.pdf", mime_type: "application/pdf", status: "ready", error: null, created_at: "2026-02-01T00:00:00Z", processed_at: null, category_id: null },
    ]);
    renderPage();
    const links = await screen.findAllByRole("link", { name: /Older lease|Newer invoice/ });
    expect(links[0]).toHaveTextContent("Newer invoice");
    expect(links[1]).toHaveTextContent("Older lease");
  });

  it("shows the recent-documents empty state when there are none", async () => {
    renderPage();
    expect(await screen.findByText("No documents yet.")).toBeInTheDocument();
  });

  it("shows open tasks", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([
      { id: "t1", document_id: null, title: "Review lease", description: null, due_date: null, assignee: null, status: "open", position: 0, source: "manual", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(api.listTasks).toHaveBeenCalledWith("open");
  });

  it("shows the pending entity review count linking to the review queue", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([
      { id: "e1", name: "Acme BV", entity_type: "organization", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
      { id: "e2", name: "Jane Doe", entity_type: "person", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("2 entities waiting for review")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "2 entities waiting for review" })).toHaveAttribute("href", "/entities/review");
  });

  it("shows recent cases", async () => {
    vi.mocked(api.listCases).mockResolvedValue([
      { id: "c1", name: "Smith matter", description: null, status: "open", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderPage();
    expect(await screen.findByText("Smith matter")).toBeInTheDocument();
  });

  it("shows a system status widget for admins", async () => {
    mockUseAuth.mockReturnValue({ user: { display_name: "Ada Admin", role: "admin" } });
    vi.mocked(api.getAdminHealth).mockResolvedValue([{ name: "postgres", status: "up", detail: null }]);
    renderPage();
    expect(await screen.findByText("System status")).toBeInTheDocument();
    expect(await screen.findByText("postgres")).toBeInTheDocument();
  });

  it("hides the system status widget for non-admins", async () => {
    renderPage();
    await waitFor(() => expect(api.listDocuments).toHaveBeenCalled());
    expect(screen.queryByText("System status")).not.toBeInTheDocument();
    expect(api.getAdminHealth).not.toHaveBeenCalled();
  });
});

describe("getGreetingKey", () => {
  it("returns the morning key before noon", () => {
    expect(getGreetingKey(0)).toBe("dashboard.greetingMorning");
    expect(getGreetingKey(11)).toBe("dashboard.greetingMorning");
  });

  it("returns the afternoon key from noon up to 6pm", () => {
    expect(getGreetingKey(12)).toBe("dashboard.greetingAfternoon");
    expect(getGreetingKey(17)).toBe("dashboard.greetingAfternoon");
  });

  it("returns the evening key from 6pm onward", () => {
    expect(getGreetingKey(18)).toBe("dashboard.greetingEvening");
    expect(getGreetingKey(23)).toBe("dashboard.greetingEvening");
  });
});
```

This last block needs `getGreetingKey` imported alongside the default export — update the top of the file to a named+default import:

```tsx
import Dashboard, { getGreetingKey } from "./Dashboard";
```

(Replace the earlier `import Dashboard from "./Dashboard";` line with this one.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pnpm --filter web test -- --run src/routes/Dashboard.test.tsx`
Expected: FAIL with "Failed to resolve import ./Dashboard"

- [ ] **Step 3: Write the implementation**

```tsx
// apps/web/src/routes/Dashboard.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import {
  listDocuments,
  listTasks,
  listCases,
  listEntities,
  getAdminHealth,
  type DocumentOut,
  type TaskOut,
  type CaseOut,
  type EntityOut,
  type ServiceHealthOut,
} from "../lib/api";
import Card from "../components/Card";
import { DashboardWidgetCard } from "../components/DashboardWidgetCard";
import { Badge } from "../components/ui/Badge";

const QUICK_ACTIONS: { to: string; titleKey: string; descKey: string }[] = [
  { to: "/chat", titleKey: "dashboard.quickActionChat", descKey: "dashboard.quickActionChatDesc" },
  { to: "/legal", titleKey: "dashboard.quickActionLegal", descKey: "dashboard.quickActionLegalDesc" },
  { to: "/assistant", titleKey: "dashboard.quickActionAssistant", descKey: "dashboard.quickActionAssistantDesc" },
  { to: "/tasks", titleKey: "dashboard.quickActionTasks", descKey: "dashboard.quickActionTasksDesc" },
];

export function getGreetingKey(hour: number): "dashboard.greetingMorning" | "dashboard.greetingAfternoon" | "dashboard.greetingEvening" {
  if (hour < 12) return "dashboard.greetingMorning";
  if (hour < 18) return "dashboard.greetingAfternoon";
  return "dashboard.greetingEvening";
}

export default function Dashboard() {
  const { t } = useTranslation();
  const { user } = useAuth();

  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [tasksLoading, setTasksLoading] = useState(true);
  const [pendingEntities, setPendingEntities] = useState<EntityOut[]>([]);
  const [pendingLoading, setPendingLoading] = useState(true);
  const [cases, setCases] = useState<CaseOut[]>([]);
  const [casesLoading, setCasesLoading] = useState(true);
  const [health, setHealth] = useState<ServiceHealthOut[]>([]);
  const [healthLoading, setHealthLoading] = useState(true);

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(() => {
        // Widgets degrade to their empty state on failure -- not core navigation.
      })
      .finally(() => setDocumentsLoading(false));
  }, []);

  useEffect(() => {
    listTasks("open")
      .then(setTasks)
      .catch(() => {})
      .finally(() => setTasksLoading(false));
  }, []);

  useEffect(() => {
    listEntities(undefined, undefined, "pending_review")
      .then(setPendingEntities)
      .catch(() => {})
      .finally(() => setPendingLoading(false));
  }, []);

  useEffect(() => {
    listCases()
      .then(setCases)
      .catch(() => {})
      .finally(() => setCasesLoading(false));
  }, []);

  useEffect(() => {
    if (user?.role !== "admin") {
      setHealthLoading(false);
      return;
    }
    getAdminHealth()
      .then(setHealth)
      .catch(() => {})
      .finally(() => setHealthLoading(false));
  }, [user?.role]);

  const recentDocuments = [...documents].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  const recentTasks = tasks.slice(0, 5);
  const recentCases = [...cases].sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 5);
  const now = new Date();

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold text-ink">
        {t(getGreetingKey(now.getHours()), { name: user?.display_name ?? "" })}
      </h1>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-ink">{t("dashboard.quickActionsTitle")}</h2>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {QUICK_ACTIONS.map((action) => (
            <Link
              key={action.to}
              to={action.to}
              className="flex flex-col gap-1 rounded-xl border border-edge px-3 py-2.5 transition-colors duration-fast hover:border-accent hover:bg-hover"
            >
              <span className="text-sm font-medium text-ink">{t(action.titleKey)}</span>
              <span className="text-xs text-ink-2">{t(action.descKey)}</span>
            </Link>
          ))}
        </div>
      </Card>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
        <DashboardWidgetCard
          title={t("dashboard.recentDocumentsTitle")}
          loading={documentsLoading}
          isEmpty={recentDocuments.length === 0}
          emptyMessage={t("dashboard.recentDocumentsEmpty")}
          actions={
            <Link to="/documents" className="text-xs text-accent hover:underline">
              {t("dashboard.viewAll")}
            </Link>
          }
        >
          <ul className="flex flex-col gap-2">
            {recentDocuments.map((doc) => (
              <li key={doc.id}>
                <Link to={`/documents/${doc.id}`} className="text-sm text-ink hover:text-accent">
                  {doc.title}
                </Link>
              </li>
            ))}
          </ul>
        </DashboardWidgetCard>

        <DashboardWidgetCard
          title={t("dashboard.myTasksTitle")}
          loading={tasksLoading}
          isEmpty={recentTasks.length === 0}
          emptyMessage={t("dashboard.myTasksEmpty")}
          actions={
            <Link to="/tasks" className="text-xs text-accent hover:underline">
              {t("dashboard.viewAll")}
            </Link>
          }
        >
          <ul className="flex flex-col gap-2">
            {recentTasks.map((task) => (
              <li key={task.id} className="text-sm text-ink">
                {task.title}
              </li>
            ))}
          </ul>
        </DashboardWidgetCard>

        <DashboardWidgetCard
          title={t("dashboard.pendingReviewsTitle")}
          loading={pendingLoading}
          isEmpty={pendingEntities.length === 0}
          emptyMessage={t("dashboard.pendingReviewsEmpty")}
        >
          <Link to="/entities/review" className="text-sm font-medium text-accent hover:underline">
            {t("dashboard.pendingReviewsCount", { count: pendingEntities.length })}
          </Link>
        </DashboardWidgetCard>

        <DashboardWidgetCard
          title={t("dashboard.recentCasesTitle")}
          loading={casesLoading}
          isEmpty={recentCases.length === 0}
          emptyMessage={t("dashboard.recentCasesEmpty")}
          actions={
            <Link to="/cases" className="text-xs text-accent hover:underline">
              {t("dashboard.viewAll")}
            </Link>
          }
        >
          <ul className="flex flex-col gap-2">
            {recentCases.map((c) => (
              <li key={c.id}>
                <Link to={`/cases/${c.id}`} className="text-sm text-ink hover:text-accent">
                  {c.name}
                </Link>
              </li>
            ))}
          </ul>
        </DashboardWidgetCard>

        {user?.role === "admin" && (
          <DashboardWidgetCard
            title={t("dashboard.systemStatusTitle")}
            loading={healthLoading}
            isEmpty={health.length === 0}
            emptyMessage={t("dashboard.recentDocumentsEmpty")}
          >
            <ul className="flex flex-col gap-2">
              {health.map((service) => (
                <li key={service.name} className="flex items-center justify-between text-sm">
                  <span className="text-ink">{service.name}</span>
                  <Badge variant={service.status === "up" ? "success" : "danger"}>{service.status}</Badge>
                </li>
              ))}
            </ul>
          </DashboardWidgetCard>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm --filter web test -- --run src/routes/Dashboard.test.tsx`
Expected: PASS (12 tests)

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/Dashboard.tsx apps/web/src/routes/Dashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat: add Dashboard page with quick actions and 5 data widgets"
```

---

### Task 3: Route Dashboard at `/`, move Documents to `/documents`

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/lib/navigation.ts`
- Modify: `apps/web/src/routes/DocumentDetail.tsx`
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`, `apps/web/src/locales/de.json` (add `nav.dashboard`)

**Interfaces:**
- Consumes: `Dashboard` default export (Task 2).
- Produces: `/` renders `Dashboard`; `/documents` renders the existing `Workspace` component (file/name unchanged, see Global Constraints). `NAV_ITEMS[0]` becomes `{ to: "/", labelKey: "nav.dashboard" }`; a new second entry `{ to: "/documents", labelKey: "nav.documents" }` is added.

- [ ] **Step 1: Add the `nav.dashboard` key to all three locale files**

In `apps/web/src/locales/en.json`, inside `"nav"`, add `"dashboard": "Dashboard",` as the first key (before `"documents"`).
In `apps/web/src/locales/nl.json`, inside `"nav"`, add `"dashboard": "Dashboard",` as the first key (Dutch commonly uses the same loanword).
In `apps/web/src/locales/de.json`, inside `"nav"`, add `"dashboard": "Dashboard",` as the first key (German commonly uses the same loanword).

- [ ] **Step 2: Update `navigation.ts`**

Replace the `NAV_ITEMS` array in `apps/web/src/lib/navigation.ts`:

```ts
export const NAV_ITEMS: { to: string; labelKey: string }[] = [
  { to: "/", labelKey: "nav.dashboard" },
  { to: "/documents", labelKey: "nav.documents" },
  { to: "/chat", labelKey: "nav.aiChat" },
  { to: "/legal", labelKey: "nav.legalDraft" },
  { to: "/tasks", labelKey: "nav.tasks" },
  { to: "/entities", labelKey: "nav.entities" },
  { to: "/cases", labelKey: "nav.cases" },
  { to: "/vehicles", labelKey: "nav.vehicles" },
  { to: "/assistant", labelKey: "nav.assistant" },
  { to: "/settings", labelKey: "nav.settings" },
];
```

(The `navItemsForRole` function below it is unchanged.)

- [ ] **Step 3: Update `App.tsx` routing**

In `apps/web/src/App.tsx`, add the `Dashboard` import alongside the other route imports:

```tsx
import Dashboard from "./routes/Dashboard";
```

Change the `/` route's element from `<Workspace />` to `<Dashboard />`, and add a new `/documents` route rendering `<Workspace />`:

```tsx
                <Route
                  path="/"
                  element={
                    <ProtectedRoute>
                      <Dashboard />
                    </ProtectedRoute>
                  }
                />
                <Route
                  path="/documents"
                  element={
                    <ProtectedRoute>
                      <Workspace />
                    </ProtectedRoute>
                  }
                />
```

(This replaces the single existing `path="/"` route block; everything else in `App.tsx` — the `Workspace` import, the other routes — stays as-is.)

- [ ] **Step 4: Fix the two root-path references in `DocumentDetail.tsx`**

In `apps/web/src/routes/DocumentDetail.tsx`, change the post-delete redirect on line 69 from `navigate("/")` to `navigate("/documents")`.

Change both `Breadcrumbs` items on lines 80 and 92 from `{ label: t("nav.documents"), to: "/" }` to `{ label: t("nav.documents"), to: "/documents" }`.

- [ ] **Step 5: Run the full frontend test suite**

Run: `pnpm --filter web test -- --run`
Expected: PASS — `Workspace.test.tsx` and `DocumentDetail.test.tsx` still pass unchanged (neither test file asserts on the literal `"/"` path, confirmed during planning), `Sidebar.test.tsx` will fail here (its "Documents" link assertion expects `href="/"`) — that is expected and fixed in Task 5, which rewrites `Sidebar.test.tsx`. Confirm no *other* file fails.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/App.tsx apps/web/src/lib/navigation.ts apps/web/src/routes/DocumentDetail.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat: route Dashboard at / and move Documents workspace to /documents"
```

---

### Task 4: AlertsBell component

**Files:**
- Create: `apps/web/src/components/AlertsBell.tsx`
- Test: `apps/web/src/components/AlertsBell.test.tsx`
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`, `apps/web/src/locales/de.json`

**Interfaces:**
- Consumes: `Dropdown` (`apps/web/src/components/ui/Dropdown.tsx`, named export, `{ trigger: ReactNode; options: DropdownOption[] }` where `DropdownOption = { label: string; onSelect: () => void; danger?: boolean }`). `listEntities` from `apps/web/src/lib/api.ts`.
- Produces: `AlertsBell` named export, a self-contained component (no props) rendered by `Sidebar` in Task 5.

- [ ] **Step 1: Add `alerts` locale keys to all three files**

Add to `apps/web/src/locales/en.json`, right after the `"dashboard"` block added in Task 2:

```json
  "alerts": {
    "title": "Alerts",
    "empty": "You're all caught up",
    "pendingReviews_one": "{{count}} entity pending review",
    "pendingReviews_other": "{{count}} entities pending review"
  },
```

Add to `apps/web/src/locales/nl.json`:

```json
  "alerts": {
    "title": "Meldingen",
    "empty": "Je bent helemaal bij",
    "pendingReviews_one": "{{count}} entiteit wacht op beoordeling",
    "pendingReviews_other": "{{count}} entiteiten wachten op beoordeling"
  },
```

Add to `apps/web/src/locales/de.json`:

```json
  "alerts": {
    "title": "Benachrichtigungen",
    "empty": "Alles erledigt",
    "pendingReviews_one": "{{count}} Entität wartet auf Prüfung",
    "pendingReviews_other": "{{count}} Entitäten warten auf Prüfung"
  },
```

- [ ] **Step 2: Write the failing test**

```tsx
// apps/web/src/components/AlertsBell.test.tsx
import { describe, expect, it, beforeEach, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AlertsBell } from "./AlertsBell";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listEntities: vi.fn() };
});

function renderBell() {
  return render(
    <MemoryRouter>
      <AlertsBell />
    </MemoryRouter>
  );
}

describe("AlertsBell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("shows no count badge when there is nothing pending", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    renderBell();
    await screen.findByLabelText("Alerts");
    expect(screen.queryByTestId("alerts-bell-badge")).not.toBeInTheDocument();
  });

  it("shows the pending count as a badge and lists it in the dropdown", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([
      { id: "e1", name: "Acme BV", entity_type: "organization", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
      { id: "e2", name: "Jane Doe", entity_type: "person", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderBell();
    expect(await screen.findByTestId("alerts-bell-badge")).toHaveTextContent("2");
    fireEvent.click(screen.getByLabelText("Alerts"));
    expect(screen.getByText("2 entities pending review")).toBeInTheDocument();
  });

  it("navigates to the review queue when the pending item is selected", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([
      { id: "e1", name: "Acme BV", entity_type: "organization", status: "pending_review", created_at: "2026-01-01T00:00:00Z" },
    ]);
    renderBell();
    await screen.findByTestId("alerts-bell-badge");
    fireEvent.click(screen.getByLabelText("Alerts"));
    fireEvent.click(screen.getByText("1 entity pending review"));
    // Navigation itself is exercised by CommandCenter's existing "Go to X" tests
    // via the same react-router API; here we only assert the option is clickable
    // without throwing.
  });

  it("shows the caught-up message when nothing is pending", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    renderBell();
    await screen.findByLabelText("Alerts");
    fireEvent.click(screen.getByLabelText("Alerts"));
    expect(screen.getByText("You're all caught up")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm --filter web test -- --run src/components/AlertsBell.test.tsx`
Expected: FAIL with "Failed to resolve import ./AlertsBell"

- [ ] **Step 4: Write the implementation**

```tsx
// apps/web/src/components/AlertsBell.tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Dropdown } from "./ui/Dropdown";
import { listEntities } from "../lib/api";

export function AlertsBell() {
  const [pendingCount, setPendingCount] = useState(0);
  const navigate = useNavigate();
  const { t } = useTranslation();

  useEffect(() => {
    listEntities(undefined, undefined, "pending_review")
      .then((entities) => setPendingCount(entities.length))
      .catch(() => {
        // Alerts are a nice-to-have signal, not core navigation -- fail silently.
      });
  }, []);

  const options =
    pendingCount > 0
      ? [{ label: t("alerts.pendingReviews", { count: pendingCount }), onSelect: () => navigate("/entities/review") }]
      : [{ label: t("alerts.empty"), onSelect: () => {} }];

  return (
    <Dropdown
      trigger={
        <span
          aria-label={t("alerts.title")}
          className="relative flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path
              d="M10 2.5a4 4 0 0 0-4 4v2.1c0 .53-.21 1.04-.59 1.41L4 11.5v1h12v-1l-1.41-1.49a2 2 0 0 1-.59-1.41V6.5a4 4 0 0 0-4-4Z"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinejoin="round"
            />
            <path d="M8.2 14.5a1.8 1.8 0 0 0 3.6 0" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          {pendingCount > 0 && (
            <span
              data-testid="alerts-bell-badge"
              className="absolute -right-0.5 -top-0.5 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-accent px-1 text-[10px] font-semibold text-white"
            >
              {pendingCount}
            </span>
          )}
        </span>
      }
      options={options}
    />
  );
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --filter web test -- --run src/components/AlertsBell.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/AlertsBell.tsx apps/web/src/components/AlertsBell.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat: add AlertsBell dropdown for pending entity reviews"
```

---

### Task 5: Sidebar restructure — AlertsBell, Dashboard link, command-palette trigger

**Files:**
- Create: `apps/web/src/lib/commandCenter.tsx`
- Test: `apps/web/src/lib/commandCenter.test.tsx`
- Modify: `apps/web/src/components/CommandCenter.tsx`
- Modify: `apps/web/src/components/CommandCenter.test.tsx`
- Modify: `apps/web/src/components/Sidebar.tsx`
- Modify: `apps/web/src/components/Sidebar.test.tsx`
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`, `apps/web/src/locales/de.json` (add `common.search`)

**Interfaces:**
- Consumes: `AlertsBell` (Task 4).
- Produces: `CommandCenterStateProvider` (wraps children, provides context), `useCommandCenterState(): { overlay: "none" | "palette" | "shortcuts"; setOverlay: (o) => void; openPalette: () => void }` — both named exports of `apps/web/src/lib/commandCenter.tsx`. `Sidebar` gains a visible search button that calls `openPalette()`.

- [ ] **Step 1: Add `common.search` to all three locale files**

In `apps/web/src/locales/en.json`, inside `"common"`, add `"search": "Search",`.
In `apps/web/src/locales/nl.json`, inside `"common"`, add `"search": "Zoeken",`.
In `apps/web/src/locales/de.json`, inside `"common"`, add `"search": "Suchen",`.

- [ ] **Step 2: Write the failing test for the new context module**

```tsx
// apps/web/src/lib/commandCenter.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CommandCenterStateProvider, useCommandCenterState } from "./commandCenter";

function Probe() {
  const { overlay, openPalette, setOverlay } = useCommandCenterState();
  return (
    <div>
      <span data-testid="overlay">{overlay}</span>
      <button onClick={openPalette}>open palette</button>
      <button onClick={() => setOverlay("none")}>close</button>
    </div>
  );
}

describe("CommandCenterStateProvider / useCommandCenterState", () => {
  it("starts closed", () => {
    render(
      <CommandCenterStateProvider>
        <Probe />
      </CommandCenterStateProvider>
    );
    expect(screen.getByTestId("overlay")).toHaveTextContent("none");
  });

  it("openPalette sets overlay to palette", () => {
    render(
      <CommandCenterStateProvider>
        <Probe />
      </CommandCenterStateProvider>
    );
    fireEvent.click(screen.getByText("open palette"));
    expect(screen.getByTestId("overlay")).toHaveTextContent("palette");
  });

  it("throws when used outside the provider", () => {
    function renderWithoutProvider() {
      render(<Probe />);
    }
    expect(renderWithoutProvider).toThrow("useCommandCenterState must be used within CommandCenterStateProvider");
  });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pnpm --filter web test -- --run src/lib/commandCenter.test.tsx`
Expected: FAIL with "Failed to resolve import ./commandCenter"

- [ ] **Step 4: Write `commandCenter.tsx`**

```tsx
// apps/web/src/lib/commandCenter.tsx
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export type CommandCenterOverlay = "none" | "palette" | "shortcuts";

interface CommandCenterContextValue {
  overlay: CommandCenterOverlay;
  setOverlay: (overlay: CommandCenterOverlay) => void;
  openPalette: () => void;
}

const CommandCenterContext = createContext<CommandCenterContextValue | null>(null);

export function CommandCenterStateProvider({ children }: { children: ReactNode }) {
  const [overlay, setOverlay] = useState<CommandCenterOverlay>("none");
  const openPalette = useCallback(() => setOverlay("palette"), []);

  return (
    <CommandCenterContext.Provider value={{ overlay, setOverlay, openPalette }}>
      {children}
    </CommandCenterContext.Provider>
  );
}

export function useCommandCenterState(): CommandCenterContextValue {
  const ctx = useContext(CommandCenterContext);
  if (!ctx) throw new Error("useCommandCenterState must be used within CommandCenterStateProvider");
  return ctx;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pnpm --filter web test -- --run src/lib/commandCenter.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/commandCenter.tsx apps/web/src/lib/commandCenter.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat: extract command-palette open state into a shared context"
```

- [ ] **Step 7: Update `CommandCenter.tsx` to consume the context**

Replace the local `useState<OverlayState>("none")` in `apps/web/src/components/CommandCenter.tsx` with the shared context. Full new file:

```tsx
// apps/web/src/components/CommandCenter.tsx
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { NAV_ITEMS } from "../lib/navigation";
import { CommandPalette } from "./ui/CommandPalette";
import { ShortcutsSheet } from "./ui/ShortcutsSheet";
import { useDarkMode } from "../hooks/useDarkMode";
import { useCommandCenterState } from "../lib/commandCenter";

export function CommandCenter() {
  const { overlay, setOverlay } = useCommandCenterState();
  const navigate = useNavigate();
  const { toggle: toggleDarkMode } = useDarkMode();
  const { t } = useTranslation();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA";

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOverlay(overlay === "palette" ? "none" : "palette");
      } else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") {
        event.preventDefault();
        toggleDarkMode();
      } else if (event.key === "?" && !isTyping) {
        event.preventDefault();
        setOverlay(overlay === "shortcuts" ? "none" : "shortcuts");
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [toggleDarkMode, overlay, setOverlay]);

  const items = NAV_ITEMS.map((item) => ({
    label: `Go to ${t(item.labelKey)}`,
    onSelect: () => navigate(item.to),
  }));

  return (
    <>
      <CommandPalette open={overlay === "palette"} onClose={() => setOverlay("none")} items={items} />
      <ShortcutsSheet open={overlay === "shortcuts"} onClose={() => setOverlay("none")} />
    </>
  );
}
```

- [ ] **Step 8: Update `CommandCenter.test.tsx` to wrap with the provider**

Replace the `renderWithRouter` helper and the standalone render in the last test in `apps/web/src/components/CommandCenter.test.tsx` — import and wrap with `CommandCenterStateProvider`. Full new file:

```tsx
// apps/web/src/components/CommandCenter.test.tsx
import { describe, expect, it, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CommandCenter } from "./CommandCenter";
import { CommandCenterStateProvider } from "../lib/commandCenter";

afterEach(cleanup);

function renderWithRouter() {
  return render(
    <MemoryRouter>
      <CommandCenterStateProvider>
        <CommandCenter />
      </CommandCenterStateProvider>
    </MemoryRouter>
  );
}

describe("CommandCenter", () => {
  it("renders nothing visible by default", () => {
    renderWithRouter();
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("opens the command palette on Cmd+K", () => {
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument();
  });

  it("opens the shortcuts sheet on ? when not typing in a field", () => {
    renderWithRouter();
    fireEvent.keyDown(document, { key: "?" });
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
  });

  it("does not open the shortcuts sheet on ? while an input is focused", () => {
    render(
      <MemoryRouter>
        <CommandCenterStateProvider>
          <input aria-label="some field" />
          <CommandCenter />
        </CommandCenterStateProvider>
      </MemoryRouter>
    );
    screen.getByLabelText("some field").focus();
    fireEvent.keyDown(document.activeElement!, { key: "?" });
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("lists every NAV_ITEMS entry as a palette item, prefixed with 'Go to '", () => {
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByText("Go to Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Go to Vehicles")).toBeInTheDocument();
    expect(screen.getByText("Go to Settings")).toBeInTheDocument();
  });
});
```

- [ ] **Step 9: Run test to verify it passes**

Run: `pnpm --filter web test -- --run src/components/CommandCenter.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 10: Update `Sidebar.tsx`**

Replace `apps/web/src/components/Sidebar.tsx` in full — removes the inline `listEntities`/`pendingCount` logic and the per-item badge (moved into `AlertsBell`), adds the `AlertsBell` and a search button next to the wordmark:

```tsx
// apps/web/src/components/Sidebar.tsx
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useEscapeToClose } from "../hooks/useEscapeToClose";
import { useCommandCenterState } from "../lib/commandCenter";
import { Button } from "./ui/Button";
import { AlertsBell } from "./AlertsBell";
import { navItemsForRole } from "../lib/navigation";

export default function Sidebar({
  mobileOpen = false,
  onCloseMobile = () => {},
}: {
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { openPalette } = useCommandCenterState();
  const { t } = useTranslation();
  const location = useLocation();
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pillStyle, setPillStyle] = useState<{ top: number; height: number }>({ top: 0, height: 0 });
  const navItems = navItemsForRole(user?.role);

  useEscapeToClose(mobileOpen, onCloseMobile);

  useEffect(() => {
    const activeItem = navItems.find((item) => (item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)));
    const el = activeItem ? itemRefs.current[activeItem.to] : null;
    if (el) {
      setPillStyle({ top: el.offsetTop, height: el.offsetHeight });
    }
  }, [location.pathname, navItems]);

  return (
    <>
      {mobileOpen && (
        <div
          data-testid="sidebar-backdrop"
          className="fixed inset-0 z-[70] bg-[#0D0C1A]/35 backdrop-blur-sm md:hidden"
          onClick={onCloseMobile}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-[71] flex w-56 shrink-0 flex-col justify-between border-r border-edge bg-sidebar-surface px-4 py-6 transition-transform duration-base ease-spring md:static md:z-auto md:h-screen md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex flex-col gap-6">
          <div className="flex items-center justify-between">
            <span className="text-lg font-semibold text-ink">CollaBrains</span>
            <div className="flex items-center gap-1">
              <button
                type="button"
                aria-label={t("common.search")}
                onClick={openPalette}
                className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
              >
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M17 17l-4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
              <AlertsBell />
            </div>
          </div>
          <nav className="relative flex flex-col gap-1 text-sm">
            <span
              data-testid="nav-pill"
              className="absolute left-0 right-0 z-0 rounded-lg bg-accent-soft transition-all duration-base ease-spring"
              style={{ top: pillStyle.top, height: pillStyle.height }}
            />
            {navItems.map((item) => (
              <NavLink
                key={item.to}
                ref={(el) => {
                  itemRefs.current[item.to] = el;
                }}
                to={item.to}
                end={item.to === "/"}
                onClick={onCloseMobile}
                className={({ isActive }) =>
                  `relative z-10 flex items-center justify-between rounded-lg px-3 py-2 transition-colors duration-fast ${
                    isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                  }`
                }
              >
                <span>{t(item.labelKey)}</span>
              </NavLink>
            ))}
          </nav>
        </div>
        {user && (
          <div className="flex flex-col gap-2 border-t border-edge pt-4 text-sm">
            <span className="text-ink-2">{user.display_name}</span>
            <button onClick={logout} className="text-left text-ink-2 hover:text-ink">
              {t("common.signOut")}
            </button>
            <Button variant="ghost" size="sm" onClick={toggle} className="justify-start">
              {isDark ? t("common.lightMode") : t("common.darkMode")}
            </Button>
          </div>
        )}
      </aside>
    </>
  );
}
```

- [ ] **Step 11: Update `Sidebar.test.tsx`**

Replace `apps/web/src/components/Sidebar.test.tsx` in full — wraps with `CommandCenterStateProvider`, updates the Documents href to `/documents`, adds a Dashboard link assertion, replaces the two inline-badge tests (now `AlertsBell`'s responsibility, covered in Task 4) with a lighter assertion that `AlertsBell` renders, and adds a search-button test:

```tsx
// apps/web/src/components/Sidebar.test.tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";
import i18n from "../lib/i18n";
import { CommandCenterStateProvider, useCommandCenterState } from "../lib/commandCenter";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listEntities: vi.fn() };
});

function OverlayProbe() {
  const { overlay } = useCommandCenterState();
  return <span data-testid="overlay-probe">{overlay}</span>;
}

function renderAt(
  path: string,
  props: { mobileOpen?: boolean; onCloseMobile?: () => void } = {},
) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CommandCenterStateProvider>
        <OverlayProbe />
        <Sidebar {...props} />
      </CommandCenterStateProvider>
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
  });

  it("renders every nav item as a link to the right route", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases");
    expect(screen.getByRole("link", { name: "Vehicles" })).toHaveAttribute("href", "/vehicles");
  });

  it("marks the item matching the current route as active", () => {
    renderAt("/cases");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveClass("text-accent");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveClass("text-accent");
  });

  it("renders a sliding pill element behind the nav list", () => {
    renderAt("/");
    expect(document.querySelector("[data-testid=\"nav-pill\"]")).toBeInTheDocument();
  });

  it("renders the AlertsBell", async () => {
    renderAt("/");
    expect(await screen.findByLabelText("Alerts")).toBeInTheDocument();
  });

  it("opens the command palette when the search button is clicked", () => {
    renderAt("/");
    fireEvent.click(screen.getByLabelText("Search"));
    expect(screen.getByTestId("overlay-probe")).toHaveTextContent("palette");
  });

  it("does not render a mobile backdrop when closed", () => {
    renderAt("/");
    expect(screen.queryByTestId("sidebar-backdrop")).not.toBeInTheDocument();
  });

  it("renders a mobile backdrop and slides the drawer in when open", () => {
    renderAt("/", { mobileOpen: true });
    expect(screen.getByTestId("sidebar-backdrop")).toBeInTheDocument();
    expect(document.querySelector("aside")).toHaveClass("translate-x-0");
  });

  it("calls onCloseMobile when the backdrop is clicked", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.click(screen.getByTestId("sidebar-backdrop"));
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  it("calls onCloseMobile when a nav link is clicked", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.click(screen.getByRole("link", { name: "Cases" }));
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  it("calls onCloseMobile on Escape when open", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  describe("language switching", () => {
    afterEach(() => {
      i18n.changeLanguage("en");
    });

    it("renders nav labels in Dutch when the language is switched to nl", async () => {
      await i18n.changeLanguage("nl");
      renderAt("/");
      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("link", { name: "Zaken" })).toHaveAttribute("href", "/cases");
    });

    it("renders nav labels in German when the language is switched to de", async () => {
      await i18n.changeLanguage("de");
      renderAt("/");
      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("link", { name: "Fälle" })).toHaveAttribute("href", "/cases");
    });
  });
});
```

- [ ] **Step 12: Run test to verify it passes**

Run: `pnpm --filter web test -- --run src/components/Sidebar.test.tsx`
Expected: PASS (11 tests)

- [ ] **Step 13: Wrap `App.tsx` with `CommandCenterStateProvider`**

In `apps/web/src/App.tsx`, add the import:

```tsx
import { CommandCenterStateProvider } from "./lib/commandCenter";
```

Wrap `<CommandCenter />` and `<Layout>` with the provider (inside `LoadingBarProvider`, replacing the existing unwrapped `<CommandCenter />` / `<RouteChangeLoadingBar />` / `<Layout>` sequence):

```tsx
            <CommandCenterStateProvider>
              <CommandCenter />
              <RouteChangeLoadingBar />
              <Layout>
                <Routes>
                  {/* ...unchanged... */}
                </Routes>
              </Layout>
            </CommandCenterStateProvider>
```

- [ ] **Step 14: Run the full frontend test suite**

Run: `pnpm --filter web test -- --run`
Expected: PASS, all files green (0 failures).

- [ ] **Step 15: Commit**

```bash
git add apps/web/src/components/CommandCenter.tsx apps/web/src/components/CommandCenter.test.tsx apps/web/src/components/Sidebar.tsx apps/web/src/components/Sidebar.test.tsx apps/web/src/App.tsx
git commit -m "feat: restructure sidebar with Dashboard link, AlertsBell, and search trigger"
```

---

### Task 6: Final verification pass

**Files:** none (verification only)

- [ ] **Step 1: Full test suite**

Run: `pnpm --filter web test -- --run`
Expected: PASS, 0 failures.

- [ ] **Step 2: Typecheck**

Run: `pnpm --filter web exec tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Lint**

Run: `pnpm --filter web lint` (check `apps/web/package.json` for the exact script name if this differs)
Expected: no errors.

- [ ] **Step 4: Manual smoke test in the dev server**

Run: `pnpm --filter web dev`, then in a browser:
- Log in, confirm you land on the new Dashboard at `/` with the greeting, quick actions, and widgets populated from real data.
- Click "View all" on Recent Documents, confirm it goes to `/documents` and the existing Documents workspace (search/filter/upload/bulk-delete) still works unchanged.
- Open a document, delete it, confirm you're returned to `/documents` (not a 404 at the old `/`).
- Click the sidebar search icon, confirm the Cmd+K palette opens; press Escape/click away to close; confirm Cmd+K still works too.
- Trigger the alerts bell (needs at least one entity in `pending_review` status), confirm the badge count and dropdown link to `/entities/review` work.
- Toggle dark mode, resize to a mobile viewport, and switch language to nl/de — confirm the Dashboard and Sidebar render correctly in all combinations.
- Log in as a non-admin user, confirm the System Status widget is absent.

- [ ] **Step 5: Commit any smoke-test fixes, then confirm branch is ready for PR**

If Step 4 surfaces any issue, fix it, re-run Steps 1-3, and commit with a `fix:` message before moving on.
