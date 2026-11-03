"""What-if tools. The agent can build any what-if from three kinds of change, but only as a DRAFT:
applying or discarding is a button for the person, never a tool.
"""

from typing import Literal

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from app.data.campus import DataError
from app.sim import engine, presets, scenarios


class Change(BaseModel):
    """One change in a what-if. Fill in only the fields its type needs."""

    type: Literal["scale", "shift", "solar_pv"] = Field(
        description="scale: change a metric by a percent. shift: move part of one waste stream into another. "
        "solar_pv: add rooftop solar panels."
    )
    building_id: str
    metric: str | None = Field(None, description="scale only. A stored metric: electricity_lighting_kwh, "
                               "electricity_plug_kwh, electricity_hvac_kwh, natural_gas_kwh, water_m3, or a waste stream.")
    change_pct: float | None = Field(None, description="scale only. Percent change, e.g. -30 for 30% less.")
    from_metric: str | None = Field(None, description="shift only. Waste stream to take from, e.g. residual_kg.")
    to_metric: str | None = Field(None, description="shift only. Waste stream to move into: recyclable_kg, organic_kg, ...")
    share: float | None = Field(None, description="shift only. Share of from_metric that moves, 0-1.")
    kwp: float | None = Field(None, description="solar_pv only. Panel size in kWp; list_presets gives each roof's limit.")
    start: str | None = Field(None, description="Optional first day, YYYY-MM-DD. Leave empty for the whole year.")


NEEDS = {"scale": ("metric", "change_pct"), "shift": ("from_metric", "to_metric", "share"), "solar_pv": ("kwp",)}


def _intervention(c: Change | dict) -> dict:
    c = Change.model_validate(c) if isinstance(c, dict) else c
    missing = [f for f in NEEDS[c.type] if getattr(c, f) is None]
    if missing:
        raise DataError(f"A {c.type} change needs {', '.join(missing)}.")
    return {"type": c.type, "building_id": c.building_id, "start": c.start, **{f: getattr(c, f) for f in NEEDS[c.type]}}


def _brief(cmp: dict) -> dict:
    """Only what changed, to keep the result small."""
    changed = {
        system: {m: v for m, v in rows.items() if v["change"]}
        for system, rows in cmp["systems"].items()
    }
    return {"building_id": cmp["building_id"], "period": [cmp["start"], cmp["end"]],
            "changes": {s: rows for s, rows in changed.items() if rows}}


@tool
def list_presets(building_id: str) -> list[dict]:
    """Typical what-ifs for a building, with typical amounts and the exact changes they'd make.
    A starting point: copy or adjust the changes into create_whatif. Rooftop solar's amount is the roof's kWp limit.

    Args:
        building_id: from list_buildings.
    """
    out = []
    for p in presets.list_presets(building_id):
        make = presets.PRESETS[p["preset"]]["make"]
        changes = [iv.model_dump(mode="json") for iv in make(building_id, float(p["default_amount"]), None)]
        out.append({**p, "changes": changes})
    return out


@tool
def create_whatif(name: str, changes: list[Change]) -> dict:
    """Create a DRAFT what-if and get its before/after for the whole year.
    Only the user can apply or discard it (buttons in the building panel). After creating it,
    call ShowScenario with the returned scenario_id so the user sees it.

    Args:
        name: short name the user will see, e.g. "LED + solar on the library".
        changes: one or more changes (see Change).
    """
    s = scenarios.create_draft(name, [_intervention(c) for c in changes], source="agent")
    return {"scenario_id": s.id, "name": s.name, "status": s.status, "comparison": _brief(engine.compare(s.id))}


@tool
def compare_whatif(scenario_id: str, building_id: str | None = None) -> dict:
    """Before/after of an existing what-if over the whole year (only metrics that change).

    Args:
        scenario_id: from list_whatifs or create_whatif.
        building_id: optional; default is the building it touches, or "campus" if several.
    """
    return _brief(engine.compare(scenario_id, None if building_id in (None, "campus") else building_id))


@tool
def list_whatifs() -> list[dict]:
    """All what-ifs: drafts (only previews) and applied ones (already part of every number you get)."""
    return [
        {"scenario_id": s.id, "name": s.name, "status": s.status, "made_by": s.source, "note": s.note,
         "changes": [iv.model_dump(mode="json") for iv in s.interventions]}
        for s in scenarios.list_scenarios()
    ]


WHATIF_TOOLS = [list_presets, create_whatif, compare_whatif, list_whatifs]
