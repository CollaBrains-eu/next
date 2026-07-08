# Phase 20d2: Cases, CaseDetail & Vehicles Page Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the three real Cases/Vehicles pages (`Cases.tsx`, `CaseDetail.tsx`, `Vehicles.tsx`) from raw Tailwind slate classes to the violet design system primitives built in Phase 20a-20c (`Button`, `Badge`, `TextField`, design tokens), matching the validated artifact's visual language, following the same real-API-grounded migration approach used in Phase 20d1 (Documents).

**Architecture:** Each page keeps its existing data-fetching logic and component structure untouched (no new endpoints, no fabricated functionality) — only the JSX markup and className strings change, swapping raw `<button>`/`<input>`/color classes for the `Button`, `Badge`, and `TextField` primitives, and hand-styled equivalents (matching the same token classes) where no primitive fits the exact shape needed.

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4 (violet token theme from Phase 20a), Vitest 3, @testing-library/react, react-router-dom (MemoryRouter in tests).

## Global Constraints

- Do not modify `apps/web/src/lib/api.ts` — only real, existing endpoints/types may be used (`CaseOut`, `CaseDashboardOut`, `VehicleOut`, `listCases`, `createCase`, `getCase`, `updateCaseStatus`, `listVehicles`, `lookupVehicle`, `linkVehicleToCase`, `attachDocumentToCase`, `linkTaskToCase`, `linkDecisionToCase`, `listDocuments`, `listTasks`, `listDecisions`).
- `Select` primitive (`components/ui/form.tsx`) only supports `options: string[]` where value===label — it does NOT fit `CaseDetail`'s attach dropdowns, which need distinct id/label pairs. Do not extend `Select`'s API for this (would ripple into its existing consumers/tests). Use a hand-styled `<select>` with the same token classes (`rounded-xl border border-edge bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft`) instead — same deliberate-deviation pattern as Phase 20d1's DocumentDetail keeping a route instead of forcing `Drawer`.
- No `Textarea` primitive exists. `Cases.tsx`'s description field stays a hand-styled `<textarea>` using the same token classes as `TextField`'s input (`rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft`).
- `LicensePlateInput.tsx` and `Vehicles.tsx`'s RDW-data `<dl>` are explicitly OUT of scope — Phase 20's spec (PR #26) explicitly defers "a real license-plate input with country selector and validation state" and "a styled metadata key-value display" as a future focused design pass. Do not touch either.
- Card usage (`components/Card.tsx`) is already token-based from Phase 20a — no changes needed there, only its consumers' surrounding markup.
- Verify each task with `npx vite build` (from `apps/web`) + `pnpm test` (not full `pnpm build` — pre-existing `apps/mobile`/`apps/web` `@types/react` hoisting conflict, documented in PR #28, remains out of scope).
- Branch this plan's implementation off `phase-20d2-plan-cases-vehicles-migration` (this plan's own branch), which itself sits on `phase-20d1-documents-page` — nothing is merged to `main` yet.
- Commit after each task. Push and open a PR against `main` at the end (do not merge).

---

### Task 1: Migrate Cases.tsx

**Files:**
- Modify: `apps/web/src/routes/Cases.tsx`
- Test: `apps/web/src/routes/Cases.test.tsx` (new)

**Interfaces:**
- Consumes: `Button` (`import { Button } from "../components/ui/Button"`, props `{variant?, size?, ...ButtonHTMLAttributes}`), `Badge` (`import { Badge } from "../components/ui/Badge"`, props `{variant?: "default"|"success"|"warning"|"danger", ...}`), `EmptyState` (`import EmptyState from "../components/EmptyState"`, unchanged `{message, action?}`), `Card` (unchanged), `ApiError`/`createCase`/`listCases`/`CaseOut` from `../lib/api` (unchanged).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Cases.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Cases from "./Cases";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listCases: vi.fn(),
    createCase: vi.fn(),
  };
});

