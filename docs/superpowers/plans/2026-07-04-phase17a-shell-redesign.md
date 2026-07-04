# Phase 17a — Sidebar Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current top-nav app shell with a persistent left sidebar, and extract two shared UI primitives (`Card`, `EmptyState`) that 17b/17c/17d will build their pages on top of.

**Architecture:** `App.tsx` shrinks from an all-in-one routing+layout component to a pure route table; a new `Layout.tsx` composes a new `Sidebar.tsx` (nav + user control) around the routed content. `Card`/`EmptyState` are small, standalone presentational components with no dependents yet in this sub-phase — they exist so 17b/17c/17d can import them immediately.

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind (existing stack, no new dependencies). No test framework exists for React components in this codebase (only `vitest` unit tests on the plain-function `api.ts` request layer) — this plan does not introduce one; verification is `tsc -b` typecheck per task plus a final live browser check, matching this project's established frontend verification practice (Phases 5a–5c).

## Global Constraints

- No new npm dependencies — Tailwind classes only, matching every existing page.
- Sidebar nav items in this sub-phase are only the 5 that already exist today (Documents, AI Chat, Legal Draft, Tasks, Entities) — do NOT add Cases/Assistant/Settings links yet, since those pages don't exist until 17b/17c/17d merge. Adding them now would ship dead links.
- Preserve current behavior exactly where not explicitly changed: the sidebar renders on every route including `/login` (matching today's header, which always renders regardless of auth state — `HeaderUser`/the sidebar's user block simply renders nothing when there's no user).
- The `web` container runs `pnpm dev` with a live volume mount (`./apps/web:/app/apps/web`) — file edits take effect immediately for local dev verification at `http://<server>:5173` (bound to `127.0.0.1` only). The **public** domain (`https://v78281.1blu.de`) is served by Caddy directly from a separate static build (`apps/web/dist`, bind-mounted read-only) — it does NOT pick up changes until `docker compose exec -e VITE_API_URL='' web pnpm build` is re-run.

---

### Task 1: `Card` and `EmptyState` primitives

**Files:**
- Create: `apps/web/src/components/Card.tsx`
- Create: `apps/web/src/components/EmptyState.tsx`

**Interfaces:**
- Produces: `export default function Card({ children, className }: { children: ReactNode; className?: string })` and `export default function EmptyState({ message, action }: { message: string; action?: ReactNode })` — both used by name in 17b's Cases/CaseDetail pages, not consumed by anything in this sub-phase.

- [ ] **Step 1: Write `Card.tsx`**

```tsx
import type { ReactNode } from "react";

export default function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded border border-slate-200 bg-white p-4 ${className}`}>{children}</div>;
}
```

- [ ] **Step 2: Write `EmptyState.tsx`**

```tsx
import type { ReactNode } from "react";

export default function EmptyState({ message, action }: { message: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded border border-dashed border-slate-300 px-6 py-12 text-center">
      <p className="text-sm text-slate-500">{message}</p>
      {action}
    </div>
  );
}
```

- [ ] **Step 3: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0 (both files are self-contained with no imports beyond `react`, so this should never fail, but confirms the new files parse and typecheck cleanly before building on them).

- [ ] **Step 4: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/components/Card.tsx apps/web/src/components/EmptyState.tsx
git commit -m "Phase 17a task 1: Card and EmptyState shared primitives"
```

---

### Task 2: `Sidebar` component

**Files:**
- Create: `apps/web/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `useAuth()` from `apps/web/src/lib/auth.tsx` (exact shape: `{ user: UserOut | null; loading: boolean; login: (...) => Promise<void>; logout: () => void }` — only `user` and `logout` are used here).
- Produces: `export default function Sidebar()` — a self-contained component with no props, consumed by `Layout` in Task 3.

- [ ] **Step 1: Write `Sidebar.tsx`**

```tsx
import { NavLink } from "react-router-dom";
import { useAuth } from "../lib/auth";

const NAV_ITEMS = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
];

