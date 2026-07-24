# App UX Redesign Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure navigation into grouped sections, surface two fully-working "AI knowledge" backends (Facts, Memories) that have no frontend today, add three dry placeholder admin areas, fix two traced bugs, and visually polish the three busiest pages — with zero regression to any existing route or test.

**Architecture:** Pure frontend + no schema changes, working entirely within the existing `apps/web` React/TypeScript app and its established Violet design system (`Card`, `Badge`, `Alert`, `Button`, `EmptyState`, `Dropdown` from `apps/web/src/components`). Facts/Memories/AI Tools tasks add new `apps/web/src/lib/api.ts` client functions against three already-complete FastAPI routers (`facts_router.py`, `memories.py`, `tools_router.py`) — no backend code changes needed anywhere in this plan.

**Tech Stack:** React 18 + TypeScript, react-router v7, react-i18next (en/nl/de), Vitest + @testing-library/react (frontend tests), FastAPI + pytest (backend, read-only reference for existing endpoints — not modified), Playwright (final live smoke check).

## Global Constraints

- **Zero regression**: every existing route, component, and test must keep passing exactly as today. This is additive/reorganizing work, not a rewrite.
- **Violet DS only**: reuse `Card`, `Badge`, `Alert`, `Button`, `EmptyState`, `Dropdown`, `SkeletonLines` from `apps/web/src/components` — no new colors, no new component patterns invented. The user's own Violet DS reference artifact (accent `#5A52E8`/`#8B82FF` dark, `rounded-2xl`/`rounded-xl` cards, `shadow-raised`) matches these components exactly; do not deviate.
- **i18n**: every new user-facing string is a `t("...")` key added to all three locale files: `apps/web/src/locales/en.json`, `nl.json`, `de.json` — never hardcoded text.
- **Test conventions**: frontend tests use Vitest + `@testing-library/react`, mocking `../lib/api` via `vi.mock("../lib/api", async () => { const actual = await vi.importActual...; return { ...actual, someFn: vi.fn() }; })`, matching `AdminDashboard.test.tsx`'s existing pattern exactly.
- **Stub-area contract**: Support Tickets, Email Templates, Product Analytics, Notification Preferences render a real nav entry + real page shell + `EmptyState`, but make **zero API calls** and have **zero working buttons**. Do not add API client functions or backend calls for these four.
- **Facts/Memories/AI Tools are real, not stubs**: full API client functions, full data fetching, full error handling via `Alert`, full test coverage — their backends already work today.
- **Git workflow** (matches this session's established pattern — PRs #108–117, all merged same-day): one feature branch for this whole plan (`feat/ux-redesign-phase1`), small commits per task, push, open a PR, let CI run, merge to `main` after CI is green, then deploy to the live server (178.254.22.178 — `docker compose` rebuild of the `web` container only, no DB migration needed since no schema changed) and verify with Playwright against `https://collabrains.eu` using a disposable test admin user, cleaned up after — same discipline as every prior live-verification pass in this project.

---

### Task 1: Group the main navigation (Overview / Records / Planning / AI Tools / Account)

**Files:**
- Modify: `apps/web/src/lib/navigation.ts`
- Modify: `apps/web/src/components/ui/Dropdown.tsx`
- Modify: `apps/web/src/components/Navbar.tsx`
- Modify: `apps/web/src/components/MobileNavDrawer.tsx`
- Test: `apps/web/src/components/Navbar.test.tsx` (existing file — add cases)
- Test: `apps/web/src/components/MobileNavDrawer.test.tsx` (existing file — add cases)
- Locale: `apps/web/src/locales/en.json`, `nl.json`, `de.json`

**Interfaces:**
- Consumes: existing `NAV_ITEMS`/`navItemsForRole` shape (`{ to, labelKey, icon }`).
- Produces: `NAV_ITEMS` items gain a `group: NavGroup` field; `navItemsForRole` return type becomes `{ to, labelKey, icon, group }[]`. `DropdownOption` gains an optional `group?: string` field consumed by `Dropdown`. Later tasks (2, 6-9) do not depend on this task's output — independent.

The real desktop nav is a horizontal bar (`Navbar.tsx`) with 5 "primary" items always visible plus everything else behind a "More" dropdown, not a vertical sidebar — grouping here means labeled subsections inside that dropdown (and inside the mobile drawer), not a new visual shell.

- [ ] **Step 1: Write the failing test for grouped dropdown rendering**

Add to `apps/web/src/components/ui/Dropdown.test.tsx` (create if it doesn't exist — check first with `find apps/web/src/components/ui -iname "Dropdown.test.tsx"`; if absent, create it):

```typescript
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Dropdown } from "./Dropdown";

describe("Dropdown grouping", () => {
  it("renders a group header once before its options, and none for ungrouped options", () => {
    render(
      <Dropdown
        trigger={<span>Open</span>}
        options={[
          { label: "Vehicles", onSelect: () => {}, group: "Records" },
          { label: "Calendar", onSelect: () => {}, group: "Planning" },
          { label: "Assistant", onSelect: () => {}, group: "Planning" },
          { label: "Sign out", onSelect: () => {} },
        ]}
      />
    );
    fireEvent.click(screen.getByText("Open"));
    const menu = screen.getByRole("menu");
    const headers = menu.querySelectorAll("[data-testid='dropdown-group-header']");
    expect(headers).toHaveLength(2);
    expect(headers[0]).toHaveTextContent("Records");
    expect(headers[1]).toHaveTextContent("Planning");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/components/ui/Dropdown.test.tsx`
Expected: FAIL — `group` prop doesn't exist on `DropdownOption`, no `dropdown-group-header` testid rendered.

- [ ] **Step 3: Add `group` support to `DropdownOption` and `Dropdown`**

In `apps/web/src/components/ui/Dropdown.tsx`, change:

```typescript
export interface DropdownOption {
  label: string;
  onSelect: () => void;
  danger?: boolean;
}
```

to:

```typescript
export interface DropdownOption {
  label: string;
  onSelect: () => void;
  danger?: boolean;
  group?: string;
}
```

Then replace the options-rendering block:

```typescript
        {options.map((option) => (
          <button
            key={option.label}
            role="menuitem"
            type="button"
            onClick={() => {
              option.onSelect();
              setOpen(false);
            }}
            className={`block w-full rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors duration-fast ${
              option.danger ? "text-danger hover:bg-danger-soft" : "text-ink-2 hover:bg-hover hover:text-ink"
            }`}
          >
            {option.label}
          </button>
        ))}
```

with:

```typescript
        {options.map((option, index) => {
          const showHeader = option.group && option.group !== options[index - 1]?.group;
          return (
            <div key={option.label}>
              {showHeader && (
                <div
                  data-testid="dropdown-group-header"
                  className="px-2.5 pb-1 pt-2 text-[10.5px] font-semibold uppercase tracking-wide text-ink-3"
                >
                  {option.group}
                </div>
              )}
              <button
                role="menuitem"
                type="button"
                onClick={() => {
                  option.onSelect();
                  setOpen(false);
                }}
                className={`block w-full rounded-lg px-2.5 py-2 text-left text-[13px] transition-colors duration-fast ${
                  option.danger ? "text-danger hover:bg-danger-soft" : "text-ink-2 hover:bg-hover hover:text-ink"
                }`}
              >
                {option.label}
              </button>
            </div>
          );
        })}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && npx vitest run src/components/ui/Dropdown.test.tsx`
Expected: PASS

- [ ] **Step 5: Add `group` to `NAV_ITEMS` and update `navItemsForRole`**

In `apps/web/src/lib/navigation.ts`, replace the whole file body with:

```typescript
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

export type NavGroup = "Overview" | "Records" | "Planning" | "AI Tools" | "Account";

export const NAV_ITEMS: { to: string; labelKey: string; icon: LucideIcon; group: NavGroup }[] = [
  { to: "/", labelKey: "nav.dashboard", icon: LayoutDashboard, group: "Overview" },
  { to: "/documents", labelKey: "nav.documents", icon: FileText, group: "Records" },
  { to: "/entities", labelKey: "nav.entities", icon: Users, group: "Records" },
  { to: "/cases", labelKey: "nav.cases", icon: FolderOpen, group: "Records" },
  { to: "/vehicles", labelKey: "nav.vehicles", icon: Car, group: "Records" },
  { to: "/tasks", labelKey: "nav.tasks", icon: CheckSquare, group: "Planning" },
  { to: "/calendar", labelKey: "nav.calendar", icon: Calendar, group: "Planning" },
  { to: "/chat", labelKey: "nav.aiChat", icon: Sparkles, group: "AI Tools" },
  { to: "/legal", labelKey: "nav.legalDraft", icon: Scale, group: "AI Tools" },
  { to: "/assistant", labelKey: "nav.assistant", icon: Bot, group: "AI Tools" },
  { to: "/settings", labelKey: "nav.settings", icon: Settings, group: "Account" },
];

export function navItemsForRole(
  role: string | undefined
): { to: string; labelKey: string; icon: LucideIcon; group: NavGroup }[] {
  if (role !== "admin") return NAV_ITEMS;
  return [...NAV_ITEMS, { to: "/admin", labelKey: "nav.admin", icon: ShieldCheck, group: "Account" }];
}
```

Note: item order changed (grouped items are now adjacent) but every `to`/`labelKey`/`icon` value is unchanged — no route behavior changes.

- [ ] **Step 6: Wire `group` through the "More" dropdown in `Navbar.tsx`**

In `apps/web/src/components/Navbar.tsx`, replace:

```typescript
  const moreOptions = secondaryItems.map((item) => ({
    label: t(item.labelKey),
    onSelect: () => navigate(item.to),
  }));
```

with:

```typescript
  const moreOptions = secondaryItems.map((item) => ({
    label: t(item.labelKey),
    onSelect: () => navigate(item.to),
    group: t(`navGroup.${item.group.toLowerCase().replace(/\s+/g, "")}`),
  }));
```

- [ ] **Step 7: Add group headers to `MobileNavDrawer.tsx`**

In `apps/web/src/components/MobileNavDrawer.tsx`, replace the `<nav>` block:

```typescript
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
```

with:

```typescript
        <nav className="flex flex-col gap-1 text-sm">
          {navItems.map((item, index) => {
            const Icon = item.icon;
            const showHeader = item.group !== navItems[index - 1]?.group;
            return (
              <div key={item.to}>
                {showHeader && (
                  <div
                    data-testid="drawer-group-header"
                    className="px-3 pb-1 pt-3 text-[10.5px] font-semibold uppercase tracking-wide text-ink-3 first:pt-0"
                  >
                    {t(`navGroup.${item.group.toLowerCase().replace(/\s+/g, "")}`)}
                  </div>
                )}
                <NavLink
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
              </div>
            );
          })}
        </nav>
```

- [ ] **Step 8: Add the 5 group-label translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside the top-level object, add:

```json
  "navGroup": {
    "overview": "Overview",
    "records": "Records",
    "planning": "Planning",
    "aitools": "AI Tools",
    "account": "Account"
  },
```

In `apps/web/src/locales/nl.json`:

```json
  "navGroup": {
    "overview": "Overzicht",
    "records": "Documenten",
    "planning": "Planning",
    "aitools": "AI-tools",
    "account": "Account"
  },
```

In `apps/web/src/locales/de.json`:

```json
  "navGroup": {
    "overview": "Übersicht",
    "records": "Unterlagen",
    "planning": "Planung",
    "aitools": "KI-Werkzeuge",
    "account": "Konto"
  },
```

- [ ] **Step 9: Run the full frontend test suite to check for regressions**

Run: `cd apps/web && npx vitest run`
Expected: PASS — same pass count as before this task, plus the new `Dropdown.test.tsx` case.

- [ ] **Step 10: Commit**

```bash
git checkout -b feat/ux-redesign-phase1
git add apps/web/src/lib/navigation.ts apps/web/src/components/ui/Dropdown.tsx apps/web/src/components/ui/Dropdown.test.tsx apps/web/src/components/Navbar.tsx apps/web/src/components/MobileNavDrawer.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(nav): group main navigation into Overview/Records/Planning/AI Tools/Account"
```

---

### Task 2: Regroup Admin tabs (Overview / Users / Monitoring / Feedback / Communication)

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx`
- Modify: `apps/web/src/routes/AdminDashboard.test.tsx`
- Locale: `apps/web/src/locales/en.json`, `nl.json`, `de.json`

**Interfaces:**
- Consumes: existing `Tab` type (`"overview" | "ai-usage" | "health" | "bugs" | "users" | "feedback"`).
- Produces: `Tab` type extended with `"support-tickets" | "email-templates" | "product-analytics"` (added here as empty tab-content placeholders; Tasks 3-5 fill in their real component bodies by replacing a one-line placeholder each — this task's job is only the grouped tab bar plus a trivial `<EmptyState>` placeholder for each new id so Tasks 3-5 have an exact anchor to replace).

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/AdminDashboard.test.tsx`:

```typescript
describe("AdminDashboard grouped tabs", () => {
  it("renders group headers in the tab bar", () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    render(<AdminDashboard />);
    const tabBar = screen.getByRole("tablist");
    expect(tabBar.querySelectorAll("[data-testid='admin-tab-group-header']")).toHaveLength(4);
    expect(screen.getByRole("tab", { name: "Support Tickets" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Email Templates" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Product Analytics" })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx -t "grouped tabs"`
Expected: FAIL — no `role="tablist"`, no new tabs exist yet.

- [ ] **Step 3: Restructure the tab type and tab bar**

In `apps/web/src/routes/AdminDashboard.tsx`, replace:

```typescript
type Tab = "overview" | "ai-usage" | "health" | "bugs" | "users" | "feedback";
```

with:

```typescript
type Tab =
  | "overview"
  | "users"
  | "health"
  | "ai-usage"
  | "product-analytics"
  | "bugs"
  | "feedback"
  | "support-tickets"
  | "email-templates";

const TAB_GROUPS: { labelKey: string; tabs: Tab[] }[] = [
  { labelKey: "admin.groupUsers", tabs: ["users"] },
  { labelKey: "admin.groupMonitoring", tabs: ["health", "ai-usage", "product-analytics"] },
  { labelKey: "admin.groupFeedback", tabs: ["bugs", "feedback", "support-tickets"] },
  { labelKey: "admin.groupCommunication", tabs: ["email-templates"] },
];
```

Find the current tab-bar rendering (search for `tabs.map((tabOption)` around line 59-70) and replace the whole tab-bar JSX block:

```typescript
        {tabs.map((tabOption) => (
          <button
            key={tabOption.id}
            onClick={() => setTab(tabOption.id)}
            className={
              tab === tabOption.id ? "border-b-2 border-accent text-accent" : "text-ink-3 hover:text-ink"
            }
          >
            {tabOption.label}
          </button>
        ))}
```

with:

```typescript
      <div role="tablist" className="flex flex-wrap items-center gap-1 border-b border-edge pb-0">
        <button
          role="tab"
          aria-selected={tab === "overview"}
          onClick={() => setTab("overview")}
          className={`px-3 py-2 text-sm ${tab === "overview" ? "border-b-2 border-accent font-semibold text-accent" : "text-ink-3 hover:text-ink"}`}
        >
          {t("admin.tabOverview")}
        </button>
        {TAB_GROUPS.map((groupDef) => (
          <div key={groupDef.labelKey} className="flex items-center gap-1">
            <span data-testid="admin-tab-group-header" className="px-2 text-[10.5px] font-semibold uppercase tracking-wide text-ink-3">
              {t(groupDef.labelKey)}
            </span>
            {groupDef.tabs.map((tabId) => (
              <button
                key={tabId}
                role="tab"
                aria-selected={tab === tabId}
                onClick={() => setTab(tabId)}
                className={`px-3 py-2 text-sm ${tab === tabId ? "border-b-2 border-accent font-semibold text-accent" : "text-ink-3 hover:text-ink"}`}
              >
                {t(TAB_LABEL_KEYS[tabId])}
              </button>
            ))}
          </div>
        ))}
      </div>
```

Add the label-key lookup table right after `TAB_GROUPS`:

```typescript
const TAB_LABEL_KEYS: Record<Tab, string> = {
  overview: "admin.tabOverview",
  users: "admin.tabUsers",
  health: "admin.tabHealth",
  "ai-usage": "admin.tabAiUsage",
  "product-analytics": "admin.tabProductAnalytics",
  bugs: "admin.tabBugs",
  feedback: "admin.tabFeedback",
  "support-tickets": "admin.tabSupportTickets",
  "email-templates": "admin.tabEmailTemplates",
};
```

Find the tab-content switch (search for `{tab === "overview" && <OverviewTab />}` around line 72-77) and replace with:

```typescript
      {tab === "overview" && <OverviewTab />}
      {tab === "ai-usage" && <AiUsageTab />}
      {tab === "health" && <HealthTab />}
      {tab === "bugs" && <BugsTab />}
      {tab === "users" && <UsersTab />}
      {tab === "feedback" && <FeedbackTab />}
      {tab === "product-analytics" && <ProductAnalyticsTab />}
      {tab === "support-tickets" && <SupportTicketsTab />}
      {tab === "email-templates" && <EmailTemplatesTab />}
```

Add three placeholder tab components at the end of the file (Tasks 3-5 replace each function body in turn — this is the exact anchor each of those tasks edits):

```typescript
function ProductAnalyticsTab() {
  const { t } = useTranslation();
  return <EmptyState message={t("admin.productAnalyticsPlaceholder")} />;
}

function SupportTicketsTab() {
  const { t } = useTranslation();
  return <EmptyState message={t("admin.supportTicketsPlaceholder")} />;
}

function EmailTemplatesTab() {
  const { t } = useTranslation();
  return <EmptyState message={t("admin.emailTemplatesPlaceholder")} />;
}
```

- [ ] **Step 4: Add the new translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside the existing `"admin": { ... }` object, add:

```json
    "groupUsers": "Users",
    "groupMonitoring": "Monitoring",
    "groupFeedback": "Feedback",
    "groupCommunication": "Communication",
    "tabProductAnalytics": "Product Analytics",
    "tabSupportTickets": "Support Tickets",
    "tabEmailTemplates": "Email Templates",
    "productAnalyticsPlaceholder": "Product analytics is coming soon.",
    "supportTicketsPlaceholder": "Support tickets are coming soon.",
    "emailTemplatesPlaceholder": "Email template management is coming soon.",
```

In `apps/web/src/locales/nl.json`, inside `"admin": { ... }`:

```json
    "groupUsers": "Gebruikers",
    "groupMonitoring": "Monitoring",
    "groupFeedback": "Feedback",
    "groupCommunication": "Communicatie",
    "tabProductAnalytics": "Productanalyse",
    "tabSupportTickets": "Support tickets",
    "tabEmailTemplates": "E-mailsjablonen",
    "productAnalyticsPlaceholder": "Productanalyse komt binnenkort.",
    "supportTicketsPlaceholder": "Support tickets komen binnenkort.",
    "emailTemplatesPlaceholder": "E-mailsjabloonbeheer komt binnenkort.",
```

In `apps/web/src/locales/de.json`, inside `"admin": { ... }`:

```json
    "groupUsers": "Benutzer",
    "groupMonitoring": "Überwachung",
    "groupFeedback": "Feedback",
    "groupCommunication": "Kommunikation",
    "tabProductAnalytics": "Produktanalyse",
    "tabSupportTickets": "Support-Tickets",
    "tabEmailTemplates": "E-Mail-Vorlagen",
    "productAnalyticsPlaceholder": "Produktanalyse folgt in Kürze.",
    "supportTicketsPlaceholder": "Support-Tickets folgen in Kürze.",
    "emailTemplatesPlaceholder": "E-Mail-Vorlagenverwaltung folgt in Kürze.",
```

- [ ] **Step 5: Run test to verify it passes, then the full suite**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): regroup Admin tabs into Users/Monitoring/Feedback/Communication + 3 stub tabs"
```

---

### Task 3: Support Tickets stub tab (dry placeholder)

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx` (replace `SupportTicketsTab` body from Task 2)
- Modify: `apps/web/src/routes/AdminDashboard.test.tsx`

**Interfaces:**
- Consumes: `EmptyState` component (`{ heading?, message, action? }`).
- Produces: nothing consumed by later tasks — fully independent, can run in parallel with Tasks 4, 5, 6, 7, 8, 9.

- [ ] **Step 1: Write the failing test**

```typescript
describe("AdminDashboard Support Tickets tab", () => {
  it("shows a dry placeholder with no API calls", () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("tab", { name: "Support Tickets" }));
    expect(screen.getByText("No support tickets yet")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx -t "Support Tickets"`
Expected: FAIL — current placeholder text is "Support tickets are coming soon.", not "No support tickets yet".

- [ ] **Step 3: Replace the `SupportTicketsTab` body**

In `apps/web/src/routes/AdminDashboard.tsx`, replace:

```typescript
function SupportTicketsTab() {
  const { t } = useTranslation();
  return <EmptyState message={t("admin.supportTicketsPlaceholder")} />;
}
```

with:

```typescript
function SupportTicketsTab() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold text-ink">{t("admin.tabSupportTickets")}</h2>
        <Button size="sm" variant="secondary" disabled>
          {t("admin.newTicket")}
        </Button>
      </div>
      <EmptyState heading={t("admin.supportTicketsEmptyHeading")} message={t("admin.supportTicketsEmptyBody")} />
    </div>
  );
}
```

- [ ] **Step 4: Update translation keys in all 3 locales**

In `apps/web/src/locales/en.json`, inside `"admin": { ... }`, replace `"supportTicketsPlaceholder": "Support tickets are coming soon.",` with:

```json
    "newTicket": "New ticket",
    "supportTicketsEmptyHeading": "No support tickets yet",
    "supportTicketsEmptyBody": "Ticket tracking is not wired up yet -- this is a preview of where it will live.",
```

In `apps/web/src/locales/nl.json`, replace `"supportTicketsPlaceholder": "Support tickets komen binnenkort.",` with:

```json
    "newTicket": "Nieuw ticket",
    "supportTicketsEmptyHeading": "Nog geen support tickets",
    "supportTicketsEmptyBody": "Ticketbeheer is nog niet aangesloten -- dit is een voorbeeld van waar het straks komt.",
```

In `apps/web/src/locales/de.json`, replace `"supportTicketsPlaceholder": "Support-Tickets folgen in Kürze.",` with:

```json
    "newTicket": "Neues Ticket",
    "supportTicketsEmptyHeading": "Noch keine Support-Tickets",
    "supportTicketsEmptyBody": "Die Ticketverwaltung ist noch nicht angebunden -- dies ist eine Vorschau.",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): Support Tickets stub tab"
```

---

### Task 4: Email Templates stub tab (dry placeholder)

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx` (replace `EmailTemplatesTab` body from Task 2)
- Modify: `apps/web/src/routes/AdminDashboard.test.tsx`

**Interfaces:** Fully independent, same pattern as Task 3.

- [ ] **Step 1: Write the failing test**

```typescript
describe("AdminDashboard Email Templates tab", () => {
  it("shows a dry placeholder with a disabled test-send button", () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("tab", { name: "Email Templates" }));
    expect(screen.getByRole("button", { name: "Send test" })).toBeDisabled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx -t "Email Templates"`
Expected: FAIL — no such button exists yet.

- [ ] **Step 3: Replace the `EmailTemplatesTab` body**

```typescript
function EmailTemplatesTab() {
  const { t } = useTranslation();
  return (
    <div className="flex max-w-md flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("admin.tabEmailTemplates")}</h2>
      <div>
        <label className="text-sm font-medium text-ink">{t("admin.emailTemplateLabel")}</label>
        <select disabled className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink-3">
          <option>{t("admin.emailTemplateWelcome")}</option>
        </select>
      </div>
      <div>
        <label className="text-sm font-medium text-ink">{t("admin.emailTestRecipient")}</label>
        <input disabled placeholder="you@example.com" className="mt-1 w-full rounded-xl border border-edge bg-surface px-3 py-2 text-sm text-ink-3" />
      </div>
      <Button size="sm" disabled className="self-start">
        {t("admin.sendTest")}
      </Button>
      <p className="text-xs text-ink-3">{t("admin.emailTemplatesPlaceholder")}</p>
    </div>
  );
}
```

- [ ] **Step 4: Add translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside `"admin": { ... }`, add:

```json
    "emailTemplateLabel": "Template",
    "emailTemplateWelcome": "Welcome email",
    "emailTestRecipient": "Send test to",
    "sendTest": "Send test",
```

In `apps/web/src/locales/nl.json`:

```json
    "emailTemplateLabel": "Sjabloon",
    "emailTemplateWelcome": "Welkomst-e-mail",
    "emailTestRecipient": "Test versturen naar",
    "sendTest": "Test versturen",
```

In `apps/web/src/locales/de.json`:

```json
    "emailTemplateLabel": "Vorlage",
    "emailTemplateWelcome": "Willkommens-E-Mail",
    "emailTestRecipient": "Test senden an",
    "sendTest": "Test senden",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): Email Templates stub tab"
```

---

### Task 5: Product Analytics stub tab (dry placeholder)

**Files:**
- Modify: `apps/web/src/routes/AdminDashboard.tsx` (replace `ProductAnalyticsTab` body from Task 2)
- Modify: `apps/web/src/routes/AdminDashboard.test.tsx`

**Interfaces:** Fully independent, same pattern as Tasks 3-4.

- [ ] **Step 1: Write the failing test**

```typescript
describe("AdminDashboard Product Analytics tab", () => {
  it("shows placeholder stat tiles with dashes, not real numbers", () => {
    vi.mocked(api.getAdminStats).mockResolvedValue({
      total_users: 0, total_documents: 0, documents_by_status: {}, ai_calls_last_24h: 0,
    });
    render(<AdminDashboard />);
    fireEvent.click(screen.getByRole("tab", { name: "Product Analytics" }));
    expect(screen.getAllByText("—")).toHaveLength(3);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx -t "Product Analytics"`
Expected: FAIL — no stat tiles exist yet.

- [ ] **Step 3: Replace the `ProductAnalyticsTab` body**

```typescript
function ProductAnalyticsTab() {
  const { t } = useTranslation();
  const stats = [
    t("admin.paTotalUsersTrend"),
    t("admin.paDocsProcessedTrend"),
    t("admin.paAvgResponseTime"),
  ];
  return (
    <div className="flex flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("admin.tabProductAnalytics")}</h2>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {stats.map((label) => (
          <Card key={label} className="flex flex-col gap-1">
            <span className="text-xs text-ink-3">{label}</span>
            <span className="text-2xl font-semibold text-ink">—</span>
          </Card>
        ))}
      </div>
      <p className="text-xs text-ink-3">{t("admin.productAnalyticsPlaceholder")}</p>
    </div>
  );
}
```

- [ ] **Step 4: Add translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside `"admin": { ... }`, add:

```json
    "paTotalUsersTrend": "Total users (trend)",
    "paDocsProcessedTrend": "Documents processed (trend)",
    "paAvgResponseTime": "Avg. response time",
```

In `apps/web/src/locales/nl.json`:

```json
    "paTotalUsersTrend": "Totaal gebruikers (trend)",
    "paDocsProcessedTrend": "Verwerkte documenten (trend)",
    "paAvgResponseTime": "Gem. reactietijd",
```

In `apps/web/src/locales/de.json`:

```json
    "paTotalUsersTrend": "Nutzer gesamt (Trend)",
    "paDocsProcessedTrend": "Verarbeitete Dokumente (Trend)",
    "paAvgResponseTime": "Durchschn. Reaktionszeit",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd apps/web && npx vitest run src/routes/AdminDashboard.test.tsx`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/AdminDashboard.tsx apps/web/src/routes/AdminDashboard.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(admin): Product Analytics stub tab"
```

---

### Task 6: Notification Preferences stub (Settings)

**Files:**
- Modify: `apps/web/src/routes/Settings.tsx`
- Modify: `apps/web/src/routes/Settings.test.tsx`

**Interfaces:**
- Produces: a `NotificationPreferencesSection` component rendered in `Settings.tsx` right after the general-prefs `<Card>` (before `<PasskeySettings />`). No API calls. Fully independent of every other task.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/Settings.test.tsx`:

```typescript
describe("Notification Preferences (stub)", () => {
  it("renders the digest toggle with no backend call", () => {
    render(<Settings />);
    expect(screen.getByText("Notifications")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Per document" })).toBeChecked();
    expect(screen.getByRole("radio", { name: "Daily digest" })).not.toBeChecked();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx -t "Notification Preferences"`
Expected: FAIL — no such section exists yet.

- [ ] **Step 3: Add the `NotificationPreferencesSection` component**

In `apps/web/src/routes/Settings.tsx`, add this new function near `OrganizationSection` (same file, any location after imports):

```typescript
function NotificationPreferencesSection() {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"per-document" | "digest">("per-document");
  return (
    <Card className="flex max-w-md flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("settings.notificationsTitle")}</h2>
      <p className="text-xs text-ink-3">{t("settings.notificationsHint")}</p>
      <label className="flex items-center gap-2 text-sm text-ink">
        <input
          type="radio"
          name="notif-mode"
          checked={mode === "per-document"}
          onChange={() => setMode("per-document")}
        />
        {t("settings.notifPerDocument")}
      </label>
      <label className="flex items-center gap-2 text-sm text-ink">
        <input type="radio" name="notif-mode" checked={mode === "digest"} onChange={() => setMode("digest")} />
        {t("settings.notifDigest")}
      </label>
      <p className="text-xs text-ink-3">{t("settings.notificationsPlaceholder")}</p>
    </Card>
  );
}
```

Then insert `<NotificationPreferencesSection />` into the main `Settings` component's return, directly after the closing `</Card>` of the general-prefs card and before `<PasskeySettings />`:

```typescript
      </Card>

      <NotificationPreferencesSection />

      <PasskeySettings />
```

- [ ] **Step 4: Add translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside `"settings": { ... }`, add:

```json
    "notificationsTitle": "Notifications",
    "notificationsHint": "Choose how you're notified when a new document is processed.",
    "notifPerDocument": "Per document",
    "notifDigest": "Daily digest",
    "notificationsPlaceholder": "This is a preview -- the digest schedule isn't wired up yet.",
```

In `apps/web/src/locales/nl.json`:

```json
    "notificationsTitle": "Meldingen",
    "notificationsHint": "Kies hoe je een melding krijgt als een nieuw document is verwerkt.",
    "notifPerDocument": "Per document",
    "notifDigest": "Dagelijks overzicht",
    "notificationsPlaceholder": "Dit is een voorbeeld -- het dagelijkse overzicht is nog niet aangesloten.",
```

In `apps/web/src/locales/de.json`:

```json
    "notificationsTitle": "Benachrichtigungen",
    "notificationsHint": "Wähle, wie du benachrichtigt wirst, wenn ein neues Dokument verarbeitet wurde.",
    "notifPerDocument": "Pro Dokument",
    "notifDigest": "Tägliche Zusammenfassung",
    "notificationsPlaceholder": "Dies ist eine Vorschau -- der Zeitplan ist noch nicht angebunden.",
```

- [ ] **Step 5: Run test to verify it passes, then full suite**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/Settings.tsx apps/web/src/routes/Settings.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(settings): Notification Preferences stub"
```

---

### Task 7: Facts section in Settings (real — list, approve, reject)

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/routes/Settings.tsx`
- Modify: `apps/web/src/routes/Settings.test.tsx`

**Interfaces:**
- Produces: `api.ts` exports `listFacts(): Promise<UserFactOut[]>`, `approveFact(id: string): Promise<UserFactOut>`, `rejectFact(id: string): Promise<UserFactOut>`, and type `UserFactOut { id: string; user_id: string; fact_type: string; value: Record<string, unknown>; valid_from: string; valid_to: string | null; confidence: number; status: string; created_at: string }`. Independent of every other task — backend (`facts_router.py`) already exists unmodified.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/Settings.test.tsx`:

```typescript
describe("Facts section", () => {
  it("lists pending facts and approves one", async () => {
    vi.mocked(api.listFacts).mockResolvedValue([
      {
        id: "f1", user_id: "u1", fact_type: "address", value: { city: "Utrecht" },
        valid_from: "2026-01-01", valid_to: null, confidence: 0.9, status: "pending_review",
        created_at: "2026-01-01T00:00:00Z",
      },
    ]);
    vi.mocked(api.approveFact).mockResolvedValue({
      id: "f1", user_id: "u1", fact_type: "address", value: { city: "Utrecht" },
      valid_from: "2026-01-01", valid_to: null, confidence: 0.9, status: "confirmed",
      created_at: "2026-01-01T00:00:00Z",
    });
    render(<Settings />);
    expect(await screen.findByText("address")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(api.approveFact).toHaveBeenCalledWith("f1"));
  });
});
```

Add the corresponding mocks to the existing `vi.mock("../lib/api", ...)` block at the top of `Settings.test.tsx`: add `listFacts: vi.fn()`, `approveFact: vi.fn()`, `rejectFact: vi.fn()` to the returned object.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx -t "Facts section"`
Expected: FAIL — `api.listFacts` is not a function.

- [ ] **Step 3: Add the API client functions**

In `apps/web/src/lib/api.ts`, add (near the other list/detail functions, e.g. after `getPreferences`/`setPreferences`):

```typescript
export interface UserFactOut {
  id: string;
  user_id: string;
  fact_type: string;
  value: Record<string, unknown>;
  valid_from: string;
  valid_to: string | null;
  confidence: number;
  status: string;
  created_at: string;
}

export function listFacts(): Promise<UserFactOut[]> {
  return request<UserFactOut[]>("/facts");
}

export function approveFact(id: string): Promise<UserFactOut> {
  return request<UserFactOut>(`/facts/${id}/approve`, { method: "POST" });
}

export function rejectFact(id: string): Promise<UserFactOut> {
  return request<UserFactOut>(`/facts/${id}/reject`, { method: "POST" });
}
```

- [ ] **Step 4: Add the `FactsSection` component to `Settings.tsx`**

```typescript
function FactsSection() {
  const { t } = useTranslation();
  const [facts, setFacts] = useState<UserFactOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    listFacts()
      .then(setFacts)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.factsLoadError")));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  useEffect(load, []);

  async function handleApprove(id: string) {
    setBusyId(id);
    try {
      await approveFact(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.factsActionError"));
    } finally {
      setBusyId(null);
    }
  }

  async function handleReject(id: string) {
    setBusyId(id);
    try {
      await rejectFact(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.factsActionError"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card className="flex max-w-md flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("settings.factsTitle")}</h2>
      <p className="text-xs text-ink-3">{t("settings.factsHint")}</p>
      {error && (
        <Alert variant="danger" title={t("settings.factsLoadError")}>
          {error}
        </Alert>
      )}
      {!facts ? (
        <SkeletonLines />
      ) : facts.length === 0 ? (
        <EmptyState message={t("settings.factsEmpty")} />
      ) : (
        facts.map((fact) => (
          <div key={fact.id} className="flex items-center justify-between gap-2 rounded-xl border border-edge p-3">
            <div>
              <p className="text-sm font-medium text-ink">{fact.fact_type}</p>
              <p className="text-xs text-ink-3">{JSON.stringify(fact.value)}</p>
              <Badge variant={fact.status === "confirmed" ? "success" : fact.status === "rejected" ? "danger" : "default"}>
                {fact.status}
              </Badge>
            </div>
            {fact.status === "pending_review" && (
              <div className="flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => handleApprove(fact.id)} disabled={busyId === fact.id}>
                  {t("settings.factsApprove")}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => handleReject(fact.id)} disabled={busyId === fact.id}>
                  {t("settings.factsReject")}
                </Button>
              </div>
            )}
          </div>
        ))
      )}
    </Card>
  );
}
```

Add the needed imports at the top of `Settings.tsx`: `Alert` from `"../components/ui/Alert"`, `SkeletonLines` from `"../components/ui/Skeleton"`, `EmptyState` from `"../components/EmptyState"` (default import), and add `listFacts, approveFact, rejectFact, type UserFactOut` to the existing `from "../lib/api"` import block.

Insert `<FactsSection />` into the main return, directly after `<NotificationPreferencesSection />` and before `<PasskeySettings />`.

- [ ] **Step 5: Add translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside `"settings": { ... }`, add:

```json
    "factsTitle": "What the AI knows about you",
    "factsHint": "Facts extracted from your documents. Approve or reject anything pending review.",
    "factsEmpty": "No facts on file yet.",
    "factsApprove": "Approve",
    "factsReject": "Reject",
    "factsLoadError": "Couldn't load your facts.",
    "factsActionError": "That didn't go through -- try again.",
```

In `apps/web/src/locales/nl.json`:

```json
    "factsTitle": "Wat de AI over je weet",
    "factsHint": "Feiten uit je documenten. Keur goed of af wat nog beoordeeld moet worden.",
    "factsEmpty": "Nog geen feiten bekend.",
    "factsApprove": "Goedkeuren",
    "factsReject": "Afwijzen",
    "factsLoadError": "Kon je feiten niet laden.",
    "factsActionError": "Dat is niet gelukt -- probeer het opnieuw.",
```

In `apps/web/src/locales/de.json`:

```json
    "factsTitle": "Was die KI über dich weiß",
    "factsHint": "Aus deinen Dokumenten extrahierte Fakten. Genehmige oder lehne ausstehende ab.",
    "factsEmpty": "Noch keine Fakten vorhanden.",
    "factsApprove": "Genehmigen",
    "factsReject": "Ablehnen",
    "factsLoadError": "Deine Fakten konnten nicht geladen werden.",
    "factsActionError": "Das hat nicht geklappt -- versuch es erneut.",
```

- [ ] **Step 6: Run test to verify it passes, then full suite**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/routes/Settings.tsx apps/web/src/routes/Settings.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(settings): AI Facts section -- list, approve, reject (real backend)"
```

---

### Task 8: Memories section in Settings (real — list, delete)

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/routes/Settings.tsx`
- Modify: `apps/web/src/routes/Settings.test.tsx`

**Interfaces:**
- Produces: `listMemories(): Promise<MemoryOut[]>`, `deleteMemory(id: string): Promise<void>`, type `MemoryOut { id: string; memory_type: string; importance: number; summary: string; created_at: string; last_used_at: string | null; expires_at: string | null }`. Independent of every other task.

- [ ] **Step 1: Write the failing test**

```typescript
describe("Memories section", () => {
  it("lists memories and deletes one", async () => {
    vi.mocked(api.listMemories).mockResolvedValue([
      {
        id: "m1", memory_type: "preference", importance: 5, summary: "Prefers Dutch responses",
        created_at: "2026-01-01T00:00:00Z", last_used_at: null, expires_at: null,
      },
    ]);
    vi.mocked(api.deleteMemory).mockResolvedValue(undefined);
    render(<Settings />);
    expect(await screen.findByText("Prefers Dutch responses")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Forget this" }));
    await waitFor(() => expect(api.deleteMemory).toHaveBeenCalledWith("m1"));
  });
});
```

Add `listMemories: vi.fn(), deleteMemory: vi.fn()` to the `vi.mock("../lib/api", ...)` block.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx -t "Memories section"`
Expected: FAIL — `api.listMemories` is not a function.

- [ ] **Step 3: Add the API client functions**

In `apps/web/src/lib/api.ts`:

```typescript
export interface MemoryOut {
  id: string;
  memory_type: string;
  importance: number;
  summary: string;
  created_at: string;
  last_used_at: string | null;
  expires_at: string | null;
}

export function listMemories(): Promise<MemoryOut[]> {
  return request<MemoryOut[]>("/memories");
}

export function deleteMemory(id: string): Promise<void> {
  return request<void>(`/memories/${id}`, { method: "DELETE" });
}
```

- [ ] **Step 4: Add the `MemoriesSection` component to `Settings.tsx`**

```typescript
function MemoriesSection() {
  const { t } = useTranslation();
  const [memories, setMemories] = useState<MemoryOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  function load() {
    listMemories()
      .then(setMemories)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.memoriesLoadError")));
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  useEffect(load, []);

  async function handleDelete(id: string) {
    setBusyId(id);
    try {
      await deleteMemory(id);
      load();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : t("settings.memoriesActionError"));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <Card className="flex max-w-md flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("settings.memoriesTitle")}</h2>
      <p className="text-xs text-ink-3">{t("settings.memoriesHint")}</p>
      {error && (
        <Alert variant="danger" title={t("settings.memoriesLoadError")}>
          {error}
        </Alert>
      )}
      {!memories ? (
        <SkeletonLines />
      ) : memories.length === 0 ? (
        <EmptyState message={t("settings.memoriesEmpty")} />
      ) : (
        memories.map((memory) => (
          <div key={memory.id} className="flex items-center justify-between gap-2 rounded-xl border border-edge p-3">
            <p className="text-sm text-ink">{memory.summary}</p>
            <Button size="sm" variant="ghost" onClick={() => handleDelete(memory.id)} disabled={busyId === memory.id}>
              {t("settings.memoriesForget")}
            </Button>
          </div>
        ))
      )}
    </Card>
  );
}
```

Add `listMemories, deleteMemory, type MemoryOut` to the existing `from "../lib/api"` import in `Settings.tsx`. Insert `<MemoriesSection />` directly after `<FactsSection />`.

- [ ] **Step 5: Add translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside `"settings": { ... }`, add:

```json
    "memoriesTitle": "What the AI remembers",
    "memoriesHint": "Things the assistant has picked up from your conversations. Delete anything you'd rather it forgot.",
    "memoriesEmpty": "Nothing on file yet.",
    "memoriesForget": "Forget this",
    "memoriesLoadError": "Couldn't load your memories.",
    "memoriesActionError": "That didn't go through -- try again.",
```

In `apps/web/src/locales/nl.json`:

```json
    "memoriesTitle": "Wat de AI onthoudt",
    "memoriesHint": "Dingen die de assistent heeft opgepikt uit je gesprekken. Verwijder wat je liever vergeten ziet.",
    "memoriesEmpty": "Nog niets bekend.",
    "memoriesForget": "Vergeten",
    "memoriesLoadError": "Kon je herinneringen niet laden.",
    "memoriesActionError": "Dat is niet gelukt -- probeer het opnieuw.",
```

In `apps/web/src/locales/de.json`:

```json
    "memoriesTitle": "Was die KI sich merkt",
    "memoriesHint": "Dinge, die der Assistent aus deinen Gesprächen aufgeschnappt hat. Lösche, was er lieber vergessen soll.",
    "memoriesEmpty": "Noch nichts vorhanden.",
    "memoriesForget": "Vergessen",
    "memoriesLoadError": "Deine Erinnerungen konnten nicht geladen werden.",
    "memoriesActionError": "Das hat nicht geklappt -- versuch es erneut.",
```

- [ ] **Step 6: Run test to verify it passes, then full suite**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/routes/Settings.tsx apps/web/src/routes/Settings.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(settings): AI Memories section -- list, forget (real backend)"
```

---

### Task 9: AI Tools transparency section in Settings (real — read-only list)

**Files:**
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/routes/Settings.tsx`
- Modify: `apps/web/src/routes/Settings.test.tsx`

**Interfaces:**
- Produces: `listAiTools(): Promise<ToolOut[]>`, type `ToolOut { name: string; description: string; permissions: string[]; input_schema: Record<string, string>; output_schema: Record<string, string> }`. Independent of every other task.

- [ ] **Step 1: Write the failing test**

```typescript
describe("AI Tools section", () => {
  it("lists available AI tools read-only", async () => {
    vi.mocked(api.listAiTools).mockResolvedValue([
      { name: "web_search", description: "Searches the web", permissions: [], input_schema: {}, output_schema: {} },
    ]);
    render(<Settings />);
    expect(await screen.findByText("web_search")).toBeInTheDocument();
    expect(screen.getByText("Searches the web")).toBeInTheDocument();
  });
});
```

Add `listAiTools: vi.fn()` to the `vi.mock("../lib/api", ...)` block.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx -t "AI Tools section"`
Expected: FAIL — `api.listAiTools` is not a function.

- [ ] **Step 3: Add the API client function**

In `apps/web/src/lib/api.ts`:

```typescript
export interface ToolOut {
  name: string;
  description: string;
  permissions: string[];
  input_schema: Record<string, string>;
  output_schema: Record<string, string>;
}

export function listAiTools(): Promise<ToolOut[]> {
  return request<ToolOut[]>("/tools");
}
```

- [ ] **Step 4: Add the `AiToolsSection` component to `Settings.tsx`**

```typescript
function AiToolsSection() {
  const { t } = useTranslation();
  const [tools, setTools] = useState<ToolOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listAiTools()
      .then(setTools)
      .catch((err) => setError(err instanceof ApiError ? err.message : t("settings.aiToolsLoadError")));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- run once on mount
  }, []);

  return (
    <Card className="flex max-w-md flex-col gap-3">
      <h2 className="text-lg font-semibold text-ink">{t("settings.aiToolsTitle")}</h2>
      <p className="text-xs text-ink-3">{t("settings.aiToolsHint")}</p>
      {error && (
        <Alert variant="danger" title={t("settings.aiToolsLoadError")}>
          {error}
        </Alert>
      )}
      {!tools ? (
        <SkeletonLines />
      ) : tools.length === 0 ? (
        <EmptyState message={t("settings.aiToolsEmpty")} />
      ) : (
        tools.map((tool) => (
          <div key={tool.name} className="rounded-xl border border-edge p-3">
            <p className="text-sm font-medium text-ink">{tool.name}</p>
            <p className="text-xs text-ink-3">{tool.description}</p>
          </div>
        ))
      )}
    </Card>
  );
}
```

Add `listAiTools, type ToolOut` to the existing `from "../lib/api"` import in `Settings.tsx`. Insert `<AiToolsSection />` directly after `<MemoriesSection />`.

- [ ] **Step 5: Add translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside `"settings": { ... }`, add:

```json
    "aiToolsTitle": "What the AI can do",
    "aiToolsHint": "Tools the assistant can currently use, for transparency.",
    "aiToolsEmpty": "No tools registered.",
    "aiToolsLoadError": "Couldn't load the tool list.",
```

In `apps/web/src/locales/nl.json`:

```json
    "aiToolsTitle": "Wat de AI kan doen",
    "aiToolsHint": "Tools die de assistent momenteel kan gebruiken, ter transparantie.",
    "aiToolsEmpty": "Geen tools geregistreerd.",
    "aiToolsLoadError": "Kon de toolslijst niet laden.",
```

In `apps/web/src/locales/de.json`:

```json
    "aiToolsTitle": "Was die KI tun kann",
    "aiToolsHint": "Werkzeuge, die der Assistent derzeit nutzen kann, zur Transparenz.",
    "aiToolsEmpty": "Keine Werkzeuge registriert.",
    "aiToolsLoadError": "Werkzeugliste konnte nicht geladen werden.",
```

- [ ] **Step 6: Run test to verify it passes, then full suite**

Run: `cd apps/web && npx vitest run src/routes/Settings.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/routes/Settings.tsx apps/web/src/routes/Settings.test.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "feat(settings): AI Tools transparency section (real backend, read-only)"
```

---

### Task 10: Fix PDF preview blob-URL failure (same-tab navigation)

**Files:**
- Modify: `apps/web/src/lib/api.ts:810-815`
- Test: `apps/web/src/lib/api.test.ts` (existing file — check with `find apps/web/src/lib -iname "api.test.ts"`; create if absent)

**Interfaces:** Changes `previewDocumentFile`'s internal behavior only — same exported signature `(id: string) => Promise<void>`. Independent of every other task.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/lib/api.test.ts` (create the file if it doesn't exist, with this content plus whatever existing tests are already there — check first):

```typescript
import { describe, expect, it, vi, beforeEach } from "vitest";
import { previewDocumentFile } from "./api";

describe("previewDocumentFile", () => {
  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      blob: () => Promise.resolve(new Blob(["pdf-bytes"], { type: "application/pdf" })),
    });
    global.URL.createObjectURL = vi.fn().mockReturnValue("blob:http://localhost/abc");
    global.URL.revokeObjectURL = vi.fn();
  });

  it("navigates the current window to the blob URL instead of opening a new tab", async () => {
    const assignSpy = vi.fn();
    Object.defineProperty(window, "location", { value: { assign: assignSpy }, writable: true });
    await previewDocumentFile("doc-1");
    expect(assignSpy).toHaveBeenCalledWith("blob:http://localhost/abc");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/lib/api.test.ts -t "previewDocumentFile"`
Expected: FAIL — current implementation calls `window.open`, not `window.location.assign`.

- [ ] **Step 3: Fix `previewDocumentFile`**

In `apps/web/src/lib/api.ts`, replace:

```typescript
export async function previewDocumentFile(id: string): Promise<void> {
  const blob = await fetchDocumentFileBlob(id, "inline");
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
```

with:

```typescript
export async function previewDocumentFile(id: string): Promise<void> {
  const blob = await fetchDocumentFileBlob(id, "inline");
  const url = URL.createObjectURL(blob);
  // Navigate the current tab rather than window.open(url, "_blank") -- blob: URLs
  // don't reliably survive the handoff to a newly opened browsing context on
  // mobile Safari/iOS (a documented WebKit limitation), which surfaced as
  // "Unexpected server response (0)" in the native PDF viewer.
  window.location.assign(url);
}
```

Note: the `setTimeout(() => URL.revokeObjectURL(url), 60_000)` is removed — since the current tab now navigates away to the blob URL, there is no later JS context left to run the revoke; the browser reclaims the blob when the tab/document unloads.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd apps/web && npx vitest run src/lib/api.test.ts`
Expected: PASS

- [ ] **Step 5: Run the full suite to check for regressions**

Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/lib/api.test.ts
git commit -m "fix(documents): navigate same tab for PDF preview instead of window.open(blob:)

Fixes 'Unexpected server response (0)' on mobile Safari/iOS -- blob:
URLs don't reliably survive the handoff to a new browsing context."
```

---

### Task 11: Fix `taskUrgency.ts` — never render Invalid Date or an unbounded overdue count

**Files:**
- Modify: `apps/web/src/lib/taskUrgency.ts`
- Modify: `apps/web/src/lib/taskUrgency.test.ts` (existing file — check with `find apps/web/src/lib -iname "taskUrgency.test.ts"`; create if absent)
- Modify: `apps/web/src/routes/Tasks.tsx`
- Locale: `apps/web/src/locales/en.json`, `nl.json`, `de.json`

**Interfaces:**
- Produces: `taskUrgency(dueDate: string | null | undefined): TaskUrgency` (now accepts null/undefined/malformed input); `TaskUrgency` gains `variant: "danger" | "warning" | "default" | "unknown"` and `overdueDays: number | null`; `relativeDueLabel` handles the new `"unknown"` variant and stops showing a raw day-count past 365 days overdue, showing the absolute date instead. Independent of every other task (Task 13's Tasks-list polish builds visually on top of this, so run this one first if sequencing serially).

- [ ] **Step 1: Write the failing tests**

Create/add to `apps/web/src/lib/taskUrgency.test.ts`:

```typescript
import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { taskUrgency, relativeDueLabel } from "./taskUrgency";

describe("taskUrgency", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-07-24T00:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("returns 'unknown' for a missing due date instead of crashing", () => {
    expect(taskUrgency(null).variant).toBe("unknown");
    expect(taskUrgency(undefined).variant).toBe("unknown");
    expect(taskUrgency("").variant).toBe("unknown");
  });

  it("returns 'unknown' for an unparseable due date instead of NaN", () => {
    expect(taskUrgency("not-a-date").variant).toBe("unknown");
  });

  it("computes overdueDays correctly for a genuinely old valid date", () => {
    const result = taskUrgency("2019-04-09");
    expect(result.variant).toBe("danger");
    expect(result.overdueDays).toBeGreaterThan(2000);
  });

  it("relativeDueLabel shows 'No date on file' for missing/invalid dates", () => {
    const t = (key: string) => ({ "tasks.dueUnknown": "No date on file" }[key] ?? key);
    expect(relativeDueLabel(null, t, (d) => d)).toBe("No date on file");
    expect(relativeDueLabel("garbage", t, (d) => d)).toBe("No date on file");
  });

  it("relativeDueLabel shows the absolute date, not a raw day count, past 365 days overdue", () => {
    const t = (key: string, opts?: Record<string, unknown>) =>
      key === "tasks.dueOverdueSince" ? `Overdue since ${opts?.date}` : key;
    const formatDate = (d: string) => "9 Apr 2019";
    expect(relativeDueLabel("2019-04-09", t, formatDate)).toBe("Overdue since 9 Apr 2019");
  });
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd apps/web && npx vitest run src/lib/taskUrgency.test.ts`
Expected: FAIL — current `taskUrgency` signature is `(dueDate: string)`, no `"unknown"` variant, no `null`/`undefined` handling, no 365-day cap.

- [ ] **Step 3: Rewrite `taskUrgency.ts`**

Replace the entire file content with:

```typescript
export type UrgencyVariant = "danger" | "warning" | "default" | "unknown";

export interface TaskUrgency {
  variant: UrgencyVariant;
  overdueDays: number | null;
}

const OVERDUE_DAYS_ABSOLUTE_CUTOFF = 365;

function isValidDateString(value: string): boolean {
  return !Number.isNaN(new Date(value).getTime());
}

export function taskUrgency(dueDate: string | null | undefined): TaskUrgency {
  if (!dueDate || !isValidDateString(dueDate)) {
    return { variant: "unknown", overdueDays: null };
  }
  const today = new Date().toISOString().slice(0, 10);
  if (dueDate < today) {
    const days = Math.round((new Date(today).getTime() - new Date(dueDate).getTime()) / 86400000);
    return { variant: "danger", overdueDays: days };
  }
  if (dueDate === today) {
    return { variant: "warning", overdueDays: null };
  }
  return { variant: "default", overdueDays: null };
}

export function daysUntil(dueDate: string): number {
  const today = new Date().toISOString().slice(0, 10);
  return Math.round((new Date(dueDate).getTime() - new Date(today).getTime()) / 86400000);
}

export function relativeDueLabel(
  dueDate: string | null | undefined,
  t: (key: string, opts?: Record<string, unknown>) => string,
  formatDate: (value: string) => string,
): string {
  const urgency = taskUrgency(dueDate);
  if (urgency.variant === "unknown") return t("tasks.dueUnknown");
  if (urgency.variant === "danger") {
    if (urgency.overdueDays !== null && urgency.overdueDays > OVERDUE_DAYS_ABSOLUTE_CUTOFF) {
      return t("tasks.dueOverdueSince", { date: formatDate(dueDate as string) });
    }
    return t("tasks.dueOverdue", { count: urgency.overdueDays });
  }
  if (urgency.variant === "warning") return t("tasks.dueToday");
  const days = daysUntil(dueDate as string);
  if (days === 1) return t("tasks.dueTomorrow");
  if (days <= 7) return t("tasks.dueInDays", { count: days });
  return t("tasks.due", { date: formatDate(dueDate as string) });
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd apps/web && npx vitest run src/lib/taskUrgency.test.ts`
Expected: PASS

- [ ] **Step 5: Update `Tasks.tsx` call sites for the new nullable signature and `"unknown"` variant**

In `apps/web/src/routes/Tasks.tsx`, the badge-building block currently reads:

```typescript
            const badge = task.due_date
              ? { variant: taskUrgency(task.due_date).variant, label: relativeDueLabel(task.due_date, t, formatDate) }
              : null;
```

This still works unchanged (it already guards on `task.due_date` truthiness before calling), but the border-color lookup does NOT currently have an `"unknown"` branch and will need one once `taskUrgency` can return it for appointment-type tasks with a due date field that's present but unparseable. Replace:

```typescript
                className={`flex cursor-pointer items-start gap-3 border-l-2 px-4 py-3 ${
                  task.due_date && task.status !== "done"
                    ? { danger: "border-l-danger", warning: "border-l-warning", default: "border-l-transparent" }[taskUrgency(task.due_date).variant]
                    : "border-l-transparent"
                }`}
```

with:

```typescript
                className={`flex cursor-pointer items-start gap-3 border-l-2 px-4 py-3 ${
                  task.due_date && task.status !== "done"
                    ? {
                        danger: "border-l-danger",
                        warning: "border-l-warning",
                        default: "border-l-transparent",
                        unknown: "border-l-transparent",
                      }[taskUrgency(task.due_date).variant]
                    : "border-l-transparent"
                }`}
```

- [ ] **Step 6: Add the 2 new translation keys to all 3 locales**

In `apps/web/src/locales/en.json`, inside `"tasks": { ... }`, add:

```json
    "dueUnknown": "No date on file",
    "dueOverdueSince": "Overdue since {{date}}",
```

In `apps/web/src/locales/nl.json`:

```json
    "dueUnknown": "Geen datum bekend",
    "dueOverdueSince": "Verlopen sinds {{date}}",
```

In `apps/web/src/locales/de.json`:

```json
    "dueUnknown": "Kein Datum hinterlegt",
    "dueOverdueSince": "Überfällig seit {{date}}",
```

- [ ] **Step 7: Run the full frontend suite to check for regressions**

Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add apps/web/src/lib/taskUrgency.ts apps/web/src/lib/taskUrgency.test.ts apps/web/src/routes/Tasks.tsx apps/web/src/locales/en.json apps/web/src/locales/nl.json apps/web/src/locales/de.json
git commit -m "fix(tasks): never render Invalid Date or an unbounded overdue-day count

taskUrgency() now returns 'unknown' for missing/unparseable due dates
instead of propagating NaN, and dates over 365 days overdue show the
absolute date instead of an alarming raw day count."
```

---

### Task 12: Visual polish — Tasks list

**Files:**
- Modify: `apps/web/src/routes/Tasks.tsx`
- Modify: `apps/web/src/routes/Tasks.test.tsx`

**Interfaces:** Depends on Task 11's `taskUrgency`/`relativeDueLabel` signatures (already merged if run in order) — purely visual/structural, no new exports.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/Tasks.test.tsx` (adjust existing mocked task fixtures as needed to match the file's established fixture style):

```typescript
it("shows 'No date on file' for a task with no due date, not a blank space", async () => {
  vi.mocked(api.listTasks).mockResolvedValue([
    { id: "t1", title: "Vaderschapsherkenning", status: "open", due_date: null, description: null, assignee: null, document_id: null, recurrence_rule: null },
  ]);
  render(<Tasks />);
  expect(await screen.findByText("No date on file")).not.toBeInTheDocument();
});
```

Wait — the current code path only renders a badge `if (task.due_date)`, so a null due_date currently shows NOTHING, not "No date on file". Decide and encode the actual desired behavior: since Task 11 established "No date on file" as the friendly label for a missing/invalid date, Tasks.tsx's badge-gating condition must change from `task.due_date ? ... : null` to always compute the badge. Replace the test above with:

```typescript
it("shows 'No date on file' for a task with no due date, not a blank space", async () => {
  vi.mocked(api.listTasks).mockResolvedValue([
    { id: "t1", title: "Vaderschapsherkenning", status: "open", due_date: null, description: null, assignee: null, document_id: null, recurrence_rule: null },
  ]);
  render(<Tasks />);
  expect(await screen.findByText("No date on file")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Tasks.test.tsx -t "No date on file"`
Expected: FAIL — no badge renders today when `due_date` is null.

- [ ] **Step 3: Always compute the badge (real behavior change, matches Task 11's new "unknown" variant)**

In `apps/web/src/routes/Tasks.tsx`, replace:

```typescript
            const badge = task.due_date
              ? { variant: taskUrgency(task.due_date).variant, label: relativeDueLabel(task.due_date, t, formatDate) }
              : null;
```

with:

```typescript
            const badge = { variant: taskUrgency(task.due_date).variant, label: relativeDueLabel(task.due_date, t, formatDate) };
```

(`taskUrgency`/`relativeDueLabel` from Task 11 already accept `null`/`undefined` and return the `"unknown"` variant + "No date on file" label, so this is now safe.)

Find the badge-rendering line:

```typescript
                    {badge && <Badge variant={badge.variant}>{badge.label}</Badge>}
```

Replace with:

```typescript
                    <Badge variant={badge.variant === "unknown" ? "default" : badge.variant}>{badge.label}</Badge>
```

(`Badge`'s `variant` prop only accepts `"default" | "success" | "warning" | "danger"` — map `"unknown"` to `"default"` at the render boundary rather than widening the shared `Badge` component's type.)

- [ ] **Step 4: Run test to verify it passes, then full suite**

Run: `cd apps/web && npx vitest run src/routes/Tasks.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/Tasks.tsx apps/web/src/routes/Tasks.test.tsx
git commit -m "polish(tasks): always show a due-date badge, including 'No date on file'"
```

---

### Task 13: Visual polish — Document Detail metadata grouping

**Files:**
- Modify: `apps/web/src/components/DocumentDetailContent.tsx`
- Modify: `apps/web/src/components/DocumentDetailContent.test.tsx`

**Interfaces:** Purely structural/visual — no prop or export changes. Independent of every other task.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/components/DocumentDetailContent.test.tsx`:

```typescript
it("groups classification and extracted-field metadata into separate labeled cards", () => {
  render(<DocumentDetailContent doc={baseDoc} onChanged={() => {}} />);
  expect(screen.getAllByTestId("doc-detail-section-card")).toHaveLength(2);
});
```

(Use whatever `baseDoc` fixture the existing test file already defines — check the top of `DocumentDetailContent.test.tsx` for its shape before writing this.)

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/components/DocumentDetailContent.test.tsx -t "groups classification"`
Expected: FAIL — no `doc-detail-section-card` testid exists yet.

- [ ] **Step 3: Wrap the classification and metafields sections in labeled `Card`s**

In `apps/web/src/components/DocumentDetailContent.tsx`, find the classification block (starts around line 177 with `<h2 className="text-sm font-medium text-ink-2">{t("documentDetail.classification")}</h2>`) and wrap its containing `<div>` in a `Card`:

```typescript
        <div data-testid="doc-detail-section-card">
          <Card className="flex flex-col gap-2">
            <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.classification")}</h2>
            {/* ...existing tags/correspondent content unchanged... */}
          </Card>
        </div>
```

Find the metafields block (starts around line 208 with `<h2 className="text-sm font-medium text-ink-2">{t("documentDetail.metafields")}</h2>`) and wrap it the same way:

```typescript
        <div data-testid="doc-detail-section-card">
          <Card className="flex flex-col gap-2">
            <h2 className="text-sm font-medium text-ink-2">{t("documentDetail.metafields")}</h2>
            {/* ...existing metafield rows unchanged... */}
          </Card>
        </div>
```

Add `import Card from "./Card";` to the top of the file if not already imported (check first — it likely isn't, since this file currently renders these sections as bare `<div>`s).

- [ ] **Step 4: Run test to verify it passes, then full suite**

Run: `cd apps/web && npx vitest run src/components/DocumentDetailContent.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/components/DocumentDetailContent.tsx apps/web/src/components/DocumentDetailContent.test.tsx
git commit -m "polish(documents): group Document Detail metadata into labeled cards"
```

---

### Task 14: Visual polish — Documents list consistency pass

**Files:**
- Modify: `apps/web/src/routes/Workspace.tsx`
- Modify: `apps/web/src/routes/Workspace.test.tsx`

**Interfaces:** Purely structural/visual (spacing/consistency only) — no prop or export changes. Independent of every other task.

- [ ] **Step 1: Write the failing test**

Add to `apps/web/src/routes/Workspace.test.tsx`:

```typescript
it("wraps the filter row in a Card for visual consistency with the search row", () => {
  vi.mocked(api.listDocuments).mockResolvedValue([]);
  render(<Workspace />);
  expect(screen.getByTestId("documents-filter-card")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd apps/web && npx vitest run src/routes/Workspace.test.tsx -t "filter row"`
Expected: FAIL — no `documents-filter-card` testid exists yet.

- [ ] **Step 3: Wrap the filter row in a `Card`**

In `apps/web/src/routes/Workspace.tsx`, find the filter-chips row (around line 251, `<div className="flex flex-wrap gap-2">` following the search `<form>`) and wrap it:

```typescript
        <div data-testid="documents-filter-card">
          <Card className="flex flex-wrap gap-2 !p-3">
            {/* ...existing filter-chip content unchanged... */}
          </Card>
        </div>
```

Add `import Card from "../components/Card";` to the top of the file if not already imported (check first).

- [ ] **Step 4: Run test to verify it passes, then full suite**

Run: `cd apps/web && npx vitest run src/routes/Workspace.test.tsx`
Expected: PASS
Run: `cd apps/web && npx vitest run`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/Workspace.tsx apps/web/src/routes/Workspace.test.tsx
git commit -m "polish(documents): wrap filter row in a Card for visual consistency"
```

---

### Task 15: Push, open PR, merge, deploy to production, and verify with Playwright as a real user

**Files:** None modified — this task is CI/deploy/verification only.

**Interfaces:** N/A — final integration task, depends on all prior tasks being committed on `feat/ux-redesign-phase1`.

- [ ] **Step 1: Run the complete frontend and backend test suites one more time locally**

Run: `cd apps/web && npx vitest run`
Expected: PASS, full suite, zero regressions vs. the pre-task-1 baseline count.
Run: `cd services/api && python -m pytest` (backend untouched by this plan, but confirm nothing broke)
Expected: PASS.

- [ ] **Step 2: Push the branch and open a PR**

```bash
git push -u origin feat/ux-redesign-phase1
gh pr create --title "Phase 1 UX redesign: grouped nav, AI knowledge pages, 2 bug fixes, busiest-page polish" --body "$(cat <<'EOF'
## Summary
- Groups main nav (Overview/Records/Planning/AI Tools/Account) and Admin tabs (Users/Monitoring/Feedback/Communication), no route changes.
- Surfaces two fully-working backends with no prior frontend: Facts (approve/reject) and Memories (list/forget) under a new Settings "AI & Knowledge" area, plus a read-only AI Tools list.
- Adds 3 dry admin placeholders (Support Tickets, Email Templates, Product Analytics) and 1 dry Settings placeholder (Notification Preferences) -- visible, no backend calls.
- Fixes 2 traced bugs: PDF preview blob:// failure on mobile Safari (same-tab navigation instead of window.open), and taskUrgency.ts's Invalid Date / unbounded overdue-day-count bug.
- Visual polish (Violet DS only, no new components) on Documents list, Document Detail, and Tasks list.

## Test plan
- [ ] Full vitest suite passes
- [ ] Full pytest suite passes (untouched, sanity check)
- [ ] CI green
- [ ] Post-merge: deployed to collabrains.eu and verified end-to-end with Playwright as a real user

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Wait for CI, then merge**

```bash
gh pr checks --watch
gh pr merge --squash
```

If CI fails on anything, fix it on the branch, commit, push, and re-check before merging — do not merge red CI.

- [ ] **Step 4: Deploy to the live server**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && git pull origin main && docker compose build web && docker compose up -d web"
```

Confirm the container is healthy:

```bash
ssh root@178.254.22.178 "docker compose ps web && curl -sI https://collabrains.eu | head -1"
```

Expected: `web` service `Up`/healthy, `curl` returns `HTTP/2 200`.

- [ ] **Step 5: Real-user-POV Playwright verification against production**

Create a disposable admin test user first (same discipline as every prior live-verification pass in this project — via the existing admin user-creation flow, not a raw DB insert), then run this script and delete the test user afterward regardless of outcome.

Write `apps/e2e/phase1-verification.spec.ts`:

```typescript
import { test, expect } from "@playwright/test";

test.describe("Phase 1 UX redesign — live verification", () => {
  test("grouped navigation reaches every existing page", async ({ page }) => {
    await page.goto("https://collabrains.eu/login");
    await page.fill('input[name="username"]', process.env.PHASE1_TEST_USER!);
    await page.fill('input[name="password"]', process.env.PHASE1_TEST_PASSWORD!);
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL("https://collabrains.eu/");

    for (const path of ["/documents", "/entities", "/cases", "/vehicles", "/tasks", "/calendar", "/chat", "/legal", "/assistant", "/settings"]) {
      await page.goto(`https://collabrains.eu${path}`);
      await expect(page.locator("body")).not.toContainText("Unexpected server response");
      await expect(page.locator("body")).not.toContainText("Invalid Date");
    }
  });

  test("Settings shows Facts, Memories, and AI Tools sections without errors", async ({ page }) => {
    await page.goto("https://collabrains.eu/settings");
    await expect(page.getByText("What the AI knows about you")).toBeVisible();
    await expect(page.getByText("What the AI remembers")).toBeVisible();
    await expect(page.getByText("What the AI can do")).toBeVisible();
    await expect(page.locator('[role="alert"]')).toHaveCount(0);
  });

  test("Admin shows grouped tabs including the 3 new stub areas", async ({ page }) => {
    await page.goto("https://collabrains.eu/admin");
    await page.getByRole("tab", { name: "Support Tickets" }).click();
    await expect(page.getByText("No support tickets yet")).toBeVisible();
    await page.getByRole("tab", { name: "Email Templates" }).click();
    await expect(page.getByRole("button", { name: "Send test" })).toBeDisabled();
    await page.getByRole("tab", { name: "Product Analytics" }).click();
    await expect(page.getByText("—").first()).toBeVisible();
  });

  test("Document preview navigates the same tab instead of opening a blank one", async ({ page, context }) => {
    await page.goto("https://collabrains.eu/documents");
    const [popup] = await Promise.all([
      context.waitForEvent("page", { timeout: 3000 }).catch(() => null),
      page.getByRole("button", { name: /preview/i }).first().click(),
    ]);
    expect(popup).toBeNull();
  });
});
```

Run: `cd apps/e2e && PHASE1_TEST_USER=<disposable-user> PHASE1_TEST_PASSWORD=<its-password> npx playwright test phase1-verification.spec.ts --project=chromium`
Expected: all 4 tests PASS against the live site.

- [ ] **Step 6: Clean up the disposable test user and the verification spec**

Delete the disposable admin test user through the Admin Users tab (same as every prior live-verification pass), and remove the throwaway spec file since it's a one-off production smoke check, not a permanent addition to the e2e suite:

```bash
git rm apps/e2e/phase1-verification.spec.ts
git commit -m "chore: remove one-off Phase 1 production verification spec"
git push
```

- [ ] **Step 7: Report results**

Summarize: CI status, deploy confirmation (container healthy, `curl` 200), the 4 Playwright checks' pass/fail results, and explicitly call out anything that failed and was NOT auto-fixed (do not claim success on anything not actually observed passing). This is the point where the user plans their first release.
