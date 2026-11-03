"""The Data API's questions. Every function returns plain dicts/lists.

Time ranges are half-open, [start, end): start included, end excluded. Pass ISO strings
('2026-01-15' or '2026-01-15T14:00') or datetimes, in local Istanbul time.

Derived metrics (electricity_kwh, co2e_*, recycling_rate) are never stored. They are
computed from the stored metrics *after* summing over time and buildings, so ratios like
the recycling rate are ratios of totals, not averages of ratios.

Bad input raises DataError with a message that says what the valid options are.

The `adjust` argument on the questions is for the Simulation engine only (what-ifs).
Call the Simulation engine, not these, when you want "now" or what-if numbers.
"""

import json
from collections.abc import Callable
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import pandas as pd
import yaml

from app.data import store

FACTORS = yaml.safe_load(Path(__file__).with_name("factors.yaml").read_text(encoding="utf-8"))
EF_ELEC = FACTORS["electricity_kg_co2e_per_kwh"]
EF_GAS = FACTORS["natural_gas_kg_co2e_per_kwh"]

SYSTEMS = ["energy", "emissions", "water", "waste", "occupancy"]
RESOLUTIONS = {"hour": None, "day": "D", "month": "MS"}
PER = ["total", "m2", "person_hour"]

ELEC_PARTS = ["electricity_lighting_kwh", "electricity_plug_kwh", "electricity_hvac_kwh"]
WASTE_STREAMS = ["recyclable_kg", "organic_kg", "residual_kg", "hazardous_kg"]


def _m(system, unit, resolution, aggregate, description, needs=None):
    return {"system": system, "unit": unit, "resolution": resolution, "aggregate": aggregate,
            "derived": needs is not None, "description": description, "_needs": needs}


# aggregate: how a metric adds up over time. sum = add it up; mean = average (people); ratio = derived ratio
METRICS = {
    "people": _m("occupancy", "people", "hour", "mean", "People in the building"),
    "electricity_kwh": _m("energy", "kWh", "hour", "sum", "Total electricity used (lighting + plug + HVAC)", ELEC_PARTS),
    "electricity_grid_kwh": _m("energy", "kWh", "hour", "sum", "Electricity bought from the grid (total minus rooftop solar)", ELEC_PARTS),
    "pv_generation_kwh": _m("energy", "kWh", "hour", "sum", "Electricity made by rooftop solar (0 unless a what-if adds panels)", ELEC_PARTS),
    "electricity_lighting_kwh": _m("energy", "kWh", "hour", "sum", "Electricity for lighting"),
    "electricity_plug_kwh": _m("energy", "kWh", "hour", "sum", "Electricity for plugged-in devices (computers, network, fridges, ...)"),
    "electricity_hvac_kwh": _m("energy", "kWh", "hour", "sum", "Electricity for ventilation fans and cooling"),
    "natural_gas_kwh": _m("energy", "kWh", "hour", "sum", "Natural gas burned for heating"),
    "co2e_kg": _m("emissions", "kg CO2e", "hour", "sum", "Total greenhouse gas emissions (grid electricity + gas)", ELEC_PARTS + ["natural_gas_kwh"]),
    "co2e_electricity_kg": _m("emissions", "kg CO2e", "hour", "sum", "Emissions from electricity bought from the grid", ELEC_PARTS),
    "co2e_gas_kg": _m("emissions", "kg CO2e", "hour", "sum", "Emissions from burning natural gas", ["natural_gas_kwh"]),
    "water_m3": _m("water", "m³", "hour", "sum", "Water used"),
    "recyclable_kg": _m("waste", "kg", "day", "sum", "Recyclable waste (paper, plastic, glass, metal)"),
    "organic_kg": _m("waste", "kg", "day", "sum", "Organic waste (food)"),
    "residual_kg": _m("waste", "kg", "day", "sum", "Residual (mixed, non-recyclable) waste"),
    "hazardous_kg": _m("waste", "kg", "day", "sum", "Hazardous waste (batteries, e-waste, chemicals)"),
    "recycling_rate": _m("waste", "share", "day", "ratio", "Recyclable share of all waste (0-1)", WASTE_STREAMS),
}


class DataError(ValueError):
    """Bad input to a Data API question. The message says what's valid."""


# --- helpers -----------------------------------------------------------------


def _metric(metric: str) -> dict:
    if metric not in METRICS:
        raise DataError(f"Unknown metric {metric!r}. Valid metrics: {', '.join(METRICS)}")
    return METRICS[metric]


