# Document Categories Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current flat 5-type document classification (`invoice|contract|correspondence|legal|other`) with a real, hierarchical category taxonomy — ~25 doc-types grouped into 6 parent categories — ported from CollaBrains v2 (`support-cb/Cbrains-v2` on Codeberg, local reference clone at `/Users/stagnaat/Downloads/cbrains-v2`), adapted to this project's stack and i18n infrastructure.

**Architecture:** A new generic, self-referential `Category` table (ported as-is from v2 — it's already reusable, not document-specific) plus `Document.category_id`. The existing single-prompt classification call (`document_classification.py`, Phase 23) gets its `VALID_DOC_TYPES` expanded from 5 to ~25 values and gains an auto-categorization step (doc_type → category, via a static map, mirroring v2's `tasks.py` pattern) — no new AI call, no new architecture, same `json_mode=True` grounded-decoding pattern already in place. Category display names are i18n keys (`categories.<slug>`), not hardcoded strings — v2 baked Dutch names directly into its seed data; this project already has a working i18n system, so names route through it instead. The frontend reuses the existing `FilterChips` component (already used for document status filtering on `Workspace.tsx`) as a second filter dimension, rather than porting v2's bespoke animated tile-grid component.

**Tech Stack:** SQLAlchemy async, Alembic, FastAPI, React + react-i18next, pytest.

## Global Constraints

- The richer taxonomy is the whole point of this plan — do not ship a trimmed-down version. All ~25 doc-types and all 6 parent categories from v2's `seed_categories.py` get ported, not a subset.
- Category display names live in `apps/web/src/locales/{en,nl,de}.json` under a new `categories` namespace, not hardcoded in Python seed data or Python-side English strings shown directly to users.
- `Category` is generic (`category_type` discriminator, matching v2 exactly) — this plan only seeds `category_type="document"` rows, but the schema itself must not assume documents are the only thing ever categorized.
- New Alembic migration's `down_revision` is `d1a4e7f9c2b6` — verified via the live database's actual `alembic_version` table (`SELECT version_num FROM alembic_version`), not assumed from the file tree, which currently has stray unmerged heads left over from an earlier, since-abandoned build (`b4f7a2c9d1e3`, `c7e2b9f4a1d6`) that predate this project's 2026-07-02 from-scratch rebuild. Not this plan's job to clean up those stray files.
- Every task must leave `pytest services/api/tests/ -x` fully green before its commit step.

---

### Task 1: `Category` model + migration (schema + seed data together)

