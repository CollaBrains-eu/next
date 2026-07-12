# User-configurable date/time format — Design

## Status

Approved (brainstormed 2026-07-12)

## Context

Date and time values are displayed inconsistently across the app today:
some places call `new Date(x).toLocaleDateString()` / `.toLocaleString()`
(browser-locale-dependent, uncontrolled), others render the raw ISO or
RDW string with no formatting at all (`AddressHistory.valid_from`,
`Vehicles.vervaldatum_apk`, `KanbanBoard.due_date`, etc.). There is no
shared date-formatting utility.

The app already has one user preference — `preferred_language`, stored
in `UserPreference` (`services/api/src/api/models.py`), fetched via
`GET /preferences`, and set from `Settings.tsx` via `POST /preferences`.
`AuthProvider` (`apps/web/src/lib/auth.tsx`) fetches it on login and
calls `syncLanguage()` to drive i18next. This design adds a
`date_format` and `time_format` preference following the exact same
plumbing.

## Goals

1. Users pick a date format (EU `31/12/2026`, US `12/31/2026`, or ISO
   `2026-12-31`) and a time format (24h `14:30` or 12h `2:30 PM`) in
   Settings.
2. Every absolute date/time shown in the app honors the chosen format,
   reactively (no page reload needed).
3. New/existing users with no preference set get a sane default: EU
   date format, 24h time (matches the org's primary NL locale).

## Non-goals

- Not touching relative/humanized date text (`"Due today"`,
  `"Overdue by 3 days"`) — those stay as-is regardless of format.
- Not touching native `<input type="date">` pickers — browser-native
  widgets use the OS/browser locale, unrelated to this setting.
- Not adding a custom/free-form format pattern — a fixed 3-option list
  covers the userbase without exposing pattern-string complexity.
- Not changing `preferred_language`'s existing behavior (AI response
  language + i18next UI language) — unrelated, unaffected.

## Backend

**`services/api/src/api/models.py`** — `UserPreference` gains two
nullable columns:

```python
date_format: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "eu" | "us" | "iso"
time_format: Mapped[str | None] = mapped_column(String(10), nullable=True)  # "h24" | "h12"
```

**Migration** — new Alembic revision adding the two columns
(nullable, no backfill needed; `None` means "use the default").

**`services/api/src/api/preferences.py`** — `set_preferences()` gains
`date_format` and `time_format` keyword params, mirroring
`preferred_language`'s existing update-or-create logic.

**`services/api/src/api/preferences_router.py`** — `PreferencesRequest`
and `PreferencesOut` both gain `date_format: str | None = None` and
`time_format: str | None = None`.

No validation beyond the Pydantic type — an unrecognized value falls
back to the frontend default (see below), same tolerance the language
field already has.

## Frontend

**`apps/web/src/lib/dateFormat.ts`** (new) — pure functions, no React
dependency, unit-testable in isolation:

```typescript
export type DateFormat = "eu" | "us" | "iso";
export type TimeFormat = "h24" | "h12";
export interface DateFormatPrefs { dateFormat: DateFormat; timeFormat: TimeFormat; }

export const DEFAULT_DATE_FORMAT_PREFS: DateFormatPrefs = { dateFormat: "eu", timeFormat: "h24" };

export function formatDate(value: string | Date, prefs: DateFormatPrefs): string;
export function formatTime(value: string | Date, prefs: DateFormatPrefs): string;
export function formatDateTime(value: string | Date, prefs: DateFormatPrefs): string;

// RDW returns APK expiry as a compact "YYYYMMDD" string, not ISO.
export function parseCompactDate(value: string): Date | null;
```

Implementation formats manually from `Date` getters (not
`Intl.DateTimeFormat` with a locale trick) so the three options are
exact and don't drift with browser ICU data. Invalid/unparsable input
returns the original string unchanged (defensive default). `Vehicles.tsx`
calls `parseCompactDate(vervaldatum_apk)` first; a `null` result (missing
or malformed) falls back to the existing `"-"` placeholder rather than
being passed into `formatDate`.

**`apps/web/src/lib/auth.tsx`** — `AuthContextValue` gains
`dateFormatPrefs: DateFormatPrefs`. The existing effect that calls
`getPreferences().then((prefs) => syncLanguage(...))` also sets
`dateFormatPrefs` from `prefs.date_format`/`prefs.time_format`,
falling back to `DEFAULT_DATE_FORMAT_PREFS` for null/unrecognized
values.

**`apps/web/src/lib/useDateFormat.ts`** (new) — thin hook:

```typescript
export function useDateFormat() {
  const { dateFormatPrefs } = useAuth();
  return useMemo(() => ({
    formatDate: (v) => formatDate(v, dateFormatPrefs),
    formatTime: (v) => formatTime(v, dateFormatPrefs),
    formatDateTime: (v) => formatDateTime(v, dateFormatPrefs),
  }), [dateFormatPrefs]);
}
```

**`apps/web/src/routes/Settings.tsx`** — two new `<select>`s beside
the existing language picker, same loading/saving state machine
already in the component (`getPreferences`/`setPreferences`,
`saving`/`saved`/`error` states unchanged in shape).

**`apps/web/src/lib/api.ts`** — `PreferencesOut`/preferences request
types extended with `date_format`/`time_format` to match the backend
schema change.

### Sweep — call sites switched to the new hook

| File | Current | New |
|---|---|---|
| `components/AddressHistory.tsx` | raw `valid_from`/`valid_to` strings | `formatDate(...)` |
| `components/ui/KanbanBoard.tsx` | raw `task.due_date` in `Due {date}` | `formatDate(...)` |
| `routes/Tasks.tsx` | raw `dueDate` in `dueBadge()` | `formatDate(...)` |
| `components/PasskeySettings.tsx` | `created_at.slice(0, 10)` | `formatDate(...)` |
| `routes/Workspace.tsx` | `new Date(doc.created_at).toLocaleString()` | `formatDateTime(...)` |
| `routes/Cases.tsx` | `new Date(c.created_at).toLocaleDateString()` | `formatDate(...)` |
| `routes/AdminDashboard.tsx` (×2) | `new Date(...).toLocaleString()` / `.toLocaleDateString()` | `formatDateTime(...)` / `formatDate(...)` |
| `routes/Vehicles.tsx` | raw `vervaldatum_apk` (RDW `"20270225"`, no separators) | `parseCompactDate(...)` then `formatDate(...)`, or `"-"` if unparsable |

`dueBadge()` in `Tasks.tsx` and the `KanbanBoard` due-date label are
plain functions/components, not hooks — they'll take `formatDate` as
a parameter from their caller (which does have hook access), keeping
the pure/presentational split intact.

## Testing

- `dateFormat.test.ts` — unit tests for all 3×2 format combinations,
  invalid-input passthrough, and `parseCompactDate` (valid `"20270225"`,
  malformed, and empty-string cases).
- `useDateFormat` exercised indirectly through the sweep's existing
  component tests (e.g. `AddressHistory.test.tsx` already asserts on
  rendered date text — assertions updated to the new formatted
  output).
- `preferences_router` backend tests: round-trip `date_format`/
  `time_format` through `POST` then `GET`, same shape as the existing
  `preferred_language` test.
- `Settings.test.tsx` (new or extended): selecting a format and saving
  calls `setPreferences` with the right payload.

## Open questions resolved during brainstorming

- **Format option set**: fixed EU/US/ISO list for date, separate
  24h/12h toggle for time — not locale-inferred, not free-form.
- **Default for unset preference**: EU date + 24h time.
