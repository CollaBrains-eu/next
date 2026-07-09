# ADR 0040: Phase 23 — Document Classification

## Status

Accepted

## Context

`docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md` §3.2 identified
document auto-tagging/classification as a concrete gap versus CollaBrains
v2, which used paperless-gpt's 7 separate LLM prompts per document
(title/correspondent/document_type/tag/created_date/custom_field/OCR).

## Decision

**Migrate the functionality (doc-type/tags/correspondent extraction), not
v2's architecture.** v2's own v3 redesign already abandoned the 7-prompt
approach for one consolidated prompt with schema validation. Next already
has a better pattern for exactly this shape of problem --
`entity_agent.py`/`planner_agent.py`'s single `json_mode=True` call --
so `document_classification.py` follows that, not paperless-gpt's.

**Wired into the existing event chain, not a new mechanism.**
`_handle_classify_document` subscribes to `EmbeddingsCreated` alongside
the existing task/entity/vehicle extraction handlers (ADR 0017), gated by
a new `auto_classify_on_ready` setting (same on/off convention as the
other three). Publishes a new `DocumentClassified` event other future
consumers can subscribe to.

**No review-queue for low-confidence classifications.** The original
plan sketch mentioned reusing the entity-review-queue pattern for this,
but there is no concrete requirement driving it yet and Document doesn't
have a review-state field distinct from its pipeline `status`
(pending/ocr_processing/embedding/ready/failed) -- repurposing that would
conflict. Not built speculatively; `classification_confidence` is stored
so this can be added later without a schema change.

## Consequences

- `documents` gained four columns (`doc_type`, `tags`, `correspondent`,
  `classification_confidence`), exposed on both `DocumentOut` and
  `DocumentDetailOut`.
- Every document upload in the test suite now also triggers a
  classification call unless a test explicitly disables
  `auto_classify_on_ready` or mocks `api.document_classification.chat_completion`
  -- same tradeoff already accepted for vehicle detection (ADR 0036).
  Full suite re-run after this change showed the identical 14
  pre-existing failures as before (none newly introduced), confirming
  this doesn't add new flakiness beyond what vehicle detection already
  does.
