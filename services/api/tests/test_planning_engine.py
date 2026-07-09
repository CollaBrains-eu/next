import uuid as uuid_module
from unittest.mock import patch

from sqlalchemy import select

from api.db import async_session
from api.ldap_auth import LdapIdentity
from api.models import DEFAULT_ORGANIZATION_ID, Document
from api.organizations import set_organization_policies
from api.planning_engine import (
    approve_plan,
    build_steps,
    create_plan,
    execute_plan,
    generate_timeline,
    organize_document_collection,
)

FAKE_EMBEDDING = [0.1] * 768


def _unique(base: str) -> str:
    return f"{base}-{uuid_module.uuid4().hex[:8]}"


async def _login(client, base_username: str) -> tuple[str, str]:
    username = _unique(base_username)
    identity = LdapIdentity(username=username, display_name=username, email=f"{username}@collabrains.eu", is_admin=False)
    with patch("api.auth.ldap_authenticate", return_value=identity):
        response = await client.post("/auth/token", data={"username": username, "password": "whatever"})
    return response.json()["access_token"], username


async def _upload_ready_document(client, headers, text: str) -> str:
    with (
        patch("api.documents.submit_document", return_value="task-x"),
        patch("api.documents.wait_for_paperless_id", return_value=99),
        patch("api.documents.fetch_document_text", return_value=text),
        patch("api.documents.embed_text", return_value=FAKE_EMBEDDING),
        patch("api.documents.settings.auto_extract_tasks_on_ready", False),
        patch("api.documents.settings.auto_extract_entities_on_ready", False),
    ):
        upload = await client.post(
            "/documents", headers=headers, files={"file": ("notes.txt", text.encode(), "text/plain")}
        )
    return upload.json()["id"]


async def _user_id_for(username: str):
    from api.models import User

    async with async_session() as db:
        return (await db.execute(select(User).where(User.username == username))).scalar_one().id


# --- goal decomposition (build_steps) ---


def test_build_steps_summarize_case_one_step_per_document():
    steps = build_steps("summarize_case", {"document_ids": ["a", "b", "c"]})
    assert [s["agent"] for s in steps] == ["document_agent"] * 3
    assert [s["input_data"]["document_id"] for s in steps] == ["a", "b", "c"]


def test_build_steps_analyze_new_upload_three_agents_in_order():
    steps = build_steps("analyze_new_upload", {"document_id": "doc-1"})
    assert [s["agent"] for s in steps] == ["document_agent", "planner_agent", "entity_agent"]
    assert all(s["input_data"]["document_id"] == "doc-1" for s in steps)


def test_build_steps_prepare_objection_uses_canned_instruction_with_grounds():
    steps = build_steps("prepare_objection", {"grounds": "late filing", "document_ids": ["d1"]})
    assert len(steps) == 1
    assert steps[0]["agent"] == "legal_agent"
    assert "late filing" in steps[0]["input_data"]["instruction"]


def test_build_steps_draft_communication_one_step_with_all_fields():
    steps = build_steps(
        "draft_communication",
        {"instruction": "Remind about APK", "channel": "signal", "recipient": "+31600000000", "document_ids": ["d1"]},
    )
    assert len(steps) == 1
    assert steps[0]["agent"] == "communication_agent"
    assert steps[0]["input_data"] == {
        "instruction": "Remind about APK", "channel": "signal", "recipient": "+31600000000", "document_ids": ["d1"],
    }


def test_build_steps_draft_communication_requires_recipient():
    try:
        build_steps("draft_communication", {"instruction": "x", "channel": "signal"})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_steps_rejects_unknown_goal_type():
    try:
        build_steps("teleport_documents", {})
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_build_steps_rejects_missing_document_ids():
    try:
        build_steps("summarize_case", {})
        assert False, "expected ValueError"
    except ValueError:
        pass


# --- create_plan / approval gating ---


async def test_create_plan_for_read_goal_starts_running_no_approval_needed(client):
    token, username = await _login(client, "plan-read-user")
    user_id = await _user_id_for(username)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user_id, goal_type="organize_document_collection", goal_params={"document_ids": ["x"]}
        )

    assert plan.status == "running"
    assert plan.requires_approval is False


