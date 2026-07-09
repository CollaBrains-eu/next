# Phase 21: Entity Review Queue (AI-Confidence Confirmation)

## Status
Approved (brainstorming)

## Context

`apps/web`'s entity extraction pipeline (`services/api/src/api/entity_agent.py`)
runs fully automatically: whenever a document reaches the `EMBEDDINGS_CREATED`
event, an Ollama model (`qwen2.5:3b-instruct` by default, see
`config.py:25`) extracts `{name, type}` pairs and relationships from the
document text and commits them straight to the `entities` table as ground
truth. There is currently no draft/staging step and no confidence or review
concept anywhere on `Entity`, `EntityMention`, or `EntityRelationship`
(`models.py:184-222`) -- a wrong auto-extracted entity is immediately as
trustworthy-looking as a human-verified one, which is a real liability
concern for a legal/insurance-adjacent product.

A live production check of the Entities page during this same session
surfaced concrete noise from this gap: extraction misclassifying phone
numbers and dates (e.g. `"088 227 77 00"`, `"14 februari 2024"`) as `other`
entities, sitting in the list with no way to distinguish them from a
correctly-extracted person or organization, and no way to suppress them
from reappearing on the next document that repeats the same string.

Research into a sibling, independent, more mature parallel product on
Codeberg (`support-cb/Cbrains-v2`, 595 commits, not a fork of this repo --
its visual design tokens were already ported into this app in Phase 20)
found it has exactly this feature: an "Open Questions" review queue where
a human approves or rejects each AI-suggested entity match before it's
treated as ground truth, plus a mobile-only Tinder-style swipe variant of
the same review action (`mobile/app/entities/review.tsx`, using
`PanResponder`). Neither of those UIs is being ported directly -- this
phase designs an equivalent for this app's own data model and (desktop
web) interaction conventions.

The codebase already has the *shape* of an approval workflow elsewhere --
`Plan.status` gates on `pending_approval` before an `approve` endpoint
transitions it (`models.py:271-274`) -- so this phase applies an existing,
proven pattern to a new model rather than inventing a new one.

## Decision

**Add a `status` field to `Entity` with three states: `pending_review`,
`confirmed`, `rejected`.** New entities are created as `pending_review`.
A migration backfills all entities that exist *before* this phase ships to
`confirmed` -- they are already relied on throughout the app (case
linking, the entity graph, search), so nothing currently visible may
disappear behind a review gate on deploy day.

**Review happens once per distinct `(name, entity_type)` pair, not once
per mention ("first-sighting-only" review).** `entity_agent.py`'s
`_get_or_create_entity` already dedupes case-insensitively on
`(name, entity_type)` before this phase; that lookup is extended to
branch on the matched row's status:

- Matches a `confirmed` entity -> reuse it, attach the new mention, create
  no pending row. A client's own name will not re-trigger review every
  time it appears in a new document.
- Matches a `pending_review` entity -> attach the new mention to that
  *same* pending row rather than creating a duplicate pending entity, so
  the queue does not fill with multiple copies of one not-yet-reviewed
  name.
- Matches a `rejected` entity -> suppress; do not recreate a pending row
  for the same `(name, entity_type)` pair again. This is what stops
  something like `"088 227 77 00"` from reappearing in the queue every
  time a new document happens to repeat that string.
- No match -> create as `pending_review`.

**Every existing entity-listing consumer defaults to `confirmed`-only,
unchanged from today's behavior**, and only the new review queue itself
asks for `pending_review`. This keeps the blast radius of this phase
contained to genuinely new surfaces plus one shared list endpoint's query
parameter, rather than an app-wide behavior change.

**Vehicles are explicitly out of scope.** Vehicle detection
(`vehicle_agent.py`) is a separate extraction path into a separate
`vehicles` table with its own RDW-enrichment-based confidence concept
(ownership/plate lookup accuracy, not "did the AI hallucinate this"). It
is a different kind of correctness problem and does not fit this same
status field.

**Improving entity-extraction *prompt* precision is explicitly out of
scope.** Reducing how often phone numbers or dates get misclassified as
`other` in the first place is a model/prompt-engineering problem. This
phase's job is to make wrong extractions cheap to catch and correct after
the fact, not to make the model extract more precisely.

## Data Model

