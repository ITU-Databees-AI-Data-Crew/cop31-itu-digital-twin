"""Checks for screen actions before they reach the screen.

A screen action with a wrong id would do nothing on screen while the model believes it worked
(it once sent SelectBuilding("LIB") and said "I've selected the library"). So every action is
checked against the real data: a fixable one is normalised, an invalid one goes back to the model
as an error so it can correct itself.
"""

import pandas as pd
from pydantic import BaseModel

from app.contract import SelectBuilding, SetTime, ShowScenario
from app.data import campus
from app.data.campus import DataError
from app.sim import scenarios


def check(action: BaseModel) -> str | None:
    """None if the action is fine (it may be normalised in place), else an error for the model."""
    if isinstance(action, SelectBuilding):
        ids = [b["id"] for b in campus.list_buildings()]
        bid = action.building_id.strip().lower()
        if bid not in ids:
            return f"No building with id {action.building_id!r}; nothing was selected. Valid ids: {', '.join(ids)}."
        action.building_id = bid
    elif isinstance(action, ShowScenario):
        try:
            scenarios.get_scenario(action.scenario_id)
        except DataError as e:
            return f"{e} Nothing was shown."
    elif isinstance(action, SetTime):
        r = campus.time_range()
        t = pd.Timestamp(action.time)
        if not pd.Timestamp(r["start"]) <= t <= pd.Timestamp(r["end"]):
            return f"{t:%Y-%m-%d %H:%M} is outside the data year ({r['start']} to {r['end']}); the clock didn't move."
    return None