async def test_create_plan_for_legal_goal_starts_pending_approval(client):
    token, username = await _login(client, "plan-legal-user")
    user_id = await _user_id_for(username)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user_id, goal_type="draft_legal_document", goal_params={"instruction": "Draft a letter."}
        )

    assert plan.status == "pending_approval"
    assert plan.requires_approval is True


async def test_create_plan_honors_an_organization_level_approval_override(client):
    token, username = await _login(client, "plan-org-policy-user")
    user_id = await _user_id_for(username)

    async with async_session() as db:
        await set_organization_policies(
            db, organization_id=DEFAULT_ORGANIZATION_ID,
            policies={"approval_required_goals": ["organize_document_collection"]},
        )

    try:
        async with async_session() as db:
            # normally auto-runs with no approval (ADR 0019) -- the org
            # policy override makes it require approval instead (ADR 0029)
            plan = await create_plan(
                db, user_id=user_id, goal_type="organize_document_collection", goal_params={"document_ids": ["x"]}
            )

        assert plan.requires_approval is True
        assert plan.status == "pending_approval"
    finally:
        async with async_session() as db:
            await set_organization_policies(db, organization_id=DEFAULT_ORGANIZATION_ID, policies={})


async def test_create_plan_resolves_case_id_to_its_documents_for_summarize_case(client):
    from api.cases import attach_document_to_case, create_case

    token, username = await _login(client, "plan-case-user")
    user_id = await _user_id_for(username)

    async with async_session() as db:
        document_a = Document(
            owner_id=user_id, title="a", filename="a.pdf", mime_type="application/pdf", status="ready",
        )
        document_b = Document(
            owner_id=user_id, title="b", filename="b.pdf", mime_type="application/pdf", status="ready",
        )
        db.add_all([document_a, document_b])
        await db.commit()
        await db.refresh(document_a)
        await db.refresh(document_b)

        case = await create_case(db, user_id=user_id, name="A case")
        await attach_document_to_case(db, document_id=document_a.id, case_id=case.id)
        await attach_document_to_case(db, document_id=document_b.id, case_id=case.id)

    async with async_session() as db:
        plan = await create_plan(db, user_id=user_id, goal_type="summarize_case", goal_params={"case_id": str(case.id)})

    assert plan.status == "running"
    resolved_document_ids = set(plan.goal_params["document_ids"])
    assert resolved_document_ids == {str(document_a.id), str(document_b.id)}


async def test_create_plan_prefers_case_id_over_document_ids_when_both_given(client):
    from api.cases import attach_document_to_case, create_case

    token, username = await _login(client, "plan-case-precedence-user")
    user_id = await _user_id_for(username)

    async with async_session() as db:
        document = Document(
            owner_id=user_id, title="a", filename="a.pdf", mime_type="application/pdf", status="ready",
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)

        case = await create_case(db, user_id=user_id, name="A case")
        await attach_document_to_case(db, document_id=document.id, case_id=case.id)

    async with async_session() as db:
        plan = await create_plan(
            db, user_id=user_id, goal_type="summarize_case",
            goal_params={"case_id": str(case.id), "document_ids": ["ignored-value"]},
        )

    assert plan.goal_params["document_ids"] == [str(document.id)]


async def test_approve_plan_executes_and_completes():
    async with async_session() as db:
        from api.models import User

        user = User(username=_unique("plan-approve-user"), display_name="x", role="member")
        db.add(user)
        await db.commit()
        await db.refresh(user)

        plan = await create_plan(
            db, user_id=user.id, goal_type="draft_legal_document", goal_params={"instruction": "Draft a notice."}
        )

    assert plan.status == "pending_approval"

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="Draft text."),
    ):
        async with async_session() as db:
            approved = await approve_plan(db, plan_id=plan.id, user_id=user.id)

    assert approved.status == "completed"
    assert approved.approved_at is not None


async def test_approve_plan_rejects_non_owner():
    async with async_session() as db:
        from api.models import User

        owner = User(username=_unique("plan-owner"), display_name="x", role="member")
        intruder = User(username=_unique("plan-intruder"), display_name="x", role="member")
        db.add_all([owner, intruder])
        await db.commit()
        await db.refresh(owner)
        await db.refresh(intruder)

        plan = await create_plan(
            db, user_id=owner.id, goal_type="prepare_objection", goal_params={"grounds": "x"}
        )

    async with async_session() as db:
        result = await approve_plan(db, plan_id=plan.id, user_id=intruder.id)
    assert result is None


