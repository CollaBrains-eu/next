from unittest.mock import patch
from uuid import uuid4

from api.db import async_session
from api.manager_agent import _tools_for_role, handle_request
from api.models import Document, User
from api.preferences import set_preferences
from api.search_service import SearchHit


def _unique(base: str) -> str:
    return f"{base}-{uuid4().hex[:8]}"


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


def test_tools_for_role_filters_by_permission():
    member_tools = {entry["function"]["name"] for entry in _tools_for_role("member")}
    service_tools = {entry["function"]["name"] for entry in _tools_for_role("service")}

    assert "search" in member_tools
    assert service_tools == set()


async def test_handle_request_with_no_permitted_tools_falls_back_to_plain_completion():
    user = await _create_user(_unique("manageruser"), role="service")

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion", return_value="a direct answer") as mock_plain,
            patch("api.manager_agent.chat_completion_with_tools") as mock_with_tools,
        ):
            result = await handle_request(db, user_id=user.id, role="service", message="hello")

    assert result == {"answer": "a direct answer", "tool_called": None}
    mock_plain.assert_called_once()
    mock_with_tools.assert_not_called()


async def test_handle_request_returns_direct_answer_when_model_requests_no_tool():
    user = await _create_user(_unique("manageruser"))

    async with async_session() as db:
        with patch("api.manager_agent.chat_completion_with_tools", return_value={"content": "just an answer"}):
            result = await handle_request(db, user_id=user.id, role="member", message="what's the weather")

    assert result == {"answer": "just an answer", "tool_called": None}


async def test_handle_request_dispatches_a_real_tool_end_to_end():
    user = await _create_user(_unique("manageruser"))

    class _FakeChunk:
        def __init__(self):
            self.id = uuid4()
            self.document_id = uuid4()
            self.content = "found this"

    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.7)
    tool_call_response = {
        "content": "",
        "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response),
            patch("api.tools.hybrid_search", return_value=[fake_hit]),
            patch("api.manager_agent.chat_completion", return_value="Here's what I found.") as mock_final,
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="find hello")

    assert result == {"answer": "Here's what I found.", "tool_called": "search"}
    follow_up_messages = mock_final.call_args.args[0]
    assert follow_up_messages[-1]["role"] == "tool"
    assert "found this" in follow_up_messages[-1]["content"]


async def test_handle_request_feeds_a_tool_error_back_to_the_model():
    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "",
        "tool_calls": [{"function": {"name": "summarize_document", "arguments": {"document_id": str(uuid4())}}}],
    }

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response),
            patch("api.manager_agent.chat_completion", return_value="I couldn't find that document.") as mock_final,
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="summarize doc x")

    assert result == {"answer": "I couldn't find that document.", "tool_called": "summarize_document"}
    follow_up_messages = mock_final.call_args.args[0]
    assert "error" in follow_up_messages[-1]["content"]


async def test_handle_request_denies_a_tool_the_role_lacks_permission_for():
    # Simulates the model somehow requesting a tool outside its offered set
    # (a buggy/adversarial response) -- dispatch()'s own permission check
    # (ADR 0023) is the real backstop, not _tools_for_role's filtering alone.
    user = await _create_user(_unique("manageruser"), role="service")
    fake_tools = [{"type": "function", "function": {"name": "search", "description": "d", "parameters": {}}}]
    tool_call_response = {
        "content": "",
        "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }

    async with async_session() as db:
        with (
            patch("api.manager_agent._tools_for_role", return_value=fake_tools),
            patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response),
            patch("api.manager_agent.chat_completion", return_value="Sorry, I can't do that.") as mock_final,
        ):
            result = await handle_request(db, user_id=user.id, role="service", message="find hello")

    assert result["tool_called"] == "search"
    follow_up_messages = mock_final.call_args.args[0]
    assert "error" in follow_up_messages[-1]["content"]


async def test_handle_request_includes_preferred_language_in_system_prompt():
    user = await _create_user(_unique("manageruser"), role="service")
    async with async_session() as db:
        await set_preferences(db, user_id=user.id, preferred_language="nl")

    async with async_session() as db:
        with patch("api.manager_agent.chat_completion", return_value="ok") as mock_completion:
            await handle_request(db, user_id=user.id, role="service", message="hello")

    sent_messages = mock_completion.call_args.args[0]
    system_message = sent_messages[0]["content"]
    assert "you must respond only in nl" in system_message.lower()


async def test_handle_request_omits_language_instruction_when_no_preference_set():
    user = await _create_user(_unique("manageruser"), role="service")

    async with async_session() as db:
        with patch("api.manager_agent.chat_completion", return_value="ok") as mock_completion:
            await handle_request(db, user_id=user.id, role="service", message="hello")

    sent_messages = mock_completion.call_args.args[0]
    system_message = sent_messages[0]["content"]
    assert "respond only in" not in system_message.lower()
