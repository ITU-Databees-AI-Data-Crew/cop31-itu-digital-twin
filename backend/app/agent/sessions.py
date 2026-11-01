from langchain_core.messages import BaseMessage


class SessionStore:
    """Chat history per session, kept in memory.

    Lost when the server restarts, which is fine for a laptop demo.
    """

    def __init__(self) -> None:
        self._histories: dict[str, list[BaseMessage]] = {}

    def get(self, session_id: str) -> list[BaseMessage]:
        return list(self._histories.get(session_id, []))

    def append(self, session_id: str, messages: list[BaseMessage]) -> None:
        self._histories.setdefault(session_id, []).extend(messages)

    def reset(self, session_id: str) -> None:
        self._histories.pop(session_id, None)
