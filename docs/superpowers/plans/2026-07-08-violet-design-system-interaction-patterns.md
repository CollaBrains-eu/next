# Phase 20c: Violet Design System — Interaction Pattern Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the four interaction-pattern primitives from the Phase 20 spec that neither Phase 20a nor 20b built — bulk selection, filter chips, inline editing, and a split-view layout — as generic, page-agnostic components ready for Phase 20d to wire into real pages.

**Architecture:** Every component here is deliberately data-agnostic (generic over `T`, or driven entirely by primitive props) since none of them have a real page to live in yet — that wiring is Phase 20d. Unlike Phase 20a/20b, there is no natural "always-visible chrome" home for these in the current app shell, so this plan's verification is thorough component testing only; real-browser verification is explicitly deferred to Phase 20d when these get mounted with real data (inventing a throwaway demo page just to poke at these in a browser now would be exactly the kind of placeholder scaffolding this process avoids).

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4 (Phase 20a tokens), Vitest 3 + `@testing-library/react`, pnpm workspace.

## Scope

Builds on Phase 20a (branch `phase-20a-design-system-foundation`, PR #28) and Phase 20b (branch `phase-20b-layout-chrome`, PR #30) — neither merged to `main` yet. Uses Phase 20a's `Button`/tokens and Phase 20b's design conventions as-is.

This plan covers, and only covers: `useBulkSelection` + `BulkActionBar`, `FilterChips`, `InlineEditableText`, and `SplitView`.

Explicitly **not** in this plan — Phase 20d: applying any of Phase 20a/20b/20c's components to the 9 real pages (Documents, Cases, Vehicles, Entities, Chat, Legal, Tasks, Settings, Assistant). That rollout is large enough to need its own plan(s), likely split further per this project's own convention (e.g. Phase 16→17a-17d).

## Global Constraints

- Everything reuses Phase 20a's Tailwind theme tokens (`bg-surface`, `text-ink-2`, `border-edge`, `bg-accent`, `bg-accent-soft`, `text-danger`, `shadow-overlay`, `duration-fast`/`base`, `ease-spring`) — no new colors or motion values.
- Package manager is **pnpm**. Verify with `vite build` + `pnpm test`, not the full `pnpm build` (pre-existing, out-of-scope `apps/mobile` `@types/react@19` hoisting conflict documented in PR #28).
- No new dependencies.

## Environment Setup (read before Task 1)

Same as Phase 20a/20b — no local clone, only SSH:

```bash
ssh root@195.90.216.230   # apps/web lives at /opt/collabrains/apps/web
cd /opt/collabrains
git fetch origin --quiet
git checkout phase-20b-layout-chrome
git checkout -b phase-20c-interaction-patterns
cd apps/web
```

Branch from `phase-20b-layout-chrome`, **not** `main`. Run every `pnpm` command from `/opt/collabrains/apps/web`. Commit after each task. Push and open a PR at the end (do not merge).

---

### Task 1: `useBulkSelection` hook

**Files:**
- Create: `apps/web/src/hooks/useBulkSelection.ts`
- Test: `apps/web/src/hooks/useBulkSelection.test.ts`

**Interfaces:**
- Produces: `useBulkSelection<T>(getKey: (item: T) => string): { selectedKeys: Set<string>; isSelected: (item: T) => boolean; toggle: (item: T) => void; clear: () => void; selectedCount: number }`. Task 2's `BulkActionBar` consumes `selectedCount` and `clear`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/hooks/useBulkSelection.test.ts`:
```typescript
import { describe, expect, it } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useBulkSelection } from "./useBulkSelection";

interface Doc {
  id: string;
  name: string;
}

const docA: Doc = { id: "a", name: "factuur.pdf" };
const docB: Doc = { id: "b", name: "notes.txt" };

describe("useBulkSelection", () => {
  it("starts with nothing selected", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.isSelected(docA)).toBe(false);
  });

  it("toggle selects an item, and toggling again deselects it", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    act(() => result.current.toggle(docA));
    expect(result.current.isSelected(docA)).toBe(true);
    expect(result.current.selectedCount).toBe(1);
    act(() => result.current.toggle(docA));
    expect(result.current.isSelected(docA)).toBe(false);
    expect(result.current.selectedCount).toBe(0);
  });

  it("tracks multiple selected items independently", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    act(() => result.current.toggle(docA));
    act(() => result.current.toggle(docB));
    expect(result.current.selectedCount).toBe(2);
    expect(result.current.isSelected(docA)).toBe(true);
    expect(result.current.isSelected(docB)).toBe(true);
  });

  it("clear deselects everything", () => {
    const { result } = renderHook(() => useBulkSelection<Doc>((d) => d.id));
    act(() => result.current.toggle(docA));
    act(() => result.current.toggle(docB));
    act(() => result.current.clear());
    expect(result.current.selectedCount).toBe(0);
    expect(result.current.isSelected(docA)).toBe(false);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test useBulkSelection`
Expected: FAIL — `Cannot find module './useBulkSelection'`.

- [ ] **Step 3: Implement the hook**

Create `apps/web/src/hooks/useBulkSelection.ts`:
```typescript
import { useCallback, useState } from "react";

export function useBulkSelection<T>(getKey: (item: T) => string): {
  selectedKeys: Set<string>;
  isSelected: (item: T) => boolean;
  toggle: (item: T) => void;
  clear: () => void;
  selectedCount: number;
} {
  const [selectedKeys, setSelectedKeys] = useState<Set<string>>(new Set());

  const toggle = useCallback(
    (item: T) => {
      const key = getKey(item);
      setSelectedKeys((prev) => {
        const next = new Set(prev);
        if (next.has(key)) next.delete(key);
        else next.add(key);
        return next;
      });
    },
    [getKey]
  );

  const isSelected = useCallback((item: T) => selectedKeys.has(getKey(item)), [selectedKeys, getKey]);

  const clear = useCallback(() => setSelectedKeys(new Set()), []);

  return { selectedKeys, isSelected, toggle, clear, selectedCount: selectedKeys.size };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test useBulkSelection`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useBulkSelection.ts src/hooks/useBulkSelection.test.ts
git commit -m "feat: add useBulkSelection hook"
```

---

### Task 2: `BulkActionBar` component

**Files:**
- Create: `apps/web/src/components/ui/BulkActionBar.tsx`
- Test: `apps/web/src/components/ui/BulkActionBar.test.tsx`

**Interfaces:**
- Produces: `<BulkActionBar count: number onCancel: () => void actions: { label: string; onClick: () => void; variant?: "danger" }[] />`. Renders nothing when `count` is `0`. Phase 20d will pass real actions like `{ label: "Delete", onClick: ..., variant: "danger" }`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/BulkActionBar.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { BulkActionBar } from "./BulkActionBar";

describe("BulkActionBar", () => {
  it("renders nothing when count is 0", () => {
    render(<BulkActionBar count={0} onCancel={() => {}} actions={[]} />);
    expect(screen.queryByText(/selected/)).not.toBeInTheDocument();
  });

  it("shows the count when greater than 0", () => {
    render(<BulkActionBar count={3} onCancel={() => {}} actions={[]} />);
    expect(screen.getByText("3 selected")).toBeInTheDocument();
  });

  it("renders every action as a clickable button", () => {
    const onExport = vi.fn();
    const onDelete = vi.fn();
    render(
      <BulkActionBar
        count={2}
        onCancel={() => {}}
        actions={[
          { label: "Export", onClick: onExport },
          { label: "Delete", onClick: onDelete, variant: "danger" },
        ]}
      />
    );
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    expect(onExport).toHaveBeenCalledOnce();
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(onDelete).toHaveBeenCalledOnce();
  });

  it("applies danger styling to actions marked variant danger", () => {
    render(
      <BulkActionBar
        count={1}
        onCancel={() => {}}
        actions={[{ label: "Delete", onClick: () => {}, variant: "danger" }]}
      />
    );
    expect(screen.getByRole("button", { name: "Delete" })).toHaveClass("bg-danger");
  });

  it("calls onCancel when Cancel is clicked", () => {
    const onCancel = vi.fn();
    render(<BulkActionBar count={2} onCancel={onCancel} actions={[]} />);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test BulkActionBar`
Expected: FAIL — `Cannot find module './BulkActionBar'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/BulkActionBar.tsx`:
```tsx
interface BulkAction {
  label: string;
  onClick: () => void;
  variant?: "danger";
}

export function BulkActionBar({
  count,
  onCancel,
  actions,
}: {
  count: number;
  onCancel: () => void;
  actions: BulkAction[];
}) {
  if (count === 0) return null;

  return (
    <div className="fixed bottom-6 left-1/2 z-[60] flex -translate-x-1/2 items-center gap-3.5 rounded-2xl bg-ink px-4 py-2.5 text-sm text-surface shadow-overlay">
      <span>
        <span className="font-bold">{count}</span> selected
      </span>
      <button onClick={onCancel} className="text-surface/80 hover:text-surface">
        Cancel
      </button>
      {actions.map((action) => (
        <button
          key={action.label}
          onClick={action.onClick}
          className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition-colors duration-fast ${
            action.variant === "danger" ? "bg-danger text-white hover:opacity-90" : "bg-white/10 text-surface hover:bg-white/20"
          }`}
        >
          {action.label}
        </button>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test BulkActionBar`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/BulkActionBar.tsx src/components/ui/BulkActionBar.test.tsx
git commit -m "feat: add BulkActionBar component"
```

---

### Task 3: `FilterChips` component

**Files:**
- Create: `apps/web/src/components/ui/FilterChips.tsx`
- Test: `apps/web/src/components/ui/FilterChips.test.tsx`

**Interfaces:**
- Produces: `<FilterChips chips: {id: string; label: string}[] onRemove: (id: string) => void addOptions: {id: string; label: string}[] onAdd: (option: {id: string; label: string}) => void />`. The "+ Add filter" affordance is a small self-contained dropdown (this is the only current consumer of that pattern, so it isn't factored into a separate generic `Dropdown` primitive — YAGNI).

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/FilterChips.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { FilterChips } from "./FilterChips";

describe("FilterChips", () => {
  it("renders each chip's label with a remove button", () => {
    render(
      <FilterChips
        chips={[{ id: "status-ready", label: "Status: Ready" }]}
        onRemove={() => {}}
        addOptions={[]}
        onAdd={() => {}}
      />
    );
    expect(screen.getByText("Status: Ready")).toBeInTheDocument();
  });

  it("calls onRemove with the chip's id when its remove button is clicked", () => {
    const onRemove = vi.fn();
    render(
      <FilterChips
        chips={[{ id: "status-ready", label: "Status: Ready" }]}
        onRemove={onRemove}
        addOptions={[]}
        onAdd={() => {}}
      />
    );
    fireEvent.click(screen.getByLabelText("Remove Status: Ready"));
    expect(onRemove).toHaveBeenCalledWith("status-ready");
  });

  it("opens the add-filter menu and lists addOptions when the add button is clicked", () => {
    render(
      <FilterChips
        chips={[]}
        onRemove={() => {}}
        addOptions={[{ id: "type-pdf", label: "Type: PDF" }]}
        onAdd={() => {}}
      />
    );
    expect(screen.queryByText("Type: PDF")).not.toBeInTheDocument();
    fireEvent.click(screen.getByText("+ Add filter"));
    expect(screen.getByText("Type: PDF")).toBeInTheDocument();
  });

  it("calls onAdd with the chosen option and closes the menu", () => {
    const onAdd = vi.fn();
    render(
      <FilterChips
        chips={[]}
        onRemove={() => {}}
        addOptions={[{ id: "type-pdf", label: "Type: PDF" }]}
        onAdd={onAdd}
      />
    );
    fireEvent.click(screen.getByText("+ Add filter"));
    fireEvent.click(screen.getByText("Type: PDF"));
    expect(onAdd).toHaveBeenCalledWith({ id: "type-pdf", label: "Type: PDF" });
    expect(screen.queryByText("Type: PDF")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test FilterChips`
Expected: FAIL — `Cannot find module './FilterChips'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/FilterChips.tsx`:
```tsx
import { useState } from "react";

interface FilterOption {
  id: string;
  label: string;
}

export function FilterChips({
  chips,
  onRemove,
  addOptions,
  onAdd,
}: {
  chips: FilterOption[];
  onRemove: (id: string) => void;
  addOptions: FilterOption[];
  onAdd: (option: FilterOption) => void;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {chips.map((chip) => (
        <span
          key={chip.id}
          className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft py-1 pl-3 pr-1.5 text-xs font-semibold text-accent"
        >
          {chip.label}
          <button
            aria-label={`Remove ${chip.label}`}
            onClick={() => onRemove(chip.id)}
            className="flex h-4 w-4 items-center justify-center rounded-full bg-accent/20 text-[10px] hover:bg-accent/30"
          >
            ✕
          </button>
        </span>
      ))}
      <div className="relative">
        <button
          onClick={() => setMenuOpen((prev) => !prev)}
          className="rounded-full border border-dashed border-edge px-3 py-1 text-xs font-semibold text-ink-2 transition-colors duration-fast hover:border-accent hover:text-accent"
        >
          + Add filter
        </button>
        {menuOpen && (
          <div className="absolute left-0 top-full z-20 mt-1.5 min-w-[170px] rounded-xl border border-edge bg-surface p-1.5 shadow-overlay">
            {addOptions.map((option) => (
              <div
                key={option.id}
                onClick={() => {
                  onAdd(option);
                  setMenuOpen(false);
                }}
                className="cursor-pointer rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-hover hover:text-ink"
              >
                {option.label}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test FilterChips`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/FilterChips.tsx src/components/ui/FilterChips.test.tsx
git commit -m "feat: add FilterChips component"
```

---

### Task 4: `InlineEditableText` component

**Files:**
- Create: `apps/web/src/components/ui/InlineEditableText.tsx`
- Test: `apps/web/src/components/ui/InlineEditableText.test.tsx`

**Interfaces:**
- Produces: `<InlineEditableText value: string onSave: (newValue: string) => void />`. Matches the validated prototype exactly: click the pencil → input appears pre-filled → Enter or blur commits (calls `onSave`, only if the trimmed value is non-empty) → Escape cancels without calling `onSave`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/InlineEditableText.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { InlineEditableText } from "./InlineEditableText";

describe("InlineEditableText", () => {
  it("renders the value as plain text with an edit button", () => {
    render(<InlineEditableText value="factuur.pdf" onSave={() => {}} />);
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
    expect(screen.getByLabelText("Edit")).toBeInTheDocument();
  });

  it("clicking Edit shows an input pre-filled with the current value", () => {
    render(<InlineEditableText value="factuur.pdf" onSave={() => {}} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    expect(screen.getByRole("textbox")).toHaveValue("factuur.pdf");
  });

  it("Enter commits the new value and calls onSave, reverting to text display", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "renamed.pdf" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSave).toHaveBeenCalledWith("renamed.pdf");
    expect(screen.getByText("renamed.pdf")).toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("blur also commits the new value", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "renamed.pdf" } });
    fireEvent.blur(input);
    expect(onSave).toHaveBeenCalledWith("renamed.pdf");
  });

  it("Escape cancels without calling onSave and reverts to the original value", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "renamed.pdf" } });
    fireEvent.keyDown(input, { key: "Escape" });
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
  });

  it("does not call onSave with an empty/whitespace-only value", () => {
    const onSave = vi.fn();
    render(<InlineEditableText value="factuur.pdf" onSave={onSave} />);
    fireEvent.click(screen.getByLabelText("Edit"));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "   " } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onSave).not.toHaveBeenCalled();
    expect(screen.getByText("factuur.pdf")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test InlineEditableText`
Expected: FAIL — `Cannot find module './InlineEditableText'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/InlineEditableText.tsx`:
```tsx
import { useRef, useState } from "react";

export function InlineEditableText({ value, onSave }: { value: string; onSave: (newValue: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(value);
  const [displayValue, setDisplayValue] = useState(value);
  const committedRef = useRef(false);

  function startEditing() {
    setDraft(displayValue);
    committedRef.current = false;
    setEditing(true);
  }

  function commit() {
    if (committedRef.current) return;
    committedRef.current = true;
    const trimmed = draft.trim();
    if (trimmed) {
      setDisplayValue(trimmed);
      onSave(trimmed);
    }
    setEditing(false);
  }

  function cancel() {
    committedRef.current = true;
    setEditing(false);
  }

  if (!editing) {
    return (
      <span className="inline-flex items-center gap-1.5">
        <span>{displayValue}</span>
        <button
          aria-label="Edit"
          onClick={startEditing}
          className="rounded-md p-0.5 text-ink-3 transition-colors duration-fast hover:bg-hover hover:text-accent"
        >
          ✎
        </button>
      </span>
    );
  }

  return (
    <input
      autoFocus
      value={draft}
      onChange={(event) => setDraft(event.target.value)}
      onBlur={commit}
      onKeyDown={(event) => {
        if (event.key === "Enter") {
          event.preventDefault();
          commit();
        } else if (event.key === "Escape") {
          cancel();
        }
      }}
      className="rounded-lg border border-accent bg-surface px-2 py-1 text-sm text-ink outline-none ring-2 ring-accent-soft"
    />
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test InlineEditableText`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/InlineEditableText.tsx src/components/ui/InlineEditableText.test.tsx
git commit -m "feat: add InlineEditableText component"
```

---

### Task 5: `SplitView` layout component

**Files:**
- Create: `apps/web/src/components/ui/SplitView.tsx`
- Test: `apps/web/src/components/ui/SplitView.test.tsx`

**Interfaces:**
- Produces: `<SplitView enabled: boolean list: ReactNode detail: ReactNode | null />`. `enabled` is controlled by the consumer (e.g. a checkbox on the page using it) — `SplitView` itself owns no toggle UI, only the layout. Phase 20d will wire a real toggle plus real `detail` content on whichever page adopts it, as an alternative to that page's `Drawer` overlay.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/SplitView.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SplitView } from "./SplitView";

describe("SplitView", () => {
  it("renders only the list when disabled", () => {
    render(<SplitView enabled={false} list={<p>The list</p>} detail={<p>The detail</p>} />);
    expect(screen.getByText("The list")).toBeInTheDocument();
    expect(screen.queryByText("The detail")).not.toBeInTheDocument();
  });

  it("renders list and detail side by side when enabled", () => {
    render(<SplitView enabled list={<p>The list</p>} detail={<p>The detail</p>} />);
    expect(screen.getByText("The list")).toBeInTheDocument();
    expect(screen.getByText("The detail")).toBeInTheDocument();
  });

  it("shows a placeholder message when enabled but detail is null", () => {
    render(<SplitView enabled list={<p>The list</p>} detail={null} />);
    expect(screen.getByText(/select an item to preview it here/i)).toBeInTheDocument();
  });

  it("does not show the placeholder when disabled, even with a null detail", () => {
    render(<SplitView enabled={false} list={<p>The list</p>} detail={null} />);
    expect(screen.queryByText(/select an item to preview it here/i)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test SplitView`
Expected: FAIL — `Cannot find module './SplitView'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/SplitView.tsx`:
```tsx
import type { ReactNode } from "react";

export function SplitView({
  enabled,
  list,
  detail,
}: {
  enabled: boolean;
  list: ReactNode;
  detail: ReactNode | null;
}) {
  if (!enabled) return <>{list}</>;

  return (
    <div className="flex gap-0 divide-x divide-edge">
      <div className="flex-1 overflow-y-auto pr-5">{list}</div>
      <div className="w-[260px] flex-shrink-0 overflow-y-auto pl-5">
        {detail ?? <p className="text-center text-sm text-ink-3">Select an item to preview it here</p>}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test SplitView`
Expected: `4 passed`.

- [ ] **Step 5: Run the full suite**

Run: `pnpm test`
Expected: all tests across all three phases (20a + 20b + 20c) pass together.

- [ ] **Step 6: Verify the build compiles**

Run: `npx vite build`
Expected: succeeds (same `tsc`-bypassing approach as Phase 20a/20b, for the same pre-existing, out-of-scope `apps/mobile` type conflict).

- [ ] **Step 7: Commit**

```bash
git add src/components/ui/SplitView.tsx src/components/ui/SplitView.test.tsx
git commit -m "feat: add SplitView layout component"
```

---

## Self-Review

**Spec coverage:** bulk selection (row checkboxes → floating action bar) → Tasks 1-2 (`useBulkSelection` + `BulkActionBar`). Filter chips (add/remove, dropdown-to-add) → Task 3. Inline editing (pencil → edit → save-flash-equivalent commit) → Task 4. Split-view layout → Task 5. Everything else from the spec (tokens, primitives, layout/chrome, and the 9-page rollout) was covered by Phase 20a, 20b, or remains Phase 20d — all explicitly out of scope here.

**Placeholder scan:** no TBD/TODO; every step has complete, real code. No throwaway demo page was added just to make manual browser verification possible — that verification is honestly deferred to Phase 20d, where these components get real data and a real home in the app, rather than inventing scaffolding here.

**Type consistency:** `useBulkSelection<T>`'s returned shape (`selectedKeys`, `isSelected`, `toggle`, `clear`, `selectedCount`) matches between Task 1's test and implementation; `selectedCount`/`clear` are the two fields `BulkActionBar` (Task 2) is documented to consume. `BulkAction`'s `{label, onClick, variant?}` shape matches between Task 2's test and implementation. `FilterOption`'s `{id, label}` shape is used identically for both `chips` and `addOptions` in Task 3. `InlineEditableText`'s `onSave: (newValue: string) => void` signature matches between Task 4's test and implementation.
