"""The agent loop.

BASELINE: ported from the original assistant.py, plus UI-action recording.
Meant to be replaced by a custom loop. Keep the run_loop signature and anything
else can change.
"""

import json

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from app.contract import UI_ACTIONS_BY_NAME, UiAction

from .tools import EXECUTABLE_BY_NAME

MAX_ITERATIONS = 5


def run_loop(
    llm: BaseChatModel | Runnable, messages: list[BaseMessage]
) -> tuple[list[BaseMessage], list[UiAction]]:
    """Run one turn.

    llm:      the model, already bound to the tools
    messages: system prompt + history + the new user message

    Returns the messages produced this turn (to be saved in history) and the
    UI actions the model asked for. Every tool call gets exactly one ToolMessage
    right after it, otherwise the next model call fails.
    """
    new: list[BaseMessage] = []
    actions: list[UiAction] = []

    for _ in range(MAX_ITERATIONS):
        response = llm.invoke(messages + new)
        new.append(response)
        if not response.tool_calls:
            return new, actions
        for call in response.tool_calls:
            new.append(ToolMessage(content=_handle_call(call, actions), tool_call_id=call["id"]))

    new.append(AIMessage(content="I hit the tool-call limit for this message. Please try asking more simply."))
    return new, actions


def _handle_call(call: dict, actions: list[UiAction]) -> str:
    name, args = call["name"], call["args"]

    if name in UI_ACTIONS_BY_NAME:
        try:
            parsed = UI_ACTIONS_BY_NAME[name](**args)
        except ValidationError as e:
            return f"Invalid arguments for {name}: {e}"
        actions.append(UiAction(type=name, args=parsed.model_dump()))
        return "Done."

    tool = EXECUTABLE_BY_NAME.get(name)
    if tool is None:
        return f"Unknown tool: {name}"
    try:
        result = tool.invoke(args)
    except Exception as e:
        return f"Tool error: {e}"
    return result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)
