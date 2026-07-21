# Design System Extension + Sidebar/Layout Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend Violet DS with a brand gradient, a glass-surface utility, and a
named radius scale, then use those tokens to add a brand mark, per-item icons,
and a collapsible desktop rail to the sidebar — without regressing anything
the sidebar already does (active pill, mobile drawer, dark mode, command
palette, alerts).

**Architecture:** Additive CSS custom properties in the existing
`tokens.css`/`tailwind.config.js` token system, one new tiny hook
(`useSidebarCollapsed`, mirroring the existing `useDarkMode` hook's
localStorage pattern), one new presentational component (`BrandMark`, an
inline SVG — no external asset), a one-field addition to the existing
`navigation.ts` data, and a focused rewrite of `Sidebar.tsx`'s JSX (state and
existing behaviors are untouched).

**Tech Stack:** React 18 + TypeScript, Tailwind CSS, `lucide-react` (already a
dependency), Vitest + Testing Library (`jsdom` environment).

Full context: `docs/superpowers/specs/2026-07-22-design-system-sidebar-layout-design.md`.

## Global Constraints

- No new color hues — the brand gradient stays within the existing violet
  accent family (violet → a cooler blue/indigo secondary), per the spec's
  "rustig maar krachtig, niet overdreven" direction.
- Additive only: do not change the value of any existing CSS custom property
  in `tokens.css`, and do not touch Tailwind's built-in `borderRadius` keys
  (`lg`, `xl`, etc.) — new radius utilities must use distinct `ds-*` names so
  every existing `rounded-lg`/`rounded-xl`/`rounded-2xl` usage across the app
  keeps its current visual radius unchanged.
- Sidebar collapse is a **desktop-only** (`md:` and up) concept. The mobile
  drawer keeps its current full-width, full-overlay behavior regardless of
  the collapsed preference.
- No new npm dependencies — `lucide-react` and `framer-motion` are already
  installed; reuse them.
- Nav item labels must remain in the accessible tree (queryable by screen
  readers) even when the sidebar is visually collapsed to an icon rail — no
  icon-only link with no accessible name.
- This project commits directly to `main` (no PR flow, confirmed standing
  workflow) — each task ends with a local commit. Do **not** `git push` or
  deploy to the live server as part of this plan; that is a separate,
  explicit step to take up with the user once all tasks are done and
  verified locally (pushing to the shared GitHub remote and touching the
  production server are both actions that need their own checkpoint, not
  silent execution mid-plan).

---

### Task 1: Design tokens — brand gradient, glass-surface utility, named radius scale

**Files:**
- Modify: `apps/web/src/styles/tokens.css`
- Modify: `apps/web/src/index.css`
- Modify: `apps/web/tailwind.config.js`
- Test: `apps/web/src/styles/designTokens.test.js` (plain JS — see note below)

**Interfaces:**
- Produces: CSS custom properties `--gradient-brand-from`, `--gradient-brand-to`,
  `--gradient-brand` (light in `:root`, dark in `.dark`), `--bg-card-glass`
  (light in `:root`, dark in `.dark`), and theme-independent
  `--radius-sm`/`--radius-md`/`--radius-lg`/`--radius-xl` (defined once in
  `:root`). A `.glass-surface` CSS class in `index.css`. Tailwind utilities
  `bg-gradient-brand` (via `theme.extend.backgroundImage["gradient-brand"]`)
  and `rounded-ds-sm`/`rounded-ds-md`/`rounded-ds-lg`/`rounded-ds-xl` (via
  `theme.extend.borderRadius`). Task 3 (BrandMark) consumes
  `--gradient-brand-from`/`--gradient-brand-to` directly.

**Note on the test file's `.js` extension:** this project's `tsconfig.json`
only `include`s `"src"` and does not set `allowJs`, so plain `.js` files
inside `src/` are invisible to the `tsc -b` build gate (TypeScript silently
skips them) while Vitest (esbuild-based) runs them the same as any other
test file. This test needs to read raw CSS text and import the project-root
`tailwind.config.js`, and this repo has no ambient type declaration for
`*.css?raw` — writing it as `.ts` would make `tsc -b` fail with an
unresolvable-module error. Keep it `.js`; don't "fix" it to `.ts`.

**Note on reading the CSS files (confirmed by actually running this, not
assumed):** a Vite `?raw` import of a `.css` file (`import css from
"./tokens.css?raw"`) silently returns an **empty string** under Vitest —
Vite's CSS plugin short-circuits raw queries for `.css` files in the
Node/SSR context Vitest executes tests in. And `new URL("./tokens.css",
import.meta.url)` — the normally-correct Vite pattern for referencing a
file's real path — doesn't work either here: Vite statically detects that
exact `new URL(relative, import.meta.url)` call shape and rewrites it into a
dev-server asset URL (`http://localhost:.../...`) instead of a real `file://`
path, which then makes `readFileSync` throw `TypeError: The URL must be of
scheme file`. The fix used below: `node:fs`'s `readFileSync` with a plain
string path built from `path.join(import.meta.dirname, ...)` — `import.meta.dirname`
alone (not wrapped in `new URL(...)`) isn't pattern-matched by Vite's asset
rewriter, so it resolves to a real filesystem path.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/styles/designTokens.test.js`:

```js
import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import tailwindConfig from "../../tailwind.config.js";

