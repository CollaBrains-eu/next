# Phase 20d1: Documents Page Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the Documents list (`Workspace.tsx`) and document detail (`DocumentDetail.tsx`) pages to the violet design system built in Phases 20a-20c, using real API data — the first of several page-cluster migrations that make up Phase 20d.

**Architecture:** Pure application of existing components (`DataTable`, `Badge`, `Button`, `TextField`, `EmptyState`, `Modal`, `useToast`, `useBulkSelection`, `BulkActionBar`, `FilterChips`) to real pages — no new design-system components are created in this plan. `DataTable` directly fixes a real, previously-documented bug: the Documents list currently renders as one unbounded flat list with no pagination.

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4, Vitest 3 + `@testing-library/react`, pnpm workspace.

## Scope

Builds on Phase 20a (branch `phase-20a-design-system-foundation`, PR #28), 20b (branch `phase-20b-layout-chrome`, PR #30), and 20c (branch `phase-20c-interaction-patterns`, PR #32) — none merged to `main` yet.

Covers only `apps/web/src/routes/DocumentDetail.tsx` and `apps/web/src/routes/Workspace.tsx`.

**Deliberate deviation from the validated prototype, stated explicitly**: the prototype used a slide-in `Drawer` for document detail. This plan keeps the existing **route-based** detail page (`/documents/:id`) instead of converting it to a `Drawer` overlay. The route-based approach is a real architectural advantage the prototype didn't have to consider — bookmarkable, shareable URLs, and it already has working polling logic tied to the route param. Retrofitting a `Drawer` here would trade that away for no clear user benefit, so `Drawer` stays available for a future page where an overlay genuinely fits better rather than being forced in here.

**Also not included**: `InlineEditableText` on the document title — there is no rename/update endpoint on the backend (`services/api`), only `GET`/`DELETE`/upload/`summarize`. Wiring it up would mean building a fake edit control with no real effect, which this project's own practice (see the earlier production audit) treats as a bug, not a feature — not repeating that here.

The other 8 pages (Cases, CaseDetail, Vehicles, Entities, EntityGraph, Chat, Legal, Tasks, Settings, Assistant) remain future phases (20d2, 20d3, ...), each requiring its own look at real data/API shape before planning, same as this one.

## Global Constraints

- Reuses Phase 20a/20b/20c components and tokens as-is: `Badge`, `Button`, `TextField`, `EmptyState`, `Modal`, `DataTable`/`Column`, `useToast`/`ToastProvider` (already mounted in `App.tsx`), `useBulkSelection`, `BulkActionBar`, `FilterChips`.
- Only wire UI to API calls that actually exist in `apps/web/src/lib/api.ts` (`listDocuments`, `getDocument`, `deleteDocument`, `summarizeDocument`, `search`) — no fabricated endpoints.
- Package manager is **pnpm**. Verify with `vite build` + `pnpm test`, not the full `pnpm build` (pre-existing, out-of-scope `apps/mobile` `@types/react@19` hoisting conflict, documented in PR #28).
- No new dependencies.

## Environment Setup (read before Task 1)

Same as prior phases — no local clone, only SSH:

```bash
ssh root@195.90.216.230   # apps/web lives at /opt/collabrains/apps/web
cd /opt/collabrains
git fetch origin --quiet
git checkout phase-20c-interaction-patterns
git checkout -b phase-20d1-documents-page
cd apps/web
```

Branch from `phase-20c-interaction-patterns`, **not** `main`. Run every `pnpm` command from `/opt/collabrains/apps/web`. Commit after each task. Push and open a PR at the end (do not merge).

---

### Task 1: Migrate `DocumentDetail.tsx`

**Files:**
- Modify: `apps/web/src/routes/DocumentDetail.tsx`
- Test: `apps/web/src/routes/DocumentDetail.test.tsx`

**Interfaces:**
- Consumes: `Badge`, `Button`, `Modal` (`apps/web/src/components/ui/`), `useToast` (`apps/web/src/lib/toast`), existing `getDocument`/`deleteDocument`/`summarizeDocument`/`ApiError` from `apps/web/src/lib/api`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/routes/DocumentDetail.test.tsx`:
```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import DocumentDetail from "./DocumentDetail";
import { ToastProvider } from "../lib/toast";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getDocument: vi.fn(),
    deleteDocument: vi.fn(),
    summarizeDocument: vi.fn(),
  };
});

