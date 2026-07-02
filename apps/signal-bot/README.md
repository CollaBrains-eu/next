# signal-bot

First-class Signal client for CollaBrains — upload documents, ask
questions, manage cases, and receive proactive notifications via Signal
chat.

**Phase 3a (done)**: text-chat bridge. Polls `signal-cli-rest-api` for
incoming Signal messages, forwards each to the CollaBrains `/chat`
orchestrator (Phase 2a), and sends the answer back. All senders currently
share one service identity (Postgres user `signal-bot`, role `service`) —
per-sender identity mapping, document upload via attachments, and
proactive/outbound notifications are Phase 3b. See
`docs/adr/0005-phase3a-signal-bot.md`.

Registered number: `+4949534254784` (env `SIGNAL_PHONE_NUMBER`).
