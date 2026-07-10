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

    assert result["answer"] == "a direct answer"
    assert result["tools_called"] == []
    mock_plain.assert_called_once()
    mock_with_tools.assert_not_called()


async def test_handle_request_returns_direct_answer_when_model_requests_no_tool():
    user = await _create_user(_unique("manageruser"))

    async with async_session() as db:
        with patch("api.manager_agent.chat_completion_with_tools", return_value={"content": "just an answer"}):
            result = await handle_request(db, user_id=user.id, role="member", message="what's the weather")

    assert result["answer"] == "just an answer"
    assert result["tools_called"] == []


async def test_handle_request_dispatches_a_real_tool_end_to_end():
    user = await _create_user(_unique("manageruser"))

    class _FakeChunk:
        def __init__(self):
            self.id = uuid4()
            self.document_id = uuid4()
            self.content = "found this"

    fake_hit = SearchHit(chunk=_FakeChunk(), score=0.7)
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }
    final_response = {"content": "Here's what I found."}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[tool_call_response, final_response],
            ) as mock_with_tools,
            patch("api.tools.hybrid_search", return_value=[fake_hit]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="find hello")

    assert result["answer"] == "Here's what I found."
    assert result["tools_called"] == ["search"]
    second_round_messages = mock_with_tools.call_args_list[1].args[0]
    assert second_round_messages[-1]["role"] == "tool"
    assert "found this" in second_round_messages[-1]["content"]


async def test_handle_request_feeds_a_tool_error_back_to_the_model():
    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "",
        "tool_calls": [{"function": {"name": "summarize_document", "arguments": {"document_id": str(uuid4())}}}],
    }
    final_response = {"content": "I couldn't find that document."}

    async with async_session() as db:
        with patch(
            "api.manager_agent.chat_completion_with_tools",
            side_effect=[tool_call_response, final_response],
        ) as mock_with_tools:
            result = await handle_request(db, user_id=user.id, role="member", message="summarize doc x")

    assert result["answer"] == "I couldn't find that document."
    assert result["tools_called"] == ["summarize_document"]
    second_round_messages = mock_with_tools.call_args_list[1].args[0]
    assert "error" in second_round_messages[-1]["content"]


async def test_handle_request_denies_a_tool_the_role_lacks_permission_for():
    # Simulates the model somehow requesting a tool outside its offered set
    # (a buggy/adversarial response) -- dispatch()'s own permission check
    # (ADR 0023) is the real backstop, not _tools_for_role's filtering alone.
    user = await _create_user(_unique("manageruser"), role="service")
    fake_tools = [{"type": "function", "function": {"name": "search", "description": "d", "parameters": {}}}]
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }
    final_response = {"content": "Sorry, I can't do that."}

    async with async_session() as db:
        with (
            patch("api.manager_agent._tools_for_role", return_value=fake_tools),
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[tool_call_response, final_response],
            ) as mock_with_tools,
        ):
            result = await handle_request(db, user_id=user.id, role="service", message="find hello")

    assert result["tools_called"] == ["search"]
    second_round_messages = mock_with_tools.call_args_list[1].args[0]
    assert "error" in second_round_messages[-1]["content"]


async def test_handle_request_chains_two_tool_calls():
    user = await _create_user(_unique("manageruser"))
    first_call = {
        "content": "", "tool_calls": [{"function": {"name": "lookup_vehicle", "arguments": {"kenteken": "AB-12-CD"}}}],
    }
    second_call = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "owner"}}}],
    }
    final = {"content": "Here's the combined answer."}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[first_call, second_call, final],
            ),
            patch("api.tools._lookup_vehicle", return_value=None),
            patch("api.tools.hybrid_search", return_value=[]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="look up then search")

    assert result["answer"] == "Here's the combined answer."
    assert result["tools_called"] == ["lookup_vehicle", "search"]


