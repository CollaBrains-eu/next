# Phase 20d3: Entities & EntityGraph Page Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate `Entities.tsx` and `EntityGraph.tsx` from raw Tailwind slate classes to the violet design system tokens (light/dark), continuing Phase 20's page-by-page rollout after Documents (20d1) and Cases/Vehicles (20d2).

**Architecture:** Chrome-only token migration — headings, body text, borders, backgrounds, and the search/filter inputs move to the `ink`/`ink-2`/`ink-3`/`edge`/`surface`/`danger` token classes. Data-fetching logic is untouched.

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4 (violet token theme), Vitest 3, @testing-library/react, react-router-dom.

## Global Constraints

- Do not modify `apps/web/src/lib/api.ts` — only real, existing exports may be used (`EntityOut`, `EntityGraphOut`, `GraphNode`, `GraphEdge`, `listEntities`, `getEntityGraph`, `ApiError`).
- `Entities.tsx`'s `TypeBadge` (person/organization/location/other) is a **categorical taxonomy badge, not a status badge** — it does not map onto the design system `Badge` component's 4 semantic variants (default/success/warning/danger). Keep it as a distinct hand-rolled component, but add `dark:` Tailwind variants to each category color so it respects dark mode, instead of switching it to the `Badge` primitive.
- `EntityGraph.tsx`'s SVG node/edge colors (`TYPE_COLORS`: person `#2563eb`, organization `#7c3aed`, location `#16a34a`, other `#64748b`) are a **categorical data-visualization palette**, not page chrome. They stay as hardcoded hex values — reworking an SVG diagram's semantic color-by-category system into CSS custom properties is out of scope for this pass. Only the surrounding page chrome (heading, back-link, loading/error/empty text, container border/background) moves to tokens.
- Verify each task with `npx vite build` (from `apps/web`) + `pnpm test` (not full `pnpm build` — pre-existing `apps/mobile`/`apps/web` `@types/react` hoisting conflict, documented in PR #28, remains out of scope).
- Branch this plan's implementation off `phase-20d3-plan-entities-migration` (this plan's own branch), which itself sits on `phase-20d2-cases-vehicles-migration` — nothing is merged to `main` yet.
- Commit after each task. Push and open a PR against `main` at the end (do not merge).

---

### Task 1: Migrate Entities.tsx

**Files:**
- Modify: `apps/web/src/routes/Entities.tsx`
- Test: `apps/web/src/routes/Entities.test.tsx` (new)

**Interfaces:**
- Consumes: `listEntities(q?, entityType?): Promise<EntityOut[]>`, `EntityOut { id, name, entity_type, ... }` from `../lib/api` (unchanged).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/Entities.test.tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Entities from "./Entities";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    listEntities: vi.fn(),
  };
});

const ENTITIES: api.EntityOut[] = [
  { id: "e1", name: "Jane Smith", entity_type: "person" } as api.EntityOut,
  { id: "e2", name: "Acme Corp", entity_type: "organization" } as api.EntityOut,
];

function renderPage() {
  return render(
    <MemoryRouter>
      <Entities />
    </MemoryRouter>
  );
}

