# 0007: Phase 3c — Signal document upload & proactive notifications

## Status
Accepted (2026-07-02)

## Context
The last piece of the Phase 3 brief scope: uploading documents via Signal
attachments, and proactive/outbound notifications. Both build directly on
existing infrastructure from earlier phases rather than needing anything
new: the document pipeline (1b), the workflow trigger (2b/0004), and
identity linking (3b/0006).

## Decisions

### Attachment upload reuses the existing pipeline exactly
A Signal message with an attachment is downloaded from
`signal-cli-rest-api` (`GET /v1/attachments/{id}`) and forwarded to the
existing `POST /documents` endpoint -- same OCR/chunk/embed pipeline as a
web upload, no parallel code path. `upload_document` now resolves its
caller via `get_effective_user` (ADR 0006) instead of `get_current_user`,
so the same "only linked phone numbers get through" rule that already
governs `/chat` applies here too. If the message has a text caption
alongside the attachment, it becomes the document's title; otherwise the
filename is used, same as any other upload.

### No polling for completion -- notifications close the loop instead
The bot does not poll `GET /documents/{id}` waiting for OCR/embedding to
finish. It sends one immediate acknowledgement ("received, processing"),
uploads, and lets the *notification* half of this ADR tell the user when
it's actually ready. This avoids adding a second polling loop next to the
one the bot already runs against `/v1/receive`, and reuses work instead of
building two independent completion-signaling mechanisms.

### Proactive notifications: extend the existing workflow trigger
`api/documents.py::_process_document` already has one workflow trigger
(auto task-extraction, ADR 0004). This adds a second effect at the same
point: when a document reaches `status="ready"` or `"failed"`, if its
owner has a linked `phone_number`, send them a Signal message via a new
`api/signal_client.py::send_signal_message()`. Best-effort and
non-blocking, same as the task-extraction trigger -- a Signal-send failure
(e.g. `signal-cli` not running, since it's gated behind the `signal`
Compose profile and not everyone runs it) must never fail the ingest
pipeline itself.

This is deliberately the only notification trigger added. Task due-date
reminders (also plausibly "proactive notifications") would need a
periodic scheduler, which doesn't exist anywhere in this stack yet --
introducing one for a single reminder use case is bigger than this ADR's
scope. Revisit once there's a second scheduled/periodic need to justify
it, per the same reasoning ADR 0004 used to defer Celery.

### Still one webhook-free polling loop
No changes to how the bot receives messages -- still polling
`GET /v1/receive`, per ADR 0005. Outbound notifications from `services/api`
call `signal-cli-rest-api`'s `POST /v2/send` directly (new
`SIGNAL_CLI_URL`/`SIGNAL_PHONE_NUMBER` settings, reusing the same env vars
`signal-bot` already uses) -- they don't route through the bot process at
all, since the bot has no long-running job to attach a callback to.
