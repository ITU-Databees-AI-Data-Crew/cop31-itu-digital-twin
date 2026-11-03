"""python -m app.generator [--plot]"""

import argparse

import pandas as pd

from app.data import store
from app.generator import inputs, occupancy, systems


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.generator")
    ap.add_argument("--plot", action="store_true", help="also write eyeball plots to data/generated/plots/")
    args = ap.parse_args()

    params = inputs.load_params()
    buildings = inputs.load_buildings()
    weather = inputs.load_weather()
    days = inputs.load_days(weather.index)

    occ = occupancy.generate(buildings, weather, days, params)
    m = systems.generate(occ, buildings, weather, params)

    for bid, g in occ.groupby("building_id"):
        cap = buildings.loc[bid, "gross_floor_area_m2"] / params["m2_per_person"]
        print(f"  {bid}: capacity {cap:.0f} | peak {g['people'].max()} | mean {g['people'].mean():.0f}")
    with pd.option_context("display.width", 120):
        print(systems.summary(m, buildings).to_string())

    problems = occupancy.check(occ, buildings, params) + systems.check(m, buildings, params)
    print("checks: OK" if not problems else "checks FAILED:\n  " + "\n  ".join(problems))

    capacity = (buildings["gross_floor_area_m2"] / params["m2_per_person"]).round().astype(int)
    store.build(m, buildings.assign(capacity=capacity), weather, meta={"seed": params["seed"]})
    print(f"{store.DB_PATH.relative_to(inputs.REPO)}: {len(m)} measurements, {len(buildings)} buildings")

    if args.plot:
        from app.generator import plot

        d = inputs.GENERATED / "plots"
        plot.occupancy(occ, days, d / "occupancy.png")
        plot.energy(m, d / "energy.png")
        plot.water_waste(m, d / "water_waste.png")
        print(f"plots: {d.relative_to(inputs.REPO)}/")


if __name__ == "__main__":
    main()