export default function Sidebar() {
  const { user, logout } = useAuth();

  return (
    <aside className="flex h-screen w-56 shrink-0 flex-col justify-between border-r border-slate-200 bg-white px-4 py-6">
      <div className="flex flex-col gap-6">
        <span className="text-lg font-semibold">CollaBrains</span>
        <nav className="flex flex-col gap-1 text-sm">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `rounded px-3 py-2 ${
                  isActive ? "bg-slate-100 font-medium text-slate-900" : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </div>
      {user && (
        <div className="flex flex-col gap-2 border-t border-slate-200 pt-4 text-sm">
          <span className="text-slate-500">{user.display_name}</span>
          <button onClick={logout} className="text-left text-slate-500 hover:text-slate-900">
            Sign out
          </button>
        </div>
      )}
    </aside>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/components/Sidebar.tsx
git commit -m "Phase 17a task 2: Sidebar component"
```

---

### Task 3: `Layout` component

**Files:**
- Create: `apps/web/src/components/Layout.tsx`

**Interfaces:**
- Consumes: `Sidebar` (Task 2, no props).
- Produces: `export default function Layout({ children }: { children: ReactNode })`, consumed by `App.tsx` in Task 4.

- [ ] **Step 1: Write `Layout.tsx`**

```tsx
import type { ReactNode } from "react";
import Sidebar from "./Sidebar";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-slate-50 text-slate-900">
      <Sidebar />
      <main className="flex-1 overflow-y-auto px-8 py-8">{children}</main>
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
git add apps/web/src/components/Layout.tsx
git commit -m "Phase 17a task 3: Layout component"
```

---

### Task 4: Refactor `App.tsx` into a pure route table

**Files:**
- Modify: `apps/web/src/App.tsx` (full rewrite — the whole file is small enough that a full rewrite is clearer than a diff)

**Interfaces:**
- Consumes: `Layout` (Task 3).
- Produces: no exports besides the default `App` component (unchanged from before — nothing outside this file imports from it).

- [ ] **Step 1: Replace the full contents of `apps/web/src/App.tsx`**

```tsx
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider, ProtectedRoute } from "./lib/auth";
import Layout from "./components/Layout";
import Login from "./routes/Login";
import Workspace from "./routes/Workspace";
import DocumentDetail from "./routes/DocumentDetail";
import Chat from "./routes/Chat";
import Legal from "./routes/Legal";
import Tasks from "./routes/Tasks";
import Entities from "./routes/Entities";
import EntityGraph from "./routes/EntityGraph";
import NotFound from "./routes/NotFound";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Layout>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <Workspace />
                </ProtectedRoute>
              }
            />
            <Route
              path="/documents/:id"
              element={
                <ProtectedRoute>
                  <DocumentDetail />
                </ProtectedRoute>
              }
            />
            <Route
              path="/chat"
              element={
                <ProtectedRoute>
                  <Chat />
                </ProtectedRoute>
              }
            />
            <Route
              path="/legal"
              element={
                <ProtectedRoute>
                  <Legal />
                </ProtectedRoute>
              }
            />
            <Route
              path="/tasks"
              element={
                <ProtectedRoute>
                  <Tasks />
                </ProtectedRoute>
              }
            />
            <Route
              path="/entities"
              element={
                <ProtectedRoute>
                  <Entities />
                </ProtectedRoute>
              }
            />
            <Route
              path="/entities/:id"
              element={
                <ProtectedRoute>
                  <EntityGraph />
                </ProtectedRoute>
              }
            />
            <Route path="*" element={<NotFound />} />
          </Routes>
        </Layout>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0. This is the step most likely to catch a real mistake (e.g. a missed import, an unclosed `ProtectedRoute` tag) since it's a full-file rewrite.

- [ ] **Step 3: Run the existing frontend test suite**

Run: `cd /opt/collabrains && docker compose exec web pnpm test`
Expected: `5 passed` (the existing `api.test.ts` suite — this task doesn't touch `api.ts`, so this just confirms the rewrite didn't break anything unrelated via a shared import path).

- [ ] **Step 4: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/App.tsx
git commit -m "Phase 17a task 4: App.tsx reduced to a pure route table"
```

---

### Task 5: Rebuild, live verification, ADR, PR

**Files:**
- Create: `docs/adr/0032-phase17a-sidebar-shell.md`

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0032-phase17a-sidebar-shell.md` following the exact style of `docs/adr/0025-phase10-knowledge-graph-2.md` (Status/Context/Decision/Consequences sections). Content to cover: the sidebar-over-topnav decision and why (explicitly requested during brainstorming, aiming for an enterprise-SaaS feel); the `Sidebar`/`Layout`/`App` split and why (`App.tsx` should only own routing, matching this codebase's one-responsibility-per-file convention); that `Card`/`EmptyState` exist now with no consumers yet (17b/c/d will use them) — a deliberate small exception to the "don't build things nothing uses yet" bias, justified because this sub-phase's whole purpose is to prepare the shell for the next three; and that Cases/Assistant/Settings nav links are deliberately NOT added in this sub-phase (would be dead links until 17b/c/d ship).

- [ ] **Step 2: Rebuild the production bundle**

Run: `cd /opt/collabrains && docker compose exec -e VITE_API_URL='' web pnpm build`
Expected: builds successfully, ending in a `dist/` output summary with no errors. This regenerates `apps/web/dist`, which Caddy serves directly to the public domain.

- [ ] **Step 3: Live verification against the public domain**

Run these curl checks:
```bash
curl -s -o /dev/null -w '%{http_code}\n' https://v78281.1blu.de/
curl -s -o /dev/null -w '%{http_code}\n' https://v78281.1blu.de/tasks
```
Expected: both `200`.

Then use the Playwright MCP against `https://v78281.1blu.de` to confirm visually: log in, see the left sidebar with 5 nav items (Documents/AI Chat/Legal Draft/Tasks/Entities) and the display name + Sign out pinned at the bottom, click through all 5 nav items and confirm each page still renders its existing content correctly inside the new shell, and confirm Sign out still works (returns to `/login`).

- [ ] **Step 4: Commit the ADR, push, open the draft PR**

```bash
cd /opt/collabrains
git add docs/adr/0032-phase17a-sidebar-shell.md
git commit -m "Phase 17a: sidebar shell redesign"
git push -u origin phase-17a-sidebar-shell
gh pr create --draft --base main --head phase-17a-sidebar-shell \
  --title "Phase 17a: Sidebar shell redesign" \
  --body "See docs/superpowers/specs/2026-07-04-frontend-catchup-design.md for the full Phase 17 design and docs/adr/0032-phase17a-sidebar-shell.md for this sub-phase's decisions. Replaces the top nav with a persistent left sidebar; extracts Card/EmptyState primitives for 17b/17c/17d to build on. No new nav items for Cases/Assistant/Settings yet -- those ship with their own sub-phases."
```

## Self-Review Notes

**Spec coverage**: this plan covers every item the spec's "Architecture: Shell Redesign (17a)" section names — `Sidebar`/`Layout` extraction, flat nav (scoped to the 5 currently-real items, with the 3 future ones explicitly deferred per the reasoning above), user control moved to sidebar bottom, top header removed, and the two shared primitives. The spec's `Card`/`EmptyState` primitives have no consumer in this sub-phase by design (17b consumes them) — noted explicitly in Task 5's ADR guidance so this isn't mistaken for dead code later.

**Placeholder scan**: no TBD/TODO; every step has complete, real code or an exact command.

**Type consistency**: `Layout`'s `{ children: ReactNode }` prop matches exactly how `App.tsx` (Task 4) invokes it (`<Layout><Routes>...</Routes></Layout>`); `Sidebar` takes no props anywhere it's referenced (Task 2's definition, Task 3's usage). `Card`/`EmptyState`'s signatures are defined here for 17b's plan to consume verbatim later.
