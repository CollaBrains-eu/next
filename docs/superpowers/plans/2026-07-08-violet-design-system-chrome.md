# Phase 20b: Violet Design System — Layout & Chrome Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the layout/chrome pieces of the violet design language that Phase 20a explicitly deferred — a sliding-nav-pill sidebar, a slide-in detail drawer with tabs, a command palette, a keyboard shortcuts sheet, a global loading bar, a sortable data table with pagination, and an empty-state redesign — on top of Phase 20a's tokens and primitives, with no page-level rollout yet.

**Architecture:** Every new component is generic and reusable, taking no knowledge of any specific page's data (that wiring is Phase 20c). Overlays (Drawer, CommandPalette, ShortcutsSheet) share a small `useEscapeToClose` hook instead of each re-implementing the same `keydown` listener — Phase 20a's `Modal` gets refactored to use it too, so there's exactly one Escape-handling implementation in the codebase, not four. The command palette and sidebar share one `NAV_ITEMS` source of truth instead of duplicating the route list. The loading bar is a real hook (`useLoadingBar`) wired to actual route-change events via `react-router-dom`'s `useLocation`, not a fake demo trigger button.

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4 (tokens from Phase 20a), Vitest 3 + `@testing-library/react`, react-router-dom 6, pnpm workspace.

## Scope

Builds on Phase 20a (PR #28, branch `phase-20a-design-system-foundation` — not yet merged to `main`): the tokens (`page`/`surface`/`sidebar-surface`/`ink`/`ink-2`/`ink-3`/`edge`/`accent`/etc., motion durations/easings) and primitives (`Button`, `Badge`, `Tooltip`, `ToastProvider`/`useToast`, `Modal`, `TextField`/`Select`/`Checkbox`/`Switch`) all already exist and are used as-is here.

This plan covers, and only covers: the sidebar's sliding active-indicator, a generic `Drawer` component, a generic `DataTable`+pagination component, an `EmptyState` visual redesign (same props, so its two existing call sites need zero changes), a `useLoadingBar` hook wired to real navigation, `CommandPalette`, and `ShortcutsSheet`.

Explicitly **not** in this plan — Phase 20c: bulk selection, filter chips, inline editing, split-view layout, and using any of `Drawer`/`DataTable`/etc. on the 9 real pages (Documents, Cases, Vehicles, Entities, Chat, Legal, Tasks, Settings, Assistant). Those pages are untouched by this plan except `Sidebar.tsx` (chrome shared by all of them) and `App.tsx` (mounting `CommandCenter`).

## Global Constraints

- Everything reuses Phase 20a's Tailwind theme tokens (`bg-surface`, `text-ink-2`, `border-edge`, `bg-accent`, `shadow-overlay`, `shadow-modal`, `duration-fast`/`base`/`slow`, `ease-out-token`/`spring`) — no new colors or motion values are introduced.
- All new overlay components must close on `Escape` (via `useEscapeToClose`, Task 2) and respect `prefers-reduced-motion` the same way Phase 20a's components do (CSS transitions naturally no-op under the global `@media (prefers-reduced-motion: reduce)` rule already in this codebase's Tailwind setup — no extra JS guard needed unless a component does cursor-tracked/JS-driven motion, none of which exist in this plan).
- Package manager is **pnpm**. `pnpm build`'s `tsc -b` step currently fails on `main` due to a pre-existing, unrelated `apps/mobile` `@types/react@19` hoisting conflict (documented in PR #28) — verify with `vite build` alone plus `pnpm test`, not the full `pnpm build`, exactly as Phase 20a did.
- No new dependencies. Everything in this plan is buildable with what Phase 20a already has installed (`react`, `react-router-dom`, `@testing-library/react`).

## Environment Setup (read before Task 1)

Same as Phase 20a — no local clone, only SSH:

```bash
ssh root@195.90.216.230   # apps/web lives at /opt/collabrains/apps/web
cd /opt/collabrains
git fetch origin --quiet
git checkout phase-20a-design-system-foundation
git checkout -b phase-20b-layout-chrome
cd apps/web
```

Branch from `phase-20a-design-system-foundation`, **not** `main` — Phase 20a's primitives (Button, Modal, tokens, etc.) aren't on `main` yet. Run every `pnpm` command from `/opt/collabrains/apps/web`. Commit after each task. Push and open a PR at the end (do not merge).

---

### Task 1: Shared nav items + sliding-pill Sidebar

**Files:**
- Create: `apps/web/src/lib/navigation.ts`
- Modify: `apps/web/src/components/Sidebar.tsx`
- Test: `apps/web/src/components/Sidebar.test.tsx`

