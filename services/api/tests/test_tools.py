from unittest.mock import patch
from uuid import uuid4

import pytest

from api.db import async_session
from api.legal import DraftResponse
from api.models import Document, Entity, Task, User
from api.search_service import SearchHit
from api.tool_registry import ToolPermissionError, dispatch


async def _create_user(username: str, *, role: str = "member") -> User:
    async with async_session() as db:
        user = User(username=username, display_name=username, role=role)
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user


async def _create_document(owner_id, *, status: str = "ready", ocr_text: str | None = "some text") -> Document:
    async with async_session() as db:
        document = Document(
            owner_id=owner_id, title="t", filename="t.pdf", mime_type="application/pdf",
            status=status, ocr_text=ocr_text,
        )
        db.add(document)
        await db.commit()
        await db.refresh(document)
        return document


class _FakeChunk:
    def __init__(self):
        self.id = uuid4()
        self.document_id = uuid4()
        self.content = "hello"


async def test_search_tool_returns_documents():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.9)

    async with async_session() as db:
        with patch("api.tools.hybrid_search", return_value=[fake_hit]):
            result = await dispatch("search", db=db, user_id=user.id, query="hello")

    assert result["documents"][0]["content"] == "hello"
    assert result["documents"][0]["score"] == 0.9


async def test_summarize_document_tool_returns_summary():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id)

    async with async_session() as db:
        with patch("api.tools._generate_summary", return_value="a summary"):
            result = await dispatch("summarize_document", db=db, user_id=user.id, document_id=document.id)

    assert result == {"summary": "a summary"}


async def test_summarize_document_tool_rejects_not_ready_document():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id, status="pending", ocr_text=None)

    async with async_session() as db:
        with pytest.raises(ValueError):
            await dispatch("summarize_document", db=db, user_id=user.id, document_id=document.id)


async def test_summarize_document_tool_rejects_missing_document():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")

    async with async_session() as db:
        with pytest.raises(ValueError):
            await dispatch("summarize_document", db=db, user_id=user.id, document_id=uuid4())


async def test_draft_legal_document_tool_returns_draft_dict():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_draft = DraftResponse(draft="a draft", citations=[])

    async with async_session() as db:
        with patch("api.tools._generate_draft", return_value=fake_draft):
            result = await dispatch("draft_legal_document", db=db, user_id=user.id, instruction="draft something")

    assert result["draft"] == "a draft"
    assert "disclaimer" in result


async def test_extract_tasks_tool_returns_tasks():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id)
    fake_task = Task(id=uuid4(), title="Do the thing", document_id=document.id)

    async with async_session() as db:
        with patch("api.tools.extract_tasks", return_value=[fake_task]):
            result = await dispatch(
                "extract_tasks", db=db, user_id=user.id, document_id=document.id, text="do the thing by friday",
            )

    assert result["tasks"][0]["title"] == "Do the thing"


async def test_extract_entities_tool_returns_entities():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    document = await _create_document(user.id)
    fake_entity = Entity(id=uuid4(), name="Jane Doe", entity_type="person")

    async with async_session() as db:
        with patch("api.tools.extract_entities", return_value=[fake_entity]):
            result = await dispatch(
                "extract_entities", db=db, user_id=user.id, document_id=document.id,
                text="Jane Doe signed the contract",
            )

    assert result["entities"][0]["name"] == "Jane Doe"


async def test_search_tool_denies_a_role_with_no_permissions():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}", role="service")

    async with async_session() as db:
        with pytest.raises(ToolPermissionError):
            await dispatch("search", db=db, user_id=user.id, query="hello")


async def test_lookup_vehicle_tool_returns_rdw_fields():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_data = {
        "voertuigsoort": "Personenauto", "merk": "TOYOTA", "handelsbenaming": "AYGO",
        "eerste_kleur": "GRIJS", "datum_eerste_toelating": "20180501",
        "vervaldatum_apk": "20270501", "wam_verzekerd": "Ja",
        "openstaande_terugroepactie_indicator": "Nee", "brandstofomschrijving": "Benzine",
        "massa_ledig_voertuig": "840", "aantal_cilinders": "3", "wielbasis": "2340",
        "catalogusprijs": "12500", "aantal_zitplaatsen": "4", "aantal_deuren": "5",
        "vermogen_massarijklaar": "51", "europese_voertuigcategorie": "M1",
    }

    async with async_session() as db:
        with patch("api.vehicle_agent.fetch_vehicle_data", return_value=fake_data):
            result = await dispatch("lookup_vehicle", db=db, user_id=user.id, kenteken="TO-OL-01")

    assert result["kenteken"] == "TOOL01"
    assert result["merk"] == "TOYOTA"
    assert result["found"] is True


async def test_lookup_vehicle_tool_reports_not_found():
    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")

    async with async_session() as db:
        with patch("api.vehicle_agent.fetch_vehicle_data", return_value=None):
            result = await dispatch("lookup_vehicle", db=db, user_id=user.id, kenteken="ZZ-99-ZZ")

    assert result["found"] is False


async def test_lookup_vehicle_tool_reports_rdw_outage_gracefully_without_raising():
    from api.rdw_client import RdwLookupError

    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")

    async with async_session() as db:
        with patch("api.vehicle_agent.fetch_vehicle_data", side_effect=RdwLookupError("boom")):
            result = await dispatch("lookup_vehicle", db=db, user_id=user.id, kenteken="ZZ-98-ZZ")

    assert result["found"] is False
    assert "error" in result


async def test_answer_from_documents_tool_returns_grounded_answer():
    from api.chat import Citation, GroundedAnswer

    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_answer = GroundedAnswer(
        answer="the answer",
        citations=[Citation(marker=1, document_id=uuid4(), document_title="t", chunk_id=uuid4())],
    )

    async with async_session() as db:
        with patch("api.tools.answer_grounded_question", return_value=fake_answer):
            result = await dispatch("answer_from_documents", db=db, user_id=user.id, message="what is x")

    assert result["answer"] == "the answer"
    assert result["citations"][0]["document_title"] == "t"


async def test_answer_from_documents_tool_passes_history_through():
    from api.chat import GroundedAnswer

    user = await _create_user(f"tooluser-{uuid4().hex[:8]}")
    fake_answer = GroundedAnswer(answer="ok", citations=[])

    async with async_session() as db:
        with patch("api.tools.answer_grounded_question", return_value=fake_answer) as mock_answer:
            await dispatch(
                "answer_from_documents", db=db, user_id=user.id, message="follow-up",
                history=[{"role": "user", "content": "earlier question"}],
            )

    assert mock_answer.call_args.kwargs["history"] == [{"role": "user", "content": "earlier question"}]
