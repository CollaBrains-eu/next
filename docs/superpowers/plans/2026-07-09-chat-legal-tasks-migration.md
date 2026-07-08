# Phase 20d4: Chat, Legal & Tasks Page Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `Chat.tsx`, `Legal.tsx`, and `Tasks.tsx` from raw Tailwind slate classes to the violet design system, continuing Phase 20's page-by-page rollout after Documents (20d1), Cases/Vehicles (20d2), and Entities/EntityGraph (20d3). This is also the first real-page use of the `Checkbox` primitive (Phase 20a) and `useLoadingBar` (Phase 20b) — both built but never wired to a real page until now.

**Architecture:** Data-fetching logic is untouched. Markup swaps raw classes/buttons for `Button`, `Checkbox`, and token classes. `Chat.tsx` and `Legal.tsx` both call `useLoadingBar()`'s `start()`/`done()` around their AI request (`chat()`, `legalDraft()`) — the spec (PR #26) explicitly calls out AI response times of ~15-20s reading as a hang as the reason the loading bar interaction pattern was validated in Phase 20c.

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4 (violet token theme), Vitest 3, @testing-library/react, react-router-dom.

## Global Constraints

- Do not modify `apps/web/src/lib/api.ts` — only real, existing exports may be used (`ChatTurn`, `ChatResponse`, `Citation`, `chat`, `DraftResponse`, `legalDraft`, `listDocuments`, `DocumentOut`, `TaskOut`, `listTasks`, `updateTaskStatus`, `ApiError`).
- `Tasks.tsx`'s done-toggle checkbox stays a hand-styled `<input type="checkbox">` with `accent-accent` (not the `Checkbox` primitive) — the primitive's API takes a single string `label`, but this checkbox sits beside a multi-line rich block (title, description, due date, assignee, source-document link), not a simple label string. Forcing that content into `Checkbox`'s `label` prop would mean passing JSX where the primitive expects a string, or restructuring the primitive's API for one consumer — out of scope. Same deliberate-deviation precedent as 20d2's hand-styled `<select>` in CaseDetail.
- `Legal.tsx`'s document-scope list DOES fit `Checkbox` exactly (`label: doc.title`, `checked: selectedIds.has(doc.id)`, `onChange: () => toggleDocument(doc.id)`) — use the primitive there.
- Verify each task with `npx vite build` (from `apps/web`) + `pnpm test` (not full `pnpm build` — pre-existing `apps/mobile`/`apps/web` `@types/react` hoisting conflict, documented in PR #28, remains out of scope).
- Branch this plan's implementation off `phase-20d4-plan-chat-legal-tasks-migration` (this plan's own branch), which itself sits on `phase-20d3-entities-migration` — nothing is merged to `main` yet.
- Commit after each task. Push and open a PR against `main` at the end (do not merge).

---

### Task 1: Migrate Chat.tsx

**Files:**
- Modify: `apps/web/src/routes/Chat.tsx`
- Test: `apps/web/src/routes/Chat.test.tsx` (new)

**Interfaces:**
- Consumes: `Button` (`import { Button } from "../components/ui/Button"`), `useLoadingBar` (`import { useLoadingBar } from "../lib/loadingBar"`, returns `{ start(): void, done(): void }`), `ApiError`/`chat`/`ChatTurn`/`Citation` from `../lib/api` (unchanged). Test must wrap in `LoadingBarProvider` (`import { LoadingBarProvider } from "../lib/loadingBar"`) since `useLoadingBar` throws outside it.
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Chat.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Chat from "./Chat";
import { LoadingBarProvider } from "../lib/loadingBar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    chat: vi.fn(),
  };
});

function renderPage() {
  return render(
    <MemoryRouter>
      <LoadingBarProvider>
        <Chat />
      </LoadingBarProvider>
    </MemoryRouter>
  );
}

