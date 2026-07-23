# Reliable Entity Extraction + Maps Links Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make automatic address/organization entity extraction actually reliable (structured fields populated, no garbage entities, a working residency timeline, no duplicate fragments), add maps links surfaced in the web UI and Signal, then extend auto-extraction to person/location entities now that the guardrails exist to do so safely.

**Architecture:** Split address recognition (LLM, semantic: "is this text an address?") from address parsing (new deterministic regex module: "what are its fields?"). Add a code-level classification guardrail before any address/person entity is created. Fix the residency-timeline trigger using live evidence of why it's never fired. Fix duplicate-fragment dedup. Surface maps links in both the REST API and a new Signal notification.

**Tech Stack:** FastAPI (`services/api`), SQLAlchemy + Alembic, pytest, React/TypeScript (`apps/web`), Ollama via the existing `api.ai_gateway.chat_completion`.

## Global Constraints

- Server: `root@178.254.22.178` (`/opt/collabrains`). `api` runs `uvicorn --reload` against a bind mount — Python changes apply automatically; a new Alembic migration needs `docker compose exec api alembic upgrade head` explicitly; frontend changes need `docker compose exec web sh -c 'cd /app/apps/web && npx vite build'` (established project pattern, see `docs/deployment/ai-optimization.md` and prior deploy history).
- This backend test suite shares one live Postgres with no per-test transaction rollback — every new test must use a `_unique(...)`-suffixed username/street/etc. (see `test_residencies.py`'s own docstring on this), matching the existing convention in `test_entities.py`/`test_residencies.py`/`test_entity_merge.py`.
- `entity_agent.py`'s existing dedup/entity-status contract (rejected = permanently suppressed, pending_review/confirmed both reusable) must not change — only what data feeds into it and how addresses specifically get matched.
- Real production evidence this plan fixes (verify against, not just unit tests, once deployed): only 1/15 `AddressDetail` rows have any structured field populated; several are misclassified garbage (email/URL/person-salutation text); zero `Residency` rows exist despite the feature being wired since 2026-07-11; "Gaslaan 16" exists as two separate fragmented entities.

---

### Task 1: `address_parser.py` — deterministic address field parsing + maps link builder

**Files:**
- Create: `services/api/src/api/address_parser.py`
- Test: `services/api/tests/test_address_parser.py`

**Interfaces:**
- Produces: `parse_address(raw_text: str) -> dict[str, str | None]` (keys: `street`, `house_number`, `postal_code`, `city`, `country`) and `build_maps_url(*, street, house_number, postal_code, city, country) -> str | None`. Both are pure functions, no I/O, no DB — Task 2 imports and calls them.

- [x] **Step 1: Write the failing tests**

Create `services/api/tests/test_address_parser.py`:

```python
from api.address_parser import build_maps_url, parse_address


def test_parses_street_and_house_number_only():
    assert parse_address("Achterweg 15") == {
        "street": "Achterweg", "house_number": "15",
        "postal_code": None, "city": None, "country": None,
    }


def test_parses_nl_postal_code_and_city_only():
    assert parse_address("9671 CT WINSCHOTEN") == {
        "street": None, "house_number": None,
        "postal_code": "9671 CT", "city": "WINSCHOTEN", "country": "NL",
    }


def test_parses_de_postal_code_and_city_only():
    assert parse_address("26831 Bunde") == {
        "street": None, "house_number": None,
        "postal_code": "26831", "city": "Bunde", "country": "DE",
    }


def test_parses_full_nl_address_in_one_string():
    result = parse_address("Gaslaan 16, 9671 CT Winschoten")
    assert result == {
        "street": "Gaslaan", "house_number": "16",
        "postal_code": "9671 CT", "city": "Winschoten", "country": "NL",
    }


def test_parses_full_address_without_comma():
    result = parse_address("Gaslaan 16 9671 CT Winschoten")
    assert result["street"] == "Gaslaan"
    assert result["house_number"] == "16"
    assert result["postal_code"] == "9671 CT"
    assert result["city"] == "Winschoten"


def test_unparseable_text_returns_all_none():
    assert parse_address("Beschermingsbewind@vkb.nl") == {
        "street": None, "house_number": None,
        "postal_code": None, "city": None, "country": None,
    }


def test_build_maps_url_from_full_address():
    url = build_maps_url(
        street="Gaslaan", house_number="16", postal_code="9671 CT",
        city="Winschoten", country="NL",
    )
    assert url == (
        "https://www.google.com/maps/search/?api=1&query="
        "Gaslaan%2016%2C%209671%20CT%2C%20Winschoten%2C%20NL"
    )


def test_build_maps_url_returns_none_for_insufficient_data():
    assert build_maps_url(street=None, house_number=None, postal_code=None, city=None, country="NL") is None
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/tests/test_address_parser.py root@178.254.22.178:/opt/collabrains/services/api/tests/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_address_parser.py -v"
```
Expected: `ModuleNotFoundError: No module named 'api.address_parser'` (or collection error) for every test.

- [x] **Step 3: Write the implementation**

Create `services/api/src/api/address_parser.py`:

```python
"""Deterministic address parsing + maps-link building.

Splits address *recognition* (entity_agent.py's LLM call: "is this text an
address?") from *parsing* (this module: "what are its structured fields?").
Live production data showed the LLM reliably spots address-shaped text but
almost never fills in the structured fields itself (1/15 real extractions
had any field populated) -- see
docs/superpowers/specs/2026-07-23-reliable-entity-extraction-maps-design.md.
A small local model doing both semantic identification AND precise field
splitting in one pass is the likely cause; this module does the splitting
with plain regex instead, which is far more reliable for the fixed,
recognizable NL/DE postal-code formats this app's real documents use.

Scoped to NL ("9671 CT", 4 digits + 2 letters) and DE ("26831", 5 digits)
formats only -- the two seen in production so far, not a general
international address parser (YAGNI).
"""
import re
from urllib.parse import quote

_NL_POSTAL = r"\d{4}\s?[A-Z]{2}"
_DE_POSTAL = r"\d{5}"
_STREET_NUMBER = r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ.\-' ]*?\s+\d+[A-Za-z]?"
_TRAILING_NUMBER = re.compile(r"\d+[A-Za-z]?$")

_FULL_NL_RE = re.compile(rf"({_STREET_NUMBER}),?\s+({_NL_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_FULL_DE_RE = re.compile(rf"({_STREET_NUMBER}),?\s+({_DE_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_POSTAL_CITY_NL_RE = re.compile(rf"({_NL_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_POSTAL_CITY_DE_RE = re.compile(rf"({_DE_POSTAL})\s+([A-Za-zÀ-ÿ\-' ]+)", re.IGNORECASE)
_STREET_NUMBER_RE = re.compile(rf"({_STREET_NUMBER})", re.IGNORECASE)


def _split_street_number(street_number: str) -> tuple[str, str | None]:
    number_match = _TRAILING_NUMBER.search(street_number)
    if not number_match:
        return street_number.strip(), None
    return street_number[: number_match.start()].strip(), number_match.group(0)


def parse_address(raw_text: str) -> dict[str, str | None]:
    """Best-effort split of an address-shaped string into structured fields.
    Any field not confidently parsed stays None -- never guessed."""
    text = raw_text.strip()
    result: dict[str, str | None] = {
        "street": None, "house_number": None, "postal_code": None, "city": None, "country": None,
    }

    for regex, country in ((_FULL_NL_RE, "NL"), (_FULL_DE_RE, "DE")):
        match = regex.search(text)
        if match:
            street, house_number = _split_street_number(match.group(1).strip())
            result["street"] = street
            result["house_number"] = house_number
            result["postal_code"] = match.group(2).upper() if country == "NL" else match.group(2)
            result["city"] = match.group(3).strip()
            result["country"] = country
            return result

    for regex, country in ((_POSTAL_CITY_NL_RE, "NL"), (_POSTAL_CITY_DE_RE, "DE")):
        match = regex.search(text)
        if match:
            result["postal_code"] = match.group(1).upper() if country == "NL" else match.group(1)
            result["city"] = match.group(2).strip()
            result["country"] = country
            return result

    street_match = _STREET_NUMBER_RE.search(text)
    if street_match:
        street, house_number = _split_street_number(street_match.group(1).strip())
        if house_number:
            result["street"] = street
            result["house_number"] = house_number

    return result


def build_maps_url(
    *, street: str | None, house_number: str | None, postal_code: str | None,
    city: str | None, country: str | None,
) -> str | None:
    """Google Maps universal search link -- works with or without the app
    installed, no API key needed. Returns None if there isn't enough data
    to build a meaningful query (callers must not show/send a link then)."""
    if not any([street, postal_code, city]):
        return None
    parts = [
        " ".join(p for p in (street, house_number) if p) or None,
        postal_code,
        city,
        country,
    ]
    query = ", ".join(p for p in parts if p)
    return f"https://www.google.com/maps/search/?api=1&query={quote(query)}"
```

- [x] **Step 4: Run tests to verify they pass**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_address_parser.py -v"
```
Expected: all PASSED.

- [x] **Step 5: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/address_parser.py services/api/tests/test_address_parser.py
git commit -m "Add deterministic address_parser module (regex-based, NL/DE) + maps link builder

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 2: Classification guardrail + wire address_parser into entity_agent.py

**Files:**
- Modify: `services/api/src/api/entity_agent.py`
- Modify: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: `address_parser.parse_address` (Task 1).
- Produces: `_get_or_create_address_entity` now rejects garbage candidates before creating an `Entity`, and fills structured fields from `parse_address` whenever the LLM left them null.

- [x] **Step 1: Write the failing tests**

Add to `services/api/tests/test_entities.py` (reuses this file's existing `_login`/`_upload_ready_document` helpers):

```python
async def test_extraction_rejects_email_as_address(client):
    token = await _login(client, "entityuser-emailreject")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "contact us")
    fake = (
        '{"entities": [{"name": "user@example.com", "type": "address"}], "relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_extraction_rejects_url_as_address(client):
    token = await _login(client, "entityuser-urlreject")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "visit us")
    fake = '{"entities": [{"name": "www.example.com", "type": "address"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_extraction_rejects_person_salutation_as_address(client):
    token = await _login(client, "entityuser-salutationreject")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "letter")
    fake = '{"entities": [{"name": "t.a.v. mevrouw A. Thole", "type": "address"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    assert response.json() == []


