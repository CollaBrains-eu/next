# Phase 18: Vehicle Entity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Detect Dutch license plates (kenteken) and VINs in document text, enrich them from the RDW open data API, and link documents that reference the same vehicle — all as a new `entity_type="vehicle"` reusing the existing Entity/EntityMention graph, plus an on-demand `lookup_vehicle` tool.

**Architecture:** A new `Vehicle` table holds RDW-fetched fields, 1:1 FK'd to an `Entity(entity_type="vehicle")` row. Detection is pure regex (`vehicle_agent.py`), run as an extra step in the existing document-processing event chain (Phase 8a) alongside the LLM-based Entity Agent. RDW lookups go through a new `rdw_client.py` (anonymous, no App Token). The same orchestration function backs both the passive pipeline hook and an active Tool Registry entry (`lookup_vehicle`), so it's automatically callable from `/manager/ask` and MCP.

**Tech Stack:** FastAPI, SQLAlchemy (async), Alembic, `httpx`, `pytest`/`pytest-asyncio`, Redis-backed event bus (`api/events.py`).

## Global Constraints

- No RDW App Token yet — the client calls `opendata.rdw.nl` anonymously; a token can be added later via `settings.rdw_app_token` without changing call sites.
- Detection is regex-only, not LLM-based.
- RDW field set is the "extended" tier (identification + core specs), not just minimal ID fields — see spec for the full list.
- Dedup key is kenteken once known; VIN is a secondary field, not an independent global dedup key (no fuzzy merge across a later-discovered kenteken for a VIN-only vehicle) — matches ADR 0008's existing "no fuzzy resolution" stance.
- No auto-refresh of RDW data — fetched once, `fetched_at` records when; a fresh fetch only happens via an explicit `lookup_vehicle` tool call.
- Spec: `docs/superpowers/specs/2026-07-04-vehicle-entity-design.md`. Branch: `phase-18-vehicle-entity` (spec already committed there as `731a6d7`).
- All backend work happens on the live server at `root@195.90.216.230`, repo at `/opt/collabrains`, backend in `services/api` inside the `api` Docker Compose container. Run tests via `docker compose exec -T api pytest -q` (or targeted with `::test_name`). `pytest`/`ruff` must first be installed in the container per-session with `docker compose exec -T api pip install -q pytest pytest-asyncio ruff` if not already present (they are dev-only, not baked into the image).
- No new frontend UI this phase — a vehicle is reachable via the existing `/entities` list/graph view (no code changes needed there — `entity_type` is an open string filter, already accepts `vehicle`) and via the Manager Agent tool.

---

### Task 1: `Vehicle` model + migration