describe("Chat", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.chat).mockResolvedValue({
      answer: "The contract expires in 2027.",
      citations: [{ marker: 1, document_id: "d1", document_title: "Lease Agreement", chunk_id: "c1" }],
    });
  });

  it("shows the hint text before any messages are sent", () => {
    renderPage();
    expect(screen.getByText(/Ask a question about your documents/)).toBeInTheDocument();
  });

  it("sends a message and renders the assistant reply with a citation link", async () => {
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "When does it expire?" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("The contract expires in 2027.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1] Lease Agreement" })).toHaveAttribute("href", "/documents/d1");
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.chat).mockRejectedValue(new api.ApiError(500, "Chat boom"));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(await screen.findByText("Chat boom")).toBeInTheDocument();
  });

  it("disables the Send button while a request is in flight", async () => {
    let resolveChat: (v: api.ChatResponse) => void = () => {};
    vi.mocked(api.chat).mockReturnValue(new Promise((resolve) => { resolveChat = resolve; }));
    renderPage();
    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.getByRole("button", { name: "Send" })).toBeDisabled();
    resolveChat({ answer: "done", citations: [] });
    await waitFor(() => expect(screen.getByRole("button", { name: "Send" })).not.toBeDisabled());
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Chat.test.tsx`
Expected: FAIL (file compiles against the current component; confirms the test harness catches drift once Step 3 rewrites the component).

- [ ] **Step 3: Rewrite Chat.tsx**

```tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, chat, type ChatTurn, type Citation } from "../lib/api";
import { Button } from "../components/ui/Button";
import { useLoadingBar } from "../lib/loadingBar";

interface DisplayTurn extends ChatTurn {
  citations?: Citation[];
}

export default function Chat() {
  const [turns, setTurns] = useState<DisplayTurn[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { start, done } = useLoadingBar();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const message = input.trim();
    if (!message || sending) return;

    const history = turns.map(({ role, content }) => ({ role, content }));
    setTurns((prev) => [...prev, { role: "user", content: message }]);
    setInput("");
    setError(null);
    setSending(true);
    start();

    try {
      const response = await chat(message, history);
      setTurns((prev) => [...prev, { role: "assistant", content: response.answer, citations: response.citations }]);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Chat request failed");
    } finally {
      setSending(false);
      done();
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">AI Chat</h1>

      <div className="flex flex-col gap-3">
        {turns.length === 0 && (
          <p className="text-sm text-ink-2">
            Ask a question about your documents. Answers are grounded only in retrieved content and cite sources.
          </p>
        )}
        {turns.map((turn, i) => (
          <div
            key={i}
            className={
              turn.role === "user"
                ? "self-end max-w-[80%] rounded-2xl bg-accent px-4 py-2 text-sm text-white"
                : "max-w-[80%] rounded-2xl border border-edge bg-surface px-4 py-2 text-sm text-ink"
            }
          >
            <p className="whitespace-pre-wrap">{turn.content}</p>
            {turn.citations && turn.citations.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-2 border-t border-edge pt-2 text-xs text-ink-3">
                {turn.citations.map((c) => (
                  <Link key={c.chunk_id} to={`/documents/${c.document_id}`} className="hover:text-accent hover:underline">
                    [{c.marker}] {c.document_title}
                  </Link>
                ))}
              </div>
            )}
          </div>
        ))}
        {sending && <p className="text-sm text-ink-3">Thinking…</p>}
        {error && <p className="text-sm text-danger">{error}</p>}
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question…"
          disabled={sending}
          className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft disabled:opacity-50"
        />
        <Button type="submit" disabled={sending || !input.trim()}>
          Send
        </Button>
      </form>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Chat.test.tsx`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Chat.tsx apps/web/src/routes/Chat.test.tsx
git commit -m "feat(web): migrate Chat page to violet design system, wire up loading bar"
```

---

### Task 2: Migrate Legal.tsx

**Files:**
- Modify: `apps/web/src/routes/Legal.tsx`
- Test: `apps/web/src/routes/Legal.test.tsx` (new)

**Interfaces:**
- Consumes: `Button`, `Checkbox` (`import { Checkbox } from "../components/ui/form"`, props `{label: string, checked: boolean, onChange: (checked: boolean) => void}`), `useLoadingBar` (same as Task 1), `ApiError`/`legalDraft`/`listDocuments`/`Citation`/`DocumentOut` from `../lib/api` (unchanged).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Legal.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Legal from "./Legal";
import { LoadingBarProvider } from "../lib/loadingBar";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    legalDraft: vi.fn(),
    listDocuments: vi.fn(),
  };
});

