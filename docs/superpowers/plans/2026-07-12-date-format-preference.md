# User-Configurable Date/Time Format Preference Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users pick a date format (EU/US/ISO) and time format (24h/12h) in Settings, and have every absolute date/time display in the app honor it reactively.

**Architecture:** A new `date_format`/`time_format` column pair on the existing `UserPreference` backend row, exposed through the existing `/preferences/me` endpoints. On the frontend, a pure formatting module (`lib/dateFormat.ts`) plus a `useSyncExternalStore`-backed global store/hook (`hooks/useDateFormat.ts`) — mirroring the codebase's existing `syncLanguage()` plain-function-singleton pattern for `preferred_language` rather than adding a new React Context, so it plugs into `AuthProvider`'s existing preferences fetch and `Settings.tsx`'s existing save flow with minimal new surface area. ~10 call sites across the app switch from ad hoc `toLocaleDateString()`/raw-string rendering to this shared formatter.

**Tech Stack:** FastAPI + SQLAlchemy + Alembic (backend), React + TypeScript + Vitest/Testing Library (frontend), same stack as the rest of the repo.

**Deviation from the spec:** `docs/superpowers/specs/2026-07-12-date-format-preference-design.md` describes extending `AuthContext` with `dateFormatPrefs`. While mapping out exact files, this plan instead uses a `useSyncExternalStore` module singleton (Task 4) because `Settings.test.tsx` renders `<Settings />` without any provider wrapper — a Context dependency would break that existing, unrelated test. The singleton approach also mirrors `syncLanguage()`/i18next, the codebase's existing precedent for exactly this "preference set in Settings, consumed reactively everywhere" shape. The goal (every consumer re-renders live when the preference changes) is preserved.

## Global Constraints

- Default preference when unset: `date_format = null` → treated as `"eu"`; `time_format = null` → treated as `"h24"`.
- No format-string validation beyond Pydantic's `str | None` type on the backend — unrecognized values fall back to the default on the frontend (same tolerance `preferred_language` already has).
- Relative/humanized date text (`"Due today"`, `"Overdue by N days"`) is unaffected — only absolute date/time displays change.
- Native `<input type="date">` pickers are unaffected.
- Run frontend commands from `apps/web/`; run backend commands from `services/api/` using `/Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/` (python/pytest/alembic) — that venv is already provisioned against the local Postgres (`postgresql+asyncpg://collabrains:changeme@localhost:5432/collabrains`, confirmed running).
- Work happens on branch `violet-ds-date-format-preference` (already created, already rebased onto latest `origin/main` at commit `67acd68`).

---

### Task 1: Backend — `date_format`/`time_format` columns + migration

**Files:**
- Modify: `services/api/src/api/models.py:488` (inside `UserPreference`)
- Create: `services/api/alembic/versions/1a9b3c5d7e2f_add_date_format_and_time_format_to_user_preferences.py`

**Interfaces:**
- Produces: `UserPreference.date_format: str | None`, `UserPreference.time_format: str | None` — consumed by Task 2.

- [ ] **Step 1: Add the two columns to the model**

In `services/api/src/api/models.py`, inside `class UserPreference(Base):`, change:

```python
    preferred_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

to:

```python
    preferred_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    time_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

- [ ] **Step 2: Write the migration**

Create `services/api/alembic/versions/1a9b3c5d7e2f_add_date_format_and_time_format_to_user_preferences.py`:

```python
"""add date_format and time_format to user_preferences

Revision ID: 1a9b3c5d7e2f
Revises: b6d4f9a3e7c2
Create Date: 2026-07-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1a9b3c5d7e2f'
down_revision: Union[str, None] = 'b6d4f9a3e7c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user_preferences', sa.Column('date_format', sa.String(length=10), nullable=True))
    op.add_column('user_preferences', sa.Column('time_format', sa.String(length=10), nullable=True))


def downgrade() -> None:
    op.drop_column('user_preferences', 'time_format')
    op.drop_column('user_preferences', 'date_format')
```

Before writing, confirm `b6d4f9a3e7c2` is still the real current head (other parallel branches may have merged since this plan was written):

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/alembic heads`
Expected: `b6d4f9a3e7c2 (head)`. If a different revision is reported, use that as `down_revision` instead.

- [ ] **Step 3: Apply the migration**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/alembic upgrade head`
Expected: output ending in `... -> 1a9b3c5d7e2f, add date_format and time_format to user_preferences`

If this fails with `Can't locate revision identified by ...` (the shared local Postgres has previously been stamped by a different parallel worktree branch), fall back to applying the same DDL directly for local dev only — the migration file remains the source of truth for CI/other environments:

Run: `psql postgresql://collabrains:changeme@localhost:5432/collabrains -c "ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS date_format VARCHAR(10), ADD COLUMN IF NOT EXISTS time_format VARCHAR(10);"`

Then verify: `psql postgresql://collabrains:changeme@localhost:5432/collabrains -c "\d user_preferences"` shows both new columns.

- [ ] **Step 4: Commit**

```bash
git add services/api/src/api/models.py services/api/alembic/versions/1a9b3c5d7e2f_add_date_format_and_time_format_to_user_preferences.py
git commit -m "feat: add date_format/time_format columns to user_preferences"
```

---

### Task 2: Backend — `preferences.py` + `preferences_router.py` + tests

**Files:**
- Modify: `services/api/src/api/preferences.py:36-45` (`set_preferences`)
- Modify: `services/api/src/api/preferences_router.py` (full file)
- Modify: `services/api/tests/test_preferences.py` (add 2 tests)
- Modify: `services/api/tests/test_preferences_router.py` (full file — every existing JSON-equality assertion needs the two new keys)

**Interfaces:**
- Consumes: `UserPreference.date_format`, `UserPreference.time_format` (Task 1).
- Produces: `set_preferences(db, *, user_id, preferred_language, date_format=None, time_format=None)`; `PreferencesRequest`/`PreferencesOut` with `date_format`/`time_format` fields — consumed by the frontend's `/preferences/me` calls (Task 5).

- [ ] **Step 1: Write the failing backend unit tests**

In `services/api/tests/test_preferences.py`, add after `test_set_preferences_upserts_an_existing_row`:

```python
async def test_set_preferences_persists_date_and_time_format():
    user = await _create_user(_unique("prefuser"))
    async with async_session() as db:
        preferences = await set_preferences(
            db, user_id=user.id, preferred_language=None, date_format="us", time_format="h12"
        )
    assert preferences.date_format == "us"
    assert preferences.time_format == "h12"

    async with async_session() as db:
        fetched = await get_preferences(db, user_id=user.id)
    assert fetched.date_format == "us"
    assert fetched.time_format == "h12"


async def test_set_preferences_date_and_time_format_default_to_none():
    user = await _create_user(_unique("prefuser"))
    async with async_session() as db:
        preferences = await set_preferences(db, user_id=user.id, preferred_language="de")
    assert preferences.date_format is None
    assert preferences.time_format is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest tests/test_preferences.py -k "date_and_time_format" -v`
Expected: FAIL — `set_preferences() got an unexpected keyword argument 'date_format'`

- [ ] **Step 3: Update `set_preferences`**

In `services/api/src/api/preferences.py`, change:

```python
async def set_preferences(db: AsyncSession, *, user_id: UUID, preferred_language: str | None) -> UserPreference:
    preferences = await get_preferences(db, user_id=user_id)
    if preferences is None:
        preferences = UserPreference(user_id=user_id, preferred_language=preferred_language)
        db.add(preferences)
    else:
        preferences.preferred_language = preferred_language
    await db.commit()
    await db.refresh(preferences)
    return preferences
```

