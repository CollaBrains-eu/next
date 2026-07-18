# Calendar Case Picker (Phase 27b Follow-up) — Design

## Status
Proposed

## Context

`docs/superpowers/specs/2026-07-09-phase27b-calendar-design.md` already ships `Appointment.case_id` (nullable FK, `ON DELETE SET NULL`) on both the model and `AppointmentOut`, and that same spec's final line explicitly lists *"A case picker in the create/edit UI... isn't surfaced in the v1 form"* under "Explicitly out of scope." This item is that deliberately-deferred follow-up, not a new discovery. `docs/roadmap/phase-27.md` and the 2026-07-17 addendum in the spec confirm recurring events, real Maps integration, `.ics` import, and notifications are separately and explicitly out of scope — this item does not touch any of those.

Current code:
- `AppointmentOut` (api.ts) already has `case_id: string | null`.
- `AppointmentInput` (api.ts) does **not** declare `case_id` (or `vehicle_id`), even though the backend accepts it — a straightforward typing gap, not a backend gap.
- The create/edit `Modal` form (`Calendar.tsx`) has four plain, directly-styled `<input>`/`<textarea>` fields (title, starts_at, location, notes) — no `Combobox`, no `<select>`. This is a deliberately simpler style than `CaseDetail.tsx`'s `Combobox`-based attach UI.
- `listCases(): Promise<CaseOut[]>` already exists and is already used elsewhere (`Cases.tsx`, `CaseDetail.tsx`).
- `CaseDashboardOut` (`cases_router.py`) currently returns `documents`/`tasks`/`decisions`/`vehicles` only. `get_case_dashboard()` builds each list via one cheap query per relation — documents via a direct `Document.case_id` FK filter (identical shape to what an `appointments` list would need, since `Appointment.case_id` is also a direct FK).

## Goals

1. Surface a case picker (`<select>`, populated by `listCases()`) in the Calendar create/edit modal.
2. Add the missing `case_id` field to `AppointmentInput` and thread it through create/update calls.
3. Show a case's linked appointments on the Case dashboard — recommended in scope since it's a one-line addition mirroring the existing `documents` query exactly (direct FK, no join complexity).

## Non-goals

Everything the phase-27b spec already excludes: recurring appointments, real Maps API integration, `.ics` import, any notification. Also out of scope: a vehicle picker (`vehicle_id` has the identical gap, but the ask is specifically "case picker" — leaving `vehicle_id` for a symmetrical future pass keeps this change small).

## Design

### `apps/web/src/lib/api.ts`

```typescript
export interface AppointmentInput {
  title: string;
  starts_at: string;
  ends_at?: string;
  location?: string;
  notes?: string;
  case_id?: string | null;
}
```

(`updateAppointment` already takes `Partial<AppointmentInput>`, so no separate change needed there.)

### `apps/web/src/routes/Calendar.tsx`

- New state: `const [cases, setCases] = useState<CaseOut[]>([]);` fetched once via `useEffect(() => { listCases().then(setCases).catch(() => undefined); }, [])` — same "fire-and-forget, fail silently" pattern `CaseDetail.tsx` already uses for its side-fetches.
- New form field state: `const [formCaseId, setFormCaseId] = useState<string>("");` (empty string = no case).
- `openCreateForm`/`openEditForm` reset/prefill `formCaseId` from `appointment.case_id ?? ""`, alongside the existing four fields.
- New form control, placed after the Location field (before Notes), matching the existing plain-`<input>` styling exactly — a native `<select>`, not the `Combobox` component, to stay consistent with this file's own established plain-form-element convention:

```tsx
<div className="flex flex-col gap-1">
  <label className="text-xs font-medium text-ink-2" htmlFor="appointment-case">
    {t("calendar.caseLabel")}
  </label>
  <select
    id="appointment-case"
    value={formCaseId}
    onChange={(e) => setFormCaseId(e.target.value)}
    className="rounded-lg border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent"
  >
    <option value="">{t("calendar.noCase")}</option>
    {cases.map((c) => (
      <option key={c.id} value={c.id}>{c.name}</option>
    ))}
  </select>
</div>
```

- `handleSubmitForm`'s `payload` gains `case_id: formCaseId || null`.
- Agenda-pane appointment rows: optionally show the linked case name as a small tag next to the location/`.ics` links (nice-to-have, droppable if scope needs trimming).

### Backend: `CaseDashboardOut` gains appointments (recommended in-scope)

`services/api/src/api/cases.py`, `get_case_dashboard()`:

```python
appointments_result = await db.execute(select(Appointment).where(Appointment.case_id == case_id).order_by(Appointment.starts_at))
appointments = list(appointments_result.scalars().all())
# add "appointments": appointments to the returned dict
```

`services/api/src/api/cases_router.py`:

```python
class CaseAppointmentOut(BaseModel):
    id: UUID
    title: str
    starts_at: datetime

class CaseDashboardOut(CaseOut):
    documents: list[CaseDocumentOut]
    tasks: list[CaseTaskOut]
    decisions: list[CaseDecisionOut]
    vehicles: list[CaseVehicleOut]
    appointments: list[CaseAppointmentOut]
```

`apps/web/src/lib/api.ts`'s `CaseDashboardOut` gains the matching `appointments: { id: string; title: string; starts_at: string }[]` field; `CaseDetail.tsx` renders a fifth `Card` section identical in shape to the existing four. There's no `/calendar/:id` deep link today, so rows render as unlinked text for v1 rather than inventing a new calendar deep-link route.

## Testing

- `Calendar.test.tsx` (existing): the case `<select>` renders options from a mocked `listCases()`; selecting a case and submitting the create form calls `createAppointment` with the chosen `case_id`; opening the edit form for an appointment with a `case_id` pre-selects the right `<option>`; submitting with "No case" selected sends `case_id: null`.
- Backend `test_appointments.py` (existing): creating with `case_id` set returns it in the response.
- Backend `test_cases.py` (existing): `GET /cases/{id}` includes `appointments` matching `Appointment.case_id`, empty list when none linked.
