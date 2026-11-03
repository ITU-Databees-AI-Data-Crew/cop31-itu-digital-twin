"""Every tool the model can call.

Two kinds:
- executable tools (data, what-if, web): the loop runs them and gives the result back to the model
- UI actions (from app.contract): the loop doesn't run them, it records them for the frontend
"""

from app.contract import UI_ACTIONS

from .data import DATA_TOOLS
from .web import web_search
from .whatif import WHATIF_TOOLS

EXECUTABLE_TOOLS = [*DATA_TOOLS, *WHATIF_TOOLS, web_search]
EXECUTABLE_BY_NAME = {t.name: t for t in EXECUTABLE_TOOLS}

ALL_TOOLS = [*EXECUTABLE_TOOLS, *UI_ACTIONS]
