# Login Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle `/login` with this session's design tokens and fix a routing
bug where it currently renders inside the authenticated app shell (full
`Sidebar` + mobile chrome visible to unauthenticated visitors).

**Architecture:** No backend changes. Two frontend files: `App.tsx` gets a new
top-level `/login` route sibling to `/` (removed from `AppShell`'s
`<Layout>`-wrapped routes), and `Login.tsx` gets a restyled card (`glass-surface`,
`rounded-ds-lg`, `BrandMark` + gradient wordmark, `bg-gradient-brand` submit
button) inside a full-viewport centered wrapper, replacing the old
`Card`-wrapped layout.

**Tech Stack:** React + TypeScript, Vitest + Testing Library, Tailwind CSS
(custom design tokens via CSS custom properties, see `apps/web/src/tokens.css`
and `apps/web/tailwind.config.js`), React Router v6.

## Global Constraints

- No backend changes at all — this sub-project is frontend-only.
- Do not modify `TextField`, `Select`, or any other shared form component —
  they're used across the whole app's forms; a login-only redesign must not
  change their radius/style.
- Do not modify `Button.tsx` or `Card.tsx` (the shared components) — Login's
  restyle uses its own plain wrapper markup instead of `Card`, and accepts
  `Button`'s existing built-in `rounded-xl` corner radius as-is (confirmed
  during planning: an appended `rounded-ds-lg` className does NOT visually
  override `Button`'s baked-in `rounded-xl` — both are equal-specificity
  Tailwind utilities and `rounded-xl`'s generated CSS rule currently compiles
  after `rounded-ds-lg`'s, so `rounded-xl` wins the cascade. Fighting this
  would require editing the shared `Button` component, which is out of
  scope). Do not attempt to add a border-radius override to `Button` usages
  in this plan.
- No changes to `handleSubmit`, `handlePasskeyLogin`, `useAuth()`,
  `isPasskeySupported()`, or any state/hooks in `Login.tsx` — visual/routing
  changes only.