**Files:**
- Modify: `services/api/src/api/models.py` (add `Vehicle` class, after the `Case` class around line 380)
- Create: `services/api/alembic/versions/c48f1e7a92d3_create_vehicles_table.py`
- Test: `services/api/tests/test_vehicle_agent.py` (new file — this task's test is the first entry in it)

**Interfaces:**
- Produces: `Vehicle` model with columns `id`, `entity_id` (unique FK to `entities.id`, `ondelete="CASCADE"`), `kenteken` (nullable, indexed), `vin` (nullable, indexed), `voertuigsoort`, `merk`, `handelsbenaming`, `eerste_kleur`, `datum_eerste_toelating`, `vervaldatum_apk`, `wam_verzekerd`, `openstaande_terugroepactie_indicator`, `brandstofomschrijving`, `massa_ledig_voertuig`, `aantal_cilinders`, `wielbasis`, `catalogusprijs`, `aantal_zitplaatsen`, `aantal_deuren`, `vermogen_massarijklaar`, `lengte`, `europese_voertuigcategorie` (all nullable strings — RDW's SODA API returns these as strings, not typed numerics, so storing them as strings avoids coercion failures), `fetched_at` (nullable timestamptz), `created_at` (server-default now()).

- [ ] **Step 1: Add the `Vehicle` model**

In `services/api/src/api/models.py`, add this class immediately after the `Case` class (after its `created_at` column, before the next class):

```python
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
```

- [ ] **Step 2: Write the migration**

Create `services/api/alembic/versions/c48f1e7a92d3_create_vehicles_table.py`:

```python
"""create vehicles table

Revision ID: c48f1e7a92d3
Revises: a3f7c9e2b5d8
Create Date: 2026-07-04 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c48f1e7a92d3'
down_revision: Union[str, None] = 'a3f7c9e2b5d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('vehicles',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('entity_id', sa.UUID(), nullable=False),
    sa.Column('kenteken', sa.String(length=20), nullable=True),
    sa.Column('vin', sa.String(length=17), nullable=True),
    sa.Column('voertuigsoort', sa.String(length=100), nullable=True),
    sa.Column('merk', sa.String(length=100), nullable=True),
    sa.Column('handelsbenaming', sa.String(length=100), nullable=True),
    sa.Column('eerste_kleur', sa.String(length=50), nullable=True),
    sa.Column('datum_eerste_toelating', sa.String(length=20), nullable=True),
    sa.Column('vervaldatum_apk', sa.String(length=20), nullable=True),
    sa.Column('wam_verzekerd', sa.String(length=10), nullable=True),
    sa.Column('openstaande_terugroepactie_indicator', sa.String(length=10), nullable=True),
    sa.Column('brandstofomschrijving', sa.String(length=100), nullable=True),
    sa.Column('massa_ledig_voertuig', sa.String(length=20), nullable=True),
    sa.Column('aantal_cilinders', sa.String(length=20), nullable=True),
    sa.Column('wielbasis', sa.String(length=20), nullable=True),
    sa.Column('catalogusprijs', sa.String(length=20), nullable=True),
    sa.Column('aantal_zitplaatsen', sa.String(length=20), nullable=True),
    sa.Column('aantal_deuren', sa.String(length=20), nullable=True),
    sa.Column('vermogen_massarijklaar', sa.String(length=20), nullable=True),
    sa.Column('lengte', sa.String(length=20), nullable=True),
    sa.Column('europese_voertuigcategorie', sa.String(length=20), nullable=True),
    sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('entity_id')
    )
    op.create_index('ix_vehicles_kenteken', 'vehicles', ['kenteken'])
    op.create_index('ix_vehicles_vin', 'vehicles', ['vin'])


def downgrade() -> None:
    op.drop_index('ix_vehicles_vin', table_name='vehicles')
    op.drop_index('ix_vehicles_kenteken', table_name='vehicles')
    op.drop_table('vehicles')
```

- [ ] **Step 3: Apply the migration**

Run: `docker compose exec -T api alembic upgrade head`
Expected: output ends with `... -> c48f1e7a92d3, create vehicles table`

- [ ] **Step 4: Write a failing round-trip test**

Create `services/api/tests/test_vehicle_agent.py`:

```python
from uuid import uuid4

from api.db import async_session
from api.models import Entity, Vehicle


async def test_vehicle_row_round_trips_via_entity_fk():
    async with async_session() as db:
        entity = Entity(name="AB-12-CD", entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken="AB12CD")
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)

    async with async_session() as db:
        fetched = await db.get(Vehicle, vehicle.id)
        assert fetched is not None
        assert fetched.kenteken == "AB12CD"
        assert fetched.entity_id == entity.id
```

- [ ] **Step 5: Run test to verify it fails (before Step 1/2 if done out of order) or passes**

Run: `docker compose exec -T api pytest tests/test_vehicle_agent.py -v`
Expected: PASS (the model and migration from Steps 1-3 already make this pass — this step exists to confirm the schema is actually live, not just defined in Python)

- [ ] **Step 6: Commit**

```bash
git add services/api/src/api/models.py services/api/alembic/versions/c48f1e7a92d3_create_vehicles_table.py services/api/tests/test_vehicle_agent.py
git commit -m "Phase 18 task 1: Vehicle model + migration"
```

---

### Task 2: Regex-based kenteken/VIN detection

**Files:**
- Create: `services/api/src/api/vehicle_agent.py`
- Test: `services/api/tests/test_vehicle_agent.py` (append)

**Interfaces:**
- Consumes: nothing from other tasks yet (pure functions).
- Produces: `detect_kentekens(text: str) -> list[str]` (normalized, deduplicated, uppercase, no separators) and `detect_vins(text: str) -> list[str]` (uppercase, deduplicated) — both used by Task 4's `detect_and_link_vehicles`.

- [ ] **Step 1: Write failing detection tests**

Append to `services/api/tests/test_vehicle_agent.py`:

```python
from api.vehicle_agent import detect_kentekens, detect_vins


def test_detect_kentekens_matches_common_sidecode_formats():
    text = (
        "Kenteken AB-12-CD staat op naam. Ook gezien: 12-AB-34, 12-34-AB, "
        "AB-12-34, 12-ABC-3, 1-ABC-23, AB-123-C, A-123-BC."
    )
    assert detect_kentekens(text) == sorted({
        "AB12CD", "12AB34", "1234AB", "AB1234", "12ABC3", "1ABC23", "AB123C", "A123BC",
    })


def test_detect_kentekens_ignores_plain_dates_and_numbers():
    text = "Datum: 04-07-2026. Bedrag: 123456."
    assert detect_kentekens(text) == []


def test_detect_kentekens_deduplicates_and_normalizes_case():
    text = "ab-12-cd en nogmaals AB-12-CD."
    assert detect_kentekens(text) == ["AB12CD"]


def test_detect_vins_matches_17_char_pattern():
    text = "VIN: 1HGCM82633A004352 staat in het kentekenbewijs."
    assert detect_vins(text) == ["1HGCM82633A004352"]


def test_detect_vins_ignores_shorter_or_longer_alphanumeric_runs():
    text = "Referentie ABC123 en een langere code 1HGCM82633A0043521234"
    assert detect_vins(text) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/test_vehicle_agent.py -v -k detect`
Expected: FAIL with `ModuleNotFoundError` / `ImportError: cannot import name 'detect_kentekens'`

- [ ] **Step 3: Implement detection**

Create `services/api/src/api/vehicle_agent.py`:

```python
"""Vehicle Agent: regex-detect kentekens/VINs in document text, enrich
from RDW, and link matching vehicles across documents (Phase 18).

Detection is deliberately regex, not LLM-based -- see
docs/superpowers/specs/2026-07-04-vehicle-entity-design.md for why:
Dutch kentekens and VINs follow strict, small, fixed syntactic formats,
which a deterministic pattern matches more reliably (and for free) than
an LLM prompt. This covers the commonly-used NL kenteken "sidecodes";
older/rarer historical formats are not exhaustively covered -- an
accepted, documented limitation, not a bug.
"""
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Entity, EntityMention, Vehicle
from api.rdw_client import RdwLookupError, fetch_vehicle_data

logger = logging.getLogger(__name__)

_SEP = r"[-\s]?"
_KENTEKEN_PATTERNS = [
    rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}",  # XX-99-XX
    rf"\d{{2}}{_SEP}[A-Z]{{2}}{_SEP}\d{{2}}",  # 99-XX-99
    rf"\d{{2}}{_SEP}\d{{2}}{_SEP}[A-Z]{{2}}",  # 99-99-XX
    rf"[A-Z]{{2}}{_SEP}\d{{2}}{_SEP}\d{{2}}",  # XX-99-99
    rf"\d{{2}}{_SEP}[A-Z]{{3}}{_SEP}\d{{1}}",  # 99-XXX-9
    rf"\d{{1}}{_SEP}[A-Z]{{3}}{_SEP}\d{{2}}",  # 9-XXX-99
    rf"[A-Z]{{2}}{_SEP}\d{{3}}{_SEP}[A-Z]{{1}}",  # XX-999-X
    rf"[A-Z]{{1}}{_SEP}\d{{3}}{_SEP}[A-Z]{{2}}",  # X-999-XX
]
KENTEKEN_RE = re.compile(r"\b(?:" + "|".join(_KENTEKEN_PATTERNS) + r")\b", re.IGNORECASE)
# 17-char VIN per ISO 3779, excluding I/O/Q (never used, to avoid 1/0 confusion).
VIN_RE = re.compile(r"\b[A-HJ-NPR-Z0-9]{17}\b", re.IGNORECASE)


def _normalize_kenteken(raw: str) -> str:
    return raw.upper().replace("-", "").replace(" ", "")


def detect_kentekens(text: str) -> list[str]:
    return sorted({_normalize_kenteken(match) for match in KENTEKEN_RE.findall(text)})


def detect_vins(text: str) -> list[str]:
    return sorted({match.upper() for match in VIN_RE.findall(text)})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_vehicle_agent.py -v -k detect`
Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/vehicle_agent.py services/api/tests/test_vehicle_agent.py
git commit -m "Phase 18 task 2: regex kenteken/VIN detection"
```

---

### Task 3: RDW client

**Files:**
- Create: `services/api/src/api/rdw_client.py`
- Modify: `services/api/src/api/config.py` (add `rdw_app_token` setting)
- Test: `services/api/tests/test_rdw_client.py` (new file)

**Interfaces:**
- Consumes: `settings.rdw_app_token: str` (new config field).
- Produces: `async def fetch_vehicle_data(kenteken: str) -> dict | None` (returns a flat dict of RDW fields, or `None` if RDW has no record) and `class RdwLookupError(RuntimeError)` (raised on timeout/5xx/rate-limit — a transient failure, distinct from a confirmed "not found"). Used by Task 4's `vehicle_agent.py`.

- [ ] **Step 1: Add the config field**

In `services/api/src/api/config.py`, add this line right after `auto_extract_entities_on_ready: bool = True`:

```python
    rdw_app_token: str = ""
```

- [ ] **Step 2: Write failing tests against a mocked httpx client**

Create `services/api/tests/test_rdw_client.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from api.rdw_client import RdwLookupError, fetch_vehicle_data

FAKE_VEHICLE_ROW = {
    "voertuigsoort": "Personenauto",
    "merk": "TOYOTA",
    "handelsbenaming": "AYGO",
    "eerste_kleur": "GRIJS",
    "datum_eerste_toelating": "20180501",
    "vervaldatum_apk": "20270501",
    "wam_verzekerd": "Ja",
    "openstaande_terugroepactie_indicator": "Nee",
    "massa_ledig_voertuig": "840",
    "aantal_cilinders": "3",
    "wielbasis": "2340",
    "catalogusprijs": "12500",
    "aantal_zitplaatsen": "4",
    "aantal_deuren": "5",
    "vermogen_massarijklaar": "51",
    "lengte": "3455",
    "europese_voertuigcategorie": "M1",
}
FAKE_FUEL_ROW = {"brandstof_omschrijving": "Benzine"}


def _mock_response(json_data, status_code=200):
    response = MagicMock(spec=httpx.Response)
    response.status_code = status_code
    response.json.return_value = json_data
    response.raise_for_status = MagicMock()
    if status_code >= 400:
        response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "error", request=MagicMock(), response=response
        )
    return response


async def test_fetch_vehicle_data_returns_merged_vehicle_and_fuel_fields():
    vehicle_response = _mock_response([FAKE_VEHICLE_ROW])
    fuel_response = _mock_response([FAKE_FUEL_ROW])

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[vehicle_response, fuel_response])
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_vehicle_data("AB12CD")

    assert result["merk"] == "TOYOTA"
    assert result["handelsbenaming"] == "AYGO"
    assert result["brandstofomschrijving"] == "Benzine"


