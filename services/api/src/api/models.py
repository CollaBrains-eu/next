import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Boolean, Computed, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func, text
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
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    correspondent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    classification_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    """A chunk of a document's OCR text, embedded for semantic search.

    `content_tsv` backs keyword search (GIN index) and `embedding` backs
    semantic search (HNSW index) — see migration for index definitions.
    Both live on the chunk, not the parent document, so search results can
    point at the specific passage that matched.
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim), nullable=False)
    content_tsv: Mapped[str] = mapped_column(
        TSVECTOR, Computed("to_tsvector('english', content)", persisted=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")


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


class Task(Base):
    """An actionable item, created manually or extracted from a document by the Planner Agent.

    Deliberately minimal (ADR 0004): no calendar sync, no recurrence, no
    linked-user assignment -- assignee is free text until there's a real
    scheduling/notification feature to justify more structure.
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
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Entity(Base):
    """A person, organization, location, or other named thing extracted from documents.

    Deduplicated by exact case-insensitive (name, entity_type) match only
    -- see docs/adr/0008-phase4-entity-graph.md for why fuzzy/LLM-based
    resolution is deliberately out of scope for now.

    `status` gates whether an extracted entity is trusted: new entities
    start `pending_review` and must be explicitly approved before they
    appear in normal listings, case linking, or the entity graph -- see
    docs/superpowers/specs/2026-07-09-entity-review-queue-design.md.
    """

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
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
