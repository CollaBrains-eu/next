# ADR 0035: Phase 17d — Personal AI Preferences / Settings UI

## Status
Accepted

## Context

The Phase 13 Personal AI preferences backend (`GET`/`PUT /preferences/me`,
ADR 0028) had no UI before this sub-phase. This is the last of the four
Phase 17 sub-phases (`docs/superpowers/specs/2026-07-04-frontend-catchup-design.md`):
17a built the sidebar shell, 17b built Case Workspace UI, 17c built the
Assistant page, and this sub-phase adds `/settings`.

## Decision

**One `<select>` with a curated language list, not free text.** The
backend stores an arbitrary string (`preferred_language: str | None`),
but the frontend offers a fixed list — `English`, `Nederlands`,
`Deutsch` — matching this project's existing Paperless OCR language
footprint (`eng+nld+deu`, configured since Phase 1b). A controlled
vocabulary is easier to get right than free text for a field that only
needs to communicate a small, known set of languages to the LLM.

**Intentionally the only setting on the page.** `Settings.tsx` exists
so future settings have a home once they're built, not because more
exist to add right now — matching this project's "smallest safe slice"
bias applied to a page instead of a backend feature.

**No backend changes.** `GET`/`PUT /preferences/me` already existed and
needed no modification.

## Consequences

- With this sub-phase merged, all four Phase 17 sub-phases are
  complete: the sidebar has all 8 nav items the Phase 17 spec named
  (Documents, AI Chat, Legal Draft, Tasks, Entities, Cases, Assistant,
  Settings), and three previously backend-only capabilities (Case
  Workspace, Manager Agent, Personal AI preferences) now have real UI.
- Planning Engine, Tool Registry/MCP, Knowledge Graph Decisions (beyond
  what 17b's attach-picker needed), Organizations/admin policies, and
  Learning dataset export remain backend-only — explicitly out of
  scope for Phase 17 per its spec, left as candidate future work.
- No component-level test coverage was added for `Settings.tsx` — same
  reasoning as every other Phase 17 sub-phase's ADR: no React
  component testing library in this codebase. Verified via `tsc -b`
  plus a live browser check confirming the value persists across a
  reload.
