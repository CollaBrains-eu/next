# Phase 17d — Personal AI Preferences / Settings UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Phase 13 Personal AI preferences backend (`GET`/`PUT /preferences/me`) a UI: a new `/settings` page with a language select.

**Architecture:** Pure frontend addition — no backend changes, since the preferences endpoints already exist and are fully functional. One new `api.ts` interface/functions, one new page, one new sidebar nav item, built on the Phase 17a shell.

**Tech Stack:** React + TypeScript + Vite + Tailwind (existing stack, no new dependencies).

## Global Constraints

- This sub-phase depends on Phase 17a having merged (`Layout`/`Sidebar` must exist in `main`). It does not depend on 17b or 17c.
- No new frontend test pattern — verification is `tsc -b` typecheck plus a live browser check, matching 17a/17b/17c.

---

### Task 1: `api.ts` additions for preferences

**Files:**
- Modify: `apps/web/src/lib/api.ts`

**Interfaces:**
- Produces: `PreferencesOut { preferred_language: string | null }`, `getPreferences(): Promise<PreferencesOut>` (`GET /preferences/me`), `setPreferences(preferredLanguage: string | null): Promise<PreferencesOut>` (`PUT /preferences/me`). Consumed by `Settings.tsx` in Task 2.

- [ ] **Step 1: Append to `apps/web/src/lib/api.ts`**

```ts
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

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 3: Run the existing frontend test suite**

Run: `cd /opt/collabrains && docker compose exec web pnpm test`
Expected: `5 passed`.

- [ ] **Step 4: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/lib/api.ts
git commit -m "Phase 17d task 1: api.ts additions for preferences"
```

---

### Task 2: `Settings.tsx`

**Files:**
- Create: `apps/web/src/routes/Settings.tsx`

**Interfaces:**
- Consumes: `getPreferences`, `setPreferences`, `PreferencesOut` (Task 1).
- Produces: `export default function Settings()`, wired into routing in Task 3.

- [ ] **Step 1: Write `Settings.tsx`**

```tsx
import { useEffect, useState } from "react";
import Card from "../components/Card";
import { ApiError, getPreferences, setPreferences } from "../lib/api";

const LANGUAGE_OPTIONS = [
  { value: "", label: "No preference" },
  { value: "English", label: "English" },
  { value: "Nederlands", label: "Nederlands" },
  { value: "Deutsch", label: "Deutsch" },
];

export default function Settings() {
  const [language, setLanguage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getPreferences()
      .then((prefs) => setLanguage(prefs.preferred_language ?? ""))
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load preferences"))
      .finally(() => setLoading(false));
  }, []);

  async function handleSave() {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      await setPreferences(language || null);
      setSaved(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save preferences");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Settings</h1>

      <Card className="flex max-w-md flex-col gap-3">
        <div>
          <label className="text-sm font-medium" htmlFor="preferred-language">
            Preferred language
          </label>
          <p className="text-xs text-slate-500">Used by AI Chat to respond in your preferred language.</p>
        </div>
        {loading ? (
          <p className="text-sm text-slate-500">Loading…</p>
        ) : (
          <select
            id="preferred-language"
            value={language}
            onChange={(e) => {
              setLanguage(e.target.value);
              setSaved(false);
            }}
            className="rounded border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none"
          >
            {LANGUAGE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        )}
        {error && <p className="text-sm text-red-600">{error}</p>}
        {saved && <p className="text-sm text-green-700">Saved.</p>}
        <button
          onClick={handleSave}
          disabled={loading || saving}
          className="self-start rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
        >
          Save
        </button>
      </Card>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 3: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/routes/Settings.tsx
git commit -m "Phase 17d task 2: Settings page"
```

---

### Task 3: Wire into Sidebar and routing

**Files:**
- Modify: `apps/web/src/components/Sidebar.tsx`
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: `Settings` (Task 2).