**Interfaces:**
- Produces: `NAV_ITEMS: { to: string; label: string }[]` exported from `lib/navigation.ts` — Task 9's `CommandCenter` imports this same array so the palette's "Go to X" entries can never drift out of sync with the sidebar's actual routes.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/Sidebar.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  it("renders every nav item as a link to the right route", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases");
    expect(screen.getByRole("link", { name: "Vehicles" })).toHaveAttribute("href", "/vehicles");
  });

  it("marks the item matching the current route as active", () => {
    renderAt("/cases");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveClass("text-accent");
    expect(screen.getByRole("link", { name: "Documents" })).not.toHaveClass("text-accent");
  });

  it("renders a sliding pill element behind the nav list", () => {
    renderAt("/");
    expect(document.querySelector('[data-testid="nav-pill"]')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Sidebar`
Expected: FAIL — current `Sidebar` uses `bg-slate-100`/`text-slate-900` for the active state, not `text-accent`, and has no `nav-pill` element.

- [ ] **Step 3: Create the shared nav items file**

Create `apps/web/src/lib/navigation.ts`:
```typescript
export const NAV_ITEMS: { to: string; label: string }[] = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
  { to: "/cases", label: "Cases" },
  { to: "/vehicles", label: "Vehicles" },
  { to: "/assistant", label: "Assistant" },
  { to: "/settings", label: "Settings" },
];
```

- [ ] **Step 4: Update Sidebar to use the shared list, the new tokens, and a sliding pill**

Modify `apps/web/src/components/Sidebar.tsx` — replace its full contents:
```tsx
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { Button } from "./ui/Button";
import { NAV_ITEMS } from "../lib/navigation";

export default function Sidebar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const location = useLocation();
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pillStyle, setPillStyle] = useState<{ top: number; height: number }>({ top: 0, height: 0 });

  useEffect(() => {
    const activeItem = NAV_ITEMS.find((item) => (item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)));
    const el = activeItem ? itemRefs.current[activeItem.to] : null;
    if (el) {
      setPillStyle({ top: el.offsetTop, height: el.offsetHeight });
    }
  }, [location.pathname]);

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col justify-between border-r border-edge bg-sidebar-surface px-4 py-6">
      <div className="flex flex-col gap-6">
        <span className="text-lg font-semibold text-ink">CollaBrains</span>
        <nav className="relative flex flex-col gap-1 text-sm">
          <span
            data-testid="nav-pill"
            className="absolute left-0 right-0 z-0 rounded-lg bg-accent-soft transition-all duration-base ease-spring"
            style={{ top: pillStyle.top, height: pillStyle.height }}
          />
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              ref={(el) => {
                itemRefs.current[item.to] = el;
              }}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `relative z-10 rounded-lg px-3 py-2 transition-colors duration-fast ${
                  isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      {user && (
        <div className="flex flex-col gap-2 border-t border-edge pt-4 text-sm">
          <span className="text-ink-2">{user.display_name}</span>
          <button onClick={logout} className="text-left text-ink-2 hover:text-ink">
            Sign out
          </button>
          <Button variant="ghost" size="sm" onClick={toggle} className="justify-start">
            {isDark ? "☀️ Light mode" : "🌙 Dark mode"}
          </Button>
        </div>
      )}
    </aside>
  );
}
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pnpm test Sidebar`
Expected: `3 passed`. (The pill's `top`/`height` will both be `0` in jsdom since there's no real layout engine — that's expected and is why Step 1's test only asserts the pill element *exists*, not its position; positioning is verified visually in Task 9's manual browser check.)

- [ ] **Step 6: Run the full suite to check for regressions**

Run: `pnpm test`
Expected: all tests still pass (confirms nothing else imported the old inline `NAV_ITEMS` from `Sidebar.tsx`).

- [ ] **Step 7: Commit**

```bash
git add src/lib/navigation.ts src/components/Sidebar.tsx src/components/Sidebar.test.tsx
git commit -m "feat: sliding nav-pill sidebar, extract shared NAV_ITEMS"
```

---

### Task 2: `useEscapeToClose` hook (and refactor `Modal` to use it)

**Files:**
- Create: `apps/web/src/hooks/useEscapeToClose.ts`
- Test: `apps/web/src/hooks/useEscapeToClose.test.ts`
- Modify: `apps/web/src/components/ui/Modal.tsx`

**Interfaces:**
- Produces: `useEscapeToClose(active: boolean, onClose: () => void): void`. Tasks 3 (Drawer), 7 (CommandPalette), and 8 (ShortcutsSheet) all consume this instead of writing their own `keydown` listener.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/hooks/useEscapeToClose.test.ts`:
```typescript
import { describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { useEscapeToClose } from "./useEscapeToClose";

describe("useEscapeToClose", () => {
  it("calls onClose when Escape is pressed and active is true", () => {
    const onClose = vi.fn();
    renderHook(() => useEscapeToClose(true, onClose));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when active is false", () => {
    const onClose = vi.fn();
    renderHook(() => useEscapeToClose(false, onClose));
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("does not call onClose for other keys", () => {
    const onClose = vi.fn();
    renderHook(() => useEscapeToClose(true, onClose));
    fireEvent.keyDown(document, { key: "Enter" });
    expect(onClose).not.toHaveBeenCalled();
  });

  it("removes its listener when active becomes false", () => {
    const onClose = vi.fn();
    const { rerender } = renderHook(({ active }) => useEscapeToClose(active, onClose), {
      initialProps: { active: true },
    });
    rerender({ active: false });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test useEscapeToClose`
Expected: FAIL — `Cannot find module './useEscapeToClose'`.

- [ ] **Step 3: Implement the hook**

Create `apps/web/src/hooks/useEscapeToClose.ts`:
```typescript
import { useEffect } from "react";

export function useEscapeToClose(active: boolean, onClose: () => void): void {
  useEffect(() => {
    if (!active) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [active, onClose]);
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test useEscapeToClose`
Expected: `4 passed`.

- [ ] **Step 5: Refactor Modal to use the hook instead of its own inline listener**

Modify `apps/web/src/components/ui/Modal.tsx` — replace its full contents:
```tsx
import type { ReactNode } from "react";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  useEscapeToClose(open, onClose);

  if (!open) return null;

  return (
    <>
      <div
        data-testid="modal-backdrop"
        className="fixed inset-0 z-[70] bg-[#0D0C1A]/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="fixed left-1/2 top-1/2 z-[71] w-[min(380px,90vw)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-edge bg-surface p-6 shadow-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <h4 className="mb-2 text-base font-semibold text-ink">{title}</h4>
        {children}
      </div>
    </>
  );
}
```

- [ ] **Step 6: Run Modal's existing tests to confirm the refactor didn't break anything**

Run: `pnpm test Modal`
Expected: `5 passed` — same 5 tests from Phase 20a, now passing against the refactored implementation.

- [ ] **Step 7: Run the full suite**

Run: `pnpm test`
Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add src/hooks/useEscapeToClose.ts src/hooks/useEscapeToClose.test.ts src/components/ui/Modal.tsx
git commit -m "feat: add useEscapeToClose hook, refactor Modal to use it"
```

---

### Task 3: `Drawer` component (slide-in panel with tabs)

**Files:**
- Create: `apps/web/src/components/ui/Drawer.tsx`
- Test: `apps/web/src/components/ui/Drawer.test.tsx`

**Interfaces:**
- Consumes: `useEscapeToClose` (Task 2).
- Produces: `<Drawer open: boolean onClose: () => void title: string tabs: {id: string; label: string; content: ReactNode}[] footer?: ReactNode />`. Reopening (transitioning `open` from `false` to `true`) always resets to the first tab. Phase 20c will feed this real document/case data as `tabs[].content`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/Drawer.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Drawer } from "./Drawer";

const tabs = [
  { id: "details", label: "Details", content: <p>Detail content</p> },
  { id: "activity", label: "Activity", content: <p>Activity content</p> },
];

describe("Drawer", () => {
  it("renders nothing when closed", () => {
    render(<Drawer open={false} onClose={() => {}} title="factuur.pdf" tabs={tabs} />);
    expect(screen.queryByText("factuur.pdf")).not.toBeInTheDocument();
  });

  it("renders the title and the first tab's content by default when open", () => {
    render(<Drawer open onClose={() => {}} title="factuur.pdf" tabs={tabs} />);
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
    expect(screen.getByText("Detail content")).toBeInTheDocument();
    expect(screen.queryByText("Activity content")).not.toBeInTheDocument();
  });

  it("switches tab content when a tab is clicked", () => {
    render(<Drawer open onClose={() => {}} title="factuur.pdf" tabs={tabs} />);
    fireEvent.click(screen.getByText("Activity"));
    expect(screen.getByText("Activity content")).toBeInTheDocument();
    expect(screen.queryByText("Detail content")).not.toBeInTheDocument();
  });

  it("calls onClose when the close button is clicked", () => {
    const onClose = vi.fn();
    render(<Drawer open onClose={onClose} title="factuur.pdf" tabs={tabs} />);
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose on Escape", () => {
    const onClose = vi.fn();
    render(<Drawer open onClose={onClose} title="factuur.pdf" tabs={tabs} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("renders the footer when given", () => {
    render(
      <Drawer open onClose={() => {}} title="factuur.pdf" tabs={tabs} footer={<button>Download</button>}>
      </Drawer>
    );
    expect(screen.getByRole("button", { name: "Download" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Drawer`
Expected: FAIL — `Cannot find module './Drawer'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/Drawer.tsx`:
```tsx
import { useEffect, useState, type ReactNode } from "react";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

interface DrawerTab {
  id: string;
  label: string;
  content: ReactNode;
}

export function Drawer({
  open,
  onClose,
  title,
  tabs,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  tabs: DrawerTab[];
  footer?: ReactNode;
}) {
  const [activeTabId, setActiveTabId] = useState(tabs[0]?.id);

  useEffect(() => {
    if (open) setActiveTabId(tabs[0]?.id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  useEscapeToClose(open, onClose);

  if (!open) return null;

  const activeTab = tabs.find((tab) => tab.id === activeTabId) ?? tabs[0];

  return (
    <>
      <div
        data-testid="drawer-backdrop"
        className="fixed inset-0 z-[80] bg-[#0D0C1A]/35 backdrop-blur-sm"
        onClick={onClose}
      />
      <div className="fixed bottom-0 right-0 top-0 z-[81] flex w-[min(380px,92vw)] flex-col border-l border-edge bg-surface shadow-overlay">
        <div className="flex items-start justify-between border-b border-edge p-5">
          <h4 className="text-base font-semibold text-ink">{title}</h4>
          <button aria-label="Close" onClick={onClose} className="rounded-lg p-1 text-ink-2 hover:bg-hover hover:text-ink">
            ✕
          </button>
        </div>
        <div className="flex gap-4 border-b border-edge px-5">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTabId(tab.id)}
              className={`border-b-2 py-2.5 text-xs transition-colors duration-fast ${
                tab.id === activeTab.id ? "border-accent font-semibold text-accent" : "border-transparent text-ink-2"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex-1 overflow-y-auto p-5">{activeTab.content}</div>
        {footer && <div className="flex gap-2 border-t border-edge p-4">{footer}</div>}
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test Drawer`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/Drawer.tsx src/components/ui/Drawer.test.tsx
git commit -m "feat: add Drawer component (slide-in panel with tabs)"
```

---

### Task 4: `DataTable` with sorting and pagination

**Files:**
- Create: `apps/web/src/components/ui/DataTable.tsx`
- Test: `apps/web/src/components/ui/DataTable.test.tsx`

**Interfaces:**
- Produces: `<DataTable<T> columns: Column<T>[] rows: T[] pageSize?: number rowKey: (row: T) => string />` where `Column<T> = { key: string; header: string; render: (row: T) => ReactNode; sortable?: boolean; sortValue?: (row: T) => string | number }`. Generic over row type `T` — Phase 20c will pass real `Vehicle[]`/`Case[]`/etc.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/DataTable.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { fireEvent } from "@testing-library/react";
import { DataTable, type Column } from "./DataTable";

interface Row {
  id: string;
  plate: string;
  make: string;
}

const columns: Column<Row>[] = [
  { key: "plate", header: "Plate", sortable: true, sortValue: (r) => r.plate, render: (r) => r.plate },
  { key: "make", header: "Make", sortable: true, sortValue: (r) => r.make, render: (r) => r.make },
];

function makeRows(n: number): Row[] {
  return Array.from({ length: n }, (_, i) => ({ id: String(i), plate: `PLATE-${String(i).padStart(2, "0")}`, make: `Make ${i}` }));
}

describe("DataTable", () => {
  it("renders column headers and row cells", () => {
    render(<DataTable columns={columns} rows={makeRows(3)} rowKey={(r) => r.id} />);
    expect(screen.getByText("Plate")).toBeInTheDocument();
    expect(screen.getByText("PLATE-00")).toBeInTheDocument();
  });

  it("paginates: only pageSize rows show, and page buttons appear", () => {
    render(<DataTable columns={columns} rows={makeRows(25)} pageSize={10} rowKey={(r) => r.id} />);
    expect(screen.getAllByRole("row")).toHaveLength(1 + 10); // header row + 10 data rows
    expect(screen.getByRole("button", { name: "2" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "3" })).toBeInTheDocument();
  });

  it("clicking a page button shows that page's rows", () => {
    render(<DataTable columns={columns} rows={makeRows(25)} pageSize={10} rowKey={(r) => r.id} />);
    fireEvent.click(screen.getByRole("button", { name: "2" }));
    expect(screen.getByText("PLATE-10")).toBeInTheDocument();
    expect(screen.queryByText("PLATE-00")).not.toBeInTheDocument();
  });

  it("clicking a sortable header sorts the rows ascending, then descending on a second click", () => {
    const rows = [
      { id: "1", plate: "B", make: "X" },
      { id: "2", plate: "A", make: "Y" },
      { id: "3", plate: "C", make: "Z" },
    ];
    render(<DataTable columns={columns} rows={rows} rowKey={(r) => r.id} />);
    fireEvent.click(screen.getByText("Plate"));
    const cellsAsc = within(screen.getAllByRole("row")[1]).getByText("A");
    expect(cellsAsc).toBeInTheDocument();
    fireEvent.click(screen.getByText("Plate"));
    const cellsDesc = within(screen.getAllByRole("row")[1]).getByText("C");
    expect(cellsDesc).toBeInTheDocument();
  });

  it("does not attach a sort handler to a non-sortable column", () => {
    const nonSortableColumns: Column<Row>[] = [{ key: "plate", header: "Plate", render: (r) => r.plate }];
    render(<DataTable columns={nonSortableColumns} rows={makeRows(3)} rowKey={(r) => r.id} />);
    const header = screen.getByText("Plate");
    expect(header.closest("th")).not.toHaveClass("cursor-pointer");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test DataTable`
Expected: FAIL — `Cannot find module './DataTable'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/DataTable.tsx`:
```tsx
import { useMemo, useState } from "react";

export interface Column<T> {
  key: string;
  header: string;
  sortable?: boolean;
  sortValue?: (row: T) => string | number;
  render: (row: T) => React.ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  pageSize = 10,
  rowKey,
}: {
  columns: Column<T>[];
  rows: T[];
  pageSize?: number;
  rowKey: (row: T) => string;
}) {
  const [sort, setSort] = useState<{ key: string; direction: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(1);

  const sortedRows = useMemo(() => {
    if (!sort) return rows;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return rows;
    const sorted = [...rows].sort((a, b) => {
      const va = column.sortValue!(a);
      const vb = column.sortValue!(b);
      if (va < vb) return sort.direction === "asc" ? -1 : 1;
      if (va > vb) return sort.direction === "asc" ? 1 : -1;
      return 0;
    });
    return sorted;
  }, [rows, sort, columns]);

  const totalPages = Math.max(1, Math.ceil(sortedRows.length / pageSize));
  const pageRows = sortedRows.slice((page - 1) * pageSize, page * pageSize);

  function handleSort(column: Column<T>) {
    if (!column.sortable) return;
    setSort((prev) => {
      if (prev?.key !== column.key) return { key: column.key, direction: "asc" };
      return { key: column.key, direction: prev.direction === "asc" ? "desc" : "asc" };
    });
    setPage(1);
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-edge bg-surface shadow-raised">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                onClick={() => handleSort(column)}
                className={`border-b border-edge px-4 py-2.5 text-left text-[11px] font-semibold uppercase tracking-wide text-ink-3 ${
                  column.sortable ? "cursor-pointer select-none hover:text-ink" : ""
                }`}
              >
                {column.header}
                {sort?.key === column.key && <span className="ml-1">{sort.direction === "asc" ? "▲" : "▼"}</span>}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pageRows.map((row) => (
            <tr key={rowKey(row)} className="transition-colors duration-fast hover:bg-hover">
              {columns.map((column) => (
                <td key={column.key} className="border-b border-edge px-4 py-2.5 tabular-nums last:border-b-0">
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-1 py-3">
          {Array.from({ length: totalPages }, (_, i) => i + 1).map((p) => (
            <button
              key={p}
              onClick={() => setPage(p)}
              className={`h-7 w-7 rounded-lg text-xs transition-colors duration-fast ${
                p === page ? "bg-accent text-white" : "text-ink-2 hover:bg-hover"
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test DataTable`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/DataTable.tsx src/components/ui/DataTable.test.tsx
git commit -m "feat: add generic DataTable with sorting and pagination"
```

---

### Task 5: `EmptyState` visual redesign

**Files:**
- Modify: `apps/web/src/components/EmptyState.tsx`
- Test: `apps/web/src/components/EmptyState.test.tsx`

**Interfaces:**
- Consumes/Produces: unchanged public API (`{ message: string; action?: ReactNode }`) — `Cases.tsx` and `Vehicles.tsx` (the two existing call sites) need zero changes, exactly like Phase 20a's `Card` migration.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/EmptyState.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import EmptyState from "./EmptyState";

describe("EmptyState", () => {
  it("renders the message", () => {
    render(<EmptyState message="No cases yet" />);
    expect(screen.getByText("No cases yet")).toBeInTheDocument();
  });

  it("renders the action when given", () => {
    render(<EmptyState message="No cases yet" action={<button>New case</button>} />);
    expect(screen.getByRole("button", { name: "New case" })).toBeInTheDocument();
  });

  it("uses the design-system tokens, not the old slate/dashed classes", () => {
    render(<EmptyState message="No cases yet" />);
    const container = screen.getByText("No cases yet").closest("div[class]");
    expect(container?.className).not.toMatch(/slate|dashed/);
  });

  it("renders the illustration blob", () => {
    render(<EmptyState message="No cases yet" />);
    expect(document.querySelector('[data-testid="empty-state-blob"]')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test EmptyState`
Expected: FAIL — third and fourth assertions fail against the current slate/dashed implementation with no blob.

- [ ] **Step 3: Update the component**

Modify `apps/web/src/components/EmptyState.tsx` — replace its full contents:
```tsx
import type { ReactNode } from "react";

export default function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-4 rounded-2xl border border-edge bg-surface px-6 py-14 text-center">
      <div
        data-testid="empty-state-blob"
        className="h-16 w-16 animate-bounce rounded-full bg-accent-soft"
        style={{ animationDuration: "3s" }}
      />
      <p className="text-sm text-ink-2">{message}</p>
      {action}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test EmptyState`
Expected: `4 passed`.

- [ ] **Step 5: Run the full suite to confirm the two existing call sites (Cases.tsx, Vehicles.tsx) still work**

Run: `pnpm test`
Expected: all tests pass — this component has no dedicated tests in those two route files today, so this is confirming nothing else broke, not that those routes gained new coverage.

- [ ] **Step 6: Commit**

```bash
git add src/components/EmptyState.tsx src/components/EmptyState.test.tsx
git commit -m "feat: redesign EmptyState with design-system tokens and blob illustration"
```

---

### Task 6: Global loading bar (`LoadingBarProvider` / `useLoadingBar`)

**Files:**
- Create: `apps/web/src/lib/loadingBar.tsx`
- Test: `apps/web/src/lib/loadingBar.test.tsx`

**Interfaces:**
- Produces: `<LoadingBarProvider>{children}</LoadingBarProvider>` and `useLoadingBar(): { start: () => void; done: () => void }`. Task 9 wires `start()`/`done()` to real route-change events via `useLocation`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/loadingBar.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { LoadingBarProvider, useLoadingBar } from "./loadingBar";

function Trigger() {
  const { start, done } = useLoadingBar();
  return (
    <>
      <button onClick={start}>start</button>
      <button onClick={done}>done</button>
    </>
  );
}

describe("loading bar", () => {
  it("is not visible (0 width) before start is called", () => {
    render(
      <LoadingBarProvider>
        <Trigger />
      </LoadingBarProvider>
    );
    const bar = screen.getByTestId("loading-bar");
    expect(bar).toHaveStyle({ width: "0%" });
  });

  it("becomes visible with nonzero width after start", () => {
    render(
      <LoadingBarProvider>
        <Trigger />
      </LoadingBarProvider>
    );
    screen.getByText("start").click();
    const bar = screen.getByTestId("loading-bar");
    expect(bar).not.toHaveStyle({ width: "0%" });
  });

  it("goes to 100% width after done", () => {
    render(
      <LoadingBarProvider>
        <Trigger />
      </LoadingBarProvider>
    );
    screen.getByText("start").click();
    screen.getByText("done").click();
    const bar = screen.getByTestId("loading-bar");
    expect(bar).toHaveStyle({ width: "100%" });
  });

  it("throws a clear error if useLoadingBar is called outside the provider", () => {
    function Orphan() {
      useLoadingBar();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow("useLoadingBar must be used within a LoadingBarProvider");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test loadingBar`
Expected: FAIL — `Cannot find module './loadingBar'`.

- [ ] **Step 3: Implement the provider and hook**

Create `apps/web/src/lib/loadingBar.tsx`:
```tsx
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface LoadingBarContextValue {
  start: () => void;
  done: () => void;
}

const LoadingBarContext = createContext<LoadingBarContextValue | null>(null);

export function LoadingBarProvider({ children }: { children: ReactNode }) {
  const [width, setWidth] = useState(0);

  const start = useCallback(() => {
    setWidth(70);
  }, []);

  const done = useCallback(() => {
    setWidth(100);
    setTimeout(() => setWidth(0), 300);
  }, []);

  return (
    <LoadingBarContext.Provider value={{ start, done }}>
      {children}
      <div
        data-testid="loading-bar"
        className="fixed left-0 top-0 z-[200] h-[3px] bg-accent transition-[width] duration-base ease-out-token"
        style={{ width: `${width}%` }}
      />
    </LoadingBarContext.Provider>
  );
}

export function useLoadingBar(): LoadingBarContextValue {
  const ctx = useContext(LoadingBarContext);
  if (!ctx) throw new Error("useLoadingBar must be used within a LoadingBarProvider");
  return ctx;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test loadingBar`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/lib/loadingBar.tsx src/lib/loadingBar.test.tsx
git commit -m "feat: add LoadingBarProvider/useLoadingBar"
```

---

### Task 7: `CommandPalette`

**Files:**
- Create: `apps/web/src/components/ui/CommandPalette.tsx`
- Test: `apps/web/src/components/ui/CommandPalette.test.tsx`

**Interfaces:**
- Consumes: `useEscapeToClose` (Task 2).
- Produces: `<CommandPalette open: boolean onClose: () => void items: {label: string; onSelect: () => void}[] />`. Task 9 builds `items` from `NAV_ITEMS` (Task 1) plus `useNavigate()`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/CommandPalette.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { CommandPalette } from "./CommandPalette";

const items = [
  { label: "Go to Documents", onSelect: vi.fn() },
  { label: "Go to Cases", onSelect: vi.fn() },
  { label: "Go to Vehicles", onSelect: vi.fn() },
];

describe("CommandPalette", () => {
  it("renders nothing when closed", () => {
    render(<CommandPalette open={false} onClose={() => {}} items={items} />);
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
  });

  it("renders all items when open with an empty query", () => {
    render(<CommandPalette open onClose={() => {}} items={items} />);
    expect(screen.getByText("Go to Documents")).toBeInTheDocument();
    expect(screen.getByText("Go to Cases")).toBeInTheDocument();
    expect(screen.getByText("Go to Vehicles")).toBeInTheDocument();
  });

  it("filters items as you type", () => {
    render(<CommandPalette open onClose={() => {}} items={items} />);
    fireEvent.change(screen.getByPlaceholderText(/search/i), { target: { value: "vehicles" } });
    expect(screen.getByText("Go to Vehicles")).toBeInTheDocument();
    expect(screen.queryByText("Go to Documents")).not.toBeInTheDocument();
  });

  it("calls the matching item's onSelect and onClose when clicked", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} items={items} />);
    fireEvent.click(screen.getByText("Go to Cases"));
    expect(items[1].onSelect).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("ArrowDown moves the selection and Enter selects it", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} items={items} />);
    const input = screen.getByPlaceholderText(/search/i);
    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(items[1].onSelect).toHaveBeenCalledOnce();
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<CommandPalette open onClose={onClose} items={items} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test CommandPalette`
Expected: FAIL — `Cannot find module './CommandPalette'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/CommandPalette.tsx`:
```tsx
import { useEffect, useState } from "react";
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

interface CommandItem {
  label: string;
  onSelect: () => void;
}

export function CommandPalette({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: CommandItem[];
}) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);

  useEscapeToClose(open, onClose);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
    }
  }, [open]);

  if (!open) return null;

  const filtered = items.filter((item) => item.label.toLowerCase().includes(query.toLowerCase()));

  function runSelection(item: CommandItem) {
    item.onSelect();
    onClose();
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      const item = filtered[selectedIndex];
      if (item) runSelection(item);
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-50 bg-[#0D0C1A]/35 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed left-1/2 top-[18%] z-[51] w-[min(520px,90vw)] -translate-x-1/2 overflow-hidden rounded-2xl border border-edge bg-surface shadow-overlay">
        <input
          autoFocus
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setSelectedIndex(0);
          }}
          onKeyDown={handleKeyDown}
          placeholder="Search documents, cases, vehicles…"
          className="w-full border-b border-edge bg-transparent px-4 py-4 text-sm text-ink outline-none"
        />
        <div>
          {filtered.map((item, index) => (
            <div
              key={item.label}
              onClick={() => runSelection(item)}
              onMouseEnter={() => setSelectedIndex(index)}
              className={`cursor-pointer px-4 py-2.5 text-sm transition-colors duration-fast ${
                index === selectedIndex ? "bg-hover text-ink" : "text-ink-2"
              }`}
            >
              {item.label}
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test CommandPalette`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/CommandPalette.tsx src/components/ui/CommandPalette.test.tsx
git commit -m "feat: add CommandPalette (filtering, keyboard navigation)"
```

---

### Task 8: `ShortcutsSheet`

**Files:**
- Create: `apps/web/src/components/ui/ShortcutsSheet.tsx`
- Test: `apps/web/src/components/ui/ShortcutsSheet.test.tsx`

**Interfaces:**
- Consumes: `useEscapeToClose` (Task 2).
- Produces: `<ShortcutsSheet open: boolean onClose: () => void />`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/ShortcutsSheet.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ShortcutsSheet } from "./ShortcutsSheet";

describe("ShortcutsSheet", () => {
  it("renders nothing when closed", () => {
    render(<ShortcutsSheet open={false} onClose={() => {}} />);
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("lists the known shortcuts when open", () => {
    render(<ShortcutsSheet open onClose={() => {}} />);
    expect(screen.getByText("Keyboard shortcuts")).toBeInTheDocument();
    expect(screen.getByText("Open command palette")).toBeInTheDocument();
    expect(screen.getByText("⌘K")).toBeInTheDocument();
    expect(screen.getByText("Show this sheet")).toBeInTheDocument();
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    render(<ShortcutsSheet open onClose={onClose} />);
    fireEvent.click(screen.getByTestId("shortcuts-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(<ShortcutsSheet open onClose={onClose} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test ShortcutsSheet`
Expected: FAIL — `Cannot find module './ShortcutsSheet'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/ShortcutsSheet.tsx`:
```tsx
import { useEscapeToClose } from "../../hooks/useEscapeToClose";

const SHORTCUTS: { label: string; keys: string }[] = [
  { label: "Open command palette", keys: "⌘K" },
  { label: "Show this sheet", keys: "?" },
  { label: "Close any overlay", keys: "Esc" },
  { label: "Toggle dark mode", keys: "⌘D" },
];

export function ShortcutsSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEscapeToClose(open, onClose);

  if (!open) return null;

  return (
    <>
      <div data-testid="shortcuts-backdrop" className="fixed inset-0 z-50 bg-[#0D0C1A]/35 backdrop-blur-sm" onClick={onClose} />
      <div className="fixed left-1/2 top-[15%] z-[51] w-[min(420px,90vw)] -translate-x-1/2 overflow-hidden rounded-2xl border border-edge bg-surface shadow-overlay">
        <div className="border-b border-edge px-5 py-4 text-sm font-semibold text-ink">Keyboard shortcuts</div>
        {SHORTCUTS.map((shortcut) => (
          <div key={shortcut.label} className="flex items-center justify-between px-5 py-2.5 text-sm text-ink-2">
            <span>{shortcut.label}</span>
            <kbd className="rounded-md bg-accent-soft px-1.5 py-0.5 text-xs text-accent">{shortcut.keys}</kbd>
          </div>
        ))}
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test ShortcutsSheet`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/ShortcutsSheet.tsx src/components/ui/ShortcutsSheet.test.tsx
git commit -m "feat: add ShortcutsSheet"
```

---

### Task 9: `CommandCenter` integration + loading bar wiring + manual verification

**Files:**
- Create: `apps/web/src/components/CommandCenter.tsx`
- Test: `apps/web/src/components/CommandCenter.test.tsx`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: `NAV_ITEMS` (Task 1), `CommandPalette` (Task 7), `ShortcutsSheet` (Task 8), `useLoadingBar`/`LoadingBarProvider` (Task 6), `react-router-dom`'s `useNavigate`/`useLocation`.
- Produces: `<CommandCenter />` — a single component owning global `⌘K`/`?`/dark-mode-shortcut keyboard listening and rendering whichever overlay is active, plus a location-change-driven loading bar flash. Mounted once in `App.tsx`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/CommandCenter.test.tsx`:
```tsx
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { CommandCenter } from "./CommandCenter";

afterEach(cleanup);

function renderWithRouter() {
  return render(
    <MemoryRouter>
      <CommandCenter />
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
        <input aria-label="some field" />
        <CommandCenter />
      </MemoryRouter>
    );
    screen.getByLabelText("some field").focus();
    fireEvent.keyDown(document.activeElement!, { key: "?" });
    expect(screen.queryByText("Keyboard shortcuts")).not.toBeInTheDocument();
  });

  it("lists every NAV_ITEMS entry as a palette item, prefixed with 'Go to '", () => {
    renderWithRouter();
    fireEvent.keyDown(document, { key: "k", metaKey: true });
    expect(screen.getByText("Go to Documents")).toBeInTheDocument();
    expect(screen.getByText("Go to Vehicles")).toBeInTheDocument();
    expect(screen.getByText("Go to Settings")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test CommandCenter`
Expected: FAIL — `Cannot find module './CommandCenter'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/CommandCenter.tsx`:
```tsx
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { NAV_ITEMS } from "../lib/navigation";
import { CommandPalette } from "./ui/CommandPalette";
import { ShortcutsSheet } from "./ui/ShortcutsSheet";
import { useDarkMode } from "../hooks/useDarkMode";

type OverlayState = "none" | "palette" | "shortcuts";

export function CommandCenter() {
  const [overlay, setOverlay] = useState<OverlayState>("none");
  const navigate = useNavigate();
  const { toggle: toggleDarkMode } = useDarkMode();

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      const isTyping = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA";

      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOverlay((prev) => (prev === "palette" ? "none" : "palette"));
      } else if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "d") {
        event.preventDefault();
        toggleDarkMode();
      } else if (event.key === "?" && !isTyping) {
        event.preventDefault();
        setOverlay((prev) => (prev === "shortcuts" ? "none" : "shortcuts"));
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [toggleDarkMode]);

  const items = NAV_ITEMS.map((item) => ({
    label: `Go to ${item.label}`,
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

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test CommandCenter`
Expected: `5 passed`.

- [ ] **Step 5: Wire `LoadingBarProvider` and a route-change flash, and mount `CommandCenter`, in App.tsx**

Modify `apps/web/src/App.tsx` — add these imports near the existing ones:
```tsx
import { ToastProvider } from "./lib/toast";
import { LoadingBarProvider, useLoadingBar } from "./lib/loadingBar";
import { CommandCenter } from "./components/CommandCenter";
```
Add this small route-change component in the same file, right after the imports and before `export default function App()`:
```tsx
function RouteChangeLoadingBar() {
  const location = useLocation();
  const { start, done } = useLoadingBar();
  const [lastPath, setLastPath] = useState(location.pathname);

  useEffect(() => {
    if (location.pathname === lastPath) return;
    setLastPath(location.pathname);
    start();
    const timer = setTimeout(done, 250);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  return null;
}
```
This needs two more imports added alongside the ones above: `useLocation` from `"react-router-dom"` (already imports `Route`/`Routes` from there — extend that same import line to include `useLocation`) and `useEffect`, `useState` from `"react"` (new import line, since `App.tsx` currently imports nothing from `"react"` directly).

Then wrap `<Layout>` with `<LoadingBarProvider>` (inside `<ToastProvider>`, since toasts and the loading bar are independent chrome), and mount `<CommandCenter />` and `<RouteChangeLoadingBar />` as siblings of `<Layout>` inside the router context:
```tsx
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <LoadingBarProvider>
            <CommandCenter />
            <RouteChangeLoadingBar />
            <Layout>
              <Routes>
                {/* ...unchanged, every existing <Route> stays exactly as-is... */}
              </Routes>
            </Layout>
          </LoadingBarProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
```
`CommandCenter` and `RouteChangeLoadingBar` must be *inside* `<BrowserRouter>` (they use `useNavigate`/`useLocation`) but can be siblings of, not children of, `<Layout>`.

- [ ] **Step 6: Run the full test suite**

Run: `pnpm test`
Expected: all tests pass (Phase 20a's 43 plus this plan's new ones).

- [ ] **Step 7: Verify the build compiles (Tailwind/CSS portion)**

Run: `npx vite build`
Expected: succeeds — same `tsc`-bypassing verification approach as Phase 20a, since the pre-existing `apps/mobile` type conflict (documented in PR #28) still blocks the full `pnpm build`.

- [ ] **Step 8: Manually verify in a real browser**

Same approach as Phase 20a Task 11 — SSH-tunnel the already-running `docker compose` `web` (port 5173) and `api` (port 8000) containers to two free local ports (check `lsof -i :5173` and `lsof -i :8000` locally first; if either is occupied by something else, as happened during Phase 20a, tunnel to different local ports instead and temporarily add that origin to the API's CORS `allow_origins` list in `services/api/src/api/main.py`, reverting it immediately after — exactly as documented in this project's own history for this exact QA scenario).

Once connected, log in and confirm, for real, in the browser:
- Clicking sidebar nav items now shows the active-item pill sliding smoothly between them (not just snapping)
- Pressing `⌘K` opens the command palette; typing filters the list; arrow keys + Enter navigate
- Pressing `?` (outside any input) opens the shortcuts sheet; pressing `?` while a search box is focused does *not* open it
- `Escape` closes whichever overlay is open
- Navigating between pages (e.g. Documents → Cases) shows a brief loading bar flash at the top of the viewport
- Visit `/cases` or `/vehicles` with no data (or check the existing "Smith v. Jones" test-fixture case is still shown) — the empty/populated state area should show the redesigned rounded card styling with the bouncing blob when genuinely empty

- [ ] **Step 9: Commit**

```bash
git add src/components/CommandCenter.tsx src/components/CommandCenter.test.tsx src/App.tsx
git commit -m "feat: wire CommandCenter and route-change loading bar into the app shell"
```

---

## Self-Review

**Spec coverage:** sliding nav-pill sidebar → Task 1. Detail drawer with tabs → Task 3. Command palette (filtering, keyboard nav) → Task 7. Keyboard shortcuts sheet → Task 8. Global loading bar → Task 6, wired to real navigation in Task 9. Sortable data table + pagination → Task 4. Empty-state redesign → Task 5. Shared Escape-handling (a design-system-hygiene improvement over the prototype, which just reused one DOM backdrop element informally) → Task 2. Everything else from the spec (bulk selection, filter chips, inline editing, split view, and applying any of this to the 9 real pages) is explicitly out of scope — Phase 20c.

**Placeholder scan:** no TBD/TODO; every step has complete, real code.

**Type consistency:** `Column<T>` in Task 4 is used identically in its test and implementation. `DrawerTab`'s `{id, label, content}` shape matches between Task 3's test and implementation. `CommandItem`'s `{label, onSelect}` shape matches between Task 7's test/implementation and Task 9's `CommandCenter` usage (built from `NAV_ITEMS`). `useEscapeToClose(active, onClose)`'s signature (Task 2) is used identically by `Modal` (refactored in Task 2), `Drawer` (Task 3), `CommandPalette` (Task 7), and `ShortcutsSheet` (Task 8) — same argument order and names throughout.
