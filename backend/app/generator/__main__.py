"""python -m app.generator [--plot]"""

import argparse

from app.generator import inputs, occupancy


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m app.generator")
    ap.add_argument("--plot", action="store_true", help="also write eyeball plots to data/generated/plots/")
    args = ap.parse_args()

    params = inputs.load_params()
    buildings = inputs.load_buildings()
    weather = inputs.load_weather()
    days = inputs.load_days(weather.index)

    occ = occupancy.generate(buildings, weather, days, params)
    inputs.GENERATED.mkdir(parents=True, exist_ok=True)
    out = inputs.GENERATED / "occupancy.csv"
    occ.to_csv(out, index=False)
    print(f"{out.relative_to(inputs.REPO)}: {len(occ)} rows ({occ['building_id'].nunique()} buildings × {len(weather)} hours)")

    for bid, g in occ.groupby("building_id"):
        cap = buildings.loc[bid, "gross_floor_area_m2"] / params["m2_per_person"]
        print(f"  {bid}: capacity {cap:.0f} | peak {g['people'].max()} | mean {g['people'].mean():.0f}")

    problems = occupancy.check(occ, buildings, params)
    print("checks: OK" if not problems else "checks FAILED:\n  " + "\n  ".join(problems))

    if args.plot:
        from app.generator import plot

        path = inputs.GENERATED / "plots" / "occupancy.png"
        plot.occupancy(occ, days, path)
        print(f"plot: {path.relative_to(inputs.REPO)}")


if __name__ == "__main__":
    main()