async def test_extraction_fills_structured_fields_when_llm_leaves_them_null(client):
    """The live bug this fixes: the LLM's schema-constrained output is often
    {"name": "Achterweg 15", "type": "address", "street": null, ...} --
    address_parser must fill the gaps from the name string."""
    token = await _login(client, "entityuser-fillfields")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "letter")
    fake = (
        '{"entities": [{"name": "Achterweg 15", "type": "address", "street": null, '
        '"house_number": null, "postal_code": null, "city": null, "country": null}], '
        '"relationships": []}'
    )

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1

    from api.db import async_session
    from api.models import AddressDetail
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(AddressDetail).where(AddressDetail.entity_id == entities[0]["id"]))
        detail = result.scalar_one()
    assert detail.street == "Achterweg"
    assert detail.house_number == "15"
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/tests/test_entities.py root@178.254.22.178:/opt/collabrains/services/api/tests/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_entities.py -v -k 'reject or fillfields'"
```
Expected: the reject tests FAIL (entities list is non-empty, garbage entity was created); the fillfields test FAILS (`detail.street` is `None`, not `"Achterweg"`).

- [x] **Step 3: Write the implementation**

In `services/api/src/api/entity_agent.py`, add the import and guardrail near the top (after existing imports):

```python
import re

from api.address_parser import parse_address
```

Add after `CONTRACT_CATEGORY_SLUGS` (after line 39):

```python
# Code-level guardrail, not prompt-only -- this project's own established lesson
# (ai_gateway.py's json_mode docstring) is that prompt instructions alone are not
# reliable on a small local model. Live production data had an email, a URL, and a
# person-salutation line all extracted as entity_type="address" despite the prompt
# explicitly saying "Do not extract people's names."
_GARBAGE_ADDRESS_RE = re.compile(
    r"@|https?://|www\.|\bt\.a\.v\.|\bde heer\b|\bmevrouw\b|\bdhr\.|\bmw\.",
    re.IGNORECASE,
)


def _looks_like_garbage_address(name: str) -> bool:
    return bool(_GARBAGE_ADDRESS_RE.search(name))
```

Replace `_get_or_create_address_entity` (lines 131-162) with:

```python
async def _get_or_create_address_entity(db: AsyncSession, item: dict, owner_id: UUID) -> Entity | None:
    """Same contract as `_get_or_create_entity`, but dedups address entities by
    normalized structured fields (still scoped to `owner_id`) instead of exact name
    match -- two LLM extractions of the same real address rarely render as identical
    text. Rejects candidates that look like an email/URL/person-salutation before
    ever creating an Entity row (see _looks_like_garbage_address)."""
    raw_name = str(item.get("name") or "").strip()
    if _looks_like_garbage_address(raw_name):
        logger.info("entity_agent: rejected garbage address candidate %r", raw_name)
        return None

    parsed = parse_address(raw_name)
    # Prefer the LLM's own structured fields when present (schema-constrained, so
    # at least well-typed when given), fall back to the deterministic parser for
    # whatever it left null -- live data showed the LLM leaves these null far more
    # often than it fills them.
    filled_item = {
        "name": raw_name,
        "street": item.get("street") or parsed["street"],
        "house_number": item.get("house_number") or parsed["house_number"],
        "postal_code": item.get("postal_code") or parsed["postal_code"],
        "city": item.get("city") or parsed["city"],
        "country": item.get("country") or parsed["country"],
    }

    normalized_key = _normalize_address_key(filled_item)
    result = await db.execute(
        select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
            AddressDetail.normalized_key == normalized_key, Entity.owner_id == owner_id
        )
    )
    entity = result.scalar_one_or_none()
    if entity is not None:
        if entity.status == "rejected":
            return None
        return entity

    entity = Entity(name=raw_name or normalized_key, entity_type="address", owner_id=owner_id)
    db.add(entity)
    await db.flush()
    db.add(
        AddressDetail(
            entity_id=entity.id,
            street=filled_item["street"],
            house_number=filled_item["house_number"],
            postal_code=filled_item["postal_code"],
            city=filled_item["city"],
            country=filled_item["country"],
            normalized_key=normalized_key,
        )
    )
    return entity
