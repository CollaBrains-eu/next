# signal-bot

First-class Signal client for CollaBrains — upload documents, ask
questions, manage cases, and receive proactive notifications via Signal
chat.

**Phase 3a (done)**: text-chat bridge. Polls `signal-cli-rest-api` for
incoming Signal messages and forwards each to the CollaBrains `/chat`
orchestrator.

**Phase 3b (done)**: per-sender identity. Resolves the sender's phone
number (via `sourceNumber`, or a `/v1/contacts` lookup when Signal's
sealed-sender behavior only gives a UUID) and answers on behalf of
whichever CollaBrains user has linked that number
(`PUT /auth/me/phone`). Unlinked numbers get a clear explanation instead
of an answer — only linked users get access. See
`docs/adr/0006-phase3b-signal-identity-linking.md`.

Document upload via attachments and proactive/outbound notifications are
Phase 3c.

Registered number: `+4949534254784` (env `SIGNAL_PHONE_NUMBER`).