# --- sequential execution + partial failure recovery ---


async def test_execute_plan_runs_steps_sequentially_and_completes(client):
    token, username = await _login(client, "plan-exec-user")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for(username)

    doc_a = await _upload_ready_document(client, headers, "First document text.")
    doc_b = await _upload_ready_document(client, headers, "Second document text.")

    with patch("api.documents.chat_completion", return_value="A short summary."):
        async with async_session() as db:
            plan = await create_plan(
                db, user_id=user_id, goal_type="summarize_case", goal_params={"document_ids": [doc_a, doc_b]}
            )
            await execute_plan(db, plan_id=plan.id)
            await db.refresh(plan)

    assert plan.status == "completed"

    from api.models import PlanStep

    async with async_session() as db:
        steps = list(
            (await db.execute(select(PlanStep).where(PlanStep.plan_id == plan.id).order_by(PlanStep.step_index)))
            .scalars()
            .all()
        )
    assert [s.status for s in steps] == ["done", "done"]
    assert steps[0].result_data["summary"] == "A short summary."


async def test_execute_plan_dispatches_communication_agent(client):
    token, username = await _login(client, "plan-comm-user")
    user_id = await _user_id_for(username)

    with (
        patch("api.communication_agent.hybrid_search", return_value=[]),
        patch(
            "api.communication_agent.chat_completion",
            return_value='{"subject": null, "body": "Your appointment is confirmed."}',
        ),
    ):
        async with async_session() as db:
            plan = await create_plan(
                db, user_id=user_id, goal_type="draft_communication",
                goal_params={"instruction": "Confirm the appointment", "channel": "signal", "recipient": "+31600000002"},
            )
            await execute_plan(db, plan_id=plan.id)
            await db.refresh(plan)

    assert plan.status == "completed"

    from api.models import PlanStep

    async with async_session() as db:
        steps = list(
            (await db.execute(select(PlanStep).where(PlanStep.plan_id == plan.id).order_by(PlanStep.step_index)))
            .scalars()
            .all()
        )
    assert steps[0].agent == "communication_agent"
    assert steps[0].status == "done"
    assert steps[0].result_data["body"] == "Your appointment is confirmed."


async def test_execute_plan_isolates_a_failing_step_as_partially_failed(client):
    token, username = await _login(client, "plan-partial-user")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for(username)

    good_doc = await _upload_ready_document(client, headers, "Readable document text.")
    missing_doc_id = str(uuid_module.uuid4())  # no such document -> that step must fail

    with patch("api.documents.chat_completion", return_value="Summary of the good doc."):
        async with async_session() as db:
            plan = await create_plan(
                db,
                user_id=user_id,
                goal_type="summarize_case",
                goal_params={"document_ids": [good_doc, missing_doc_id]},
            )
            await execute_plan(db, plan_id=plan.id)
            await db.refresh(plan)

    assert plan.status == "partially_failed"

    from api.models import PlanStep

    async with async_session() as db:
        steps = list(
            (await db.execute(select(PlanStep).where(PlanStep.plan_id == plan.id).order_by(PlanStep.step_index)))
            .scalars()
            .all()
        )
    assert steps[0].status == "done"
    assert steps[1].status == "failed"
    assert steps[1].error is not None


async def test_analyze_new_upload_runs_summarize_then_extract_tasks_then_entities(client):
    token, username = await _login(client, "plan-analyze-user")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = await _user_id_for(username)

    doc_id = await _upload_ready_document(client, headers, "Alice must file the report by 2026-08-01.")

    tasks_json = '[{"title": "File the report", "description": null, "due_date": "2026-08-01", "assignee": "Alice"}]'
    entities_json = '{"entities": [], "relationships": []}'

    with (
        patch("api.documents.chat_completion", return_value="Summary text."),
        patch("api.planner_agent.chat_completion", return_value=tasks_json),
        patch("api.entity_agent.chat_completion", return_value=entities_json),
    ):
        async with async_session() as db:
            plan = await create_plan(
                db, user_id=user_id, goal_type="analyze_new_upload", goal_params={"document_id": doc_id}
            )
            await execute_plan(db, plan_id=plan.id)
            await db.refresh(plan)

    assert plan.status == "completed"

    from api.models import PlanStep

    async with async_session() as db:
        steps = list(
            (await db.execute(select(PlanStep).where(PlanStep.plan_id == plan.id).order_by(PlanStep.step_index)))
            .scalars()
            .all()
        )
    assert steps[0].result_data["summary"] == "Summary text."
    assert steps[1].result_data["task_count"] == 1
    assert steps[2].result_data["entity_count"] == 0


