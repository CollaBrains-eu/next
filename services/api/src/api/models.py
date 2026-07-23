import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.config import settings
from api.db import Base

# The organization every pre-Phase-14 user is backfilled into (ADR 0029).
# Fixed, well-known UUID so new rows default to it at the DB layer without
# a Python-side lookup -- see the migration for where the row is created.
DEFAULT_ORGANIZATION_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Organization(Base):
    """The tenant boundary (Phase 14, ADR 0029). Every user belongs to
    exactly one. `policies` holds org-level overrides of otherwise
    hardcoded platform behavior (e.g. approval_required_goals) --
    application-enforced, not a DB constraint, the same choice ADR 0008
    made for Entity.entity_type.

    No per-table organization_id retrofit (documents/memories/plans/...)
    yet -- see ADR 0029 for why that's its own dedicated future phase,
    not done speculatively here.
    """

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    policies: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class User(Base):
    """A CollaBrains user, provisioned from LDAP on first successful login.

    LDAP is the identity source (username/password); this table is the
    authorization source (role). Auto-created on first login rather than
    synced ahead of time, since Signal/guest accounts (Phase 3) won't all
    come through LDAP.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")
    phone_number: Mapped[str | None] = mapped_column(String(32), unique=True, nullable=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False,
        server_default=text(f"'{DEFAULT_ORGANIZATION_ID}'::uuid"),
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    phone_prompt_dismissed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class PendingUserPhoneNumber(Base):
    """A phone number set by an admin at user-creation time, before the
    Postgres `User` row exists (it's only created on first LDAP login).
    `_get_or_provision_user` (auth.py) consumes -- reads and deletes --
    the matching row on first login, same "LDAP is identity, Postgres is
    authorization" division as everything else in this table's docstring.
    """

    __tablename__ = "pending_user_phone_numbers"

    username: Mapped[str] = mapped_column(String(255), primary_key=True)
    phone_number: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PendingRegistration(Base):
    """A self-service signup awaiting email verification (Priority 3
    commercial SaaS, ADR 0074). No LDAP entry or Postgres `User` row exists
    yet -- both are created together, in registration_service.complete_registration,
    once the address is confirmed reachable. `password_hash` is
    pre-computed at registration time (the same SSHA scheme ldap_auth.py
    already uses for admin-created users) so verification never needs the
    plaintext password again.

    No unique constraint on `username`/`email` here (unlike `User.username`)
    -- uniqueness against real accounts is enforced in
    registration_service.username_or_email_taken at write time, the same
    "application-enforced, not a DB constraint" choice `Organization.policies`
    already made, since a merely pending, unconfirmed row shouldn't
    permanently squat a name the way a real account does.
    """

    __tablename__ = "pending_registrations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Document(Base):
    """An uploaded file, tracked through OCR (via Paperless-ngx) and embedding.

    Paperless owns the actual file bytes and OCR once consumed
    (`paperless_id`); this table tracks CollaBrains-side pipeline status and
    caches the extracted text so search doesn't need to call out to
    Paperless on every query.
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(255), nullable=False)
    paperless_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    residency_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("residencies.id", ondelete="SET NULL"), nullable=True
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    correspondent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Correspondent address, same field set/lengths as AddressDetail (entities'
    # own address side table) -- kept as flat columns here rather than a side
    # table since a document has at most one correspondent, not a dedup'd,
    # relationship-bearing graph node like Entity.
    correspondent_street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correspondent_house_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    correspondent_po_box: Mapped[str | None] = mapped_column(String(20), nullable=True)
    correspondent_postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    correspondent_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    correspondent_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    metafields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Postgres text-search config name ('english'/'german'/'dutch'), detected
    # from ocr_text at ingestion -- see api.text_language. Drives both this
    # document's chunks' content_tsv and, indirectly via the querying user's
    # own preferred_language, which config hybrid_search's keyword half uses.
    language: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """A chunk of a document's OCR text, embedded for semantic search.

    `content_tsv` backs keyword search (GIN index) and `embedding` backs
    semantic search (HNSW index) — see migration for index definitions.
    Both live on the chunk, not the parent document, so search results can
    point at the specific passage that matched.

    content_tsv was originally a GENERATED column hardcoded to
    to_tsvector('english', content) -- Postgres generated columns require
    an IMMUTABLE expression, which rules out a per-row regconfig looked up
    from the parent document's detected language (api.text_language), so
    it's now a plain column the ingestion pipeline populates explicitly
    (documents.py) with the document's own language's config instead.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    content_tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")


class Category(Base):
    """A generic, hierarchical category/tag taxonomy (Phase 24, ported from
    CollaBrains v2's `categories` table -- see docs/superpowers/plans/2026-07-10-document-categories.md).

    `category_type` is a discriminator so this table can hold more than one
    independent taxonomy (documents today; entities or anything else later)
    without needing a separate table per concern -- `slug` only needs to be
    unique *within* a category_type, not globally.
    """

    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    category_type: Mapped[str] = mapped_column(String(50), nullable=False)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    color: Mapped[str | None] = mapped_column(String(50), nullable=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("slug", "category_type", name="uq_category_slug_type"),)


class AiCallLog(Base):
    """Audit trail for every AI Gateway call (ADR 0003).

    Kept separate from application tables so it can grow independently and
    be retained/pruned on its own policy without touching user-facing data.
    """

    __tablename__ = "ai_call_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReflectionLog(Base):
    """Audit trail of reflection reviews on generated answers (Phase 8d, ADR 0020).

    Kept separate from ai_call_log (a record of raw model calls) since a
    reflection is a judgment about a *previous* call's output, not a call
    in its own right -- mirrors ai_call_log's own "grow independently"
    rationale.
    """

    __tablename__ = "reflection_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    sufficient_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    issues: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    retried: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnswerFeedback(Base):
    """User thumbs up/down on a grounded answer (Phase 28, answer-quality
    signal). Stores the answer text and the reflection verdict computed for
    that same answer, so an admin can query the correlation ReflectionLog
    alone can't show: a high-confidence answer the user rejected -- the
    shape of a hallucination worth investigating.
    """

    __tablename__ = "answer_feedback"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(50), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[str] = mapped_column(String(10), nullable=False)  # "up" | "down"
    reflection_confidence: Mapped[int | None] = mapped_column(Integer, nullable=True)
    reflection_sufficient_evidence: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# Shared with planner_agent.py (auto-categorization) and tasks.py (manual
# create/update validation) -- lives here rather than tasks.py to avoid a
# circular import (tasks.py already imports from planner_agent.py).
TASK_CATEGORIES = ("payment", "appointment", "deadline", "notification")


class Task(Base):
    """An actionable item, created manually or extracted from a document by the Planner Agent.

    Deliberately minimal (ADR 0004): no calendar sync, no linked-user
    assignment -- assignee is free text. Recurrence and due-date
    notifications were added in ADR 0064, resolving the "until there's a
    real scheduling/notification feature" deferral this docstring used
    to describe.
    """

    __tablename__ = "tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    recurrence_rule: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    category: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Entity(Base):
    """A person, organization, location, or other named thing extracted from documents.

    Deduplicated by exact case-insensitive (name, entity_type) match --
    scoped per `owner_id` (Phase 28, matching v2/v3: each account has its
    own entity graph, not a system-wide one) -- see
    docs/adr/0008-phase4-entity-graph.md for why fuzzy/LLM-based
    resolution is deliberately out of scope for now.

    `status` gates whether an extracted entity is trusted: new entities
    start `pending_review` and must be explicitly approved before they
    appear in normal listings, case linking, or the entity graph -- see
    docs/superpowers/specs/2026-07-09-entity-review-queue-design.md.
    """

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntityMention(Base):
    """Records that an entity appears in a given document."""

    __tablename__ = "entity_mentions"
    __table_args__ = (UniqueConstraint("entity_id", "document_id", name="uq_entity_mentions_entity_document"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntityRelationship(Base):
    """A directed, typed relationship between two entities, evidenced by a document."""

    __tablename__ = "entity_relationships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class EntityMergeLog(Base):
    """Audit trail of entity merges (Phase 25). `source_entity_id` is deliberately not a
    foreign key -- the source row is deleted as part of the merge it records, so an FK
    would force either cascading the log away (defeating its purpose) or blocking the
    delete entirely."""

    __tablename__ = "entity_merge_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False)
    merged_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    merged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AddressDetail(Base):
    """Structured fields for an `Entity` where `entity_type = 'address'`.

    Kept as a side table rather than adding columns to `Entity` itself --
    same pattern as `Vehicle` enriching `Entity(entity_type="vehicle")` --
    so entity dedup, mentions, relationships, and the review queue all
    apply to addresses for free. `normalized_key` (postal_code + house_number
    + street, lowercased) is what dedup actually keys on, not `Entity.name`
    -- two differently-formatted LLM extractions of the same real address
    must resolve to the same entity for relocation detection to work.
    """

    __tablename__ = "address_details"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    street: Mapped[str | None] = mapped_column(String(255), nullable=True)
    house_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    normalized_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class ContactDetail(Base):
    """Structured contact fields for an Entity where entity_type is 'person' or
    'organization'. One row per entity (same 1:1 pattern as AddressDetail) --
    gap-filled across documents, never fragmented into duplicates. PO box and
    visiting address are FKs to `entities.id` (type 'address'), not raw text,
    reusing the same parsing/dedup/maps_url machinery AddressDetail already has.
    """

    __tablename__ = "contact_details"

    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), primary_key=True
    )
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    po_box_address_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )
    visiting_address_entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="SET NULL"), nullable=True
    )


class Residency(Base):
    """A period during which a user lived at a given address (ADR pending).

    `valid_to IS NULL` means "current" -- enforced to be unique per user at
    the DB level (see migration's partial unique index), not just in
    application code, after the `pending_user_phone_numbers` uniqueness gap
    found in the phone-at-creation feature made DB-level enforcement the
    default assumption for this kind of "at most one active X" invariant.
    `status` mirrors `Entity.status` (pending_review/confirmed/rejected) --
    a single document revealing a new address is evidence, not proof.
    """

    __tablename__ = "residencies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    address_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Memory(Base):
    """Persistent AI memory (Phase 8b, ADR 0018).

    `memory_type` is one of `episodic` (conversation summaries), `semantic`
    (facts about users/entities/cases), or `procedural` (reusable
    workflows/plans) -- enforced in application code (api/memory.py), not a
    DB enum, the same choice ADR 0008 made for `Entity.entity_type`.
    `json_data` holds type-specific structured extras a summary string can't
    carry (e.g. a structured entity/document reference). Retrieval is by
    `embedding` similarity (HNSW cosine index, same strategy as
    `DocumentChunk`), scoped to `user_id` and non-expired rows.
    """

    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    memory_type: Mapped[str] = mapped_column(String(50), nullable=False)
    importance: Mapped[int] = mapped_column(Integer, nullable=False, default=50)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    json_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Plan(Base):
    """A goal decomposed into an ordered sequence of steps (Phase 8c, ADR 0019).

    `goal_type` is one of `planning_engine.GOAL_TYPES`; `goal_params` holds
    whatever that goal template needs (usually `document_ids`).
    `requires_approval` gates execution behind `POST /plans/{id}/approve`
    for goals whose output is meant to leave the system (drafts) -- see
    the ADR. `status` is `pending_approval`, `running`, `completed`,
    `partially_failed`, or `failed`.
    """

    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(50), nullable=False)
    goal_params: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending_approval")
    requires_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class PlanStep(Base):
    """One step of a `Plan`'s task tree, executed in `step_index` order.

    `agent` selects the handler in `planning_engine.AGENT_DISPATCH`
    (`document_agent`, `planner_agent`, `entity_agent`, `legal_agent`,
    `collection_agent`, or `timeline_agent`). A failed step is retried
    once by the engine before being recorded as `failed` -- it does not
    abort the rest of the plan (ADR 0019).
    """

    __tablename__ = "plan_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("plans.id", ondelete="CASCADE"), nullable=False)
    step_index: Mapped[int] = mapped_column(Integer, nullable=False)
    agent: Mapped[str] = mapped_column(String(50), nullable=False)
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    result_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Decision(Base):
    """A recorded decision -- the first Phase 10 knowledge-graph node type
    beyond Entity (Phase 4, ADR 0008). Created when a human approves a
    Plan whose output leaves the system (ADR 0025): approving is
    deciding, so this is a side effect of `planning_engine.approve_plan`,
    not a separate user-facing action.
    """

    __tablename__ = "decisions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    plan_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("plans.id", ondelete="SET NULL"), nullable=True
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class GraphEdge(Base):
    """A directed, typed relationship between two knowledge-graph nodes of
    possibly different types (Phase 10, ADR 0025).

    Deliberately polymorphic and generalized beyond ADR 0008's
    Entity-to-Entity-only `entity_relationships`: `source_id`/`target_id`
    have no DB-level foreign key (a single column can't reference two
    different tables) -- a real trade-off accepted for extensibility.
    `source_type`/`target_type` are plain strings (e.g. "decision",
    "document"), the same choice ADR 0008 made for `Entity.entity_type`.
    """

    __tablename__ = "graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    relationship_type: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPreference(Base):
    """Durable, explicitly-set facts about a specific user (Phase 13, ADR
    0028) -- distinct from Memory (Phase 8b), which stores facts extracted
    from conversations. One row per user, upserted, never expires.
    """

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    preferred_language: Mapped[str | None] = mapped_column(String(50), nullable=True)
    date_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    time_format: Mapped[str | None] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Case(Base):
    """A persistent case/matter that documents, tasks, and decisions can
    belong to (Phase 16). Membership is optional everywhere -- a document,
    task, or decision can exist with no case at all, same as before this
    phase. Documents link via a direct `case_id` FK (the most central,
    most-queried relationship); tasks and decisions link via the existing
    polymorphic `GraphEdge` table (Phase 10, ADR 0025) instead of new
    columns on their own tables.
    """

    __tablename__ = "cases"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CaseMember(Base):
    """Grants a user access to a case they don't own (Phase 26) -- e.g. a
    contractor working a homeowner's renovation case needs to see/manage
    it without becoming its owner. `Case.user_id` stays the single source
    of truth for ownership -- "owner" is not a role stored here, it's the
    case creator, automatic and un-invited; `role` covers the two kinds of
    invited access (worker/member).

    Invitation-based, same pending/accepted/declined shape as entity and
    residency review elsewhere in this codebase: adding a member creates a
    `pending` invitation the invited user must accept before it grants any
    access (`is_case_member`/`_require_case_access` only count `accepted`
    rows).
    """

    __tablename__ = "case_members"
    __table_args__ = (UniqueConstraint("case_id", "user_id", name="uq_case_members_case_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("cases.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="member")  # "worker" | "member"
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # "pending" | "accepted" | "declined"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkspaceMember(Base):
    """Grants a user read access to another user's entire workspace (v2
    parity port -- v2 called this "werkruimte delen", sharing with up to
    2 trusted co-admins). Distinct from CaseMember, which scopes access
    to one case; this scopes to everything an owner owns. Same
    pending/accepted/declined invitation shape, capped at 2 active
    (pending or accepted) memberships per owner -- v2's "maximaal 2
    vertrouwde personen" limit, enforced in workspace_sharing.py rather
    than at the DB level since it depends on counting sibling rows.
    """

    __tablename__ = "workspace_members"
    __table_args__ = (UniqueConstraint("owner_id", "member_id", name="uq_workspace_members_owner_member"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    member_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    can_export: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # "pending" | "accepted" | "declined"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class OnboardingToken(Base):
    """A single-use link sent by email to get a user started (Phase 27,
    v2 port). Narrower than v2's version -- no PocketID one-time-token
    fallback (this backend has no PocketID/OIDC layer at all), and no
    Signal-safety-number identity verification (that's a separate,
    much larger feature this port doesn't attempt); just a random token
    with an expiry and a used_at marker, checked by the onboarding page.
    """

    __tablename__ = "onboarding_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Vehicle(Base):
    """RDW-enriched vehicle data behind an `Entity(entity_type="vehicle")`
    row (Phase 18). A separate table, not columns on `Entity` itself --
    `Entity` only ever holds `name`/`entity_type` (Phase 4, ADR 0008), and
    every other node type needing structured data (`Case`, `Decision`)
    already gets its own table rather than bloating `Entity`. See
    docs/superpowers/specs/2026-07-04-vehicle-entity-design.md.

    All RDW-sourced fields are stored as plain strings -- RDW's open data
    API (Socrata/SODA) returns them as JSON strings, not typed numerics,
    so this avoids coercion failures on values like "1200" or "J"/"N".
    """

    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    kenteken: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vin: Mapped[str | None] = mapped_column(String(17), nullable=True)
    voertuigsoort: Mapped[str | None] = mapped_column(String(100), nullable=True)
    merk: Mapped[str | None] = mapped_column(String(100), nullable=True)
    handelsbenaming: Mapped[str | None] = mapped_column(String(100), nullable=True)
    eerste_kleur: Mapped[str | None] = mapped_column(String(50), nullable=True)
    datum_eerste_toelating: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vervaldatum_apk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    wam_verzekerd: Mapped[str | None] = mapped_column(String(10), nullable=True)
    openstaande_terugroepactie_indicator: Mapped[str | None] = mapped_column(String(10), nullable=True)
    brandstofomschrijving: Mapped[str | None] = mapped_column(String(100), nullable=True)
    massa_ledig_voertuig: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aantal_cilinders: Mapped[str | None] = mapped_column(String(20), nullable=True)
    wielbasis: Mapped[str | None] = mapped_column(String(20), nullable=True)
    catalogusprijs: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aantal_zitplaatsen: Mapped[str | None] = mapped_column(String(20), nullable=True)
    aantal_deuren: Mapped[str | None] = mapped_column(String(20), nullable=True)
    vermogen_massarijklaar: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lengte: Mapped[str | None] = mapped_column(String(20), nullable=True)
    europese_voertuigcategorie: Mapped[str | None] = mapped_column(String(20), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Appointment(Base):
    """A scheduled event with a specific time (unlike Task.due_date, which
    is date-only) and an optional physical location, for the calendar/
    agenda page and .ics export. Optionally linked to a Case and/or a
    Vehicle -- e.g. an RDW APK inspection tied to a specific kenteken.
    See docs/superpowers/specs/2026-07-09-phase27b-calendar-design.md.
    """

    __tablename__ = "appointments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cases.id", ondelete="SET NULL"), nullable=True
    )
    vehicle_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vehicles.id", ondelete="SET NULL"), nullable=True
    )
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BugReport(Base):
    """A user-submitted bug report, optionally AI-analyzed (Admin Dashboard, Phase 22).

    Migrated from CollaBrains v2's `BugReport` model/admin tab -- v2 had no
    equivalent of `AiCallLog`'s cost tracking, so that part of the admin
    dashboard is new, not migrated; this table covers the bug-report part
    v2 did have.
    """

    __tablename__ = "bug_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")  # open|analyzed|closed
    ai_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # v2 lifecycle fields (title/page_url/AI-triage/Codeberg-issue/clarifying-Q&A),
    # additive alongside the original description/status/ai_analysis columns above.
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    page_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ai_labels: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded list[str]
    ai_priority: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ai_suggested_fix: Mapped[str | None] = mapped_column(Text, nullable=True)
    codeberg_issue_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    codeberg_issue_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clarifying_questions: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded list[str]
    clarifying_answers: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON-encoded dict
    clarifying_status: Mapped[str | None] = mapped_column(String(20), nullable=True)


class UserFact(Base):
    """A time-bound fact about a user (e.g. address, employer), valid over [valid_from, valid_to)
    (Phase 26). `status` reuses Entity's pending_review/confirmed/rejected convention
    (ADR 0008/Phase 21) rather than a separate review-queue system -- see api/user_facts.py.
    """

    __tablename__ = "user_facts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    fact_type: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    valid_from: Mapped[date] = mapped_column(Date, nullable=False)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    source_document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review", server_default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ActivityLogEntry(Base):
    """Append-only audit trail of meaningful lifecycle events on a
    Document/Case/Task (Phase 29). Same "separate, independently growable/
    prunable audit table" rationale as AiCallLog.

    `entity_id` is a plain column, not a FK -- an entry must survive its
    subject's deletion (e.g. a "deleted" entry itself), same reasoning as
    EntityMergeLog.source_entity_id. `entity_type` is a plain string (not a
    DB enum), the same choice ADR 0008 made for Entity.entity_type.

    Deliberately distinct from api/dashboard.py's derived "recent items"
    widget: that's a recency-sorted view over existing tables' created_at,
    not a persisted record of what happened -- this table is the real thing.
    """

    __tablename__ = "activity_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ShareLink(Base):
    """A token-gated shareable link to a Document/Case/Task's detail view
    (Phase 29). One live token per (entity_type, entity_id) -- creating a
    new one for an entity that already has one rotates it in place, the
    same upsert shape as `add_case_member`'s re-invite.

    Resolving a token still requires an authenticated CollaBrains login
    (see api/sharing_router.py's `GET /share/{token}`) -- this bypasses the
    entity's own ownership check for whoever holds the link, it is not
    anonymous access.
    """

    __tablename__ = "share_links"
    __table_args__ = (UniqueConstraint("entity_type", "entity_id", name="uq_share_links_entity"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    created_by_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WebauthnCredential(Base):
    """A passkey registered by a user (Phase 25, v2 port). Additive
    alongside LDAP password login (auth.py) -- registering a passkey never
    disables the password, unlike v2's optional `passkey_required` lockout.

    Unlike v2 (a single JSONB column on its user-profile table, one passkey
    per account), this is its own table so a user can register more than
    one device. `credential_id` is looked up directly on login (indexed,
    unique) rather than v2's documented linear scan over every user.
    """

    __tablename__ = "webauthn_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    credential_id: Mapped[str] = mapped_column(String(512), unique=True, index=True, nullable=False)
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    sign_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
