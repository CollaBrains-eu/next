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
of an answer.

**Phase 3c (done)**: document upload via attachments, and proactive
notifications. Send the bot a file (with an optional caption used as the
title) and it's forwarded straight into the existing document pipeline
(OCR → chunk → embed) on behalf of the linked sender — the bot
acknowledges receipt immediately and does not poll for completion.
Instead, `services/api` itself messages the document's owner directly on
Signal once processing finishes (ready or failed), reusing the same
"linked phone number" identity as everything else. See
`docs/adr/0007-phase3c-signal-attachments-notifications.md`.

Registered number: `+4949534254784` (env `SIGNAL_PHONE_NUMBER`).
