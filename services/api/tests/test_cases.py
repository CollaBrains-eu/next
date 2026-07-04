from uuid import uuid4

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
from api.db import async_session
from api.models import Case, Decision, Document, Entity, GraphEdge, Task, User, Vehicle


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


async def _create_user(username: str) -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def test_case_can_be_created_and_defaults_to_open_status():
    user = await _create_user(_unique("caseuser"))

    async with async_session() as db:
        case = Case(user_id=user.id, name="Smith v. Jones")
        db.add(case)
        await db.commit()
        await db.refresh(case)

    assert case.status == "open"
    assert case.description is None


async def test_document_case_id_defaults_to_none():
    user = await _create_user(_unique("caseuser"))

    async with async_session() as db:
        document = Document(
            owner_id=user.id, title="t", filename="t.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

    assert document.case_id is None


async def _create_document(owner_id) -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="t.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


async def _create_task(created_by) -> Task:
    async with async_session() as db:
        task = Task(title="Do the thing", source="manual", created_by=created_by)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task


async def _create_decision(user_id) -> Decision:
    async with async_session() as db:
        decision = Decision(user_id=user_id, summary="Approved something")
        db.add(decision)
        await db.commit()
        await db.refresh(decision)
        return decision


async def test_create_case_persists_it():
    user = await _create_user(_unique("caseuser"))
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="Smith v. Jones", description="A matter")
    assert case.name == "Smith v. Jones"
    assert case.description == "A matter"


async def test_list_cases_scoped_to_user():
    user = await _create_user(_unique("caseuser"))
    other = await _create_user(_unique("caseuser"))
    async with async_session() as db:
        await create_case(db, user_id=user.id, name="Mine")
        await create_case(db, user_id=other.id, name="Not mine")

    async with async_session() as db:
        cases = await list_cases(db, user_id=user.id)
    assert all(c.user_id == user.id for c in cases)
    assert any(c.name == "Mine" for c in cases)
    assert not any(c.name == "Not mine" for c in cases)


async def test_update_case_changes_only_given_fields():
    user = await _create_user(_unique("caseuser"))
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="Original", description="Orig desc")

    async with async_session() as db:
        updated = await update_case(db, case_id=case.id, status_value="closed")

    assert updated.name == "Original"
    assert updated.description == "Orig desc"
    assert updated.status == "closed"


async def test_update_case_returns_none_for_unknown_id():
    async with async_session() as db:
        result = await update_case(db, case_id=uuid4(), name="x")
    assert result is None


async def test_attach_document_to_case_sets_case_id():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")

    async with async_session() as db:
        updated = await attach_document_to_case(db, document_id=document.id, case_id=case.id)
    assert updated.case_id == case.id


async def test_attach_document_to_case_with_none_detaches():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)

    async with async_session() as db:
        updated = await attach_document_to_case(db, document_id=document.id, case_id=None)
    assert updated.case_id is None


async def test_link_task_to_case_creates_graph_edge():
    user = await _create_user(_unique("caseuser"))
    task = await _create_task(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        linked = await link_task_to_case(db, case_id=case.id, task_id=task.id)
    assert linked is True

    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(GraphEdge).where(
                GraphEdge.source_type == "task", GraphEdge.source_id == task.id,
                GraphEdge.target_type == "case", GraphEdge.target_id == case.id,
            )
        )
        edges = result.scalars().all()
    assert len(edges) == 1
    assert edges[0].relationship_type == "belongs_to"


async def test_link_decision_to_case_creates_graph_edge():
    user = await _create_user(_unique("caseuser"))
    decision = await _create_decision(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        linked = await link_decision_to_case(db, case_id=case.id, decision_id=decision.id)
    assert linked is True


async def test_get_case_dashboard_assembles_documents_tasks_decisions():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    task = await _create_task(user.id)
    decision = await _create_decision(user.id)

    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)
        await link_task_to_case(db, case_id=case.id, task_id=task.id)
        await link_decision_to_case(db, case_id=case.id, decision_id=decision.id)

    async with async_session() as db:
        dashboard = await get_case_dashboard(db, case.id)

    assert dashboard["case"].id == case.id
    assert [d.id for d in dashboard["documents"]] == [document.id]
    assert [t.id for t in dashboard["tasks"]] == [task.id]
    assert [dec.id for dec in dashboard["decisions"]] == [decision.id]


async def test_get_case_dashboard_returns_none_for_unknown_id():
    async with async_session() as db:
        dashboard = await get_case_dashboard(db, uuid4())
    assert dashboard is None


async def test_delete_case_removes_it_and_its_graph_edges():
    user = await _create_user(_unique("caseuser"))
    task = await _create_task(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await link_task_to_case(db, case_id=case.id, task_id=task.id)

    async with async_session() as db:
        deleted = await delete_case(db, case_id=case.id)
    assert deleted is True

    async with async_session() as db:
        from sqlalchemy import select
        remaining_edges = (
            await db.execute(select(GraphEdge).where(GraphEdge.target_type == "case", GraphEdge.target_id == case.id))
        ).scalars().all()
        remaining_case = await db.get(Case, case.id)
    assert remaining_edges == []
    assert remaining_case is None


async def test_delete_case_nulls_document_case_id():
    user = await _create_user(_unique("caseuser"))
    document = await _create_document(user.id)
    async with async_session() as db:
        case = await create_case(db, user_id=user.id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)
        await delete_case(db, case_id=case.id)

    async with async_session() as db:
        refreshed = await db.get(Document, document.id)
    assert refreshed.case_id is None


async def test_delete_case_returns_false_for_unknown_id():
    async with async_session() as db:
        deleted = await delete_case(db, case_id=uuid4())
    assert deleted is False


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
