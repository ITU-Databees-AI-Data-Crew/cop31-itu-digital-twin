"""The Simulation engine's questions: the Data API's questions with the clock and what-ifs applied.

Every question works on the current campus (baseline + applied what-ifs). Pass scenario_id to
preview a draft on top of it.
"""

import pandas as pd

from app.data import campus
from app.data.campus import DataError
from app.sim import scenarios, whatif
from app.sim.clock import CLOCK

COMPARE_SYSTEMS = ["energy", "emissions", "water", "waste"]


def _world(scenario_id: str | None = None, exclude: str | None = None) -> list:
    """Interventions in force: every applied what-if (minus `exclude`), plus the draft `scenario_id` if given."""
    ivs = [iv for s in scenarios.list_scenarios("applied") if s.id != exclude for iv in s.interventions]
    if scenario_id:
        s = scenarios.get_scenario(scenario_id)
        if s.status == "draft" or s.id == exclude:
            ivs += s.interventions
    return ivs


def _adjust(scenario_id: str | None = None):
    return whatif.adjuster(_world(scenario_id))


def clock() -> dict:
    return CLOCK.state()


def now(building_id: str, system: str, scenario_id: str | None = None) -> dict:
    """A building's values for one system at the clock's current hour."""
    return campus.get_values_at(building_id, system, CLOCK.now(), adjust=_adjust(scenario_id))


def campus_now(system: str, scenario_id: str | None = None) -> list[dict]:
    """Every building's values for one system at the current hour (e.g. to colour the 3D campus)."""
    return [now(b["id"], system, scenario_id) for b in campus.list_buildings()]


def series(building_id: str, metric: str, start, end, resolution: str = "hour", scenario_id: str | None = None) -> dict:
    return campus.get_series(building_id, metric, start, end, resolution, adjust=_adjust(scenario_id))


def totals(building_id: str | None, system: str, start, end, scenario_id: str | None = None) -> dict:
    return campus.get_totals(building_id, system, start, end, adjust=_adjust(scenario_id))


def rank(metric: str, start, end, per: str = "total", scenario_id: str | None = None) -> list[dict]:
    return campus.rank_buildings(metric, start, end, per, adjust=_adjust(scenario_id))


def compare(scenario_id: str, building_id: str | None = None, start=None, end=None) -> dict:
    """Before vs after for one what-if, per metric. Before = current campus without this what-if.

    Default building: the one the what-if touches (or the whole campus if it touches several).
    Default period: the whole data year.
    """
    s = scenarios.get_scenario(scenario_id)
    if building_id is None:
        touched = {iv.building_id for iv in s.interventions}
        building_id = touched.pop() if len(touched) == 1 else None
    if start is None or end is None:
        r = campus.time_range()
        start = start or r["start"]
        end = end or (pd.Timestamp(r["end"]) + pd.Timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    before_adj = whatif.adjuster(_world(exclude=s.id))
    after_adj = whatif.adjuster(_world(s.id, exclude=s.id))

    result = {}
    for system in COMPARE_SYSTEMS:
        before = campus.get_totals(building_id, system, start, end, adjust=before_adj)
        after = campus.get_totals(building_id, system, start, end, adjust=after_adj)
        rows = {}
        for metric, b in before["totals"].items():
            a = after["totals"][metric]
            if b is None or a is None:
                continue
            change = a - b
            rows[metric] = {
                "before": b, "after": a, "change": round(change, 4 if abs(change) < 1 else 2),
                "change_pct": round(change / b * 100, 1) if b else None, "unit": before["units"][metric],
            }
        result[system] = rows
    return {
        "scenario": s.model_dump(mode="json"),
        "building_id": building_id or "campus",
        "start": before["start"], "end": before["end"],
        "systems": result,
    }