```

- [x] **Step 4: Run tests to verify they pass**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_entities.py -v"
```
Expected: all PASSED (both new and pre-existing tests in this file).

- [x] **Step 5: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/entity_agent.py services/api/tests/test_entities.py
git commit -m "Add code-level garbage-address guardrail, wire address_parser into extraction

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 3: Fix the residency-timeline trigger (broaden RESIDENCE_CATEGORY_SLUGS + diagnostic logging)

**Files:**
- Modify: `services/api/src/api/entity_agent.py`
- Modify: `services/api/tests/test_residencies.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `_update_residency` now also fires for `correspondence`/`other_documents` categories (where live data shows real addresses actually land, given `document_classification.py`'s current precision), and logs a diagnostic line whenever an address is extracted but the category still doesn't match — so this specific silent-failure class is visible in logs next time, not just discoverable via a live DB query.

**Root cause (already diagnosed, not re-investigated here)**: live production query joining `AddressDetail`/`EntityMention`/`Document`/`Category` showed **zero** of the 13 address-producing documents had a category in the original `RESIDENCE_CATEGORY_SLUGS = {"identity_document", "mortgage_housing", "rental_contract", "government"}` — all were `employment_contract`, `other_documents`, `education`, `correspondence`, or `medical_care`. Separately, `other_documents` holds 49 of ~74 total documents (66%) — `document_classification.py`'s classifier defaults to this generic bucket far more than to specific categories. The categories themselves are valid and current (confirmed against `document_categories.py`'s `DOCUMENT_CATEGORIES` list) — this is a classifier-precision gap, not a stale-slug bug.

- [x] **Step 1: Write the failing test**

Add to `services/api/tests/test_residencies.py` (reuses this file's existing `_address_extraction`/`_create_document`/`_current_residency` helpers):

```python
async def test_extracting_address_from_correspondence_document_creates_residency(client):
    """Real production evidence: zero documents were ever classified into the
    original RESIDENCE_CATEGORY_SLUGS, but 'correspondence' and 'other_documents'
    both held genuine home-address extractions -- see
    docs/superpowers/specs/2026-07-23-reliable-entity-extraction-maps-design.md."""
    username = _unique("residencyuser-correspondence")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="correspondence")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            persisted = await extract_entities(db, document_id=document_id, text="letter", user_id=user.id)

    assert len(persisted) == 1
    residency = await _current_residency(user.id)
    assert residency is not None
    assert residency.address_entity_id == persisted[0].id


async def test_extracting_address_from_other_documents_creates_residency(client):
    username = _unique("residencyuser-otherdocs")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="other_documents")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            persisted = await extract_entities(db, document_id=document_id, text="doc", user_id=user.id)

    assert len(persisted) == 1
    residency = await _current_residency(user.id)
    assert residency is not None


async def test_extracting_address_from_employment_contract_does_not_create_residency(client):
    """Unchanged behavior: an employer's address on an employment contract is not
    residency evidence -- employment_contract stays out of the trigger set."""
    username = _unique("residencyuser-employment")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="employment_contract")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="contract", user_id=user.id)

    residency = await _current_residency(user.id)
    assert residency is None
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/tests/test_residencies.py root@178.254.22.178:/opt/collabrains/services/api/tests/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py -v -k 'correspondence or otherdocs'"
```
Expected: both new "creates residency" tests FAIL (`residency is None`).

- [x] **Step 3: Write the implementation**

In `services/api/src/api/entity_agent.py`, replace the `RESIDENCE_CATEGORY_SLUGS` definition (line 38):

```python
# Documents where an extracted address is very likely the user's own current
# address, not a third party's (e.g. a landlord on a rental contract, or a
# store on an invoice) -- residency detection only fires for these, contract
# documents get linked to the resulting residency period once it exists.
#
# "correspondence" and "other_documents" were added 2026-07-23 after live
# production data showed zero real documents were ever classified into the
# original four slugs, while both of these held genuine home-address
# extractions -- document_classification.py's classifier currently defaults
# to "other_documents" for 66% of all documents, so excluding it left this
# feature permanently dark. See
# docs/superpowers/specs/2026-07-23-reliable-entity-extraction-maps-design.md.
RESIDENCE_CATEGORY_SLUGS = {
    "identity_document", "mortgage_housing", "rental_contract", "government",
    "correspondence", "other_documents",
}
```

Add diagnostic logging in `extract_entities`, replacing the residency-trigger block (lines 268-272):

```python
    if address_entity_ids:
        if category_slug in RESIDENCE_CATEGORY_SLUGS:
            # Ambiguous which address is the user's own if several were found
            # (e.g. landlord + property on one rental contract) -- take the
            # first, still `pending_review` so a human can correct it.
            await _update_residency(db, user_id=user_id, address_entity_id=address_entity_ids[0], document_id=document_id)
        else:
            logger.info(
                "entity_agent: address extracted from document %s (category=%r) did not "
                "trigger residency detection -- category not in RESIDENCE_CATEGORY_SLUGS",
                document_id, category_slug,
            )
```

- [x] **Step 4: Run tests to verify they pass**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py -v"
```
Expected: all PASSED, including the pre-existing `test_extracting_address_from_identity_document_creates_residency` (unchanged behavior for the original 4 slugs).

- [x] **Step 5: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/entity_agent.py services/api/tests/test_residencies.py
git commit -m "Broaden RESIDENCE_CATEGORY_SLUGS to categories addresses actually land in

Live data: zero of 13 address-producing documents had a category in the
original 4-slug set; correspondence/other_documents held genuine home
addresses instead (other_documents alone is 66% of all documents).
Residency detection has never produced a row in production despite being
wired since 2026-07-11 -- this is why. Added diagnostic logging for the
remaining non-matching case so this doesn't silently regress again.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 4: Dedup/merge fix — enrich partial matches instead of fragmenting

**Files:**
- Modify: `services/api/src/api/entity_agent.py`
- Modify: `services/api/tests/test_residencies.py`

**Interfaces:**
- Consumes: Task 2's `filled_item` structure (already has parsed fields by the time this runs).
- Produces: `_get_or_create_address_entity` now matches an existing `AddressDetail` via a priority-ordered fallback (postal_code+house_number, then street+house_number, then exact name) and fills gaps on the matched row instead of always requiring one exact `normalized_key`.

