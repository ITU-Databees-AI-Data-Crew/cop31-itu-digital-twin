"""Occupancy: how many people are in each building, every hour.

people(building, hour) = capacity × day_level × hour_shape × noise

- capacity:   gross floor area / m2_per_person (same rule for every building)
- day_level:  how busy the day is, from the calendar day type and weekend
- hour_shape: a soft plateau (opening hours) plus a few bumps (lunch, ...) on top of a night floor
- noise:      a day-level factor plus slowly drifting hourly noise, seeded
"""

import numpy as np
import pandas as pd


def hour_shape(hours: np.ndarray, p: dict) -> np.ndarray:
    """Share of the day's level present at each hour of day (0..~1). `hours` can be fractional."""
    pl = p["plateau"]
    rise = 1 / (1 + np.exp(-(hours - pl["start"]) / pl["ramp"] * 4))
    fall = 1 / (1 + np.exp((hours - pl["end"]) / pl["ramp"] * 4))
    shape = pl["level"] * rise * fall
    for b in p.get("bumps", []):
        shape = shape + b["height"] * np.exp(-0.5 * ((hours - b["at"]) / b["width"]) ** 2)
    floor = p["night_floor"]
    return floor + (1 - floor) * shape


def day_levels(days: pd.DataFrame, p: dict) -> tuple[pd.Series, pd.Series]:
    """Day level for each date, before 13:00 and from 13:00 (they differ only on half holidays)."""
    lv = p["day_level"]
    base = days["day_type"].map(lv).astype(float)
    base = base.where(~days["weekend"], base * p["weekend"])
    holiday = lv["holiday"]
    morning = base.where(days["holiday"] != "holiday", holiday)
    afternoon = morning.where(days["holiday"] != "half_holiday", holiday)
    return morning, afternoon


def soft_cap(share: np.ndarray, knee: float) -> np.ndarray:
    """Crowding: unchanged below `knee`, then bends smoothly towards 1 (full) without ever passing it."""
    over = np.maximum(share - knee, 0)
    return np.where(share < knee, share, knee + (1 - knee) * np.tanh(over / (1 - knee)))


def ar1(n: int, phi: float, sigma: float, rng: np.random.Generator) -> np.ndarray:
    """Slowly drifting noise with standard deviation ~sigma."""
    e = rng.normal(0, sigma * np.sqrt(1 - phi**2), n)
    x = np.empty(n)
    x[0] = rng.normal(0, sigma)
    for i in range(1, n):
        x[i] = phi * x[i - 1] + e[i]
    return x


def generate(buildings: pd.DataFrame, weather: pd.DataFrame, days: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Long table: building_id, time, people."""
    rng = np.random.default_rng(params["seed"])
    nz = params["noise"]
    times = weather.index
    date = times.normalize()
    hour = times.hour.to_numpy() + 0.5  # middle of the hour
    rain = (weather["precip_mm"] > 0.2).to_numpy()

    out = []
    for bid, row in buildings.iterrows():
        p = params["buildings"][bid]
        capacity = row["gross_floor_area_m2"] / params["m2_per_person"]

        morning, afternoon = day_levels(days, p)
        level = np.where(times.hour < 13, morning.reindex(date).to_numpy(), afternoon.reindex(date).to_numpy())

        day_noise = pd.Series(np.exp(rng.normal(0, nz["day_sigma"], len(days))), index=days.index)
        noise = day_noise.reindex(date).to_numpy() * np.exp(ar1(len(times), nz["hour_memory"], nz["hour_sigma"], rng))

        share = level * hour_shape(hour, p) * noise * (1 + p["rain_boost"] * rain)
        people = np.round(capacity * soft_cap(share, params["crowding_knee"]))
        out.append(pd.DataFrame({"building_id": bid, "time": times, "people": people.astype(int)}))
    return pd.concat(out, ignore_index=True)


def check(occ: pd.DataFrame, buildings: pd.DataFrame, params: dict) -> list[str]:
    """Sanity checks from the design. Returns a list of problems (empty = fine)."""
    problems = []
    hour = occ["time"].dt.hour
    for bid, g in occ.groupby("building_id"):
        cap = buildings.loc[bid, "gross_floor_area_m2"] / params["m2_per_person"]
        if g["people"].max() > cap:
            problems.append(f"{bid}: above capacity")
        night = g[hour.loc[g.index].isin([2, 3, 4])]["people"]
        if params["buildings"][bid]["night_floor"] == 0 and night.mean() > 0.01 * cap:
            problems.append(f"{bid}: nights not ~0 (mean {night.mean():.0f})")
        if params["buildings"][bid]["night_floor"] > 0 and (g["people"] == 0).any():
            problems.append(f"{bid}: hits 0 but should never be empty")
    return problems
