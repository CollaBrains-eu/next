# Phase 19: Vehicles Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/vehicles` page — a plate-styled kenteken lookup plus a list of all detected vehicles — and let vehicles be linked to Cases, the same way Documents/Tasks/Decisions already are.

**Architecture:** A new `vehicles_router.py` exposes Phase 18's `Vehicle` data over REST (`GET /vehicles`, `POST /vehicles/lookup`) for the first time — previously only reachable via the Manager Agent/MCP tool. `cases.py`/`cases_router.py` gain a fourth linkable type (Vehicle) via the existing `graph_edges` mechanism. The frontend adds one reusable plate-styled input component, one new page, and extends the existing Case detail page's attach-flow pattern to a fourth section.

**Tech Stack:** FastAPI, SQLAlchemy (async), `pytest`, React+TypeScript+Vite+Tailwind, `vitest`, Playwright MCP for live verification.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-04-vehicles-page-design.md`. Branch: `phase-19-vehicles-page` (spec already committed there as `e1d1b39`).
- `GET /vehicles`/`POST /vehicles/lookup` require only authentication (`get_current_user`), no extra permission check — matching `GET /entities`'s existing simplicity; the Tool Registry's `vehicles.write` permission (Phase 18) is a separate, tool-specific concern (ADR 0023) and isn't duplicated onto the direct REST path.
- `POST /cases/{case_id}/vehicles/{vehicle_id}` checks Case ownership only, not Vehicle ownership — vehicles (like all entities) have no owner field to check.
- No client-side kenteken format validation — RDW/`lookup_vehicle` is the sole source of truth.
- No unlink endpoint (matches Task/Decision, which don't have one either).
- All backend work happens on the live server at `root@195.90.216.230`, repo at `/opt/collabrains`, backend in `services/api` inside the `api` Docker Compose container, frontend in `apps/web` inside the `web` container. Run backend tests via `docker compose exec -T api pytest -q`; frontend typecheck via `docker compose exec -T web pnpm exec tsc -b`; frontend tests via `docker compose exec -T web pnpm test -- --run`.
- **The Caddy reverse-proxy allowlist (`infra/caddy/Caddyfile`) must include the new `/vehicles*` path prefix**, or requests to it will silently fall through to the SPA in production instead of reaching the API — the exact bug found and fixed earlier this project (PR #17). This is Task 1, not an afterthought.
- Rebuilding the production frontend bundle (`docker compose exec -e VITE_API_URL='' web sh -c "cd /app/apps/web && pnpm build"`) and reloading Caddy are required before any live verification of the new page — the dev server's live-reload does not affect the production `dist/` Caddy serves.

---

### Task 1: Vehicle list endpoint + Caddy allowlist

**Files:**
- Create: `services/api/src/api/vehicles_router.py`
- Modify: `services/api/src/api/main.py` (register the new router)
- Modify: `infra/caddy/Caddyfile:20` (add `/vehicles*` to the `@api` path matcher)
- Test: `services/api/tests/test_vehicles_router.py` (new file)

**Interfaces:**
- Consumes: `Vehicle` (`api/models.py`, Phase 18), `get_current_user` (`api/auth.py`), `get_db` (`api/db.py`).
- Produces: `VehicleOut` (pydantic model — `id`, `kenteken`, `vin`, `voertuigsoort`, `merk`, `handelsbenaming`, `eerste_kleur`, `datum_eerste_toelating`, `vervaldatum_apk`, `wam_verzekerd`, `openstaande_terugroepactie_indicator`, `brandstofomschrijving`, `fetched_at`, `created_at`), `GET /vehicles` returning `list[VehicleOut]`. Task 2 appends to this same file/router.

- [ ] **Step 1: Write the failing test**

Create `services/api/tests/test_vehicles_router.py`:

```python
from unittest.mock import patch
from uuid import uuid4

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import Entity, Vehicle


async def _login(client, username: str) -> str:
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"]


async def _create_vehicle(kenteken: str, *, merk: str | None = None) -> Vehicle:
    async with async_session() as db:
        entity = Entity(name=kenteken, entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken=kenteken, merk=merk)
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle


async def test_list_vehicles_returns_created_vehicles(client):
    token = await _login(client, f"vehiclerouter-{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}
    vehicle = await _create_vehicle(f"LI-{uuid4().hex[:2].upper()}-ST", merk="TOYOTA")

    response = await client.get("/vehicles", headers=headers)

    assert response.status_code == 200
    kentekens = {v["kenteken"] for v in response.json()}
    assert vehicle.kenteken in kentekens


async def test_list_vehicles_requires_auth(client):
    response = await client.get("/vehicles")
    assert response.status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_vehicles_router.py -v`
Expected: FAIL with `404 Not Found` (no `/vehicles` route registered yet) or `ModuleNotFoundError` if `api.vehicles_router` doesn't exist yet.

- [ ] **Step 3: Create the router**

Create `services/api/src/api/vehicles_router.py`:

```python
"""Vehicle list + direct lookup REST endpoints (Phase 19).

Phase 18 built `Vehicle`/`vehicle_agent.lookup_vehicle` with only a Tool
Registry entry (reachable via the Manager Agent/MCP) -- no REST surface
existed. This file adds one: a list endpoint and a direct lookup
endpoint, both new. See docs/superpowers/specs/2026-07-04-vehicles-page-design.md.
"""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import User, Vehicle

router = APIRouter(tags=["vehicles"])


class VehicleOut(BaseModel):
    id: UUID
    kenteken: str | None
    vin: str | None
    voertuigsoort: str | None
    merk: str | None
    handelsbenaming: str | None
    eerste_kleur: str | None
    datum_eerste_toelating: str | None
    vervaldatum_apk: str | None
    wam_verzekerd: str | None
    openstaande_terugroepactie_indicator: str | None
    brandstofomschrijving: str | None
    fetched_at: datetime | None
    created_at: datetime


@router.get("/vehicles", response_model=list[VehicleOut])
async def list_vehicles_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Vehicle]:
    result = await db.execute(select(Vehicle).order_by(Vehicle.created_at.desc()))
    return list(result.scalars().all())
