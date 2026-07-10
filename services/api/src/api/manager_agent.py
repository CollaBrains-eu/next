"""Manager Agent: model-driven tool selection for free-form requests
(Phase 11, ADR 0026).

The model is the Manager -- there is no separate agent-selection
abstraction. Offers the calling user's permitted tools (9a/9c) to the
model via Ollama's native function-calling (9d); if it requests one,
dispatches it (9a, respecting 9c's enforcement unchanged) and feeds the
result back. The model may chain up to MAX_TOOL_ROUNDS tool calls
before producing a final answer, enabling compound requests.
"""
import json
import logging
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from api.ai_gateway import chat_completion, chat_completion_with_tools
from api.chat import Citation
from api.legal import DraftResponse
from api.permissions import has_permission
from api.preferences import build_language_instruction, get_preferences
from api.tool_registry import ToolPermissionError, dispatch, list_tools, to_ollama_tools

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the CollaBrains assistant. If one of the available tools can help "
    "answer the user's request, call it. Otherwise answer directly. Never "
    "invent information a tool call could have provided."
)


def _tools_for_role(role: str) -> list[dict[str, Any]]:
    """Only offer the model tools this role is actually permitted to call.

    9d's to_ollama_tools() lists every registered tool regardless of role
    (ADR 0024); this is the caller ADR 0024 said should filter by
    has_permission() before offering them to a model.
    """
    permitted_names = {tool.name for tool in list_tools() if has_permission(role, tool.permissions)}
    return [entry for entry in to_ollama_tools() if entry["function"]["name"] in permitted_names]


MAX_TOOL_ROUNDS = 5

TERMINAL_TOOLS = {"answer_from_documents", "draft_legal_document"}


async def handle_request(db: AsyncSession, *, user_id: UUID, role: str, message: str) -> dict[str, Any]:
    """Answer a free-form request, autonomously chaining up to MAX_TOOL_ROUNDS tool calls."""
    language_instruction = ""
    try:
        preferences = await get_preferences(db, user_id=user_id)
        language_instruction = build_language_instruction(preferences.preferred_language if preferences else None)
    except Exception:  # noqa: BLE001 - preference lookup must never fail the manager agent response
        logger.exception("preference lookup failed for manager agent request")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT + language_instruction},
        {"role": "user", "content": message},
    ]

    tools = _tools_for_role(role)
    if not tools:
        answer = await chat_completion(messages, user_id=user_id, endpoint="manager_agent")
        return {"answer": answer, "tools_called": [], "citations": None, "legal_draft": None}

    tools_called: list[str] = []
    for _round in range(MAX_TOOL_ROUNDS):
        response_message = await chat_completion_with_tools(
            messages, user_id=user_id, endpoint="manager_agent", tools=tools,
        )
        tool_calls = response_message.get("tool_calls")
        if not tool_calls:
            return {
                "answer": response_message.get("content", ""), "tools_called": tools_called,
                "citations": None, "legal_draft": None,
            }

        call = tool_calls[0]
        function = call.get("function", {})
        tool_name = function.get("name")
        arguments = function.get("arguments") or {}

        try:
            result = await dispatch(tool_name, db=db, user_id=user_id, **arguments)
        except (KeyError, ValueError, ToolPermissionError) as exc:
            logger.info("manager agent tool call %r failed: %s", tool_name, exc)
            tools_called.append(tool_name)
            messages = [
                *messages,
                {"role": "assistant", "content": "", "tool_calls": tool_calls},
                {"role": "tool", "content": json.dumps({"error": str(exc)})},
            ]
            continue

        tools_called.append(tool_name)

        if tool_name in TERMINAL_TOOLS:
            if tool_name == "answer_from_documents":
                return {
                    "answer": result["answer"],
                    "tools_called": tools_called,
                    "citations": [Citation(**c) for c in result["citations"]],
                    "legal_draft": None,
                }
            return {  # tool_name == "draft_legal_document"
                "answer": result["draft"],
                "tools_called": tools_called,
                "citations": None,
                "legal_draft": DraftResponse(**result),
            }

        messages = [
            *messages,
            {"role": "assistant", "content": "", "tool_calls": tool_calls},
            {"role": "tool", "content": json.dumps(result)},
        ]

    answer = await chat_completion(messages, user_id=user_id, endpoint="manager_agent")
    return {"answer": answer, "tools_called": tools_called, "citations": None, "legal_draft": None}