async def test_fetch_vehicle_data_returns_none_when_rdw_has_no_record():
    vehicle_response = _mock_response([])

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=vehicle_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        result = await fetch_vehicle_data("ZZ99ZZ")

    assert result is None


async def test_fetch_vehicle_data_raises_rdw_lookup_error_on_http_error():
    error_response = _mock_response({}, status_code=500)

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=error_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RdwLookupError):
            await fetch_vehicle_data("AB12CD")


async def test_fetch_vehicle_data_raises_rdw_lookup_error_on_timeout():
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timed out"))
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("api.rdw_client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(RdwLookupError):
            await fetch_vehicle_data("AB12CD")
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/test_rdw_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'api.rdw_client'`

- [ ] **Step 4: Implement the client**

Create `services/api/src/api/rdw_client.py`:

```python
"""RDW open data client (Phase 18).

Anonymous access (no App Token yet) against opendata.rdw.nl's
"Gekentekende voertuigen" dataset and its fuel-type sub-dataset --
both public Socrata/SODA endpoints, keyed on kenteken only (VIN is not
in the public dataset -- RDW doesn't publish it, for privacy). See
docs/superpowers/specs/2026-07-04-vehicle-entity-design.md.

`settings.rdw_app_token` is read here but unused today (empty string);
wiring it in later (once the user has one) is a one-line addition to
`_params()`, not a call-site change.
"""
import httpx

from api.config import settings

RDW_VEHICLES_URL = "https://opendata.rdw.nl/resource/m9d7-ebf2.json"
RDW_FUEL_URL = "https://opendata.rdw.nl/resource/8ys7-d773.json"

_VEHICLE_FIELDS = [
    "voertuigsoort", "merk", "handelsbenaming", "eerste_kleur",
    "datum_eerste_toelating", "vervaldatum_apk", "wam_verzekerd",
    "openstaande_terugroepactie_indicator", "massa_ledig_voertuig",
    "aantal_cilinders", "wielbasis", "catalogusprijs", "aantal_zitplaatsen",
    "aantal_deuren", "vermogen_massarijklaar", "lengte", "europese_voertuigcategorie",
]


class RdwLookupError(RuntimeError):
    """A transient RDW failure (timeout, 5xx, rate-limit) -- distinct from
    a confirmed "no such kenteken" (which returns None, not an error)."""


def _params(kenteken: str) -> dict[str, str]:
    params = {"kenteken": kenteken}
    if settings.rdw_app_token:
        params["$$app_token"] = settings.rdw_app_token
    return params


async def fetch_vehicle_data(kenteken: str) -> dict | None:
    """Look up a vehicle by kenteken. Returns None if RDW has no record
    (a real, confirmed "not found" -- the SODA API returns 200 with an
    empty array for a filter that matches nothing, not a 404). Raises
    RdwLookupError on timeout/5xx/rate-limit so callers can tell "we
    don't know" apart from "we couldn't ask"."""
    params = _params(kenteken)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            vehicle_response = await client.get(RDW_VEHICLES_URL, params=params)
            vehicle_response.raise_for_status()
            fuel_response = await client.get(RDW_FUEL_URL, params=params)
            fuel_response.raise_for_status()
    except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.HTTPError) as exc:
        raise RdwLookupError(f"RDW lookup failed for {kenteken!r}: {exc}") from exc

    vehicle_rows = vehicle_response.json()
    if not vehicle_rows:
        return None

    vehicle = vehicle_rows[0]
    fuel_rows = fuel_response.json()
    fuel = fuel_rows[0] if fuel_rows else {}

    result = {field: vehicle.get(field) for field in _VEHICLE_FIELDS}
    result["brandstofomschrijving"] = fuel.get("brandstof_omschrijving")
    return result
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_rdw_client.py -v`
Expected: `4 passed`

- [ ] **Step 6: Manually verify against the real RDW API once**

Run: `curl -s 'https://opendata.rdw.nl/resource/m9d7-ebf2.json?kenteken=69VXX7' | head -c 800`
(Use any currently-registered NL kenteken you have on hand — this only confirms the real field names still match what Step 4 expects; the test suite itself never calls the live API.) If a field name has changed, update `_VEHICLE_FIELDS`/`brandstof_omschrijving` in `rdw_client.py` accordingly before continuing.

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/rdw_client.py services/api/src/api/config.py services/api/tests/test_rdw_client.py
git commit -m "Phase 18 task 3: RDW open data client"
```