```

- [ ] **Step 4: Register the router**

In `services/api/src/api/main.py`, add this import alongside the other router imports (after `from api.tasks import router as tasks_router`):

```python
from api.vehicles_router import router as vehicles_router
```

Add this line alongside the other `app.include_router(...)` calls (after `app.include_router(learning_router)`):

```python
app.include_router(vehicles_router)
```

- [ ] **Step 5: Add `/vehicles*` to the Caddy allowlist**

In `infra/caddy/Caddyfile`, change:

```
path /auth* /documents* /chat* /legal* /tasks* /entities* /search* /health* /plans* /memories* /tools* /mcp* /decisions* /manager* /preferences* /organizations* /learning* /cases*
```

to:

```
path /auth* /documents* /chat* /legal* /tasks* /entities* /search* /health* /plans* /memories* /tools* /mcp* /decisions* /manager* /preferences* /organizations* /learning* /cases* /vehicles*
```

Validate and reload Caddy:

Run: `docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile`
Expected: `Valid configuration`

Run: `docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile`

- [ ] **Step 6: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_vehicles_router.py -v`
Expected: `2 passed`

- [ ] **Step 7: Commit**

```bash
git add services/api/src/api/vehicles_router.py services/api/src/api/main.py services/api/tests/test_vehicles_router.py infra/caddy/Caddyfile
git commit -m "Phase 19 task 1: Vehicle list endpoint + Caddy allowlist"
```

---

### Task 2: Direct lookup endpoint

**Files:**
- Modify: `services/api/src/api/vehicles_router.py` (append)
- Test: `services/api/tests/test_vehicles_router.py` (append)

**Interfaces:**
- Consumes: `lookup_vehicle` (`api/vehicle_agent.py`, Phase 18), `RdwLookupError` (`api/rdw_client.py`, Phase 18).
- Produces: `POST /vehicles/lookup` (body `{kenteken: str}`) returning `VehicleOut`, 502 on `RdwLookupError`.

- [ ] **Step 1: Write the failing tests**

Append to `services/api/tests/test_vehicles_router.py`:

```python
FAKE_RDW_DATA = {
    "voertuigsoort": "Personenauto", "merk": "TOYOTA", "handelsbenaming": "AYGO",
    "eerste_kleur": "GRIJS", "datum_eerste_toelating": "20180501",
    "vervaldatum_apk": "20270501", "wam_verzekerd": "Ja",
    "openstaande_terugroepactie_indicator": "Nee", "brandstofomschrijving": "Benzine",
    "massa_ledig_voertuig": "840", "aantal_cilinders": "3", "wielbasis": "2340",
    "catalogusprijs": "12500", "aantal_zitplaatsen": "4", "aantal_deuren": "5",
    "vermogen_massarijklaar": "51", "europese_voertuigcategorie": "M1",
}


async def test_lookup_vehicle_endpoint_returns_rdw_data(client):
    token = await _login(client, f"vehiclerouter-{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.vehicles_router.lookup_vehicle") as mock_lookup:
        mock_lookup.return_value = await _create_vehicle("LO-01-OK", merk="TOYOTA")
        response = await client.post("/vehicles/lookup", headers=headers, json={"kenteken": "LO-01-OK"})

    assert response.status_code == 200
    assert response.json()["merk"] == "TOYOTA"


async def test_lookup_vehicle_endpoint_returns_502_on_rdw_outage(client):
    from api.rdw_client import RdwLookupError

    token = await _login(client, f"vehiclerouter-{uuid4().hex[:8]}")
    headers = {"Authorization": f"Bearer {token}"}

    with patch("api.vehicles_router.lookup_vehicle", side_effect=RdwLookupError("boom")):
        response = await client.post("/vehicles/lookup", headers=headers, json={"kenteken": "ZZ-99-ZZ"})

    assert response.status_code == 502
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `docker compose exec -T api pytest tests/test_vehicles_router.py -v -k lookup`
Expected: FAIL with `404 Not Found` (route doesn't exist yet)

- [ ] **Step 3: Add the endpoint**

In `services/api/src/api/vehicles_router.py`, change the imports at the top from:

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import User, Vehicle
```

to:

```python
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import get_current_user
from api.db import get_db
from api.models import User, Vehicle
from api.rdw_client import RdwLookupError
from api.vehicle_agent import lookup_vehicle
```

Then append this class and endpoint after `list_vehicles_endpoint`:

