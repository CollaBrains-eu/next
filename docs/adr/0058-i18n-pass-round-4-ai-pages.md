# 0058 — i18n pass round 4: Chat, Legal, Assistant

## Status

Accepted

## Context

Follow-on to ADR 0055/0056 (rounds 2-3). This round translates the
three AI-interaction pages — `Chat`, `Legal`, `Assistant` — chosen
ahead of the remaining admin/settings pages because they're used far
more by non-English-speaking end users day-to-day than admin-only
screens, and because the original migration request specifically
called out that both UI language and AI language must follow the
user's `preferred_language` setting. Same `t()` pattern, same
three-locale structure, three new namespaces
(`chat`/`legal`/`assistant`) plus two new shared `common` entries
(`send`, `thinking`) since "Send" and "Thinking…" are byte-identical
across `Chat.tsx` and `Assistant.tsx`.

## Decision

- **`Chat.tsx`**: title reuses `nav.aiChat`, hint text, input
  placeholder, load-error fallback, and the shared `common.send`/
  `common.thinking`.
- **`Legal.tsx`**: title reuses `nav.legalDraft`, description,
  drafting-instruction label, instruction placeholder, scope label,
  the Draft/Drafting… button states, and the load-error fallback.
- **`Assistant.tsx`**: title reuses `nav.assistant`, hint text, input
  placeholder, the `"via: {{tool}}"` tool-attribution line
  (interpolated — this is UI chrome around a tool name, not raw data,
  unlike the entity-type badges left untranslated in ADR 0056), and
  the load-error fallback.
- None of these three pages translate model-generated content (chat
  answers, legal drafts, citations) — that's the AI Gateway's own
  output, already governed by `preferred_language` via
  `preferences.build_language_instruction` since a much earlier phase,
  not something the frontend controls or needs a locale key for.

## Verification

- Full frontend suite (live `web` container, freshly rsynced): 48
  files / 217 tests passed, unchanged — verified the English source
  strings stay byte-identical to what the existing tests assert on
  (`getByPlaceholderText("Ask a question…")`,
  `getByRole("button", {name: "Send"})`,
  `getByPlaceholderText(/Draft a letter/)`,
  `getByRole("button", {name: "Draft"})`, etc.) before wiring
  anything up.
- `pnpm exec vite build` succeeded.
- Real browser verification via Playwright against a throwaway QA
  admin session (`preferred_language=Deutsch` this round, for
  variety — prior rounds used Dutch): confirmed correct German
  rendering on all three pages (title, hint, placeholder, button,
  label, description, scope text). Sent one real message through
  `Assistant` to check the `toolCalled` conditional still behaves
  correctly post-refactor (it does — no tool was called for that
  message, and the `via:` line correctly stayed hidden, matching
  the unmodified `{turn.toolCalled && (...)}` guard). Cleaned up the
  QA user afterward, including its `ai_call_log` row (FK-ordered
  delete — deleting `users` directly first fails with a foreign key
  violation once a real AI call has been logged against that user;
  worth remembering for any future QA session that actually exercises
  an AI-backed endpoint, not just page loads).

## Consequences

- 11 of the remaining ~50 files now have real page-content
  translation. `AdminDashboard`, `Settings`, `Login`, `NotFound`, and
  shared chrome components are still English-only.
- A larger, separate conversation started about consolidating `Chat`/
  `Legal`/`Assistant` (and eventually the Signal bridge) into one
  orchestrated surface, plus moving phone-number capture into user
  creation/onboarding instead of self-service-only post-creation
  linking. That is explicitly **not** started here — it's a real
  architecture change to backend routing and the Signal bot, not a UI
  wording change, and needs its own design pass before any
  implementation. This i18n round shipped first specifically because
  it's orthogonal: these translations remain valid regardless of
  whether the three pages later get merged into one.
