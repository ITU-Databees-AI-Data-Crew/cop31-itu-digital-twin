"""Campus data tools.

Everything goes through the Simulation engine, so the agent sees the current campus
(baseline + applied what-ifs) and "now" is the app clock. Pass scenario_id to preview a draft.
Errors (bad id, bad time, ...) come back as a message that says what's valid.
"""

from typing import Literal

from langchain_core.tools import tool

from app.contract import System
from app.data import campus
from app.data.campus import DataError
from app.sim import engine

MAX_POINTS = 400  # keep tool results small; ask for a coarser resolution instead

Resolution = Literal["hour", "day", "month"]


def _cap(points: list, what: str) -> None:
    if len(points) > MAX_POINTS:
        raise DataError(f"{len(points)} {what} is too many. Use a shorter period or a coarser resolution (day or month).")


@tool
def get_clock() -> dict:
    """The app's current time ("now" on screen), whether it's playing, and the data year's range."""
    c = engine.clock()
    return {"now": c["sim_time"], "playing": c["playing"], "data_range": c["range"]}


@tool
def list_buildings() -> list[dict]:
    """The modelled buildings: id, name, floors, footprint and floor area (m²), capacity (people)."""
    return campus.list_buildings()


@tool
def list_metrics() -> list[dict]:
    """Every metric: name, system, unit, hourly or daily, and what it means."""
    keep = ("metric", "system", "unit", "resolution", "description")
    return [{k: m[k] for k in keep} for m in campus.list_metrics()]


@tool
def get_now(building_id: str, system: System, scenario_id: str | None = None) -> dict:
    """One building's values for one system at the app's current time (the clock on screen).

    Args:
        building_id: from list_buildings.
        system: energy, emissions, water, waste or occupancy.
        scenario_id: optional draft what-if to preview on top.
    """
    return engine.now(building_id, system, scenario_id)


@tool
def get_totals(building_id: str, system: System, start: str, end: str, scenario_id: str | None = None) -> dict:
    """Totals of one system over a period [start, end). Occupancy gives mean, peak and person-hours.

    Args:
        building_id: from list_buildings, or "campus" for all buildings together.
        system: energy, emissions, water, waste or occupancy.
        start: first moment included, local Istanbul time, e.g. '2026-01-05' or '2026-01-05T14:00'.
        end: first moment NOT included.
        scenario_id: optional draft what-if to preview on top.
    """
    return engine.totals(None if building_id == "campus" else building_id, system, start, end, scenario_id)


@tool
def get_series(building_id: str, metric: str, start: str, end: str, resolution: Resolution = "day",
               scenario_id: str | None = None) -> dict:
    """A time series of one metric for one building over [start, end), at most 400 points.

    Args:
        building_id: from list_buildings.
        metric: from list_metrics, e.g. natural_gas_kwh, co2e_kg, people, recycling_rate.
        start: first moment included, local Istanbul time, e.g. '2026-01-05' or '2026-01-05T14:00'.
        end: first moment NOT included.
        resolution: hour, day or month. People are averaged per period; everything else is summed.
        scenario_id: optional draft what-if to preview on top.
    """
    out = engine.series(building_id, metric, start, end, resolution, scenario_id)
    _cap(out["points"], "points")
    return out


@tool
def rank_buildings(metric: str, start: str, end: str, per: Literal["total", "m2", "person_hour"] = "total",
                   scenario_id: str | None = None) -> list[dict]:
    """Buildings ranked by a metric over [start, end), highest first.

    Args:
        metric: from list_metrics.
        start: first moment included, local Istanbul time, e.g. '2026-01-05' or '2026-01-05T14:00'.
        end: first moment NOT included.
        per: total, m2 (per m² floor area, fair between big and small buildings) or person_hour.
        scenario_id: optional draft what-if to preview on top.
    """
    return engine.rank(metric, start, end, per, scenario_id)


@tool
def get_weather(start: str, end: str, resolution: Resolution = "day") -> dict:
    """Real Istanbul weather over [start, end): temperature, humidity, rain, cloud, wind, sunshine.
    Useful to explain heating (cold), cooling (heat) or solar output (sunshine).

    Args:
        start: first moment included, local Istanbul time, e.g. '2026-01-05' or '2026-01-05T14:00'.
        end: first moment NOT included.
        resolution: hour, day or month (averages; rain is summed).
    """
    out = campus.get_weather(start, end, resolution)
    _cap(out["points"], "points")
    return out


DATA_TOOLS = [get_clock, list_buildings, list_metrics, get_now, get_totals, get_series, rank_buildings, get_weather]
