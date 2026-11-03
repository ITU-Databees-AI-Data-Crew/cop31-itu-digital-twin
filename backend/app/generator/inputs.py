"""Load the real inputs from data/inputs/."""

from pathlib import Path

import pandas as pd
import yaml

REPO = Path(__file__).resolve().parents[3]
INPUTS = REPO / "data" / "inputs"
GENERATED = REPO / "data" / "generated"
PARAMS = Path(__file__).with_name("params.yaml")

HOLIDAY_TYPES = {"holiday", "half_holiday"}


def load_params() -> dict:
    return yaml.safe_load(PARAMS.read_text(encoding="utf-8"))


def load_buildings() -> pd.DataFrame:
    return pd.read_csv(INPUTS / "buildings.csv").set_index("id")


def load_weather() -> pd.DataFrame:
    """Hourly weather, indexed by local time (Istanbul, UTC+3 all year)."""
    w = pd.read_csv(INPUTS / "weather.csv", parse_dates=["time"])
    return w.set_index("time")


def load_days(dates: pd.DatetimeIndex) -> pd.DataFrame:
    """One row per date: day_type (term/exam/break/...), holiday (none/holiday/half_holiday), weekend.

    Periods are applied in file order, so a later row overrides an earlier one
    (e.g. the spring mid-term break inside the spring term). Holidays go on top.
    """
    cal = pd.read_csv(INPUTS / "calendar.csv", parse_dates=["start", "end"])
    days = pd.DataFrame(index=pd.DatetimeIndex(dates.normalize().unique(), name="date"))
    days["day_type"] = None
    days["holiday"] = "none"
    for row in cal.itertuples():
        span = (days.index >= row.start) & (days.index <= row.end)
        col = "holiday" if row.day_type in HOLIDAY_TYPES else "day_type"
        days.loc[span, col] = row.day_type
    if days["day_type"].isna().any():
        missing = days.index[days["day_type"].isna()]
        raise SystemExit(f"calendar.csv doesn't cover {missing.min().date()} .. {missing.max().date()}")
    days["weekend"] = days.index.dayofweek >= 5
    return days
