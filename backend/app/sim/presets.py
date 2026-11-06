"""Ready-made what-ifs for the agent and the UI. Each has one adjustable `amount`.

The default amounts are typical figures for this kind of measure, not İTÜ measurements:
the UI should present them as "typical, adjustable".
"""

from datetime import date

from app.data import campus
from app.data.campus import DataError
from app.sim import scenarios, whatif
from app.sim.scenarios import Scale, Shift, SolarPV


def _led(b, amount, start):
    return [Scale(building_id=b, metric="electricity_lighting_kwh", change_pct=-amount, start=start)]


def _heating(b, amount, start):
    return [Scale(building_id=b, metric="natural_gas_kwh", change_pct=-amount, start=start)]


def _it(b, amount, start):
    return [Scale(building_id=b, metric="electricity_plug_kwh", change_pct=-amount, start=start)]


def _taps(b, amount, start):
    return [Scale(building_id=b, metric="water_m3", change_pct=-amount, start=start)]


def _sorting(b, amount, start):
    # `amount` % of residual waste gets sorted, half into recyclable and half into organic
    half = amount / 200
    return [
        Shift(building_id=b, from_metric="residual_kg", to_metric="recyclable_kg", share=half, start=start),
        Shift(building_id=b, from_metric="residual_kg", to_metric="organic_kg", share=half / (1 - half), start=start),
    ]


def _solar(b, amount, start):
    return [SolarPV(building_id=b, kwp=amount, start=start)]


PRESETS = {
    "led_lighting": {
        "name": "LED lighting", "make": _led, "amount": 50, "amount_unit": "% less lighting electricity",
        "description": "Replace fluorescent lights with LEDs. Typical saving 40-60% of lighting electricity.",
    },
    "heating_upgrade": {
        "name": "Heating upgrade", "make": _heating, "amount": 25, "amount_unit": "% less gas",
        "description": "Roof/wall insulation, better windows and a condensing boiler. Typical saving 20-30% of heating gas.",
    },
    "it_shutdown": {
        "name": "After-hours IT shutdown", "make": _it, "amount": 15, "amount_unit": "% less plug electricity",
        "description": "Switch off PCs, screens and printers at night and on weekends. Typical saving 10-20% of plug loads.",
    },
    "low_flow_taps": {
        "name": "Low-flow taps and toilets", "make": _taps, "amount": 20, "amount_unit": "% less water",
        "description": "Aerators on taps and dual-flush toilets. Typical saving 15-30% of water.",
    },
    "waste_sorting": {
        "name": "Waste sorting", "make": _sorting, "amount": 40, "amount_unit": "% of residual waste sorted",
        "description": "Separate bins (and composting for cafés): part of the mixed residual waste becomes recyclable or organic.",
    },
    "rooftop_solar": {
        "name": "Rooftop solar", "make": _solar, "amount": None, "amount_unit": "kWp",
        "description": "Solar panels on the roof. Output follows the real Istanbul sunshine. Default: the biggest array the roof can take.",
    },
}


def list_presets(building_id: str | None = None) -> list[dict]:
    """The presets, with default amounts (for rooftop solar: the building's roof limit, if a building is given)."""
    out = []
    for pid, p in PRESETS.items():
        amount = p["amount"]
        if pid == "rooftop_solar" and building_id:
            amount = whatif.max_pv_kwp(campus.get_building(building_id))
        out.append({"preset": pid, "name": p["name"], "description": p["description"],
                    "default_amount": amount, "amount_unit": p["amount_unit"]})
    return out


def create_from_preset(preset: str, building_id: str, amount: float | None = None, start: date | str | None = None,
                       source: str = "user", name: str | None = None) -> scenarios.Scenario:
    """Make a draft what-if from a preset. Leave amount empty for the typical default."""
    if preset not in PRESETS:
        raise DataError(f"Unknown preset {preset!r}. Valid: {', '.join(PRESETS)}")
    p = PRESETS[preset]
    building = campus.get_building(building_id)
    if amount is None:
        amount = whatif.max_pv_kwp(building) if preset == "rooftop_solar" else p["amount"]
    if preset != "rooftop_solar" and not 0 < amount <= 100:
        raise DataError(f"amount for {preset} is a percentage between 0 and 100.")
    try:
        first_day = date.fromisoformat(str(start)[:10]) if start else None
    except ValueError as e:
        raise DataError(f"Can't read start {start!r} as a date. Use YYYY-MM-DD.") from e
    ivs = p["make"](building_id, float(amount), first_day)
    label = name or f"{p['name']}: {building['name']}"
    return scenarios.create_draft(label, ivs, source=source, preset=preset, note=f"{amount:g} {p['amount_unit']}")