- No i18n key changes — reuse existing `auth.*` keys exactly as they are.
- Do not touch `/onboard`'s routing or `Landing.tsx` — both are explicitly
  out of scope (see spec's Background section).
- Design tokens available and confirmed present in this codebase:
  `glass-surface` (CSS class, `apps/web/src/index.css`), `bg-gradient-brand`
  (Tailwind `backgroundImage` utility → `background-image: var(--gradient-brand)`),
  `rounded-ds-lg` (Tailwind `borderRadius` utility → `border-radius: var(--radius-lg)`),
  `shadow-raised` (Tailwind `boxShadow` utility, already used by the old `Card`
  component).

---

### Task 1: Move `/login` out of the authenticated app shell

**Files:**
- Modify: `apps/web/src/App.tsx`

**Interfaces:**
- Consumes: nothing new.
- Produces: nothing new — this is a pure routing rearrangement, no new
  exports or props for Task 2 to consume.

**Context:** `apps/web/src/App.tsx` currently has this structure (read the
full file before editing — it's 212 lines):

```tsx
function AppShell() {
  return (
    <Layout>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/onboard" element={<Onboard />} />
        {/* ...all the ProtectedRoute-wrapped routes... */}
        <Route path="*" element={<NotFound />} />
      </Routes>
    </Layout>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <LoadingBarProvider>
            <CommandCenterStateProvider>
              <CommandCenter />
              <PhonePromptModal />
              <RouteChangeLoadingBar />
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/*" element={<AppShell />} />
              </Routes>
            </CommandCenterStateProvider>
          </LoadingBarProvider>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
```

Because `/login` is one of `AppShell`'s routes, it renders inside `AppShell`'s
`<Layout>` wrapper — which always renders `Sidebar` and `MobileTabBar`
regardless of whether `user` is set (`Sidebar.tsx:31` calls
`navItemsForRole(user?.role)`, which returns the full nav list even when
`role` is `undefined`). An unauthenticated visitor on `/login` currently sees
the entire app's navigation chrome around the login card.

- [ ] **Step 1: Run the existing baseline tests for the affected routes**

No test currently imports `App.tsx` directly (confirmed: `grep -rln "from
\"\.\./App\"\|import App from" --include="*.test.tsx"` in `apps/web/src`
returns nothing), so there is no direct regression test for this exact
routing behavior. Run the closest existing coverage as a baseline instead:

Run: `npx vitest run src/routes/Login.test.tsx src/routes/Landing.test.tsx`
Expected: PASS (4 tests in `Login.test.tsx`, existing tests in
`Landing.test.tsx` — both render their component standalone via
`MemoryRouter`, not through `App.tsx`, so this step confirms nothing is
already broken, not that this task's change is covered).

- [ ] **Step 2: Move the `/login` route to the top level**

In `apps/web/src/App.tsx`, remove this line from inside `AppShell`'s
`<Routes>` (it is currently the first `<Route>` in that block):

```tsx
        <Route path="/login" element={<Login />} />
```

Then add a new top-level route inside `App()`'s outer `<Routes>`, as a
sibling of `/` and `/*`, placed before the `/*` catch-all:

Before:
```tsx
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/*" element={<AppShell />} />
              </Routes>
```

After:
```tsx
              <Routes>
                <Route path="/" element={<RootRoute />} />
                <Route path="/login" element={<Login />} />
                <Route path="/*" element={<AppShell />} />
              </Routes>
```

`Login` is still imported at the top of the file (`import Login from
"./routes/Login";`) — that import stays, only its usage moves. Do not
remove the `Login` import.

- [ ] **Step 3: Run the baseline tests again to confirm nothing broke**

Run: `npx vitest run src/routes/Login.test.tsx src/routes/Landing.test.tsx`
Expected: PASS, same 4 + existing `Landing.test.tsx` count as Step 1 —
unchanged, since neither test mounts `App.tsx`.

- [ ] **Step 4: Run the full frontend suite as a broader regression guard**

`App.tsx` is the application's entry point, so run the whole suite once to
catch any indirect breakage:

Run: `npx vitest run`
Expected: PASS, same total test count as before this task (check the
"Test Files" / "Tests" summary line against a `git stash`-free baseline if
in doubt — there should be zero new failures).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/App.tsx
git commit -m "fix: render /login outside the authenticated app shell"
```

**Note for the implementer:** do not create a new `App.test.tsx` for this
task. Mocking the full provider tree (`AuthProvider`, `ToastProvider`,
`LoadingBarProvider`, `CommandCenterStateProvider`) just to assert "no
sidebar renders on /login" is disproportionate to a one-line route move.
Live-browser verification of this exact behavior happens in Task 2 (it's
more efficient to verify the routing fix and the visual restyle together in
one pass, since both require the same dev-server + screenshot setup).

---

### Task 2: Restyle `Login.tsx` with design tokens and brand identity

**Files:**
- Modify: `apps/web/src/routes/Login.tsx`

**Interfaces:**
- Consumes: Task 1's routing change (this task's live-browser verification
  step confirms both the visual restyle AND that `/login` no longer shows
  `Sidebar`/`MobileTabBar` chrome).
- Produces: nothing new — same component export, same props (none — it's a
  route-level component), same internal state/handlers.

**Context:** current `apps/web/src/routes/Login.tsx` (read the full file
first — 102 lines) imports `Card` from `"../components/Card"` and wraps
everything in `<Card className="mx-auto mt-16 max-w-sm p-6">`. `Card`'s own
implementation (`apps/web/src/components/Card.tsx`) hardcodes
`rounded-2xl border border-edge bg-surface p-4 shadow-raised` as its base
classes — appending an override className to change `rounded-2xl` or
`bg-surface` risks the same unreliable-cascade problem flagged in Global
Constraints for `Button`, so this task replaces the `Card` wrapper with a
plain `<div>` carrying the exact classes needed (the same approach already
used elsewhere in this codebase, e.g. `apps/web/src/components/
CategoryFilterGrid.tsx:34`: `<div className="glass-surface ... rounded-ds-lg p-3">`).

- [ ] **Step 1: Run the baseline test**

Run: `npx vitest run src/routes/Login.test.tsx`
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

(`Button`, `TextField`, and all other existing imports stay unchanged.)

- [ ] **Step 3: Replace the returned JSX**

Change the return statement from:

```tsx
  return (
    <Card className="mx-auto mt-16 max-w-sm p-6">
      <h1 className="text-2xl font-semibold text-ink">{t("auth.title")}</h1>
      <p className="mt-1 text-sm text-ink-2">{t("auth.subtitle")}</p>

      {isPasskeySupported() && (
        <>
          <Button
            type="button"
            variant="secondary"
            className="mt-6 w-full"
            onClick={handlePasskeyLogin}
            disabled={passkeySubmitting}
          >
            {passkeySubmitting ? t("auth.passkeySubmitting") : t("auth.passkeyLogin")}
          </Button>
          <div className="my-4 flex items-center gap-3 text-xs text-ink-2">
            <div className="h-px flex-1 bg-edge" />
            {t("auth.orDivider")}
            <div className="h-px flex-1 bg-edge" />
          </div>
        </>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-4">
        <TextField
          label={t("auth.username")}
          value={username}
          onChange={setUsername}
          autoComplete="username"
          autoFocus
          required
        />
        <TextField
          label={t("auth.password")}
          type="password"
          value={password}
          onChange={setPassword}
          autoComplete="current-password"
          required
        />
        {error && <p className="text-sm text-danger">{error}</p>}
        <Button type="submit" disabled={submitting}>
          {submitting ? t("auth.submitting") : t("auth.submit")}
        </Button>
      </form>
    </Card>
  );
```

to:

```tsx
  return (
    <div className="flex min-h-screen items-center justify-center bg-page p-4">
      <div className="glass-surface w-full max-w-sm rounded-ds-lg p-6 shadow-raised">
        <div className="mb-6 flex items-center gap-2">
          <BrandMark size={32} />
          <span className="text-lg font-semibold text-ink">
            Collabr
            <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
              AI
            </span>
            ns
          </span>
        </div>

        <h1 className="text-2xl font-semibold text-ink">{t("auth.title")}</h1>
        <p className="mt-1 text-sm text-ink-2">{t("auth.subtitle")}</p>

        {isPasskeySupported() && (
          <>
            <Button
              type="button"
              variant="secondary"
              className="mt-6 w-full"
              onClick={handlePasskeyLogin}
              disabled={passkeySubmitting}
            >
              {passkeySubmitting ? t("auth.passkeySubmitting") : t("auth.passkeyLogin")}
            </Button>
            <div className="my-4 flex items-center gap-3 text-xs text-ink-2">
              <div className="h-px flex-1 bg-edge" />
              {t("auth.orDivider")}
              <div className="h-px flex-1 bg-edge" />
            </div>
          </>
        )}

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <TextField
            label={t("auth.username")}
            value={username}
            onChange={setUsername}
            autoComplete="username"
            autoFocus
            required
          />
          <TextField
            label={t("auth.password")}
            type="password"
            value={password}
            onChange={setPassword}
            autoComplete="current-password"
            required
          />
          {error && <p className="text-sm text-danger">{error}</p>}
          <Button type="submit" disabled={submitting} className="bg-gradient-brand hover:opacity-90">
            {submitting ? t("auth.submitting") : t("auth.submit")}
          </Button>
        </form>
      </div>
    </div>
  );
```

The `bg-gradient-brand hover:opacity-90` className on the submit `Button` is
safe to append (unlike the radius case): `bg-gradient-brand` sets
`background-image`, while `Button`'s `primary`-variant base class
(`bg-accent`) sets `background-color` — two different CSS properties that
compose (the opaque gradient image paints over the color), so there's no
cascade-order risk here. `hover:opacity-90` gives visible hover feedback
since the base `hover:bg-accent-hover` (also a `background-color`) is hidden
under the gradient image.

- [ ] **Step 4: Run the test to verify it still passes**

Run: `npx vitest run src/routes/Login.test.tsx`
Expected: PASS (4 tests, unchanged) — all queries (`getByRole("heading",
...)`, `getByLabelText(...)`, `getByRole("button", ...)`) target text/roles
that are unaffected by the className/wrapper changes.

- [ ] **Step 5: Live-browser verification**

Temporarily override `useAuth()` in `apps/web/src/lib/auth.tsx` to return
`{ user: null, login: ..., loginWithPasskey: ... }` (a logged-out state —
Login only renders its form when `user` is falsy; use mock functions that
resolve, matching the established technique this session), start the dev
server, and check both:

1. **Task 1's fix**: navigate to `/login` and confirm NO `Sidebar` and NO
   mobile tab bar/header render around the card — just the centered card on
   a plain `bg-page` background, at both desktop and mobile widths.
2. **Task 2's restyle**: confirm the `BrandMark` + "Collabr**AI**ns" wordmark
   renders above the title, the card has a visibly frosted/translucent
   (`glass-surface`) look, and the submit button shows the brand gradient
   background.

Revert the `useAuth()` override via `git checkout -- apps/web/src/lib/auth.tsx`
before continuing — never commit it.

- [ ] **Step 6: Run the full frontend suite and build**

Run: `npx vitest run` then `npx vite build`
Expected: all tests PASS (same count as Task 1's Step 4), build succeeds with
no new errors.

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/routes/Login.tsx
git commit -m "feat: apply design tokens and brand identity to Login"
```

---

## Deployment

1. Push to `main`.
2. On the server: `git pull` (check for and discard any byte-identical
   leftover rsync artifacts first, same as prior sub-projects).
3. Rebuild the frontend: `docker compose exec web sh -c 'cd /app/apps/web &&
   npx vite build'`.
4. No backend restart needed — no backend changes in this plan.
5. Verify live: open `/login` in an incognito/logged-out browser session,
   confirm no sidebar chrome and the new card styling, at both desktop and
   mobile widths.