---

### Task 4: Vehicle orchestration (get-or-create, linking, RDW enrichment)

**Files:**
- Modify: `services/api/src/api/vehicle_agent.py` (append orchestration functions)
- Test: `services/api/tests/test_vehicle_agent.py` (append)

**Interfaces:**
- Consumes: `detect_kentekens`/`detect_vins` (Task 2), `fetch_vehicle_data`/`RdwLookupError` (Task 3), `Entity`/`EntityMention`/`Vehicle` (Task 1).
- Produces: `async def detect_and_link_vehicles(db: AsyncSession, *, document_id: UUID, text: str) -> list[Vehicle]` (the pipeline entry point, Task 5 depends on this) and `async def lookup_vehicle(*, kenteken: str) -> Vehicle` (the active/tool entry point, Task 6 depends on this — it manages its own DB session internally, so it takes no `db` parameter).

- [ ] **Step 1: Write failing orchestration tests**

Append to `services/api/tests/test_vehicle_agent.py`:

```python
from unittest.mock import patch

from sqlalchemy import select

from api.models import EntityMention
from api.vehicle_agent import detect_and_link_vehicles, lookup_vehicle

FAKE_RDW_DATA = {
    "voertuigsoort": "Personenauto", "merk": "TOYOTA", "handelsbenaming": "AYGO",
    "eerste_kleur": "GRIJS", "datum_eerste_toelating": "20180501",
    "vervaldatum_apk": "20270501", "wam_verzekerd": "Ja",
    "openstaande_terugroepactie_indicator": "Nee", "brandstofomschrijving": "Benzine",
    "massa_ledig_voertuig": "840", "aantal_cilinders": "3", "wielbasis": "2340",
    "catalogusprijs": "12500", "aantal_zitplaatsen": "4", "aantal_deuren": "5",
    "vermogen_massarijklaar": "51", "lengte": "3455", "europese_voertuigcategorie": "M1",
}


async def test_detect_and_link_vehicles_creates_entity_and_enriches_from_rdw():
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        async with async_session() as db:
            vehicles = await detect_and_link_vehicles(
                db, document_id=uuid4(), text="Kenteken TE-ST01 is geregistreerd."
            )
    assert len(vehicles) == 1
    assert vehicles[0].kenteken == "TEST01"
    assert vehicles[0].merk == "TOYOTA"
    assert vehicles[0].fetched_at is not None


async def test_detect_and_link_vehicles_links_kenteken_and_vin_from_same_document():
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        async with async_session() as db:
            vehicles = await detect_and_link_vehicles(
                db, document_id=uuid4(),
                text="Kenteken TE-ST02, VIN 1HGCM82633A004352.",
            )
    assert len(vehicles) == 1
    assert vehicles[0].kenteken == "TEST02"
    assert vehicles[0].vin == "1HGCM82633A004352"


async def test_detect_and_link_vehicles_shares_one_entity_across_two_documents():
    doc_a, doc_b = uuid4(), uuid4()
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        async with async_session() as db:
            first = await detect_and_link_vehicles(db, document_id=doc_a, text="Kenteken TE-ST03.")
        async with async_session() as db:
            second = await detect_and_link_vehicles(db, document_id=doc_b, text="Kenteken TE-ST03.")

    assert first[0].id == second[0].id
    async with async_session() as db:
        mentions = await db.execute(
            select(EntityMention).where(EntityMention.entity_id == first[0].entity_id)
        )
        assert len(mentions.scalars().all()) == 2


async def test_detect_and_link_vehicles_never_raises_on_rdw_failure():
    with patch("api.vehicle_agent.fetch_vehicle_data", side_effect=RdwLookupError("boom")):
        async with async_session() as db:
            vehicles = await detect_and_link_vehicles(db, document_id=uuid4(), text="Kenteken TE-ST04.")
    assert len(vehicles) == 1
    assert vehicles[0].merk is None
    assert vehicles[0].fetched_at is None


async def test_lookup_vehicle_force_refreshes_even_if_already_fetched():
    with patch("api.vehicle_agent.fetch_vehicle_data", return_value=FAKE_RDW_DATA):
        vehicle_first = await lookup_vehicle(kenteken="TE-ST05")
        vehicle_second = await lookup_vehicle(kenteken="TE-ST05")
    assert vehicle_first.id == vehicle_second.id
    assert vehicle_second.fetched_at >= vehicle_first.fetched_at
```

