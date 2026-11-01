from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.contract import AgentReply, UiState

from .llm import make_llm
from .loop import run_loop
from .prompt import SYSTEM_PROMPT, format_turn
from .sessions import SessionStore
from .tools import ALL_TOOLS


class Agent:
    def __init__(self, llm: BaseChatModel | None = None, sessions: SessionStore | None = None) -> None:
        self.llm = (llm or make_llm()).bind_tools(ALL_TOOLS)
        self.sessions = sessions or SessionStore()

    def run(self, session_id: str, message: str, ui_state: UiState) -> AgentReply:
        """One chat turn: read the session's history, answer, record UI actions, save history."""
        turn = HumanMessage(content=format_turn(message, ui_state))
        messages = [SystemMessage(content=SYSTEM_PROMPT), *self.sessions.get(session_id), turn]

        new, actions = run_loop(self.llm, messages)

        self.sessions.append(session_id, [turn, *new])
        return AgentReply(reply=new[-1].text, ui_actions=actions)