```python
class VehicleLookupRequest(BaseModel):
    kenteken: str


@router.post("/vehicles/lookup", response_model=VehicleOut)
async def lookup_vehicle_endpoint(
    request: VehicleLookupRequest,
    current_user: User = Depends(get_current_user),
) -> Vehicle:
    try:
        return await lookup_vehicle(kenteken=request.kenteken)
    except RdwLookupError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_vehicles_router.py -v`
Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add services/api/src/api/vehicles_router.py services/api/tests/test_vehicles_router.py
git commit -m "Phase 19 task 2: direct vehicle lookup endpoint"
```

---

### Task 3: Vehicle↔Case linking

**Files:**
- Modify: `services/api/src/api/cases.py` (add `link_vehicle_to_case`, extend `get_case_dashboard`)
- Modify: `services/api/src/api/cases_router.py` (add `CaseVehicleOut`, extend `CaseDashboardOut`, add `link_vehicle_endpoint`)
- Test: `services/api/tests/test_cases.py` (append), `services/api/tests/test_cases_router.py` (append)

**Interfaces:**
- Consumes: `Vehicle` (`api/models.py`), `GraphEdge` (`api/models.py`, Phase 10).
- Produces: `link_vehicle_to_case(db, *, case_id: UUID, vehicle_id: UUID) -> bool`, `get_case_dashboard()`'s returned dict gains a `"vehicles": list[Vehicle]` key, `CaseDashboardOut.vehicles: list[CaseVehicleOut]`, `POST /cases/{case_id}/vehicles/{vehicle_id}`.

- [ ] **Step 1: Write the failing domain-logic test**

Append to `services/api/tests/test_cases.py`:

```python
from api.cases import link_vehicle_to_case
from api.models import Entity, Vehicle


async def _create_vehicle(kenteken: str) -> Vehicle:
    async with async_session() as db:
        entity = Entity(name=kenteken, entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken=kenteken)
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle


async def test_link_vehicle_to_case_and_dashboard_includes_it():
    user = User(username=_unique("caseuser"), display_name="Case User", role="member")
    async with async_session() as db:
        db.add(user)
        await db.commit()
        await db.refresh(user)

    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        vehicle = await _create_vehicle(_unique("VE") + "-01-ST")
        linked = await link_vehicle_to_case(db, case_id=case.id, vehicle_id=vehicle.id)
        assert linked is True

    async with async_session() as db:
        dashboard = await get_case_dashboard(db, case.id)
        assert [v.id for v in dashboard["vehicles"]] == [vehicle.id]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_cases.py -v -k link_vehicle`
Expected: FAIL with `ImportError: cannot import name 'link_vehicle_to_case'`

- [ ] **Step 3: Implement domain logic**

In `services/api/src/api/cases.py`, change the import line:

```python
from api.models import Case, Decision, Document, GraphEdge, Task
```

to:

```python
from api.models import Case, Decision, Document, GraphEdge, Task, Vehicle
```

Add this function after `link_decision_to_case`:

```python
async def link_vehicle_to_case(db: AsyncSession, *, case_id: UUID, vehicle_id: UUID) -> bool:
    case = await db.get(Case, case_id)
    vehicle = await db.get(Vehicle, vehicle_id)
    if case is None or vehicle is None:
        return False
    db.add(GraphEdge(
        source_type="vehicle", source_id=vehicle.id, target_type="case", target_id=case.id,
        relationship_type="belongs_to",
    ))
    await db.commit()
    return True
```

In `get_case_dashboard`, change:

```python
    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.target_type == "case", GraphEdge.target_id == case_id,
            GraphEdge.relationship_type == "belongs_to",
        )
    )
    edges = list(edges_result.scalars().all())
    task_ids = [edge.source_id for edge in edges if edge.source_type == "task"]
    decision_ids = [edge.source_id for edge in edges if edge.source_type == "decision"]

    tasks: list[Task] = []
    if task_ids:
        tasks_result = await db.execute(select(Task).where(Task.id.in_(task_ids)))
        tasks = list(tasks_result.scalars().all())

    decisions: list[Decision] = []
    if decision_ids:
        decisions_result = await db.execute(select(Decision).where(Decision.id.in_(decision_ids)))
        decisions = list(decisions_result.scalars().all())

    return {"case": case, "documents": documents, "tasks": tasks, "decisions": decisions}
```

to:

```python
    edges_result = await db.execute(
        select(GraphEdge).where(
            GraphEdge.target_type == "case", GraphEdge.target_id == case_id,
            GraphEdge.relationship_type == "belongs_to",
        )
    )
    edges = list(edges_result.scalars().all())
    task_ids = [edge.source_id for edge in edges if edge.source_type == "task"]
    decision_ids = [edge.source_id for edge in edges if edge.source_type == "decision"]
    vehicle_ids = [edge.source_id for edge in edges if edge.source_type == "vehicle"]

    tasks: list[Task] = []
    if task_ids:
        tasks_result = await db.execute(select(Task).where(Task.id.in_(task_ids)))
        tasks = list(tasks_result.scalars().all())

    decisions: list[Decision] = []
    if decision_ids:
        decisions_result = await db.execute(select(Decision).where(Decision.id.in_(decision_ids)))
        decisions = list(decisions_result.scalars().all())

    vehicles: list[Vehicle] = []
    if vehicle_ids:
        vehicles_result = await db.execute(select(Vehicle).where(Vehicle.id.in_(vehicle_ids)))
        vehicles = list(vehicles_result.scalars().all())

    return {"case": case, "documents": documents, "tasks": tasks, "decisions": decisions, "vehicles": vehicles}
```

Also add `AsyncSession`/`UUID` imports if not already present at the top of `cases.py` (they already are, per the existing `link_task_to_case` signature — no change needed there).

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api pytest tests/test_cases.py -v -k link_vehicle`
Expected: `1 passed`

- [ ] **Step 5: Write the failing router test**