# --- deterministic aggregations (no LLM) ---


async def test_organize_document_collection_groups_entities_by_type(client):
    token, username = await _login(client, "plan-collection-user")
    headers = {"Authorization": f"Bearer {token}"}

    doc_id = await _upload_ready_document(client, headers, "Wanda Cole represents Beacon Inc.")

    from api.entity_agent import extract_entities

    fake_extraction = (
        '{"entities": [{"name": "Wanda Cole", "type": "person"}, {"name": "Beacon Inc", "type": "organization"}], '
        '"relationships": []}'
    )
    with patch("api.entity_agent.chat_completion", return_value=fake_extraction):
        async with async_session() as db:
            document = await db.get(Document, uuid_module.UUID(doc_id))
            await extract_entities(db, document_id=document.id, text=document.ocr_text, user_id=document.owner_id)

    async with async_session() as db:
        result = await organize_document_collection(db, [uuid_module.UUID(doc_id)])

    assert result["document_count"] == 1
    assert sorted(result["entities_by_type"]["person"]) == ["Wanda Cole"]
    assert sorted(result["entities_by_type"]["organization"]) == ["Beacon Inc"]


async def test_generate_timeline_orders_events_chronologically(client):
    token, username = await _login(client, "plan-timeline-user")
    headers = {"Authorization": f"Bearer {token}"}

    doc_id = await _upload_ready_document(client, headers, "Bob should call the client by 2026-01-15.")

    from api.planner_agent import extract_tasks

    fake_tasks = '[{"title": "Call the client", "description": null, "due_date": "2026-01-15", "assignee": "Bob"}]'
    with patch("api.planner_agent.chat_completion", return_value=fake_tasks):
        async with async_session() as db:
            document = await db.get(Document, uuid_module.UUID(doc_id))
            await extract_tasks(
                db, document_id=document.id, text=document.ocr_text, user_id=document.owner_id, source="planner_agent"
            )

    async with async_session() as db:
        timeline = await generate_timeline(db, [uuid_module.UUID(doc_id)])

    kinds = [event["kind"] for event in timeline]
    assert "document_uploaded" in kinds
    assert "task_due" in kinds
    assert timeline == sorted(timeline, key=lambda event: event["date"])


# --- HTTP layer ---


async def test_create_plan_endpoint_rejects_unknown_goal_type(client):
    token, _ = await _login(client, "plan-http-badgoal-user")
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/plans", headers=headers, json={"goal_type": "invent_a_new_law", "goal_params": {}}
    )
    assert response.status_code == 400


async def test_plan_http_round_trip_for_legal_goal_requires_approval(client):
    token, _ = await _login(client, "plan-http-legal-user")
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        "/plans",
        headers=headers,
        json={"goal_type": "prepare_objection", "goal_params": {"grounds": "missed deadline"}},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["status"] == "pending_approval"
    assert body["steps"][0]["status"] == "pending"

    plan_id = body["id"]

    with (
        patch("api.legal.hybrid_search", return_value=[]),
        patch("api.legal.chat_completion", return_value="Objection draft text."),
    ):
        approve_response = await client.post(f"/plans/{plan_id}/approve", headers=headers)

    assert approve_response.status_code == 200
    approved_body = approve_response.json()
    assert approved_body["status"] == "completed"
    assert approved_body["steps"][0]["result_data"]["draft"] == "Objection draft text."

    get_response = await client.get(f"/plans/{plan_id}", headers=headers)
    assert get_response.json()["status"] == "completed"


async def test_plans_list_endpoint_scoped_to_current_user(client):
    token, _ = await _login(client, "plan-http-list-user")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        "/plans", headers=headers, json={"goal_type": "organize_document_collection", "goal_params": {"document_ids": [str(uuid_module.uuid4())]}}
    )

    listing = await client.get("/plans", headers=headers)
    assert listing.status_code == 200
    assert len(listing.json()) >= 1


async def test_create_plan_endpoint_rejects_missing_token(client):
    response = await client.post("/plans", json={"goal_type": "generate_timeline", "goal_params": {}})
    assert response.status_code == 401