to:

```python
async def set_preferences(
    db: AsyncSession,
    *,
    user_id: UUID,
    preferred_language: str | None,
    date_format: str | None = None,
    time_format: str | None = None,
) -> UserPreference:
    preferences = await get_preferences(db, user_id=user_id)
    if preferences is None:
        preferences = UserPreference(
            user_id=user_id,
            preferred_language=preferred_language,
            date_format=date_format,
            time_format=time_format,
        )
        db.add(preferences)
    else:
        preferences.preferred_language = preferred_language
        preferences.date_format = date_format
        preferences.time_format = time_format
    await db.commit()
    await db.refresh(preferences)
    return preferences
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest tests/test_preferences.py -v`
Expected: all tests PASS (existing 3 + 2 new = 5 in that file... actually existing file already has 6 tests total across preferences + language-instruction; just confirm no FAIL/ERROR lines)

- [ ] **Step 5: Update the router's request/response models and both mutating endpoints**

Replace the full contents of `services/api/src/api/preferences_router.py` with:

```python
"""Preference endpoints (Phase 13, ADR 0028).

Scoped to the caller's own preferences only -- no admin override, unlike
Plan/Decision, since there's no operational need for one here.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import User
from api.preferences import delete_preferences, get_preferences, set_preferences

router = APIRouter(prefix="/preferences", tags=["preferences"])


class PreferencesRequest(BaseModel):
    preferred_language: str | None = None
    date_format: str | None = None
    time_format: str | None = None


class PreferencesOut(BaseModel):
    preferred_language: str | None
    date_format: str | None
    time_format: str | None


@router.get("/me", response_model=PreferencesOut)
async def get_my_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferencesOut:
    preferences = await get_preferences(db, user_id=current_user.id)
    return PreferencesOut(
        preferred_language=preferences.preferred_language if preferences else None,
        date_format=preferences.date_format if preferences else None,
        time_format=preferences.time_format if preferences else None,
    )


@router.put("/me", response_model=PreferencesOut)
async def set_my_preferences(
    request: PreferencesRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PreferencesOut:
    preferences = await set_preferences(
        db,
        user_id=current_user.id,
        preferred_language=request.preferred_language,
        date_format=request.date_format,
        time_format=request.time_format,
    )
    return PreferencesOut(
        preferred_language=preferences.preferred_language,
        date_format=preferences.date_format,
        time_format=preferences.time_format,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = await delete_preferences(db, user_id=current_user.id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No preferences to delete")
```

- [ ] **Step 6: Update the router tests**

Replace the full contents of `services/api/tests/test_preferences_router.py` with:

```python
from unittest.mock import patch

from api.ldap_auth import LdapIdentity


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def test_get_preferences_returns_null_when_unset(client):
    token = await _login(client, "prefrouteruser1")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/preferences/me", headers=headers)

    assert response.status_code == 200
    assert response.json() == {"preferred_language": None, "date_format": None, "time_format": None}


async def test_set_and_get_preferences_round_trip(client):
    token = await _login(client, "prefrouteruser2")
    headers = {"Authorization": f"Bearer {token}"}

    put_response = await client.put(
        "/preferences/me",
        headers=headers,
        json={"preferred_language": "de", "date_format": "us", "time_format": "h12"},
    )
    assert put_response.status_code == 200
    assert put_response.json() == {"preferred_language": "de", "date_format": "us", "time_format": "h12"}

    get_response = await client.get("/preferences/me", headers=headers)
    assert get_response.json() == {"preferred_language": "de", "date_format": "us", "time_format": "h12"}


async def test_delete_preferences(client):
    token = await _login(client, "prefrouteruser3")
    headers = {"Authorization": f"Bearer {token}"}

    await client.put("/preferences/me", headers=headers, json={"preferred_language": "nl"})

    delete_response = await client.delete("/preferences/me", headers=headers)
    assert delete_response.status_code == 204

    get_response = await client.get("/preferences/me", headers=headers)
    assert get_response.json() == {"preferred_language": None, "date_format": None, "time_format": None}


async def test_delete_preferences_returns_404_when_nothing_to_delete(client):
    token = await _login(client, "prefrouteruser4")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.delete("/preferences/me", headers=headers)
    assert response.status_code == 404


async def test_preferences_endpoints_are_scoped_to_the_caller(client):
    token_a = await _login(client, "prefrouteruserA")
    token_b = await _login(client, "prefrouteruserB")

    await client.put(
        "/preferences/me", headers={"Authorization": f"Bearer {token_a}"}, json={"preferred_language": "de"}
    )

    response_b = await client.get("/preferences/me", headers={"Authorization": f"Bearer {token_b}"})
    assert response_b.json() == {"preferred_language": None, "date_format": None, "time_format": None}


async def test_get_preferences_rejects_missing_token(client):
    response = await client.get("/preferences/me")
    assert response.status_code == 401
```

- [ ] **Step 7: Run all preferences tests**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest tests/test_preferences.py tests/test_preferences_router.py -v`
Expected: all PASS

- [ ] **Step 8: Commit**

```bash
git add services/api/src/api/preferences.py services/api/src/api/preferences_router.py services/api/tests/test_preferences.py services/api/tests/test_preferences_router.py
git commit -m "feat: expose date_format/time_format on the preferences endpoints"
```

---

### Task 3: Frontend — `lib/dateFormat.ts` pure formatting utility

**Files:**
- Create: `apps/web/src/lib/dateFormat.ts`
- Create: `apps/web/src/lib/dateFormat.test.ts`

**Interfaces:**
- Produces: `DateFormat`, `TimeFormat`, `DateFormatPrefs` types; `DEFAULT_DATE_FORMAT_PREFS`; `formatDate(value, prefs)`, `formatTime(value, prefs)`, `formatDateTime(value, prefs)`, `parseCompactDate(value)`, `toDateFormatPrefs(dateFormat, timeFormat)` — consumed by Task 4 (`hooks/useDateFormat.ts`), Task 6 (`auth.tsx`), Task 7 (`Settings.tsx`), and every Task 8-13 sweep file.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/lib/dateFormat.test.ts`:

```typescript
import { describe, expect, it } from "vitest";
import {
  DEFAULT_DATE_FORMAT_PREFS,
  formatDate,
  formatDateTime,
  formatTime,
  parseCompactDate,
  toDateFormatPrefs,
  type DateFormatPrefs,
} from "./dateFormat";

const EU: DateFormatPrefs = { dateFormat: "eu", timeFormat: "h24" };
const US: DateFormatPrefs = { dateFormat: "us", timeFormat: "h12" };
const ISO: DateFormatPrefs = { dateFormat: "iso", timeFormat: "h24" };

const SAMPLE = new Date(2026, 11, 31, 14, 30); // 31 Dec 2026, 14:30 local time

describe("formatDate", () => {
  it("formats eu as DD/MM/YYYY", () => {
    expect(formatDate(SAMPLE, EU)).toBe("31/12/2026");
  });

  it("formats us as MM/DD/YYYY", () => {
    expect(formatDate(SAMPLE, US)).toBe("12/31/2026");
  });

  it("formats iso as YYYY-MM-DD", () => {
    expect(formatDate(SAMPLE, ISO)).toBe("2026-12-31");
  });

  it("accepts an ISO string as well as a Date", () => {
    expect(formatDate("2026-12-31T00:00:00", EU)).toBe("31/12/2026");
  });

  it("returns the original string unchanged for unparsable input", () => {
    expect(formatDate("not-a-date", EU)).toBe("not-a-date");
  });
});

describe("formatTime", () => {
  it("formats h24 as HH:MM", () => {
    expect(formatTime(SAMPLE, EU)).toBe("14:30");
  });

  it("formats h12 with AM/PM", () => {
    expect(formatTime(SAMPLE, US)).toBe("2:30 PM");
  });

  it("formats midnight as 12 AM in h12", () => {
    expect(formatTime(new Date(2026, 0, 1, 0, 5), US)).toBe("12:05 AM");
  });

  it("formats noon as 12 PM in h12", () => {
    expect(formatTime(new Date(2026, 0, 1, 12, 0), US)).toBe("12:00 PM");
  });
});

describe("formatDateTime", () => {
  it("joins the date and time with a space", () => {
    expect(formatDateTime(SAMPLE, EU)).toBe("31/12/2026 14:30");
  });
});

describe("parseCompactDate", () => {
  it("parses a valid YYYYMMDD string", () => {
    const parsed = parseCompactDate("20270225");
    expect(parsed).not.toBeNull();
    expect(formatDate(parsed!, EU)).toBe("25/02/2027");
  });

  it("returns null for a malformed string", () => {
    expect(parseCompactDate("2027-02-25")).toBeNull();
  });

  it("returns null for an empty string", () => {
    expect(parseCompactDate("")).toBeNull();
  });

  it("returns null for an impossible date", () => {
    expect(parseCompactDate("20271345")).toBeNull();
  });
});

describe("toDateFormatPrefs", () => {
  it("returns the given valid values", () => {
    expect(toDateFormatPrefs("us", "h12")).toEqual({ dateFormat: "us", timeFormat: "h12" });
  });

  it("falls back to eu/h24 for null values", () => {
    expect(toDateFormatPrefs(null, null)).toEqual(DEFAULT_DATE_FORMAT_PREFS);
  });

  it("falls back to eu/h24 for unrecognized values", () => {
    expect(toDateFormatPrefs("klingon", "whenever")).toEqual(DEFAULT_DATE_FORMAT_PREFS);
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && npx vitest run src/lib/dateFormat.test.ts`
Expected: FAIL — `Failed to resolve import "./dateFormat"`

- [ ] **Step 3: Write the implementation**

Create `apps/web/src/lib/dateFormat.ts`:

```typescript
export type DateFormat = "eu" | "us" | "iso";
export type TimeFormat = "h24" | "h12";

export interface DateFormatPrefs {
  dateFormat: DateFormat;
  timeFormat: TimeFormat;
}

export const DEFAULT_DATE_FORMAT_PREFS: DateFormatPrefs = { dateFormat: "eu", timeFormat: "h24" };

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

function toDate(value: string | Date): Date | null {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | Date, prefs: DateFormatPrefs): string {
  const date = toDate(value);
  if (!date) return String(value);
  const day = pad2(date.getDate());
  const month = pad2(date.getMonth() + 1);
  const year = date.getFullYear();
  switch (prefs.dateFormat) {
    case "us":
      return `${month}/${day}/${year}`;
    case "iso":
      return `${year}-${month}-${day}`;
    case "eu":
    default:
      return `${day}/${month}/${year}`;
  }
}

export function formatTime(value: string | Date, prefs: DateFormatPrefs): string {
  const date = toDate(value);
  if (!date) return String(value);
  const hours24 = date.getHours();
  const minutes = pad2(date.getMinutes());
  if (prefs.timeFormat === "h12") {
    const period = hours24 < 12 ? "AM" : "PM";
    const hours12 = hours24 % 12 === 0 ? 12 : hours24 % 12;
    return `${hours12}:${minutes} ${period}`;
  }
  return `${pad2(hours24)}:${minutes}`;
}

export function formatDateTime(value: string | Date, prefs: DateFormatPrefs): string {
  const date = toDate(value);
  if (!date) return String(value);
  return `${formatDate(date, prefs)} ${formatTime(date, prefs)}`;
}

// RDW returns APK expiry as a compact "YYYYMMDD" string, not ISO.
export function parseCompactDate(value: string): Date | null {
  const match = /^(\d{4})(\d{2})(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return date;
}

export function toDateFormatPrefs(dateFormat: string | null, timeFormat: string | null): DateFormatPrefs {
  const df: DateFormat = dateFormat === "us" || dateFormat === "iso" ? dateFormat : "eu";
  const tf: TimeFormat = timeFormat === "h12" ? "h12" : "h24";
  return { dateFormat: df, timeFormat: tf };
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && npx vitest run src/lib/dateFormat.test.ts`
Expected: PASS, all tests green

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/lib/dateFormat.ts apps/web/src/lib/dateFormat.test.ts
git commit -m "feat: add pure date/time formatting utility"
```

---

### Task 4: Frontend — `hooks/useDateFormat.ts` reactive store + hook

**Files:**
- Create: `apps/web/src/hooks/useDateFormat.ts`
- Create: `apps/web/src/hooks/useDateFormat.test.ts`

**Interfaces:**
- Consumes: `DEFAULT_DATE_FORMAT_PREFS`, `DateFormatPrefs`, `formatDate`, `formatTime`, `formatDateTime` from `../lib/dateFormat` (Task 3).
- Produces: `setDateFormatPrefs(prefs: DateFormatPrefs): void` (plain function, mirrors `syncLanguage`) and `useDateFormat(): { formatDate, formatTime, formatDateTime }` (each taking `(value: string | Date) => string`) — consumed by Task 6 (`auth.tsx`), Task 7 (`Settings.tsx`), and every Task 8-13 sweep file.

- [ ] **Step 1: Write the failing tests**

Create `apps/web/src/hooks/useDateFormat.test.ts`:

```typescript
import { afterEach, describe, expect, it } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { setDateFormatPrefs, useDateFormat } from "./useDateFormat";
import { DEFAULT_DATE_FORMAT_PREFS } from "../lib/dateFormat";