describe("Entities", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.listEntities).mockResolvedValue(ENTITIES);
  });

  it("renders entities with their type badge", async () => {
    renderPage();
    expect(await screen.findByText("Jane Smith")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("person")).toBeInTheDocument();
    expect(screen.getByText("organization")).toBeInTheDocument();
  });

  it("shows an empty message when there are no entities", async () => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    renderPage();
    expect(await screen.findByText("No entities found.")).toBeInTheDocument();
  });

  it("re-queries listEntities when the search box changes", async () => {
    renderPage();
    await screen.findByText("Jane Smith");
    fireEvent.change(screen.getByPlaceholderText("Search entities…"), { target: { value: "Jane" } });
    await waitFor(() => expect(api.listEntities).toHaveBeenLastCalledWith("Jane", undefined));
  });

  it("re-queries listEntities when the type filter changes", async () => {
    renderPage();
    await screen.findByText("Jane Smith");
    fireEvent.change(screen.getByDisplayValue("All types"), { target: { value: "person" } });
    await waitFor(() => expect(api.listEntities).toHaveBeenLastCalledWith(undefined, "person"));
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Entities.test.tsx`
Expected: FAIL (file compiles against the current component; confirms the test harness catches drift once Step 3 rewrites the component).

- [ ] **Step 3: Rewrite Entities.tsx**

```tsx
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { listEntities, type EntityOut } from "../lib/api";

const TYPE_STYLES: Record<string, string> = {
  person: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  organization: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  location: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  other: "bg-hover text-ink-2",
};

function TypeBadge({ type }: { type: string }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${TYPE_STYLES[type] ?? TYPE_STYLES.other}`}>
      {type}
    </span>
  );
}

export default function Entities() {
  const [entities, setEntities] = useState<EntityOut[]>([]);
  const [q, setQ] = useState("");
  const [entityType, setEntityType] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    listEntities(q || undefined, entityType || undefined)
      .then(setEntities)
      .finally(() => setLoading(false));
  }, [q, entityType]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
  }

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-2xl font-semibold text-ink">Entities</h1>
        <p className="mt-1 text-sm text-ink-2">
          People, organizations, and locations extracted from your documents. Select one to explore its
          relationships.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search entities…"
          className="w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft"
        />
        <select
          value={entityType}
          onChange={(e) => setEntityType(e.target.value)}
          className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
        >
          <option value="">All types</option>
          <option value="person">Person</option>
          <option value="organization">Organization</option>
          <option value="location">Location</option>
          <option value="other">Other</option>
        </select>
      </form>

      {loading ? (
        <p className="text-ink-3">Loading…</p>
      ) : entities.length === 0 ? (
        <p className="text-ink-3">No entities found.</p>
      ) : (
        <div className="flex flex-col divide-y divide-edge rounded-2xl border border-edge bg-surface">
          {entities.map((entity) => (
            <Link
              key={entity.id}
              to={`/entities/${entity.id}`}
              className="flex items-center justify-between px-4 py-3 transition-colors duration-fast hover:bg-hover"
            >
              <span className="text-sm font-medium text-ink">{entity.name}</span>
              <TypeBadge type={entity.entity_type} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/Entities.test.tsx`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/Entities.tsx apps/web/src/routes/Entities.test.tsx
git commit -m "feat(web): migrate Entities page to violet design system tokens"
```

---

### Task 2: Migrate EntityGraph.tsx chrome

**Files:**
- Modify: `apps/web/src/routes/EntityGraph.tsx`
- Test: `apps/web/src/routes/EntityGraph.test.tsx` (new)

**Interfaces:**
- Consumes: `getEntityGraph(id): Promise<EntityGraphOut>`, `EntityGraphOut { center: GraphNode, nodes: GraphNode[], edges: GraphEdge[] }`, `GraphNode { id, name, entity_type }`, `GraphEdge { source, target, relationship_type }`, `ApiError` from `../lib/api` (unchanged).
- Produces: nothing consumed by later tasks (leaf page).

- [ ] **Step 1: Write the failing test**

```tsx
// apps/web/src/routes/EntityGraph.test.tsx
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import EntityGraph from "./EntityGraph";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getEntityGraph: vi.fn(),
  };
});

const GRAPH: api.EntityGraphOut = {
  center: { id: "e1", name: "Jane Smith", entity_type: "person" },
  nodes: [{ id: "e2", name: "Acme Corp", entity_type: "organization" }],
  edges: [{ source: "e1", target: "e2", relationship_type: "works at", document_id: null }],
};

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/entities/e1"]}>
      <Routes>
        <Route path="/entities/:id" element={<EntityGraph />} />
      </Routes>
    </MemoryRouter>
  );
}

