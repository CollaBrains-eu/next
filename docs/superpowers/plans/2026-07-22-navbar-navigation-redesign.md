# Navbar Navigation Redesign Implementation Plan

**Goal:** Replace the fixed left `Sidebar` with a responsive top `Navbar`, delete the now-dead
collapse/drawer machinery, and confirm the rest of the app (forms, layout width) already matches the
Violet Design Language artifact.

**Architecture:** One new `Navbar` component owns both the desktop bar and the mobile compact header +
hamburger (mirrors how `Sidebar` used to own both its desktop and mobile-drawer rendering via one
component branched with Tailwind `md:` prefixes). A new `MobileNavDrawer` replaces `Sidebar`'s old role
as the mobile "show everything" panel, with a plain active-row highlight instead of the animated pill
(the drawer is transient; the extra motion isn't worth the code).

**Tech stack:** React + TypeScript, react-router NavLink, existing `Dropdown`/`Avatar`/`Tooltip`/
`AlertsBell`/`BrandMark` components, Tailwind design tokens already in `tailwind.config.js`.

## Global Constraints

- Reuse existing components/tokens; do not introduce new CSS variables or one-off colors — everything
  in this change must render only from `tailwind.config.js` tokens already in use by `Sidebar.tsx`/`Layout.tsx`.
- Primary nav = Dashboard, Documents, Cases, Tasks, Chat. Secondary ("More" dropdown) = Calendar, Legal
  Draft, Entities, Vehicles, Assistant. Account dropdown (behind `Avatar`) = Settings, Admin (admin role
  only), Sign out.
- i18n: every visible string goes through `useTranslation()`/`t()`, added to all three locale files
  (en/de/nl) — no hardcoded English strings.
- No backend changes. Baseline is 520/520 frontend tests passing; suite must stay green (net changes:
  remove `Sidebar`/`useSidebarCollapsed` tests, add `Navbar`/`MobileNavDrawer` tests).

---

### Task 1: i18n keys

**Files:** `apps/web/src/locales/{en,de,nl}.json`

- [ ] Remove `common.expandSidebar` and `common.collapseSidebar` from all three files.
- [ ] Add `common.more`: en `"More"`, de `"Mehr"`, nl `"Meer"`.
- [ ] Run `npx vitest run src/styles/designTokens.test.js src/lib/navigation.test.ts` — unaffected, just a
      sanity check the JSON still parses (any locale-completeness test, if one exists, will also catch
      missing keys — check for one via `grep -rl "en.json" src --include=*.test.*` first).
- [ ] Commit: `git add apps/web/src/locales && git commit -m "i18n: add common.more, drop sidebar-collapse keys"`

### Task 2: Navbar component

**Files:**
- Create: `apps/web/src/components/Navbar.tsx`
- Test: `apps/web/src/components/Navbar.test.tsx`

**Interfaces:**
- Consumes: `navItemsForRole(role)` from `../lib/navigation` (existing), `useAuth()`, `useDarkMode()`,
  `useCommandCenterState()` (`openPalette`), `Dropdown`/`Avatar`/`Tooltip`/`AlertsBell`/`BrandMark` from
  existing component files, `useEscapeToClose`.
- Produces: `export default function Navbar()` — no props (owns its own mobile-drawer open state
  internally and renders `MobileNavDrawer` itself). Exports nothing else.

Split the role-filtered nav items locally:
```tsx
const PRIMARY_PATHS = ["/", "/documents", "/cases", "/tasks", "/chat"];
const allItems = navItemsForRole(user?.role).filter((i) => i.to !== "/settings");
const primaryItems = allItems.filter((i) => PRIMARY_PATHS.includes(i.to));
const secondaryItems = allItems.filter((i) => !PRIMARY_PATHS.includes(i.to));
```
(`/settings` is filtered out of the nav-item list entirely — it lives in the account dropdown instead.)

Horizontal sliding active-pill: same technique as the old `Sidebar.tsx` nav pill, axis-swapped
(`offsetLeft`/`offsetWidth` instead of `offsetTop`/`offsetHeight`):
```tsx
const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
const [pillStyle, setPillStyle] = useState<{ left: number; width: number }>({ left: 0, width: 0 });

useEffect(() => {
  const activeItem = primaryItems.find((item) =>
    item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)
  );
  const el = activeItem ? itemRefs.current[activeItem.to] : null;
  if (el) setPillStyle({ left: el.offsetLeft, width: el.offsetWidth });
}, [location.pathname, primaryItems]);
```
If no primary item is active (route is under a secondary path), render the pill with `width: 0` (no
`el` match → `pillStyle` keeps its last value but visually there's no active `NavLink` state applied, so
it reads correctly — don't special-case this, `isActive` from `NavLink` already governs per-item text
color regardless of the pill).

Full markup:
```tsx
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronDown, Menu } from "lucide-react";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useCommandCenterState } from "../lib/commandCenter";
import { Dropdown } from "./ui/Dropdown";
import { Tooltip } from "./ui/Tooltip";
import { Avatar } from "./ui/Avatar";
import { AlertsBell } from "./AlertsBell";
import { BrandMark } from "./BrandMark";
import { MobileNavDrawer } from "./MobileNavDrawer";
import { navItemsForRole } from "../lib/navigation";

const PRIMARY_PATHS = ["/", "/documents", "/cases", "/tasks", "/chat"];

function useMobileHeaderTitle(): string {
  const { t } = useTranslation();
  const location = useLocation();
  if (location.pathname === "/") return "CollaBrains";
  const item = navItemsForRole(undefined).find((i) => i.to !== "/" && location.pathname.startsWith(i.to));
  return item ? t(item.labelKey) : "CollaBrains";
}

export default function Navbar() {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { openPalette } = useCommandCenterState();
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();
  const [drawerOpen, setDrawerOpen] = useState(false);
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pillStyle, setPillStyle] = useState<{ left: number; width: number }>({ left: 0, width: 0 });
  const title = useMobileHeaderTitle();

  const allItems = navItemsForRole(user?.role).filter((i) => i.to !== "/settings");
  const primaryItems = allItems.filter((i) => PRIMARY_PATHS.includes(i.to));
  const secondaryItems = allItems.filter((i) => !PRIMARY_PATHS.includes(i.to));

  useEffect(() => {
    const activeItem = primaryItems.find((item) =>
      item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)
    );
    const el = activeItem ? itemRefs.current[activeItem.to] : null;
    if (el) setPillStyle({ left: el.offsetLeft, width: el.offsetWidth });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const accountOptions = [
    { label: t("nav.settings"), onSelect: () => navigate("/settings") },
    ...(user?.role === "admin" ? [{ label: t("nav.admin"), onSelect: () => navigate("/admin") }] : []),
    { label: t("common.signOut"), onSelect: logout, danger: true },
  ];

  const moreOptions = secondaryItems.map((item) => ({
    label: t(item.labelKey),
    onSelect: () => navigate(item.to),
  }));

  return (
    <>
      <header className="sticky top-0 z-30 glass-surface border-b border-edge">
        {/* Desktop bar */}
        <div className="mx-auto hidden h-16 max-w-screen-2xl items-center justify-between gap-4 px-6 md:flex">
          <NavLink to="/" className="flex shrink-0 items-center gap-2">
            <BrandMark size={28} />
            <span className="whitespace-nowrap text-lg font-semibold text-ink">
              Collabr
              <span className="bg-clip-text text-transparent" style={{ backgroundImage: "var(--gradient-brand)" }}>
                AI
              </span>
              ns
            </span>
          </NavLink>

          <nav className="relative flex flex-1 items-center gap-1">
            <span
              className="absolute bottom-1 z-0 h-9 rounded-lg bg-accent-soft transition-all duration-base ease-spring"
              style={{ left: pillStyle.left, width: pillStyle.width }}
            />
            {primaryItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  ref={(el) => {
                    itemRefs.current[item.to] = el;
                  }}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `relative z-10 flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors duration-fast ${
                      isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                    }`
                  }
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                  {t(item.labelKey)}
                </NavLink>
              );
            })}
            <Dropdown
              trigger={
                <span className="relative z-10 flex items-center gap-1 rounded-lg px-3 py-2 text-sm text-ink-2 transition-colors duration-fast hover:text-ink">
                  {t("common.more")}
                  <ChevronDown className="h-[14px] w-[14px]" aria-hidden="true" />
                </span>
              }
              options={moreOptions}
            />
          </nav>

          <div className="flex shrink-0 items-center gap-1">
            <Tooltip label={t("common.search")}>
              <button
                type="button"
                aria-label={t("common.search")}
                onClick={openPalette}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
              >
                <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" />
                  <path d="M17 17l-4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
              </button>
            </Tooltip>
            <AlertsBell />
            <button
              type="button"
              aria-label={isDark ? t("common.lightMode") : t("common.darkMode")}
              onClick={toggle}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
            >
              {isDark ? "☀️" : "🌙"}
            </button>
            {user && (
              <Dropdown
                trigger={
                  <span className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink">
                    <Avatar name={user.display_name} size={28} />
                    <ChevronDown className="h-[14px] w-[14px]" aria-hidden="true" />
                  </span>
                }
                options={accountOptions}
              />
            )}
          </div>
        </div>

        {/* Mobile compact header */}
        <div className="flex items-center justify-between gap-2 px-4 py-3 md:hidden">
          <div className="flex min-w-0 items-center gap-2">
            {user && (
              <NavLink to="/settings" aria-label={t("common.profile")}>
                <Avatar name={user.display_name} size={28} />
              </NavLink>
            )}
            <span data-testid="mobile-header-title" className="truncate text-lg font-semibold text-ink">
              {title}
            </span>
          </div>
          <div className="flex shrink-0 items-center gap-1">
            <button
              type="button"
              aria-label={t("common.search")}
              onClick={openPalette}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 hover:bg-hover hover:text-ink"
            >
              <svg width="18" height="18" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="9" cy="9" r="6" stroke="currentColor" strokeWidth="1.5" />
                <path d="M17 17l-4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
            </button>
            <AlertsBell />
            <button
              type="button"
              aria-label={isDark ? t("common.lightMode") : t("common.darkMode")}
              onClick={toggle}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 hover:bg-hover hover:text-ink"
            >
              {isDark ? "☀️" : "🌙"}
            </button>
            <button
              aria-label={t("common.openMenu")}
              onClick={() => setDrawerOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg text-ink-2 hover:bg-hover hover:text-ink"
            >
              <Menu className="h-5 w-5" aria-hidden="true" />
            </button>
          </div>
        </div>
      </header>
      <MobileNavDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} />
    </>
  );
}
```

Notes for the implementer:
- `isDark`/`toggle` come from `useDarkMode()` exactly as `Sidebar.tsx` used them — same hook, same call
  shape, no changes needed there.
- The `☀️`/`🌙` inline emoji matches the old `Layout.tsx` mobile header exactly (it used the same emoji
  as plain text, not an SVG, for this one button) — keep it, don't "upgrade" it to SVG as part of this
  task; that's an unrelated change.
- `lucide-react` is already a dependency (used throughout `Sidebar.tsx`/`navigation.ts`) — `ChevronDown`
  and `Menu` are both real exports from it, no new dependency needed.

- [ ] Write `Navbar.test.tsx` covering: brand link to `/`, primary items render with translated labels,
      clicking a "More" option (e.g. Calendar) navigates, account dropdown contains Settings + Sign out
      (and Admin only when `role: "admin"`), mobile header shows avatar linking to `/settings` and the
      title, clicking the hamburger opens `MobileNavDrawer` (assert via a testid or role it exposes —
      see Task 3), dark-mode toggle flips `document.documentElement`'s `dark` class. Model the test
      structure on the equivalent assertions already in `Sidebar.test.tsx`/`Layout.test.tsx` (read both
      before writing — they cover this exact behavior today, just against the old structure).
- [ ] Run: `npx vitest run src/components/Navbar.test.tsx` — expect PASS (Task 3 must land first if the
      drawer-open assertion depends on it; if doing these as one commit, write both together).
- [ ] Commit: `git add apps/web/src/components/Navbar.tsx apps/web/src/components/Navbar.test.tsx && git commit -m "feat: add top Navbar component"`

### Task 3: MobileNavDrawer component

**Files:**
- Create: `apps/web/src/components/MobileNavDrawer.tsx`
- Test: `apps/web/src/components/MobileNavDrawer.test.tsx`

**Interfaces:**
- Produces: `export function MobileNavDrawer({ open, onClose }: { open: boolean; onClose: () => void })`.

```tsx
import { NavLink } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useEscapeToClose } from "../hooks/useEscapeToClose";
import { Button } from "./ui/Button";
import { navItemsForRole } from "../lib/navigation";

export function MobileNavDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { t } = useTranslation();
  const navItems = navItemsForRole(user?.role);

  useEscapeToClose(open, onClose);

  return (
    <>
      {open && (
        <div
          data-testid="mobile-nav-backdrop"
          className="fixed inset-0 z-[70] bg-[#0D0C1A]/35 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-[71] flex w-64 flex-col justify-between border-r border-edge bg-sidebar-surface px-4 py-6 transition-transform duration-base ease-spring md:hidden ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <nav className="flex flex-col gap-1 text-sm">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={onClose}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 transition-colors duration-fast ${
                    isActive ? "bg-accent-soft font-semibold text-accent" : "text-ink-2 hover:bg-hover hover:text-ink"
                  }`
                }
              >
                <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                {t(item.labelKey)}
              </NavLink>
            );
          })}
        </nav>
        {user && (
          <div className="flex flex-col gap-2 border-t border-edge pt-4 text-sm">
            <span>{user.display_name}</span>
            <button onClick={logout} className="text-left text-ink-2 hover:text-ink">
              {t("common.signOut")}
            </button>
            <Button variant="ghost" size="sm" onClick={toggle} className="justify-start">
              {isDark ? t("common.lightMode") : t("common.darkMode")}
            </Button>
          </div>
        )}
      </aside>
    </>
  );
}
```

- [ ] Write `MobileNavDrawer.test.tsx`: renders nothing visible when `open=false` (backdrop absent), shows
      all nav items + sign out + display name when `open=true`, clicking the backdrop calls `onClose`,
      clicking a nav item calls `onClose` too (so the drawer doesn't stay open after navigating), Escape
      calls `onClose`. Mirror the equivalent tests already in `Sidebar.test.tsx` for its mobile-drawer
      behavior.
- [ ] Run: `npx vitest run src/components/MobileNavDrawer.test.tsx` — expect PASS.
- [ ] Commit: `git add apps/web/src/components/MobileNavDrawer.tsx apps/web/src/components/MobileNavDrawer.test.tsx && git commit -m "feat: add MobileNavDrawer replacing Sidebar's mobile drawer role"`

### Task 4: Rewire Layout, delete Sidebar

**Files:**
- Modify: `apps/web/src/components/Layout.tsx`
- Modify: `apps/web/src/components/Layout.test.tsx`
- Delete: `apps/web/src/components/Sidebar.tsx`, `apps/web/src/components/Sidebar.test.tsx`,
  `apps/web/src/hooks/useSidebarCollapsed.ts`, `apps/web/src/hooks/useSidebarCollapsed.test.ts`

New `Layout.tsx`:
```tsx
import type { ReactNode } from "react";
import Navbar from "./Navbar";
import MobileTabBar from "./MobileTabBar";

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-page text-ink">
      <Navbar />
      <main className="mx-auto w-full max-w-screen-2xl flex-1 px-4 py-6 pb-24 md:px-8 md:py-8 md:pb-8">
        {children}
      </main>
      <MobileTabBar />
    </div>
  );
}
```

- [ ] Update `Layout.test.tsx`: it currently renders `Layout` and asserts mobile-drawer/backdrop behavior,
      dark-mode toggle, profile avatar, bottom tab bar, and design-token background classes directly
      against `Layout`'s own markup. Since that markup has moved into `Navbar`/`MobileNavDrawer`
      (Task 2/3 already cover it there), trim `Layout.test.tsx` down to what `Layout` itself is still
      responsible for: renders `bg-page`/`text-ink` (not `bg-slate-*`) on its root, renders `children`,
      and renders exactly one `Navbar` + one `MobileTabBar`. Delete the now-redundant sidebar-backdrop/
      dark-mode/profile-avatar/bottom-tab-bar assertions from this file — they're duplicated, correctly,
      in `Navbar.test.tsx`/`MobileNavDrawer.test.tsx` now.
- [ ] Delete the four Sidebar files: `git rm apps/web/src/components/Sidebar.tsx apps/web/src/components/Sidebar.test.tsx apps/web/src/hooks/useSidebarCollapsed.ts apps/web/src/hooks/useSidebarCollapsed.test.ts`
- [ ] Run: `npx vitest run` (full suite) — expect the same total test count give or take (Sidebar's ~N
      tests removed, Navbar's + MobileNavDrawer's added), zero failures.
- [ ] Run: `npm run build` — must complete with no TypeScript errors (this catches any stray import of
      the deleted `Sidebar`/`useSidebarCollapsed` this plan missed).
- [ ] Commit: `git add -A && git commit -m "refactor: replace Sidebar with Navbar across the app shell"`

### Task 5: Local verification, then deploy

- [ ] `npm run dev` locally, open the app in a browser at desktop width (~1440px): confirm the navbar
      shows brand, 5 primary items with the sliding active pill, "More" dropdown with the other 5 items
      navigating correctly, search/bell/dark-toggle/avatar all functional, avatar dropdown shows
      Settings/Sign out (and Admin if logged in as an admin).
  Resize to mobile width (~390px): confirm the compact header (avatar+title, search/bell/dark/hamburger)
  and bottom tab bar both render, hamburger opens the drawer with all items, tapping an item closes the
  drawer and navigates, Escape and backdrop-click both close it.
- [ ] Spot-check 2-3 content pages (Dashboard, Documents, Settings) at both widths to confirm content now
      spans full width sensibly (no leftover gutter where the sidebar used to be) and respects the new
      `max-w-screen-2xl` cap on a wide viewport.
- [ ] Once verified locally: commit any final fixes, then follow the established deploy sequence (push to
      `origin/main`, SSH to `178.254.22.178`, reconcile git state, `docker compose exec web sh -c 'cd
      /app/apps/web && npx vite build'`), and confirm the live site at collabrains.eu renders the new
      navbar correctly (desktop + mobile).