- [ ] **Step 1: Add the "Settings" nav item to `Sidebar.tsx`**

Change `NAV_ITEMS` in `apps/web/src/components/Sidebar.tsx` (adding after "Assistant", which 17c already added):

```ts
const NAV_ITEMS = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
  { to: "/cases", label: "Cases" },
  { to: "/assistant", label: "Assistant" },
  { to: "/settings", label: "Settings" },
];
```

- [ ] **Step 2: Add the route to `App.tsx`**

Add the import (after the `Assistant` import, which 17c already added):

```tsx
import Assistant from "./routes/Assistant";
import Settings from "./routes/Settings";
```

Add the route (after the `/assistant` route, before the `*` catch-all):

```tsx
            <Route
              path="/settings"
              element={
                <ProtectedRoute>
                  <Settings />
                </ProtectedRoute>
              }
            />
```

- [ ] **Step 3: Typecheck**

Run: `cd /opt/collabrains && docker compose exec web pnpm exec tsc -b`
Expected: no output, exit code 0.

- [ ] **Step 4: Run the existing frontend test suite**

Run: `cd /opt/collabrains && docker compose exec web pnpm test`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
cd /opt/collabrains
git add apps/web/src/components/Sidebar.tsx apps/web/src/App.tsx
git commit -m "Phase 17d task 3: wire Settings into sidebar and routing"
```

---

### Task 4: ADR, rebuild, live verification, PR

**Files:**
- Create: `docs/adr/0035-phase17d-settings-ui.md`

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0035-phase17d-settings-ui.md`, same style as `docs/adr/0025-phase10-knowledge-graph-2.md`. Cover: this is the last of the four Phase 17 sub-phases (17a shell, 17b Cases, 17c Assistant, 17d this one); the language options are a fixed curated list (`English`/`Nederlands`/`Deutsch`) matching this project's existing Paperless OCR language footprint (`eng+nld+deu`) rather than a free-text field, even though the backend stores an arbitrary string; this is intentionally the only setting on the page today — it exists so future settings have a home, not because more exist to add right now. Also note that with this sub-phase merged, all four Phase 17 sub-phases are complete and the sidebar now has all 8 nav items the spec named.

- [ ] **Step 2: Rebuild the production bundle**

Run: `cd /opt/collabrains && docker compose exec -e VITE_API_URL='' web pnpm build`
Expected: builds successfully with no errors.

- [ ] **Step 3: Live verification**

Use the Playwright MCP against `https://v78281.1blu.de`: log in, click "Settings" in the sidebar, confirm the language select defaults to "No preference" (or whatever's currently set), pick a language, click Save, confirm "Saved." appears, then reload the page and confirm the selection persisted.

- [ ] **Step 4: Commit the ADR, push, open the draft PR**

```bash
cd /opt/collabrains
git add docs/adr/0035-phase17d-settings-ui.md
git commit -m "Phase 17d: Settings UI"
git push -u origin phase-17d-settings-ui
gh pr create --draft --base main --head phase-17d-settings-ui \
  --title "Phase 17d: Personal AI Preferences / Settings UI" \
  --body "See docs/superpowers/specs/2026-07-04-frontend-catchup-design.md for the full Phase 17 design and docs/adr/0035-phase17d-settings-ui.md for this sub-phase's decisions. Adds a new /settings page for the Phase 13 preferred-language preference, wired into the Phase 17a sidebar shell. No backend changes. This is the last of the four Phase 17 sub-phases -- completes the whole phase."
```

## Self-Review Notes

**Spec coverage**: covers every item in the spec's "Architecture: Personal AI Preferences / Settings UI (17d)" section.

**Placeholder scan**: no TBD/TODO; every step has complete code or an exact command.

**Type consistency**: `PreferencesOut.preferred_language: string | null` (Task 1) matches exactly how `Settings.tsx` (Task 2) reads it (`prefs.preferred_language ?? ""`) and writes it back (`setPreferences(language || null)`).
