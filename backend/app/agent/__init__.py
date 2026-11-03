from collections.abc import Iterator

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.contract import AgentReply, UiAction, UiState

from .llm import make_llm
from .loop import Turn
from .prompt import SYSTEM_PROMPT, format_turn
from .sessions import SessionStore
from .tools import ALL_TOOLS


class Agent:
    def __init__(self, llm: BaseChatModel | None = None, sessions: SessionStore | None = None) -> None:
        self.llm = (llm or make_llm()).bind_tools(ALL_TOOLS)
        self.sessions = sessions or SessionStore()

    def stream(self, session_id: str, message: str, ui_state: UiState) -> Iterator[dict]:
        """One chat turn as events (see loop.py). History is saved when the turn ends, even on error."""
        user = HumanMessage(content=format_turn(message, ui_state))
        turn = Turn(self.llm, [SystemMessage(content=SYSTEM_PROMPT), *self.sessions.get(session_id), user])
        try:
            yield from turn.events()
        finally:
            self.sessions.append(session_id, [user, *turn.messages])

    def run(self, session_id: str, message: str, ui_state: UiState) -> AgentReply:
        """One chat turn, all at once."""
        reply, actions = "", []
        for event in self.stream(session_id, message, ui_state):
            if event["type"] == "done":
                reply, actions = event["reply"], [UiAction(**a) for a in event["ui_actions"]]
            elif event["type"] == "error":
                reply = f"Sorry, something went wrong: {event['detail']}"
        return AgentReply(reply=reply, ui_actions=actions)