def _system(system: str) -> list[str]:
    if system not in SYSTEMS:
        raise DataError(f"Unknown system {system!r}. Valid systems: {', '.join(SYSTEMS)}")
    return [k for k, v in METRICS.items() if v["system"] == system]


def _building_ids(con) -> list[str]:
    return [r["id"] for r in con.execute("SELECT id FROM buildings ORDER BY rowid")]


def _building(con, building_id: str) -> None:
    ids = _building_ids(con)
    if building_id not in ids:
        raise DataError(f"No building with id {building_id!r}. Valid ids: {', '.join(ids)}")


def _time(t, name: str) -> str:
    try:
        return pd.Timestamp(t).strftime(store.TIME_FORMAT)
    except (ValueError, TypeError) as e:
        raise DataError(f"Can't read {name} {t!r} as a time. Use e.g. '2026-01-15' or '2026-01-15T14:00'.") from e


def _range(con, start, end) -> tuple[str, str]:
    s, e = _time(start, "start"), _time(end, "end")
    if s >= e:
        raise DataError(f"start ({s}) must be before end ({e}).")
    first, last = con.execute("SELECT MIN(time), MAX(time) FROM measurements").fetchone()
    if e <= first or s > last:
        raise DataError(f"No data between {s} and {e}. Data covers {first} to {last}.")
    return s, e


def _stored(metrics: list[str]) -> list[str]:
    """Stored metrics needed to answer `metrics` (derived ones expanded)."""
    out = []
    for m in metrics:
        needs = METRICS[m]["_needs"]
        for s in [m] if needs is None else needs:
            if s not in out:
                out.append(s)
    return out


Adjust = Callable[[str, pd.DataFrame], pd.DataFrame]


def _frame(con, building_ids: list[str], metrics: list[str], start: str, end: str, adjust: Adjust | None = None) -> pd.DataFrame:
    """Stored metrics as columns, time as index, summed over the given buildings.

    `adjust(building_id, frame)` is the Simulation engine's hook: it changes one building's raw
    numbers (what-ifs) before they are summed. It may add a pv_generation_kwh column.
    """
    marks = f"building_id IN ({','.join('?' * len(building_ids))}) AND metric IN ({','.join('?' * len(metrics))}) AND time >= ? AND time < ?"
    params = [*building_ids, *metrics, start, end]
    if adjust is None:
        df = pd.read_sql_query(f"SELECT time, metric, SUM(value) AS value FROM measurements WHERE {marks} GROUP BY time, metric", con, params=params)
        wide = df.pivot(index="time", columns="metric", values="value")
        wide.index = pd.to_datetime(wide.index)
        return wide.reindex(columns=metrics)
    if set(metrics) & set(WASTE_STREAMS):  # what-ifs can move waste between streams, so fetch them all
        metrics = list(dict.fromkeys([*metrics, *WASTE_STREAMS]))
        marks = f"building_id IN ({','.join('?' * len(building_ids))}) AND metric IN ({','.join('?' * len(metrics))}) AND time >= ? AND time < ?"
        params = [*building_ids, *metrics, start, end]
    df = pd.read_sql_query(f"SELECT building_id, time, metric, value FROM measurements WHERE {marks}", con, params=params)
    df["time"] = pd.to_datetime(df["time"])
    parts = []
    for bid in building_ids:
        wide = df[df["building_id"] == bid].pivot(index="time", columns="metric", values="value").reindex(columns=metrics)
        parts.append(adjust(bid, wide))
    return pd.concat(parts).groupby(level=0).sum(min_count=1).sort_index()


def _derive(metric: str, df: pd.DataFrame) -> pd.Series:
    """Compute any metric (stored or derived) from a frame of stored metrics (rows can be totals)."""
    if not METRICS[metric]["derived"]:
        return df[metric]
    if metric in ("electricity_kwh", "electricity_grid_kwh", "pv_generation_kwh", "co2e_electricity_kg", "co2e_kg"):
        used = df[ELEC_PARTS].sum(axis=1, min_count=1)
        pv = df["pv_generation_kwh"].fillna(0) if "pv_generation_kwh" in df else used * 0
        grid = (used - pv).clip(lower=0)  # surplus solar isn't counted (no export credit)
        if metric == "electricity_kwh":
            return used
        if metric == "electricity_grid_kwh":
            return grid
        if metric == "pv_generation_kwh":
            return pv.where(used.notna())
        if metric == "co2e_electricity_kg":
            return grid * EF_ELEC
        return grid * EF_ELEC + df["natural_gas_kwh"] * EF_GAS
    if metric == "co2e_gas_kg":
        return df["natural_gas_kwh"] * EF_GAS
    if metric == "recycling_rate":
        total = df[WASTE_STREAMS].sum(axis=1, min_count=1)
        return (df["recyclable_kg"] / total).where(total > 0)
    raise AssertionError(metric)