**Files:**
- Modify: `services/api/src/api/models.py`
- Create: `services/api/alembic/versions/<new_revision>_create_categories_table.py`
- Test: `services/api/tests/test_models.py` (or wherever existing model-level tests for similar tables live — check `test_tasks.py`'s pattern for `Task.position` if no dedicated `test_models.py` exists, and follow whichever convention is actually present)

**Interfaces:**
- Produces: `class Category(Base)` with `id, name, slug, category_type, icon, color, parent_id, created_at, updated_at`; unique constraint on `(slug, category_type)`. `Document.category_id: Mapped[uuid.UUID | None]` FK to `categories.id`, `ondelete="SET NULL"`.

- [ ] **Step 1: Check the actual test convention for model-only changes first**

Run: `grep -rn "class Task\b" -A5 services/api/tests/test_tasks.py 2>/dev/null | head -20` and `find services/api/tests -iname "test_models*"`. If no dedicated model test file exists, this task's verification is the migration round-trip itself (Step 5) plus the fact that Task 2 immediately exercises the new column — do not invent a placeholder model test file that doesn't match this project's actual conventions.

- [ ] **Step 2: Add the `Category` model**

In `services/api/src/api/models.py`, add (place near `Document`, since it's document-classification-adjacent even though the table itself is generic):

```python
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
```

Note `name` stays on the model (matching v2's schema exactly, for portability) even though this plan's own Global Constraints say display names route through i18n on the frontend — `name` is populated with the **slug-derived English identifier** (e.g. `"payslip"`), used only as a fallback/admin-facing label and as what `to_ollama_tools`-style tooling would show a model if a category name ever needs to reach an LLM prompt; the frontend never renders `category.name` directly, it renders `t(\`categories.${category.slug}\`)`.

Add `category_id` to `Document`, right after the existing `doc_type` column:

```python
    doc_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
```

Check the top of `models.py` for `UniqueConstraint` in the existing import line from `sqlalchemy` — add it if not already imported.

- [ ] **Step 3: Write the seed data as a plain Python module (imported by both the migration and the classifier)**

Create `services/api/src/api/document_categories.py`:

```python
"""Document category taxonomy (Phase 24, ported from CollaBrains v2's
seed_categories.py -- see docs/superpowers/plans/2026-07-10-document-categories.md).

Slugs and doc_types are English identifiers, not user-facing strings --
display names live in apps/web/src/locales/{en,nl,de}.json under the
"categories" namespace, keyed by slug. This is the one difference from
v2's approach, which baked Dutch names directly into this data; the
taxonomy structure itself (6 parent groups, ~20 subcategories) is
otherwise a direct port.
"""

DOCUMENT_CATEGORIES: list[dict] = [
    # -- Finance --
    {"slug": "finance", "icon": "Coins", "color": "#FF9500", "parent": None, "doc_types": []},
    {"slug": "payslip", "icon": "Banknote", "color": "#FF9500", "parent": "finance",
     "doc_types": ["payslip", "salary", "annual_statement"]},
    {"slug": "tax", "icon": "Landmark", "color": "#FF3B30", "parent": "finance", "doc_types": ["tax"]},
    {"slug": "pension_benefits", "icon": "PiggyBank", "color": "#FFCC00", "parent": "finance",
     "doc_types": ["pension", "benefits"]},
    {"slug": "bank_statement", "icon": "Building2", "color": "#34AADC", "parent": "finance",
     "doc_types": ["bank_statement", "bank"]},
    {"slug": "invoice", "icon": "Receipt", "color": "#FF3B30", "parent": "finance", "doc_types": ["invoice"]},
    {"slug": "guardianship", "icon": "Gavel", "color": "#FF9500", "parent": "finance",
     "doc_types": ["guardianship"]},

    # -- Housing & Vehicle --
    {"slug": "housing_vehicle", "icon": "Home", "color": "#34C759", "parent": None, "doc_types": []},
    {"slug": "mortgage_housing", "icon": "Home", "color": "#007AFF", "parent": "housing_vehicle",
     "doc_types": ["mortgage", "housing", "notarial"]},
    {"slug": "vehicle", "icon": "Car", "color": "#FF6B35", "parent": "housing_vehicle", "doc_types": ["vehicle"]},
    {"slug": "rental_contract", "icon": "Key", "color": "#34C759", "parent": "housing_vehicle", "doc_types": []},

    # -- Insurance & Care --
    {"slug": "insurance_care", "icon": "Shield", "color": "#4CD964", "parent": None, "doc_types": []},
    {"slug": "insurance", "icon": "Shield", "color": "#4CD964", "parent": "insurance_care",
     "doc_types": ["policy", "insurance"]},
    {"slug": "medical_care", "icon": "HeartPulse", "color": "#5AC8FA", "parent": "insurance_care",
     "doc_types": ["medical", "care"]},

    # -- Work & Education --
    {"slug": "work_education", "icon": "Briefcase", "color": "#5856D6", "parent": None, "doc_types": []},
    {"slug": "employment_contract", "icon": "FileText", "color": "#5856D6", "parent": "work_education",
     "doc_types": ["contract"]},
    {"slug": "education", "icon": "GraduationCap", "color": "#5856D6", "parent": "work_education",
     "doc_types": ["education"]},
    {"slug": "cv_references", "icon": "User", "color": "#5856D6", "parent": "work_education", "doc_types": ["cv"]},

    # -- Government & Identity --
    {"slug": "government_identity", "icon": "Shield", "color": "#8E8E93", "parent": None, "doc_types": []},
    {"slug": "government", "icon": "Landmark", "color": "#8E8E93", "parent": "government_identity",
     "doc_types": ["government"]},
    {"slug": "identity_document", "icon": "CreditCard", "color": "#8E8E93", "parent": "government_identity",
     "doc_types": ["identity_document"]},
    {"slug": "notarial", "icon": "Scale", "color": "#8E8E93", "parent": "government_identity", "doc_types": []},

    # -- Other --
    {"slug": "other_group", "icon": "Inbox", "color": "#8E8E93", "parent": None, "doc_types": []},
    {"slug": "correspondence", "icon": "Mail", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["correspondence"]},
    {"slug": "other_documents", "icon": "File", "color": "#8E8E93", "parent": "other_group",
     "doc_types": ["other", "legal"]},
]

DOC_TYPE_TO_CATEGORY_SLUG: dict[str, str] = {
    doc_type: cat["slug"] for cat in DOCUMENT_CATEGORIES for doc_type in cat["doc_types"]
}

VALID_DOC_TYPES: frozenset[str] = frozenset(DOC_TYPE_TO_CATEGORY_SLUG) | {"other"}
```

Note `"legal"` (the one doc_type from the old 5-type set with no direct v2 equivalent) is folded into `other_documents` rather than dropped — existing behavior for anything the model classifies as `legal` is preserved (it still gets *a* category), just not a dedicated one.

- [ ] **Step 4: Write the migration**

Run: `cd services/api && python -m alembic heads` first to reconfirm `d1a4e7f9c2b6` is still what the live database is actually on (re-run the `SELECT version_num FROM alembic_version` check from this plan's Global Constraints against the live database if this local check disagrees — the live database is the source of truth, not the file tree, given the known stray-heads situation).

Create `services/api/alembic/versions/a1b2c3d4e5f6_create_categories_table.py` (generate a real revision id the normal way — `alembic revision` — rather than reusing this literal placeholder):

```python
"""create categories table

Revision ID: a1b2c3d4e5f6
Revises: d1a4e7f9c2b6
Create Date: 2026-07-10 00:00:00.000000

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from api.document_categories import DOCUMENT_CATEGORIES

revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'd1a4e7f9c2b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'categories',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=255), nullable=False),
        sa.Column('category_type', sa.String(length=50), nullable=False),
        sa.Column('icon', sa.String(length=100), nullable=True),
        sa.Column('color', sa.String(length=50), nullable=True),
        sa.Column('parent_id', UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('slug', 'category_type', name='uq_category_slug_type'),
    )
    op.add_column(
        'documents',
        sa.Column('category_id', UUID(as_uuid=True), sa.ForeignKey('categories.id', ondelete='SET NULL'), nullable=True),
    )

    categories_table = sa.table(
        'categories',
        sa.column('id', UUID(as_uuid=True)),
        sa.column('name', sa.String),
        sa.column('slug', sa.String),
        sa.column('category_type', sa.String),
        sa.column('icon', sa.String),
        sa.column('color', sa.String),
        sa.column('parent_id', UUID(as_uuid=True)),
    )

    slug_to_id: dict[str, uuid.UUID] = {cat["slug"]: uuid.uuid4() for cat in DOCUMENT_CATEGORIES}

    op.bulk_insert(
        categories_table,
        [
            {
                "id": slug_to_id[cat["slug"]],
                "name": cat["slug"],
                "slug": cat["slug"],
                "category_type": "document",
                "icon": cat["icon"],
                "color": cat["color"],
                "parent_id": slug_to_id[cat["parent"]] if cat["parent"] else None,
            }
            for cat in DOCUMENT_CATEGORIES
        ],
    )


def downgrade() -> None:
    op.drop_column('documents', 'category_id')
    op.drop_table('categories')
```

Seeding inside the migration itself (rather than a separately-run script, which is how v2 did it) means the taxonomy ships and applies atomically with the schema — nobody can run the migration and forget the seed step, and `alembic downgrade` cleanly removes both.

- [ ] **Step 5: Run the migration against a scratch database and verify the round trip**

Run: `cd services/api && python -m alembic upgrade head` (against the isolated scratch-dir Postgres this project's established testing discipline uses, not the live database yet).
Expected: succeeds, `SELECT count(*) FROM categories WHERE category_type='document'` returns 25 (6 parents + 19 children — recount against the actual `DOCUMENT_CATEGORIES` list length once Step 3 is final, this number must match exactly).

Run: `python -m alembic downgrade -1` then `python -m alembic upgrade head` again.
Expected: both succeed cleanly (confirms `downgrade()` is correct, not just `upgrade()`).

- [ ] **Step 6: Run the full backend suite**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS (no existing test references `categories` yet, so this just confirms the new column/table doesn't break anything already there).

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/models.py services/api/src/api/document_categories.py services/api/alembic/versions/a1b2c3d4e5f6_create_categories_table.py
git commit -m "feat: add Category model + documents.category_id, seeded with the full v2-derived taxonomy

Ported from CollaBrains v2 (support-cb/Cbrains-v2 on Codeberg) --
6 parent groups, ~19 subcategories, full richness kept (not trimmed).
Slugs are English identifiers; display names route through i18n on
the frontend rather than being hardcoded here, unlike v2's approach."
```

---

### Task 2: Expand classification + auto-categorization

**Files:**
- Modify: `services/api/src/api/document_classification.py`
- Test: `services/api/tests/test_document_classification.py`

**Interfaces:**
- Consumes: `api.document_categories.VALID_DOC_TYPES`, `api.document_categories.DOC_TYPE_TO_CATEGORY_SLUG` (Task 1).
- Produces: `classify_and_persist()` now also sets `document.category_id` when a match is found.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_document_classification.py`:

```python
async def test_classify_document_accepts_the_full_expanded_taxonomy():
    user = await _create_user(_unique("classifyrichuser"))
    fake = '{"doc_type": "payslip", "tags": [], "correspondent": null, "confidence": 0.9}'
    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        result = await classify_document(text="whatever", user_id=user.id)

    assert result is not None
    assert result.doc_type == "payslip"


async def test_classify_and_persist_sets_category_from_doc_type():
    from sqlalchemy import select
    from api.models import Category

    user = await _create_user(_unique("classifycatuser"))
    document = await _create_document(user.id)
    fake = '{"doc_type": "payslip", "tags": [], "correspondent": null, "confidence": 0.9}'

    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        async with async_session() as db:
            updated = await classify_and_persist(
                db, document_id=document.id, text=document.ocr_text, user_id=user.id
            )

    assert updated is not None
    assert updated.category_id is not None

    async with async_session() as db:
        category = (
            await db.execute(select(Category).where(Category.id == updated.category_id))
        ).scalar_one()
    assert category.slug == "payslip"


async def test_classify_and_persist_falls_back_to_other_documents_category_for_unmapped_doc_type():
    from sqlalchemy import select
    from api.models import Category

    user = await _create_user(_unique("classifyfallbackuser"))
    document = await _create_document(user.id)
    fake = '{"doc_type": "other", "tags": [], "correspondent": null, "confidence": 0.2}'

    with patch("api.document_classification.chat_completion", AsyncMock(return_value=fake)):
        async with async_session() as db:
            updated = await classify_and_persist(
                db, document_id=document.id, text=document.ocr_text, user_id=user.id
            )

    async with async_session() as db:
        category = (
            await db.execute(select(Category).where(Category.id == updated.category_id))
        ).scalar_one()
    assert category.slug == "other_documents"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd services/api && python -m pytest tests/test_document_classification.py -k "expanded_taxonomy or sets_category or falls_back" -v`
Expected: FAIL — `payslip` isn't in the current `VALID_DOC_TYPES`, so it gets coerced to `"other"`; `category_id` doesn't get set at all yet.

- [ ] **Step 3: Implement**

In `services/api/src/api/document_classification.py`, replace the hardcoded `VALID_DOC_TYPES` and prompt with the imported taxonomy:

```python
from api.document_categories import DOC_TYPE_TO_CATEGORY_SLUG, VALID_DOC_TYPES
```

Remove the old `VALID_DOC_TYPES = {"invoice", "contract", "correspondence", "legal", "other"}` line entirely (now imported).

Update `CLASSIFICATION_PROMPT` to list the real enum instead of the old 5-value one:

```python
CLASSIFICATION_PROMPT = """Classify the following document. Return ONLY a JSON object \
(no prose, no markdown fences) with this shape:

{{"doc_type": one of {doc_types}, \
"tags": [str, ...], "correspondent": str|null, "confidence": float}}

"tags" should be short, lowercase keywords (max 5). "correspondent" is the sender/counterparty \
name if identifiable, otherwise null. "confidence" is 0.0-1.0, your confidence in "doc_type".

Document:
{text}"""
```

Update `classify_document()` to interpolate the type list into the prompt:

```python
async def classify_document(*, text: str, user_id: UUID) -> DocumentClassification | None:
    """Classify `text` via the AI Gateway. Returns None on unparseable model output
    (graceful degradation, same as memory.py/entity_agent.py -- a bad classification
    call must never crash the document pipeline it's a subscriber of)."""
    prompt = CLASSIFICATION_PROMPT.format(
        doc_types=" | ".join(f'"{t}"' for t in sorted(VALID_DOC_TYPES)), text=text[:8000],
    )
    raw = await chat_completion(
        [{"role": "user", "content": prompt}], user_id=user_id, endpoint="document.classify", json_mode=True
    )
    return _parse_classification(raw)
```

Add the auto-categorization helper and wire it into `classify_and_persist`:

```python
async def _category_id_for_doc_type(db: AsyncSession, doc_type: str) -> UUID | None:
    from sqlalchemy import select
    from api.models import Category

    slug = DOC_TYPE_TO_CATEGORY_SLUG.get(doc_type, "other_documents")
    category = (
        await db.execute(select(Category).where(Category.slug == slug, Category.category_type == "document"))
    ).scalar_one_or_none()
    return category.id if category is not None else None


async def classify_and_persist(db: AsyncSession, *, document_id: UUID, text: str, user_id: UUID) -> Document | None:
    document = await db.get(Document, document_id)
    if document is None:
        return None

    result = await classify_document(text=text, user_id=user_id)
    if result is None:
        return document

    document.doc_type = result.doc_type
    document.tags = result.tags
    document.correspondent = result.correspondent
    document.classification_confidence = result.confidence
    document.category_id = await _category_id_for_doc_type(db, result.doc_type)
    await db.commit()
    await db.refresh(document)
    return document
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd services/api && python -m pytest tests/test_document_classification.py -v`
Expected: PASS, all tests including the pre-existing ones (the old 5 doc_types are all still valid — this is a superset expansion, nothing was removed, so `test_classify_document_returns_valid_parsed_output`'s `"invoice"` assertion and `test_classify_document_defaults_unknown_doc_type_to_other`'s `"not-a-real-type"` case both still behave identically).

- [ ] **Step 5: Run the full backend suite**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/document_classification.py services/api/tests/test_document_classification.py
git commit -m "feat: classify against the full document-category taxonomy, auto-assign category_id

Same single json_mode AI call as before, just offered the real ~25-type
enum instead of the old 5-type placeholder. Auto-categorization mirrors
v2's tasks.py pattern: doc_type maps to a category slug via a static
dict built from the same seed data the migration used, falling back to
other_documents for anything unmapped."
```

---

### Task 3: `GET /categories` endpoint

**Files:**
- Modify: `services/api/src/api/documents.py` (or a new `categories_router.py` if `documents.py` is already large — check its current line count first and decide; either is acceptable, this task doesn't mandate one over the other)
- Test: matching test file for wherever the endpoint lands

**Interfaces:**
- Produces: `GET /categories?category_type=document` → `list[CategoryOut]` where `CategoryOut = {id, slug, icon, color, parent_id}` (no `name` field — the frontend derives the display label from `slug` via i18n, per this plan's Global Constraints, so shipping the placeholder English `name` value over the wire would invite it to get rendered by mistake).

- [ ] **Step 1: Check `documents.py`'s current size to decide router placement**

Run: `wc -l services/api/src/api/documents.py`. If it's already large (a few hundred lines), create `services/api/src/api/categories_router.py` as its own small router (matching this project's established pattern of splitting routers by resource, e.g. `manager_router.py`, `admin_router.py`) and register it in `services/api/src/api/main.py` alongside the other routers. If it's small, adding one endpoint to `documents.py` directly is fine.

- [ ] **Step 2: Write the failing test**

Add a new test (in the test file matching wherever Step 1 puts the endpoint):

```python
async def test_list_categories_returns_the_document_taxonomy(client):
    token = await _login(client)  # reuse this file's existing login helper
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.get("/categories", headers=headers, params={"category_type": "document"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) > 20  # the full taxonomy, not a trimmed placeholder
    slugs = {c["slug"] for c in body}
    assert "payslip" in slugs
    assert "medical_care" in slugs
    assert all("name" not in c for c in body)
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `cd services/api && python -m pytest tests/ -k list_categories -v`
Expected: FAIL with a 404 (route doesn't exist yet).

- [ ] **Step 4: Implement the endpoint**

```python
class CategoryOut(BaseModel):
    id: UUID
    slug: str
    icon: str | None
    color: str | None
    parent_id: UUID | None


@router.get("/categories", response_model=list[CategoryOut])
async def list_categories(
    category_type: str = "document",
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Category]:
    result = await db.execute(select(Category).where(Category.category_type == category_type).order_by(Category.name))
    return list(result.scalars().all())
```

(Adjust imports at the top of whichever file this lands in: `Category` from `api.models`, `select` from `sqlalchemy`, `get_current_user` from `api.auth` — check what's already imported there before adding duplicates.)

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd services/api && python -m pytest tests/ -k list_categories -v`
Expected: PASS.

- [ ] **Step 6: Run the full backend suite**

Run: `cd services/api && python -m pytest tests/ -x`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add <whichever files Step 1/4 touched>
git commit -m "feat: GET /categories endpoint for the frontend category filter"
```

---

### Task 4: Frontend — category names in i18n + filter UI on Workspace

**Files:**
- Modify: `apps/web/src/locales/en.json`, `apps/web/src/locales/nl.json`, `apps/web/src/locales/de.json`, `apps/web/src/lib/api.ts`, `apps/web/src/routes/Workspace.tsx`
- Test: `apps/web/src/routes/Workspace.test.tsx`

**Interfaces:**
- Consumes: `GET /categories` (Task 3).
- Produces: a `categories` i18n namespace (25 keys, one per slug); `listCategories(): Promise<CategoryOut[]>` in `api.ts`; a second `FilterChips` row on `Workspace.tsx` for category, alongside the existing status one.

- [ ] **Step 1: Add the `categories` namespace to all three locale files**

In `apps/web/src/locales/en.json`, add (English names, matching the slugs 1:1 — this is the base/fallback language):

```json
"categories": {
  "finance": "Finance",
  "payslip": "Payslip & Salary",
  "tax": "Tax",
  "pension_benefits": "Pension & Benefits",
  "bank_statement": "Bank Statements",
  "invoice": "Invoices",
  "guardianship": "Guardianship",
  "housing_vehicle": "Housing & Vehicle",
  "mortgage_housing": "Mortgage & Housing",
  "vehicle": "Vehicle",
  "rental_contract": "Rental Contract",
  "insurance_care": "Insurance & Care",
  "insurance": "Insurance",
  "medical_care": "Medical & Care",
  "work_education": "Work & Education",
  "employment_contract": "Employment Contract",
  "education": "Education & Diploma",
  "cv_references": "CV & References",
  "government_identity": "Government & Identity",
  "government": "Government Documents",
  "identity_document": "Identity Documents",
  "notarial": "Notarial",
  "other_group": "Other",
  "correspondence": "Correspondence",
  "other_documents": "Other Documents"
}
```

In `apps/web/src/locales/nl.json`, add the same keys with the **original v2 Dutch names** (this is the one language where the port is a direct restoration of v2's actual wording, not a fresh translation):

```json
"categories": {
  "finance": "Financiën",
  "payslip": "Loonstrook & Salaris",
  "tax": "Belasting",
  "pension_benefits": "Pensioen & Uitkering",
  "bank_statement": "Bankafschriften",
  "invoice": "Facturen",
  "guardianship": "Bewindvoering",
  "housing_vehicle": "Woning & Voertuig",
  "mortgage_housing": "Hypotheek & Woning",
  "vehicle": "Voertuig",
  "rental_contract": "Huurcontract",
  "insurance_care": "Verzekering & Zorg",
  "insurance": "Verzekering",
  "medical_care": "Zorg & Medisch",
  "work_education": "Werk & Opleiding",
  "employment_contract": "Arbeidscontract",
  "education": "Opleiding & Diploma",
  "cv_references": "CV & Referenties",
  "government_identity": "Overheid & Identiteit",
  "government": "Overheidsdocumenten",
  "identity_document": "Identiteitsdocumenten",
  "notarial": "Notarieel",
  "other_group": "Overig",
  "correspondence": "Correspondentie",
  "other_documents": "Overige documenten"
}
```

In `apps/web/src/locales/de.json`, add the same keys translated to German:

```json
"categories": {
  "finance": "Finanzen",
  "payslip": "Gehaltsabrechnung & Lohn",
  "tax": "Steuern",
  "pension_benefits": "Rente & Leistungen",
  "bank_statement": "Kontoauszüge",
  "invoice": "Rechnungen",
  "guardianship": "Betreuung",
  "housing_vehicle": "Wohnen & Fahrzeug",
  "mortgage_housing": "Hypothek & Wohnen",
  "vehicle": "Fahrzeug",
  "rental_contract": "Mietvertrag",
  "insurance_care": "Versicherung & Pflege",
  "insurance": "Versicherung",
  "medical_care": "Medizin & Pflege",
  "work_education": "Arbeit & Bildung",
  "employment_contract": "Arbeitsvertrag",
  "education": "Ausbildung & Diplom",
  "cv_references": "Lebenslauf & Referenzen",
  "government_identity": "Behörden & Identität",
  "government": "Behördendokumente",
  "identity_document": "Ausweisdokumente",
  "notarial": "Notariell",
  "other_group": "Sonstiges",
  "correspondence": "Korrespondenz",
  "other_documents": "Sonstige Dokumente"
}
```

- [ ] **Step 2: Add `listCategories` to the API client**

In `apps/web/src/lib/api.ts`, add (matching the existing `listDocuments`-style pattern already in that file):

```typescript
export interface CategoryOut {
  id: string;
  slug: string;
  icon: string | null;
  color: string | null;
  parent_id: string | null;
}

export async function listCategories(categoryType = "document"): Promise<CategoryOut[]> {
  return request(`/categories?category_type=${categoryType}`);
}
```

(Match whatever the existing `request()` helper's exact call signature is in this file before writing this — copy the pattern from the adjacent `listDocuments` function rather than assuming.)

- [ ] **Step 3: Write the failing test**

Add to `apps/web/src/routes/Workspace.test.tsx`:

```typescript
it("filters by category using the category FilterChips row", async () => {
  vi.mocked(api.listCategories).mockResolvedValue([
    { id: "cat-1", slug: "payslip", icon: "Banknote", color: "#FF9500", parent_id: "cat-0" },
    { id: "cat-2", slug: "invoice", icon: "Receipt", color: "#FF3B30", parent_id: "cat-0" },
  ]);
  vi.mocked(api.listDocuments).mockResolvedValue([
    { ...DOC_FIXTURE, id: "d1", category_id: "cat-1" },
    { ...DOC_FIXTURE, id: "d2", category_id: "cat-2" },
  ]);

  renderPage();
  await screen.findByText(DOC_FIXTURE.title); // wait for initial load, adjust to this file's real fixture name

  fireEvent.click(await screen.findByText("Payslip & Salary"));

  expect(screen.getByText(/d1/)).toBeInTheDocument(); // adjust assertions to match this file's actual existing DOC_FIXTURE/title conventions once read directly
});
```

This step's exact fixture names (`DOC_FIXTURE`, mock document shape) must be copied from what `Workspace.test.tsx` already uses for its existing status-filter test — read that file's current content before writing this, rather than inventing fixture names that don't match.

- [ ] **Step 4: Run the test to verify it fails**

Run: `cd apps/web && pnpm exec vitest run src/routes/Workspace.test.tsx -t "category FilterChips"`
Expected: FAIL — no category filter row exists yet, `api.listCategories` isn't called.

- [ ] **Step 5: Implement**

In `apps/web/src/routes/Workspace.tsx`, add category state and a second `FilterChips` row, following the exact pattern the existing `statusFilters`/`STATUS_FILTER_OPTIONS` already establish in this file:

```typescript
const [categories, setCategories] = useState<CategoryOut[]>([]);
const [categoryFilters, setCategoryFilters] = useState<string[]>([]);
```

```typescript
useEffect(() => {
  listCategories().then(setCategories);
}, []);
```

```typescript
const CATEGORY_FILTER_OPTIONS = categories.map((c) => ({ id: c.id, label: t(`categories.${c.slug}`) }));
```

Extend `filteredDocuments`'s `useMemo` to also filter by `categoryFilters` (`documents.filter((doc) => activeFilters.has(doc.status) && (categoryFilters.length === 0 || (doc.category_id && categoryFilters.includes(doc.category_id))))` — adjust to match this file's actual current filter-composition style once read directly, don't assume the exact existing variable names without checking).

Render a second `<FilterChips>` immediately below the existing status one, using `CATEGORY_FILTER_OPTIONS`/`categoryFilters`/`setCategoryFilters` in place of the status equivalents.

Add `category_id: string | null` to the `DocumentOut` type in `api.ts` if it isn't already there (it should be, given the backend model already has the column from Task 1 — check `DocumentOut`'s current field list before assuming it needs adding).

- [ ] **Step 6: Run the test to verify it passes**

Run: `cd apps/web && pnpm exec vitest run src/routes/Workspace.test.tsx`
Expected: PASS, including all pre-existing tests in this file (unchanged).

- [ ] **Step 7: Run the full frontend suite**

Run against the live container, per this project's established pattern: `docker exec collabrains-web-1 sh -c 'cd /app/apps/web && pnpm exec vitest run'`
Expected: PASS, full count.

- [ ] **Step 8: Deploy and verify live**

Sync all Task 1-4 backend/frontend files to the live containers, run the migration against the live database (`docker exec collabrains-api-1 python -m alembic upgrade head` — the established pattern, not a fresh `docker compose exec`), rebuild the frontend, and do a real Playwright check: upload or pick an existing document, trigger classification, confirm a real category chip appears and filtering by it actually narrows the document list — not just that the unit tests pass in isolation.

- [ ] **Step 9: Write the ADR and commit**

Write `docs/adr/00XX-document-categories.md` (check `docs/adr/` for the next free number at execution time) covering: the v2 taxonomy port, the i18n-names-instead-of-hardcoded-strings improvement, the auto-categorization mechanism, and the live verification performed.

```bash
git add apps/web/src/locales/ apps/web/src/lib/api.ts apps/web/src/routes/Workspace.tsx apps/web/src/routes/Workspace.test.tsx docs/adr/00XX-document-categories.md
git commit -m "feat: category filter on the Documents page, i18n'd category names

Closes out the document-categories port (see
docs/superpowers/plans/2026-07-10-document-categories.md): the full
v2-derived taxonomy is now selectable as a second filter dimension
alongside status, with names routed through i18n instead of hardcoded
per-language strings baked into seed data."
```
