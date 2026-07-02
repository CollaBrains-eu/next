# 0005: Phase 3a — Signal Bot (text chat bridge)

## Status
Accepted (2026-07-02)

## Context
Phase 3's brief scope ("First-class Signal client — upload documents, ask
questions, manage cases, receive proactive notifications") is large.
Following the same pattern as Phases 1 and 2, it's split: 3a proves the
core loop (a person messages the CollaBrains number on Signal, gets an
answer grounded in the knowledge base back), 3b covers everything that
needs its own design (per-user identity, attachments, notifications).

The number `+4949534254784` was registered via `signal-cli-rest-api`'s
"native" mode: solved the hCaptcha challenge (required for API-based
registration — `https://signalcaptchas.org/registration/generate.html`),
SMS verification failed for this number ("Couldn't use SMS verification"),
voice call verification succeeded on retry. Registration data persists in
the `./infra/signal-cli` bind mount.

## Decisions

### One shared service account, not per-sender identity yet
Every Signal sender's message is answered through a single dedicated
Postgres user (`signal-bot`, role `service`) with a long-lived JWT
(`SIGNAL_BOT_API_TOKEN` in `.env`, 10-year expiry, minted once directly --
not through `/auth/token`, since there's no LDAP identity for a bot).
`/chat` doesn't yet know *which human* is messaging via Signal, only that
a message arrived.

This is a real scope cut, not an oversight: mapping a Signal phone number
to a specific CollaBrains/LDAP identity needs its own decision (a pairing
flow? an admin-configured allowlist? trust-on-first-use?) and affects
authorization (does a Signal sender get the permissions of a specific
user, or a fixed low-privilege role?). Building that alongside first
getting Signal talking to the AI Gateway at all would conflate two
separable problems. Phase 3b addresses it once 3a's plumbing is proven.

### Polling, not the receive-websocket
`signal_bot/main.py` polls `GET /v1/receive/{number}` on a fixed interval
(default 3s) rather than using signal-cli-rest-api's websocket receive
mode. Simpler, no new client library, and the latency difference (up to
one poll interval) doesn't matter yet for a text-chat bridge. Revisit if
message volume or latency requirements change.

### Scope for 3a: text in, text out
Incoming messages are forwarded to `POST /chat` (the Phase 2a
orchestrator) verbatim; the answer text is sent back via `POST /v2/send`.
No attachment handling (upload-via-Signal is 3b), no quick-reply buttons,
no proactive/outbound notifications triggered by the workflow engine (also
3b, and needs the workflow engine to have something worth notifying about
first). A failure anywhere in the chat call is caught and replaced with a
plain apology reply rather than leaving the sender without a response or
crashing the poll loop.

## Operational note: minting the service token

There's no login flow for the `signal-bot` account (no LDAP identity), so
its JWT is minted directly, once, against the running API container:

```bash
docker compose exec -e PYTHONPATH=/app/src api python3 -c "
from datetime import datetime, timedelta, timezone
from jose import jwt
from api.config import settings

expire = datetime.now(timezone.utc) + timedelta(days=3650)
payload = {'sub': 'signal-bot', 'role': 'service', 'exp': expire}
print(jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm))
"
```

Paste the result into `.env` as `SIGNAL_BOT_API_TOKEN`. Re-mint (and
restart `signal-bot`) if `JWT_SECRET` ever rotates.

## Verified end-to-end (2026-07-02)

Registered, deployed, and tested against a real message from a real
phone: sent "What documents do you have?" to +4949534254784 on Signal,
`signal-bot` picked it up on the next poll, forwarded it to `/chat`,
and the reply arrived back on Signal successfully.

One finding worth recording: the received envelope identified the sender
by a UUID (`envelope.source`), not a phone number — `sourceNumber` was
absent. This is Signal's phone-number-privacy/sealed-sender behavior, not
a bug. `signal-cli-rest-api`'s `/v2/send` accepts a UUID in `recipients`
just as well as a phone number, so replying worked without extra handling
— but this is worth remembering for Phase 3b's identity-mapping work:
"the sender's phone number" won't always be available, so mapping a
Signal sender to a CollaBrains user may need to key off the UUID instead.