const tokensCss = readFileSync(join(import.meta.dirname, "tokens.css"), "utf-8");
const indexCss = readFileSync(join(import.meta.dirname, "..", "index.css"), "utf-8");

describe("design tokens", () => {
  it("defines a two-stop brand gradient", () => {
    expect(tokensCss).toContain("--gradient-brand-from");
    expect(tokensCss).toContain("--gradient-brand-to");
    expect(tokensCss).toContain(
      "--gradient-brand: linear-gradient(135deg, var(--gradient-brand-from), var(--gradient-brand-to));"
    );
  });

  it("defines a glass-surface background token", () => {
    expect(tokensCss).toContain("--bg-card-glass");
  });

  it("defines a named radius scale without touching existing tokens", () => {
    expect(tokensCss).toContain("--radius-sm: 8px;");
    expect(tokensCss).toContain("--radius-md: 12px;");
    expect(tokensCss).toContain("--radius-lg: 16px;");
    expect(tokensCss).toContain("--radius-xl: 24px;");
    expect(tokensCss).toContain("--accent: #6C63FF;");
  });
});

describe(".glass-surface utility", () => {
  it("is defined once, using the glass background token", () => {
    expect(indexCss).toContain(".glass-surface");
    expect(indexCss).toContain("var(--bg-card-glass)");
    expect(indexCss).toContain("backdrop-filter: blur(16px);");
  });
});

