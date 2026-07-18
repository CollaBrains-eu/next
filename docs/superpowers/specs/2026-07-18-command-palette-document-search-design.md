# Command Palette Document Search — Design

## Status
Proposed

## Context

`apps/web/src/components/CommandCenter.tsx` builds `items` synchronously and exclusively from `NAV_ITEMS` (`apps/web/src/lib/navigation.ts`), mapped to `{ label: "Go to X", onSelect }`. `apps/web/src/components/ui/CommandPalette.tsx` is a flat, presentational list: `interface CommandItem { label: string; onSelect: () => void }`, client-side substring filter on `label`, no grouping, no async concept, no loading state. Its own placeholder text (`"Search documents, cases, vehicles…"`) already promises more than the component delivers today — only nav items exist.

A document search backend already exists and is already wired into the frontend: `GET /search?q=&limit=` (`search_router` in `services/api/src/api/documents.py:511-535`) → `hybrid_search()` (`services/api/src/api/search_service.py`), owner-scoped, `q` has `min_length=1`, `limit` defaults to 10/max 50. `apps/web/src/lib/api.ts` already has a typed wrapper: `search(query: string): Promise<SearchResult[]>` (`SearchResult = { chunk_id, document_id, document_title, content, score }`), already consumed once in `Workspace.tsx`. `hybrid_search` calls `embed_text()` (Ollama, synchronous, not free) — not safe to call on every keystroke.

No debounce hook or pattern exists in the frontend. The closest timing precedent is `apps/web/src/lib/toast.tsx`'s bare `setTimeout`/cleanup, but the `hooks/` directory's actual convention is small single-purpose hooks (`useBulkSelection`, `useEscapeToClose`, `useClickOutside`, `useDarkMode`, `useDateFormat`) — a `useDebouncedValue` hook fits that convention better than inlining `setTimeout` logic directly into `CommandCenter`.

## Goals

1. Typing 2+ characters into Cmd+K, after a short pause, shows matching document titles/snippets under a "Documents" group, below or alongside the existing "Navigation" group.
2. Selecting a document result navigates to `/documents/:id` (route already exists in `App.tsx`).
3. No behavior change to the existing nav-only filtering (must not regress `CommandPalette.test.tsx`/`CommandCenter.test.tsx`, both of which construct `items` as bare `{label, onSelect}[]`).
4. `CommandPalette` stays presentational; the fetch/debounce orchestration lives in `CommandCenter`, matching the existing split of responsibility (`CommandCenter` = smart/stateful, `CommandPalette` = dumb/reusable).

## Non-goals

- Searching cases/vehicles by content — only `/search` (documents) exists as a backend capability today; the placeholder text overpromising is a pre-existing cosmetic issue, not something this pass needs to fully resolve (though the copy will now be *more* true than before).
- Redesigning `CommandPalette`'s internals (no controlled/uncontrolled rewrite, no virtualization, no new keyboard model).
- Full-text result pagination or a "view all results" link — top `limit=5` is enough for a palette.

## Design

### `apps/web/src/hooks/useDebouncedValue.ts` (new file)

```typescript
import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}
```

### `CommandPalette.tsx` — minimal extension

`CommandItem` gains two optional fields (backward-compatible with existing bare `{label, onSelect}` items and their tests):

```typescript
export interface CommandItem {
  label: string;
  onSelect: () => void;
  group?: "navigation" | "documents";
  description?: string; // e.g. a matched content snippet, rendered as a secondary line
}
```

New optional props on `CommandPalette`:

```typescript
{
  asyncItems?: CommandItem[];   // pre-filtered server-side; not re-filtered by the local substring match
  asyncLoading?: boolean;
  onQueryChange?: (query: string) => void; // fired on every keystroke, in addition to existing internal setQuery
}
```

`filtered` becomes `items.filter(...)` (unchanged substring logic) concatenated with `asyncItems ?? []` for both rendering and the `ArrowUp`/`ArrowDown`/`Enter` index math (no behavior change when `asyncItems` is omitted — existing tests keep passing). When both groups are non-empty, render two small section headers (reuse `DataTable`'s header styling: `text-[11px] font-semibold uppercase tracking-wide text-ink-3`) — `t("commandCenter.groupNavigation")` / `t("commandCenter.groupDocuments")`. When `asyncLoading` is true and the query is long enough to have triggered a search, show a lightweight `"Searching…"` row under the Documents header (no new Spinner component needed/exists in this codebase).

### `CommandCenter.tsx` — orchestration

```typescript
const [query, setQuery] = useState("");
const [docItems, setDocItems] = useState<CommandItem[]>([]);
const [searching, setSearching] = useState(false);
const debouncedQuery = useDebouncedValue(query, 300);
const latestRequestId = useRef(0);

useEffect(() => {
  if (overlay !== "palette") {
    setQuery("");
    setDocItems([]);
    return;
  }
}, [overlay]);

useEffect(() => {
  if (debouncedQuery.trim().length < 2) {
    setDocItems([]);
    return;
  }
  const requestId = ++latestRequestId.current;
  setSearching(true);
  search(debouncedQuery.trim(), 5)
    .then((results) => {
      if (requestId !== latestRequestId.current) return; // stale response guard, request() has no AbortController
      setDocItems(
        results.map((r) => ({
          label: r.document_title,
          description: r.content.slice(0, 120),
          group: "documents" as const,
          onSelect: () => navigate(`/documents/${r.document_id}`),
        }))
      );
    })
    .finally(() => {
      if (requestId === latestRequestId.current) setSearching(false);
    });
}, [debouncedQuery, navigate]);
```

`search()` in `apps/web/src/lib/api.ts` currently only takes `query: string` (no `limit`); it needs a second optional param (`limit = 10`) threaded through to `` `/search?q=${encodeURIComponent(query)}&limit=${limit}` `` — a one-line addition, backend already accepts `limit`.

`<CommandPalette>` render call gains `asyncItems={docItems}` `asyncLoading={searching}` `onQueryChange={setQuery}`.

## Data flow

Keystroke → `CommandPalette`'s own `query` state updates (drives the instant nav-item filter, unchanged) and calls `onQueryChange` → `CommandCenter.query` updates → 300ms after the last keystroke, `debouncedQuery` updates → if `debouncedQuery.length >= 2`, fetch `/search?q=&limit=5` → map `SearchResult[]` to `CommandItem[]` tagged `group: "documents"` → merged into the palette's combined list → click/Enter → `navigate("/documents/" + document_id)` and palette closes (existing `runSelection` behavior, unchanged).

## Testing

- `useDebouncedValue.test.ts` (new): value updates only after the delay elapses; rapid successive updates reset the timer (use `vi.useFakeTimers()`).
- `CommandPalette.test.tsx`: extend with `asyncItems`/`asyncLoading` cases — renders a "Documents" group header only when `asyncItems` is non-empty; `asyncLoading` shows the searching indicator; arrow-key navigation spans both groups.
- `CommandCenter.test.tsx`: mock `search()` from `../lib/api`; typing 1 char does not call it; typing 2+ chars calls it only after the debounce delay (fake timers); a stale in-flight response (resolved after a newer query was typed) is discarded; selecting a document result calls `navigate("/documents/:id")`.
