# ADR 0042: Phase 25 — Entity Merge

## Status

Accepted

## Context

`docs/superpowers/plans/2026-07-09-fase1-admin-dashboard.md` §3.4
identified entity merge as a gap versus CollaBrains v2
(`POST /entities/{target_id}/merge`). Next's automatic dedup only
catches exact case-insensitive (name, entity_type) matches (ADR 0008) --
"Acme Corp" vs "Acme Corporation" are never auto-merged, and there was
no manual fallback.

## Decision

**`merge_entities()` moves mentions/relationships from source to target,
then deletes source**, mirroring v2's endpoint shape
(`POST /entities/{target_id}/merge`, body `{source_entity_id}`).

**Two edge cases handled by leaving rows untouched and letting the
existing `ON DELETE CASCADE` on `entities.id` clean them up**, not by
explicit deletes:
- An `EntityMention` for a document both source and target already
  mention would violate `entity_mentions`' `(entity_id, document_id)`
  unique constraint if moved -- left pointed at `source_id`.
- An `EntityRelationship` directly between source and target would
  become a meaningless self-loop if both sides got repointed to
  `target_id` -- left pointed at `source_id`.

  An earlier version of this code called `db.delete()` on these rows
  explicitly, which raced with the CASCADE from the `source` delete
  later in the same transaction and produced a harmless but noisy
  SQLAlchemy warning ("DELETE statement ... 0 were matched"). Caught
  via the test suite's own warning output, not a functional test
  failure -- fixed by simply not touching those rows, letting the
  cascade be the only thing that removes them.

**`entity_merge_log.source_entity_id` is not a foreign key** (see the
column's docstring in `models.py`) -- it deliberately outlives the row
it names, since the whole point of the audit log is to record that a
now-deleted entity existed and was merged.

## Consequences

- One new table, no changes to existing tables.
- Full test suite re-run after this change showed the identical 14
  pre-existing failures as every prior phase, confirming no new
  regressions.