describe("tailwind config", () => {
  it("exposes the gradient-brand background-image utility", () => {
    expect(tailwindConfig.theme.extend.backgroundImage).toEqual({
      "gradient-brand": "var(--gradient-brand)",
    });
  });

  it("exposes ds-prefixed radius utilities without overriding Tailwind's built-in scale", () => {
    const radius = tailwindConfig.theme.extend.borderRadius;
    expect(radius).toEqual({
      "ds-sm": "var(--radius-sm)",
      "ds-md": "var(--radius-md)",
      "ds-lg": "var(--radius-lg)",
      "ds-xl": "var(--radius-xl)",
    });
    expect(radius).not.toHaveProperty("lg");
    expect(radius).not.toHaveProperty("xl");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/styles/designTokens.test.js`
Expected: FAIL (tokens/utilities don't exist yet — `toContain` assertions fail).

- [ ] **Step 3: Add the tokens to `tokens.css`**

In `apps/web/src/styles/tokens.css`, add to the existing `:root` block (after
`--shadow-modal`, before the closing `}`):

```css
  --gradient-brand-from: #6C63FF;
  --gradient-brand-to: #4C6EFF;
  --gradient-brand: linear-gradient(135deg, var(--gradient-brand-from), var(--gradient-brand-to));
  --bg-card-glass: rgba(255, 255, 255, 0.72);
  --radius-sm: 8px;
  --radius-md: 12px;
  --radius-lg: 16px;
  --radius-xl: 24px;
```

And to the existing `.dark` block (after its `--shadow-modal`, before the
closing `}`) — no radius lines here, radius is theme-independent and stays in
`:root` only:

```css
  --gradient-brand-from: #8B82FF;
  --gradient-brand-to: #6E9BFF;
  --gradient-brand: linear-gradient(135deg, var(--gradient-brand-from), var(--gradient-brand-to));
  --bg-card-glass: rgba(19, 17, 42, 0.72);
```

- [ ] **Step 4: Add the `.glass-surface` utility to `index.css`**

In `apps/web/src/index.css`, add after the existing `.card-tilt` rule block:

```css
.glass-surface {
  background: var(--bg-card-glass);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
}
```

- [ ] **Step 5: Extend `tailwind.config.js`**

In `apps/web/tailwind.config.js`, inside `theme.extend` (alongside the
existing `colors`/`boxShadow`/`fontFamily` keys), add:

```js
      backgroundImage: {
        "gradient-brand": "var(--gradient-brand)",
      },
      borderRadius: {
        "ds-sm": "var(--radius-sm)",
        "ds-md": "var(--radius-md)",
        "ds-lg": "var(--radius-lg)",
        "ds-xl": "var(--radius-xl)",
      },
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/styles/designTokens.test.js`
Expected: PASS (all assertions green).

- [ ] **Step 7: Run the full frontend suite and a production build as a regression check**

Run: `cd apps/web && pnpm exec vitest run && pnpm exec vite build`

**Note (confirmed by actually running it, not assumed):** `pnpm exec tsc -b`
fails with 106 pre-existing errors even on an unmodified checkout (verified
by stashing this task's changes and re-running) — a `@types/react` version
mismatch across the workspace unrelated to this plan. This matches this
project's own documented history of a "pre-existing broken `tsc -b` gate"
that deploys already route around by building with `vite build` directly
instead of the full `tsc -b && vite build` chain. Use `vite build` (which
runs esbuild's own faster, more lenient transform) as the real regression
gate for every task in this plan, not `tsc -b`.

Expected: all existing tests still pass; `vite build` succeeds (this task
touches no `.ts`/`.tsx` files, only `.css`/`.js`, so no new build errors are
possible from this task itself).

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/styles/tokens.css apps/web/src/index.css apps/web/tailwind.config.js apps/web/src/styles/designTokens.test.js
git commit -m "feat(design-system): add brand gradient, glass-surface utility, named radius scale"
```

---

### Task 2: `useSidebarCollapsed` hook

**Files:**
- Create: `apps/web/src/hooks/useSidebarCollapsed.ts`
- Test: `apps/web/src/hooks/useSidebarCollapsed.test.ts`

**Interfaces:**
- Produces: `useSidebarCollapsed(): { collapsed: boolean; toggle: () => void }`,
  persisted under the localStorage key `"collabrains_sidebar_collapsed"`
  (string `"true"`/`"false"`). Task 6 (Sidebar integration) consumes this
  hook directly.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/hooks/useSidebarCollapsed.test.ts`:

```ts
import { describe, expect, it, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSidebarCollapsed } from "./useSidebarCollapsed";

describe("useSidebarCollapsed", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("defaults to expanded (not collapsed) with no stored preference", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed).toBe(false);
  });

  it("toggle collapses, and persists the preference", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle());
    expect(result.current.collapsed).toBe(true);
    expect(localStorage.getItem("collabrains_sidebar_collapsed")).toBe("true");
  });

  it("toggle twice returns to expanded and persists that", () => {
    const { result } = renderHook(() => useSidebarCollapsed());
    act(() => result.current.toggle());
    act(() => result.current.toggle());
    expect(result.current.collapsed).toBe(false);
    expect(localStorage.getItem("collabrains_sidebar_collapsed")).toBe("false");
  });

  it("reads an existing stored preference on mount", () => {
    localStorage.setItem("collabrains_sidebar_collapsed", "true");
    const { result } = renderHook(() => useSidebarCollapsed());
    expect(result.current.collapsed).toBe(true);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/hooks/useSidebarCollapsed.test.ts`
Expected: FAIL with "Cannot find module './useSidebarCollapsed'".

- [ ] **Step 3: Write the implementation**

Create `apps/web/src/hooks/useSidebarCollapsed.ts`:

```ts
import { useCallback, useState } from "react";

const STORAGE_KEY = "collabrains_sidebar_collapsed";

export function useSidebarCollapsed(): { collapsed: boolean; toggle: () => void } {
  const [collapsed, setCollapsed] = useState(() => localStorage.getItem(STORAGE_KEY) === "true");

  const toggle = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, String(next));
      return next;
    });
  }, []);

  return { collapsed, toggle };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/hooks/useSidebarCollapsed.test.ts`
Expected: PASS (4/4).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/hooks/useSidebarCollapsed.ts apps/web/src/hooks/useSidebarCollapsed.test.ts
git commit -m "feat(sidebar): add useSidebarCollapsed persisted-preference hook"
```

---

### Task 3: `BrandMark` component

**Files:**
- Create: `apps/web/src/components/BrandMark.tsx`
- Test: `apps/web/src/components/BrandMark.test.tsx`

**Interfaces:**
- Consumes: CSS custom properties `--gradient-brand-from`/`--gradient-brand-to`
  from Task 1.
- Produces: `BrandMark({ size?: number }): JSX.Element`, an accessible
  (`role="img"`, `aria-label="CollaBrains"`) inline SVG mark with a
  **unique-per-instance** gradient id (via `useId()`) so two instances on the
  same page (e.g. sidebar + a future mobile header usage) never collide.
  Task 6 (Sidebar integration) consumes this directly.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/BrandMark.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { BrandMark } from "./BrandMark";