const DOCS: api.DocumentOut[] = [
  { id: "d1", title: "Lease Agreement" } as api.DocumentOut,
  { id: "d2", title: "Evidence letter" } as api.DocumentOut,
];

function renderPage() {
  return render(
    <MemoryRouter>
      <LoadingBarProvider>
        <Legal />
      </LoadingBarProvider>
    </MemoryRouter>
  );
}

describe("Legal", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listDocuments).mockResolvedValue(DOCS);
    vi.mocked(api.legalDraft).mockResolvedValue({
      draft: "Dear Sir or Madam, ...",
      citations: [{ marker: 1, document_id: "d1", document_title: "Lease Agreement", chunk_id: "c1" }],
      disclaimer: "This draft is not legal advice.",
    });
  });

  it("lists documents as checkboxes once loaded", async () => {
    renderPage();
    expect(await screen.findByLabelText("Lease Agreement")).toBeInTheDocument();
    expect(screen.getByLabelText("Evidence letter")).toBeInTheDocument();
  });

  it("drafts and renders the result with disclaimer and citation", async () => {
    renderPage();
    await screen.findByLabelText("Lease Agreement");
    fireEvent.click(screen.getByLabelText("Lease Agreement"));
    fireEvent.change(screen.getByPlaceholderText(/Draft a letter/), { target: { value: "Summarize the lease." } });
    fireEvent.click(screen.getByRole("button", { name: "Draft" }));
    await waitFor(() => expect(api.legalDraft).toHaveBeenCalledWith("Summarize the lease.", ["d1"]));
    expect(await screen.findByText("Dear Sir or Madam, ...")).toBeInTheDocument();
    expect(screen.getByText("This draft is not legal advice.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "[1] Lease Agreement" })).toHaveAttribute("href", "/documents/d1");
  });

  it("shows an error message when the request fails", async () => {
    vi.mocked(api.legalDraft).mockRejectedValue(new api.ApiError(500, "Draft boom"));
    renderPage();
    await screen.findByLabelText("Lease Agreement");
    fireEvent.change(screen.getByPlaceholderText(/Draft a letter/), { target: { value: "hi" } });
    fireEvent.click(screen.getByRole("button", { name: "Draft" }));
    expect(await screen.findByText("Draft boom")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Legal.test.tsx`
Expected: FAIL (file compiles against the current component; confirms the test harness catches drift once Step 3 rewrites the component).

- [ ] **Step 3: Rewrite Legal.tsx**

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError, legalDraft, listDocuments, type Citation, type DocumentOut } from "../lib/api";
import { Button } from "../components/ui/Button";
import { Checkbox } from "../components/ui/form";
import { useLoadingBar } from "../lib/loadingBar";

export default function Legal() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [instruction, setInstruction] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ draft: string; citations: Citation[]; disclaimer: string } | null>(null);
  const { start, done } = useLoadingBar();

  useEffect(() => {
    listDocuments().then(setDocuments);
  }, []);

  function toggleDocument(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!instruction.trim() || drafting) return;
    setDrafting(true);
    setError(null);
    setResult(null);
    start();
    try {
      setResult(await legalDraft(instruction.trim(), Array.from(selectedIds)));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Draft request failed");
    } finally {
      setDrafting(false);
      done();
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Legal Draft</h1>
        <p className="mt-1 text-sm text-ink-2">
          Drafts are grounded only in the documents you select (or all documents if none are selected) and are
          never a substitute for attorney review.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm text-ink">
          Drafting instruction
          <textarea
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            rows={4}
            placeholder="e.g. Draft a letter summarizing the client's obligations under the attached agreement."
            className="rounded-xl border border-edge bg-surface px-3 py-2 text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
          />
        </label>

        {documents.length > 0 && (
          <div>
            <p className="text-sm font-medium text-ink-2">Scope to documents (optional)</p>
            <div className="mt-1 flex flex-col gap-1 rounded-xl border border-edge bg-surface p-3 max-h-48 overflow-y-auto">
              {documents.map((doc) => (
                <Checkbox
                  key={doc.id}
                  label={doc.title}
                  checked={selectedIds.has(doc.id)}
                  onChange={() => toggleDocument(doc.id)}
                />
              ))}
            </div>
          </div>
        )}

        <Button type="submit" disabled={drafting || !instruction.trim()} className="self-start">
          {drafting ? "Drafting…" : "Draft"}
        </Button>
        {error && <p className="text-sm text-danger">{error}</p>}
      </form>

      {result && (
        <div className="flex flex-col gap-3 rounded-2xl border border-edge bg-surface p-4">
          <p className="rounded-xl bg-warning-soft p-3 text-xs text-warning">{result.disclaimer}</p>
          <p className="whitespace-pre-wrap text-sm text-ink">{result.draft}</p>
          {result.citations.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-edge pt-2 text-xs text-ink-3">
              {result.citations.map((c) => (
                <Link key={c.chunk_id} to={`/documents/${c.document_id}`} className="hover:text-accent hover:underline">
                  [{c.marker}] {c.document_title}
                </Link>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Legal.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Legal.tsx apps/web/src/routes/Legal.test.tsx
git commit -m "feat(web): migrate Legal Draft page to violet design system, wire up loading bar"
```

---

### Task 3: Migrate Tasks.tsx

**Files:**
- Modify: `apps/web/src/routes/Tasks.tsx`
- Test: `apps/web/src/routes/Tasks.test.tsx` (new)

**Interfaces:**
- Consumes: `Button` (same as Task 1), `ApiError`/`listTasks`/`updateTaskStatus`/`TaskOut` from `../lib/api` (unchanged).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Tasks.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Tasks from "./Tasks";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listTasks: vi.fn(),
    updateTaskStatus: vi.fn(),
  };
});

const OPEN_TASKS: api.TaskOut[] = [
  {
    id: "t1", document_id: "d1", title: "Review lease", description: "Check termination clause",
    due_date: "2026-08-01", assignee: "Ada", status: "open", source: "manual", created_at: "2026-01-01T00:00:00Z",
  },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Tasks />
    </MemoryRouter>
  );
}

describe("Tasks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listTasks).mockResolvedValue(OPEN_TASKS);
    vi.mocked(api.updateTaskStatus).mockResolvedValue({ ...OPEN_TASKS[0], status: "done" });
  });

  it("renders open tasks with their metadata and source-document link", async () => {
    renderPage();
    expect(await screen.findByText("Review lease")).toBeInTheDocument();
    expect(screen.getByText("Check termination clause")).toBeInTheDocument();
    expect(screen.getByText("Due 2026-08-01")).toBeInTheDocument();
    expect(screen.getByText("Assignee: Ada")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Source document" })).toHaveAttribute("href", "/documents/d1");
  });

  it("defaults to the open filter and re-queries when a different tab is clicked", async () => {
    renderPage();
    await screen.findByText("Review lease");
    expect(api.listTasks).toHaveBeenLastCalledWith("open");
    fireEvent.click(screen.getByRole("button", { name: "done" }));
    await waitFor(() => expect(api.listTasks).toHaveBeenLastCalledWith("done"));
  });

  it("toggles a task's done status when its checkbox is clicked", async () => {
    renderPage();
    await screen.findByText("Review lease");
    fireEvent.click(screen.getByRole("checkbox"));
    await waitFor(() => expect(api.updateTaskStatus).toHaveBeenCalledWith("t1", "done"));
  });

  it("shows an empty message when there are no tasks", async () => {
    vi.mocked(api.listTasks).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No open tasks.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx`
Expected: FAIL (file compiles against the current component; confirms the test harness catches drift once Step 3 rewrites the component).

- [ ] **Step 3: Rewrite Tasks.tsx**

```tsx
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, listTasks, updateTaskStatus, type TaskOut } from "../lib/api";
import { Button } from "../components/ui/Button";

type Filter = "open" | "done" | "all";

export default function Tasks() {
  const [tasks, setTasks] = useState<TaskOut[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback((currentFilter: Filter) => {
    setLoading(true);
    listTasks(currentFilter === "all" ? undefined : currentFilter)
      .then(setTasks)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load tasks"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh(filter);
  }, [filter, refresh]);

  async function toggleDone(task: TaskOut) {
    const nextStatus = task.status === "done" ? "open" : "done";
    try {
      await updateTaskStatus(task.id, nextStatus);
      refresh(filter);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to update task");
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Tasks</h1>
        <div className="flex gap-1">
          {(["open", "done", "all"] as Filter[]).map((f) => (
            <Button key={f} size="sm" variant={filter === f ? "primary" : "ghost"} onClick={() => setFilter(f)}>
              {f}
            </Button>
          ))}
        </div>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      {loading ? (
        <p className="text-ink-3">Loading…</p>
      ) : tasks.length === 0 ? (
        <p className="text-ink-3">No {filter !== "all" ? filter : ""} tasks.</p>
      ) : (
        <div className="flex flex-col divide-y divide-edge rounded-2xl border border-edge bg-surface">
          {tasks.map((task) => (
            <div key={task.id} className="flex items-start gap-3 px-4 py-3">
              <input
                type="checkbox"
                checked={task.status === "done"}
                onChange={() => toggleDone(task)}
                className="mt-1 h-4 w-4 accent-accent"
              />
              <div className="flex-1">
                <p className={task.status === "done" ? "text-sm text-ink-3 line-through" : "text-sm font-medium text-ink"}>
                  {task.title}
                </p>
                {task.description && <p className="mt-0.5 text-xs text-ink-2">{task.description}</p>}
                <div className="mt-1 flex gap-3 text-xs text-ink-3">
                  {task.due_date && <span>Due {task.due_date}</span>}
                  {task.assignee && <span>Assignee: {task.assignee}</span>}
                  {task.document_id && (
                    <Link to={`/documents/${task.document_id}`} className="hover:text-accent hover:underline">
                      Source document
                    </Link>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Tasks.test.tsx`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Tasks.tsx apps/web/src/routes/Tasks.test.tsx
git commit -m "feat(web): migrate Tasks page to violet design system"
```

---

### Task 4: Full-suite verification and manual browser check

- [ ] **Step 1: Run the full test suite**

Run: `cd /opt/collabrains/apps/web && pnpm test`
Expected: all tests pass (previous 141 + this plan's 11 new tests = 152).

- [ ] **Step 2: Production build sanity check**

Run: `cd /opt/collabrains/apps/web && npx vite build`
Expected: build succeeds with no errors.

- [ ] **Step 3: Manual verification against real production data**

Tunnel to the live `web`/`api` containers exactly as done in prior phases (check `lsof -i :PORT` first for local collisions; widen `allow_origins` in `services/api/src/api/main.py` temporarily if needed, revert immediately after). Using Playwright, visit `/chat`, `/legal`, and `/tasks` against real data and confirm: sending a real chat message shows the top loading bar during the ~15-20s AI response and renders a real grounded answer with citation links; the Legal Draft page's document checkboxes toggle correctly and a real draft request also triggers the loading bar; the Tasks page's open/done/all tabs correctly re-query real tasks and toggling a real task's checkbox persists via the API.

- [ ] **Step 4: Revert any temporary CORS change and restart the api container if it was modified**

```bash
cd /opt/collabrains && git diff services/api/src/api/main.py
# if changed, revert:
git checkout services/api/src/api/main.py
docker compose restart api
```