async def test_handle_request_stops_at_max_rounds_without_a_final_answer():
    user = await _create_user(_unique("manageruser"))
    always_calls_search = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "x"}}}],
    }

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=always_calls_search),
            patch("api.tools.hybrid_search", return_value=[]),
            # MAX_TOOL_ROUNDS is exhausted without the model ever returning a
            # tool_calls-less response, so the loop falls through to one plain
            # chat_completion() call (not chat_completion_with_tools) to produce
            # a final answer -- this must be mocked separately or the test would
            # hit real Ollama.
            patch("api.manager_agent.chat_completion", return_value="ran out of steps") as mock_final,
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="loop forever")

    assert result["answer"] == "ran out of steps"
    assert result["tools_called"] == ["search"] * 5
    mock_final.assert_called_once()


async def test_handle_request_recovers_from_a_mid_chain_tool_error():
    user = await _create_user(_unique("manageruser"))
    failing_call = {
        "content": "", "tool_calls": [{"function": {"name": "summarize_document", "arguments": {"document_id": str(uuid4())}}}],
    }
    recovery_call = {"content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "x"}}}]}
    final = {"content": "Found it a different way."}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[failing_call, recovery_call, final],
            ),
            patch("api.tools.hybrid_search", return_value=[]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="try then recover")

    assert result["answer"] == "Found it a different way."
    assert result["tools_called"] == ["summarize_document", "search"]


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


async def test_handle_request_treats_answer_from_documents_as_terminal():
    from api.chat import Citation, GroundedAnswer

    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "answer_from_documents", "arguments": {"message": "what is x"}}}],
    }
    fake_answer = GroundedAnswer(
        answer="grounded answer", citations=[Citation(marker=1, document_id=uuid4(), document_title="t", chunk_id=uuid4())],
    )

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response) as mock_with_tools,
            patch("api.tools.answer_grounded_question", return_value=fake_answer),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="what is x")

    assert result["answer"] == "grounded answer"
    assert result["tools_called"] == ["answer_from_documents"]
    assert result["citations"][0].document_title == "t"
    assert result.get("legal_draft") is None
    mock_with_tools.assert_called_once()  # no second round-trip to re-synthesize


async def test_handle_request_treats_draft_legal_document_as_terminal():
    from api.legal import DraftResponse

    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "draft_legal_document", "arguments": {"instruction": "draft a letter"}}}],
    }
    fake_draft = DraftResponse(draft="Dear Sir or Madam...", citations=[])

    async with async_session() as db:
        with (
            patch("api.manager_agent.chat_completion_with_tools", return_value=tool_call_response) as mock_with_tools,
            patch("api.tools._generate_draft", return_value=fake_draft),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="draft a letter")

    assert result["answer"] == "Dear Sir or Madam..."
    assert result["tools_called"] == ["draft_legal_document"]
    assert result["legal_draft"].disclaimer
    mock_with_tools.assert_called_once()


async def test_handle_request_non_terminal_tool_still_gets_a_synthesis_round():
    user = await _create_user(_unique("manageruser"))
    tool_call_response = {
        "content": "", "tool_calls": [{"function": {"name": "search", "arguments": {"query": "hello"}}}],
    }
    final_response = {"content": "synthesized"}

    async with async_session() as db:
        with (
            patch(
                "api.manager_agent.chat_completion_with_tools",
                side_effect=[tool_call_response, final_response],
            ) as mock_with_tools,
            patch("api.tools.hybrid_search", return_value=[]),
        ):
            result = await handle_request(db, user_id=user.id, role="member", message="find hello")

    assert result["answer"] == "synthesized"
    assert result.get("citations") is None
    assert result.get("legal_draft") is None
    # search is non-terminal: the loop needs a second chat_completion_with_tools
    # call (which happens to return no tool_calls this time) to produce a final
    # answer, unlike the terminal-tool tests above which return after one call.
    assert mock_with_tools.call_count == 2
