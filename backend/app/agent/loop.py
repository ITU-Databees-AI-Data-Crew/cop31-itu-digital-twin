"""The agent loop, streaming.

One turn = model call -> run the tools it asked for -> model call -> ... until it answers.
Everything is streamed as events while it happens:

  {"type": "text", "delta": "..."}                      answer text, token by token
  {"type": "tool", "name": "...", "args": {...}}        a data tool is about to run ("checking ...")
  {"type": "ui_action", "action": {"type", "args"}}     do this on screen now
  {"type": "done", "reply": "...", "ui_actions": [...]} the turn is over
  {"type": "error", "detail": "..."}                    something broke; the turn is over

Speed rule: screen actions (UI_ACTIONS) don't need the model to see a result. If a model message
contains ONLY valid screen actions and it already wrote answer text, the turn ends there instead of
calling the model again just to hear "Done." (that round trip was ~1/3 of every answer's time).
"""

import json
from collections.abc import Iterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, ToolMessage
from langchain_core.runnables import Runnable
from pydantic import ValidationError

from app.contract import UI_ACTIONS_BY_NAME, UiAction

from .tools import EXECUTABLE_BY_NAME

MAX_MODEL_CALLS = 6


class Turn:
    """One chat turn. Iterate `events()`; afterwards `messages` holds what to save in history
    (every tool call is followed by exactly one ToolMessage, so the next call stays valid)."""

    def __init__(self, llm: BaseChatModel | Runnable, messages: list[BaseMessage]) -> None:
        self.llm = llm
        self.history = messages
        self.messages: list[BaseMessage] = []
        self.actions: list[UiAction] = []
        self.texts: list[str] = []

    @property
    def reply(self) -> str:
        return "\n\n".join(t.strip() for t in self.texts if t.strip())

    def events(self) -> Iterator[dict]:
        try:
            for _ in range(MAX_MODEL_CALLS):
                response = yield from self._call_model()
                self.messages.append(response)
                if not response.tool_calls:
                    break
                ui_only = True
                for call in response.tool_calls:
                    content, ok_ui = yield from self._handle(call)
                    ui_only &= ok_ui
                    self.messages.append(ToolMessage(content=content, tool_call_id=call["id"]))
                if ui_only and response.text.strip():
                    break  # screen actions + answer already given: no need to call the model again
            else:
                yield from self._say("I hit the step limit for this message. Please try asking more simply.")
        except Exception as e:  # network, provider, ... : end the turn cleanly
            yield {"type": "error", "detail": f"{type(e).__name__}: {e}"}
            return
        finally:  # also runs if the client disconnects mid-turn: keep history valid
            self._close_open_calls()
        if not self.reply:
            yield from self._say("Done.")
        yield {"type": "done", "reply": self.reply, "ui_actions": [a.model_dump(mode="json") for a in self.actions]}

    # --- steps ---------------------------------------------------------------

    def _call_model(self):
        """Stream one model call; yield its text as it comes; return the whole message."""
        full: AIMessageChunk | None = None
        text = []
        for chunk in self.llm.stream(self.history + self.messages):
            full = chunk if full is None else full + chunk
            delta = chunk.text
            if delta:
                text.append(delta)
                yield {"type": "text", "delta": delta}
        if text:
            self.texts.append("".join(text))
        if full is None:
            return AIMessage(content="")
        return AIMessage(content=full.content, tool_calls=full.tool_calls, id=full.id,
                         additional_kwargs=full.additional_kwargs, response_metadata=full.response_metadata)

    def _handle(self, call: dict):
        """Run one tool call. Returns (content for the ToolMessage, was it a valid screen action)."""
        name, args = call["name"], call["args"]
        if name in UI_ACTIONS_BY_NAME:
            try:
                parsed = UI_ACTIONS_BY_NAME[name](**args)
            except ValidationError as e:
                return f"Invalid arguments for {name}: {e}", False
            action = UiAction(type=name, args=parsed.model_dump(mode="json"))
            self.actions.append(action)
            yield {"type": "ui_action", "action": action.model_dump(mode="json")}
            return "Done.", True

        tool = EXECUTABLE_BY_NAME.get(name)
        if tool is None:
            return f"Unknown tool: {name}", False
        yield {"type": "tool", "name": name, "args": args}
        try:
            result = tool.invoke(args)
        except Exception as e:
            return f"Tool error: {e}", False
        return (result if isinstance(result, str) else json.dumps(result, ensure_ascii=False, default=str)), False

    def _say(self, text: str):
        self.texts.append(text)
        self.messages.append(AIMessage(content=text))
        yield {"type": "text", "delta": text}

    def _close_open_calls(self) -> None:
        """After a crash mid-turn, answer any tool call that has no ToolMessage yet."""
        answered = {m.tool_call_id for m in self.messages if isinstance(m, ToolMessage)}
        for m in [m for m in self.messages if isinstance(m, AIMessage)]:
            for call in m.tool_calls:
                if call["id"] not in answered:
                    self.messages.append(ToolMessage(content="Cancelled.", tool_call_id=call["id"]))


def run_loop(llm: BaseChatModel | Runnable, messages: list[BaseMessage]) -> tuple[list[BaseMessage], list[UiAction]]:
    """Non-streaming: run a whole turn, return (messages to save, UI actions)."""
    turn = Turn(llm, messages)
    for _ in turn.events():
        pass
    return turn.messages, turn.actions