const mockDoc = {
  id: "doc-1",
  title: "factuur-77621.pdf",
  filename: "factuur-77621.pdf",
  mime_type: "application/pdf",
  status: "ready",
  error: null,
  created_at: "2026-07-08T19:11:38Z",
  processed_at: "2026-07-08T19:12:00Z",
  ocr_text: "Extracted text here",
  chunk_count: 3,
  summary: null,
};

function renderAt(id: string) {
  return render(
    <MemoryRouter initialEntries={[`/documents/${id}`]}>
      <ToastProvider>
        <Routes>
          <Route path="/documents/:id" element={<DocumentDetail />} />
        </Routes>
      </ToastProvider>
    </MemoryRouter>
  );
}

describe("DocumentDetail", () => {
  beforeEach(() => {
    vi.mocked(api.getDocument).mockResolvedValue(mockDoc);
  });

  it("shows the document title and a Ready badge once loaded", async () => {
    renderAt("doc-1");
    expect(await screen.findByText("factuur-77621.pdf")).toBeInTheDocument();
    expect(screen.getByText("ready")).toBeInTheDocument();
  });

  it("shows extracted text in a card", async () => {
    renderAt("doc-1");
    expect(await screen.findByText("Extracted text here")).toBeInTheDocument();
  });

  it("clicking Delete opens a confirmation Modal, not window.confirm", async () => {
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    expect(screen.getByText(/cannot be undone/i)).toBeInTheDocument();
  });

  it("confirming the modal calls deleteDocument and shows a toast", async () => {
    vi.mocked(api.deleteDocument).mockResolvedValue(undefined);
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Delete document" }));
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledWith("doc-1"));
    expect(await screen.findByText(/deleted/i)).toBeInTheDocument();
  });

  it("canceling the modal does not call deleteDocument", async () => {
    renderAt("doc-1");
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(api.deleteDocument).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test DocumentDetail`
Expected: FAIL — current implementation uses `window.confirm`, has no "Delete document" confirm button, and has no toast on delete.

- [ ] **Step 3: Rewrite the component**

Modify `apps/web/src/routes/DocumentDetail.tsx` — replace its full contents:
```tsx
import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError, deleteDocument, getDocument, summarizeDocument, type DocumentDetailOut } from "../lib/api";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Modal } from "../components/ui/Modal";
import { useToast } from "../lib/toast";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "default"> = {
  ready: "success",
  pending: "default",
  ocr_processing: "warning",
  embedding: "warning",
  failed: "danger",
};

export default function DocumentDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [doc, setDoc] = useState<DocumentDetailOut | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    getDocument(id)
      .then(setDoc)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load document"));
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (doc && (doc.status === "pending" || doc.status === "processing")) {
      const interval = setInterval(load, 3000);
      return () => clearInterval(interval);
    }
  }, [doc, load]);

  async function handleSummarize() {
    if (!id) return;
    setSummarizing(true);
    try {
      await summarizeDocument(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Summarize failed");
    } finally {
      setSummarizing(false);
    }
  }

  async function handleConfirmDelete() {
    if (!id) return;
    setDeleting(true);
    try {
      await deleteDocument(id);
      setConfirmOpen(false);
      showToast(`"${doc?.title}" deleted`);
      navigate("/");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Delete failed");
      setConfirmOpen(false);
      setDeleting(false);
    }
  }

  if (error) {
    return (
      <div>
        <Link to="/" className="text-sm text-ink-2 hover:text-ink">
          ← Back
        </Link>
        <p className="mt-4 text-danger">{error}</p>
      </div>
    );
  }

  if (!doc) return <p className="text-ink-2">Loading…</p>;

  return (
    <div className="flex flex-col gap-4">
      <Link to="/" className="text-sm text-ink-2 hover:text-ink">
        ← Back
      </Link>

      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">{doc.title}</h1>
          <p className="mt-1 flex items-center gap-2 text-sm text-ink-2">
            {doc.mime_type} · <Badge variant={STATUS_VARIANT[doc.status] ?? "default"}>{doc.status}</Badge> · {doc.chunk_count} chunk(s)
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" size="sm" onClick={handleSummarize} disabled={doc.status !== "ready" || summarizing}>
            {summarizing ? "Summarizing…" : doc.summary ? "Re-summarize" : "Summarize"}
          </Button>
          <Button variant="danger" size="sm" onClick={() => setConfirmOpen(true)} disabled={deleting}>
            Delete
          </Button>
        </div>
      </div>

      {doc.error && <p className="rounded-xl bg-danger-soft p-3 text-sm text-danger">Processing error: {doc.error}</p>}

      {doc.summary && (
        <div className="rounded-2xl border border-edge bg-surface p-4 shadow-raised">
          <h2 className="text-sm font-medium text-ink-2">Summary</h2>
          <p className="mt-1 whitespace-pre-wrap text-sm text-ink">{doc.summary}</p>
        </div>
      )}

      {doc.ocr_text && (
        <div className="rounded-2xl border border-edge bg-surface p-4 shadow-raised">
          <h2 className="text-sm font-medium text-ink-2">Extracted text</h2>
          <p className="mt-1 max-h-96 overflow-y-auto whitespace-pre-wrap text-sm text-ink">{doc.ocr_text}</p>
        </div>
      )}

      <Modal open={confirmOpen} onClose={() => setConfirmOpen(false)} title={`Delete "${doc.title}"?`}>
        <p className="mb-4 text-sm text-ink-2">This cannot be undone.</p>
        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => setConfirmOpen(false)}>
            Cancel
          </Button>
          <Button variant="danger" size="sm" onClick={handleConfirmDelete} disabled={deleting}>
            Delete document
          </Button>
        </div>
      </Modal>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test DocumentDetail`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/routes/DocumentDetail.tsx src/routes/DocumentDetail.test.tsx
git commit -m "feat: migrate DocumentDetail to design system (Card panels, Badge, Modal confirm, toast)"
```

---

### Task 2: Migrate `Workspace.tsx` visuals (DataTable, Badge, Button, TextField, EmptyState)

**Files:**
- Modify: `apps/web/src/routes/Workspace.tsx`
- Test: `apps/web/src/routes/Workspace.test.tsx`

**Interfaces:**
- Consumes: `DataTable`/`Column` (Phase 20b), `Badge`, `Button`, `TextField` (Phase 20a), `EmptyState`, existing `listDocuments`/`search`/`type DocumentOut`/`type SearchResult` from `apps/web/src/lib/api`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/routes/Workspace.test.tsx`:
```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Workspace from "./Workspace";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listDocuments: vi.fn(),
    search: vi.fn(),
  };
});

