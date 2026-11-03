"""Eyeball plots: is the synthetic occupancy convincing?"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

TERM_WEEK = ("2025-11-03", "2025-11-09")
EXAM_WEEK = ("2026-01-05", "2026-01-11")
NAMES = {"bbf": "BBF", "meda": "MED-A", "lib": "Library"}


def occupancy(occ: pd.DataFrame, days: pd.DataFrame, path: Path) -> None:
    ids = list(occ["building_id"].unique())
    fig, axes = plt.subplots(len(ids), 3, figsize=(17, 3.2 * len(ids)), gridspec_kw={"width_ratios": [1, 1, 2]})
    for r, bid in enumerate(ids):
        s = occ[occ["building_id"] == bid].set_index("time")["people"]
        for c, (title, (a, b)) in enumerate([("term week", TERM_WEEK), ("exam week", EXAM_WEEK)]):
            ax = axes[r, c]
            w = s[a : f"{b} 23:00"]
            ax.plot(w.index, w.values, lw=1.2)
            ax.set_title(f"{NAMES.get(bid, bid)}: {title} ({a})", fontsize=10)
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%a"))
            ax.set_ylabel("people")
            ax.grid(alpha=0.3)
        ax = axes[r, 2]
        daily = s.resample("D").max()
        ax.plot(daily.index, daily.values, lw=1)
        for d, t in days["day_type"].items():
            if t == "exam":
                ax.axvspan(d, d + pd.Timedelta(days=1), color="tab:red", alpha=0.08, lw=0)
        ax.set_title(f"{NAMES.get(bid, bid)}: daily peak, whole year (red = finals)", fontsize=10)
        ax.grid(alpha=0.3)
    _save(fig, path)


WINTER_WEEK = ("2025-12-08", "2025-12-14")
SUMMER_WEEK = ("2026-07-13", "2026-07-19")
ENERGY_PARTS = {
    "electricity_lighting_kwh": "lighting",
    "electricity_plug_kwh": "plug",
    "electricity_hvac_kwh": "HVAC (fans + cooling)",
    "natural_gas_kwh": "gas (heating)",
}


def _series(m: pd.DataFrame, bid: str, metric: str) -> pd.Series:
    s = m[(m["building_id"] == bid) & (m["metric"] == metric)]
    return pd.Series(s["value"].to_numpy(), index=pd.to_datetime(s["time"]))


def _save(fig, path: Path) -> None:
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)


def energy(m: pd.DataFrame, path: Path) -> None:
    ids = list(m["building_id"].unique())
    fig, axes = plt.subplots(len(ids), 3, figsize=(17, 3.2 * len(ids)), gridspec_kw={"width_ratios": [1, 1, 2]})
    for r, bid in enumerate(ids):
        parts = {label: _series(m, bid, metric) for metric, label in ENERGY_PARTS.items()}
        for c, (title, (a, b)) in enumerate([("winter term week", WINTER_WEEK), ("summer week", SUMMER_WEEK)]):
            ax = axes[r, c]
            for label, s in parts.items():
                w = s[a : f"{b} 23:00"]
                ax.plot(w.index, w.values, lw=1.1, label=label)
            ax.set_title(f"{NAMES.get(bid, bid)}: {title} ({a})", fontsize=10)
            ax.xaxis.set_major_formatter(matplotlib.dates.DateFormatter("%a"))
            ax.set_ylabel("kWh per hour")
            ax.grid(alpha=0.3)
            if r == 0 and c == 0:
                ax.legend(fontsize=8)
        ax = axes[r, 2]
        elec = sum(s for label, s in parts.items() if not label.startswith("gas"))
        ax.plot(elec.resample("D").sum(), lw=1, label="electricity")
        ax.plot(parts["gas (heating)"].resample("D").sum(), lw=1, label="gas")
        ax.set_title(f"{NAMES.get(bid, bid)}: daily kWh, whole year", fontsize=10)
        ax.grid(alpha=0.3)
        if r == 0:
            ax.legend(fontsize=8)
    _save(fig, path)


def water_waste(m: pd.DataFrame, path: Path) -> None:
    ids = list(m["building_id"].unique())
    fig, axes = plt.subplots(len(ids), 2, figsize=(17, 3.0 * len(ids)))
    for r, bid in enumerate(ids):
        ax = axes[r, 0]
        ax.plot(_series(m, bid, "water_m3").resample("D").sum(), lw=1)
        ax.set_title(f"{NAMES.get(bid, bid)}: daily water (m³)", fontsize=10)
        ax.grid(alpha=0.3)
        ax = axes[r, 1]
        streams = ["recyclable", "organic", "residual", "hazardous"]
        data = [_series(m, bid, f"{s}_kg") for s in streams]
        ax.stackplot(data[0].index, *[d.values for d in data], labels=streams, alpha=0.8)
        ax.set_title(f"{NAMES.get(bid, bid)}: daily waste by stream (kg)", fontsize=10)
        ax.grid(alpha=0.3)
        if r == 0:
            ax.legend(fontsize=8, loc="upper left")
    _save(fig, path)
