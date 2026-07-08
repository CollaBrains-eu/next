# Phase 20a: Violet Design System Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the violet design language's tokens, dark mode, and core reusable primitive components (Button, Badge, Tooltip, Toast, Modal, form fields) into the real `apps/web` codebase, verified with real component tests — with no page-level rollout yet.

**Architecture:** CSS custom properties (light + dark values) drive a Tailwind theme extension, so components use ordinary semantic Tailwind classes (`bg-surface`, `text-ink-2`, `border-edge`) instead of ad-hoc slate-palette utilities or CSS-in-JS. Dark mode is a `.dark` class on `<html>`, toggled by a small hook and persisted to `localStorage` — this is the standard Tailwind `darkMode: 'class'` mechanism, not the prototype's `data-mode` attribute, because integrating with Tailwind's own convention is simpler than fighting it. No animation library is added: the validated prototype proved every motion effect (ripple, tilt, spring easing, staggered entrance) works with plain CSS transitions/keyframes and small vanilla event handlers, which keeps this consistent with the rest of the codebase's dependency-minimalism (no Celery, no Elasticsearch, no graph library — added only when proven necessary).

**Tech Stack:** React 18, TypeScript, Vite 6, Tailwind CSS 3.4, Vitest 3 + `@testing-library/react` (added this plan), pnpm workspace.

## Scope

This plan covers **only** the foundation: design tokens, dark mode, and seven standalone primitive components, plus migrating the existing `Card.tsx` as proof the tokens work end-to-end. It deliberately does **not** cover:
- Layout/chrome components (sliding nav-pill sidebar, detail drawer, command palette, shortcuts sheet, global loading bar, data table + pagination, empty-state redesign) — planned separately as Phase 20b.
- The interaction patterns (bulk selection, filter chips, inline editing, split view) and applying any of this to the 9 real pages (Documents, Cases, Vehicles, Entities, Chat, Legal, Tasks, Settings, Assistant) — planned separately as Phase 20c.

This mirrors the same "split multi-capability work" discipline already used throughout this repo (Phase 16→17a-17d, Phase 1a/1b, etc.) and matches the spec's own scope boundary (`docs/superpowers/specs/2026-07-08-violet-design-language-design.md`).

## Global Constraints

- Colors, exactly as specified (light / dark), from the spec's Decision section:
  - `--bg: #F0EFFF` / dark `#0D0C1A`
  - `--bg-sidebar: #ffffff` / dark `#13112A`
  - `--bg-card: #ffffff` / dark `#13112A`
  - `--text: #1E1B4B` / dark `rgba(255,255,255,.90)`
  - `--text-2: #6B7280` / dark `rgba(200,195,255,.65)`
  - `--text-3: #9CA3AF` / dark `rgba(200,195,255,.38)`
  - `--border: #E8E6FF` / dark `rgba(108,99,255,.18)`
  - `--accent: #6C63FF` / dark `#8B82FF`
  - `--accent-hover: #5A52E8` / dark `#9D95FF`
  - `--accent-bg: #EEECFF` / dark `rgba(108,99,255,.18)`
  - `--success: #16A34A` / dark `#4ADE80`, `--success-bg: rgba(34,197,94,.10)` / dark `rgba(34,197,94,.15)`
  - `--warning: #D97706` / dark `#FBBF24`, `--warning-bg: rgba(245,158,11,.10)` / dark `rgba(245,158,11,.15)`
  - `--danger: #EF4444` / dark `#F87171`, `--danger-bg: rgba(239,68,68,.10)` / dark `rgba(239,68,68,.15)`
- Typography: Inter (sans/UI), IBM Plex Mono (mono/data). Base body 15px/1.6.
- Tailwind's **default** spacing scale (4px base) already satisfies the spec's spacing requirement — no config changes needed there.
- Tailwind's **default** border-radius scale already approximates the spec's radius tokens (`rounded-lg`≈8px, `rounded-xl`≈12px, `rounded-2xl`≈16px) — no config changes needed there either.
- Motion: `ease-out` = `cubic-bezier(.16,1,.3,1)` for entrances, `spring` = `cubic-bezier(.34,1.56,.64,1)` for interactive elements, durations 150ms (fast) / 260ms (base) / 550ms (slow).
- All motion must respect `prefers-reduced-motion` — any JS-driven effect (not just CSS transitions) must check `window.matchMedia('(prefers-reduced-motion: reduce)').matches` and no-op if true.
- Package manager is **pnpm**, not npm/yarn — every install command below uses `pnpm`.

## Environment Setup (read before Task 1)

There is no local clone of this repo and no GitHub credentials configured on the planning machine. The only writable checkout is on the production server, and every task below must actually be executed there:

```bash
ssh root@195.90.216.230   # apps/web lives at /opt/collabrains/apps/web
cd /opt/collabrains
git checkout main && git pull
git checkout -b phase-20a-design-system-foundation
cd apps/web
```

Run every `pnpm` command in this plan from `/opt/collabrains/apps/web` on that server. After the final task, push the branch and open a PR exactly as was done for the spec (`git push -u origin phase-20a-design-system-foundation`, then `gh pr create`) — do not merge directly to `main`.

---

### Task 1: Add component-testing infrastructure

**Files:**
- Modify: `apps/web/package.json`
- Create: `apps/web/vitest.setup.ts`
- Modify: `apps/web/vitest.config.ts`