const docs: api.DocumentOut[] = Array.from({ length: 12 }, (_, i) => ({
  id: `doc-${i}`,
  title: `document-${i}.pdf`,
  filename: `document-${i}.pdf`,
  mime_type: "application/pdf",
  status: i === 0 ? "failed" : "ready",
  error: null,
  created_at: "2026-07-08T19:11:38Z",
  processed_at: "2026-07-08T19:12:00Z",
}));

function renderPage() {
  return render(
    <MemoryRouter>
      <Workspace />
    </MemoryRouter>
  );
}

describe("Workspace (Documents list)", () => {
  beforeEach(() => {
    vi.mocked(api.listDocuments).mockResolvedValue(docs);
  });

  it("renders documents in a paginated DataTable (only 10 of 12 rows visible on page 1)", async () => {
    renderPage();
    expect(await screen.findByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-11.pdf")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "2" })).toBeInTheDocument();
  });

  it("shows a status badge per row", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    expect(screen.getByText("failed")).toBeInTheDocument();
    expect(screen.getAllByText("ready").length).toBeGreaterThan(0);
  });

  it("shows the redesigned EmptyState when there are no documents", async () => {
    vi.mocked(api.listDocuments).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText(/no documents yet/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Workspace`
Expected: FAIL — the current implementation renders an unbounded flat list with no pagination, so the "only 10 of 12 visible" and "page 2 button" assertions fail.

- [ ] **Step 3: Rewrite the component**

Modify `apps/web/src/routes/Workspace.tsx` — replace its full contents:
```tsx
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { listDocuments, search as searchApi, type DocumentOut, type SearchResult } from "../lib/api";
import UploadDialog from "../components/UploadDialog";
import { DataTable, type Column } from "../components/ui/DataTable";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/form";
import EmptyState from "../components/EmptyState";

const STATUS_VARIANT: Record<string, "success" | "warning" | "danger" | "default"> = {
  ready: "success",
  pending: "default",
  ocr_processing: "warning",
  embedding: "warning",
  failed: "danger",
};

const columns: Column<DocumentOut>[] = [
  {
    key: "title",
    header: "Title",
    sortable: true,
    sortValue: (doc) => doc.title.toLowerCase(),
    render: (doc) => (
      <Link to={`/documents/${doc.id}`} className="font-medium text-ink hover:text-accent">
        {doc.title}
      </Link>
    ),
  },
  {
    key: "created_at",
    header: "Uploaded",
    sortable: true,
    sortValue: (doc) => doc.created_at,
    render: (doc) => new Date(doc.created_at).toLocaleString(),
  },
  {
    key: "status",
    header: "Status",
    render: (doc) => <Badge variant={STATUS_VARIANT[doc.status] ?? "default"}>{doc.status}</Badge>,
  },
];

export default function Workspace() {
  const [documents, setDocuments] = useState<DocumentOut[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  const refresh = useCallback((showLoading = false) => {
    if (showLoading) setLoading(true);
    listDocuments()
      .then(setDocuments)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    refresh(true);
    const interval = setInterval(() => refresh(false), 5000);
    return () => clearInterval(interval);
  }, [refresh]);

  async function handleSearch(e: FormEvent) {
    e.preventDefault();
    if (!query.trim()) {
      setResults(null);
      return;
    }
    setSearching(true);
    try {
      setResults(await searchApi(query.trim()));
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Documents</h1>
        <UploadDialog onUploaded={refresh} />
      </div>

      <form onSubmit={handleSearch} className="flex items-end gap-2">
        <div className="flex-1">
          <TextField label="Search" value={query} onChange={setQuery} placeholder="Search documents…" />
        </div>
        <Button type="submit" variant="secondary" disabled={searching}>
          Search
        </Button>
        {results !== null && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setResults(null);
              setQuery("");
            }}
          >
            Clear
          </Button>
        )}
      </form>

      {results !== null ? (
        <div className="flex flex-col gap-3">
          <h2 className="text-sm font-medium text-ink-2">{results.length} result(s)</h2>
          {results.map((r) => (
            <Link
              key={r.chunk_id}
              to={`/documents/${r.document_id}`}
              className="block rounded-2xl border border-edge bg-surface p-4 shadow-raised hover:border-accent"
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-ink">{r.document_title}</span>
                <span className="text-xs text-ink-3">score {r.score.toFixed(3)}</span>
              </div>
              <p className="mt-1 line-clamp-2 text-sm text-ink-2">{r.content}</p>
            </Link>
          ))}
        </div>
      ) : loading ? (
        <p className="text-ink-2">Loading…</p>
      ) : documents.length === 0 ? (
        <EmptyState message="No documents yet. Upload one to get started." />
      ) : (
        <DataTable columns={columns} rows={documents} rowKey={(doc) => doc.id} />
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test Workspace`
Expected: `3 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/routes/Workspace.tsx src/routes/Workspace.test.tsx
git commit -m "feat: migrate Workspace (Documents list) to DataTable with real pagination"
```

---

### Task 3: Add bulk selection + status filter chips to `Workspace.tsx`

**Files:**
- Modify: `apps/web/src/routes/Workspace.tsx`
- Modify: `apps/web/src/routes/Workspace.test.tsx`

**Interfaces:**
- Consumes: `useBulkSelection`, `BulkActionBar`, `FilterChips` (Phase 20c), `useToast` (already mounted globally), existing `deleteDocument` from `apps/web/src/lib/api`.

- [ ] **Step 1: Write the failing tests (append to the existing file)**

Modify `apps/web/src/routes/Workspace.test.tsx` — add these imports near the top (alongside the existing ones):
```tsx
import { fireEvent, waitFor } from "@testing-library/react";
import { ToastProvider } from "../lib/toast";
```
Update the mocked module to also stub `deleteDocument`:
```tsx
vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listDocuments: vi.fn(),
    search: vi.fn(),
    deleteDocument: vi.fn(),
  };
});
```
Update `renderPage` to wrap in `ToastProvider` (bulk delete shows a toast):
```tsx
function renderPage() {
  return render(
    <MemoryRouter>
      <ToastProvider>
        <Workspace />
      </ToastProvider>
    </MemoryRouter>
  );
}
```
Then append these test cases inside the existing `describe("Workspace (Documents list)", ...)` block:
```tsx
  it("shows a status filter chip for 'failed' documents, and toggling it narrows the table to just that row", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    fireEvent.click(screen.getByText("+ Add filter"));
    fireEvent.click(screen.getByText("Status: Failed"));
    expect(screen.getByText("document-0.pdf")).toBeInTheDocument();
    expect(screen.queryByText("document-1.pdf")).not.toBeInTheDocument();
  });

  it("removing an active filter chip restores the full table", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    fireEvent.click(screen.getByText("+ Add filter"));
    fireEvent.click(screen.getByText("Status: Failed"));
    fireEvent.click(screen.getByLabelText("Remove Status: Failed"));
    expect(screen.getByText("document-1.pdf")).toBeInTheDocument();
  });

  it("selecting rows shows the bulk action bar with the right count", async () => {
    renderPage();
    await screen.findByText("document-0.pdf");
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    expect(screen.getByText((_, el) => el?.textContent === "2 selected")).toBeInTheDocument();
  });

  it("bulk-deleting selected rows calls deleteDocument for each and shows a toast", async () => {
    vi.mocked(api.deleteDocument).mockResolvedValue(undefined);
    renderPage();
    await screen.findByText("document-0.pdf");
    const checkboxes = screen.getAllByRole("checkbox");
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(api.deleteDocument).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/deleted/i)).toBeInTheDocument();
  });
```

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `pnpm test Workspace`
Expected: FAIL — the 4 new tests fail (`+ Add filter`, checkboxes, and a "Delete" bulk button don't exist yet); the 3 tests from Task 2 still pass.

- [ ] **Step 3: Add bulk selection and filter chips to the component**

Modify `apps/web/src/routes/Workspace.tsx`:

Add these imports alongside the existing ones:
```tsx
import { useMemo } from "react";
import { deleteDocument } from "../lib/api";
import { useBulkSelection } from "../hooks/useBulkSelection";
import { BulkActionBar } from "../components/ui/BulkActionBar";
import { FilterChips } from "../components/ui/FilterChips";
import { useToast } from "../lib/toast";
```
(Note: `deleteDocument` needs adding to the existing `import { listDocuments, search as searchApi, type DocumentOut, type SearchResult } from "../lib/api";` line rather than a separate import — combine them into one import statement.)

Add a checkbox column to the `columns` array — insert this as the **first** entry in `columns`, before `title`:
```tsx
  {
    key: "select",
    header: "",
    render: () => null, // overridden per-row below; DataTable's Column.render doesn't receive selection state, so this column is populated via a wrapper -- see Step 3b
  },
```
Actually, since `DataTable`'s `Column.render(row)` only receives the row, not external selection state, the checkbox column needs access to `isSelected`/`toggle` from the component's own closure — define `columns` as a function of those instead of a static top-level constant. Replace the entire top-level `const columns: Column<DocumentOut>[] = [...]` block (delete it from module scope) and instead build the columns array **inside** the `Workspace` component function, right before the `return`, so it can close over `isSelected`/`toggle`:
```tsx
  const activeFilters = useMemo(() => new Set(statusFilters), [statusFilters]);
  const filteredDocuments = useMemo(
    () => (activeFilters.size === 0 ? documents : documents.filter((doc) => activeFilters.has(doc.status))),
    [documents, activeFilters]
  );

  const columns: Column<DocumentOut>[] = [
    {
      key: "select",
      header: "",
      render: (doc) => (
        <input
          type="checkbox"
          checked={isSelected(doc)}
          onChange={() => toggle(doc)}
          onClick={(event) => event.stopPropagation()}
          className="h-4 w-4 accent-accent"
        />
      ),
    },
    {
      key: "title",
      header: "Title",
      sortable: true,
      sortValue: (doc) => doc.title.toLowerCase(),
      render: (doc) => (
        <Link to={`/documents/${doc.id}`} className="font-medium text-ink hover:text-accent">
          {doc.title}
        </Link>
      ),
    },
    {
      key: "created_at",
      header: "Uploaded",
      sortable: true,
      sortValue: (doc) => doc.created_at,
      render: (doc) => new Date(doc.created_at).toLocaleString(),
    },
    {
      key: "status",
      header: "Status",
      render: (doc) => <Badge variant={STATUS_VARIANT[doc.status] ?? "default"}>{doc.status}</Badge>,
    },
  ];
```
(`STATUS_VARIANT` stays a module-level constant as before — only `columns` moves inside the component.)

Inside the `Workspace` function, add this state and these handlers right after the existing `useState`/`useCallback` declarations (before `handleSearch`):
```tsx
  const [statusFilters, setStatusFilters] = useState<string[]>([]);
  const { isSelected, toggle, clear, selectedCount, selectedKeys } = useBulkSelection<DocumentOut>((doc) => doc.id);
  const { showToast } = useToast();

  const STATUS_FILTER_OPTIONS = [
    { id: "ready", label: "Status: Ready" },
    { id: "failed", label: "Status: Failed" },
    { id: "pending", label: "Status: Pending" },
  ];

  async function handleBulkDelete() {
    const ids = [...selectedKeys];
    await Promise.all(ids.map((id) => deleteDocument(id)));
    clear();
    refresh();
    showToast(`${ids.length} document${ids.length === 1 ? "" : "s"} deleted`);
  }
```

Replace the final render branch (`documents.length === 0 ? <EmptyState .../> : <DataTable .../>`) with:
```tsx
      ) : documents.length === 0 ? (
        <EmptyState message="No documents yet. Upload one to get started." />
      ) : (
        <>
          <FilterChips
            chips={STATUS_FILTER_OPTIONS.filter((opt) => statusFilters.includes(opt.id))}
            onRemove={(id) => setStatusFilters((prev) => prev.filter((s) => s !== id))}
            addOptions={STATUS_FILTER_OPTIONS.filter((opt) => !statusFilters.includes(opt.id))}
            onAdd={(opt) => setStatusFilters((prev) => [...prev, opt.id])}
          />
          <DataTable columns={columns} rows={filteredDocuments} rowKey={(doc) => doc.id} />
          <BulkActionBar
            count={selectedCount}
            onCancel={clear}
            actions={[{ label: "Delete", onClick: handleBulkDelete, variant: "danger" }]}
          />
        </>
      )}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pnpm test Workspace`
Expected: `7 passed` (3 from Task 2 + 4 new).

- [ ] **Step 5: Run the full suite**

Run: `pnpm test`
Expected: all tests across Phases 20a-20c plus this plan pass together.

- [ ] **Step 6: Verify the build compiles**

Run: `npx vite build`
Expected: succeeds (same `tsc`-bypassing approach as prior phases, for the same pre-existing, out-of-scope conflict).

- [ ] **Step 7: Manually verify in a real browser**

Same SSH-tunnel approach as Phases 20a-20c (check `lsof -i :5173` and `lsof -i :8000` locally first for port collisions; widen CORS temporarily if the tunneled frontend port isn't exactly 5173, revert immediately after). Log in and confirm on `/`:
- The Documents list now paginates (page buttons appear if there are more than 10 documents — this project's own document list has 60+ rows from earlier test-data pollution, so pagination should be immediately visible)
- Status badges render with the correct violet/success/warning/danger colors
- Adding a "Status: Failed" filter chip narrows the table to just the failed rows; removing it restores the full list
- Checking two row checkboxes shows the floating bulk-action bar with the right count; clicking Delete actually deletes them and shows a confirmation toast
- Opening a document detail page shows the new Card-styled Summary/Extracted-text panels and a Badge for status; clicking Delete opens a real Modal (not a native browser confirm dialog)

- [ ] **Step 8: Commit**

```bash
git add src/routes/Workspace.tsx src/routes/Workspace.test.tsx
git commit -m "feat: add bulk selection and status filter chips to Workspace"
```

---

## Self-Review

**Spec coverage:** bulk selection applied to a real page → Task 3. Filter chips applied to a real page → Task 3. DataTable (with real pagination, fixing the previously-documented "no pagination" bug) applied to a real page → Task 2. Badge/Button/EmptyState/Modal/Toast applied to real pages → Tasks 1-2. Inline editing and split-view/Drawer are deliberately **not** forced onto this page, with rationale stated in Scope — no backend rename endpoint exists for the former, and the route-based detail page is a genuine architectural improvement over the prototype's Drawer for the latter, not an oversight.

**Placeholder scan:** no TBD/TODO; every step has complete, real code wired to real, existing API functions only.

**Type consistency:** `Column<DocumentOut>`'s shape matches `DataTable`'s definition from Phase 20b. `useBulkSelection<DocumentOut>`'s returned `{isSelected, toggle, clear, selectedCount, selectedKeys}` matches Phase 20c's hook signature exactly. `BulkActionBar`'s `actions: {label, onClick, variant?}[]` matches Phase 20c's component. `FilterChips`' `{chips, onRemove, addOptions, onAdd}` matches Phase 20c's component, using the same `{id, label}` option shape for both `chips` and `addOptions`.
