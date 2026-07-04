# Phase 17c — Manager Agent / Assistant UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Phase 11 Manager Agent (`POST /manager/ask`) a UI: a new `/assistant` page, distinct from the existing `/chat` page.

**Architecture:** Pure frontend addition — no backend changes, since `POST /manager/ask` already exists and is fully functional. One new `api.ts` interface/function, one new page, one new sidebar nav item, built on the Phase 17a shell.

**Tech Stack:** React + TypeScript + Vite + Tailwind (existing stack, no new dependencies).

## Global Constraints

- This sub-phase depends on Phase 17a having merged (`Layout`/`Sidebar` must exist in `main`). It does not depend on 17b.
- No new frontend test pattern — verification is `tsc -b` typecheck plus a live browser check, matching 17a/17b.

---

### Task 1: `api.ts` additions for the Manager Agent

**Files:**
- Modify: `apps/web/src/lib/api.ts`

**Interfaces:**
- Produces: `AskResponse { answer: string; tool_called: string | null }` and `askManager(message: string): Promise<AskResponse>` calling `POST /manager/ask`. Consumed by `Assistant.tsx` in Task 2.

- [ ] **Step 1: Append to `apps/web/src/lib/api.ts`**

```ts
export interface AskResponse {
  answer: string;
  tool_called: string | null;
}

export function askManager(message: string): Promise<AskResponse> {
  return request<AskResponse>("/manager/ask", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 3: Run the existing frontend test suite**

Run: `cd /opt/collabrains && docker compose exec web pnpm test`
Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/lib/api.ts
git commit -m "Phase 17c task 1: api.ts additions for the Manager Agent"
```

---

### Task 2: `Assistant.tsx`

**Files:**
- Create: `apps/web/src/routes/Assistant.tsx`

**Interfaces:**
- Consumes: `askManager`, `AskResponse` (Task 1).
- Produces: `export default function Assistant()`, wired into routing in Task 3.

- [ ] **Step 1: Write `Assistant.tsx`**

```tsx
import { useState, type FormEvent } from "react";
import { ApiError, askManager } from "../lib/api";

interface DisplayTurn {
  role: "user" | "assistant";
  content: string;
  toolCalled?: string | null;
}

export default function Assistant() {
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) return;

    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setError(null);
    setSending(true);

    try {
      const response = await askManager(message);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, toolCalled: response.tool_called }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Assistant request failed");
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Assistant</h1>

      <div className="flex flex-col gap-3">
        {turns.length === 0 && (
          <p className="text-sm text-slate-500">
            Ask the assistant to do something — it can choose and call tools on its own, unlike AI Chat which only
            answers from your documents.
          </p>
        )}
        {turns.map((turn, i) => (
          <div
            key={i}
            className={
              turn.role === "user"
                ? "self-end max-w-[80%] rounded-lg bg-slate-900 px-4 py-2 text-sm text-white"
                : "max-w-[80%] rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm"
            }
          >
            <p className="whitespace-pre-wrap">{turn.content}</p>
            {turn.toolCalled && (
              <div className="mt-2 border-t border-slate-100 pt-2 text-xs text-slate-500">
                via: {turn.toolCalled}
              </div>
            )}
          </div>
        ))}
        {sending && <p className="text-sm text-slate-400">Thinking…</p>}
        {error && <p className="text-sm text-red-600">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask the assistant…"
          disabled={sending}
          className="w-full rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          Send
        </button>
      </form>
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
git add apps/web/src/routes/Assistant.tsx
git commit -m "Phase 17c task 2: Assistant page"
```

---

### Task 3: Wire into Sidebar and routing

**Files:**
- Modify: `apps/web/src/components/Sidebar.tsx`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: `Assistant` (Task 2).

- [ ] **Step 1: Add the "Assistant" nav item to `Sidebar.tsx`**

Change `NAV_ITEMS` in `apps/web/src/components/Sidebar.tsx` (adding after "Cases", which 17b already added):

```ts
const NAV_ITEMS = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
  { to: "/cases", label: "Cases" },
  { to: "/assistant", label: "Assistant" },
];
```

- [ ] **Step 2: Add the route to `App.tsx`**

Add the import (after the `CaseDetail` import, which 17b already added):

```tsx
import CaseDetail from "./routes/CaseDetail";
import Assistant from "./routes/Assistant";
```

Add the route (after the `/cases/:id` route, before the `*` catch-all):

```tsx
            <Route
              path="/assistant"
              element={
                <ProtectedRoute>
                  <Assistant />
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
git commit -m "Phase 17c task 3: wire Assistant into sidebar and routing"
```

---

### Task 4: ADR, rebuild, live verification, PR

**Files:**
- Create: `docs/adr/0034-phase17c-assistant-ui.md`

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0034-phase17c-assistant-ui.md`, same style as `docs/adr/0025-phase10-knowledge-graph-2.md`. Cover: why `/assistant` is a separate page rather than a mode toggle inside `/chat` (avoids conflating two functionally different backend capabilities — RAG+citations+memory vs. single-round tool-calling); that `/manager/ask` is stateless (no history param) so the local turn list exists only for on-screen readability, never resent to the backend; the `tool_called` badge making the Manager Agent's tool selection observable rather than hidden.

- [ ] **Step 2: Rebuild the production bundle**

Run: `cd /opt/collabrains && docker compose exec -e VITE_API_URL='' web pnpm build`
Expected: builds successfully with no errors.

- [ ] **Step 3: Live verification**

Use the Playwright MCP against `https://v78281.1blu.de`: log in, click "Assistant" in the sidebar, send a message that should trigger a tool call (e.g. something that maps to an existing registered tool like document search — check `services/api/src/api/tools.py` for exactly which tools are registered if unsure what will trigger one), confirm the answer renders and, if a tool was called, the `via: <tool_name>` badge appears underneath.

- [ ] **Step 4: Commit the ADR, push, open the draft PR**

```bash
cd /opt/collabrains
git add docs/adr/0034-phase17c-assistant-ui.md
git commit -m "Phase 17c: Assistant UI"
git push -u origin phase-17c-assistant-ui
gh pr create --draft --base main --head phase-17c-assistant-ui \
  --title "Phase 17c: Manager Agent / Assistant UI" \
  --body "See docs/superpowers/specs/2026-07-04-frontend-catchup-design.md for the full Phase 17 design and docs/adr/0034-phase17c-assistant-ui.md for this sub-phase's decisions. Adds a new /assistant page for the Phase 11 Manager Agent, wired into the Phase 17a sidebar shell. No backend changes -- POST /manager/ask already existed."
```

## Self-Review Notes

**Spec coverage**: covers every item in the spec's "Architecture: Manager Agent / Assistant UI (17c)" section.

**Placeholder scan**: no TBD/TODO; every step has complete code or an exact command.

**Type consistency**: `AskResponse`'s `tool_called: string | null` (Task 1) matches exactly how `Assistant.tsx` (Task 2) reads `response.tool_called` into `DisplayTurn.toolCalled`.