Append to `services/api/tests/test_cases_router.py` (reuse this file's existing `_user_id_for` helper):

```python
async def _create_vehicle_router(kenteken: str) -> Vehicle:
    async with async_session() as db:
        entity = Entity(name=kenteken, entity_type="vehicle")
        db.add(entity)
        await db.flush()
        vehicle = Vehicle(entity_id=entity.id, kenteken=kenteken)
        db.add(vehicle)
        await db.commit()
        await db.refresh(vehicle)
        return vehicle


async def test_link_vehicle_to_case(client):
    token = await _login(client, "caserouteruser21")
    headers = {"Authorization": f"Bearer {token}"}
    vehicle = await _create_vehicle_router(f"LV-{uuid4().hex[:2].upper()}-ST")

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    link_response = await client.post(f"/cases/{case_id}/vehicles/{vehicle.id}", headers=headers)
    assert link_response.status_code == 204

    dashboard = await client.get(f"/cases/{case_id}", headers=headers)
    assert [v["id"] for v in dashboard.json()["vehicles"]] == [str(vehicle.id)]


async def test_link_vehicle_to_case_rejects_unknown_vehicle(client):
    token = await _login(client, "caserouteruser22")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post("/cases", headers=headers, json={"name": "A case"})
    case_id = create_response.json()["id"]

    response = await client.post(f"/cases/{case_id}/vehicles/{uuid4()}", headers=headers)
    assert response.status_code == 404
```

Add `Entity, Vehicle` to this file's existing `from api.models import Decision, Document, Task, User` import line, making it `from api.models import Decision, Document, Entity, Task, User, Vehicle`.

- [ ] **Step 6: Run test to verify it fails**

Run: `docker compose exec -T api pytest tests/test_cases_router.py -v -k link_vehicle`
Expected: FAIL with `404 Not Found` on `POST /cases/{case_id}/vehicles/{vehicle_id}` for the first test too (route doesn't exist yet), so both tests fail the same way at this point.

- [ ] **Step 7: Implement the router changes**

In `services/api/src/api/cases_router.py`, change the imports:

```python
from api.cases import (
    attach_document_to_case,
    create_case,
    delete_case,
    get_case_dashboard,
    link_decision_to_case,
    link_task_to_case,
    list_cases,
    update_case,
)
from api.db import get_db
from api.models import Case, Decision, Document, Task, User
```

to:

```python
from api.cases import (
    attach_document_to_case,
    create_case,
    delete_case,
    get_case_dashboard,
    link_decision_to_case,
    link_task_to_case,
    link_vehicle_to_case,
    list_cases,
    update_case,
)
from api.db import get_db
from api.models import Case, Decision, Document, Task, User, Vehicle
```

Add this class after `CaseDecisionOut`:

```python
class CaseVehicleOut(BaseModel):
    id: UUID
    kenteken: str | None
    merk: str | None
    handelsbenaming: str | None
```

Change `CaseDashboardOut` from:

```python
class CaseDashboardOut(CaseOut):
    documents: list[CaseDocumentOut]
    tasks: list[CaseTaskOut]
    decisions: list[CaseDecisionOut]
```

to:

```python
class CaseDashboardOut(CaseOut):
    documents: list[CaseDocumentOut]
    tasks: list[CaseTaskOut]
    decisions: list[CaseDecisionOut]
    vehicles: list[CaseVehicleOut]
```

In `get_case_endpoint`, change:

```python
    return CaseDashboardOut(
        id=case.id, name=case.name, description=case.description, status=case.status, created_at=case.created_at,
        documents=[CaseDocumentOut(id=doc.id, title=doc.title) for doc in result["documents"]],
        tasks=[CaseTaskOut(id=task.id, title=task.title, status=task.status) for task in result["tasks"]],
        decisions=[CaseDecisionOut(id=dec.id, summary=dec.summary) for dec in result["decisions"]],
    )
```

to:

```python
    return CaseDashboardOut(
        id=case.id, name=case.name, description=case.description, status=case.status, created_at=case.created_at,
        documents=[CaseDocumentOut(id=doc.id, title=doc.title) for doc in result["documents"]],
        tasks=[CaseTaskOut(id=task.id, title=task.title, status=task.status) for task in result["tasks"]],
        decisions=[CaseDecisionOut(id=dec.id, summary=dec.summary) for dec in result["decisions"]],
        vehicles=[
            CaseVehicleOut(id=v.id, kenteken=v.kenteken, merk=v.merk, handelsbenaming=v.handelsbenaming)
            for v in result["vehicles"]
        ],
    )
```

Add this endpoint after `link_decision_endpoint` (note: no ownership check on the vehicle itself, unlike `link_task_endpoint`/`link_decision_endpoint` — vehicles have no owner field):

```python
@router.post("/cases/{case_id}/vehicles/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def link_vehicle_endpoint(
    case_id: UUID,
    vehicle_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    case = await db.get(Case, case_id)
    if case is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found")
    _require_case_owner(case, current_user)

    vehicle = await db.get(Vehicle, vehicle_id)
    if vehicle is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Vehicle not found")

    await link_vehicle_to_case(db, case_id=case_id, vehicle_id=vehicle_id)
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `docker compose exec -T api pytest tests/test_cases.py tests/test_cases_router.py -v -k vehicle`
Expected: `3 passed`

- [ ] **Step 9: Run the full backend test suite and ruff**

Run: `docker compose exec -T api pytest -q`
Expected: same pass/fail counts as the Phase 18 baseline (242 passed, 6 pre-existing unrelated failures), plus this task's new tests passing.

Run: `docker compose exec -T api ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 10: Commit**

```bash
git add services/api/src/api/cases.py services/api/src/api/cases_router.py services/api/tests/test_cases.py services/api/tests/test_cases_router.py
git commit -m "Phase 19 task 3: Vehicle-Case linking"
```

---

### Task 4: Frontend API client additions

**Files:**
- Modify: `apps/web/src/lib/api.ts`

**Interfaces:**
- Produces: `VehicleOut` interface, `listVehicles(): Promise<VehicleOut[]>`, `lookupVehicle(kenteken: string): Promise<VehicleOut>`, `linkVehicleToCase(caseId: string, vehicleId: string): Promise<void>`; `CaseDashboardOut` extended with `vehicles: CaseVehicleOut[]`.

- [ ] **Step 1: Add the interfaces and functions**

In `apps/web/src/lib/api.ts`, change:

```typescript
export interface CaseDashboardOut extends CaseOut {
  documents: { id: string; title: string }[];
  tasks: { id: string; title: string; status: string }[];
  decisions: { id: string; summary: string }[];
}
```

to:

```typescript
export interface CaseDashboardOut extends CaseOut {
  documents: { id: string; title: string }[];
  tasks: { id: string; title: string; status: string }[];
  decisions: { id: string; summary: string }[];
  vehicles: { id: string; kenteken: string | null; merk: string | null; handelsbenaming: string | null }[];
}
```

Add this after `linkDecisionToCase`'s definition:

```typescript
export interface VehicleOut {
  id: string;
  kenteken: string | null;
  vin: string | null;
  voertuigsoort: string | null;
  merk: string | null;
  handelsbenaming: string | null;
  eerste_kleur: string | null;
  datum_eerste_toelating: string | null;
  vervaldatum_apk: string | null;
  wam_verzekerd: string | null;
  openstaande_terugroepactie_indicator: string | null;
  brandstofomschrijving: string | null;
  fetched_at: string | null;
  created_at: string;
}

export function listVehicles(): Promise<VehicleOut[]> {
  return request<VehicleOut[]>("/vehicles");
}

export function lookupVehicle(kenteken: string): Promise<VehicleOut> {
  return request<VehicleOut>("/vehicles/lookup", {
    method: "POST",
    body: JSON.stringify({ kenteken }),
  });
}

export function linkVehicleToCase(caseId: string, vehicleId: string): Promise<void> {
  return request<void>(`/cases/${caseId}/vehicles/${vehicleId}`, { method: "POST" });
}
```

- [ ] **Step 2: Typecheck**

Run: `docker compose exec -T web pnpm exec tsc -b`
Expected: no output (no type errors) — there will be a pre-existing error only if `CaseDetail.tsx` isn't updated yet to handle the new required `vehicles` field; Task 7 fixes that, so a transient error here referencing `CaseDetail.tsx` is expected and resolved by Task 7, not this task.

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/lib/api.ts
git commit -m "Phase 19 task 4: api.ts additions for vehicles"
```

---

### Task 5: `LicensePlateInput` component

**Files:**
- Create: `apps/web/src/components/LicensePlateInput.tsx`

**Interfaces:**
- Produces: `LicensePlateInput({ value, onChange }: { value: string; onChange: (value: string) => void })` — a controlled component. Task 6 consumes this.

- [ ] **Step 1: Create the component**

Create `apps/web/src/components/LicensePlateInput.tsx`:

```tsx
export default function LicensePlateInput({
  value,
  onChange,
}: {
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="inline-flex overflow-hidden rounded-md border-2 border-black shadow-sm">
      <div className="flex w-7 flex-col items-center justify-end bg-blue-800 pb-1 pt-1 text-white">
        <span className="text-[9px] leading-none text-yellow-400">★★★</span>
        <span className="text-[11px] font-bold leading-none">NL</span>
      </div>
      <div className="flex items-center bg-yellow-400 px-3 py-1.5">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value.toUpperCase())}
          placeholder="AB-12-CD"
          className="w-48 bg-transparent text-center font-sans text-2xl font-bold tracking-widest text-black placeholder:text-black/30 focus:outline-none"
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `docker compose exec -T web pnpm exec tsc -b`
Expected: no new errors introduced by this file (the pre-existing `CaseDetail.tsx` error from Task 4 may still show — unrelated to this step).

- [ ] **Step 3: Commit**

```bash
git add apps/web/src/components/LicensePlateInput.tsx
git commit -m "Phase 19 task 5: LicensePlateInput component"
```

---

### Task 6: `/vehicles` page + navigation

**Files:**
- Create: `apps/web/src/routes/Vehicles.tsx`
- Modify: `apps/web/src/components/Sidebar.tsx` (add nav item)
- Modify: `apps/web/src/App.tsx` (add route)

**Interfaces:**
- Consumes: `listVehicles`, `lookupVehicle`, `VehicleOut`, `ApiError` (`lib/api.ts`), `LicensePlateInput` (Task 5), `Card`, `EmptyState` (existing, Phase 17a).

- [ ] **Step 1: Create the page**

Create `apps/web/src/routes/Vehicles.tsx`:

```tsx
import { useEffect, useState } from "react";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import LicensePlateInput from "../components/LicensePlateInput";
import { ApiError, listVehicles, lookupVehicle, type VehicleOut } from "../lib/api";

function VehicleStatus({ vehicle }: { vehicle: VehicleOut }) {
  if (vehicle.fetched_at === null) {
    return <p className="text-sm text-slate-400">Nog niet opgehaald.</p>;
  }
  if (vehicle.merk === null) {
    return <p className="text-sm text-slate-400">Geen RDW-gegevens gevonden voor dit kenteken.</p>;
  }
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
      <dt className="text-slate-500">Merk / model</dt>
      <dd>{vehicle.merk} {vehicle.handelsbenaming}</dd>
      <dt className="text-slate-500">Voertuigsoort</dt>
      <dd>{vehicle.voertuigsoort ?? "-"}</dd>
      <dt className="text-slate-500">Kleur</dt>
      <dd>{vehicle.eerste_kleur ?? "-"}</dd>
      <dt className="text-slate-500">APK-vervaldatum</dt>
      <dd>{vehicle.vervaldatum_apk ?? "-"}</dd>
      <dt className="text-slate-500">WAM-verzekerd</dt>
      <dd>{vehicle.wam_verzekerd ?? "-"}</dd>
    </dl>
  );
}

export default function Vehicles() {
  const [vehicles, setVehicles] = useState<VehicleOut[]>([]);
  const [kenteken, setKenteken] = useState("");
  const [loading, setLoading] = useState(true);
  const [searching, setSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function refresh() {
    setLoading(true);
    listVehicles()
      .then(setVehicles)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load vehicles"))
      .finally(() => setLoading(false));
  }

  useEffect(refresh, []);

  async function handleSearch() {
    if (!kenteken.trim()) return;
    setSearching(true);
    setError(null);
    try {
      await lookupVehicle(kenteken.trim());
      setKenteken("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to look up vehicle");
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-semibold">Vehicles</h1>

      <Card className="flex flex-col gap-3">
        <div className="flex items-center gap-3">
          <LicensePlateInput value={kenteken} onChange={setKenteken} />
          <button
            onClick={handleSearch}
            disabled={searching || !kenteken.trim()}
            className="rounded bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-700 disabled:opacity-50"
          >
            Zoek op
          </button>
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
      </Card>

      {loading ? (
        <p className="text-slate-500">Loading…</p>
      ) : vehicles.length === 0 ? (
        <EmptyState message="No vehicles detected yet." />
      ) : (
        <div className="flex flex-col gap-3">
          {vehicles.map((vehicle) => (
            <Card key={vehicle.id}>
              <p className="mb-2 font-mono text-lg font-bold tracking-wider">{vehicle.kenteken ?? vehicle.vin}</p>
              <VehicleStatus vehicle={vehicle} />
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Add the sidebar nav item**

In `apps/web/src/components/Sidebar.tsx`, change:

```tsx
const NAV_ITEMS = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
  { to: "/cases", label: "Cases" },
  { to: "/assistant", label: "Assistant" },
  { to: "/settings", label: "Settings" },
];
```

to:

```tsx
const NAV_ITEMS = [
  { to: "/", label: "Documents" },
  { to: "/chat", label: "AI Chat" },
  { to: "/legal", label: "Legal Draft" },
  { to: "/tasks", label: "Tasks" },
  { to: "/entities", label: "Entities" },
  { to: "/cases", label: "Cases" },
  { to: "/vehicles", label: "Vehicles" },
  { to: "/assistant", label: "Assistant" },
  { to: "/settings", label: "Settings" },
];
```

- [ ] **Step 3: Add the route**

In `apps/web/src/App.tsx`, add this import after `import Cases from "./routes/Cases";`:

```tsx
import Vehicles from "./routes/Vehicles";
```

Add this route after the `/cases/:id` route and before `/assistant`:

```tsx
<Route
  path="/vehicles"
  element={
    <ProtectedRoute>
      <Vehicles />
    </ProtectedRoute>
  }
/>
```

- [ ] **Step 4: Typecheck**

Run: `docker compose exec -T web pnpm exec tsc -b`
Expected: no output (the `CaseDetail.tsx` error from Task 4 is still expected until Task 7).

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/routes/Vehicles.tsx apps/web/src/components/Sidebar.tsx apps/web/src/App.tsx
git commit -m "Phase 19 task 6: /vehicles page and navigation"
```

---

### Task 7: Case detail — Vehicles attach section

**Files:**
- Modify: `apps/web/src/routes/CaseDetail.tsx`

**Interfaces:**
- Consumes: `listVehicles`, `linkVehicleToCase`, `VehicleOut` (`lib/api.ts`).

- [ ] **Step 1: Update imports and state**

In `apps/web/src/routes/CaseDetail.tsx`, change:

```tsx
import {
  ApiError,
  attachDocumentToCase,
  getCase,
  linkDecisionToCase,
  linkTaskToCase,
  listDecisions,
  listDocuments,
  listTasks,
  updateCaseStatus,
  type CaseDashboardOut,
  type DecisionListItemOut,
  type DocumentOut,
  type TaskOut,
} from "../lib/api";

type AttachSection = "documents" | "tasks" | "decisions";
```

to:

```tsx
import {
  ApiError,
  attachDocumentToCase,
  getCase,
  linkDecisionToCase,
  linkTaskToCase,
  linkVehicleToCase,
  listDecisions,
  listDocuments,
  listTasks,
  listVehicles,
  updateCaseStatus,
  type CaseDashboardOut,
  type DecisionListItemOut,
  type DocumentOut,
  type TaskOut,
  type VehicleOut,
} from "../lib/api";

type AttachSection = "documents" | "tasks" | "decisions" | "vehicles";
```

Change:

```tsx
  const [allDocuments, setAllDocuments] = useState<DocumentOut[]>([]);
  const [allTasks, setAllTasks] = useState<TaskOut[]>([]);
  const [allDecisions, setAllDecisions] = useState<DecisionListItemOut[]>([]);
```

to:

```tsx
  const [allDocuments, setAllDocuments] = useState<DocumentOut[]>([]);
  const [allTasks, setAllTasks] = useState<TaskOut[]>([]);
  const [allDecisions, setAllDecisions] = useState<DecisionListItemOut[]>([]);
  const [allVehicles, setAllVehicles] = useState<VehicleOut[]>([]);
```

Change:

```tsx
  useEffect(() => {
    refresh();
    listDocuments().then(setAllDocuments).catch(() => undefined);
    listTasks().then(setAllTasks).catch(() => undefined);
    listDecisions().then(setAllDecisions).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
```

to:

```tsx
  useEffect(() => {
    refresh();
    listDocuments().then(setAllDocuments).catch(() => undefined);
    listTasks().then(setAllTasks).catch(() => undefined);
    listDecisions().then(setAllDecisions).catch(() => undefined);
    listVehicles().then(setAllVehicles).catch(() => undefined);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);
```

- [ ] **Step 2: Wire up the attach handler and options**

Change:

```tsx
  async function handleAttach() {
    if (!caseData || !selected) return;
    try {
      if (attaching === "documents") await attachDocumentToCase(selected, caseData.id);
      if (attaching === "tasks") await linkTaskToCase(caseData.id, selected);
      if (attaching === "decisions") await linkDecisionToCase(caseData.id, selected);
      setAttaching(null);
      setSelected("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to attach item");
    }
  }
```

to:

```tsx
  async function handleAttach() {
    if (!caseData || !selected) return;
    try {
      if (attaching === "documents") await attachDocumentToCase(selected, caseData.id);
      if (attaching === "tasks") await linkTaskToCase(caseData.id, selected);
      if (attaching === "decisions") await linkDecisionToCase(caseData.id, selected);
      if (attaching === "vehicles") await linkVehicleToCase(caseData.id, selected);
      setAttaching(null);
      setSelected("");
      refresh();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to attach item");
    }
  }
```

Change:

```tsx
  const linkedDocumentIds = new Set(caseData.documents.map((d) => d.id));
  const linkedTaskIds = new Set(caseData.tasks.map((t) => t.id));
  const linkedDecisionIds = new Set(caseData.decisions.map((d) => d.id));

  const attachOptions: Record<AttachSection, { id: string; label: string }[]> = {
    documents: allDocuments.filter((d) => !linkedDocumentIds.has(d.id)).map((d) => ({ id: d.id, label: d.title })),
    tasks: allTasks.filter((t) => !linkedTaskIds.has(t.id)).map((t) => ({ id: t.id, label: t.title })),
    decisions: allDecisions.filter((d) => !linkedDecisionIds.has(d.id)).map((d) => ({ id: d.id, label: d.summary })),
  };
```

to:

```tsx
  const linkedDocumentIds = new Set(caseData.documents.map((d) => d.id));
  const linkedTaskIds = new Set(caseData.tasks.map((t) => t.id));
  const linkedDecisionIds = new Set(caseData.decisions.map((d) => d.id));
  const linkedVehicleIds = new Set(caseData.vehicles.map((v) => v.id));

  const attachOptions: Record<AttachSection, { id: string; label: string }[]> = {
    documents: allDocuments.filter((d) => !linkedDocumentIds.has(d.id)).map((d) => ({ id: d.id, label: d.title })),
    tasks: allTasks.filter((t) => !linkedTaskIds.has(t.id)).map((t) => ({ id: t.id, label: t.title })),
    decisions: allDecisions.filter((d) => !linkedDecisionIds.has(d.id)).map((d) => ({ id: d.id, label: d.summary })),
    vehicles: allVehicles
      .filter((v) => !linkedVehicleIds.has(v.id))
      .map((v) => ({ id: v.id, label: v.kenteken ?? v.vin ?? v.id })),
  };
```

- [ ] **Step 3: Add the Vehicles card section**

Add this `Card` block after the Decisions `Card` block, before the closing `</div>` of the component's returned JSX:

```tsx
      <Card>
        <div className="mb-2 flex items-center justify-between">
          <span className="text-sm font-medium">Vehicles</span>
          <AttachControl section="vehicles" />
        </div>
        {caseData.vehicles.length === 0 ? (
          <p className="text-sm text-slate-400">Nothing linked yet.</p>
        ) : (
          <ul className="flex flex-col gap-1">
            {caseData.vehicles.map((v) => (
              <li key={v.id} className="text-sm">
                {v.kenteken} {v.merk && <span className="text-xs text-slate-400">({v.merk} {v.handelsbenaming})</span>}
              </li>
            ))}
          </ul>
        )}
      </Card>
```

- [ ] **Step 4: Typecheck**

Run: `docker compose exec -T web pnpm exec tsc -b`
Expected: no output (no type errors) — this resolves the transient `CaseDashboardOut.vehicles` error from Task 4.

- [ ] **Step 5: Run the frontend test suite**

Run: `docker compose exec -T web pnpm test -- --run`
Expected: `5 passed` (unchanged — this phase adds no new `vitest` tests, matching every prior UI phase's convention of relying on `tsc -b` + live browser verification instead, since this codebase has no React component testing library).

- [ ] **Step 6: Commit**

```bash
git add apps/web/src/routes/CaseDetail.tsx
git commit -m "Phase 19 task 7: Case detail Vehicles attach section"
```

---

### Task 8: ADR, README, and live verification

**Files:**
- Create: `docs/adr/0037-phase19-vehicles-page.md`
- Modify: `README.md`

**Interfaces:** None — this task documents and verifies, it doesn't add code.

- [ ] **Step 1: Write the ADR**

Create `docs/adr/0037-phase19-vehicles-page.md`:

```markdown
# ADR 0037: Phase 19 — Vehicles Page (List, Plate-Styled Lookup, Case Linking)

## Status
Accepted

## Context

Phase 18 (ADR 0036) built kenteken/VIN detection and RDW enrichment
entirely backend-only -- `lookup_vehicle` was reachable only via the
Manager Agent/MCP Tool Registry, with no REST endpoint and no frontend
page. This phase closes that gap with `/vehicles`, and additionally
lets vehicles link to Cases (Phase 16, ADR 0031) the same way
Documents/Tasks/Decisions already do. Full design rationale is in
`docs/superpowers/specs/2026-07-04-vehicles-page-design.md`.

## Decision

**A new `vehicles_router.py`** adds `GET /vehicles` (list, full RDW
payload) and `POST /vehicles/lookup` (direct REST wrapper around
Phase 18's `vehicle_agent.lookup_vehicle`) -- the first REST surface
for vehicle data. Both require only authentication, matching
`GET /entities`'s existing simplicity rather than duplicating the Tool
Registry's `vehicles.write` permission check.

**Vehicle↔Case linking reuses `graph_edges`**, identical to how
Task/Decision link to a Case: `POST /cases/{case_id}/vehicles/{vehicle_id}`.
Unlike Task/Decision linking, there's no ownership check on the vehicle
itself -- vehicles (like all entities) have no owner field.

**`LicensePlateInput.tsx`** is a real Dutch-plate-styled input (yellow
background, black bold text, blue "NL" band with EU stars) chosen over
a segmented multi-box input or a plain-input-plus-preview, confirmed
via a visual mockup comparison during brainstorming.

**`/vehicles`** shows this input plus a card-per-vehicle list, each
card distinguishing three states via `fetched_at`/`merk`: not yet
looked up, looked up but RDW had no match, or full RDW details.

**Built as one phase, not split into a/b sub-phases** like Phase
16->17b -- an explicit choice, even though it crosses backend and
frontend.

## Consequences

- **Deferred, not solved**: unlinking a vehicle from a case (Task/
  Decision have no unlink endpoint either); client-side kenteken
  format validation (RDW remains the sole source of truth); deleting a
  vehicle entity (no entity type in this codebase has a delete
  endpoint).
- Looking up a mistyped/nonexistent kenteken still permanently creates
  a `Vehicle`/`Entity` row with no RDW data (Phase 18's existing
  behavior, unchanged) -- the `/vehicles` list can accumulate "not
  found" entries over time from typos.
- No component-level test coverage was added for `Vehicles.tsx`/
  `LicensePlateInput.tsx` -- same reasoning as every prior frontend
  phase's ADR: this codebase has no React component testing library.
  Verified via `tsc -b` plus a live browser check.
```

- [ ] **Step 2: Update the README**

In `README.md`, update the `## Status` line to reference Phase 19, and add one bullet for **Phase 19** to both the `services/api covers` prose list and the numbered `## Phases` list at the bottom, following the exact format the Phase 16/17/18 entries already use (see those bullets for the format to match — each ends with `See ADR 0037.`).

- [ ] **Step 3: Rebuild the production frontend bundle**

Run: `docker compose exec -e VITE_API_URL='' web sh -c "cd /app/apps/web && pnpm build"`
Expected: build completes with no errors.

- [ ] **Step 4: Run the full backend test suite and ruff**

Run: `docker compose exec -T api pytest -q`
Expected: same pre-existing 6 unrelated failures only; every Phase 19 test passing (should now total roughly 250 passed).

Run: `docker compose exec -T api ruff check src/ tests/`
Expected: `All checks passed!`

- [ ] **Step 5: Live browser verification**

Using the Playwright MCP tools against `https://v78281.1blu.de`:
1. Navigate to `/vehicles`, confirm the sidebar shows "Vehicles" and the plate-styled input renders (yellow/blue).
2. Type a kenteken into the plate input, click "Zoek op", confirm a new card appears in the list below.
3. Navigate to `/cases`, open (or create) a case, click "+ Attach" under the new Vehicles section, select the vehicle just looked up, click Attach, and confirm it now appears under the case's Vehicles list.

- [ ] **Step 6: Commit**

```bash
git add docs/adr/0037-phase19-vehicles-page.md README.md
git commit -m "Phase 19 task 8: ADR + README"
```

- [ ] **Step 7: Push and open a PR**

```bash
git push -u origin phase-19-vehicles-page
gh pr create --title "Phase 19: Vehicles page (list, plate-styled lookup, case linking)" --body "Implements docs/superpowers/specs/2026-07-04-vehicles-page-design.md: GET /vehicles, POST /vehicles/lookup, Vehicle-Case linking via graph_edges, a new /vehicles page with a Dutch-plate-styled kenteken input, and a Vehicles attach section on the Case detail page. See ADR 0037."
```

Then proceed with `superpowers:finishing-a-development-branch` to verify tests one final time and merge.
