# ADR 0038: Fix Signal Sealed-Sender Resolution Race and Unenforced `preferred_language`

## Status
Accepted

## Context

Production logs (`docker compose logs signal-bot`, incident at
2026-07-03 08:37:44) showed a linked user being told their phone
number "isn't linked to a CollaBrains account yet." The sender's
envelope was sealed-sender (UUID only, no `sourceNumber` -- ADR 0005),
and `resolve_phone_number()` made exactly one `/v1/contacts` call: if
signal-cli's own contact sync hadn't yet recorded that UUID's number,
the bot gave up immediately and never called `/chat` at all.

Separately, Phase 13's `preferred_language` (ADR 0028) was found wired
into only one of four AI-response code paths (`/chat`) -- `/manager/ask`
and Legal Draft ignored the preference entirely, and even in `/chat`
it was phrased as a soft trailing note rather than a directive, which
small instruct models (`qwen2.5:3b-instruct`) don't reliably follow.

## Decision

**`resolve_phone_number()` now retries** the `/v1/contacts` refresh up
to `SIGNAL_RESOLVE_RETRY_ATTEMPTS` times (default 3, 2s apart via
`SIGNAL_RESOLVE_RETRY_DELAY_SECONDS`) when the UUID isn't found yet,
covering the contact-sync race without masking genuine failures: an
actual exception from the HTTP call (network/API error) still gives up
on the first attempt, since retrying wouldn't help.

**`build_language_instruction()`** (`services/api/src/api/preferences.py`)
is now the single source of truth for the language directive, reused
by `chat.py`, `manager_agent.py`, and `legal.py` instead of each
building its own string. Wording was strengthened from a trailing note
to an explicit imperative ("you must respond only in X, regardless of
what language ... is written in"), and it is now injected into all
three AI-response system prompts, not just `/chat`.

Both fixes are additive to existing call sites (helper functions,
config-driven constants) rather than restructuring the callers.

## Consequences

- Preference lookup failures still never fail the underlying request
  (`/chat`, `/manager/ask`, Legal Draft) -- caught and logged, falling
  back to no language instruction, matching the existing `/chat`
  behavior this pattern was copied from.
- The retry adds up to `(RESOLVE_RETRY_ATTEMPTS - 1) *
  RESOLVE_RETRY_DELAY_SECONDS` (4s by default) of latency to the worst
  case of a brand-new sealed-sender contact, before falling back to
  the unlinked reply -- accepted, since the alternative was incorrectly
  telling a linked user they weren't linked at all.
- `preferred_language` still isn't enforced in the Signal bot's own
  fixed reply strings (`UNLINKED_REPLY`, `FALLBACK_REPLY`,
  `UPLOAD_ACK_REPLY`, etc.) -- those are static English text, not
  AI-generated, so they're out of scope for this fix.