```python
# services/api/src/api/models.py -- extends the existing Entity class

class Entity(Base):
    __tablename__ = "entities"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

`status` is a plain `String(20)`, matching the existing convention used by
`Document.status`, `Plan.status`, `Task.status`, and `Case.status`
elsewhere in `models.py` -- this codebase does not use a Postgres enum
type for status fields, so this phase does not introduce one either.

Alembic migration:
1. Add `status` column, `server_default='pending_review'`, `nullable=False`.
2. Data migration: `UPDATE entities SET status = 'confirmed'` for all rows
   that existed before this migration ran (i.e. every row present at
   migration time -- there is no way for a pre-existing row to be
   anything other than already-live ground truth, so this is simply "all
   rows, once, at migration time").
3. Leave the column's `server_default` as `'pending_review'` so all
   *future* inserts (from `entity_agent.py`) default correctly without
   the application needing to set it explicitly on every insert path.

`EntityOut` Pydantic schema (`entities.py:18-22`) gains a `status: str`
field.

`EntityMention` and `EntityRelationship` are unchanged -- they reference
`Entity` by foreign key regardless of its status, and simply won't be
reachable through confirmed-only queries until their entity is confirmed.

## API

`GET /entities` (`entities.py`) gains an optional `status` query parameter,
one of `pending_review | confirmed | rejected`, defaulting to `confirmed`
when omitted. This is the only change needed to keep the general Entities
list page, the case-linking dropdown, and search behaving exactly as they
do today with zero frontend changes required at those call sites.

Two new endpoints:

```python
@router.post("/entities/{entity_id}/approve", response_model=EntityOut)
async def approve_entity(entity_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> EntityOut:
    """Transitions a pending_review entity to confirmed."""

@router.post("/entities/{entity_id}/reject", response_model=EntityOut)
async def reject_entity(entity_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> EntityOut:
    """Transitions a pending_review entity to rejected."""
```

Both 404 if the entity does not exist, and 409 if the entity is not
currently `pending_review` (mirrors the existing `Plan.approve` endpoint's
guard against double-approval, per its docstring at `models.py:261`).

One bulk endpoint for clearing a backlog in one action:

```python
class BulkReviewItem(BaseModel):
    entity_id: uuid.UUID
    action: Literal["approve", "reject"]

@router.post("/entities/bulk-review", response_model=list[EntityOut])
async def bulk_review_entities(items: list[BulkReviewItem], db: AsyncSession = Depends(get_db)) -> list[EntityOut]:
    """Approves or rejects multiple pending_review entities in one request."""
```

`GET /entities/graph` (backing `EntityGraph.tsx`) is updated to only
include confirmed entities as nodes, and only include relationships where
*both* endpoints are confirmed as edges -- so a relationship attached to a
still-pending entity does not render as a dangling or half-visible edge
before that entity is reviewed.

## Frontend

New route `apps/web/src/routes/EntityReview.tsx` at `/entities/review`:
one card at a time, showing the entity's name, its `TypeBadge` (reusing
the existing hand-rolled component from `Entities.tsx`, per its documented
deviation from the `Badge` primitive), the source document it was
mentioned in (link, via its first `EntityMention`), and Approve/Reject
buttons (`Button` primitive, `variant="primary"`/`variant="danger"`). A
counter reads "3 of 12 pending". An empty state ("Nothing to review")
shows once the queue is cleared.

**Keyboard shortcuts are the primary interaction**: `J` or `→` approves,
`K` or `←` rejects, advancing to the next card automatically. This is the
desktop-appropriate translation of Cbrains-v2 mobile's touch-swipe review
pattern -- same one-decision-at-a-time review loop, different input
method for a different platform. A "Review all" bulk-approve button
covers the case where a user trusts a whole batch and wants to clear it
in one action rather than reviewing 40 near-identical extractions
one-by-one.

The Sidebar's "Entities" nav link gains a small pending-count badge (an
accent-colored dot with a number) when the review queue is non-empty, so
a backlog is visible without a blocking modal or forced navigation.

The existing `Entities.tsx` list page gains a `status` filter dropdown
(`All | Confirmed | Pending review | Rejected`), defaulting to `Confirmed`
-- today's behavior is unchanged unless a user explicitly asks to see
other statuses.

## Testing

Backend (pytest, TDD):
- `_get_or_create_entity`'s four branches: confirmed-match reuse,
  pending-match reuse (no duplicate row), rejected-match suppression,
  no-match creation as `pending_review`.
- `approve_entity` / `reject_entity`: happy path, 404 on missing entity,
  409 on an already-confirmed or already-rejected entity.
- `bulk_review_entities`: mixed approve/reject batch, partial failure
  behavior (a 409 on one item in the batch does not silently drop it --
  return per-item results, do not accept "some succeeded silently").
- Migration: backfill sets all pre-existing rows to `confirmed`, new
  rows default to `pending_review`.
- `GET /entities/graph`: an edge with one non-confirmed endpoint is
  excluded from the response.

Frontend (Vitest + Testing Library, TDD):
- `EntityReview.tsx`: renders the first pending card, Approve/Reject
  buttons call the respective endpoint and advance to the next card,
  keyboard shortcuts (J/K, arrow keys) trigger the same actions, empty
  state renders when the queue is empty, bulk-approve clears the queue.
- `Entities.tsx`: status filter dropdown changes the query parameter and
  re-fetches; default view is unchanged (`confirmed`-only) with no filter
  interaction.
- `Sidebar.tsx`: pending-count badge renders when count > 0, is absent
  when count is 0.

Manual verification: as with every prior phase in this project, verified
against real production data over the established SSH-tunnel pattern
(temporary CORS widening in `services/api/src/api/main.py`, reverted
immediately after) rather than relying on unit tests alone.

## Open Questions Resolved

- **Should rejected entities ever come back for review?** No -- a
  rejected `(name, entity_type)` pair is suppressed permanently by this
  phase's extraction-matching logic. If this proves too strict in
  practice (e.g. a genuinely different person coincidentally shares an
  exact name with something previously rejected), that is a follow-up
  refinement, not a blocker for this phase -- YAGNI.
- **Should review block downstream features (case linking, search) from
  seeing pending entities at all?** Yes, by making `confirmed` the
  default filter everywhere except the review queue itself, rather than
  building a separate "show anyway" escape hatch. Keeping this a hard
  default (not a per-page opt-in toggle) is what makes the liability
  problem this phase exists to solve actually solved, not just decorated.
- **Why keyboard shortcuts instead of porting the mobile swipe gesture to
  web (e.g. via touch/drag events)?** This app is desktop-first (per
  every other phase's manual verification being done via Playwright
  against a desktop viewport); a drag-to-dismiss gesture is a mobile-native
  affordance that doesn't map cleanly to a mouse-and-keyboard user, whereas
  a keyboard-driven single-decision review loop is a well-understood web
  pattern (e.g. familiar from email triage tools) that achieves the same
  fast, low-friction review cadence.
