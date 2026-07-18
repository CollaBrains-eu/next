# Cases List-View Polish — Design

## Status
Proposed

## Context

`apps/web/src/routes/Cases.tsx` is a card grid only (`grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3`) — no search, filter, sort, table view, or bulk-select. `apps/web/src/routes/Workspace.tsx` (documents) already solved this exact problem with fully generic, stateless-controlled building blocks that Cases can reuse with zero new abstraction:

- `DataTable<T>` (`apps/web/src/components/ui/DataTable.tsx`) — `columns: Column<T>[]` with `sortable`/`sortValue`/`render`, client-side sort + pagination (`pageSize=10` default), no server params.
- `FilterChips` (`apps/web/src/components/ui/FilterChips.tsx`) — fully controlled (`chips`, `onRemove`, `addOptions`, `onAdd`); caller owns the filter `Set`/array.
- `useBulkSelection<T>` (`apps/web/src/hooks/useBulkSelection.ts`) — `getKey` in, `{isSelected, toggle, clear, selectedCount, selectedKeys}` out.
- `BulkActionBar` (`apps/web/src/components/ui/BulkActionBar.tsx`) — `{count, onCancel, actions}`.

`CaseOut` today: `{id, name, description, status, created_at}` (`services/api/src/api/cases_router.py`). `GET /cases` → `list_cases()` (`services/api/src/api/cases.py:28-44`) takes no query params, does one fixed query (owned + accepted-member cases), no pagination. `Document.case_id` is a direct FK, so `document_count` via one `GROUP BY` join is cheap. `CaseMember` exists with `status="accepted"` filtering already used elsewhere (`is_case_member`), so `member_count` (accepted only) is equally cheap. There is no `updated_at`/activity-tracking column anywhere on `Case`, `Document`, `Task`, or `Decision` — a real `last_activity` would need either a new column maintained on every child-table write, or an expensive per-case multi-table `MAX()` scan; out of scope for a "list-view polish" ask.

The status vocabulary is confirmed narrow: `update_case_endpoint` only validates `status in ("open", "closed")`. `Cases.tsx` already renders a `Badge` keyed on exactly these two values.

`downloadCasesCsv()`/`GET /cases/export.csv` already exists and is already wired into `Cases.tsx` — nothing to add there.

## Goals

1. Add search-by-name/description, status filter, sort, and a table view to Cases — reusing `DataTable`, `FilterChips`, `useBulkSelection`, `BulkActionBar` exactly as `Workspace.tsx` does, not a new pattern.
2. `CaseOut` gains `document_count` and `member_count` (cheap aggregate joins) so the table/cards can show them.
3. Table view as a **toggle alongside** the existing card grid (not a replacement) — the card grid is Cases' current default and nothing in the ask requires removing it.

## Non-goals

- `last_activity` — explicitly deferred; no `updated_at` column exists on any related table and adding one plus backfilling/maintaining it across every write path is a much larger change than "list-view polish" implies.
- Server-side search/filter/pagination on `GET /cases` — dataset is small per user (no pagination exists today and none is needed). Client-side, matching `Workspace.tsx`'s exact pattern, is both simpler and consistent with the sibling page.
- Bulk actions beyond bulk-close/bulk-reopen — bulk delete is riskier (cascades to case membership) and already exists as a single-item confirm flow; not extended to bulk here.

## Design

### Recommendation: client-side, `CaseOut` gains 2 fields, table is a toggle

**Search/filter/sort: client-side.** `GET /cases` returns everything for the user already; adding query params would duplicate logic the frontend needs anyway once results are in memory.

**`CaseOut` extension:**

```python
# cases_router.py
class CaseOut(BaseModel):
    id: UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    document_count: int
    member_count: int
```