Note: `lookup_vehicle` takes only `kenteken` and manages its own `async_session()` internally (see Step 3) — it's called by the Tool Registry handler (Task 6) *after* that handler's own `db`/`user_id` have already been used for the permission check, so the underlying domain function itself never needs a caller-supplied session.

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/test_vehicle_agent.py -v -k "detect_and_link or lookup_vehicle"`
Expected: FAIL with `ImportError: cannot import name 'detect_and_link_vehicles'`

- [ ] **Step 3: Implement orchestration**

Append to `services/api/src/api/vehicle_agent.py`:

```python
async def _get_or_create_vehicle_entity(
    db: AsyncSession, *, kenteken: str | None, vin: str | None
) -> tuple[Entity, Vehicle]:
    """Get-or-create the Entity+Vehicle pair for a detected kenteken/VIN.

    Kenteken is the dedup key once known. A VIN-only vehicle dedupes on
    VIN among rows that have no kenteken yet; if a kenteken for that same
    real-world vehicle surfaces later in a different document, a second,
    separate row is created rather than merged -- the same "no fuzzy
    resolution" stance ADR 0008 already takes for person/organization
    entities, applied here too (see the spec's Consequences section).
    """
    vehicle: Vehicle | None = None

    if kenteken is not None:
        result = await db.execute(select(Vehicle).where(Vehicle.kenteken == kenteken))
        vehicle = result.scalar_one_or_none()
    elif vin is not None:
        result = await db.execute(select(Vehicle).where(Vehicle.vin == vin, Vehicle.kenteken.is_(None)))
        vehicle = result.scalar_one_or_none()

    if vehicle is None:
        entity = Entity(name=kenteken or vin, entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken=kenteken, vin=vin)
        db.add(vehicle)
        await db.flush()
    else:
        entity = await db.get(Entity, vehicle.entity_id)
        if vin is not None and vehicle.vin is None:
            vehicle.vin = vin
        if kenteken is not None and vehicle.kenteken is None:
            vehicle.kenteken = kenteken
            entity.name = kenteken

    return entity, vehicle


async def _link_mention(db: AsyncSession, entity_id: UUID, document_id: UUID) -> None:
    existing = await db.execute(
        select(EntityMention).where(EntityMention.entity_id == entity_id, EntityMention.document_id == document_id)
    )
    if existing.scalar_one_or_none() is None:
        db.add(EntityMention(entity_id=entity_id, document_id=document_id))


async def _enrich_from_rdw(vehicle: Vehicle) -> None:
    """Populate `vehicle`'s RDW fields in place. Never raises -- a
    transient failure is logged and `fetched_at` is left untouched (so a
    later document mentioning this kenteken, or a manual tool call, will
    retry); a confirmed "not found" sets `fetched_at` so it isn't retried
    on every future document automatically."""
    if vehicle.kenteken is None or vehicle.fetched_at is not None:
        return
    try:
        data = await fetch_vehicle_data(vehicle.kenteken)
    except RdwLookupError as exc:
        logger.warning("vehicle_agent: RDW lookup failed for %s: %s", vehicle.kenteken, exc)
        return
    if data is None:
        vehicle.fetched_at = datetime.now(timezone.utc)
        return
    for field, value in data.items():
        setattr(vehicle, field, value)
    vehicle.fetched_at = datetime.now(timezone.utc)


async def detect_and_link_vehicles(db: AsyncSession, *, document_id: UUID, text: str) -> list[Vehicle]:
    """Regex-detect kentekens/VINs in `text`, get-or-create Vehicle/Entity
    rows, link them to `document_id`, and enrich any newly-known kenteken
    from RDW. Commits internally (same convention as
    `entity_agent.extract_entities`) -- callers don't manage the
    transaction."""
    kentekens = detect_kentekens(text)
    vins = detect_vins(text)
    vehicles: list[Vehicle] = []

    if len(kentekens) == 1 and len(vins) == 1:
        # Exactly one of each in the same document -- treat as one vehicle.
        entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=kentekens[0], vin=vins[0])
        await _link_mention(db, entity.id, document_id)
        await _enrich_from_rdw(vehicle)
        vehicles.append(vehicle)
    else:
        for kenteken in kentekens:
            entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=kenteken, vin=None)
            await _link_mention(db, entity.id, document_id)
            await _enrich_from_rdw(vehicle)
            vehicles.append(vehicle)
        for vin in vins:
            entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=None, vin=vin)
            await _link_mention(db, entity.id, document_id)
            vehicles.append(vehicle)

    await db.commit()
    for vehicle in vehicles:
        await db.refresh(vehicle)
    return vehicles