**Real bug this fixes**: the live "Gaslaan 16" address exists as two separate `AddressDetail` rows for the same user — one with all fields `None` (created before this plan's Task 2 fix), one fully structured. Once Task 2 ships, *new* extractions will have fields properly populated, but two prior partial extractions of the same real address would still fragment under the old exact-`normalized_key`-only matching, since `normalized_key` is computed from whatever fields happen to be present each time.

- [x] **Step 1: Write the failing test**

Add to `services/api/tests/test_residencies.py`:

```python
async def test_partial_and_full_extraction_of_same_address_merge_not_fragment(client):
    """Regression test for the live 'two Gaslaan 16 rows' bug: a postal_code+
    house_number match should fill in missing fields on the existing row, not
    create a second Entity for the same real address."""
    username = _unique("residencyuser-mergegap")
    await _login(client, username)
    user = await _user(username)
    street = _unique_street()

    doc1 = await _create_document(user.id, category_slug="correspondence")
    # First extraction: only postal_code + house_number known (street/city missing --
    # simulates the LLM leaving fields null, before address_parser had anything to work
    # with in the raw name).
    fake_partial = json.dumps({
        "entities": [{
            "name": f"12, 1012AB", "type": "address",
            "street": None, "house_number": "12", "postal_code": "1012AB", "city": None, "country": None,
        }],
        "relationships": [],
    })
    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=fake_partial):
            first = await extract_entities(db, document_id=doc1, text="letter one", user_id=user.id)
    assert len(first) == 1

    doc2 = await _create_document(user.id, category_slug="correspondence")
    # Second extraction: full details for the same real address.
    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street, house_number="12", postal_code="1012AB")):
            second = await extract_entities(db, document_id=doc2, text="letter two", user_id=user.id)
    assert len(second) == 1

    # Must be the SAME entity, not a second fragment.
    assert second[0].id == first[0].id

    async with async_session() as db:
        result = await db.execute(select(AddressDetail).where(AddressDetail.entity_id == first[0].id))
        detail = result.scalar_one()
    assert detail.street == street
    assert detail.city == "Amsterdam"

    # Only one Entity total for this real address.
    async with async_session() as db:
        count_result = await db.execute(
            select(func.count()).select_from(AddressDetail).where(AddressDetail.entity_id == first[0].id)
        )
    assert count_result.scalar_one() == 1
```

Add `from sqlalchemy import func` to this test file's imports if not already present (check the existing `from sqlalchemy import select` line and extend it to `from sqlalchemy import func, select`).

- [x] **Step 2: Run test to verify it fails**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/tests/test_residencies.py root@178.254.22.178:/opt/collabrains/services/api/tests/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py -v -k mergegap"
```
Expected: FAIL — `second[0].id != first[0].id` (two separate entities created).

- [x] **Step 3: Write the implementation**

In `services/api/src/api/entity_agent.py`, add a new `_find_matching_address_entity` helper, then replace the entire `_get_or_create_address_entity` function (as left by Task 2) with a version that calls it:

```python
async def _find_matching_address_entity(db: AsyncSession, filled_item: dict, owner_id: UUID) -> Entity | None:
    """Priority-ordered partial match, most-reliable signal first. Returns the
    first entity found whose AddressDetail matches on the given fields -- both
    rows must have non-empty values for the fields being compared (an empty
    field never counts as a match)."""
    postal = (filled_item.get("postal_code") or "").strip().lower()
    house = (filled_item.get("house_number") or "").strip().lower()
    street = (filled_item.get("street") or "").strip().lower()

    if postal and house:
        result = await db.execute(
            select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
                func.lower(AddressDetail.postal_code) == postal,
                func.lower(AddressDetail.house_number) == house,
                Entity.owner_id == owner_id,
            )
        )
        entity = result.scalar_one_or_none()
        if entity is not None:
            return entity

    if street and house:
        result = await db.execute(
            select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
                func.lower(AddressDetail.street) == street,
                func.lower(AddressDetail.house_number) == house,
                Entity.owner_id == owner_id,
            )
        )
        entity = result.scalar_one_or_none()
        if entity is not None:
            return entity

    normalized_key = _normalize_address_key(filled_item)
    result = await db.execute(
        select(Entity).join(AddressDetail, AddressDetail.entity_id == Entity.id).where(
            AddressDetail.normalized_key == normalized_key, Entity.owner_id == owner_id
        )
    )
    return result.scalar_one_or_none()


async def _get_or_create_address_entity(db: AsyncSession, item: dict, owner_id: UUID) -> Entity | None:
    """Same contract as `_get_or_create_entity`, but dedups address entities by
    structured-field matching (priority-ordered, see _find_matching_address_entity)
    instead of exact name match. On a partial match, fills any gap on the existing
    row from the new extraction rather than creating a fragment -- never overwrites
    an already-populated field. Rejects candidates that look like an email/URL/
    person-salutation before ever creating an Entity row."""
    raw_name = str(item.get("name") or "").strip()
    if _looks_like_garbage_address(raw_name):
        logger.info("entity_agent: rejected garbage address candidate %r", raw_name)
        return None

    parsed = parse_address(raw_name)
    filled_item = {
        "name": raw_name,
        "street": item.get("street") or parsed["street"],
        "house_number": item.get("house_number") or parsed["house_number"],
        "postal_code": item.get("postal_code") or parsed["postal_code"],
        "city": item.get("city") or parsed["city"],
        "country": item.get("country") or parsed["country"],
    }

    entity = await _find_matching_address_entity(db, filled_item, owner_id)
    if entity is not None:
        if entity.status == "rejected":
            return None
        detail = await db.get(AddressDetail, entity.id)
        if detail is not None:
            changed = False
            for field in ("street", "house_number", "postal_code", "city", "country"):
                if getattr(detail, field) is None and filled_item[field] is not None:
                    setattr(detail, field, filled_item[field])
                    changed = True
            if changed:
                detail.normalized_key = _normalize_address_key(filled_item)
        return entity

    normalized_key = _normalize_address_key(filled_item)
    entity = Entity(name=raw_name or normalized_key, entity_type="address", owner_id=owner_id)
    db.add(entity)
    await db.flush()
    db.add(
        AddressDetail(
            entity_id=entity.id,
            street=filled_item["street"],
            house_number=filled_item["house_number"],
            postal_code=filled_item["postal_code"],
            city=filled_item["city"],
            country=filled_item["country"],
            normalized_key=normalized_key,
        )
    )
    return entity
```

- [x] **Step 4: Run tests to verify they pass**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py tests/test_entities.py -v"
```
Expected: all PASSED, including every pre-existing test in both files (this changes matching logic, not the public contract).

- [x] **Step 5: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/entity_agent.py services/api/tests/test_residencies.py
git commit -m "Fix address dedup to enrich partial matches instead of fragmenting

Regression test for the live bug: 'Gaslaan 16' existed as two separate
AddressDetail rows for the same user (one empty, one complete) because
matching required an exact normalized_key. Now matches on postal_code+
house_number first (most reliable), then street+house_number, then falls
back to the original exact-key match -- and fills gaps on a matched row
rather than creating a new fragment.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 5: Migration — fix Residency.address_entity_id FK cascade