**Interfaces:**
- Produces: `render`, `screen`, `fireEvent` from `@testing-library/react` available to all later test files; `expect(...).toBeInTheDocument()` and other jest-dom matchers available globally.

- [ ] **Step 1: Install the testing libraries**

Run from `/opt/collabrains/apps/web`:
```bash
pnpm add -D @testing-library/react@^16.0.1 @testing-library/jest-dom@^6.6.3 @testing-library/user-event@^14.5.2
```
Expected: `package.json` devDependencies gain these three entries; `pnpm-lock.yaml` at the repo root updates.

- [ ] **Step 2: Create the Vitest setup file**

Create `apps/web/vitest.setup.ts`:
```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Wire the setup file into Vitest config**

Modify `apps/web/vitest.config.ts` — replace its full contents:
```typescript
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: false,
    setupFiles: ["./vitest.setup.ts"],
  },
});
```

- [ ] **Step 4: Write a smoke test to verify the setup works**

Create `apps/web/src/components/ui/__smoke__.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

describe("testing infra smoke test", () => {
  it("renders and matches jest-dom matchers", () => {
    render(<div>hello world</div>);
    expect(screen.getByText("hello world")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pnpm test`
Expected: `1 passed` including the smoke test. If it fails with a matcher error, re-check Step 3's `setupFiles` path.

- [ ] **Step 6: Delete the smoke test and commit**

The smoke test's only job was proving the infra works — remove it now that Task 4 onward will exercise real components.
```bash
rm src/components/ui/__smoke__.test.tsx
git add package.json ../../pnpm-lock.yaml vitest.setup.ts vitest.config.ts
git commit -m "test: add @testing-library/react for component testing"
```

---

### Task 2: Design tokens (CSS custom properties + Tailwind theme)

**Files:**
- Create: `apps/web/src/styles/tokens.css`
- Modify: `apps/web/src/index.css`
- Modify: `apps/web/tailwind.config.js`

**Interfaces:**
- Produces: Tailwind utility classes `bg-page`, `bg-surface`, `bg-sidebar-surface`, `text-ink`, `text-ink-2`, `text-ink-3`, `border-edge`, `bg-accent`, `text-accent`, `bg-accent-hover`, `bg-accent-soft`, `text-success`, `bg-success-soft`, `text-warning`, `bg-warning-soft`, `text-danger`, `bg-danger-soft`, `shadow-raised`, `shadow-overlay`, `shadow-modal`, `font-sans` (Inter), `font-mono` (IBM Plex Mono), `ease-out-token`, `ease-spring`, `duration-fast`, `duration-base`, `duration-slow` — all later tasks use these instead of raw Tailwind colors.

- [ ] **Step 1: Create the tokens file**

Create `apps/web/src/styles/tokens.css`:
```css
:root {
  --bg: #F0EFFF;
  --bg-sidebar: #ffffff;
  --bg-card: #ffffff;
  --text: #1E1B4B;
  --text-2: #6B7280;
  --text-3: #9CA3AF;
  --border: #E8E6FF;
  --hover: rgba(108, 99, 255, 0.06);
  --active: rgba(108, 99, 255, 0.12);
  --accent: #6C63FF;
  --accent-hover: #5A52E8;
  --accent-bg: #EEECFF;
  --success: #16A34A;
  --success-bg: rgba(34, 197, 94, 0.10);
  --warning: #D97706;
  --warning-bg: rgba(245, 158, 11, 0.10);
  --danger: #EF4444;
  --danger-bg: rgba(239, 68, 68, 0.10);
  --shadow-raised: 0 2px 16px rgba(108, 99, 255, 0.10), 0 1px 4px rgba(0, 0, 0, 0.04);
  --shadow-overlay: 0 20px 40px rgba(108, 99, 255, 0.22), 0 4px 12px rgba(0, 0, 0, 0.08);
  --shadow-modal: 0 30px 60px rgba(108, 99, 255, 0.30);
}

.dark {
  --bg: #0D0C1A;
  --bg-sidebar: #13112A;
  --bg-card: #13112A;
  --text: rgba(255, 255, 255, 0.90);
  --text-2: rgba(200, 195, 255, 0.65);
  --text-3: rgba(200, 195, 255, 0.38);
  --border: rgba(108, 99, 255, 0.18);
  --hover: rgba(108, 99, 255, 0.10);
  --active: rgba(108, 99, 255, 0.20);
  --accent: #8B82FF;
  --accent-hover: #9D95FF;
  --accent-bg: rgba(108, 99, 255, 0.18);
  --success: #4ADE80;
  --success-bg: rgba(34, 197, 94, 0.15);
  --warning: #FBBF24;
  --warning-bg: rgba(245, 158, 11, 0.15);
  --danger: #F87171;
  --danger-bg: rgba(239, 68, 68, 0.15);
  --shadow-raised: 0 2px 16px rgba(0, 0, 0, 0.40);
  --shadow-overlay: 0 20px 40px rgba(0, 0, 0, 0.55);
  --shadow-modal: 0 30px 60px rgba(0, 0, 0, 0.60);
}
```

- [ ] **Step 2: Import the tokens and set base styles in index.css**

Modify `apps/web/src/index.css` — replace its full contents:
```css
@import url("https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap");
@import "./styles/tokens.css";

@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  font-family: "Inter", system-ui, -apple-system, sans-serif;
  font-size: 15px;
  line-height: 1.6;
  background-color: var(--bg);
  color: var(--text);
  -webkit-font-smoothing: antialiased;
}

:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: 4px;
}
```

- [ ] **Step 3: Extend the Tailwind theme to reference the tokens**

Modify `apps/web/tailwind.config.js` — replace its full contents:
```js
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "var(--bg)",
        "sidebar-surface": "var(--bg-sidebar)",
        surface: "var(--bg-card)",
        ink: "var(--text)",
        "ink-2": "var(--text-2)",
        "ink-3": "var(--text-3)",
        edge: "var(--border)",
        hover: "var(--hover)",
        active: "var(--active)",
        accent: "var(--accent)",
        "accent-hover": "var(--accent-hover)",
        "accent-soft": "var(--accent-bg)",
        success: "var(--success)",
        "success-soft": "var(--success-bg)",
        warning: "var(--warning)",
        "warning-soft": "var(--warning-bg)",
        danger: "var(--danger)",
        "danger-soft": "var(--danger-bg)",
      },
      boxShadow: {
        raised: "var(--shadow-raised)",
        overlay: "var(--shadow-overlay)",
        modal: "var(--shadow-modal)",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "-apple-system", "sans-serif"],
        mono: ["IBM Plex Mono", "SF Mono", "ui-monospace", "monospace"],
      },
      transitionTimingFunction: {
        "out-token": "cubic-bezier(.16,1,.3,1)",
        spring: "cubic-bezier(.34,1.56,.64,1)",
      },
      transitionDuration: {
        fast: "150ms",
        base: "260ms",
        slow: "550ms",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 4: Verify the build picks up the new config**

Run: `pnpm build`
Expected: build succeeds with no Tailwind or TypeScript errors. If Tailwind reports an unknown token, re-check the `colors`/`boxShadow` keys above for typos.

- [ ] **Step 5: Commit**

```bash
git add src/styles/tokens.css src/index.css tailwind.config.js
git commit -m "feat: add violet design system tokens (light+dark) and Tailwind theme extension"
```

---

### Task 3: `useDarkMode` hook

**Files:**
- Create: `apps/web/src/hooks/useDarkMode.ts`
- Test: `apps/web/src/hooks/useDarkMode.test.ts`

**Interfaces:**
- Produces: `useDarkMode(): { isDark: boolean; toggle: () => void }` — reads/writes `localStorage["cb-theme"]` (`"light" | "dark"`), applies/removes the `.dark` class on `document.documentElement`. Later tasks (Task 11) call this from a UI toggle.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/hooks/useDarkMode.test.ts`:
```typescript
import { describe, expect, it, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useDarkMode } from "./useDarkMode";

describe("useDarkMode", () => {
  beforeEach(() => {
    localStorage.clear();
    document.documentElement.classList.remove("dark");
  });

  it("defaults to light mode with no stored preference", () => {
    const { result } = renderHook(() => useDarkMode());
    expect(result.current.isDark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
  });

  it("toggle switches to dark, applies the class, and persists it", () => {
    const { result } = renderHook(() => useDarkMode());
    act(() => result.current.toggle());
    expect(result.current.isDark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(localStorage.getItem("cb-theme")).toBe("dark");
  });

  it("toggle twice returns to light and removes the class", () => {
    const { result } = renderHook(() => useDarkMode());
    act(() => result.current.toggle());
    act(() => result.current.toggle());
    expect(result.current.isDark).toBe(false);
    expect(document.documentElement.classList.contains("dark")).toBe(false);
    expect(localStorage.getItem("cb-theme")).toBe("light");
  });

  it("reads an existing stored preference on mount", () => {
    localStorage.setItem("cb-theme", "dark");
    const { result } = renderHook(() => useDarkMode());
    expect(result.current.isDark).toBe(true);
    expect(document.documentElement.classList.contains("dark")).toBe(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test useDarkMode`
Expected: FAIL — `Cannot find module './useDarkMode'`.

- [ ] **Step 3: Implement the hook**

Create `apps/web/src/hooks/useDarkMode.ts`:
```typescript
import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "cb-theme";

function applyClass(isDark: boolean) {
  document.documentElement.classList.toggle("dark", isDark);
}

export function useDarkMode(): { isDark: boolean; toggle: () => void } {
  const [isDark, setIsDark] = useState(() => localStorage.getItem(STORAGE_KEY) === "dark");

  useEffect(() => {
    applyClass(isDark);
  }, [isDark]);

  const toggle = useCallback(() => {
    setIsDark((prev) => {
      const next = !prev;
      localStorage.setItem(STORAGE_KEY, next ? "dark" : "light");
      return next;
    });
  }, []);

  return { isDark, toggle };
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test useDarkMode`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/hooks/useDarkMode.ts src/hooks/useDarkMode.test.ts
git commit -m "feat: add useDarkMode hook"
```

---

### Task 4: `Button` component

**Files:**
- Create: `apps/web/src/components/ui/Button.tsx`
- Test: `apps/web/src/components/ui/Button.test.tsx`

**Interfaces:**
- Produces: `<Button variant?: "primary"|"secondary"|"ghost"|"danger" size?: "sm"|"md"|"lg" ...restButtonProps />` (default variant `"primary"`, default size `"md"`) — a drop-in replacement for the raw `<button className="...">` used today in `UploadDialog.tsx` and elsewhere. Forwards all standard `<button>` props (`onClick`, `disabled`, `type`, etc.) via `...rest`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/Button.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Button } from "./Button";

describe("Button", () => {
  it("renders its children", () => {
    render(<Button>Click me</Button>);
    expect(screen.getByRole("button", { name: "Click me" })).toBeInTheDocument();
  });

  it("applies primary variant classes by default", () => {
    render(<Button>Primary</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-accent", "text-white");
  });

  it("applies danger variant classes when requested", () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button")).toHaveClass("bg-danger", "text-white");
  });

  it("applies size classes", () => {
    render(<Button size="sm">Small</Button>);
    expect(screen.getByRole("button")).toHaveClass("text-xs");
  });

  it("fires onClick", () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Go</Button>);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("respects the disabled prop", () => {
    const onClick = vi.fn();
    render(<Button disabled onClick={onClick}>Go</Button>);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).not.toHaveBeenCalled();
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("spawns a ripple span on click", () => {
    render(<Button>Ripple</Button>);
    const button = screen.getByRole("button");
    fireEvent.click(button, { clientX: 10, clientY: 10 });
    expect(button.querySelector("span.pointer-events-none")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Button`
Expected: FAIL — `Cannot find module './Button'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/Button.tsx`:
```tsx
import { useState, type ButtonHTMLAttributes, type MouseEvent } from "react";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

const VARIANT_CLASSES: Record<Variant, string> = {
  primary: "bg-accent text-white hover:bg-accent-hover",
  secondary: "bg-accent-soft text-accent hover:bg-hover",
  ghost: "bg-transparent text-ink-2 hover:bg-hover hover:text-ink",
  danger: "bg-danger text-white hover:opacity-90",
};

const SIZE_CLASSES: Record<Size, string> = {
  sm: "px-3 py-1.5 text-xs",
  md: "px-4 py-2 text-sm",
  lg: "px-4 py-3 text-sm",
};

interface RippleSpan {
  id: number;
  x: number;
  y: number;
  size: number;
}

export function Button({
  variant = "primary",
  size = "md",
  className = "",
  onClick,
  children,
  ...rest
}: {
  variant?: Variant;
  size?: Size;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const [ripples, setRipples] = useState<RippleSpan[]>([]);

  function handleClick(event: MouseEvent<HTMLButtonElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    const size = Math.max(rect.width, rect.height);
    const id = Date.now();
    setRipples((prev) => [
      ...prev,
      { id, x: event.clientX - rect.left - size / 2, y: event.clientY - rect.top - size / 2, size },
    ]);
    setTimeout(() => setRipples((prev) => prev.filter((r) => r.id !== id)), 600);
    onClick?.(event);
  }

  return (
    <button
      className={`relative inline-flex items-center justify-center gap-2 overflow-hidden rounded-xl font-semibold transition-colors duration-base ease-out-token disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT_CLASSES[variant]} ${SIZE_CLASSES[size]} ${className}`}
      onClick={handleClick}
      {...rest}
    >
      {children}
      {ripples.map((r) => (
        <span
          key={r.id}
          className="pointer-events-none absolute animate-[ripple_0.6s_ease-out-token] rounded-full bg-white/40"
          style={{ left: r.x, top: r.y, width: r.size, height: r.size }}
        />
      ))}
    </button>
  );
}
```

- [ ] **Step 4: Add the ripple keyframe to Tailwind config**

Modify `apps/web/tailwind.config.js` — add a `keyframes`/`animation` block inside `theme.extend`, alongside `transitionDuration` from Task 2:
```js
      keyframes: {
        ripple: {
          to: { transform: "scale(4)", opacity: "0" },
        },
      },
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `pnpm test Button`
Expected: `6 passed`.

- [ ] **Step 6: Commit**

```bash
git add src/components/ui/Button.tsx src/components/ui/Button.test.tsx tailwind.config.js
git commit -m "feat: add Button component (4 variants, 3 sizes, ripple feedback)"
```

---

### Task 5: `Badge` component

**Files:**
- Create: `apps/web/src/components/ui/Badge.tsx`
- Test: `apps/web/src/components/ui/Badge.test.tsx`

**Interfaces:**
- Produces: `<Badge variant?: "default"|"success"|"warning"|"danger" pulsing?: boolean ready?: boolean>{children}</Badge>` (default variant `"default"`). `pulsing` renders an animated dot (for "processing"-style states); `ready` renders a checkmark instead of the dot (for the processing→ready morph used later when this is wired into document/task status displays in Phase 20c).

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/Badge.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Badge } from "./Badge";

describe("Badge", () => {
  it("renders its children", () => {
    render(<Badge>Ready</Badge>);
    expect(screen.getByText("Ready")).toBeInTheDocument();
  });

  it("applies default variant classes", () => {
    render(<Badge>Default</Badge>);
    expect(screen.getByText("Default").closest("span")).toHaveClass("bg-accent-soft", "text-accent");
  });

  it("applies danger variant classes", () => {
    render(<Badge variant="danger">Failed</Badge>);
    expect(screen.getByText("Failed").closest("span")).toHaveClass("bg-danger-soft", "text-danger");
  });

  it("renders a pulsing dot when pulsing is true", () => {
    render(<Badge pulsing>Processing</Badge>);
    expect(document.querySelector(".animate-pulse")).toBeInTheDocument();
  });

  it("renders a checkmark svg instead of a dot when ready is true", () => {
    render(<Badge ready>Ready</Badge>);
    expect(document.querySelector("svg")).toBeInTheDocument();
    expect(document.querySelector(".animate-pulse")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Badge`
Expected: FAIL — `Cannot find module './Badge'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/Badge.tsx`:
```tsx
import type { HTMLAttributes } from "react";

type Variant = "default" | "success" | "warning" | "danger";

const VARIANT_CLASSES: Record<Variant, string> = {
  default: "bg-accent-soft text-accent",
  success: "bg-success-soft text-success",
  warning: "bg-warning-soft text-warning",
  danger: "bg-danger-soft text-danger",
};

export function Badge({
  variant = "default",
  pulsing = false,
  ready = false,
  className = "",
  children,
  ...rest
}: {
  variant?: Variant;
  pulsing?: boolean;
  ready?: boolean;
} & HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-semibold ${VARIANT_CLASSES[variant]} ${className}`}
      {...rest}
    >
      {ready ? (
        <svg width="10" height="10" viewBox="0 0 16 16" fill="none">
          <path d="M3 8l3.5 3.5L13 5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      ) : (
        <span className={`h-1.5 w-1.5 rounded-full bg-current ${pulsing ? "animate-pulse" : ""}`} />
      )}
      {children}
    </span>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test Badge`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/Badge.tsx src/components/ui/Badge.test.tsx
git commit -m "feat: add Badge component (4 variants, pulsing/ready states)"
```

---

### Task 6: `Tooltip` component

**Files:**
- Create: `apps/web/src/components/ui/Tooltip.tsx`
- Test: `apps/web/src/components/ui/Tooltip.test.tsx`

**Interfaces:**
- Produces: `<Tooltip label={string}>{children}</Tooltip>` — wraps any single child element/component; shows `label` in a small bubble above the child on hover, via pure CSS (`group`/`group-hover`), no JS state needed.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/Tooltip.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tooltip } from "./Tooltip";

describe("Tooltip", () => {
  it("renders the child content", () => {
    render(
      <Tooltip label="Owner-only action">
        <button>Hover me</button>
      </Tooltip>
    );
    expect(screen.getByRole("button", { name: "Hover me" })).toBeInTheDocument();
  });

  it("renders the label text in the DOM (visibility is CSS-only, not asserted here)", () => {
    render(
      <Tooltip label="Owner-only action">
        <button>Hover me</button>
      </Tooltip>
    );
    expect(screen.getByText("Owner-only action")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Tooltip`
Expected: FAIL — `Cannot find module './Tooltip'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/Tooltip.tsx`:
```tsx
import type { ReactNode } from "react";

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      {children}
      <span className="pointer-events-none absolute bottom-full left-1/2 mb-2 -translate-x-1/2 translate-y-1 whitespace-nowrap rounded-lg bg-ink px-2.5 py-1 text-[11px] text-surface opacity-0 transition-all duration-fast ease-out-token group-hover:translate-y-0 group-hover:opacity-100">
        {label}
      </span>
    </span>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test Tooltip`
Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/Tooltip.tsx src/components/ui/Tooltip.test.tsx
git commit -m "feat: add Tooltip component"
```

---

### Task 7: Toast system (`ToastProvider` + `useToast`)

**Files:**
- Create: `apps/web/src/lib/toast.tsx`
- Test: `apps/web/src/lib/toast.test.tsx`

**Interfaces:**
- Produces: `<ToastProvider>{children}</ToastProvider>` (wrap the app once, in Task 11) and `useToast(): { showToast: (text: string, options?: { onUndo?: () => void }) => void }`. Toasts auto-dismiss after 4000ms; if `onUndo` is given, a visible "Undo" button calls it and marks the toast as resolved. This is the exact behavior validated in the prototype's `spawnToast`.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/lib/toast.test.tsx`:
```tsx
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ToastProvider, useToast } from "./toast";

function ToastTrigger({ onUndo }: { onUndo?: () => void }) {
  const { showToast } = useToast();
  return <button onClick={() => showToast("Case deleted", onUndo ? { onUndo } : undefined)}>Trigger</button>;
}

describe("toast system", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("shows a toast with the given text", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Trigger"));
    expect(screen.getByText("Case deleted")).toBeInTheDocument();
  });

  it("auto-dismisses after 4000ms", () => {
    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Trigger"));
    expect(screen.getByText("Case deleted")).toBeInTheDocument();
    vi.advanceTimersByTime(4000);
    expect(screen.queryByText("Case deleted")).not.toBeInTheDocument();
  });

  it("renders an Undo button and calls onUndo when clicked", () => {
    const onUndo = vi.fn();
    render(
      <ToastProvider>
        <ToastTrigger onUndo={onUndo} />
      </ToastProvider>
    );
    fireEvent.click(screen.getByText("Trigger"));
    fireEvent.click(screen.getByText("Undo"));
    expect(onUndo).toHaveBeenCalledOnce();
  });

  it("throws a clear error if useToast is called outside a ToastProvider", () => {
    function Orphan() {
      useToast();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow("useToast must be used within a ToastProvider");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test toast`
Expected: FAIL — `Cannot find module './toast'`.

- [ ] **Step 3: Implement the toast system**

Create `apps/web/src/lib/toast.tsx`:
```tsx
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

interface ToastItem {
  id: number;
  text: string;
  onUndo?: () => void;
}

interface ToastContextValue {
  showToast: (text: string, options?: { onUndo?: () => void }) => void;
}

const ToastContext = createContext<ToastContextValue | null>(null);

let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const showToast = useCallback((text: string, options?: { onUndo?: () => void }) => {
    const id = nextId++;
    setToasts((prev) => [...prev, { id, text, onUndo: options?.onUndo }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 4000);
  }, []);

  function handleUndo(toast: ToastItem) {
    toast.onUndo?.();
    setToasts((prev) => prev.filter((t) => t.id !== toast.id));
  }

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <div className="fixed right-4 top-4 z-[60] flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="min-w-[220px] rounded-xl border border-edge bg-surface px-4 py-3 text-sm shadow-overlay"
          >
            <span>{t.text}</span>
            {t.onUndo && (
              <button className="ml-2.5 font-bold text-accent" onClick={() => handleUndo(t)}>
                Undo
              </button>
            )}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used within a ToastProvider");
  return ctx;
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test toast`
Expected: `4 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/lib/toast.tsx src/lib/toast.test.tsx
git commit -m "feat: add ToastProvider/useToast (with undo support)"
```

---

### Task 8: `Modal` component

**Files:**
- Create: `apps/web/src/components/ui/Modal.tsx`
- Test: `apps/web/src/components/ui/Modal.test.tsx`

**Interfaces:**
- Produces: `<Modal open: boolean onClose: () => void title: string>{children}</Modal>` — renders nothing when `open` is false; when open, renders a backdrop + centered panel, closes on backdrop click and on `Escape`. Generic (used later for delete-confirmation and other dialogs in Phase 20c).

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/Modal.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("renders nothing when closed", () => {
    render(
      <Modal open={false} onClose={() => {}} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    expect(screen.queryByText("Delete case?")).not.toBeInTheDocument();
  });

  it("renders the title and children when open", () => {
    render(
      <Modal open onClose={() => {}} title="Delete case?">
        <p>This can't be undone.</p>
      </Modal>
    );
    expect(screen.getByText("Delete case?")).toBeInTheDocument();
    expect(screen.getByText("This can't be undone.")).toBeInTheDocument();
  });

  it("calls onClose when the backdrop is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    fireEvent.click(screen.getByTestId("modal-backdrop"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("calls onClose when Escape is pressed", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("does not call onClose when the panel itself is clicked", () => {
    const onClose = vi.fn();
    render(
      <Modal open onClose={onClose} title="Delete case?">
        <p>Body</p>
      </Modal>
    );
    fireEvent.click(screen.getByText("Body"));
    expect(onClose).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Modal`
Expected: FAIL — `Cannot find module './Modal'`.

- [ ] **Step 3: Implement the component**

Create `apps/web/src/components/ui/Modal.tsx`:
```tsx
import { useEffect, type ReactNode } from "react";

export function Modal({
  open,
  onClose,
  title,
  children,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <>
      <div
        data-testid="modal-backdrop"
        className="fixed inset-0 z-[70] bg-[#0D0C1A]/40 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        className="fixed left-1/2 top-1/2 z-[71] w-[min(380px,90vw)] -translate-x-1/2 -translate-y-1/2 rounded-2xl border border-edge bg-surface p-6 shadow-modal"
        onClick={(event) => event.stopPropagation()}
      >
        <h4 className="mb-2 text-base font-semibold text-ink">{title}</h4>
        {children}
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test Modal`
Expected: `5 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/Modal.tsx src/components/ui/Modal.test.tsx
git commit -m "feat: add generic Modal component"
```

---

### Task 9: Form field primitives (`TextField`, `Select`, `Checkbox`, `Switch`)

**Files:**
- Create: `apps/web/src/components/ui/form.tsx`
- Test: `apps/web/src/components/ui/form.test.tsx`

**Interfaces:**
- Produces: `<TextField label: string value: string onChange: (v: string) => void error?: string ...restInputProps />`, `<Select label: string value: string onChange: (v: string) => void options: string[] />`, `<Checkbox label: string checked: boolean onChange: (v: boolean) => void />`, `<Switch label: string checked: boolean onChange: (v: boolean) => void />`. `TextField`'s `error` prop, when set, renders red border + message below the input — this is what Task 9's tests (and later, the real New Case form in Phase 20c) rely on for validation display.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/ui/form.test.tsx`:
```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { TextField, Select, Checkbox, Switch } from "./form";

describe("TextField", () => {
  it("renders the label and current value", () => {
    render(<TextField label="Case title" value="Claim #4471" onChange={() => {}} />);
    expect(screen.getByLabelText("Case title")).toHaveValue("Claim #4471");
  });

  it("calls onChange with the new value", () => {
    const onChange = vi.fn();
    render(<TextField label="Case title" value="" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Case title"), { target: { value: "New title" } });
    expect(onChange).toHaveBeenCalledWith("New title");
  });

  it("shows an error message and error styling when error is set", () => {
    render(<TextField label="Case title" value="" onChange={() => {}} error="Case title is required" />);
    expect(screen.getByText("Case title is required")).toBeInTheDocument();
    expect(screen.getByLabelText("Case title")).toHaveClass("border-danger");
  });

  it("renders no error message when error is unset", () => {
    render(<TextField label="Case title" value="x" onChange={() => {}} />);
    expect(screen.queryByText(/required/)).not.toBeInTheDocument();
  });
});

describe("Select", () => {
  it("renders all options and the selected value", () => {
    render(<Select label="Case type" value="Legal matter" onChange={() => {}} options={["Insurance claim", "Legal matter"]} />);
    expect(screen.getByLabelText("Case type")).toHaveValue("Legal matter");
    expect(screen.getByText("Insurance claim")).toBeInTheDocument();
  });

  it("calls onChange with the new value", () => {
    const onChange = vi.fn();
    render(<Select label="Case type" value="Insurance claim" onChange={onChange} options={["Insurance claim", "Legal matter"]} />);
    fireEvent.change(screen.getByLabelText("Case type"), { target: { value: "Legal matter" } });
    expect(onChange).toHaveBeenCalledWith("Legal matter");
  });
});

describe("Checkbox", () => {
  it("reflects the checked prop and calls onChange on toggle", () => {
    const onChange = vi.fn();
    render(<Checkbox label="Notify assignee" checked={true} onChange={onChange} />);
    const checkbox = screen.getByLabelText("Notify assignee");
    expect(checkbox).toBeChecked();
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenCalledWith(false);
  });
});

describe("Switch", () => {
  it("reflects the checked prop and calls onChange on toggle", () => {
    const onChange = vi.fn();
    render(<Switch label="Auto-archive when closed" checked={false} onChange={onChange} />);
    const toggle = screen.getByLabelText("Auto-archive when closed");
    expect(toggle).not.toBeChecked();
    fireEvent.click(toggle);
    expect(onChange).toHaveBeenCalledWith(true);
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test form`
Expected: FAIL — `Cannot find module './form'`.

- [ ] **Step 3: Implement the components**

Create `apps/web/src/components/ui/form.tsx`:
```tsx
import { useId, type InputHTMLAttributes } from "react";

type BaseInputProps = Omit<InputHTMLAttributes<HTMLInputElement>, "value" | "onChange" | "type">;

export function TextField({
  label,
  value,
  onChange,
  error,
  ...rest
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
} & BaseInputProps) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-semibold text-ink-2">
        {label}
      </label>
      <input
        id={id}
        type="text"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`rounded-xl border bg-surface px-3 py-2 text-sm text-ink outline-none transition-colors duration-fast focus:border-accent focus:ring-2 focus:ring-accent-soft ${
          error ? "border-danger" : "border-edge"
        }`}
        {...rest}
      />
      {error && <span className="text-[11.5px] text-danger">{error}</span>}
    </div>
  );
}

export function Select({
  label,
  value,
  onChange,
  options,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-semibold text-ink-2">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
}

export function Checkbox({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center gap-2 text-sm text-ink">
      <input
        id={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="h-4 w-4 accent-accent"
      />
      {label}
    </label>
  );
}

export function Switch({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (checked: boolean) => void;
}) {
  const id = useId();
  return (
    <label htmlFor={id} className="flex cursor-pointer items-center gap-2.5 text-sm text-ink">
      <span className="relative inline-block h-[22px] w-[38px] flex-shrink-0">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className="peer absolute h-0 w-0 opacity-0"
        />
        <span className="absolute inset-0 rounded-full bg-edge transition-colors duration-base peer-checked:bg-accent" />
        <span className="absolute left-[3px] top-[3px] h-4 w-4 rounded-full bg-white shadow transition-transform duration-base ease-spring peer-checked:translate-x-4" />
      </span>
      {label}
    </label>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test form`
Expected: `9 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/components/ui/form.tsx src/components/ui/form.test.tsx
git commit -m "feat: add form primitives (TextField, Select, Checkbox, Switch)"
```

---

### Task 10: Migrate `Card.tsx` to the new tokens

**Files:**
- Modify: `apps/web/src/components/Card.tsx`
- Test: `apps/web/src/components/Card.test.tsx`

**Interfaces:**
- Consumes: nothing new — same public API as today (`children`, `className`).
- Produces: unchanged export signature, so every existing usage of `<Card>` across the app keeps working with zero call-site changes. This task exists to prove the token system integrates cleanly into an already-shared component before Phase 20c touches real pages.

- [ ] **Step 1: Write the failing test**

Create `apps/web/src/components/Card.test.tsx`:
```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import Card from "./Card";

describe("Card", () => {
  it("renders its children", () => {
    render(<Card>Card content</Card>);
    expect(screen.getByText("Card content")).toBeInTheDocument();
  });

  it("uses the design-system surface/edge/shadow tokens instead of the old slate classes", () => {
    render(<Card>Content</Card>);
    const card = screen.getByText("Content");
    expect(card).toHaveClass("bg-surface", "border-edge", "shadow-raised");
    expect(card.className).not.toMatch(/slate/);
  });

  it("still accepts an additional className", () => {
    render(<Card className="mt-4">Content</Card>);
    expect(screen.getByText("Content")).toHaveClass("mt-4");
  });
});
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pnpm test Card`
Expected: FAIL — current implementation has `border-slate-200 bg-white` and no `shadow-raised`, so the second assertion fails.

- [ ] **Step 3: Update the component**

Modify `apps/web/src/components/Card.tsx` — replace its full contents:
```tsx
import type { ReactNode } from "react";

export default function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div className={`rounded-2xl border border-edge bg-surface p-4 shadow-raised ${className}`}>{children}</div>
  );
}
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pnpm test Card`
Expected: `3 passed`.

- [ ] **Step 5: Run the full test suite to check for regressions**

Run: `pnpm test`
Expected: all tests across the whole app still pass (this confirms no existing page broke from the `Card` styling change).

- [ ] **Step 6: Commit**

```bash
git add src/components/Card.tsx src/components/Card.test.tsx
git commit -m "refactor: migrate Card to violet design system tokens"
```

---

### Task 11: Wire `ToastProvider` and a dark-mode toggle into the app shell

**Files:**
- Modify: `apps/web/src/App.tsx`
- Modify: `apps/web/src/components/Sidebar.tsx`

**Interfaces:**
- Consumes: `ToastProvider` (Task 7), `useDarkMode` (Task 3), `Button` (Task 4).
- Produces: a working, visible dark-mode toggle in the sidebar and a toast layer mounted once for the whole app — this is what makes Tasks 2-9 actually *visible* in the running app for manual verification, without touching any of the 9 real page components (which stay exactly as they are until Phase 20c).

- [ ] **Step 1: Wrap the app in `ToastProvider`**

Modify `apps/web/src/App.tsx` — add the import and wrap the existing `<Layout>` tree. Find:
```tsx
import Layout from "./components/Layout";
```
Add immediately after it:
```tsx
import { ToastProvider } from "./lib/toast";
```
Then find the return statement's outer `<BrowserRouter>` block and wrap `<Layout>` with `<ToastProvider>`, e.g.:
```tsx
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Layout>
            <Routes>
              {/* ...unchanged... */}
            </Routes>
          </Layout>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
```
(Keep every existing `<Route>` entry inside `<Routes>` exactly as-is — only the indentation around them changes because of the new wrapping `<ToastProvider>`.)

- [ ] **Step 2: Add a dark-mode toggle to the sidebar**

Modify `apps/web/src/components/Sidebar.tsx` — add imports at the top:
```tsx
import { useDarkMode } from "../hooks/useDarkMode";
import { Button } from "./ui/Button";
```
Then, inside the `Sidebar` component function, add the hook call:
```tsx
  const { isDark, toggle } = useDarkMode();
```
Then, in the JSX, inside the `{user && (...)}` block, add the toggle button right after the "Sign out" button:
```tsx
          <button onClick={logout} className="text-left text-slate-500 hover:text-slate-900">
            Sign out
          </button>
          <Button variant="ghost" size="sm" onClick={toggle} className="justify-start">
            {isDark ? "☀️ Light mode" : "🌙 Dark mode"}
          </Button>
```

- [ ] **Step 3: Manually verify in a real browser**

Run: `pnpm dev` (from `/opt/collabrains/apps/web`, this binds `0.0.0.0:5173` per the existing Vite config)

Since this server's port 5173 isn't publicly exposed (only 80/443 are, per the production TLS setup), verify over SSH port-forwarding from your own machine:
```bash
ssh -L 5173:localhost:5173 -L 8000:localhost:8000 root@195.90.216.230
```
Then open `http://localhost:5173` locally, log in, and confirm: the "🌙 Dark mode" button appears at the bottom of the sidebar, clicking it flips the whole app to dark colors (background, sidebar, and any `<Card>` on the current page), and reloading the page keeps the chosen mode (persisted via `localStorage`). This is real product code — actually click it in a browser, don't just trust the tests.

- [ ] **Step 4: Run the full test suite one more time**

Run: `pnpm test`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/App.tsx src/components/Sidebar.tsx
git commit -m "feat: wire ToastProvider and dark-mode toggle into the app shell"
```

---

## Self-Review

**Spec coverage:** colors/typography/spacing/elevation/motion tokens → Task 2. Dark mode → Task 3. Button (ripple, 4 variants, 3 sizes) → Task 4. Badge (processing/ready states) → Task 5. Tooltip → Task 6. Toast (with undo) → Task 7. Modal → Task 8. Form inputs (text/select/checkbox/switch, error state) → Task 9. Card migration as an integration proof → Task 10. Visible wiring for manual verification → Task 11. Everything else in the spec (data table+pagination, empty state, drawer, command palette, shortcuts sheet, loading bar, sliding nav pill, bulk selection, filter chips, inline editing, split view, and all 9 real pages) is explicitly out of scope for this plan — see "Scope" above — and will be covered by Phase 20b/20c plans.

**Placeholder scan:** no TBD/TODO; every step has complete, real code.

**Type consistency:** `Button`'s `variant`/`size` union types match across Task 4's component and its test. `useDarkMode`'s return shape (`{ isDark, toggle }`) is used identically in Task 3's test and Task 11's Sidebar wiring. `useToast`'s `showToast(text, { onUndo })` signature matches between Task 7's implementation and test. `TextField`'s `error` prop name matches between Task 9's implementation and test.