async def lookup_vehicle(*, kenteken: str) -> Vehicle:
    """Actively look up (or force-refresh) a vehicle by kenteken -- backs
    the `lookup_vehicle` tool (Task 6). Unlike the passive pipeline path,
    this always calls RDW even if `fetched_at` is already set, so a user
    can force a stale or previously-failed lookup to retry. Manages its
    own session/transaction -- the Tool Registry handler that calls this
    (Task 6) already consumed its own `db`/`user_id` for the permission
    check before reaching here, so this function needs no caller-supplied
    session."""
    from api.db import async_session as _async_session

    normalized = _normalize_kenteken(kenteken)
    async with _async_session() as db:
        entity, vehicle = await _get_or_create_vehicle_entity(db, kenteken=normalized, vin=None)
        try:
            data = await fetch_vehicle_data(normalized)
        except RdwLookupError:
            data = None
        if data is not None:
            for field, value in data.items():
                setattr(vehicle, field, value)
        vehicle.fetched_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_vehicle_agent.py -v`
Expected: `10 passed` (5 from Task 2 + 5 new)

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/vehicle_agent.py services/api/tests/test_vehicle_agent.py
git commit -m "Phase 18 task 4: vehicle get-or-create, linking, RDW enrichment"
```

---

### Task 5: Wire into the document pipeline

**Files:**
- Modify: `services/api/src/api/config.py` (add `auto_extract_vehicles_on_ready`)
- Modify: `services/api/src/api/events.py` (add `EventType.VEHICLES_DETECTED`)
- Modify: `services/api/src/api/documents.py` (module docstring + new event handler)
- Test: `services/api/tests/test_documents.py` (append)

**Interfaces:**
- Consumes: `detect_and_link_vehicles` (Task 4), `EventType.EMBEDDINGS_CREATED` (existing), `publish`/`subscribe`/`Event` (existing, `api/events.py`).
- Produces: `EventType.VEHICLES_DETECTED = "VehiclesDetected"` (published after the new handler runs; nothing subscribes to it yet, same as `ENTITIES_EXTRACTED` originally had no downstream subscriber either).

- [ ] **Step 1: Add the config flag**

In `services/api/src/api/config.py`, add this line right after `auto_extract_entities_on_ready: bool = True`:

```python
    auto_extract_vehicles_on_ready: bool = True
```

- [ ] **Step 2: Add the event type**

In `services/api/src/api/events.py`, inside `class EventType`, add this line right after `ENTITIES_EXTRACTED = "EntitiesExtracted"`:

```python
    VEHICLES_DETECTED = "VehiclesDetected"
```

- [ ] **Step 3: Update the pipeline docstring**

In `services/api/src/api/documents.py`, in the module docstring, change:

```
event handlers reacting to that event and the ones it
chains into (`OCRCompleted` -> `EmbeddingsCreated` -> `TasksCreated` /
`EntitiesExtracted` -> `NotificationRequested` -> `WorkflowCompleted`), not
```

to:

```
event handlers reacting to that event and the ones it
chains into (`OCRCompleted` -> `EmbeddingsCreated` -> `TasksCreated` /
`EntitiesExtracted` / `VehiclesDetected` -> `NotificationRequested` ->
`WorkflowCompleted`), not
```

- [ ] **Step 4: Write a failing pipeline test**

`services/api/tests/test_documents.py` already defines `_login(client)` (logs in as fixed user `"docuser"`, no username parameter) and `FAKE_EMBEDDING = [0.1] * 768` at module level — reuse both rather than redefining them. Append this test:

```python
async def test_upload_triggers_vehicle_detection_and_creates_entity(client):
    token = await _login(client)
    headers = {"Authorization": f"Bearer {token}"}

    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=101),
        patch("api.documents.fetch_document_text", return_value="Kenteken VE-HI01 staat geregistreerd."),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
        patch("api.vehicle_agent.fetch_vehicle_data", return_value=None),
    ):
        upload = await client.post(
            "/documents", headers=headers,
            files={"file": ("vehicle.txt", b"Kenteken VE-HI01 staat geregistreerd.", "text/plain")},
        )

    assert upload.status_code == 202
    response = await client.get("/entities?entity_type=vehicle", headers=headers)
    names = {entity["name"] for entity in response.json()}
    assert "VEHI01" in names
```

- [ ] **Step 5: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_documents.py -v -k vehicle_detection`
Expected: FAIL — `AssertionError: assert 'VEHI01' in set()` (the handler doesn't exist yet, so no entity gets created)

- [ ] **Step 6: Add the pipeline handler**

In `services/api/src/api/documents.py`, add this import near the top alongside the other agent imports (after `from api.entity_agent import extract_entities`):

```python
from api.vehicle_agent import detect_and_link_vehicles
```

Then add this handler immediately after the existing `_handle_extract_entities` function:

```python
@subscribe(EventType.EMBEDDINGS_CREATED)
async def _handle_extract_vehicles(event: Event) -> None:
    if not settings.auto_extract_vehicles_on_ready:
        return
    document_id = event.payload["document_id"]
    async with async_session() as db:
        vehicles = await detect_and_link_vehicles(db, document_id=document_id, text=event.payload["text"])
    await publish(EventType.VEHICLES_DETECTED, {"document_id": document_id, "vehicle_count": len(vehicles)})
