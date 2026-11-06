"""What-if math: turn interventions into an `adjust(building_id, frame)` for the Data API.

The Data API fetches each building's raw numbers, calls adjust, then sums and derives as usual,
so emissions, grid electricity and recycling rate follow the what-if automatically.

Simplification: effects don't chain (LEDs give off less heat, so heating would rise a little;
that's ignored).
"""

from collections import defaultdict

import pandas as pd

from app.data import campus
from app.data.campus import DataError
from app.sim.scenarios import Scale, Shift, SolarPV

# Rooftop solar. Typical values, adjustable.
PV_KWP_PER_M2 = 0.18  # modern panels: roughly 180-220 Wp per m² of panel
PV_USABLE_ROOF = 0.5  # share of the roof that can take panels (edges, equipment, shading, walkways)
PV_PERFORMANCE_RATIO = 0.80  # inverter, temperature, wiring and dirt losses

SCALABLE = [m for m, v in campus.METRICS.items() if not v["derived"] and m != "people"]


def max_pv_kwp(building: dict) -> float:
    """Biggest solar array the building's real roof (OSM footprint) can take."""
    return round(building["footprint_m2"] * PV_USABLE_ROOF * PV_KWP_PER_M2, 1)


def validate(interventions: list) -> None:
    """Check every intervention against the campus. Raises DataError explaining what's wrong."""
    buildings = {b["id"]: b for b in campus.list_buildings()}
    r = campus.time_range()
    first, last = r["start"][:10], r["end"][:10]
    for iv in interventions:
        if iv.start and not first <= iv.start.isoformat() <= last:
            raise DataError(f"Start {iv.start} is outside the data year ({first} to {last}), so it would never take effect.")
        if iv.building_id not in buildings:
            raise DataError(f"No building with id {iv.building_id!r}. Valid ids: {', '.join(buildings)}")
        if isinstance(iv, Scale) and iv.metric not in SCALABLE:
            raise DataError(f"Can't scale {iv.metric!r}. Scalable metrics: {', '.join(SCALABLE)}")
        if isinstance(iv, Shift):
            for m in (iv.from_metric, iv.to_metric):
                if m not in campus.WASTE_STREAMS:
                    raise DataError(f"Shift works between waste streams only: {', '.join(campus.WASTE_STREAMS)}")
            if iv.from_metric == iv.to_metric:
                raise DataError("Shift needs two different waste streams.")
        if isinstance(iv, SolarPV):
            cap = max_pv_kwp(buildings[iv.building_id])
            if iv.kwp > cap:
                raise DataError(f"{iv.kwp} kWp doesn't fit on {iv.building_id}'s roof; the most is about {cap} kWp.")


def pv_output(kwp: float, index: pd.DatetimeIndex) -> pd.Series:
    """kWh per hour from kWp panels, from the real hourly sunshine (W/m² on the ground)."""
    sun = campus.weather_frame()["solar_wm2"].reindex(index).fillna(0)
    return kwp * sun / 1000 * PV_PERFORMANCE_RATIO


def _apply(iv, df: pd.DataFrame) -> pd.DataFrame:
    on = df.index >= pd.Timestamp(iv.start) if iv.start else slice(None)
    if isinstance(iv, Scale) and iv.metric in df:
        df.loc[on, iv.metric] *= 1 + iv.change_pct / 100
    elif isinstance(iv, Shift) and iv.from_metric in df and iv.to_metric in df:
        moved = df.loc[on, iv.from_metric] * iv.share
        df.loc[on, iv.from_metric] -= moved
        df.loc[on, iv.to_metric] += moved
    elif isinstance(iv, SolarPV) and set(campus.ELEC_PARTS) <= set(df.columns):
        pv = pv_output(iv.kwp, df.index)
        if iv.start:
            pv = pv.where(df.index >= pd.Timestamp(iv.start), 0)
        hourly = df[campus.ELEC_PARTS].notna().any(axis=1)  # only rows that carry electricity
        df["pv_generation_kwh"] = df.get("pv_generation_kwh", 0) + pv.where(hourly)
    return df


def adjuster(interventions: list):
    """An adjust(building_id, frame) for the Data API, or None if there's nothing to apply."""
    if not interventions:
        return None
    by_building = defaultdict(list)
    for iv in interventions:
        by_building[iv.building_id].append(iv)

    def adjust(building_id: str, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        for iv in by_building.get(building_id, []):
            df = _apply(iv, df)
        return df

    return adjust
