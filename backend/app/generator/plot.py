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
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