**Files:**
- Create: `services/api/alembic/versions/<new_revision>_residency_address_entity_cascade.py`

**Interfaces:** None (schema-only change, no application code touches this behavior directly).

**Real bug this fixes**: `entities.py`'s `merge_entities` (line 310, `await db.delete(source)`) has no entity-type check and no check for an existing `Residency` row pointing at the entity being deleted. Every other FK from this schema to `entities.id` (`AddressDetail.entity_id`, `EntityMention.entity_id`, `EntityRelationship.*_entity_id`) specifies `ondelete="CASCADE"` — `Residency.address_entity_id` (`models.py:400`) is the one exception, so merging an address entity that backs a residency currently raises an unhandled `IntegrityError` (500). Not reachable through any frontend today (merge isn't exposed in the UI), but worth closing before it becomes reachable.

- [x] **Step 1: Find the current Alembic head**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api python3 -c \"
import asyncio
from sqlalchemy import text
from api.db import async_session

async def main():
    async with async_session() as db:
        result = await db.execute(text('SELECT version_num FROM alembic_version'))
        print(result.scalar_one())

asyncio.run(main())
\""
```
Expected output at time of writing: `c4d7f2a9e1b3` — but re-run this rather than trusting the value here, since Tasks 1-4 don't add migrations but other work may have landed on `main` since this plan was written.

- [x] **Step 2: Write the migration**

Create `services/api/alembic/versions/a1b2c3d4e5f6_residency_address_entity_cascade.py` (generate a real revision id the same way existing migrations do, or use this placeholder-format one — Alembic only requires it be unique):

```python
"""residency address_entity_id cascade delete

Revision ID: a1b2c3d4e5f6
Revises: c4d7f2a9e1b3
Create Date: 2026-07-23

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'c4d7f2a9e1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('residencies_address_entity_id_fkey', 'residencies', type_='foreignkey')
    op.create_foreign_key(
        'residencies_address_entity_id_fkey', 'residencies', 'entities',
        ['address_entity_id'], ['id'], ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('residencies_address_entity_id_fkey', 'residencies', type_='foreignkey')
    op.create_foreign_key(
        'residencies_address_entity_id_fkey', 'residencies', 'entities',
        ['address_entity_id'], ['id'],
    )
```

Also update `services/api/src/api/models.py`'s `Residency.address_entity_id` (line 400) to match, so future fresh-DB test setups get the same constraint:

```python
    address_entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False
    )
```

**Constraint name confirmed live** (2026-07-23, `docker compose exec postgres psql -U collabrains -d collabrains -c '\d residencies'`): `residencies_address_entity_id_fkey` — matches what Step 2's migration already references, no adjustment needed.

- [x] **Step 3: Apply and verify**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/alembic/versions/a1b2c3d4e5f6_residency_address_entity_cascade.py root@178.254.22.178:/opt/collabrains/services/api/alembic/versions/
rsync -avz services/api/src/api/models.py root@178.254.22.178:/opt/collabrains/services/api/src/api/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api alembic upgrade head"
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T postgres psql -U collabrains -d collabrains -c \"\\d residencies\" | grep -i foreign"
```
Expected: the FK now shows `ON DELETE CASCADE`.

- [x] **Step 4: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/alembic/versions/a1b2c3d4e5f6_residency_address_entity_cascade.py services/api/src/api/models.py
git commit -m "Fix Residency.address_entity_id FK to cascade-delete like every other entities.id FK

merge_entities unconditionally deletes the source entity with no check for
an existing Residency row pointing at it -- every other FK to entities.id
(AddressDetail, EntityMention, EntityRelationship) already cascades, this
was the one exception. Not reachable via any frontend today (merge isn't
exposed in the UI), closed before it becomes reachable.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 6: Maps link — backend field + frontend display

**Files:**
- Modify: `services/api/src/api/residencies_router.py`
- Modify: `services/api/src/api/entities.py`
- Modify: `services/api/tests/test_residencies.py`
- Modify: `apps/web/src/lib/api.ts`
- Modify: `apps/web/src/components/AddressHistory.tsx`
- Modify: `apps/web/src/routes/Entities.tsx`

**Interfaces:**
- Consumes: `address_parser.build_maps_url` (Task 1).
- Produces: `AddressOut.maps_url: str | None` (residencies), `EntityOut.maps_url: str | None` (entities, only non-null for `entity_type == "address"`).

- [x] **Step 1: Write the failing backend test**

Add to `services/api/tests/test_residencies.py`:

```python
async def test_residency_out_includes_maps_url_for_complete_address(client):
    username = _unique("residencyuser-mapsurl")
    await _login(client, username)
    user = await _user(username)
    document_id = await _create_document(user.id, category_slug="correspondence")
    street = _unique_street()

    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="letter", user_id=user.id)

    token = await _login(client, username)
    response = await client.get("/users/me/residencies", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["address"]["maps_url"] is not None
    assert body[0]["address"]["maps_url"].startswith("https://www.google.com/maps/search/?api=1&query=")
```

- [x] **Step 2: Run test to verify it fails**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/tests/test_residencies.py root@178.254.22.178:/opt/collabrains/services/api/tests/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py -v -k mapsurl"
```
Expected: FAIL — `KeyError: 'maps_url'`.

- [x] **Step 3: Write the backend implementation**

In `services/api/src/api/residencies_router.py`, add the import:

```python
from api.address_parser import build_maps_url
```

Update `AddressOut` (lines 29-36):

```python
class AddressOut(BaseModel):
    id: UUID
    name: str
    street: str | None
    house_number: str | None
    postal_code: str | None
    city: str | None
    country: str | None
    maps_url: str | None
```

Update `_to_out` (lines 59-82) to build it:

```python
async def _to_out(db: AsyncSession, residency: Residency) -> ResidencyOut:
    detail = await db.get(AddressDetail, residency.address_entity_id)
    entity_row = await db.get(Entity, residency.address_entity_id)
    count_result = await db.execute(
        select(func.count()).select_from(Document).where(Document.residency_id == residency.id)
    )
    return ResidencyOut(
        id=residency.id,
        address=AddressOut(
            id=residency.address_entity_id,
            name=entity_row.name if entity_row else "",
            street=detail.street if detail else None,
            house_number=detail.house_number if detail else None,
            postal_code=detail.postal_code if detail else None,
            city=detail.city if detail else None,
            country=detail.country if detail else None,
            maps_url=build_maps_url(
                street=detail.street if detail else None,
                house_number=detail.house_number if detail else None,
                postal_code=detail.postal_code if detail else None,
                city=detail.city if detail else None,
                country=detail.country if detail else None,
            ) if detail else None,
        ),
        valid_from=residency.valid_from,
        valid_to=residency.valid_to,
        status=residency.status,
        source_document_id=residency.source_document_id,
        linked_document_count=count_result.scalar_one(),
        created_at=residency.created_at,
    )
```

In `services/api/src/api/entities.py`, update `EntityOut` (lines 23-28) and populate it in `list_entities`/wherever entities are serialized. First add the import:

```python
from api.address_parser import build_maps_url
from api.models import AddressDetail, Document, Entity, EntityMention, EntityMergeLog, EntityRelationship, User
```

Update `EntityOut`:

```python
class EntityOut(BaseModel):
    id: UUID
    name: str
    entity_type: str
    status: str
    created_at: datetime
    maps_url: str | None = None

    @classmethod
    async def from_entity(cls, db: AsyncSession, entity: Entity) -> "EntityOut":
        maps_url = None
        if entity.entity_type == "address":
            detail = await db.get(AddressDetail, entity.id)
            if detail is not None:
                maps_url = build_maps_url(
                    street=detail.street, house_number=detail.house_number,
                    postal_code=detail.postal_code, city=detail.city, country=detail.country,
                )
        return cls(
            id=entity.id, name=entity.name, entity_type=entity.entity_type,
            status=entity.status, created_at=entity.created_at, maps_url=maps_url,
        )
```

`maps_url` needs an async DB lookup FastAPI's automatic ORM→Pydantic conversion can't do, so every handler that currently returns `Entity`/`list[Entity]` directly must instead call `EntityOut.from_entity(db, ...)` explicitly. `response_model` stays `EntityOut`/`list[EntityOut]` unchanged on every one of these — only the return statement changes. Six call sites, each shown in full (current code → new):

`extract_entities_from_document` (currently ends `return await extract_entities(db, document_id=document.id, text=document.ocr_text, user_id=document.owner_id)`) — replace with:
```python
    entities = await extract_entities(db, document_id=document.id, text=document.ocr_text, user_id=document.owner_id)
    return [await EntityOut.from_entity(db, e) for e in entities]
```

`list_entities` (currently ends `result = await db.execute(query)` / `return list(result.scalars().all())`) — replace with:
```python
    result = await db.execute(query)
    return [await EntityOut.from_entity(db, e) for e in result.scalars().all()]
```

`create_entity` (currently has two `return` points, lines 122 and 128) — replace both:
```python
    entity = existing.scalar_one_or_none()
    if entity is not None:
        if entity.status != "confirmed":
            entity.status = "confirmed"
            await db.commit()
            await db.refresh(entity)
        return await EntityOut.from_entity(db, entity)

    entity = Entity(name=name, entity_type=payload.entity_type, status="confirmed", owner_id=current_user.id)
    db.add(entity)
    await db.commit()
    await db.refresh(entity)
    return await EntityOut.from_entity(db, entity)
```

`approve_entity`/`reject_entity` (both currently `return await _transition_entity(db, entity_id, ..., current_user)`) — replace both:
```python
@router.post("/entities/{entity_id}/approve", response_model=EntityOut)
async def approve_entity(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> EntityOut:
    entity = await _transition_entity(db, entity_id, "confirmed", current_user)
    return await EntityOut.from_entity(db, entity)


@router.post("/entities/{entity_id}/reject", response_model=EntityOut)
async def reject_entity(
    entity_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> EntityOut:
    entity = await _transition_entity(db, entity_id, "rejected", current_user)
    return await EntityOut.from_entity(db, entity)
```

`bulk_review_entities` (currently builds `results: list[Entity]` and returns it) — replace with:
```python
@router.post("/entities/bulk-review", response_model=list[EntityOut])
async def bulk_review_entities(
    items: list[BulkReviewItem],
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_effective_user),
) -> list[EntityOut]:
    results: list[Entity] = []
    for item in items:
        new_status = "confirmed" if item.action == "approve" else "rejected"
        results.append(await _transition_entity(db, item.entity_id, new_status, current_user))
    return [await EntityOut.from_entity(db, e) for e in results]
```

`merge_entity` (currently `return await merge_entities(...)` inside the `try` block) — replace with:
```python
    try:
        merged = await merge_entities(
            db, target_id=target_id, source_id=request.source_entity_id, merged_by=current_user.id
        )
        return await EntityOut.from_entity(db, merged)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
```

- [x] **Step 4: Run tests to verify they pass**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py tests/test_entities.py tests/test_entity_merge.py -v"
```
Expected: all PASSED. If any pre-existing test asserts an exact response body shape without accounting for the new `maps_url: null` field, update its assertion to match (Pydantic includes `None`-valued optional fields in JSON output by default).

- [x] **Step 5: Frontend — update types and display**

In `apps/web/src/lib/api.ts`, update `AddressOut` (lines 1046-1054) and `EntityOut` (lines 375-ish, check exact current fields first):

```typescript
export interface AddressOut {
  id: string;
  name: string;
  street: string | null;
  house_number: string | null;
  postal_code: string | null;
  city: string | null;
  country: string | null;
  maps_url: string | null;
}
```

Add `maps_url: string | null;` to the existing `EntityOut` interface (keep every other field as-is).

In `apps/web/src/components/AddressHistory.tsx`, add a maps link next to the formatted address line. Replace the block at lines 99-106:

```tsx
            <div>
              <p className="font-medium text-ink">
                {residency.address.maps_url ? (
                  <a
                    href={residency.address.maps_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-accent hover:underline"
                  >
                    {formatAddressLine(residency)}
                  </a>
                ) : (
                  formatAddressLine(residency)
                )}
              </p>
              <p className="text-xs text-ink-3">
                {residency.valid_from ? formatDate(residency.valid_from) : "?"} &rarr;{" "}
                {residency.valid_to ? formatDate(residency.valid_to) : t("addressHistory.current")}
              </p>
            </div>
```

In `apps/web/src/routes/Entities.tsx`, fix the missing "address" color (the cosmetic gap found during investigation — `EntityGraph.tsx` already has one, this file didn't) — update `TYPE_STYLES` (lines 10-15):

```typescript
const TYPE_STYLES: Record<string, string> = {
  person: "bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-300",
  organization: "bg-purple-100 text-purple-800 dark:bg-purple-900/30 dark:text-purple-300",
  location: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  address: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  other: "bg-hover text-ink-2",
};
```

- [x] **Step 6: Run frontend tests**

```bash
cd ~/dev/collabrains-next
rsync -avz apps/web/src/lib/api.ts apps/web/src/components/AddressHistory.tsx apps/web/src/routes/Entities.tsx root@178.254.22.178:/opt/collabrains/apps/web/src/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T web pnpm test"
```
Expected: fails to typecheck/compile first — `apps/web/src/components/AddressHistory.test.tsx:20-25` has one `RESIDENCY: api.ResidencyOut` fixture missing the new required `maps_url` field. Add it:
```typescript
const RESIDENCY: api.ResidencyOut = {
  id: "res-1",
  address: {
    id: "addr-1", name: "Kerkstraat 12, Amsterdam", street: "Kerkstraat", house_number: "12",
    postal_code: "1012AB", city: "Amsterdam", country: "NL",
    maps_url: "https://www.google.com/maps/search/?api=1&query=Kerkstraat%2012%2C%201012AB%2C%20Amsterdam%2C%20NL",
  },
  valid_from: "2026-01-01",
  valid_to: null,
  status: "pending_review",
  source_document_id: "doc-1",
  // ...rest of the fixture unchanged
};
```
Then re-run. Expected: all PASSED.

- [x] **Step 7: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/residencies_router.py services/api/src/api/entities.py services/api/tests/test_residencies.py apps/web/src/lib/api.ts apps/web/src/components/AddressHistory.tsx apps/web/src/routes/Entities.tsx
git commit -m "Surface maps links for addresses in AddressHistory and entity API responses

Also fixes a small pre-existing cosmetic gap: Entities.tsx had no color for
the address type (fell back to generic gray) while EntityGraph.tsx already
did.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

- [x] **Step 8: Deploy frontend build**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T web sh -c 'cd /app/apps/web && npx vite build'"
curl -s -o /dev/null -w 'collabrains.eu -> %{http_code}\n' https://collabrains.eu/
```
Expected: `200`.

---

### Task 7: Signal notification when a residency is confirmed with a complete address

**Files:**
- Modify: `services/api/src/api/residencies_router.py`
- Modify: `services/api/tests/test_residencies.py`

**Interfaces:**
- Consumes: `api.signal_client.send_signal_message` (existing), `AddressOut.maps_url` (Task 6).
- Produces: `approve_residency` now sends a best-effort Signal notification when the confirmed residency's address has street/house_number/postal_code/city all populated.

- [x] **Step 1: Write the failing test**

Add to `services/api/tests/test_residencies.py`:

```python
async def test_approving_complete_residency_sends_signal_notification_with_maps_link(client):
    username = _unique("residencyuser-signalnotify")
    token = await _login(client, username)
    user = await _user(username)
    phone_number = f"+1555{uuid4().hex[:7]}"  # unique per run -- users.phone_number has a unique constraint
    async with async_session() as db:
        user_row = await db.get(User, user.id)
        user_row.phone_number = phone_number
        await db.commit()

    document_id = await _create_document(user.id, category_slug="correspondence")
    street = _unique_street()
    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=_address_extraction(street)):
            await extract_entities(db, document_id=document_id, text="letter", user_id=user.id)

    residency = await _current_residency(user.id)

    with patch("api.residencies_router.send_signal_message") as mock_send:
        response = await client.post(
            f"/residencies/{residency.id}/approve", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    mock_send.assert_called_once()
    call_args = mock_send.call_args
    assert call_args.args[0] == phone_number
    assert "maps.google.com" in call_args.args[1] or "google.com/maps" in call_args.args[1]


async def test_approving_incomplete_residency_does_not_send_notification(client):
    """Gating on completeness is deliberate -- a strictly-worse maps link isn't useful."""
    username = _unique("residencyuser-incompletenotify")
    token = await _login(client, username)
    user = await _user(username)
    async with async_session() as db:
        user_row = await db.get(User, user.id)
        user_row.phone_number = f"+1555{uuid4().hex[:7]}"
        await db.commit()

    document_id = await _create_document(user.id, category_slug="correspondence")
    fake_partial = json.dumps({
        "entities": [{
            "name": "Some City", "type": "address",
            "street": None, "house_number": None, "postal_code": None, "city": "Some City", "country": None,
        }],
        "relationships": [],
    })
    async with async_session() as db:
        with patch("api.entity_agent.chat_completion", return_value=fake_partial):
            await extract_entities(db, document_id=document_id, text="letter", user_id=user.id)

    residency = await _current_residency(user.id)

    with patch("api.residencies_router.send_signal_message") as mock_send:
        response = await client.post(
            f"/residencies/{residency.id}/approve", headers={"Authorization": f"Bearer {token}"}
        )

    assert response.status_code == 200
    mock_send.assert_not_called()