const CASES: api.CaseOut[] = [
  { id: "c1", name: "Alpha matter", description: "First case", status: "open", created_at: "2026-01-01T00:00:00Z" },
  { id: "c2", name: "Beta matter", description: null, status: "closed", created_at: "2026-01-02T00:00:00Z" },
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Cases />
    </MemoryRouter>
  );
}

describe("Cases", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listCases).mockResolvedValue(CASES);
    vi.mocked(api.createCase).mockResolvedValue(CASES[0]);
  });

  it("renders case cards with name and status badge", async () => {
    renderPage();
    expect(await screen.findByText("Alpha matter")).toBeInTheDocument();
    expect(screen.getByText("Beta matter")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
    expect(screen.getByText("closed")).toBeInTheDocument();
  });

  it("shows EmptyState when there are no cases", async () => {
    vi.mocked(api.listCases).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No cases yet.")).toBeInTheDocument();
  });

  it("reveals the create form when New case is clicked", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "New case" }));
    expect(screen.getByPlaceholderText("Case name")).toBeInTheDocument();
  });

  it("submits the form and calls createCase", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByRole("button", { name: "New case" }));
    fireEvent.change(screen.getByPlaceholderText("Case name"), { target: { value: "Gamma matter" } });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));
    await waitFor(() => expect(api.createCase).toHaveBeenCalledWith("Gamma matter", undefined));
  });

  it("shows an error banner when loading fails", async () => {
    vi.mocked(api.listCases).mockRejectedValue(new api.ApiError("Boom", 500));
    renderPage();
    expect(await screen.findByText("Boom")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Cases.test.tsx`
Expected: FAIL (Cases.tsx doesn't yet import Button/Badge, and current status text may not render as plain "open"/"closed" text without a Badge wrapper — the failure confirms the test file compiles against the real current component and catches drift as the component changes in Step 3).

- [ ] **Step 3: Rewrite Cases.tsx**

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
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
    <Button onClick={() => setCreating(true)}>New case</Button>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold text-ink">Cases</h1>
        {cases.length > 0 && newCaseButton}
      </div>

      {creating && (
        <Card>
          <form onSubmit={handleCreate} className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-ink">New case</span>
              <Button type="button" variant="ghost" size="sm" onClick={() => setCreating(false)}>
                Cancel
              </Button>
            </div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Case name"
              className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
            />
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              rows={2}
              className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
            />
            <Button type="submit" disabled={submitting || !name.trim()} className="self-start">
              Create
            </Button>
          </form>
        </Card>
      )}

      {error && <p className="text-sm text-danger">{error}</p>}

      {loading ? (
        <p className="text-ink-3">Loading…</p>
      ) : cases.length === 0 && !creating ? (
        <EmptyState message="No cases yet." action={newCaseButton} />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {cases.map((c) => (
            <Link key={c.id} to={`/cases/${c.id}`}>
              <Card className="flex h-full flex-col gap-2 transition-colors duration-fast hover:border-accent">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-ink">{c.name}</span>
                  <Badge variant={c.status === "open" ? "success" : "default"}>{c.status}</Badge>
                </div>
                {c.description && <p className="text-sm text-ink-2">{c.description}</p>}
                <span className="mt-auto text-xs text-ink-3">
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

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Cases.test.tsx`
Expected: PASS (5/5)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Cases.tsx apps/web/src/routes/Cases.test.tsx
git commit -m "feat(web): migrate Cases page to violet design system primitives"
```

---

### Task 2: Migrate CaseDetail.tsx

**Files:**
- Modify: `apps/web/src/routes/CaseDetail.tsx`
- Test: `apps/web/src/routes/CaseDetail.test.tsx` (new)

**Interfaces:**
- Consumes: `Button`, `Badge` (same as Task 1), `Card` (unchanged), all existing `lib/api` exports used by the current file (unchanged signatures).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/CaseDetail.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import CaseDetail from "./CaseDetail";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getCase: vi.fn(),
    updateCaseStatus: vi.fn(),
    listDocuments: vi.fn(),
    listTasks: vi.fn(),
    listDecisions: vi.fn(),
    listVehicles: vi.fn(),
    linkVehicleToCase: vi.fn(),
  };
});

const CASE: api.CaseDashboardOut = {
  id: "c1",
  name: "Alpha matter",
  description: "First case",
  status: "open",
  created_at: "2026-01-01T00:00:00Z",
  documents: [],
  tasks: [],
  decisions: [],
  vehicles: [],
};

const VEHICLES: api.VehicleOut[] = [
  {
    id: "v1", kenteken: "AB-12-CD", vin: null, voertuigsoort: null, merk: "Volkswagen",
    handelsbenaming: "Golf", eerste_kleur: null, datum_eerste_toelating: null,
    vervaldatum_apk: null, wam_verzekerd: null, openstaande_terugroepactie_indicator: null,
    brandstofomschrijving: null, fetched_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z",
  },
];

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/cases/c1"]}>
      <Routes>
        <Route path="/cases/:id" element={<CaseDetail />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("CaseDetail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getCase).mockResolvedValue(CASE);
    vi.mocked(api.listDocuments).mockResolvedValue([]);
    vi.mocked(api.listTasks).mockResolvedValue([]);
    vi.mocked(api.listDecisions).mockResolvedValue([]);
    vi.mocked(api.listVehicles).mockResolvedValue(VEHICLES);
    vi.mocked(api.updateCaseStatus).mockResolvedValue({ ...CASE, status: "closed" });
    vi.mocked(api.linkVehicleToCase).mockResolvedValue(undefined);
  });

  it("renders the case name and status badge", async () => {
    renderPage();
    expect(await screen.findByText("Alpha matter")).toBeInTheDocument();
    expect(screen.getByText("open")).toBeInTheDocument();
  });

  it("shows 'Nothing linked yet.' for each empty section", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    expect(screen.getAllByText("Nothing linked yet.")).toHaveLength(4);
  });

  it("toggles status when the status badge is clicked", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    fireEvent.click(screen.getByText("open"));
    await waitFor(() => expect(api.updateCaseStatus).toHaveBeenCalledWith("c1", "closed"));
  });

  it("attaches a vehicle via the vehicles Attach control", async () => {
    renderPage();
    await screen.findByText("Alpha matter");
    const vehiclesSection = screen.getByText("Vehicles").closest("div")!.parentElement!;
    fireEvent.click(within(vehiclesSection).getByText("+ Attach"));
    fireEvent.change(within(vehiclesSection).getByRole("combobox"), { target: { value: "v1" } });
    fireEvent.click(within(vehiclesSection).getByRole("button", { name: "Attach" }));
    await waitFor(() => expect(api.linkVehicleToCase).toHaveBeenCalledWith("c1", "v1"));
  });
});

import { within } from "@testing-library/react";
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/CaseDetail.test.tsx`
Expected: FAIL (current toggle is a plain `<button>` with the status text directly inside, not a separately-clickable "open" text node inside a `Badge`, and the import ordering above needs the `within` import moved to the top — fix the import placement when writing the actual file: put `import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";` on the single top import line instead of two separate lines).

- [ ] **Step 3: Rewrite CaseDetail.tsx**

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import Card from "../components/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import {
  ApiError,
  attachDocumentToCase,
  getCase,
  linkDecisionToCase,
  linkTaskToCase,
  linkVehicleToCase,
  listDecisions,
  listDocuments,
  listTasks,
  listVehicles,
  updateCaseStatus,
  type CaseDashboardOut,
  type DecisionListItemOut,
  type DocumentOut,
  type TaskOut,
  type VehicleOut,
} from "../lib/api";

type AttachSection = "documents" | "tasks" | "decisions" | "vehicles";

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
  const [allVehicles, setAllVehicles] = useState<VehicleOut[]>([]);

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
    listVehicles().then(setAllVehicles).catch(() => undefined);
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
      if (attaching === "vehicles") await linkVehicleToCase(caseData.id, selected);
      setAttaching(null);
      setSelected("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to attach item");
    }
  }

  if (loading) return <p className="text-ink-3">Loading…</p>;
  if (error && !caseData) return <p className="text-sm text-danger">{error}</p>;
  if (!caseData) return null;

  const linkedDocumentIds = new Set(caseData.documents.map((d) => d.id));
  const linkedTaskIds = new Set(caseData.tasks.map((t) => t.id));
  const linkedDecisionIds = new Set(caseData.decisions.map((d) => d.id));
  const linkedVehicleIds = new Set(caseData.vehicles.map((v) => v.id));

  const attachOptions: Record<AttachSection, { id: string; label: string }[]> = {
    documents: allDocuments.filter((d) => !linkedDocumentIds.has(d.id)).map((d) => ({ id: d.id, label: d.title })),
    tasks: allTasks.filter((t) => !linkedTaskIds.has(t.id)).map((t) => ({ id: t.id, label: t.title })),
    decisions: allDecisions.filter((d) => !linkedDecisionIds.has(d.id)).map((d) => ({ id: d.id, label: d.summary })),
    vehicles: allVehicles
      .filter((v) => !linkedVehicleIds.has(v.id))
      .map((v) => ({ id: v.id, label: v.kenteken ?? v.vin ?? v.id })),
  };

  function AttachControl({ section }: { section: AttachSection }) {
    if (attaching !== section) {
      return (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            setAttaching(section);
            setSelected("");
          }}
        >
          + Attach
        </Button>
      );
    }
    const options = attachOptions[section];
    return (
      <div className="flex items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-xl border border-edge bg-surface px-2 py-1 text-xs text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
        >
          <option value="">Select…</option>
          {options.map((o) => (
            <option key={o.id} value={o.id}>
              {o.label}
            </option>
          ))}
        </select>
        <Button size="sm" onClick={handleAttach} disabled={!selected}>
          Attach
        </Button>
        <Button variant="ghost" size="sm" onClick={() => setAttaching(null)}>
          Cancel
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-ink">{caseData.name}</h1>
          {caseData.description && <p className="mt-1 text-sm text-ink-2">{caseData.description}</p>}
        </div>
        <button onClick={toggleStatus} className="rounded-full">
          <Badge variant={caseData.status === "open" ? "success" : "default"}>{caseData.status}</Badge>
        </button>
      </div>

      {error && <p className="text-sm text-danger">{error}</p>}

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">Documents</span>
          <AttachControl section="documents" />
        </div>
        {caseData.documents.length === 0 ? (
          <p className="text-sm text-ink-3">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.documents.map((d) => (
              <li key={d.id}>
                <Link to={`/documents/${d.id}`} className="text-sm text-ink hover:text-accent hover:underline">
                  {d.title}
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">Tasks</span>
          <AttachControl section="tasks" />
        </div>
        {caseData.tasks.length === 0 ? (
          <p className="text-sm text-ink-3">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.tasks.map((t) => (
              <li key={t.id} className="text-sm text-ink">
                {t.title} <span className="text-xs text-ink-3">({t.status})</span>
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">Decisions</span>
          <AttachControl section="decisions" />
        </div>
        {caseData.decisions.length === 0 ? (
          <p className="text-sm text-ink-3">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.decisions.map((d) => (
              <li key={d.id} className="text-sm text-ink">
                {d.summary}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium text-ink">Vehicles</span>
          <AttachControl section="vehicles" />
        </div>
        {caseData.vehicles.length === 0 ? (
          <p className="text-sm text-ink-3">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.vehicles.map((v) => (
              <li key={v.id} className="text-sm text-ink">
                {v.kenteken} {v.merk && <span className="text-xs text-ink-3">({v.merk} {v.handelsbenaming})</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/CaseDetail.test.tsx`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/CaseDetail.tsx apps/web/src/routes/CaseDetail.test.tsx
git commit -m "feat(web): migrate CaseDetail page to violet design system primitives"
```

---

### Task 3: Migrate Vehicles.tsx

**Files:**
- Modify: `apps/web/src/routes/Vehicles.tsx`
- Test: `apps/web/src/routes/Vehicles.test.tsx` (new)

**Interfaces:**
- Consumes: `Button` (same as Task 1), `Card`, `EmptyState`, `LicensePlateInput` (all unchanged), `ApiError`/`listVehicles`/`lookupVehicle`/`VehicleOut` from `../lib/api` (unchanged).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Vehicles.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Vehicles from "./Vehicles";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listVehicles: vi.fn(),
    lookupVehicle: vi.fn(),
  };
});

const VEHICLE: api.VehicleOut = {
  id: "v1", kenteken: "AB-12-CD", vin: null, voertuigsoort: "Personenauto", merk: "Volkswagen",
  handelsbenaming: "Golf", eerste_kleur: "Grijs", datum_eerste_toelating: null,
  vervaldatum_apk: "2027-01-01", wam_verzekerd: "Ja", openstaande_terugroepactie_indicator: null,
  brandstofomschrijving: null, fetched_at: "2026-01-01T00:00:00Z", created_at: "2026-01-01T00:00:00Z",
};

describe("Vehicles", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listVehicles).mockResolvedValue([VEHICLE]);
    vi.mocked(api.lookupVehicle).mockResolvedValue(VEHICLE);
  });

  it("renders the vehicle list with RDW details", async () => {
    render(<Vehicles />);
    expect(await screen.findByText("AB-12-CD")).toBeInTheDocument();
    expect(screen.getByText("Volkswagen Golf")).toBeInTheDocument();
  });

  it("shows EmptyState when there are no vehicles", async () => {
    vi.mocked(api.listVehicles).mockResolvedValue([]);
    render(<Vehicles />);
    expect(await screen.findByText("No vehicles detected yet.")).toBeInTheDocument();
  });

  it("disables the search button until a plate is entered", async () => {
    render(<Vehicles />);
    await screen.findByText("AB-12-CD");
    expect(screen.getByRole("button", { name: "Zoek op" })).toBeDisabled();
  });

  it("looks up a vehicle and refreshes the list", async () => {
    render(<Vehicles />);
    await screen.findByText("AB-12-CD");
    fireEvent.change(screen.getByPlaceholderText("AB-12-CD"), { target: { value: "XY-99-ZZ" } });
    fireEvent.click(screen.getByRole("button", { name: "Zoek op" }));
    await waitFor(() => expect(api.lookupVehicle).toHaveBeenCalledWith("XY-99-ZZ"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Vehicles.test.tsx`
Expected: FAIL ("Zoek op" button is not yet a `Button` component instance — current raw `<button>` does render with the same accessible name, so this specific assertion may actually pass already; the meaningful failure signal is confirmed by re-running after Step 3 shows no regressions, per this project's established pattern of using the test as a safety net through the rewrite rather than requiring every single assertion to start red when a page is a low-risk styling-only change).

- [ ] **Step 3: Rewrite Vehicles.tsx**

```tsx
import { useEffect, useState } from "react";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import LicensePlateInput from "../components/LicensePlateInput";
import { Button } from "../components/ui/Button";
import { ApiError, listVehicles, lookupVehicle, type VehicleOut } from "../lib/api";

function VehicleStatus({ vehicle }: { vehicle: VehicleOut }) {
  if (vehicle.fetched_at === null) {
    return <p className="text-sm text-ink-3">Nog niet opgehaald.</p>;
  }
  if (vehicle.merk === null) {
    return <p className="text-sm text-ink-3">Geen RDW-gegevens gevonden voor dit kenteken.</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
      <dt className="text-ink-2">Merk / model</dt>
      <dd className="text-ink">{vehicle.merk} {vehicle.handelsbenaming}</dd>
      <dt className="text-ink-2">Voertuigsoort</dt>
      <dd className="text-ink">{vehicle.voertuigsoort ?? "-"}</dd>
      <dt className="text-ink-2">Kleur</dt>
      <dd className="text-ink">{vehicle.eerste_kleur ?? "-"}</dd>
      <dt className="text-ink-2">APK-vervaldatum</dt>
      <dd className="text-ink">{vehicle.vervaldatum_apk ?? "-"}</dd>
      <dt className="text-ink-2">WAM-verzekerd</dt>
      <dd className="text-ink">{vehicle.wam_verzekerd ?? "-"}</dd>
    </dl>
  );
}

export default function Vehicles() {
  const [vehicles, setVehicles] = useState<VehicleOut[]>([]);
  const [kenteken, setKenteken] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listVehicles()
      .then(setVehicles)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load vehicles"))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleSearch() {
    if (!kenteken.trim()) return;
    setSearching(true);
    setError(null);
    try {
      await lookupVehicle(kenteken.trim());
      setKenteken("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to look up vehicle");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">Vehicles</h1>

      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <LicensePlateInput value={kenteken} onChange={setKenteken} />
          <Button onClick={handleSearch} disabled={searching || !kenteken.trim()}>
            Zoek op
          </Button>
        </div>
        {error && <p className="text-sm text-danger">{error}</p>}
      </Card>

      {loading ? (
        <p className="text-ink-3">Loading…</p>
      ) : vehicles.length === 0 ? (
        <EmptyState message="No vehicles detected yet." />
      ) : (
        <div className="flex flex-col gap-3">
          {vehicles.map((vehicle) => (
            <Card key={vehicle.id}>
              <p className="mb-2 font-mono text-lg font-bold tracking-wider text-ink">{vehicle.kenteken ?? vehicle.vin}</p>
              <VehicleStatus vehicle={vehicle} />
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Vehicles.test.tsx`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Vehicles.tsx apps/web/src/routes/Vehicles.test.tsx
git commit -m "feat(web): migrate Vehicles page to violet design system primitives"
```

---

### Task 4: Full-suite verification and manual browser check

- [ ] **Step 1: Run the full test suite**

Run: `cd /opt/collabrains/apps/web && pnpm test`
Expected: all tests pass (previous 119 + this plan's 13 new tests = 132).

- [ ] **Step 2: Production build sanity check**

Run: `cd /opt/collabrains/apps/web && npx vite build`
Expected: build succeeds with no errors (does not invoke `tsc -b`, avoiding the pre-existing unrelated `apps/mobile` type conflict).

- [ ] **Step 3: Manual verification against real production data**

Tunnel to the live `web`/`api` containers exactly as done in Phase 20a/20b/20d1 (`ssh -f -N -L <port>:localhost:5173 -L 8000:localhost:8000 root@195.90.216.230`, checking `lsof -i :PORT` first for local collisions; widen `services/api/src/api/main.py`'s `allow_origins` temporarily if the local port isn't exactly 5173, and revert immediately after). Using Playwright, visit `/cases`, `/cases/:id`, `/vehicles` against real data and confirm: case status renders as a colored pill (green for open), the New Case form opens/submits with the new input styling, a real case's Documents/Tasks/Decisions/Vehicles sections render correctly (attach at least one real vehicle to a real case via the Attach flow to confirm the hand-styled `<select>` works end-to-end), and the Vehicles page's RDW lookup still works with a real kenteken.

- [ ] **Step 4: Revert any temporary CORS change and restart the api container if it was modified**

```bash
cd /opt/collabrains && git diff services/api/src/api/main.py
# if changed, revert:
git checkout services/api/src/api/main.py
docker compose restart api
```