describe("useDateFormat", () => {
  afterEach(() => {
    act(() => setDateFormatPrefs(DEFAULT_DATE_FORMAT_PREFS));
  });

  it("formats using the default eu/h24 prefs initially", () => {
    const { result } = renderHook(() => useDateFormat());
    expect(result.current.formatDate(new Date(2026, 5, 1))).toBe("01/06/2026");
  });

  it("reactively updates already-mounted consumers when prefs change", () => {
    const { result } = renderHook(() => useDateFormat());
    act(() => setDateFormatPrefs({ dateFormat: "us", timeFormat: "h12" }));
    expect(result.current.formatDate(new Date(2026, 5, 1))).toBe("06/01/2026");
  });

  it("exposes formatTime and formatDateTime bound to the current prefs", () => {
    const { result } = renderHook(() => useDateFormat());
    act(() => setDateFormatPrefs({ dateFormat: "iso", timeFormat: "h24" }));
    const sample = new Date(2026, 5, 1, 9, 5);
    expect(result.current.formatTime(sample)).toBe("09:05");
    expect(result.current.formatDateTime(sample)).toBe("2026-06-01 09:05");
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd apps/web && npx vitest run src/hooks/useDateFormat.test.ts`
Expected: FAIL — `Failed to resolve import "./useDateFormat"`

- [ ] **Step 3: Write the implementation**

Create `apps/web/src/hooks/useDateFormat.ts`:

```typescript
import { useMemo, useSyncExternalStore } from "react";
import {
  DEFAULT_DATE_FORMAT_PREFS,
  formatDate,
  formatDateTime,
  formatTime,
  type DateFormatPrefs,
} from "../lib/dateFormat";

let currentPrefs: DateFormatPrefs = DEFAULT_DATE_FORMAT_PREFS;
const listeners = new Set<() => void>();

// Plain-function singleton, same shape as auth.tsx's syncLanguage(): callers
// (AuthProvider on preferences load, Settings on save) call this directly;
// useDateFormat() below subscribes React components to it reactively.
export function setDateFormatPrefs(prefs: DateFormatPrefs): void {
  currentPrefs = prefs;
  listeners.forEach((listener) => listener());
}

function getSnapshot(): DateFormatPrefs {
  return currentPrefs;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useDateFormat() {
  const prefs = useSyncExternalStore(subscribe, getSnapshot);
  return useMemo(
    () => ({
      formatDate: (value: string | Date) => formatDate(value, prefs),
      formatTime: (value: string | Date) => formatTime(value, prefs),
      formatDateTime: (value: string | Date) => formatDateTime(value, prefs),
    }),
    [prefs],
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd apps/web && npx vitest run src/hooks/useDateFormat.test.ts`
Expected: PASS, all tests green

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/hooks/useDateFormat.ts apps/web/src/hooks/useDateFormat.test.ts
git commit -m "feat: add reactive useDateFormat hook"
```

---

### Task 5: Frontend — `lib/api.ts` preferences types + `setPreferences` signature

**Files:**
- Modify: `apps/web/src/lib/api.ts:474-487`

**Interfaces:**
- Produces: `PreferencesOut { preferred_language, date_format, time_format }`; `setPreferences(prefs: { preferredLanguage: string | null; dateFormat: string; timeFormat: string }): Promise<PreferencesOut>` — consumed by Task 6 and Task 7.

- [ ] **Step 1: Update the preferences section**

In `apps/web/src/lib/api.ts`, change:

```typescript
export interface PreferencesOut {
  preferred_language: string | null;
}

export function getPreferences(): Promise<PreferencesOut> {
  return request<PreferencesOut>("/preferences/me");
}

export function setPreferences(preferredLanguage: string | null): Promise<PreferencesOut> {
  return request<PreferencesOut>("/preferences/me", {
    method: "PUT",
    body: JSON.stringify({ preferred_language: preferredLanguage }),
  });
}
```

to:

```typescript
export interface PreferencesOut {
  preferred_language: string | null;
  date_format: string | null;
  time_format: string | null;
}

export function getPreferences(): Promise<PreferencesOut> {
  return request<PreferencesOut>("/preferences/me");
}

export function setPreferences(prefs: {
  preferredLanguage: string | null;
  dateFormat: string;
  timeFormat: string;
}): Promise<PreferencesOut> {
  return request<PreferencesOut>("/preferences/me", {
    method: "PUT",
    body: JSON.stringify({
      preferred_language: prefs.preferredLanguage,
      date_format: prefs.dateFormat,
      time_format: prefs.timeFormat,
    }),
  });
}
```

- [ ] **Step 2: Typecheck**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | grep -i "api.ts\|Settings.tsx"`
Expected: errors referencing `Settings.tsx` calling `setPreferences(language || null)` with the old signature (expected — fixed in Task 7). No errors referencing `api.ts` itself.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "feat: add date_format/time_format to the preferences API client"
```

---

### Task 6: Frontend — wire `auth.tsx` to sync date/time prefs on login

**Files:**
- Modify: `apps/web/src/lib/auth.tsx`

**Interfaces:**
- Consumes: `toDateFormatPrefs` from `./dateFormat` (Task 3), `setDateFormatPrefs` from `../hooks/useDateFormat` (Task 4).

- [ ] **Step 1: Add the imports**

In `apps/web/src/lib/auth.tsx`, change:

```typescript
import { ApiError, clearToken, fetchMe, getPreferences, login as apiLogin, setToken, type UserOut } from "./api";
import i18n, { LANGUAGE_NAME_TO_CODE } from "./i18n";
import { loginWithPasskey as passkeyCeremony } from "./webauthn";
```

to:

```typescript
import { ApiError, clearToken, fetchMe, getPreferences, login as apiLogin, setToken, type UserOut } from "./api";
import { toDateFormatPrefs } from "./dateFormat";
import i18n, { LANGUAGE_NAME_TO_CODE } from "./i18n";
import { setDateFormatPrefs } from "../hooks/useDateFormat";
import { loginWithPasskey as passkeyCeremony } from "./webauthn";
```

- [ ] **Step 2: Update the preferences-sync effect**

Change:

```typescript
  useEffect(() => {
    if (!user) return;
    getPreferences()
      .then((prefs) => syncLanguage(prefs.preferred_language))
      .catch(() => {
        // Language sync is a nice-to-have; the default (English) stays in effect on failure.
      });
  }, [user]);
```

to:

```typescript
  useEffect(() => {
    if (!user) return;
    getPreferences()
      .then((prefs) => {
        syncLanguage(prefs.preferred_language);
        setDateFormatPrefs(toDateFormatPrefs(prefs.date_format, prefs.time_format));
      })
      .catch(() => {
        // Preference sync is a nice-to-have; the defaults stay in effect on failure.
      });
  }, [user]);
```

- [ ] **Step 3: Run the existing auth tests to confirm no regression**

Run: `cd apps/web && npx vitest run src/lib/auth.test.ts`
Expected: PASS (this file only imports/tests `syncLanguage` directly, unaffected by the effect change)

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/auth.tsx
git commit -m "feat: sync date/time format preference into AuthProvider's login flow"
```

---

### Task 7: Frontend — `Settings.tsx` UI, i18n keys, and its tests

**Files:**
- Modify: `apps/web/src/routes/Settings.tsx` (full file)
- Modify: `apps/web/src/locales/en.json:321-330`, `apps/web/src/locales/nl.json:321-330`, `apps/web/src/locales/de.json:321-330`
- Modify: `apps/web/src/routes/Settings.test.tsx` (full file)

**Interfaces:**
- Consumes: `toDateFormatPrefs`, `type DateFormat`, `type TimeFormat` from `../lib/dateFormat` (Task 3); `setDateFormatPrefs` from `../hooks/useDateFormat` (Task 4); the new `setPreferences` signature (Task 5).

- [ ] **Step 1: Add the new locale keys**

In `apps/web/src/locales/en.json`, change the `settings` block:

```json
  "settings": {
    "title": "Settings",
    "preferredLanguage": "Preferred language",
    "preferredLanguageHint": "Used by AI Chat to respond in your preferred language.",
    "noPreference": "No preference",
    "loadError": "Failed to load preferences",
    "saveError": "Failed to save preferences",
    "saved": "Saved.",
    "save": "Save"
  },
```

to:

```json
  "settings": {
    "title": "Settings",
    "preferredLanguage": "Preferred language",
    "preferredLanguageHint": "Used by AI Chat to respond in your preferred language.",
    "noPreference": "No preference",
    "dateFormat": "Date format",
    "dateFormatEu": "DD/MM/YYYY (31/12/2026)",
    "dateFormatUs": "MM/DD/YYYY (12/31/2026)",
    "dateFormatIso": "YYYY-MM-DD (2026-12-31)",
    "timeFormat": "Time format",
    "timeFormatH24": "24-hour (14:30)",
    "timeFormatH12": "12-hour (2:30 PM)",
    "loadError": "Failed to load preferences",
    "saveError": "Failed to save preferences",
    "saved": "Saved.",
    "save": "Save"
  },
```

In `apps/web/src/locales/nl.json`, change the equivalent block:

```json
  "settings": {
    "title": "Instellingen",
    "preferredLanguage": "Voorkeurstaal",
    "preferredLanguageHint": "Wordt gebruikt door AI-chat om in uw voorkeurstaal te antwoorden.",
    "noPreference": "Geen voorkeur",
    "loadError": "Kon voorkeuren niet laden",
    "saveError": "Kon voorkeuren niet opslaan",
    "saved": "Opgeslagen.",
    "save": "Opslaan"
  },
```

to:

```json
  "settings": {
    "title": "Instellingen",
    "preferredLanguage": "Voorkeurstaal",
    "preferredLanguageHint": "Wordt gebruikt door AI-chat om in uw voorkeurstaal te antwoorden.",
    "noPreference": "Geen voorkeur",
    "dateFormat": "Datumnotatie",
    "dateFormatEu": "DD/MM/JJJJ (31/12/2026)",
    "dateFormatUs": "MM/DD/JJJJ (12/31/2026)",
    "dateFormatIso": "JJJJ-MM-DD (2026-12-31)",
    "timeFormat": "Tijdnotatie",
    "timeFormatH24": "24-uurs (14:30)",
    "timeFormatH12": "12-uurs (2:30 PM)",
    "loadError": "Kon voorkeuren niet laden",
    "saveError": "Kon voorkeuren niet opslaan",
    "saved": "Opgeslagen.",
    "save": "Opslaan"
  },
```

In `apps/web/src/locales/de.json`, change the equivalent block:

```json
  "settings": {
    "title": "Einstellungen",
    "preferredLanguage": "Bevorzugte Sprache",
    "preferredLanguageHint": "Wird von KI-Chat verwendet, um in Ihrer bevorzugten Sprache zu antworten.",
    "noPreference": "Keine Präferenz",
    "loadError": "Einstellungen konnten nicht geladen werden",
    "saveError": "Einstellungen konnten nicht gespeichert werden",
    "saved": "Gespeichert.",
    "save": "Speichern"
  },
```

to:

```json
  "settings": {
    "title": "Einstellungen",
    "preferredLanguage": "Bevorzugte Sprache",
    "preferredLanguageHint": "Wird von KI-Chat verwendet, um in Ihrer bevorzugten Sprache zu antworten.",
    "noPreference": "Keine Präferenz",
    "dateFormat": "Datumformat",
    "dateFormatEu": "TT/MM/JJJJ (31/12/2026)",
    "dateFormatUs": "MM/TT/JJJJ (12/31/2026)",
    "dateFormatIso": "JJJJ-MM-TT (2026-12-31)",
    "timeFormat": "Zeitformat",
    "timeFormatH24": "24-Stunden (14:30)",
    "timeFormatH12": "12-Stunden (2:30 PM)",
    "loadError": "Einstellungen konnten nicht geladen werden",
    "saveError": "Einstellungen konnten nicht gespeichert werden",
    "saved": "Gespeichert.",
    "save": "Speichern"
  },
```

- [ ] **Step 2: Write the failing test additions**

Replace the full contents of `apps/web/src/routes/Settings.test.tsx` with:

```tsx
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Settings from "./Settings";
import * as api from "../lib/api";

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return {
    ...actual,
    getPreferences: vi.fn(),
    setPreferences: vi.fn(),
  };
});

describe("Settings", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(api.getPreferences).mockResolvedValue({
      preferred_language: "Nederlands",
      date_format: "eu",
      time_format: "h24",
    });
    vi.mocked(api.setPreferences).mockResolvedValue({
      preferred_language: "English",
      date_format: "us",
      time_format: "h12",
    });
  });

  it("loads and selects the saved preferred language", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
  });

  it("loads and selects the saved date and time format", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Date format")).toHaveValue("eu"));
    expect(screen.getByLabelText("Time format")).toHaveValue("h24");
  });

  it("saves the selected language, date format, and time format, and shows a confirmation", async () => {
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
    fireEvent.change(screen.getByLabelText("Preferred language"), { target: { value: "English" } });
    fireEvent.change(screen.getByLabelText("Date format"), { target: { value: "us" } });
    fireEvent.change(screen.getByLabelText("Time format"), { target: { value: "h12" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await waitFor(() =>
      expect(api.setPreferences).toHaveBeenCalledWith({
        preferredLanguage: "English",
        dateFormat: "us",
        timeFormat: "h12",
      }),
    );
    expect(await screen.findByText("Saved.")).toBeInTheDocument();
  });

  it("shows an error message when saving fails", async () => {
    vi.mocked(api.setPreferences).mockRejectedValue(new api.ApiError(500, "Save boom"));
    render(<Settings />);
    await waitFor(() => expect(screen.getByLabelText("Preferred language")).toHaveValue("Nederlands"));
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Save boom")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx`
Expected: FAIL — `getByLabelText("Date format")` finds no element; `setPreferences` called with the old single-string argument

- [ ] **Step 4: Rewrite `Settings.tsx`**

Replace the full contents of `apps/web/src/routes/Settings.tsx` with:

```tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { AddressHistory } from "../components/AddressHistory";
import Card from "../components/Card";
import { PasskeySettings } from "../components/PasskeySettings";
import { Button } from "../components/ui/Button";
import { ApiError, getPreferences, setPreferences } from "../lib/api";
import { syncLanguage } from "../lib/auth";
import { toDateFormatPrefs, type DateFormat, type TimeFormat } from "../lib/dateFormat";
import { setDateFormatPrefs } from "../hooks/useDateFormat";

export default function Settings() {
  const { t } = useTranslation();
  const [language, setLanguage] = useState("");
  const [dateFormat, setDateFormat] = useState<DateFormat>("eu");
  const [timeFormat, setTimeFormat] = useState<TimeFormat>("h24");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const languageOptions = [
    { value: "", label: t("settings.noPreference") },
    { value: "English", label: "English" },
    { value: "Nederlands", label: "Nederlands" },
    { value: "Deutsch", label: "Deutsch" },
  ];

  const dateFormatOptions: { value: DateFormat; label: string }[] = [
    { value: "eu", label: t("settings.dateFormatEu") },
    { value: "us", label: t("settings.dateFormatUs") },
    { value: "iso", label: t("settings.dateFormatIso") },
  ];

  const timeFormatOptions: { value: TimeFormat; label: string }[] = [
    { value: "h24", label: t("settings.timeFormatH24") },
    { value: "h12", label: t("settings.timeFormatH12") },
  ];

  useEffect(() => {
    getPreferences()
      .then((prefs) => {
        setLanguage(prefs.preferred_language ?? "");
        const parsed = toDateFormatPrefs(prefs.date_format, prefs.time_format);
        setDateFormat(parsed.dateFormat);
        setTimeFormat(parsed.timeFormat);
      })
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.loadError")))
      .finally(() => setLoading(false));
  }, [t]);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await setPreferences({ preferredLanguage: language || null, dateFormat, timeFormat });
      syncLanguage(language || null);
      setDateFormatPrefs({ dateFormat, timeFormat });
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.saveError"));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold text-ink">{t("settings.title")}</h1>

      <Card className="flex max-w-md flex-col gap-3">
        <div>
          <label className="text-sm font-medium text-ink" htmlFor="preferred-language">
            {t("settings.preferredLanguage")}
          </label>
          <p className="text-xs text-ink-3">{t("settings.preferredLanguageHint")}</p>
        </div>
        {loading ? (
          <p className="text-sm text-ink-3">{t("common.loading")}</p>
        ) : (
          <>
            <select
              id="preferred-language"
              value={language}
              onChange={(e) => {
                setLanguage(e.target.value);
                setSaved(false);
              }}
              className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
            >
              {languageOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>

            <div>
              <label className="text-sm font-medium text-ink" htmlFor="date-format">
                {t("settings.dateFormat")}
              </label>
              <select
                id="date-format"
                value={dateFormat}
                onChange={(e) => {
                  setDateFormat(e.target.value as DateFormat);
                  setSaved(false);
                }}
                className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              >
                {dateFormatOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-sm font-medium text-ink" htmlFor="time-format">
                {t("settings.timeFormat")}
              </label>
              <select
                id="time-format"
                value={timeFormat}
                onChange={(e) => {
                  setTimeFormat(e.target.value as TimeFormat);
                  setSaved(false);
                }}
                className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
              >
                {timeFormatOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </>
        )}
        {error && <p className="text-sm text-danger">{error}</p>}
        {saved && <p className="text-sm text-success">{t("settings.saved")}</p>}
        <Button onClick={handleSave} disabled={loading || saving} className="self-start">
          {t("settings.save")}
        </Button>
      </Card>

      <PasskeySettings />

      <div className="flex flex-col gap-2">
        <div>
          <h2 className="text-lg font-semibold text-ink">{t("addressHistory.title")}</h2>
          <p className="text-xs text-ink-3">{t("addressHistory.description")}</p>
        </div>
        <AddressHistory />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx`
Expected: PASS, all 4 tests green

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/Settings.tsx apps/web/src/routes/Settings.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat: date/time format pickers in Settings"
```

---

### Task 8: Sweep — `AddressHistory.tsx`

**Files:**
- Modify: `apps/web/src/components/AddressHistory.tsx`

**Interfaces:**
- Consumes: `useDateFormat` from `../hooks/useDateFormat` (Task 4).

`apps/web/src/components/AddressHistory.test.tsx` was checked during planning: none of its 9 tests assert on the rendered `valid_from`/`valid_to` date text (they check the address line, status label, linked-document count, buttons, and the `correctResidency` call args instead) — no test file changes are needed for this task.

- [ ] **Step 1: Add the hook and format the two date fields**

In `apps/web/src/components/AddressHistory.tsx`, change the import block:

```typescript
import Card from "./Card";
import EmptyState from "./EmptyState";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";
```

to:

```typescript
import Card from "./Card";
import EmptyState from "./EmptyState";
import { Alert } from "./ui/Alert";
import { Button } from "./ui/Button";
import { useDateFormat } from "../hooks/useDateFormat";
```

Inside `export function AddressHistory(...)`, add the hook call right after the existing `const { t } = useTranslation();` line:

```typescript
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
```

Change:

```tsx
              <p className="text-xs text-ink-3">
                {residency.valid_from ?? "?"} &rarr;{" "}
                {residency.valid_to ?? t("addressHistory.current")}
              </p>
```

to:

```tsx
              <p className="text-xs text-ink-3">
                {residency.valid_from ? formatDate(residency.valid_from) : "?"} &rarr;{" "}
                {residency.valid_to ? formatDate(residency.valid_to) : t("addressHistory.current")}
              </p>
```

- [ ] **Step 2: Run the test file to confirm no regression**

Run: `cd apps/web && npx vitest run src/components/AddressHistory.test.tsx`
Expected: PASS, all 9 tests green (confirms the planning-time check in the task header — no test asserted on the raw date text)

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/AddressHistory.tsx
git commit -m "feat: format address-history dates per user preference"
```

---

### Task 9: Sweep — `KanbanBoard.tsx` + `Tasks.tsx`

**Files:**
- Modify: `apps/web/src/components/ui/KanbanBoard.tsx`
- Modify: `apps/web/src/components/ui/KanbanBoard.test.tsx`
- Modify: `apps/web/src/routes/Tasks.tsx`

**Interfaces:**
- `KanbanBoard` gains a required prop `formatDate: (value: string) => string`, supplied by `Tasks.tsx` (which has hook access) — `KanbanBoard` itself stays a plain presentational component, no hook call inside it.
- `dueBadge()` in `Tasks.tsx` gains a third parameter `formatDate: (value: string) => string`.

- [ ] **Step 1: Update `KanbanBoard.tsx` to take `formatDate` as a prop**

Change:

```typescript
export function KanbanBoard({
  tasks,
  onMove,
}: {
  tasks: TaskOut[];
  onMove: (taskId: string, status: TaskStatus, position: number) => void;
}) {
```

to:

```typescript
export function KanbanBoard({
  tasks,
  onMove,
  formatDate,
}: {
  tasks: TaskOut[];
  onMove: (taskId: string, status: TaskStatus, position: number) => void;
  formatDate: (value: string) => string;
}) {
```

Change:

```tsx
                {(task.due_date || task.assignee) && (
                  <div className="mt-1 text-[11px] text-ink-3">
                    {task.due_date ? `Due ${task.due_date}` : null}
                    {task.due_date && task.assignee ? " · " : null}
                    {task.assignee ?? null}
                  </div>
                )}
```

to:

```tsx
                {(task.due_date || task.assignee) && (
                  <div className="mt-1 text-[11px] text-ink-3">
                    {task.due_date ? `Due ${formatDate(task.due_date)}` : null}
                    {task.due_date && task.assignee ? " · " : null}
                    {task.assignee ?? null}
                  </div>
                )}
```

- [ ] **Step 2: Update `KanbanBoard.test.tsx` render calls**

In `apps/web/src/components/ui/KanbanBoard.test.tsx`, every `render(<KanbanBoard tasks={...} onMove={...} />)` call needs a `formatDate` prop. Add `formatDate={(v) => v}` (identity — these tests don't exercise real formatting) to all five `render(<KanbanBoard ... />)` calls, e.g. change:

```tsx
    render(<KanbanBoard tasks={tasks} onMove={() => {}} />);
```

to:

```tsx
    render(<KanbanBoard tasks={tasks} onMove={() => {}} formatDate={(v) => v} />);
```

Do this for every occurrence in the file (there are 5: the three plain `onMove={() => {}}` calls, and both `onMove={onMove}` calls). The one test that checks due-date text specifically:

```tsx
  it("shows due date and assignee meta when present", () => {
    const tasks = [task({ due_date: "2026-08-01", assignee: "Alice" })];
    render(<KanbanBoard tasks={tasks} onMove={() => {}} />);
    expect(screen.getByText("Due 2026-08-01 · Alice")).toBeInTheDocument();
  });
```

becomes:

```tsx
  it("shows due date and assignee meta when present", () => {
    const tasks = [task({ due_date: "2026-08-01", assignee: "Alice" })];
    render(<KanbanBoard tasks={tasks} onMove={() => {}} formatDate={(v) => v} />);
    expect(screen.getByText("Due 2026-08-01 · Alice")).toBeInTheDocument();
  });
```

(identity `formatDate` keeps this specific assertion's raw-string expectation valid — it's testing KanbanBoard's own composition, not the real formatter, which is covered by Task 3's tests).

- [ ] **Step 3: Run `KanbanBoard.test.tsx`**

Run: `cd apps/web && npx vitest run src/components/ui/KanbanBoard.test.tsx`
Expected: PASS

- [ ] **Step 4: Wire `Tasks.tsx`**

Change the imports:

```typescript
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { KanbanBoard } from "../components/ui/KanbanBoard";
```

to:

```typescript
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { KanbanBoard } from "../components/ui/KanbanBoard";
import { useDateFormat } from "../hooks/useDateFormat";
```

Change `dueBadge`'s signature and its one use of the raw date:

```typescript
function dueBadge(dueDate: string, t: (key: string, opts?: Record<string, unknown>) => string) {
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) {
    const days = Math.round((new Date(today).getTime() - new Date(dueDate).getTime()) / 86400000);
    return { variant: "danger" as const, label: t("tasks.dueOverdue", { count: days }) };
  }
  if (dueDate === today) {
    return { variant: "warning" as const, label: t("tasks.dueToday") };
  }
  return { variant: "default" as const, label: t("tasks.due", { date: dueDate }) };
}
```

to:

```typescript
function dueBadge(
  dueDate: string,
  t: (key: string, opts?: Record<string, unknown>) => string,
  formatDate: (value: string) => string,
) {
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) {
    const days = Math.round((new Date(today).getTime() - new Date(dueDate).getTime()) / 86400000);
    return { variant: "danger" as const, label: t("tasks.dueOverdue", { count: days }) };
  }
  if (dueDate === today) {
    return { variant: "warning" as const, label: t("tasks.dueToday") };
  }
  return { variant: "default" as const, label: t("tasks.due", { date: formatDate(dueDate) }) };
}
```

In `export default function Tasks()`, add the hook right after `const { t } = useTranslation();`:

```typescript
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
```

Update the two call sites that use `dueBadge` and `KanbanBoard`:

```tsx
      ) : view === "board" ? (
        <KanbanBoard tasks={tasks} onMove={handleMove} />
```

to:

```tsx
      ) : view === "board" ? (
        <KanbanBoard tasks={tasks} onMove={handleMove} formatDate={formatDate} />
```

and:

```typescript
            const badge = task.due_date ? dueBadge(task.due_date, t) : null;
```

to:

```typescript
            const badge = task.due_date ? dueBadge(task.due_date, t, formatDate) : null;
```

- [ ] **Step 5: Run `Tasks.test.tsx`**

Run: `cd apps/web && npx vitest run src/routes/Tasks.test.tsx`

The existing test `expect(screen.getByText("Due 2026-08-01")).toBeInTheDocument();` (list view, via `dueBadge`/`t("tasks.due", {...})`) will now render the EU-formatted date. Update it to:

```tsx
    expect(screen.getByText("Due 01/08/2026")).toBeInTheDocument();
```

Re-run: `cd apps/web && npx vitest run src/routes/Tasks.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/components/ui/KanbanBoard.tsx apps/web/src/components/ui/KanbanBoard.test.tsx apps/web/src/routes/Tasks.tsx apps/web/src/routes/Tasks.test.tsx
git commit -m "feat: format task due dates per user preference"
```

---

### Task 10: Sweep — `PasskeySettings.tsx`

**Files:**
- Modify: `apps/web/src/components/PasskeySettings.tsx`

**Interfaces:**
- Consumes: `useDateFormat` from `../hooks/useDateFormat` (Task 4).

- [ ] **Step 1: Add the hook and format both date fields**

Change the imports:

```typescript
import Card from "./Card";
import EmptyState from "./EmptyState";
import { Button } from "./ui/Button";
```

to:

```typescript
import Card from "./Card";
import EmptyState from "./EmptyState";
import { Button } from "./ui/Button";
import { useDateFormat } from "../hooks/useDateFormat";
```

Add the hook right after `const { t } = useTranslation();`:

```typescript
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
```

Change:

```tsx
                <p className="text-xs text-ink-3">
                  {t("passkeys.createdAt", { date: credential.created_at.slice(0, 10) })}
                  {credential.last_used_at && ` · ${t("passkeys.lastUsed", { date: credential.last_used_at.slice(0, 10) })}`}
                </p>
```

to:

```tsx
                <p className="text-xs text-ink-3">
                  {t("passkeys.createdAt", { date: formatDate(credential.created_at) })}
                  {credential.last_used_at && ` · ${t("passkeys.lastUsed", { date: formatDate(credential.last_used_at) })}`}
                </p>
```

- [ ] **Step 2: Typecheck (no existing test file for this component)**

Run: `cd apps/web && npx tsc --noEmit 2>&1 | grep -i "PasskeySettings"`
Expected: no output (or only pre-existing baseline errors unrelated to this change — compare against a run before this edit if unsure)

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/PasskeySettings.tsx
git commit -m "feat: format passkey dates per user preference"
```

---

### Task 11: Sweep — `Workspace.tsx` + `Cases.tsx`

**Files:**
- Modify: `apps/web/src/routes/Workspace.tsx`
- Modify: `apps/web/src/routes/Cases.tsx`

**Interfaces:**
- Consumes: `useDateFormat` from `../hooks/useDateFormat` (Task 4).

- [ ] **Step 1: Wire `Workspace.tsx`**

Change the imports:

```typescript
import { DataTable, type Column } from "../components/ui/DataTable";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/form";
import EmptyState from "../components/EmptyState";
import { useBulkSelection } from "../hooks/useBulkSelection";
```

to:

```typescript
import { DataTable, type Column } from "../components/ui/DataTable";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { TextField } from "../components/ui/form";
import EmptyState from "../components/EmptyState";
import { useBulkSelection } from "../hooks/useBulkSelection";
import { useDateFormat } from "../hooks/useDateFormat";
```

Add the hook right after `const { t } = useTranslation();` inside `export default function Workspace()`:

```typescript
  const { t } = useTranslation();
  const { formatDateTime } = useDateFormat();
```

Change:

```typescript
    {
      key: "created_at",
      header: t("documents.columnUploaded"),
      sortable: true,
      sortValue: (doc) => doc.created_at,
      render: (doc) => new Date(doc.created_at).toLocaleString(),
    },
```

to:

```typescript
    {
      key: "created_at",
      header: t("documents.columnUploaded"),
      sortable: true,
      sortValue: (doc) => doc.created_at,
      render: (doc) => formatDateTime(doc.created_at),
    },
```

- [ ] **Step 2: Wire `Cases.tsx`**

Change the imports:

```typescript
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { ApiError, createCase, listCases, type CaseOut } from "../lib/api";
```

to:

```typescript
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { ApiError, createCase, listCases, type CaseOut } from "../lib/api";
import { useDateFormat } from "../hooks/useDateFormat";
```

Add the hook right after `const { t } = useTranslation();` inside `export default function Cases()`:

```typescript
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
```

Change:

```tsx
                <span className="mt-auto text-xs text-ink-3">
                  {new Date(c.created_at).toLocaleDateString()}
                </span>
```

to:

```tsx
                <span className="mt-auto text-xs text-ink-3">
                  {formatDate(c.created_at)}
                </span>
```

- [ ] **Step 3: Run both test files to confirm no regression**

Run: `cd apps/web && npx vitest run src/routes/Workspace.test.tsx src/routes/Cases.test.tsx`
Expected: PASS (neither file asserts on the rendered date text today)

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/routes/Workspace.tsx apps/web/src/routes/Cases.tsx
git commit -m "feat: format document/case dates per user preference"
```

---

### Task 12: Sweep — `AdminDashboard.tsx`

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx`

**Interfaces:**
- Consumes: `useDateFormat` from `../hooks/useDateFormat` (Task 4) — called once inside `BugsTab()` and once inside `UsersTab()` (separate function components in the same file).

- [ ] **Step 1: Add the import**

Change:

```typescript
import { DataTable, type Column } from "../components/ui/DataTable";
```

to:

```typescript
import { DataTable, type Column } from "../components/ui/DataTable";
import { useDateFormat } from "../hooks/useDateFormat";
```

(this import is shared by both `BugsTab` and `UsersTab`, both defined later in the same file)

- [ ] **Step 2: Wire `BugsTab`**

Inside `function BugsTab() {`, add the hook right after `const { t } = useTranslation();`:

```typescript
function BugsTab() {
  const { t } = useTranslation();
  const { formatDateTime } = useDateFormat();
```

Change:

```tsx
            <span className="text-xs text-ink-3">{new Date(report.created_at).toLocaleString()}</span>
```

to:

```tsx
            <span className="text-xs text-ink-3">{formatDateTime(report.created_at)}</span>
```

- [ ] **Step 3: Wire `UsersTab`**

Inside `function UsersTab() {`, add the hook right after `const { t } = useTranslation();`:

```typescript
function UsersTab() {
  const { t } = useTranslation();
  const { formatDate } = useDateFormat();
```

Change:

```typescript
    {
      key: "created_at",
      header: t("admin.createdAtColumn"),
      render: (row) => new Date(row.created_at).toLocaleDateString(),
    },
```

to:

```typescript
    {
      key: "created_at",
      header: t("admin.createdAtColumn"),
      render: (row) => formatDate(row.created_at),
    },
```

- [ ] **Step 4: Run the test file**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx`
Expected: PASS (no existing assertion on the rendered date text)

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx
git commit -m "feat: format admin bug-report and user dates per user preference"
```

---

### Task 13: Sweep — `Vehicles.tsx` (APK expiry date)

**Files:**
- Modify: `apps/web/src/routes/Vehicles.tsx`
- Modify: `apps/web/src/routes/Vehicles.test.tsx`

**Interfaces:**
- Consumes: `parseCompactDate` from `../lib/dateFormat` (Task 3), `useDateFormat` from `../hooks/useDateFormat` (Task 4).

- [ ] **Step 1: Fix the test fixture to match the real RDW contract**

The RDW open-data API (`services/api/src/api/rdw_client.py`) returns `vervaldatum_apk` as a compact `"YYYYMMDD"` string (confirmed against a real RDW record per that file's comments) — the current test fixture's `"2027-01-01"` doesn't match that shape. In `apps/web/src/routes/Vehicles.test.tsx`, change:

```typescript
  vervaldatum_apk: "2027-01-01", wam_verzekerd: "Ja", openstaande_terugroepactie_indicator: null,
```

to:

```typescript
  vervaldatum_apk: "20270101", wam_verzekerd: "Ja", openstaande_terugroepactie_indicator: null,
```

- [ ] **Step 2: Write the new failing test**

Add to the `describe("Vehicles", ...)` block in `apps/web/src/routes/Vehicles.test.tsx`, after the `"renders the vehicle list with RDW details"` test:

```tsx
  it("formats the APK expiry date instead of showing the raw RDW string", async () => {
    render(<Vehicles />);
    await screen.findByText("AB-12-CD");
    expect(screen.getByText("01/01/2027")).toBeInTheDocument();
    expect(screen.queryByText("20270101")).not.toBeInTheDocument();
  });
```

- [ ] **Step 3: Run to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Vehicles.test.tsx`
Expected: FAIL — `20270101` is rendered raw, `01/01/2027` is not found

- [ ] **Step 4: Wire `VehicleStatus`**

In `apps/web/src/routes/Vehicles.tsx`, change the imports:

```typescript
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import LicensePlateInput from "../components/LicensePlateInput";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ApiError, listVehicles, lookupVehicle, type VehicleOut } from "../lib/api";
```

to:

```typescript
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import LicensePlateInput from "../components/LicensePlateInput";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { ApiError, listVehicles, lookupVehicle, type VehicleOut } from "../lib/api";
import { parseCompactDate } from "../lib/dateFormat";
import { useDateFormat } from "../hooks/useDateFormat";
```

Change `VehicleStatus` to call the hook and format the APK date:

```tsx
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
      <dd className="text-ink"><WamBadge wamVerzekerd={vehicle.wam_verzekerd} /></dd>
    </dl>
  );
}
```

to:

```tsx
function VehicleStatus({ vehicle }: { vehicle: VehicleOut }) {
  const { formatDate } = useDateFormat();

  if (vehicle.fetched_at === null) {
    return <p className="text-sm text-ink-3">Nog niet opgehaald.</p>;
  }
  if (vehicle.merk === null) {
    return <p className="text-sm text-ink-3">Geen RDW-gegevens gevonden voor dit kenteken.</p>;
  }
  const apkDate = vehicle.vervaldatum_apk ? parseCompactDate(vehicle.vervaldatum_apk) : null;
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
      <dt className="text-ink-2">Merk / model</dt>
      <dd className="text-ink">{vehicle.merk} {vehicle.handelsbenaming}</dd>
      <dt className="text-ink-2">Voertuigsoort</dt>
      <dd className="text-ink">{vehicle.voertuigsoort ?? "-"}</dd>
      <dt className="text-ink-2">Kleur</dt>
      <dd className="text-ink">{vehicle.eerste_kleur ?? "-"}</dd>
      <dt className="text-ink-2">APK-vervaldatum</dt>
      <dd className="text-ink">{apkDate ? formatDate(apkDate) : "-"}</dd>
      <dt className="text-ink-2">WAM-verzekerd</dt>
      <dd className="text-ink"><WamBadge wamVerzekerd={vehicle.wam_verzekerd} /></dd>
    </dl>
  );
}
```

- [ ] **Step 5: Run to verify it passes**

Run: `cd apps/web && npx vitest run src/routes/Vehicles.test.tsx`
Expected: PASS, all tests green

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/Vehicles.tsx apps/web/src/routes/Vehicles.test.tsx
git commit -m "fix(ui): format the APK expiry date instead of showing the raw RDW string"
```

---

## Final verification

- [ ] **Backend full suite**

Run: `cd services/api && /Users/stagnaat/.claude/jobs/2ca9e950/tmp/venv/bin/pytest -q`
Expected: all pass (no new failures beyond any pre-existing baseline)

- [ ] **Frontend full suite**

Run: `cd apps/web && npx vitest run`
Expected: all pass

- [ ] **Frontend typecheck**

Run: `cd apps/web && npx tsc --noEmit`
Expected: no new errors beyond the pre-existing baseline (React 19/react-router-dom JSX type mismatches, jest-dom matcher types — confirmed present before this feature and unrelated to it)

- [ ] **Manually verify in a browser** (per the `verify` skill / this project's UI-change convention): start the dev server, open Settings, change date format to US and time format to 12h, save, then check Tasks (due-date badges), Vehicles (APK expiry), Documents (uploaded column), Cases (created date), Admin → Users/Bug Reports, and the address-history section on Settings itself all reflect the new format without a page reload.
