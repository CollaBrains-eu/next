# Address Recall and Fragmentation Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Fix two live-discovered address-extraction quality gaps: the LLM sometimes never proposes a clearly-formatted address as a candidate at all (recall), and sometimes splits one real address across two separate entity items in a single extraction (fragmentation).

**Architecture:** A deterministic regex fallback scan (`address_parser.find_full_address_matches`) runs over the full document text after the LLM extraction, feeding any missed high-confidence addresses through the existing `_get_or_create_address_entity` dedup pipeline. A new same-batch merge step then combines exactly-two complementary address fragments from a single extraction call, reusing the gap-fill rule already used elsewhere in this pipeline and logging to the existing `EntityMergeLog` audit table.

**Tech Stack:** FastAPI, SQLAlchemy async, pytest/pytest-asyncio.

## Global Constraints

- The fallback scan uses only the strict `_FULL_NL_RE`/`_FULL_DE_RE` patterns (all four address parts present) — never the looser postal-only or street-only patterns, to avoid false positives on arbitrary document prose (invoice numbers, case numbers, etc.).
- The fragment merge only fires when a single extraction call produced **exactly 2** address entities, and only when one is a street-fragment and the other is a postal-fragment with no overlap — anything else (0, 1, or 3+ address entities; two already-complete-looking addresses) is left alone.
- Merge gap-fills only — never overwrites an already-populated `AddressDetail` field, matching the rule already used throughout this pipeline.
- Every merge writes an `EntityMergeLog` row (`merged_by` = the document's owner) — same audit trail the existing manual-merge endpoint produces.

---

### Task 1: `find_full_address_matches` — deterministic recall scan

**Files:**
- Modify: `services/api/src/api/address_parser.py`
- Test: `services/api/tests/test_address_parser.py`

**Interfaces:**
- Produces: `find_full_address_matches(text: str) -> list[str]` — used by Task 2.

- [x] **Step 1: Write the failing tests**

Append to `services/api/tests/test_address_parser.py`:

```python
from api.address_parser import build_maps_url, find_full_address_matches, parse_address


def test_find_full_address_matches_finds_address_in_surrounding_prose():
    text = "Informationen zu Ihrem Termin\n\nWo?\nJahnstr. 6, 26789 Leer\nRaum: Wartebereich"
    assert find_full_address_matches(text) == ["Jahnstr. 6, 26789 Leer"]


def test_find_full_address_matches_returns_empty_list_when_no_full_address():
    text = "Bitte bringen Sie Ihr Ausweisdokument mit. Halten Sie Ihre Rentenversicherungsnummer bereit."
    assert find_full_address_matches(text) == []


def test_find_full_address_matches_ignores_bare_numbers_in_prose():
    text = "Zie pagina 5 voor meer informatie, artikel 12 lid 3 is van toepassing."
    assert find_full_address_matches(text) == []
```

Note: the existing `from api.address_parser import build_maps_url, parse_address` import line at the top of the file should be replaced with the three-name import shown above (don't add a second import line).

- [x] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest tests/test_address_parser.py -k find_full_address -v`
Expected: FAIL with `ImportError: cannot import name 'find_full_address_matches'`

- [x] **Step 3: Implement**

In `services/api/src/api/address_parser.py`, add after `parse_address` (before `build_maps_url`):

```python
def find_full_address_matches(text: str) -> list[str]:
    """Scan raw text for high-confidence full address matches (street+number+
    postal+city together) -- a recall safety net for addresses the LLM's
    semantic pass didn't propose as a candidate at all. Deliberately uses
    only the strict _FULL_NL_RE/_FULL_DE_RE patterns (all four parts
    present), not the looser postal-only or street-only fallbacks
    parse_address() also tries -- scanning arbitrary document prose with a
    loose pattern would flag invoice numbers, case numbers, etc. as false
    positives.
    """
    matches = []
    for regex in (_FULL_NL_RE, _FULL_DE_RE):
        for match in regex.finditer(text):
            matches.append(match.group(0).strip())
    return matches
```

- [x] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest tests/test_address_parser.py -v`
Expected: PASS (all tests in the file, including the 3 new ones and the pre-existing ones).

- [x] **Step 5: Commit**

```bash
git add services/api/src/api/address_parser.py services/api/tests/test_address_parser.py
git commit -m "feat: add deterministic full-address recall scan"
```

---

### Task 2: Wire the fallback scan into extraction

**Files:**
- Modify: `services/api/src/api/entity_agent.py`
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `find_full_address_matches(text: str) -> list[str]` (Task 1); existing `_get_or_create_address_entity(db, item, owner_id) -> Entity | None`.
- Produces: `extract_entities()` now also creates address entities for full addresses present in the raw text but absent from the LLM's entity list.

- [x] **Step 1: Write the failing test**

Append to `services/api/tests/test_entities.py` (after the existing contact-detail tests, before `test_extraction_fills_structured_fields_when_llm_leaves_them_null`):

```python
async def test_recall_scan_creates_address_missed_by_llm(client):
    """Live bug found 2026-07-23: a clean, well-formatted address present in the
    document text was never proposed as a candidate entity by the LLM at all."""
    token = await _login(client, "entityuser-recallscan")
    headers = {"Authorization": f"Bearer {token}"}
    document_text = "Wo?\nJahnstr. 6, 26789 Leer\nRaum: Wartebereich beim Empfang"
    document_id = await _upload_ready_document(client, headers, document_text)
    fake = '{"entities": [], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "address"
    assert entities[0]["maps_url"] is not None
```

- [x] **Step 2: Run test to verify it fails**

Run: `docker compose exec api pytest tests/test_entities.py::test_recall_scan_creates_address_missed_by_llm -v`
Expected: FAIL with `assert 0 == 1` (no entities created — the LLM's empty response is currently the end of the story).

- [x] **Step 3: Implement**

In `services/api/src/api/entity_agent.py`, update the import from `address_parser`:

```python
from api.address_parser import find_full_address_matches, parse_address
```

In `extract_entities()`, insert a new block immediately after the main `for item in raw_entities:` loop, before the `if address_entity_ids:` residency-detection block:

```python
    existing_address_names = {e.name.strip().lower() for e in persisted if e.entity_type == "address"}
    for match in find_full_address_matches(text):
        if match.strip().lower() in existing_address_names:
            continue
        entity = await _get_or_create_address_entity(db, {"name": match}, user_id)
        if entity is None:
            continue
        existing_address_names.add(match.strip().lower())
        if entity.id not in {e.id for e in persisted}:
            persisted.append(entity)
            address_entity_ids.append(entity.id)
        await _add_mention_if_missing(db, entity_id=entity.id, document_id=document_id)
```

- [x] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest tests/test_entities.py -k recall_scan -v`
Expected: PASS.

Run: `docker compose exec api pytest tests/test_entities.py -v 2>&1 | tail -20`
Expected: same pass/fail counts as before this task (the 9 pre-existing pollution failures, all new/prior feature tests passing) — confirms no regression.

- [x] **Step 5: Commit**

```bash
git add services/api/src/api/entity_agent.py services/api/tests/test_entities.py
git commit -m "feat: wire deterministic address recall scan into extraction"
```

---

### Task 3: Same-batch complementary address merge

**Files:**
- Modify: `services/api/src/api/entity_agent.py`
- Test: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `AddressDetail`, `EntityMergeLog`, `EntityMention` (existing models); `address_entity_ids: list[UUID]` and `persisted: list[Entity]` (produced by Task 2's extended loop).
- Produces: `_maybe_merge_complementary_address_fragments(db, address_entity_ids, persisted, user_id) -> list[UUID]` — returns the possibly-shortened list of address entity ids for `extract_entities()` to use for residency detection.

- [x] **Step 1: Write the failing tests**

Append to `services/api/tests/test_entities.py`:

```python
async def test_fragmented_address_from_form_fields_merges_into_one_entity(client):
    """Live bug found 2026-07-23: a Dutch form with labeled fields ("Straatnaam: Gaslaan 16"
    ... "Postcode en woonplaats: 9671CT Winschoten") caused the LLM to emit two separate
    entity items -- one street-only, one postal-only -- for what is really one address."""
    token = await _login(client, "entityuser-fragmerge1")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "form")
    fake = (
        '{"entities": [{"name": "Gaslaan 16", "type": "address", "street": "Gaslaan", '
        '"house_number": "16", "postal_code": null, "city": null, "country": null}, '
        '{"name": "9671CT Winschoten", "type": "address", "street": null, "house_number": null, '
        '"postal_code": "9671CT", "city": "Winschoten", "country": null}], "relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    assert entities[0]["maps_url"] is not None

    from api.db import async_session
    from api.models import AddressDetail, EntityMergeLog
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(AddressDetail).where(AddressDetail.entity_id == entities[0]["id"]))
        detail = result.scalar_one()
        merge_log = await db.execute(select(EntityMergeLog).where(EntityMergeLog.target_entity_id == entities[0]["id"]))
        assert merge_log.scalar_one_or_none() is not None
    assert detail.street == "Gaslaan"
    assert detail.house_number == "16"
    assert detail.postal_code == "9671CT"
    assert detail.city == "Winschoten"


async def test_two_distinct_addresses_in_one_document_are_not_merged(client):
    """A rental contract with a landlord address and a property address must stay
    separate -- both already look complete-ish (each has street+house_number), so
    neither matches the complementary-fragment shape the merge requires."""
    token = await _login(client, "entityuser-fragmerge2")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "contract")
    fake = (
        '{"entities": [{"name": "Landlordstraat 1", "type": "address", "street": "Landlordstraat", '
        '"house_number": "1", "postal_code": "1000AA", "city": "Amsterdam", "country": null}, '
        '{"name": "Propertylaan 2", "type": "address", "street": "Propertylaan", "house_number": "2", '
        '"postal_code": "2000BB", "city": "Rotterdam", "country": null}], "relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert len(response.json()) == 2
```

- [x] **Step 2: Run tests to verify they fail**

Run: `docker compose exec api pytest tests/test_entities.py -k fragmerge -v`
Expected: `test_fragmented_address_from_form_fields_merges_into_one_entity` FAILS with `assert 2 == 1`; `test_two_distinct_addresses_in_one_document_are_not_merged` PASSES already (nothing merges them yet, which happens to be correct) — that's fine, it becomes a real regression guard once Task 3's merge logic exists.

- [x] **Step 3: Implement**

In `services/api/src/api/entity_agent.py`, update the models import to add `EntityMergeLog`:

```python
from api.models import AddressDetail, Category, ContactDetail, Document, Entity, EntityMention, EntityMergeLog, EntityRelationship, Residency
```

Add a new helper after `_upsert_contact_detail` (before `_update_residency`):

```python
def _is_street_fragment(detail: AddressDetail) -> bool:
    return bool(detail.street or detail.house_number) and not (detail.postal_code and detail.city)


def _is_postal_fragment(detail: AddressDetail) -> bool:
    return bool(detail.postal_code or detail.city) and not (detail.street and detail.house_number)


async def _maybe_merge_complementary_address_fragments(
    db: AsyncSession, *, address_entity_ids: list[UUID], persisted: list[Entity], user_id: UUID
) -> list[UUID]:
    """If a single extraction call produced exactly 2 address entities, and one is a
    street-only fragment while the other is a postal/city-only fragment, they almost
    certainly describe the same real-world address split across two labeled form
    fields (e.g. "Straatnaam: Gaslaan 16" / "Postcode en woonplaats: 9671CT
    Winschoten") -- merge them. Two candidates that already look complete-ish (e.g.
    a landlord address and a property address on a rental contract) never match
    this shape and are correctly left separate. Gap-fills only, same rule as
    _get_or_create_address_entity, and logs to EntityMergeLog like the manual-merge
    endpoint does.
    """
    if len(address_entity_ids) != 2:
        return address_entity_ids

    kept_id, absorbed_id = address_entity_ids[0], address_entity_ids[1]
    kept_detail = await db.get(AddressDetail, kept_id)
    absorbed_detail = await db.get(AddressDetail, absorbed_id)
    if kept_detail is None or absorbed_detail is None:
        return address_entity_ids

    is_complementary = (
        (_is_street_fragment(kept_detail) and _is_postal_fragment(absorbed_detail))
        or (_is_postal_fragment(kept_detail) and _is_street_fragment(absorbed_detail))
    )
    if not is_complementary:
        return address_entity_ids

    for field in ("street", "house_number", "postal_code", "city", "country"):
        if getattr(kept_detail, field) is None and getattr(absorbed_detail, field) is not None:
            setattr(kept_detail, field, getattr(absorbed_detail, field))
    kept_detail.normalized_key = _normalize_address_key(
        {
            "postal_code": kept_detail.postal_code, "house_number": kept_detail.house_number,
            "street": kept_detail.street,
        }
    )

    mentions_result = await db.execute(select(EntityMention).where(EntityMention.entity_id == absorbed_id))
    for mention in mentions_result.scalars().all():
        await _add_mention_if_missing(db, entity_id=kept_id, document_id=mention.document_id)
        # Not explicitly deleting `mention` here -- entity_mentions.entity_id has
        # ondelete="CASCADE", so deleting absorbed_entity below removes it at the DB
        # level. An explicit ORM-level delete too raced with that cascade and logged
        # a "0 rows matched" SAWarning (found running this task's own tests).

    db.add(EntityMergeLog(source_entity_id=absorbed_id, target_entity_id=kept_id, merged_by=user_id))
    absorbed_entity = await db.get(Entity, absorbed_id)
    if absorbed_entity is not None:
        # Deleting the Entity is enough -- AddressDetail.entity_id has ondelete="CASCADE",
        # so explicitly deleting absorbed_detail too would double-delete the same row
        # through both the ORM and the DB cascade.
        await db.delete(absorbed_entity)
    await db.flush()

    persisted[:] = [e for e in persisted if e.id != absorbed_id]
    return [kept_id]
```

In `extract_entities()`, replace:

```python
    if address_entity_ids:
        if category_slug in RESIDENCE_CATEGORY_SLUGS:
```

with:

```python
    address_entity_ids = await _maybe_merge_complementary_address_fragments(
        db, address_entity_ids=address_entity_ids, persisted=persisted, user_id=user_id
    )

    if address_entity_ids:
        if category_slug in RESIDENCE_CATEGORY_SLUGS:
```

- [x] **Step 4: Run tests to verify they pass**

Run: `docker compose exec api pytest tests/test_entities.py -k fragmerge -v`
Expected: PASS (both tests).

Run: `docker compose exec api pytest tests/test_entities.py tests/test_address_parser.py tests/test_contact_parser.py tests/test_residencies.py -v 2>&1 | tail -20`
Expected: same 9 pre-existing pollution failures as before this task, all feature tests (old and new) passing — confirms no regression.

- [x] **Step 5: Commit**

```bash
git add services/api/src/api/entity_agent.py services/api/tests/test_entities.py
git commit -m "feat: merge complementary address fragments from the same extraction batch"
```

---

### Task 4: Deploy and verify

**Files:** none (operational task)

- [x] **Step 1: Sync changed files to the server**

The server's working tree at `/opt/collabrains` is kept in sync with local via direct file copy (its own git history has diverged and is a known, separately-tracked issue — not something to fix as part of this task). Sync each changed file individually, matching its exact relative path (never rsync multiple sources into one destination directory):

```bash
rsync -av services/api/src/api/address_parser.py root@178.254.22.178:/opt/collabrains/services/api/src/api/address_parser.py
rsync -av services/api/src/api/entity_agent.py root@178.254.22.178:/opt/collabrains/services/api/src/api/entity_agent.py
rsync -av services/api/tests/test_address_parser.py root@178.254.22.178:/opt/collabrains/services/api/tests/test_address_parser.py
rsync -av services/api/tests/test_entities.py root@178.254.22.178:/opt/collabrains/services/api/tests/test_entities.py
```

- [x] **Step 2: Run the full related test suite on the server**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T api pytest tests/test_address_parser.py tests/test_contact_parser.py tests/test_entities.py tests/test_residencies.py -v"
```

Expected: same 9 pre-existing pollution failures documented throughout this session's work, everything else passing. If `ModuleNotFoundError: No module named 'api'` appears, the container's editable install was lost on a recreate (a known recurring issue) — fix with `docker compose exec -T api sh -c 'cd /app && uv pip install --system --no-cache -e .'` and re-run.

- [x] **Step 3: Verify production health**

```bash
ssh root@178.254.22.178 "curl -s -o /dev/null -w 'HTTP %{http_code}\n' https://collabrains.eu/"
ssh root@178.254.22.178 "docker ps --format 'table {{.Names}}\t{{.Status}}'"
```

Expected: `HTTP 200`; all containers `Up`/`healthy`.

- [x] **Step 4: Live-verify against the real document that originally surfaced the recall gap**

Write this throwaway script locally (same pattern as the earlier live-verification scripts this session used):

```python
# /tmp/verify_recall_fix.py -- delete from the server after running
import asyncio
from uuid import UUID

from api.db import async_session
from api.entity_agent import extract_entities
from api.models import Document

DOCUMENT_ID = UUID("74906559-13c7-448a-88cd-deeeeb7fe041")


async def main():
    async with async_session() as db:
        doc = await db.get(Document, DOCUMENT_ID)
        entities = await extract_entities(db, document_id=DOCUMENT_ID, text=doc.ocr_text, user_id=doc.owner_id)
        for e in entities:
            print(f"  - {e.entity_type}: {e.name!r} (status={e.status})")


asyncio.run(main())
```

```bash
rsync -av /tmp/verify_recall_fix.py root@178.254.22.178:/opt/collabrains/services/api/verify_recall_fix.py
ssh root@178.254.22.178 "cd /opt/collabrains && timeout 280 docker compose exec -T api python /app/verify_recall_fix.py"
ssh root@178.254.22.178 "rm -f /opt/collabrains/services/api/verify_recall_fix.py"
```

Expected: the printed entity list now includes an `address` entity (in addition to the 3 organizations seen in the first live-verification run this session) — confirm via `docker compose exec -T postgres psql -U collabrains -d collabrains -c "select street, house_number, postal_code, city from address_details ad join entities e on e.id = ad.entity_id where e.name ilike '%Jahnstr%';"` that it has `street='Jahnstr.'`, `house_number='6'`, `postal_code='26789'`, `city='Leer'`.

- [x] **Step 5: Commit and push**

```bash
git log --oneline -5
git push origin main
```

Expected: all 3 feature commits plus the earlier spec commit push cleanly to `origin/main`.