```

- [x] **Step 2: Run tests to verify they fail**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/tests/test_residencies.py root@178.254.22.178:/opt/collabrains/services/api/tests/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py -v -k notify"
```
Expected: FAIL — `send_signal_message` never called (`AttributeError`/`assert_called_once` failure), since `api.residencies_router.send_signal_message` doesn't exist yet as an importable name in that module.

- [x] **Step 3: Write the implementation**

In `services/api/src/api/residencies_router.py`, add imports:

```python
from api.signal_client import send_signal_message
```

Replace the `approve_residency` endpoint (lines 125-132):

```python
@router.post("/residencies/{residency_id}/approve", response_model=ResidencyOut)
async def approve_residency(
    residency_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ResidencyOut:
    residency = await _transition_residency(db, residency_id, "confirmed")
    out = await _to_out(db, residency)
    await _maybe_notify_confirmed_residency(db, residency, out)
    return out


async def _maybe_notify_confirmed_residency(db: AsyncSession, residency: Residency, out: ResidencyOut) -> None:
    """Best-effort (see signal_client.py's own contract) -- a Signal failure must
    never break the approve endpoint itself. Gated on the address having all of
    street/house_number/postal_code/city populated: a strictly-worse maps link
    isn't useful, and this doubles as a live signal that the extraction pipeline
    is actually producing complete data."""
    address = out.address
    if not all([address.street, address.house_number, address.postal_code, address.city]):
        return
    user = await db.get(User, residency.user_id)
    if user is None or not user.phone_number or not address.maps_url:
        return
    try:
        await send_signal_message(
            user.phone_number,
            f"Your address has been confirmed: {address.street} {address.house_number}, "
            f"{address.postal_code} {address.city}\n{address.maps_url}",
        )
    except Exception:
        logger.exception("residencies_router: failed to send residency-confirmed Signal notification")
```

