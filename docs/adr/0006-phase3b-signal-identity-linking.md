# 0006: Phase 3b — Signal identity linking by phone number

## Status
Accepted (2026-07-02)

## Context
Phase 3a proved the Signal↔`/chat` bridge but left a real gap: every
message answered through one shared `signal-bot` service account, with no
check on who was messaging. Anyone who discovers the number gets answers
from the knowledge base. Phase 3b closes this: only a phone number the
account owner has explicitly linked to their CollaBrains account gets
answered, and the AI Gateway audit log/rate limiting attribute correctly
to that real user instead of the shared bot identity.

### Resolving sealed-sender UUIDs
Phase 3a's ADR noted Signal's sealed-sender behavior means an incoming
envelope's `source` is often a UUID, not a phone number. Confirmed
`GET /v1/contacts/{botnumber}` on `signal-cli-rest-api` resolves any UUID
the bot has seen back to its phone number (it already had this mapping
for a real test sender from Phase 3a's verification) — so phone-based
linking is viable without asking users to always send from a
non-sealed-sender client.

## Decisions

### Self-service linking, not an admin flow or pairing code
`PUT /auth/me/phone` lets an already-LDAP-authenticated user set their own
`phone_number` (E.164). No verification SMS/call to prove they own that
number -- LDAP already established who they are, and a user linking the
wrong number just means messages from that number won't answer as them
(no privilege escalation risk, since the linked number only grants access
to that *specific* LDAP-authenticated user's own permissions). Simpler
than a pairing-code flow, and there's no UI yet to drive one anyway
(Phase 5 is frontend integration) — this is reachable via a direct API
call in the meantime.

### Enforcement: unlinked numbers get a clear reply, not a silent answer
`POST /chat` now resolves the caller via a new `get_effective_user`
dependency: if the authenticated caller is the `signal-bot` service
account (role `service`) AND an `X-On-Behalf-Of-Phone` header is present,
it looks up the `User` with that `phone_number` and acts as *that* user
(their id feeds the AI Gateway's rate limit and audit log, not the bot
account's). If no user has linked that number, it raises 403. Any
non-service caller's `X-On-Behalf-Of-Phone` header is ignored outright --
only the trusted service account can act on another user's behalf, and
only via a header a normal LDAP-authenticated request has no reason to
send.

`signal_bot/main.py` resolves the sender's phone number (`sourceNumber`
directly, or a `/v1/contacts` lookup + in-memory cache when only a UUID
is present) and sends it via that header. A 403 from `/chat` gets a
specific "your number isn't linked yet" reply instead of the generic
failure message, so an unlinked sender knows what to do next instead of
assuming the bot is broken.

### Still one shared JWT, now correctly attributed downstream
The bot's own JWT (Postgres `signal-bot`/role `service`) is unchanged --
it's a transport-layer credential, not the identity that matters for
authorization or audit. The *effective* user for rate limiting and the
`ai_call_log` audit trail is now the linked human, which is what actually
matters for fairness (no more all Signal users sharing one rate-limit
bucket) and for the audit trail meaning something.

### Out of scope (Phase 3c)
Document upload via Signal attachments, proactive/outbound notifications,
and a real UI for linking a phone number (vs. a direct API call) are all
separate, deferred.