```python
# cases.py — list_cases(), aggregate via subqueries (existing ownership/membership filter untouched):
document_counts = (
    select(Document.case_id, func.count().label("n"))
    .where(Document.case_id.is_not(None))
    .group_by(Document.case_id)
    .subquery()
)
member_counts = (
    select(CaseMember.case_id, func.count().label("n"))
    .where(CaseMember.status == "accepted")
    .group_by(CaseMember.case_id)
    .subquery()
)
result = await db.execute(
    select(Case, func.coalesce(document_counts.c.n, 0), func.coalesce(member_counts.c.n, 0))
    .outerjoin(document_counts, document_counts.c.case_id == Case.id)
    .outerjoin(member_counts, member_counts.c.case_id == Case.id)
    .outerjoin(CaseMember, CaseMember.case_id == Case.id)  # existing access-scoping join, unchanged
    .where(or_(Case.user_id == user_id, (CaseMember.user_id == user_id) & (CaseMember.status == "accepted")))
    .order_by(Case.created_at.desc())
    .distinct()
)
# then zip rows into CaseOut in the router, same "router assembles Pydantic
# from ORM row tuples" pattern get_case_endpoint already uses.
```

**Table view: additive toggle**, a `viewMode: "cards" | "table"` piece of local state (mirrors Tasks.tsx's existing List/Board toggle pattern).

**Frontend `Cases.tsx` changes**, wiring identical to `Workspace.tsx`:

```typescript
const [statusFilters, setStatusFilters] = useState<string[]>([]);
const [nameQuery, setNameQuery] = useState("");
const [viewMode, setViewMode] = useState<"cards" | "table">("cards");
const { isSelected, toggle, clear, selectedCount, selectedKeys } = useBulkSelection<CaseOut>((c) => c.id);

const STATUS_FILTER_OPTIONS = [
  { id: "open", label: t("cases.filterOpen") },
  { id: "closed", label: t("cases.filterClosed") },
];

const filteredCases = useMemo(
  () => cases.filter(
    (c) =>
      (activeStatusFilters.size === 0 || activeStatusFilters.has(c.status)) &&
      (nameQuery.trim() === "" || c.name.toLowerCase().includes(nameQuery.trim().toLowerCase()))
  ),
  [cases, activeStatusFilters, nameQuery]
);

const columns: Column<CaseOut>[] = [
  { key: "select", header: "", render: (c) => <input type="checkbox" checked={isSelected(c)} onChange={() => toggle(c)} onClick={(e) => e.stopPropagation()} /> },
  { key: "name", header: t("cases.columnName"), sortable: true, sortValue: (c) => c.name.toLowerCase(),
    render: (c) => <Link to={`/cases/${c.id}`} className="font-medium text-ink hover:text-accent">{c.name}</Link> },
  { key: "status", header: t("cases.columnStatus"), sortable: true, sortValue: (c) => c.status,
    render: (c) => <Badge variant={c.status === "open" ? "success" : "default"}>{c.status}</Badge> },
  { key: "document_count", header: t("cases.columnDocuments"), sortable: true, sortValue: (c) => c.document_count,
    render: (c) => c.document_count },
  { key: "member_count", header: t("cases.columnMembers"), sortable: true, sortValue: (c) => c.member_count,
    render: (c) => c.member_count },
  { key: "created_at", header: t("cases.columnCreated"), sortable: true, sortValue: (c) => c.created_at,
    render: (c) => formatDate(c.created_at) },
];
```

Bulk action: a single `t("cases.bulkClose")`/`t("cases.bulkReopen")` action calling `Promise.all(ids.map(id => updateCaseStatus(id, targetStatus)))`, same pattern as `Workspace.tsx`'s `handleBulkDelete`. Given mixed-status selections, offer both close-selected/reopen-selected buttons and let each only affect rows already in the opposite state.

Card grid stays exactly as-is when `viewMode === "cards"`; `document_count`/`member_count` can also be surfaced as small text on each card for consistency between the two views (nice-to-have, not required).

## Testing

- `Cases.test.tsx` (existing): search filters by name/description; status `FilterChips` narrows the list; table view toggle renders `DataTable` instead of the grid; sorting by document/member count works; bulk-select + bulk close/reopen calls `updateCaseStatus` for each selected id and refetches.
- Backend `test_cases.py` (existing): `list_cases()` returns correct `document_count`/`member_count` for a case with N documents and M accepted (not pending) members; a case with zero documents/members returns `0`, not `null`.