Add `import logging` + `logger = logging.getLogger(__name__)` near the top of the file if not already present (check the existing imports first — this file currently has no logger).

- [x] **Step 4: Run tests to verify they pass**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_residencies.py -v"
```
Expected: all PASSED.

- [x] **Step 5: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/residencies_router.py services/api/tests/test_residencies.py
git commit -m "Send Signal notification with maps link when a residency is confirmed

Gated on the address being fully structured (street/house_number/
postal_code/city) -- a partial address isn't worth notifying about, and
this doubles as a live correctness signal for the extraction pipeline.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

### Task 8: Extend auto-extraction to person/location entities

**Files:**
- Modify: `services/api/src/api/entity_agent.py`
- Modify: `services/api/tests/test_entities.py`

**Interfaces:**
- Consumes: nothing new -- reuses the guardrail pattern established in Task 2, generalized.
- Produces: `AUTO_EXTRACTED_ENTITY_TYPES` now includes `"person"` and `"location"`.

**Do not start this task until Tasks 1-4 are deployed and verified against real production documents** (re-run the live diagnostic queries from this plan's Global Constraints section — structured-field population rate and residency-row count — and confirm they've actually improved). This directly reverses the 2026-07-09 decision to pull person/location back due to being "the dominant source of low-quality noise" (`entity_agent.py:26-31`) -- that decision predates any code-level guardrail existing at all (only prompt instructions), so Task 2's guardrail pattern is the actual prerequisite that makes revisiting it reasonable. Expanding scope before confirming the prerequisite fix works in practice would risk reintroducing the exact noise problem that caused the original pullback.

- [ ] **Step 1: Write the failing tests**

Add to `services/api/tests/test_entities.py`:

```python
async def test_person_entities_are_now_auto_extracted(client):
    token = await _login(client, "entityuser-personauto")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Letter from Jan de Vries.")
    fake = '{"entities": [{"name": "Jan de Vries", "type": "person"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "person"