describe("EntityGraph", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getEntityGraph).mockResolvedValue(GRAPH);
  });

  it("renders the center entity name and relationship count", async () => {
    renderPage();
    expect(await screen.findByText("Jane Smith")).toBeInTheDocument();
    expect(screen.getByText("person · 1 direct relationship")).toBeInTheDocument();
  });

  it("renders related node names", async () => {
    renderPage();
    await screen.findByText("Jane Smith");
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
  });

  it("shows an empty message when there are no relationships", async () => {
    vi.mocked(api.getEntityGraph).mockResolvedValue({ ...GRAPH, nodes: [], edges: [] });
    renderPage();
    expect(await screen.findByText("No known relationships for this entity yet.")).toBeInTheDocument();
  });

  it("shows an error message on failure", async () => {
    vi.mocked(api.getEntityGraph).mockRejectedValue(new api.ApiError(500, "Graph boom"));
    renderPage();
    expect(await screen.findByText("Graph boom")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/EntityGraph.test.tsx`
Expected: FAIL (file compiles against the current component; confirms the test harness catches drift once Step 3 rewrites the component).

- [ ] **Step 3: Rewrite EntityGraph.tsx chrome**

```tsx
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, getEntityGraph, type EntityGraphOut } from "../lib/api";

const TYPE_COLORS: Record<string, string> = {
  person: "#2563eb",
  organization: "#7c3aed",
  location: "#16a34a",
  other: "#64748b",
};

const WIDTH = 700;
const HEIGHT = 480;
const CENTER = { x: WIDTH / 2, y: HEIGHT / 2 };
const RADIUS = 170;
const NODE_RADIUS = 8;

function nodeColor(entityType: string): string {
  return TYPE_COLORS[entityType] ?? TYPE_COLORS.other;
}

export default function EntityGraph() {
  const { id } = useParams<{ id: string }>();
  const [graph, setGraph] = useState<EntityGraphOut | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    setGraph(null);
    setError(null);
    getEntityGraph(id)
      .then(setGraph)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load graph"));
  }, [id]);

  if (error) {
    return (
      <div>
        <Link to="/entities" className="text-sm text-ink-2 hover:text-ink">
          ← Back to entities
        </Link>
        <p className="mt-4 text-danger">{error}</p>
      </div>
    );
  }

  if (!graph) return <p className="text-ink-3">Loading…</p>;

  const positions = new Map<string, { x: number; y: number }>();
  positions.set(graph.center.id, CENTER);
  graph.nodes.forEach((node, i) => {
    const angle = (2 * Math.PI * i) / Math.max(graph.nodes.length, 1) - Math.PI / 2;
    positions.set(node.id, {
      x: CENTER.x + RADIUS * Math.cos(angle),
      y: CENTER.y + RADIUS * Math.sin(angle),
    });
  });

  return (
    <div className="flex flex-col gap-4">
      <div>
        <Link to="/entities" className="text-sm text-ink-2 hover:text-ink">
          ← Back to entities
        </Link>
        <h1 className="mt-2 text-2xl font-semibold text-ink">{graph.center.name}</h1>
        <p className="text-sm text-ink-2">
          {graph.center.entity_type} · {graph.nodes.length} direct relationship{graph.nodes.length === 1 ? "" : "s"}
        </p>
      </div>

      {graph.nodes.length === 0 ? (
        <p className="text-ink-3">No known relationships for this entity yet.</p>
      ) : (
        <div className="overflow-x-auto rounded-2xl border border-edge bg-surface">
          <svg width={WIDTH} height={HEIGHT} viewBox={`0 0 ${WIDTH} ${HEIGHT}`}>
            <defs>
              <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                <path d="M0,0 L10,5 L0,10 z" fill="#94a3b8" />
              </marker>
            </defs>

            {graph.edges.map((edge, i) => {
              const from = positions.get(edge.source);
              const to = positions.get(edge.target);
              if (!from || !to) return null;
              const mid = { x: (from.x + to.x) / 2, y: (from.y + to.y) / 2 };
              return (
                <g key={i} style={{ pointerEvents: "none" }}>
                  <line
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke="#94a3b8"
                    strokeWidth={1.5}
                    markerEnd="url(#arrow)"
                  />
                  <text x={mid.x} y={mid.y} textAnchor="middle" fontSize={10} fill="#64748b" className="select-none">
                    {edge.relationship_type}
                  </text>
                </g>
              );
            })}

            {graph.nodes.map((node) => {
              const pos = positions.get(node.id)!;
              return (
                <Link key={node.id} to={`/entities/${node.id}`}>
                  <g className="cursor-pointer">
                    <rect
                      x={pos.x - 45}
                      y={pos.y - NODE_RADIUS - 2}
                      width={90}
                      height={NODE_RADIUS + 30}
                      fill="transparent"
                    />
                    <circle cx={pos.x} cy={pos.y} r={NODE_RADIUS} fill={nodeColor(node.entity_type)} />
                    <text x={pos.x} y={pos.y + NODE_RADIUS + 14} textAnchor="middle" fontSize={11} fill="#1e293b">
                      {node.name.length > 24 ? `${node.name.slice(0, 24)}…` : node.name}
                    </text>
                  </g>
                </Link>
              );
            })}

            <circle cx={CENTER.x} cy={CENTER.y} r={NODE_RADIUS + 2} fill={nodeColor(graph.center.entity_type)} stroke="#0f172a" strokeWidth={2} />
            <text x={CENTER.x} y={CENTER.y + NODE_RADIUS + 18} textAnchor="middle" fontSize={12} fontWeight={600} fill="#0f172a">
              {graph.center.name}
            </text>
          </svg>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /opt/collabrains/apps/web && pnpm exec vitest run src/routes/EntityGraph.test.tsx`
Expected: PASS (4/4)

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains && git add apps/web/src/routes/EntityGraph.tsx apps/web/src/routes/EntityGraph.test.tsx
git commit -m "feat(web): migrate EntityGraph page chrome to violet design system tokens"
```

---

### Task 3: Full-suite verification and manual browser check

- [ ] **Step 1: Run the full test suite**

Run: `cd /opt/collabrains/apps/web && pnpm test`
Expected: all tests pass (previous 132 + this plan's 8 new tests = 140).

- [ ] **Step 2: Production build sanity check**

Run: `cd /opt/collabrains/apps/web && npx vite build`
Expected: build succeeds with no errors.

- [ ] **Step 3: Manual verification against real production data**

Tunnel to the live `web`/`api` containers exactly as done in prior phases (check `lsof -i :PORT` first for local collisions; widen `allow_origins` in `services/api/src/api/main.py` temporarily if needed, revert immediately after). Using Playwright, visit `/entities` and a real entity's `/entities/:id` graph page against real data and confirm: the entity list renders with correctly colored type badges (including in dark mode via the `⌘D`/moon-icon toggle), search and type-filter re-query the real API, and the relationship graph SVG renders real nodes/edges with readable labels.

- [ ] **Step 4: Revert any temporary CORS change and restart the api container if it was modified**

```bash
cd /opt/collabrains && git diff services/api/src/api/main.py
# if changed, revert:
git checkout services/api/src/api/main.py
docker compose restart api
```
