# Navbar Navigation Redesign — Design

**Source:** Artifact `1c78098b-3003-4eed-94ef-fd7ec38bd363` ("CollaBrains — Violet Design Language",
owned by this account). Read directly (saved HTML/CSS/JS, not browsed) since it's a static/interactive
component showcase, not a live app. Cross-checked against the current app: **every component the
artifact catalogs already exists** in `apps/web/src/components/ui/` (Alert, Avatar, Badge, Breadcrumbs,
BulkActionBar, Button, CalendarGrid, Combobox, CommandPalette, DataTable, Drawer, Dropdown, FilterChips,
InlineEditableText, KanbanBoard, MetadataList, Modal, ShortcutsSheet, Skeleton, SplitView, StatusPipeline,
Stepper, Tooltip, form.tsx) and the same violet token palette is already wired into `tailwind.config` (`bg-page`,
`text-ink`, `border-edge`, `bg-accent-soft`, `shadow-raised/overlay/modal`, `duration-fast/base/slow`,
`ease-spring`, etc.) — the artifact is a reference/catalog of a design language the app has already
adopted piece by piece, not a new design.

**The actual gap** — and the user's explicit ask — is architectural: the app still navigates via a fixed
left `Sidebar` on desktop. This redesign replaces it with a top navbar, makes layout fully responsive
now that no column is reserved for a sidebar, and confirms forms already match the target language.

## Scope

1. **Desktop navigation**: replace `Sidebar.tsx` with a sticky top `Navbar` (glass-surface, matching the
   blur treatment already used on Login/Onboard/Chat).
2. **Mobile navigation**: keep the existing bottom `MobileTabBar` (already a good, already-responsive
   pattern) and the existing avatar→/settings shortcut; replace the hamburger's target (currently opens
   `Sidebar` as a slide-in drawer) with a new lightweight `MobileNavDrawer` listing every nav item, since
   `Sidebar` itself is deleted.
3. **Forms**: audited `form.tsx` (TextField/Select/Checkbox/Switch) against the artifact's `.field`/`.switch`
   patterns — already matches (labeled, focus ring via `ring-accent-soft`, error state, spring-animated
   switch). No rework needed; out of scope beyond this confirmation.
4. **Responsive**: with the sidebar's reserved column gone, `<main>` becomes full-width; add a max-width
   cap (`max-w-screen-2xl`, centered) so content doesn't over-stretch on ultra-wide desktops.

## Navbar content decisions (judgment calls, not asked — reversible UI grouping)

- **Primary nav** (always visible, pill-highlighted, matches mobile tab bar's priorities plus AI Chat as
  the flagship feature from this session's redesign work): Dashboard, Documents, Cases, Tasks, Chat.
- **Secondary nav** (under a "More" `Dropdown`): Calendar, Legal Draft, Entities, Vehicles, Assistant.
- **Account cluster** (right side, unchanged responsibilities, moved out of the nav-item list into a
  `Dropdown` behind the `Avatar`): Settings, Admin Dashboard (admin role only), Sign out. Search (⌘K),
  the alerts bell, and the dark-mode toggle stay as their own icon buttons (frequent, single-tap actions
  — burying them in a menu would be a regression).
- `Sidebar.tsx`, `Sidebar.test.tsx`, `useSidebarCollapsed.ts` (+ test) are deleted — nothing else
  references them (`grep` confirmed). `common.expandSidebar`/`collapseSidebar` i18n keys are removed from
  all three locale files (en/de/nl); `common.more` is added to all three.

## Testing & rollout

Frontend-only change (no backend/API touched). Baseline: 520/520 tests passing before starting. Build and
test locally (`npm run build`, `npx vitest run`) before pushing; only push/deploy once green, per the
"local first" requirement for this session's poor-connectivity constraint.
