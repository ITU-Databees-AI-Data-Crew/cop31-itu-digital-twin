"""Energy, water and waste, built on top of occupancy + real weather + real size.

One formula per metric, the same for every building. Knobs live in params.yaml.
Emissions and the recycling rate are NOT generated: the Data API derives them at
query time, so a what-if on energy or waste carries through automatically.

Energy (hourly, kWh)
  lighting  = area × W/m² × (always-on share + share that follows people)
  plug      = area × always-on W/m² + people × W/person
  hvac      = fans while the building is on + cooling ÷ COP
  gas       = heating ÷ boiler efficiency
  Heating / cooling come from a heat balance against a smoothed outdoor temperature
  (thermal mass): loss = UA × (setpoint − outdoor); gains = people + lights + plugs + sun.
  UA = walls/windows (always) + fresh air per person (while on), so heating follows occupancy.
Water (hourly, m³)  = people × L/person-hour + area × baseload
Waste (daily, kg)   = person-hours × kg/person-hour, split into streams
"""

import numpy as np
import pandas as pd

from app.generator.occupancy import ar1

WASTE_STREAMS = ["recyclable", "organic", "residual", "hazardous"]


def smoothed(temp: pd.Series, hours: float) -> np.ndarray:
    """Outdoor temperature as the building 'feels' it: an exponential moving average."""
    return temp.ewm(alpha=1 - np.exp(-1 / hours)).mean().to_numpy()


def energy(people: np.ndarray, capacity: float, area: float, weather: pd.DataFrame, e: dict) -> dict[str, np.ndarray]:
    share = people / capacity
    on = share > e["on_threshold"]

    light_frac = e["lighting_always_on"] + (1 - e["lighting_always_on"]) * np.minimum(1, share / e["lighting_full_at"])
    lighting = area * e["lighting_w_m2"] * light_frac / 1000
    plug = (area * e["plug_base_w_m2"] + people * e["plug_w_per_person"]) / 1000
    fans = area * e["fan_w_m2"] / 1000 * on

    t_out = smoothed(weather["temp_c"], e["thermal_hours"])
    sun = weather["solar_wm2"].to_numpy() * area * e["solar_gain"] / 1000
    gains = people * e["heat_per_person_w"] / 1000 + lighting + plug + sun
    # kW per K: through walls/windows always, plus fresh outdoor air for the people inside while on
    ua = area * e["heat_loss_w_m2k"] / 1000 + on * people * e["ventilation_w_k_per_person"] / 1000

    t_heat = np.where(on, e["heat_setpoint_c"], e["heat_setback_c"])
    heat = np.maximum(0, ua * (t_heat - t_out) - gains)
    cool = np.where(on, np.maximum(0, gains - ua * (e["cool_setpoint_c"] - t_out)), 0)

    return {
        "electricity_lighting_kwh": lighting,
        "electricity_plug_kwh": plug,
        "electricity_hvac_kwh": fans + cool / e["cooling_cop"],
        "natural_gas_kwh": heat / e["boiler_efficiency"],
    }


def water(people: np.ndarray, area: float, w: dict, litres_per_person_hour: float) -> np.ndarray:
    return (people * litres_per_person_hour + area * w["base_l_per_m2_hour"]) / 1000


def waste(people: pd.Series, kg_per_person_hour: float, shares: dict, sigma: float, share_sigma: float,
          rng: np.random.Generator) -> pd.DataFrame:
    """Daily kg per stream. `people` is hourly, indexed by time.

    Each day's split wobbles around the building's typical shares, so the recycling rate isn't flat.
    """
    person_hours = people.resample("D").sum()
    n = len(person_hours)
    total = person_hours.to_numpy() * kg_per_person_hour * np.exp(rng.normal(0, sigma, n))
    base = np.array([shares[s] for s in WASTE_STREAMS])
    daily = base * np.exp(rng.normal(0, share_sigma, (n, len(WASTE_STREAMS))))
    daily /= daily.sum(axis=1, keepdims=True)
    return pd.DataFrame(total[:, None] * daily, index=person_hours.index, columns=[f"{s}_kg" for s in WASTE_STREAMS])


def generate(occ: pd.DataFrame, buildings: pd.DataFrame, weather: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Long table: building_id, system, metric, time, value (occupancy included)."""
    rng = np.random.default_rng(params["seed"] + 1)
    e, w, ws = params["energy"], params["water"], params["waste"]
    rows = []

    def add(bid, system, metric, times, values):
        rows.append(pd.DataFrame({"building_id": bid, "system": system, "metric": metric, "time": times, "value": values}))

    for bid, row in buildings.iterrows():
        bp = params["buildings"][bid]
        area = row["gross_floor_area_m2"]
        capacity = area / params["m2_per_person"]
        s = occ[occ["building_id"] == bid].set_index("time")["people"].reindex(weather.index)
        people = s.to_numpy(dtype=float)
        times = weather.index

        add(bid, "occupancy", "people", times, people)

        meter = lambda: np.exp(ar1(len(times), e["meter_memory"], e["meter_sigma"], rng))  # noqa: E731
        for metric, values in energy(people, capacity, area, weather, e).items():
            add(bid, "energy", metric, times, np.round(values * meter(), 2))

        lph = bp.get("water_l_per_person_hour", w["l_per_person_hour"])
        add(bid, "water", "water_m3", times, np.round(water(people, area, w, lph) * meter(), 3))

        kg = bp.get("waste_kg_per_person_hour", ws["kg_per_person_hour"])
        daily = waste(s, kg, bp["waste_shares"], ws["day_sigma"], ws["share_sigma"], rng)
        for metric in daily.columns:
            add(bid, "waste", metric, daily.index, daily[metric].round(2).to_numpy())

    return pd.concat(rows, ignore_index=True)


def summary(m: pd.DataFrame, buildings: pd.DataFrame) -> pd.DataFrame:
    """Yearly totals per building, per m² where it makes sense."""
    tot = m[m["system"] != "occupancy"].groupby(["building_id", "metric"])["value"].sum().unstack()
    area = buildings["gross_floor_area_m2"]
    elec = tot[[c for c in tot.columns if c.startswith("electricity_")]].sum(axis=1)
    return pd.DataFrame({
        "elec_kwh_m2": (elec / area).round(0),
        "gas_kwh_m2": (tot["natural_gas_kwh"] / area).round(0),
        "hvac_share_of_elec": (tot["electricity_hvac_kwh"] / elec).round(2),
        "water_m3": tot["water_m3"].round(0),
        "waste_t": (tot[[f"{s}_kg" for s in WASTE_STREAMS]].sum(axis=1) / 1000).round(1),
    })


def check(m: pd.DataFrame, buildings: pd.DataFrame, params: dict) -> list[str]:
    """Plausibility checks (ranges in params.yaml). Returns problems (empty = fine)."""
    problems = []
    if (m["value"] < 0).any():
        problems.append("negative values")
    for bid, bp in params["buildings"].items():
        if abs(sum(bp["waste_shares"].values()) - 1) > 1e-6:
            problems.append(f"{bid}: waste shares don't sum to 1")
    rng_ = params["checks"]
    for bid, r in summary(m, buildings).iterrows():
        for col in ("elec_kwh_m2", "gas_kwh_m2"):
            lo, hi = rng_[col]
            if not lo <= r[col] <= hi:
                problems.append(f"{bid}: {col} = {r[col]:.0f}, outside plausible {lo}–{hi}")
    return problems
