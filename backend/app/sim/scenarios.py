"""What-if storage: data/state/scenarios.db, separate from the generated data so regenerating
never wipes them.

A scenario is a named list of interventions with a status:
  draft   -> created by a person or the agent; shown only when asked for
  applied -> a person pressed Apply; now part of the current campus everywhere
Discard deletes it (draft or applied). The agent can only create drafts.
"""

import json
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from app.data.campus import DataError

REPO = Path(__file__).resolve().parents[3]
DB_PATH = REPO / "data" / "state" / "scenarios.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS scenarios (
    id            TEXT PRIMARY KEY,
    name          TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('draft', 'applied')),
    source        TEXT NOT NULL CHECK (source IN ('user', 'agent')),
    preset        TEXT,
    note          TEXT,
    created       TEXT NOT NULL,
    applied_at    TEXT,
    interventions TEXT NOT NULL
);
"""


# --- interventions -----------------------------------------------------------


class Scale(BaseModel):
    """Multiply one stored metric of one building, e.g. lighting −50% after an LED retrofit."""

    type: Literal["scale"] = "scale"
    building_id: str
    metric: str = Field(description="A stored metric, e.g. electricity_lighting_kwh, natural_gas_kwh, water_m3.")
    change_pct: float = Field(ge=-100, le=200, description="Percent change, e.g. -50 for half.")
    start: date | None = Field(default=None, description="From this day on. Empty = the whole year.")


class Shift(BaseModel):
    """Move a share of one waste stream into another, e.g. sorting residual waste into organic."""

    type: Literal["shift"] = "shift"
    building_id: str
    from_metric: str
    to_metric: str
    share: float = Field(gt=0, le=1, description="Share of from_metric that moves, 0-1.")
    start: date | None = None


class SolarPV(BaseModel):
    """Rooftop solar panels. Output follows the real hourly sunshine."""

    type: Literal["solar_pv"] = "solar_pv"
    building_id: str
    kwp: float = Field(gt=0, description="Panel size in kWp (peak kilowatts).")
    start: date | None = None


Intervention = Annotated[Scale | Shift | SolarPV, Field(discriminator="type")]
_interventions = TypeAdapter(list[Intervention])


class Scenario(BaseModel):
    id: str
    name: str
    status: Literal["draft", "applied"]
    source: Literal["user", "agent"]
    preset: str | None = None
    note: str | None = None
    created: str
    applied_at: str | None = None
    interventions: list[Intervention]


# --- storage -----------------------------------------------------------------


def _connect() -> sqlite3.Connection:
    path = DB_PATH  # read at call time, so tests can point it somewhere else
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _row(r: sqlite3.Row) -> Scenario:
    d = dict(r)
    d["interventions"] = json.loads(d["interventions"])
    return Scenario.model_validate(d)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def create_draft(name: str, interventions: list, source: str = "user", preset: str | None = None, note: str | None = None) -> Scenario:
    """Save a new draft. `interventions` can be models or plain dicts. Validated against the campus first."""
    from app.sim import whatif  # late import: whatif needs the Data API, scenarios must not need whatif at import

    ivs = _interventions.validate_python(interventions)
    if not ivs:
        raise DataError("A what-if needs at least one intervention.")
    whatif.validate(ivs)
    s = Scenario(id=uuid.uuid4().hex[:8], name=name, status="draft", source=source, preset=preset, note=note,
                 created=_now(), interventions=ivs)
    with _connect() as con:
        con.execute(
            "INSERT INTO scenarios VALUES (?,?,?,?,?,?,?,?,?)",
            (s.id, s.name, s.status, s.source, s.preset, s.note, s.created, s.applied_at,
             json.dumps(_interventions.dump_python(s.interventions, mode="json"))),
        )
    return s


def list_scenarios(status: str | None = None) -> list[Scenario]:
    if status not in (None, "draft", "applied"):
        raise DataError(f"Unknown status {status!r}. Valid: draft, applied")
    with _connect() as con:
        q = "SELECT * FROM scenarios" + (" WHERE status = ?" if status else "") + " ORDER BY created"
        return [_row(r) for r in con.execute(q, (status,) if status else ())]


def get_scenario(scenario_id: str) -> Scenario:
    with _connect() as con:
        r = con.execute("SELECT * FROM scenarios WHERE id = ?", (scenario_id,)).fetchone()
    if r is None:
        ids = [s.id for s in list_scenarios()]
        raise DataError(f"No what-if with id {scenario_id!r}. Existing: {', '.join(ids) or 'none'}")
    return _row(r)


def apply_scenario(scenario_id: str) -> Scenario:
    """A person pressed Apply: the draft becomes part of the current campus. (Not available to the agent.)"""
    s = get_scenario(scenario_id)
    if s.status == "applied":
        return s
    with _connect() as con:
        con.execute("UPDATE scenarios SET status = 'applied', applied_at = ? WHERE id = ?", (_now(), scenario_id))
    return get_scenario(scenario_id)


def discard_scenario(scenario_id: str) -> None:
    """A person pressed Discard (or Remove on an applied one). (Not available to the agent.)"""
    get_scenario(scenario_id)
    with _connect() as con:
        con.execute("DELETE FROM scenarios WHERE id = ?", (scenario_id,))