```

- [ ] **Step 7: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_documents.py -v -k vehicle_detection`
Expected: `1 passed`

- [ ] **Step 8: Run the full test suite to check for regressions**

Run: `docker compose exec -T api pytest -q`
Expected: same pass/fail counts as before this phase (224 passed, 6 pre-existing unrelated failures), plus this phase's new tests passing.

- [ ] **Step 9: Commit**

```bash
git add services/api/src/api/config.py services/api/src/api/events.py services/api/src/api/documents.py services/api/tests/test_documents.py
git commit -m "Phase 18 task 5: wire vehicle detection into document pipeline"
```

---

### Task 6: Active `lookup_vehicle` tool

**Files:**
- Modify: `services/api/src/api/permissions.py` (add `vehicles.write`)
- Modify: `services/api/src/api/tools.py` (register the tool)
- Test: `services/api/tests/test_tools.py` (append)

**Interfaces:**
- Consumes: `lookup_vehicle` (Task 4), `ToolDescriptor`/`register_tool`/`dispatch` (existing, `api/tool_registry.py`).
- Produces: a `lookup_vehicle` entry in the Tool Registry, automatically available to `/manager/ask` (Phase 11) and MCP (Phase 9b) — no changes needed in either of those modules, since both already iterate the registry generically.

- [ ] **Step 1: Add the permission**

In `services/api/src/api/permissions.py`, change:

```python
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "member": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write"}),
    "admin": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write"}),
    "service": frozenset(),
}
```

to:

```python
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "member": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write", "vehicles.write"}),
    "admin": frozenset({"documents.read", "legal.draft", "tasks.write", "entities.write", "vehicles.write"}),
    "service": frozenset(),
}
```

- [ ] **Step 2: Write a failing tool test**

Append to `services/api/tests/test_tools.py`:

```python
async def test_lookup_vehicle_tool_returns_rdw_fields():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_data = {
        "voertuigsoort": "Personenauto", "merk": "TOYOTA", "handelsbenaming": "AYGO",
        "eerste_kleur": "GRIJS", "datum_eerste_toelating": "20180501",
        "vervaldatum_apk": "20270501", "wam_verzekerd": "Ja",
        "openstaande_terugroepactie_indicator": "Nee", "brandstofomschrijving": "Benzine",
        "massa_ledig_voertuig": "840", "aantal_cilinders": "3", "wielbasis": "2340",
        "catalogusprijs": "12500", "aantal_zitplaatsen": "4", "aantal_deuren": "5",
        "vermogen_massarijklaar": "51", "lengte": "3455", "europese_voertuigcategorie": "M1",
    }

    async with async_session() as db:
        with patch("api.vehicle_agent.fetch_vehicle_data", return_value=fake_data):
            result = await dispatch("lookup_vehicle", db=db, user_id=user.id, kenteken="TO-OL01")

    assert result["kenteken"] == "TOOL01"
    assert result["merk"] == "TOYOTA"
    assert result["found"] is True


async def test_lookup_vehicle_tool_reports_not_found():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")

    async with async_session() as db:
        with patch("api.vehicle_agent.fetch_vehicle_data", return_value=None):
            result = await dispatch("lookup_vehicle", db=db, user_id=user.id, kenteken="ZZ-99-ZZ")

    assert result["found"] is False
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/test_tools.py -v -k lookup_vehicle`
Expected: FAIL with `KeyError: "unknown tool: 'lookup_vehicle'"`

- [ ] **Step 4: Register the tool**

In `services/api/src/api/tools.py`, add this import alongside the others (after `from api.search_service import hybrid_search`):

```python
from api.vehicle_agent import lookup_vehicle as _lookup_vehicle
```

Add this handler after `_extract_entities_handler`:

```python
async def _lookup_vehicle_handler(*, db: AsyncSession, user_id: UUID, kenteken: str) -> dict[str, Any]:
    vehicle = await _lookup_vehicle(kenteken=kenteken)
    return {
        "kenteken": vehicle.kenteken,
        "merk": vehicle.merk,
        "handelsbenaming": vehicle.handelsbenaming,
        "voertuigsoort": vehicle.voertuigsoort,
        "eerste_kleur": vehicle.eerste_kleur,
        "datum_eerste_toelating": vehicle.datum_eerste_toelating,
        "vervaldatum_apk": vehicle.vervaldatum_apk,
        "wam_verzekerd": vehicle.wam_verzekerd,
        "openstaande_terugroepactie_indicator": vehicle.openstaande_terugroepactie_indicator,
        "brandstofomschrijving": vehicle.brandstofomschrijving,
        "found": vehicle.merk is not None,
    }
```

Add this registration after the `extract_entities` tool's `register_tool(...)` call:

```python
register_tool(ToolDescriptor(
    name="lookup_vehicle",
    description="Look up a vehicle's RDW registration data by kenteken (Dutch license plate).",
    permissions=["vehicles.write"],
    input_schema={"kenteken": "string"},
    output_schema={
        "kenteken": "string", "merk": "string", "handelsbenaming": "string",
        "voertuigsoort": "string", "eerste_kleur": "string",
        "datum_eerste_toelating": "string", "vervaldatum_apk": "string",
        "wam_verzekerd": "string", "openstaande_terugroepactie_indicator": "string",
        "brandstofomschrijving": "string", "found": "boolean",
    },
    handler=_lookup_vehicle_handler,
))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_tools.py -v -k lookup_vehicle`
Expected: `2 passed`