def _clean(x: float | None, metric: str):
    if x is None or pd.isna(x):
        return None
    x = float(x)
    if METRICS[metric]["aggregate"] == "ratio" or abs(x) < 1:
        return float(f"{x:.4g}")  # small numbers (ratios, per-m², per-person) keep 4 significant digits
    return round(x, 2)


def _iso(t) -> str:
    return pd.Timestamp(t).strftime(store.TIME_FORMAT)


# --- the questions -----------------------------------------------------------


def list_metrics() -> list[dict]:
    """Every metric: name, system, unit, resolution (hour/day), whether it's derived, description."""
    return [{"metric": k, **{f: v for f, v in m.items() if not f.startswith("_")}} for k, m in METRICS.items()]


def list_buildings() -> list[dict]:
    """All buildings with their size and capacity."""
    with store.connect() as con:
        return [dict(r) for r in con.execute("SELECT * FROM buildings ORDER BY rowid")]


def get_building(building_id: str) -> dict:
    """One building's details."""
    with store.connect() as con:
        _building(con, building_id)
        return dict(con.execute("SELECT * FROM buildings WHERE id = ?", (building_id,)).fetchone())


def get_campus_geojson() -> dict:
    """Campus boundary + every building footprint (GeoJSON). Demo buildings have properties.demo_id set."""
    return json.loads(store.CAMPUS_GEOJSON.read_text(encoding="utf-8"))


def time_range() -> dict:
    """First and last hour with data."""
    with store.connect() as con:
        first, last, n = con.execute("SELECT MIN(time), MAX(time), COUNT(DISTINCT time) FROM measurements").fetchone()
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    return {"start": first, "end": last, "timezone": "Europe/Istanbul", "seed": meta.get("seed")}


def get_values_at(building_id: str, system: str, time: str | datetime, adjust: Adjust | None = None) -> dict:
    """All of one system's metrics for one building at one hour. Daily metrics (waste) give that whole day."""
    metrics = _system(system)
    with store.connect() as con:
        _building(con, building_id)
        t = pd.Timestamp(_time(time, "time"))
        hourly = [m for m in metrics if METRICS[m]["resolution"] == "hour"]
        daily = [m for m in metrics if METRICS[m]["resolution"] == "day"]
        values = {}
        for group, start, step in ((hourly, t.floor("h"), "1h"), (daily, t.floor("D"), "1D")):
            if not group:
                continue
            s = _iso(start)
            df = _frame(con, [building_id], _stored(group), s, _iso(start + pd.Timedelta(step)), adjust)
            if df.empty:
                raise DataError(f"No data at {s}. Use time_range() to see what's covered.")
            for m in group:
                values[m] = _clean(_derive(m, df).iloc[0], m)
    return {
        "building_id": building_id,
        "system": system,
        "time": _iso(t.floor("h")),
        "values": values,
        "units": {m: METRICS[m]["unit"] for m in metrics},
    }


def get_series(building_id: str, metric: str, start, end, resolution: str = "hour", adjust: Adjust | None = None) -> dict:
    """A time series for one building and metric. resolution: hour, day or month.

    Daily metrics (waste) can't go finer than day; asking for hourly gives daily.
    People are averaged over each period; everything else is summed.
    """
    info = _metric(metric)
    if resolution not in RESOLUTIONS:
        raise DataError(f"Unknown resolution {resolution!r}. Valid: {', '.join(RESOLUTIONS)}")
    if info["resolution"] == "day" and resolution == "hour":
        resolution = "day"
    with store.connect() as con:
        _building(con, building_id)
        s, e = _range(con, start, end)
        df = _frame(con, [building_id], _stored([metric]), s, e, adjust)
    if RESOLUTIONS[resolution]:
        how = {c: ("mean" if METRICS[c]["aggregate"] == "mean" else "sum") for c in df.columns}
        df = df.resample(RESOLUTIONS[resolution]).agg(how)
    values = _derive(metric, df)
    return {
        "building_id": building_id,
        "metric": metric,
        "unit": info["unit"],
        "resolution": resolution,
        "points": [{"time": _iso(t), "value": _clean(v, metric)} for t, v in values.items()],
    }


