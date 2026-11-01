"""Shared shapes between the frontend, the Backend API and the Agent.

Changing anything here changes an agreement other people build against,
so say it in the team chat first.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

System = Literal["energy", "emissions", "water", "waste", "occupancy"]


class UiState(BaseModel):
    """What the screen shows right now. Sent with every chat message."""

    selected_building: str | None = None
    system: System | None = None
    scenario_id: str | None = None
    sim_time: datetime


# --- UI actions --------------------------------------------------------------
# Each class is BOTH a tool the model can call AND an action the frontend runs.
# The agent loop doesn't execute them: it records them and answers the model "done".
# Class docstrings and field descriptions are what the model reads.


class SelectBuilding(BaseModel):
    """Select a building on the 3D campus. The building panel then shows it."""

    building_id: str = Field(description="Building id from the building list.")


class OpenSystem(BaseModel):
    """Open a system tab in the building panel."""

    system: System


class ColorCampus(BaseModel):
    """Colour all buildings on the 3D campus by a system's current value. Pass null to clear."""

    system: System | None


class ShowScenario(BaseModel):
    """Show a scenario's before/after comparison in the building panel."""

    scenario_id: str


UI_ACTIONS: list[type[BaseModel]] = [SelectBuilding, OpenSystem, ColorCampus, ShowScenario]
UI_ACTIONS_BY_NAME: dict[str, type[BaseModel]] = {m.__name__: m for m in UI_ACTIONS}


class UiAction(BaseModel):
    """One action for the frontend to carry out, e.g. {"type": "SelectBuilding", "args": {"building_id": "b07"}}."""

    type: str
    args: dict[str, Any]


# --- Chat in / out -----------------------------------------------------------


class ChatRequest(BaseModel):
    session_id: str
    message: str
    ui_state: UiState


class AgentReply(BaseModel):
    reply: str
    ui_actions: list[UiAction] = []