- [ ] **Step 6: Run the full test suite**

Run: `docker compose exec -T api pytest -q`
Expected: same pre-existing 6 unrelated failures, everything else (including all of Phase 18's new tests) passing.

- [ ] **Step 7: Run ruff**

Run: `docker compose exec -T api ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
git add services/api/src/api/permissions.py services/api/src/api/tools.py services/api/tests/test_tools.py
git commit -m "Phase 18 task 6: lookup_vehicle tool"
```

---

### Task 7: ADR + final verification

**Files:**
- Create: `docs/adr/0036-phase18-vehicle-entity.md`
- Modify: `README.md` (Status line + Phases list, matching every prior phase's convention)

**Interfaces:** None — this task documents and verifies, it doesn't add code.

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0036-phase18-vehicle-entity.md`:

```markdown
# ADR 0036: Phase 18 — Vehicle Entity (Kenteken/VIN Detection + RDW Enrichment)

## Status
Accepted

## Context

This phase came from a fresh brainstorm, not the original roadmap
(closed at Phase 15) or Phase 16/17's own follow-ups: the user wants
vehicle/license-plate data recognized in documents, enriched from the
RDW (Dutch vehicle authority) open data API, and linked across
documents referencing the same vehicle. Full design rationale is in
`docs/superpowers/specs/2026-07-04-vehicle-entity-design.md`.

## Decision

**A new `entity_type="vehicle"`, not a new top-level node type.** The
existing `Entity`/`EntityMention`/`EntityRelationship` machinery (Phase
4, ADR 0008) already links an entity to every document mentioning it,
so two documents mentioning the same kenteken automatically share one
entity -- no new junction tables, and the vehicle shows up for free in
the existing `/entities` list and one-hop graph view (Phase 5c).

**A new `Vehicle` table holds the RDW payload**, FK'd 1:1 to
`Entity.id` -- the same pattern `Case`/`Decision` already use for
structured data `Entity` itself has no columns for.

**Detection is pure regex** (`api/vehicle_agent.py`), not LLM
extraction -- kentekens and VINs follow small, fixed syntactic formats,
which a deterministic pattern matches more reliably (and for free) than
an LLM prompt, avoiding the 0/O, 1/I confusion LLMs occasionally
introduce on strict identifiers. Runs alongside the existing LLM-based
Entity Agent in the same document-processing event chain (Phase 8a),
not replacing it.

**RDW lookup (`api/rdw_client.py`) is keyed on kenteken only** --
VIN isn't in RDW's public dataset (privacy). Used anonymously (no App
Token yet); written so a token can be added later via config with no
call-site changes.

**Dedup key is kenteken once known**; VIN is a secondary field. A
VIN-only vehicle that later turns out to share a kenteken with an
existing vehicle produces a second, separate row rather than a merge --
the same "no fuzzy resolution" stance ADR 0008 already takes for
person/organization entities.

**One shared function backs both the passive pipeline hook and an
active tool.** `lookup_vehicle` is registered in the Tool Registry
(Phase 9a), automatically callable from the Manager Agent
(`/manager/ask`, Phase 11) and MCP (Phase 9b) with zero additional
wiring.

**No auto-refresh.** RDW data is fetched once (`fetched_at` records
when); a fresh fetch only happens via an explicit `lookup_vehicle` tool
call.

## Consequences

- **Deferred, not solved**: other Dutch open-data sources (KVK, PDOK,
  CBS, Kadaster) raised in the same brainstorm are out of scope --
  candidate future phases, each getting its own spec. No frontend UI is
  added this phase either -- a vehicle is visible today only via the
  existing `/entities` list/graph view and the Manager Agent tool.
- VIN-only vehicles that later turn out to share a kenteken with an
  existing vehicle produce a second, separate entity rather than a
  merge -- accepted, not a bug.
- RDW data can go stale (APK renewal, insurance lapsing) since there's
  no auto-refresh -- acceptable for this phase; a scheduled refresh is
  a candidate future addition if it turns out to matter in practice.
- The regex-based kenteken detection covers the commonly-used NL
  sidecode formats, not an exhaustive historical list -- a documented,
  accepted limitation, not a bug.
```

- [ ] **Step 2: Update the README**

In `README.md`, update the `## Status` line to reference Phase 18, and add a bullet for **Phase 18** to both the `services/api covers` list and the numbered `## Phases` list at the bottom, following the exact same format as the Phase 16/17 entries already there (see the README's existing Phase 16/17a-d bullets for the format to match — one paragraph in the prose list, one bullet in the numbered list, each ending with `See ADR 0036.`).

- [ ] **Step 3: Run the full test suite one more time**

Run: `docker compose exec -T api pytest -q`
Expected: same pre-existing 6 unrelated failures only; every Phase 18 test passing.

- [ ] **Step 4: Run ruff**

Run: `docker compose exec -T api ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 5: Commit**

```bash
git add docs/adr/0036-phase18-vehicle-entity.md README.md
git commit -m "Phase 18 task 7: ADR + README"
```

- [ ] **Step 6: Push and open a PR**

```bash
git push -u origin phase-18-vehicle-entity
gh pr create --title "Phase 18: Vehicle entity (kenteken/VIN detection + RDW enrichment)" --body "Implements docs/superpowers/specs/2026-07-04-vehicle-entity-design.md: a new entity_type=\"vehicle\" (Entity + new Vehicle table), regex-based kenteken/VIN detection wired into the existing document pipeline, an RDW open data client, and a lookup_vehicle tool usable from the Manager Agent and MCP. See ADR 0036."
```

Then proceed with `superpowers:finishing-a-development-branch` to verify tests one final time and merge.
