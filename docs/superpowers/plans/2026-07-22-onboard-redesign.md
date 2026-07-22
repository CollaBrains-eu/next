# Onboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle `/onboard` with this session's design tokens and fix the
same routing bug `/login` had — it currently renders inside the
authenticated app shell (full `Sidebar` + mobile chrome visible to
anonymous visitors following an invite link).

**Architecture:** No backend changes. Two frontend files: `App.tsx` gets a
new top-level `/onboard` route sibling to `/login` (removed from
`AppShell`'s `<Layout>`-wrapped routes), and `Onboard.tsx` gets the same
`glass-surface`/`BrandMark` shell `Login.tsx` already uses, wrapping all
three status branches (`loading`, `valid`, `invalid`).

**Tech Stack:** React + TypeScript, Vitest + Testing Library, Tailwind CSS
(custom design tokens, see `apps/web/src/tokens.css` and
`apps/web/tailwind.config.js`), React Router v6.

## Global Constraints

- No backend changes at all — this sub-project is frontend-only.
- Do not modify `TextField`, `Select`, `Button.tsx`, or `Card.tsx` — same
  reasoning as the Login plan: `Button`'s built-in `rounded-xl` does not
  reliably yield to an appended `rounded-ds-lg` override in this Tailwind
  setup (confirmed empirically during Login planning), and these are shared
  components used across the whole app.
- No changes to `checkOnboardingToken`, state handling (`status`,
  `displayName`), or any other logic in `Onboard.tsx` — visual/routing
  changes only.
- No i18n key changes — reuse existing `onboard.*` keys exactly as they are.
- Do not touch `Landing.tsx` — confirmed out of scope (deliberately distinct
  dark marketing page, see the spec's Background section).
- No `bg-gradient-brand` button treatment in this plan — unlike `Login.tsx`'s
  single primary submit button, `Onboard.tsx`'s CTA is contextual
  (primary/secondary depending on status) and doesn't warrant it.
- Design tokens available and already in use by `Login.tsx` (confirmed
  present): `glass-surface` (CSS class, `apps/web/src/index.css`),
  `rounded-ds-lg` (Tailwind `borderRadius` utility), `shadow-raised`
  (Tailwind `boxShadow` utility), `BrandMark` (component,
  `apps/web/src/components/BrandMark.tsx`).

---

### Task 1: Move `/onboard` out of the authenticated app shell

**Files:**
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — pure routing rearrangement.

**Context:** `apps/web/src/App.tsx` currently has (confirmed via `grep -n`):
- Line 64: `<Route path="/onboard" element={<Onboard />} />` — the first
  route inside `AppShell`'s `<Layout>`-wrapped `<Routes>`.
- Lines 202-204: the outer `<Routes>` in `App()`, currently:
  ```tsx
                <Route path="/" element={<RootRoute />} />
                <Route path="/login" element={<Login />} />
                <Route path="/*" element={<AppShell />} />
  ```
  (`/login` was moved here in the prior Login-redesign sub-project, following
  this exact same pattern.)

- [ ] **Step 1: Run the existing baseline test**

Run: `npx vitest run src/routes/Onboard.test.tsx`
Expected: PASS (4 tests) — baseline before touching `App.tsx`. (No test
imports `App.tsx` directly — confirmed via the same `grep` check used in the
Login plan — so this is the closest existing coverage, not a direct test of
the routing change itself.)

- [ ] **Step 2: Move the `/onboard` route to the top level**

In `apps/web/src/App.tsx`, remove this line from inside `AppShell`'s
`<Routes>` (currently line 64, the first `<Route>` in that block):

```tsx
        <Route path="/onboard" element={<Onboard />} />
```

Then add a new top-level route alongside `/login`:

Before:
```tsx
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/login" element={<Login />} />
                <Route path="/*" element={<AppShell />} />
              </Routes>
```

After:
```tsx
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/login" element={<Login />} />
                <Route path="/onboard" element={<Onboard />} />
                <Route path="/*" element={<AppShell />} />
              </Routes>
```

The `Onboard` import at the top of the file stays unchanged — only its
usage moves.

- [ ] **Step 3: Run the baseline test again to confirm nothing broke**

Run: `npx vitest run src/routes/Onboard.test.tsx`
Expected: PASS, same 4 tests — unchanged, since the test renders `<Onboard/>`
standalone via `MemoryRouter`, not through `App.tsx`.

- [ ] **Step 4: Run the full frontend suite as a broader regression guard**

Run: `npx vitest run`
Expected: PASS, same total test count as before this task (520 tests / 81
files as of the last full run in this project — treat any INCREASE from a
prior task's leftover work as fine, but zero new failures).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/App.tsx
git commit -m "fix: render /onboard outside the authenticated app shell"
```

**Note for the implementer:** do not create a new `App.test.tsx`. Same
reasoning as the Login plan: mocking the full provider tree for one
assertion is disproportionate to a one-line route move. Live-browser
verification happens in Task 2, alongside the visual restyle.

---

### Task 2: Restyle `Onboard.tsx` with the same shell as `Login.tsx`

**Files:**
- Modify: `apps/web/src/routes/Onboard.tsx`

**Interfaces:**
- Consumes: Task 1's routing change (this task's live-browser verification
  confirms both the visual restyle AND that `/onboard` no longer shows
  `Sidebar`/`MobileTabBar` chrome).
- Produces: nothing new — same component export, same props (none — it's a
  route-level component), same internal state/handlers.

**Context:** current `apps/web/src/routes/Onboard.tsx` (read the full file
first — 62 lines) imports `Card` from `"../components/Card"` and wraps all
three status branches in a single `<Card className="mx-auto mt-16 max-w-sm
p-6 text-center">`. This task replaces that wrapper with the same plain-div
shell `Login.tsx` now uses (`glass-surface`, `rounded-ds-lg`, `BrandMark` +
gradient wordmark), keeping the `text-center` alignment the original `Card`
applied to all three branches.

- [ ] **Step 1: Run the baseline test**

Run: `npx vitest run src/routes/Onboard.test.tsx`
Expected: PASS (4 tests) — baseline before touching the file.

- [ ] **Step 2: Update imports**

Remove:
```tsx
import Card from "../components/Card";
```

Add:
```tsx
import { BrandMark } from "../components/BrandMark";
```

(`Button`, `SkeletonLines`, and all other existing imports stay unchanged.)

- [ ] **Step 3: Replace the returned JSX**

Change the return statement from:

```tsx
  return (
    <Card className="mx-auto mt-16 max-w-sm p-6 text-center">
      {status === "loading" && <SkeletonLines />}

      {status === "valid" && (
        <>
          <h1 className="text-2xl font-semibold text-ink">{t("onboard.welcomeTitle", { name: displayName })}</h1>
          <p className="mt-2 text-sm text-ink-2">{t("onboard.welcomeBody")}</p>
          <Link to="/login" className="mt-6 block">
            <Button className="w-full">{t("onboard.continueToLogin")}</Button>
          </Link>
        </>
      )}

      {status === "invalid" && (
        <>
          <h1 className="text-2xl font-semibold text-ink">{t("onboard.invalidTitle")}</h1>
          <p className="mt-2 text-sm text-ink-2">{t("onboard.invalidBody")}</p>
          <Link to="/login" className="mt-6 block">
            <Button variant="secondary" className="w-full">
              {t("onboard.continueToLogin")}
            </Button>
          </Link>
        </>
      )}
    </Card>
  );
```

to:

```tsx
  return (
    <div className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="glass-surface w-full max-w-sm rounded-ds-lg p-6 text-center shadow-raised">
        <div className="mb-6 flex items-center justify-center gap-2">
          <BrandMark size={32} />
          <span className="text-lg font-semibold text-ink">
            Collabr
            <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
              AI
            </span>
            ns
          </span>
        </div>

        {status === "loading" && <SkeletonLines />}

        {status === "valid" && (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("onboard.welcomeTitle", { name: displayName })}</h1>
            <p className="mt-2 text-sm text-ink-2">{t("onboard.welcomeBody")}</p>
            <Link to="/login" className="mt-6 block">
              <Button className="w-full">{t("onboard.continueToLogin")}</Button>
            </Link>
          </>
        )}

        {status === "invalid" && (
          <>
            <h1 className="text-2xl font-semibold text-ink">{t("onboard.invalidTitle")}</h1>
            <p className="mt-2 text-sm text-ink-2">{t("onboard.invalidBody")}</p>
            <Link to="/login" className="mt-6 block">
              <Button variant="secondary" className="w-full">
                {t("onboard.continueToLogin")}
              </Button>
            </Link>
          </>
        )}
      </div>
    </div>
  );
```

The brand block renders in all three states (including `loading`), giving
the skeleton state the same identity treatment rather than a bare
`SkeletonLines` floating with no header — this is a deliberate improvement,
not just a mechanical port, since the original bare `Card` had no identity
in any state either.

- [ ] **Step 4: Run the test to verify it still passes**

Run: `npx vitest run src/routes/Onboard.test.tsx`
Expected: PASS (4 tests, unchanged) — all queries (`getByRole("heading",
...)`, `getByRole("link", ...)`) target text/roles unaffected by the
className/wrapper changes.

- [ ] **Step 5: Live-browser verification**

Start the dev server (`npx vite` from `apps/web`) — no `useAuth()` stub
needed, same reasoning as the Login plan: `/onboard` is meant to be visited
by anonymous visitors, so the natural logged-out state is exactly what's
being verified. Check:

1. **Task 1's fix**: navigate to `/onboard` (with no token, to hit the
   `invalid` branch — the simplest to reach without a real backend token)
   and confirm NO `Sidebar` and NO mobile tab bar/header render — just the
   centered card on `bg-page`, at both desktop and mobile widths. If the
   dev server's `checkOnboardingToken` call fails outright (no backend
   running) rather than resolving `{valid: false}`, that still lands on the
   `invalid` branch via the existing `.catch()` — either path is fine for
   verifying the shell.
2. **Task 2's restyle**: confirm the `BrandMark` + wordmark renders above
   the status content, and the card has the `glass-surface` frosted look.

Verify via DOM/computed-style checks if the screenshot tool is unreliable in
this environment (as it was during Login's verification) — query for
`document.querySelector('aside')` (should be null) and the `.glass-surface`
element's computed `backdropFilter`/`borderRadius`, the same fallback
approach used for Login.

- [ ] **Step 6: Run the full frontend suite and build**

Run: `npx vitest run` then `npx vite build`
Expected: all tests PASS (same count as Task 1's Step 4), build succeeds
with no new errors.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/routes/Onboard.tsx
git commit -m "feat: apply design tokens and brand identity to Onboard"
```

---

## Deployment

1. Push to `main`.
2. On the server: `git pull` (check for and discard any byte-identical
   leftover rsync artifacts first, same as prior sub-projects).
3. Rebuild the frontend: `docker compose exec web sh -c 'cd /app/apps/web &&
   npx vite build'`.
4. No backend restart needed — no backend changes in this plan.
5. Verify live: open `/onboard` (with an invalid/missing token) in an
   incognito/logged-out browser session, confirm no sidebar chrome and the
   new card styling, at both desktop and mobile widths.