def _totals(con, building_ids: list[str], metrics: list[str], s: str, e: str, adjust: Adjust | None = None) -> dict:
    df = _frame(con, building_ids, _stored(metrics), s, e, adjust)
    out = {}
    sums = df.sum(min_count=1).to_frame().T
    for m in metrics:
        if m == "people":
            out["people_mean"] = _clean(df["people"].mean(), m)
            out["people_peak"] = _clean(df["people"].max(), m)
            out["person_hours"] = _clean(df["people"].sum(), m)
        else:
            out[m] = _clean(_derive(m, sums).iloc[0], m)
    return out


def get_totals(building_id: str | None, system: str, start, end, adjust: Adjust | None = None) -> dict:
    """Totals of one system's metrics over a period. building_id=None means the whole campus (all buildings).

    Occupancy gives people_mean, people_peak and person_hours instead of a sum.
    """
    metrics = _system(system)
    with store.connect() as con:
        ids = _building_ids(con) if building_id is None else [building_id]
        if building_id is not None:
            _building(con, building_id)
        s, e = _range(con, start, end)
        totals = _totals(con, ids, metrics, s, e, adjust)
    units = {m: METRICS[m]["unit"] for m in metrics if m != "people"}
    if "people" in metrics:
        units.update(people_mean="people", people_peak="people", person_hours="person-hours")
    return {"building_id": building_id or "campus", "system": system, "start": s, "end": e, "totals": totals, "units": units}


def rank_buildings(metric: str, start, end, per: str = "total", adjust: Adjust | None = None) -> list[dict]:
    """Buildings ranked by a metric over a period, highest first.

    per: total, m2 (per m² of floor area) or person_hour (per hour someone spent in the building).
    Ratios (recycling_rate) and people can only be ranked as total.
    """
    info = _metric(metric)
    if per not in PER:
        raise DataError(f"Unknown per {per!r}. Valid: {', '.join(PER)}")
    if per != "total" and info["aggregate"] != "sum":
        raise DataError(f"{metric} can only be ranked with per='total'.")
    with store.connect() as con:
        s, e = _range(con, start, end)
        rows = []
        for b in con.execute("SELECT id, name, gross_floor_area_m2 FROM buildings ORDER BY rowid").fetchall():
            t = _totals(con, [b["id"]], [metric] + (["people"] if per == "person_hour" else []), s, e, adjust)
            value = t["people_mean"] if metric == "people" else t[metric]
            if value is not None and per == "m2":
                value = value / b["gross_floor_area_m2"]
            elif value is not None and per == "person_hour":
                value = value / t["person_hours"] if t["person_hours"] else None
            unit = info["unit"] + {"total": "", "m2": " per m²", "person_hour": " per person-hour"}[per]
            rows.append({"building_id": b["id"], "name": b["name"], "value": _clean(value, metric), "unit": unit})
    return sorted(rows, key=lambda r: (r["value"] is None, -(r["value"] or 0)))


WEATHER_AGG = {"temp_c": "mean", "rel_humidity_pct": "mean", "precip_mm": "sum", "cloud_cover_pct": "mean", "wind_kmh": "mean", "solar_wm2": "mean"}


@lru_cache(maxsize=1)
def weather_frame() -> pd.DataFrame:
    """The whole year of hourly weather as a DataFrame (cached). For the Simulation engine (solar what-ifs)."""
    with store.connect() as con:
        w = pd.read_sql_query("SELECT * FROM weather ORDER BY time", con)
    w.index = pd.to_datetime(w.pop("time"))
    return w


def get_weather(start, end, resolution: str = "day") -> dict:
    """Real Istanbul weather for a period. Hourly values, or per day/month: temperature, humidity, cloud,
    wind and sunshine are averaged; rain is summed."""
    if resolution not in RESOLUTIONS:
        raise DataError(f"Unknown resolution {resolution!r}. Valid: {', '.join(RESOLUTIONS)}")
    with store.connect() as con:
        s, e = _range(con, start, end)
    w = weather_frame().loc[s:e]
    w = w[w.index < pd.Timestamp(e)]
    if RESOLUTIONS[resolution]:
        w = w.resample(RESOLUTIONS[resolution]).agg(WEATHER_AGG)
    units = {"temp_c": "°C", "rel_humidity_pct": "%", "precip_mm": "mm", "cloud_cover_pct": "%", "wind_kmh": "km/h", "solar_wm2": "W/m²"}
    points = [{"time": _iso(t), **{k: round(float(v), 1) for k, v in row.items()}} for t, row in w.iterrows()]
    return {"resolution": resolution, "units": units, "points": points}