describe("BrandMark", () => {
  it("renders an accessible svg mark", () => {
    render(<BrandMark />);
    expect(screen.getByRole("img", { name: "CollaBrains" })).toBeInTheDocument();
  });

  it("gives each instance a unique gradient id so multiple marks on one page don't collide", () => {
    render(
      <>
        <BrandMark />
        <BrandMark />
      </>
    );
    const gradientIds = Array.from(document.querySelectorAll("linearGradient")).map((el) => el.id);
    expect(gradientIds).toHaveLength(2);
    expect(new Set(gradientIds).size).toBe(2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/components/BrandMark.test.tsx`
Expected: FAIL with "Cannot find module './BrandMark'".

- [ ] **Step 3: Write the implementation**

Create `apps/web/src/components/BrandMark.tsx`:

```tsx
import { useId } from "react";

export function BrandMark({ size = 28 }: { size?: number }) {
  const gradientId = useId();

  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" role="img" aria-label="CollaBrains">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="24" y2="24" gradientUnits="userSpaceOnUse">
          <stop offset="0%" style={{ stopColor: "var(--gradient-brand-from)" }} />
          <stop offset="100%" style={{ stopColor: "var(--gradient-brand-to)" }} />
        </linearGradient>
      </defs>
      <rect x="1" y="5" width="14" height="14" rx="5" fill={`url(#${gradientId})`} />
      <rect x="9" y="1" width="14" height="14" rx="5" fill={`url(#${gradientId})`} opacity="0.55" />
    </svg>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/components/BrandMark.test.tsx`
Expected: PASS (2/2).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/BrandMark.tsx apps/web/src/components/BrandMark.test.tsx
git commit -m "feat(brand): add inline SVG BrandMark component"
```

---

### Task 4: `Tooltip` — optional `className` passthrough

**Files:**
- Modify: `apps/web/src/components/ui/Tooltip.tsx`
- Modify: `apps/web/src/components/ui/Tooltip.test.tsx`

**Interfaces:**
- Produces: `Tooltip({ label, children, className? })` — `className` is
  appended to the existing wrapper's classes, defaulting to `""` so every
  current call site (`Sidebar`'s search button, `AlertsBell`, `Drawer`,
  `DataTable`, `CaseDetail`) is unaffected. Task 6 (Sidebar integration)
  uses `className="md:w-full"` on the collapsed nav-item tooltip wrapper so
  it stretches to fill the icon rail's row instead of shrink-wrapping to
  icon width (the wrapper is `inline-flex`, which sizes to content by
  default).

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/components/ui/Tooltip.test.tsx` (inside the existing
`describe("Tooltip", ...)` block):

```tsx
  it("merges an optional className onto the wrapper without dropping the default classes", () => {
    render(
      <Tooltip label="Owner-only action" className="w-full">
        <button>Hover me</button>
      </Tooltip>
    );
    const wrapper = screen.getByRole("button", { name: "Hover me" }).parentElement;
    expect(wrapper).toHaveClass("group", "relative", "inline-flex", "w-full");
  });
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/components/ui/Tooltip.test.tsx`
Expected: FAIL (`wrapper` lacks the `w-full` class — the prop doesn't exist
yet on the current component signature, so passing it is currently a no-op).

- [ ] **Step 3: Update the implementation**

Replace the contents of `apps/web/src/components/ui/Tooltip.tsx`:

```tsx
import type { ReactNode } from "react";

export function Tooltip({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return (
    <span className={`group relative inline-flex ${className}`}>
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 translate-y-1 whitespace-nowrap rounded-lg bg-ink px-2.5 py-1 text-[11px] text-surface opacity-0 transition-all duration-fast ease-out-token group-hover:translate-y-0 group-hover:opacity-100">
        {label}
      </span>
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/components/ui/Tooltip.test.tsx`
Expected: PASS (3/3 — the 2 pre-existing tests plus the new one).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/ui/Tooltip.tsx apps/web/src/components/ui/Tooltip.test.tsx
git commit -m "feat(ui): let Tooltip accept an optional wrapper className"
```

---

### Task 5: `navigation.ts` — add an icon per nav item

**Files:**
- Modify: `apps/web/src/lib/navigation.ts`
- Create: `apps/web/src/lib/navigation.test.ts`

**Interfaces:**
- Produces: `NAV_ITEMS: { to: string; labelKey: string; icon: LucideIcon }[]`,
  `navItemsForRole(role): { to: string; labelKey: string; icon: LucideIcon }[]`
  — same shape as before plus `icon`. Task 6 (Sidebar integration) reads
  `item.icon` and renders it as `<Icon .../>`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/navigation.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { NAV_ITEMS, navItemsForRole } from "./navigation";

describe("navigation", () => {
  it("gives every nav item an icon component", () => {
    for (const item of NAV_ITEMS) {
      expect(item.icon).toBeDefined();
    }
  });

  it("appends the admin item, with its own icon, only for the admin role", () => {
    const memberItems = navItemsForRole("member");
    expect(memberItems.find((i) => i.to === "/admin")).toBeUndefined();

    const adminItems = navItemsForRole("admin");
    const adminItem = adminItems.find((i) => i.to === "/admin");
    expect(adminItem).toBeDefined();
    expect(adminItem?.icon).toBeDefined();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/lib/navigation.test.ts`
Expected: FAIL — `item.icon` is `undefined` for every item (field doesn't
exist yet).

- [ ] **Step 3: Update the implementation**

Replace the contents of `apps/web/src/lib/navigation.ts`:

```ts
import {
  LayoutDashboard,
  FileText,
  Sparkles,
  Scale,
  CheckSquare,
  Calendar,
  Users,
  FolderOpen,
  Car,
  Bot,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from "lucide-react";

export const NAV_ITEMS: { to: string; labelKey: string; icon: LucideIcon }[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard },
  { to: "/documents", labelKey: "nav.documents", icon: FileText },
  { to: "/chat", labelKey: "nav.aiChat", icon: Sparkles },
  { to: "/legal", labelKey: "nav.legalDraft", icon: Scale },
  { to: "/tasks", labelKey: "nav.tasks", icon: CheckSquare },
  { to: "/calendar", labelKey: "nav.calendar", icon: Calendar },
  { to: "/entities", labelKey: "nav.entities", icon: Users },
  { to: "/cases", labelKey: "nav.cases", icon: FolderOpen },
  { to: "/vehicles", labelKey: "nav.vehicles", icon: Car },
  { to: "/assistant", labelKey: "nav.assistant", icon: Bot },
  { to: "/settings", labelKey: "nav.settings", icon: Settings },
];

export function navItemsForRole(role: string | undefined): { to: string; labelKey: string; icon: LucideIcon }[] {
  if (role !== "admin") return NAV_ITEMS;
  return [...NAV_ITEMS, { to: "/admin", labelKey: "nav.admin", icon: ShieldCheck }];
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/lib/navigation.test.ts`
Expected: PASS (2/2).

- [ ] **Step 5: Run `Layout.test.tsx` as a regression check** (it imports `NAV_ITEMS`)

Run: `cd apps/web && pnpm exec vitest run src/components/Layout.test.tsx`
Expected: PASS, unchanged — `Layout.tsx` only reads `.to`/`.labelKey`, the
extra `icon` field is inert there.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/navigation.ts apps/web/src/lib/navigation.test.ts
git commit -m "feat(nav): add a lucide-react icon to every nav item"
```

---

### Task 6: Sidebar integration — collapse toggle, icons, brand mark

**Files:**
- Modify: `apps/web/src/components/Sidebar.tsx`
- Modify: `apps/web/src/components/Sidebar.test.tsx`
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`,
  `apps/web/src/locales/de.json`

**Interfaces:**
- Consumes: `useSidebarCollapsed()` (Task 2), `BrandMark` (Task 3), `Tooltip`
  with `className` (Task 4), `NAV_ITEMS`/`navItemsForRole` with `.icon`
  (Task 5).
- Produces: no new exports — `Sidebar`'s existing default-export signature
  (`{ mobileOpen?, onCloseMobile? }`) is unchanged.

**Design notes carried over from the spec (don't re-derive these, just
implement them):**
- The collapse toggle and its effects only apply at `md:` and up — every
  collapse-driven class is `md:`-prefixed so mobile is untouched.
- Nav-item label text stays in the DOM at all times (so it's always in the
  accessible tree); when collapsed it gets `md:sr-only` (visually hidden at
  desktop widths only, screen readers still see it, mobile still shows it
  visually since `sr-only` has no unprefixed effect here).
- The collapsed nav item is wrapped in `Tooltip` (hover-to-reveal label for
  sighted desktop users); expanded nav items are not wrapped, since the
  label is already visible inline.
- The header row's search icon is hidden when collapsed (`md:hidden` on its
  `Tooltip` wrapper) — `Cmd/Ctrl+K` (already wired in `CommandCenter.tsx`,
  independent of this button) remains the way to open the command palette
  when collapsed. `AlertsBell` stays visible in both states (it's already a
  fixed-size icon-only control, nothing to collapse).
- Icons are rendered via a plain `<Icon .../>` JSX element, **not** given a
  `data-testid` prop — `lucide-react`'s exported icon type only accepts
  standard SVG/ARIA props (no arbitrary-string index signature), so an
  unknown prop would fail `tsc -b`. Tests locate icons via
  `linkElement.querySelector("svg")` instead.

- [ ] **Step 1: Write the failing/updated tests**

Replace the contents of `apps/web/src/components/Sidebar.test.tsx`:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "./Sidebar";
import i18n from "../lib/i18n";
import { CommandCenterStateProvider, useCommandCenterState } from "../lib/commandCenter";
import * as api from "../lib/api";

vi.mock("../lib/auth", () => ({
  useAuth: () => ({ user: { display_name: "Ada Admin" }, logout: vi.fn() }),
}));

vi.mock("../lib/api", async () => {
  const actual = await vi.importActual<typeof api>("../lib/api");
  return { ...actual, listEntities: vi.fn() };
});

function OverlayProbe() {
  const { overlay } = useCommandCenterState();
  return <span data-testid="overlay-probe">{overlay}</span>;
}

function renderAt(
  path: string,
  props: { mobileOpen?: boolean; onCloseMobile?: () => void } = {},
) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <CommandCenterStateProvider>
        <OverlayProbe />
        <Sidebar {...props} />
      </CommandCenterStateProvider>
    </MemoryRouter>
  );
}

describe("Sidebar", () => {
  beforeEach(() => {
    vi.mocked(api.listEntities).mockResolvedValue([]);
    localStorage.clear();
  });

  it("renders every nav item as a link to the right route", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
    expect(screen.getByRole("link", { name: "Documents" })).toHaveAttribute("href", "/documents");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveAttribute("href", "/cases");
    expect(screen.getByRole("link", { name: "Vehicles" })).toHaveAttribute("href", "/vehicles");
  });

  it("marks the item matching the current route as active", () => {
    renderAt("/cases");
    expect(screen.getByRole("link", { name: "Cases" })).toHaveClass("text-accent");
    expect(screen.getByRole("link", { name: "Dashboard" })).not.toHaveClass("text-accent");
  });

  it("renders a sliding pill element behind the nav list", () => {
    renderAt("/");
    expect(document.querySelector("[data-testid=\"nav-pill\"]")).toBeInTheDocument();
  });

  it("renders an icon inside every nav link", () => {
    renderAt("/");
    expect(screen.getByRole("link", { name: "Dashboard" }).querySelector("svg")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cases" }).querySelector("svg")).toBeInTheDocument();
  });

  it("renders the brand mark", () => {
    renderAt("/");
    expect(screen.getByRole("img", { name: "CollaBrains" })).toBeInTheDocument();
  });

  it("renders the AlertsBell", async () => {
    renderAt("/");
    expect(await screen.findByLabelText("Alerts")).toBeInTheDocument();
  });

  it("opens the command palette when the search button is clicked", () => {
    renderAt("/");
    fireEvent.click(screen.getByLabelText("Search"));
    expect(screen.getByTestId("overlay-probe")).toHaveTextContent("palette");
  });

  it("does not render a mobile backdrop when closed", () => {
    renderAt("/");
    expect(screen.queryByTestId("sidebar-backdrop")).not.toBeInTheDocument();
  });

  it("renders a mobile backdrop and slides the drawer in when open", () => {
    renderAt("/", { mobileOpen: true });
    expect(screen.getByTestId("sidebar-backdrop")).toBeInTheDocument();
    expect(document.querySelector("aside")).toHaveClass("translate-x-0");
  });

  it("calls onCloseMobile when the backdrop is clicked", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.click(screen.getByTestId("sidebar-backdrop"));
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  it("calls onCloseMobile when a nav link is clicked", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.click(screen.getByRole("link", { name: "Cases" }));
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  it("calls onCloseMobile on Escape when open", () => {
    const onCloseMobile = vi.fn();
    renderAt("/", { mobileOpen: true, onCloseMobile });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onCloseMobile).toHaveBeenCalledOnce();
  });

  describe("collapse", () => {
    it("defaults to expanded", () => {
      renderAt("/");
      expect(document.querySelector("aside")).toHaveClass("md:w-56");
      expect(screen.getByRole("button", { name: "Collapse sidebar" })).toBeInTheDocument();
    });

    it("collapses and persists the preference when the toggle is clicked", () => {
      renderAt("/");
      fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
      expect(document.querySelector("aside")).toHaveClass("md:w-16");
      expect(localStorage.getItem("collabrains_sidebar_collapsed")).toBe("true");
      expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeInTheDocument();
    });

    it("restores a persisted collapsed state on mount", () => {
      localStorage.setItem("collabrains_sidebar_collapsed", "true");
      renderAt("/");
      expect(document.querySelector("aside")).toHaveClass("md:w-16");
    });

    it("keeps nav labels in the accessible tree (visually-hidden at desktop widths) when collapsed", () => {
      localStorage.setItem("collabrains_sidebar_collapsed", "true");
      renderAt("/");
      const dashboardLink = screen.getByRole("link", { name: "Dashboard" });
      expect(dashboardLink.querySelector("span")).toHaveClass("md:sr-only");
    });
  });

  describe("language switching", () => {
    afterEach(() => {
      i18n.changeLanguage("en");
    });

    it("renders nav labels in Dutch when the language is switched to nl", async () => {
      await i18n.changeLanguage("nl");
      renderAt("/");
      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("link", { name: "Zaken" })).toHaveAttribute("href", "/cases");
    });

    it("renders nav labels in German when the language is switched to de", async () => {
      await i18n.changeLanguage("de");
      renderAt("/");
      expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/");
      expect(screen.getByRole("link", { name: "Fälle" })).toHaveAttribute("href", "/cases");
    });
  });
});
```

- [ ] **Step 2: Run tests to verify the new/changed ones fail**

Run: `cd apps/web && pnpm exec vitest run src/components/Sidebar.test.tsx`
Expected: the pre-existing tests still pass; the new "renders an icon...",
"renders the brand mark", and all `describe("collapse", ...)` tests fail
(no icons/brand mark/toggle exist yet).

- [ ] **Step 3: Add the i18n keys**

In `apps/web/src/locales/en.json`, inside the `"common"` object (after
`"signOut": "Sign out",`):

```json
    "expandSidebar": "Expand sidebar",
    "collapseSidebar": "Collapse sidebar",
```

In `apps/web/src/locales/nl.json`, same position:

```json
    "expandSidebar": "Zijbalk uitklappen",
    "collapseSidebar": "Zijbalk inklappen",
```

In `apps/web/src/locales/de.json`, same position:

```json
    "expandSidebar": "Seitenleiste erweitern",
    "collapseSidebar": "Seitenleiste einklappen",
```

- [ ] **Step 4: Rewrite `Sidebar.tsx`**

Replace the contents of `apps/web/src/components/Sidebar.tsx`:

```tsx
import { useEffect, useRef, useState } from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useAuth } from "../lib/auth";
import { useDarkMode } from "../hooks/useDarkMode";
import { useEscapeToClose } from "../hooks/useEscapeToClose";
import { useSidebarCollapsed } from "../hooks/useSidebarCollapsed";
import { useCommandCenterState } from "../lib/commandCenter";
import { Button } from "./ui/Button";
import { Tooltip } from "./ui/Tooltip";
import { AlertsBell } from "./AlertsBell";
import { BrandMark } from "./BrandMark";
import { navItemsForRole } from "../lib/navigation";

export default function Sidebar({
  mobileOpen = false,
  onCloseMobile = () => {},
}: {
  mobileOpen?: boolean;
  onCloseMobile?: () => void;
}) {
  const { user, logout } = useAuth();
  const { isDark, toggle } = useDarkMode();
  const { collapsed, toggle: toggleCollapsed } = useSidebarCollapsed();
  const { openPalette } = useCommandCenterState();
  const { t } = useTranslation();
  const location = useLocation();
  const itemRefs = useRef<Record<string, HTMLAnchorElement | null>>({});
  const [pillStyle, setPillStyle] = useState<{ top: number; height: number }>({ top: 0, height: 0 });
  const navItems = navItemsForRole(user?.role);

  useEscapeToClose(mobileOpen, onCloseMobile);

  useEffect(() => {
    const activeItem = navItems.find((item) => (item.to === "/" ? location.pathname === "/" : location.pathname.startsWith(item.to)));
    const el = activeItem ? itemRefs.current[activeItem.to] : null;
    if (el) {
      setPillStyle({ top: el.offsetTop, height: el.offsetHeight });
    }
  }, [location.pathname, navItems, collapsed]);

  return (
    <>
      {mobileOpen && (
        <div
          data-testid="sidebar-backdrop"
          className="fixed inset-0 z-[70] bg-[#0D0C1A]/35 backdrop-blur-sm md:hidden"
          onClick={onCloseMobile}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-[71] flex w-56 shrink-0 flex-col justify-between border-r border-edge bg-sidebar-surface px-4 py-6 transition-transform duration-base ease-spring md:static md:z-auto md:h-screen md:translate-x-0 ${
          mobileOpen ? "translate-x-0" : "-translate-x-full"
        } ${collapsed ? "md:w-16" : "md:w-56"}`}
      >
        <div className="flex flex-col gap-6">
          <div className={`flex items-center justify-between ${collapsed ? "md:flex-col md:justify-center md:gap-3" : ""}`}>
            <div className={`flex items-center gap-2 overflow-hidden ${collapsed ? "md:justify-center" : ""}`}>
              <BrandMark size={28} />
              <span className={`whitespace-nowrap text-lg font-semibold text-ink ${collapsed ? "md:hidden" : ""}`}>CollaBrains</span>
            </div>
            <div className={`flex items-center gap-1 ${collapsed ? "md:flex-col md:gap-2" : ""}`}>
              <Tooltip label={t("common.search")} className={collapsed ? "md:hidden" : ""}>
                <button
                  type="button"
                  aria-label={t("common.search")}
                  onClick={openPalette}
                  className="flex h-8 w-8 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink"
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
                aria-label={collapsed ? t("common.expandSidebar") : t("common.collapseSidebar")}
                onClick={toggleCollapsed}
                className="hidden h-8 w-8 shrink-0 items-center justify-center rounded-lg text-ink-2 transition-colors duration-fast hover:bg-hover hover:text-ink md:flex"
              >
                {collapsed ? (
                  <ChevronRight className="h-[18px] w-[18px]" aria-hidden="true" />
                ) : (
                  <ChevronLeft className="h-[18px] w-[18px]" aria-hidden="true" />
                )}
              </button>
            </div>
          </div>
          <nav className="relative flex flex-col gap-1 text-sm">
            <span
              data-testid="nav-pill"
              className="absolute left-0 right-0 z-0 rounded-lg bg-accent-soft transition-all duration-base ease-spring"
              style={{ top: pillStyle.top, height: pillStyle.height }}
            />
            {navItems.map((item) => {
              const Icon = item.icon;
              const label = t(item.labelKey);
              const link = (
                <NavLink
                  key={item.to}
                  ref={(el) => {
                    itemRefs.current[item.to] = el;
                  }}
                  to={item.to}
                  end={item.to === "/"}
                  onClick={onCloseMobile}
                  className={({ isActive }) =>
                    `relative z-10 flex items-center gap-3 rounded-lg px-3 py-2 transition-colors duration-fast ${
                      isActive ? "font-semibold text-accent" : "text-ink-2 hover:text-ink"
                    }`
                  }
                >
                  <Icon className="h-[18px] w-[18px] shrink-0" aria-hidden="true" />
                  <span className={collapsed ? "md:sr-only" : ""}>{label}</span>
                </NavLink>
              );
              return collapsed ? (
                <Tooltip key={item.to} label={label} className="md:w-full">
                  {link}
                </Tooltip>
              ) : (
                link
              );
            })}
          </nav>
        </div>
        {user && (
          <div className="flex flex-col gap-2 border-t border-edge pt-4 text-sm">
            <span className={collapsed ? "md:sr-only" : ""}>{user.display_name}</span>
            <button onClick={logout} className={`text-left text-ink-2 hover:text-ink ${collapsed ? "md:sr-only" : ""}`}>
              {t("common.signOut")}
            </button>
            <Button variant="ghost" size="sm" onClick={toggle} className={`justify-start ${collapsed ? "md:sr-only" : ""}`}>
              {isDark ? t("common.lightMode") : t("common.darkMode")}
            </Button>
          </div>
        )}
      </aside>
    </>
  );
}
```

Note `key={item.to}` is set on the `NavLink` itself in both branches (not
moved to the `Tooltip` wrapper) — this keeps the non-collapsed path byte-for-
byte identical in structure to the original file (`link` is returned bare,
no wrapper element, so the existing flex-stretch/full-row-width behavior of
nav items is untouched). React tolerates (and ignores) a `key` prop on an
element that isn't the outermost node `.map()` returns, so having it on
`NavLink` even in the `Tooltip`-wrapped collapsed branch is harmless — no
warning, no behavior change, and it means only one place sets the key
instead of two.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd apps/web && pnpm exec vitest run src/components/Sidebar.test.tsx`
Expected: PASS (all tests, including the new collapse/icon/brand-mark ones).

- [ ] **Step 6: Run the full frontend suite and a production build as a regression check**

Run: `cd apps/web && pnpm exec vitest run && pnpm exec vite build`
Expected: all tests pass app-wide; build succeeds. (Not `tsc -b` — see
Task 1's note on its pre-existing, unrelated 106 errors.)

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/components/Sidebar.tsx apps/web/src/components/Sidebar.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(sidebar): collapsible desktop rail with icons and brand mark"
```

---

### Task 7: Final verification pass

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `cd apps/web && pnpm exec vitest run`
Expected: 100% pass, no regressions from any of Tasks 1-6.

- [ ] **Step 2: Lint**

Run: `cd apps/web && pnpm exec eslint .`
Expected: clean. (Not `tsc -b` — pre-existing, unrelated failure documented
in Task 1; `vite build` in Step 3 is this project's actual type/build gate.)

- [ ] **Step 3: Production build smoke test**

Run: `cd apps/web && pnpm exec vite build`
Expected: build succeeds (catches any Tailwind/PostCSS config mistake from
Task 1 that `vitest` alone wouldn't, e.g. a malformed `tailwind.config.js`).

- [ ] **Step 4: Live-browser check**

This project's own history (see `docs/superpowers/specs/2026-07-22-design-system-sidebar-layout-design.md`
"Context"/"Testing" sections) has repeatedly found real bugs that typecheck +
unit tests missed — do a real check before calling this done:
- Run the local dev server (`pnpm dev`) and open it in a browser.
- Check the sidebar in both expanded and collapsed states, in both light and
  dark mode (toggle both).
- Confirm the active-item pill still lands correctly after toggling collapse
  (it's recomputed from live DOM measurements — verify it, don't assume).
- Confirm the collapsed rail's header row (brand mark, alerts, collapse
  toggle) doesn't look cramped or overlapping at `w-16`/64px — if it does,
  this is expected to need a small Tailwind spacing/wrapping nudge; adjust
  the utility classes in `Sidebar.tsx` as needed, without changing the
  collapse state mechanic (`useSidebarCollapsed`) itself.
- Confirm the mobile drawer (resize the viewport below `md:`) still opens,
  closes, and looks unchanged — no collapse toggle should appear there.
- Confirm each nav item's clickable row still spans the sidebar's full width
  (not just the icon+label's own content width) in both expanded and
  collapsed states — a visual sanity check on the `key`/wrapper structure in
  Task 6.

**Do not push to `origin/main` or deploy to the live server as part of this
task.** Once everything above is verified, tell the user it's ready and ask
whether to push/deploy — that's a separate explicit step per this plan's
Global Constraints.

---

## Post-plan (not part of this plan, tracked here so it isn't lost)

- Sub-project 2: Dashboard redesign
- Sub-project 3: Document experience redesign
- Sub-project 4: AI Chat experience redesign
- Sub-project 5: Login redesign
- Separate track: Landing page + onboarding flow (has its own open
  architecture question — see the spec's Non-goals section)
