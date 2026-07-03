# ADR 0016: Phase 7 — Mobile App Foundation (React Native / Expo)

## Status
Accepted

## Context
`apps/mobile` has existed as an empty stub directory since Phase 0.
README.md has named "Mobile" as an eventual client alongside Web/Admin/
Signal since the start, but nothing was ever designed for it. This ADR
covers the first mobile phase: a read-mostly companion app for
reviewing case information on the go, not a rebuild of the full web
app's feature set.

Scope was narrowed deliberately through discussion before any design
work started: the mobile app covers document browsing/search, AI chat,
tasks, and the entity graph. It explicitly does **not** cover document
upload or Legal Draft — upload needs camera/file-picker integration
that's a meaningfully separate chunk of work, and drafting a legal
document isn't a good fit for a phone keyboard. Both can be picked up
as a later phase if a real need shows up; nothing here forecloses them.

## Decisions

**Framework: React Native via Expo**, not Flutter or native
iOS+Android. Reuses the existing TypeScript API client and auth logic
from `apps/web` almost as-is (same request/response shapes, same
`ApiError` pattern), and Expo solves a real constraint this project has
had since day one: there is no Mac/Xcode reachable from the Linux server
everything else has been built on. Expo's dev loop (`npx expo start` +
the Expo Go app on a physical phone) and cloud builds (EAS Build) mean
mobile development doesn't need to break the "build everything on the
server" pattern the way native iOS development structurally would.

**Distribution: testable build only for this phase**, not App
Store/Play Store submission. Store distribution needs the user's own
Apple Developer and Google Play accounts (payment, identity
verification) — not something obtainable on their behalf — and is a
separable later step once the app itself is proven out.

**Navigation: Expo Router** (file-based routing) over React Navigation.
Less boilerplate for a handful of screens, and it's the framework's own
current default direction for new Expo apps, versus React Navigation's
more manual stack/tab-navigator setup.

**Project structure** (`apps/mobile/`):

```
app/                          # Expo Router screens (file-based)
  _layout.tsx                  # Root layout: AuthProvider, theme
  login.tsx
  (tabs)/
    _layout.tsx                 # Bottom tab bar: Documents | Chat | Tasks | Entities
    index.tsx                    # Document list
    chat.tsx
    tasks.tsx
    entities/index.tsx           # Entity list
  documents/[id].tsx            # Document detail
  entities/[id].tsx             # Entity graph
src/
  lib/
    api.ts                      # Ported fetch client, SecureStore-backed token
    auth.tsx                     # AuthContext + useAuth
  components/
    EntityGraph.tsx              # react-native-svg radial layout
```

Mirrors `apps/web`'s shape closely on purpose — `lib/api.ts`,
`lib/auth.tsx`, one file per screen — so the existing web app is a
working reference for anyone touching mobile code.

**Screens** (chat and task-status toggling are genuine write actions and
are included; document upload, manual summarize, and Legal Draft are
the write actions excluded from this phase per the Context above):

- `login.tsx` — same LDAP-backed `POST /auth/token` as web; JWT stored
  in `expo-secure-store` (encrypted, keychain-backed) rather than
  `localStorage`.
- Document list — `GET /documents`, pull-to-refresh (not web's 5s
  polling interval — a phone screen isn't left open and stared at the
  way a browser tab is, so refresh-on-demand is the better default
  here), search bar (`GET /search`).
- Document detail — `GET /documents/{id}`: title, status, summary (if
  already generated — no "Summarize" trigger button in v1, since that's
  a write action), OCR text.
- Chat — ports web's `Chat.tsx` behavior exactly: full visible history
  sent every turn (backend is stateless per ADR 0003), citations as
  tappable links to document detail.
- Tasks — ports web's `Tasks.tsx`: open/done/all filter, tap-to-toggle
  (`PATCH /tasks/{id}`), tap a task's source document to navigate there.
- Entity list — `GET /entities`, search + type filter, same as web.
- Entity graph — `GET /entities/{id}/graph` via `react-native-svg`
  (`Svg`/`Circle`/`Line`/`Text`/`G`, a near-1:1 match to web SVG
  elements): same radial layout math, same type-based coloring, tap a
  neighbor to re-center. The web version's Phase 5c click-target fix
  (a transparent hit-target `<rect>` behind each node+label, since SVG
  hit-testing is per-painted-shape, not per-bounding-box) is built in
  from the start here rather than re-discovered — touch targets are
  coarser than a mouse cursor, so the same gap-between-shapes problem is
  if anything more likely on mobile, not less.

**API client**: a new `apps/mobile/src/lib/api.ts`, *ported from*, not
*shared with*, the web version. `packages/` (this monorepo's shared-code
workspace) has stayed unused stub directories through every phase so
far; ~200 lines of fetch wrapper duplicated once is well inside "three
similar lines beats a premature abstraction," especially since React
Native's networking has small platform differences from browser
`fetch` (notably around `FormData`, though that only matters if/when
upload is added later) that would likely need branches in a shared
version anyway. Same `request()` logic (including the Phase 5a fix:
only default `Content-Type: application/json` when the caller hasn't
set one), same `ApiError` class, same typed function set minus
upload/summarize/legal-draft.

**Backend connection**: hardcoded to `https://v78281.1blu.de` — no
dev-server-vs-production env-var split needed the way the web app has
one (`VITE_API_URL`), since a phone has no equivalent of "the Vite dev
server on localhost." Phase 6a's public HTTPS setup is what makes this
straightforward: the phone reaches the real deployed backend directly,
no tunnel, no CORS concerns (native apps don't enforce browser CORS).

**No client-side caching layer** (no React Query/SWR/Redux) — plain
`useState`+`useEffect` per screen, same as the web app already does
throughout, with pull-to-refresh covering the "get fresh data"
explicitly rather than a caching library's implicit revalidation.

**Error handling**: same pattern as web — each screen owns its own
loading/error state, `ApiError` messages shown inline, no global error
boundary or toast system. A 401 from any call clears the stored token
and routes to `login.tsx`.

**Testing**: `vitest` unit tests for `lib/api.ts`'s `request()` logic,
ported near-verbatim from web's existing suite (same logic, same
regression coverage for the Content-Type bug). No component/UI test
framework — web never added one either; real verification there was
always live testing against the running backend, and the mobile
equivalent is the same discipline applied to an actual device/simulator
build rather than Playwright, which has no mobile equivalent here.

## Why not more
Document upload and Legal Draft are excluded from this phase (see
Context) — not because they're hard, but because they're separable
scope with their own design questions (camera/file-picker permissions
for upload; whether a phone keyboard is even the right interface for
drafting) that don't need to be answered to ship the read-mostly core.
No offline support — online-only, same as web, and nobody's stated an
actual need for it yet. No push notifications in this phase, even
though Tasks/Chat would be natural candidates — notification delivery
is its own infrastructure question (Expo push tokens, a server-side
sender) better scoped separately once the base app exists to attach it
to.
