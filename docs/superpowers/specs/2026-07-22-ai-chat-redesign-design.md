# AI Chat Redesign — Design Spec

**Sub-project 4 of the CollaBrains premium-SaaS redesign** (design system+sidebar,
dashboard+activity-timeline, documents metafields+UI, and calendar auto-sync already
shipped). Brings the visual/layout language established in sub-project 1 (design
tokens: `glass-surface`, `bg-gradient-brand`, `rounded-ds-*`) to the two AI
interaction surfaces, `/chat` and `/assistant`.

## Background

`Chat.tsx` (`/chat`, RAG Q&A with document citations + thumbs up/down feedback) and
`Assistant.tsx` (`/assistant`, Manager Agent with tool-calling) are near-identical in
structure: a single-line input, a submit button, and a shared `ChatLog` component
(`components/ui/ChatLog.tsx`) rendering turns as speech-bubble-style messages inside a
`max-h-[420px] overflow-y-auto` box. `ChatLog` itself is already reasonably
functional (asymmetric bubble corners, a bouncing-dots "thinking" indicator, a
low-confidence badge, thumbs up/down) but predates this session's design-token work
and reads as a small embedded widget rather than a dedicated page.

Address consolidation (originally the next item after calendar auto-sync) was
explicitly skipped — the user's actual address complaint was already resolved by
current's existing `AddressDetail` model, confirmed during the earlier documents
research, making that sub-project pure low-value internal cleanup right now.

## Scope

**In scope:**
1. Full-height chat layout for both `/chat` and `/assistant` (message log grows to
   fill available space with its own internal scroll, input pinned at the bottom),
   replacing the current 420px-capped box.
2. Apply this session's design tokens to `ChatLog` and both pages' chrome:
   `glass-surface` for assistant bubbles, `bg-gradient-brand` accenting user bubbles
   or the send button, `rounded-ds-*` radii, consistent header treatment matching
   Documents/Dashboard (breadcrumb-free `<h1>` header, consistent with existing
   pattern on those pages).
3. Replace the single-line `<input>` with an auto-resizing `<textarea>` (grows with
   content up to a max height, Enter submits / Shift+Enter newlines).

**Out of scope:**
- Conversation persistence / history sidebar — turns stay ephemeral (component
  state, lost on navigation), same as today. No new backend storage.
- Streaming responses — still a single blocking request/response per turn, same
  `chat()`/`askManager()` API calls, no backend changes at all. This sub-project is
  frontend-only.
- Merging `/chat` and `/assistant` into one route — they keep their distinct
  backends (`POST /chat` vs `POST /manager/ask`) and distinct footers (citations vs.
  tool-called badge); only the visual chrome becomes consistent between them.

## Architecture

No backend changes. Three frontend files:

- `components/ui/ChatLog.tsx`: restyle bubbles with design tokens, remove the
  `max-h-[420px]` cap in favor of the parent controlling scroll height, keep its
  existing props/behavior (citations footer, tool-called footer, confidence badge,
  feedback buttons) unchanged — this is a visual-only pass, not an API change, so
  `Chat.tsx`/`Assistant.tsx` keep constructing `ChatTurnDisplay[]` exactly as they do
  today.
- `Chat.tsx` / `Assistant.tsx`: restructure the page's root layout to
  `flex h-full flex-col`, wrap `ChatLog` in a `flex-1 overflow-y-auto` region, and
  replace the `<input>` with an auto-resizing `<textarea>` (a small new local
  component or inline handler — auto-resize via `scrollHeight` on each keystroke,
  capped at a max height with its own internal scroll beyond that).

## Testing

- `ChatLog.test.tsx` (if none exists yet, create one; confirm during planning):
  bubble rendering, confidence badge, feedback button behavior — should be minimal
  changes since props/behavior are unchanged, just class names.
- `Chat.test.tsx` / `Assistant.test.tsx`: existing tests should keep passing
  (structure/behavior unchanged); add a case for the textarea's Enter-submits/
  Shift+Enter-newlines behavior.
- Live-browser verification (per this session's established practice for visual
  work): temporarily override `useAuth()`, screenshot both `/chat` and `/assistant`
  at desktop and mobile widths, revert before finishing.

## Risks / open items for planning

- Exact auto-resize textarea implementation (a small reusable component vs. inline
  per-page logic) is a planning-time call — given both pages need it identically, a
  small shared component is likely cleanest, mirroring `ChatLog`'s existing
  shared-component pattern.
- Whether `ChatLog.test.tsx` already exists needs to be checked at plan-writing time
  (not confirmed during this brainstorm).