async def test_location_entities_are_now_auto_extracted(client):
    token = await _login(client, "entityuser-locationauto")
    headers = {"Authorization": f"Bearer {token}"}
    document_id = await _upload_ready_document(client, headers, "Meeting held in Amsterdam.")
    fake = '{"entities": [{"name": "Amsterdam", "type": "location"}], "relationships": []}'

    with patch("api.entity_agent.chat_completion", return_value=fake):
        response = await client.post(f"/documents/{document_id}/extract-entities", headers=headers)

    assert response.status_code == 200
    entities = response.json()
    assert len(entities) == 1
    assert entities[0]["entity_type"] == "location"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd ~/dev/collabrains-next
rsync -avz services/api/tests/test_entities.py root@178.254.22.178:/opt/collabrains/services/api/tests/
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_entities.py -v -k personauto or locationauto"
```
Expected: FAIL — `entities == []` (person/location still filtered out by `AUTO_EXTRACTED_ENTITY_TYPES`).

- [ ] **Step 3: Write the implementation**

In `services/api/src/api/entity_agent.py`, update `AUTO_EXTRACTED_ENTITY_TYPES` (line 32) and its comment:

```python
# Broadened 2026-07-23 to include person/location, now that a code-level guardrail
# exists (_looks_like_garbage_address et al, generalized below) -- the 2026-07-09
# pullback to organization/address only predates any such guardrail (prompt
# instructions alone weren't reliable). Deployed only after Tasks 1-4 of
# docs/superpowers/plans/2026-07-23-reliable-entity-extraction-maps.md were verified
# against real production data.
AUTO_EXTRACTED_ENTITY_TYPES = {"organization", "address", "person", "location"}
```

Update the `EXTRACTION_PROMPT` (lines 41-57) to ask for all four types instead of just organization/address:

```python
EXTRACTION_PROMPT = """Extract people, organizations, locations, and specific addresses \
mentioned in the following document. Return ONLY a JSON object (no prose, no markdown \
fences) with this shape:

{{"entities": [{{"name": str, "type": "person"|"organization"|"location"|"address", \
"street": str|null, "house_number": str|null, "postal_code": str|null, "city": str|null, \
"country": str|null}}], "relationships": [{{"source": str, "target": str, "type": str}}]}}

The "street"/"house_number"/"postal_code"/"city"/"country" fields only apply to \
type "address" entities; omit or null them for every other type.

"source" and "target" must exactly match a "name" from the entities list. If there are no \
entities, return {{"entities": [], "relationships": []}}.

Document:
{text}"""
```

Update `EXTRACTION_SCHEMA`'s `type` enum (line 68) to match:

```python
                    "type": {"type": "string", "enum": ["person", "organization", "location", "address"]},
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api pytest tests/test_entities.py -v"
```
Expected: all PASSED **except** `test_extract_entities_does_not_auto_create_person_or_location` (line 112 in the existing file) — this test asserts the *old* behavior being deliberately reversed. Update that test's name and assertion to match the new behavior (or delete it if fully superseded by the two new tests above — check its exact current body first and decide based on whether it tests anything the new tests don't already cover).

- [ ] **Step 5: Live verification (not just unit tests)**

Upload a handful of real documents already in production (or re-run extraction on existing ones via `POST /documents/{id}/extract-entities`) and manually review the `/entities/review` queue for a few days' worth of real traffic before considering this task done -- the whole point of the 2026-07-09 pullback was noise that only showed up under real usage, not synthetic tests. Watch specifically for: extraction volume becoming unmanageable, low-quality person/location names appearing (partial names, titles without names, etc.).

- [ ] **Step 6: Commit**

```bash
cd ~/dev/collabrains-next
git add services/api/src/api/entity_agent.py services/api/tests/test_entities.py
git commit -m "Extend auto-extraction to person/location entities

Reverses the 2026-07-09 pullback (person/location were 'the dominant
source of low-quality noise') now that a code-level classification
guardrail exists -- that decision predated any such guardrail, prompt
instructions alone weren't reliable. Deployed only after Tasks 1-4 were
verified against real production data per this plan's own gate.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
git push origin main
```

---

## Final live verification (after all tasks)

Re-run the exact diagnostic queries used to scope this plan, confirm the fix:

```bash
ssh root@178.254.22.178 "cd /opt/collabrains && docker compose exec -T -e PYTHONPATH=/app/src api python3 -c \"
import asyncio
from sqlalchemy import select
from api.db import async_session
from api.models import AddressDetail, Entity, Residency

async def main():
    async with async_session() as db:
        result = await db.execute(select(AddressDetail))
        rows = result.scalars().all()
        complete = sum(1 for r in rows if all([r.street, r.house_number, r.postal_code, r.city]))
        print(f'{complete}/{len(rows)} AddressDetail rows fully structured')
        result2 = await db.execute(select(Residency))
        print(f'{len(result2.scalars().all())} Residency rows')

asyncio.run(main())
\""
```

Expected: the complete/total ratio for AddressDetail rows created *after* Task 2 deployed should be near 100% (pre-existing rows from before the fix stay as they were — this plan doesn't retroactively re-parse old data), and at least one Residency row should now exist if any real correspondence/other_documents/etc. document has been processed since Task 3 deployed.

**Attempted live, 2026-07-23**: re-ran `POST /documents/{id}/extract-entities` on a real production document (a full Dutch legal decision letter, `other_documents` category) as admin, to see Tasks 1-4 against real text end-to-end, not just mocked test fixtures. It hit `httpx.ReadTimeout` at 240s (`ai_gateway.py`'s `ollama_timeout_seconds`) -- this specific document's OCR text is long and `qwen3:8b` on this CPU-only host is already known-slow for shorter prompts (see `docs/deployment/ai-optimization.md`), so a longer real document timing out is consistent with pre-existing host performance, not evidence of a logic bug in this plan's changes. Did not retry (repeated slow real-Ollama calls compete with real user traffic on the same global semaphore -- see the earlier "orphaned backlog" lesson from this same day). **Confidence in Tasks 1-4 instead rests on**: comprehensive passing unit tests using fixture strings copied directly from the real production data that motivated this plan ("Achterweg 15", "9671 CT WINSCHOTEN", the exact garbage strings that were misclassified), plus the confirmed root-cause diagnosis (RESIDENCE_CATEGORY_SLUGS mismatch, empty structured fields) matching exactly what got fixed. A true full-pipeline live confirmation on a real long document is still open -- retry when the host isn't under real contention, or with a shorter real document.
