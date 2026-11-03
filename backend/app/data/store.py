"""The store: one SQLite file, data/generated/campus.db.

Written once by the Generator (build), then only read by the app (connect).
Times are local Istanbul time as text, 'YYYY-MM-DDTHH:MM', so they sort and compare as strings.
"""

import sqlite3
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[3]
DB_PATH = REPO / "data" / "generated" / "campus.db"
CAMPUS_GEOJSON = REPO / "data" / "inputs" / "campus.geojson"
TIME_FORMAT = "%Y-%m-%dT%H:%M"

SCHEMA = """
CREATE TABLE buildings (
    id                  TEXT PRIMARY KEY,
    osm_id              INTEGER,
    name                TEXT,
    levels              INTEGER,
    levels_underground  INTEGER,
    height_m            REAL,
    footprint_m2        REAL,
    gross_floor_area_m2 REAL,
    capacity            INTEGER
);
CREATE TABLE measurements (
    building_id TEXT NOT NULL REFERENCES buildings(id),
    system      TEXT NOT NULL,
    metric      TEXT NOT NULL,
    time        TEXT NOT NULL,
    value       REAL NOT NULL,
    PRIMARY KEY (building_id, metric, time)
) WITHOUT ROWID;
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def build(measurements: pd.DataFrame, buildings: pd.DataFrame, meta: dict, path: Path = DB_PATH) -> None:
    """Write a fresh store. `buildings` is indexed by id and has a capacity column."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".db.tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    try:
        con.executescript(SCHEMA)
        b = buildings.reset_index().rename(columns={"index": "id"})
        b["height_m"] = b["height_m"].where(b["height_m"].notna(), None)
        cols = ["id", "osm_id", "name", "levels", "levels_underground", "height_m", "footprint_m2", "gross_floor_area_m2", "capacity"]
        con.executemany(f"INSERT INTO buildings VALUES ({','.join('?' * len(cols))})", b[cols].itertuples(index=False))
        m = measurements.assign(time=pd.to_datetime(measurements["time"]).dt.strftime(TIME_FORMAT))
        con.executemany(
            "INSERT INTO measurements VALUES (?,?,?,?,?)",
            m[["building_id", "system", "metric", "time", "value"]].itertuples(index=False),
        )
        con.executemany("INSERT INTO meta VALUES (?,?)", [(k, str(v)) for k, v in meta.items()])
        con.commit()
    finally:
        con.close()
    tmp.replace(path)  # swap in only when complete, so a crash never leaves a half-written store


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    """Read-only connection."""
    if not path.exists():
        raise FileNotFoundError(f"{path} doesn't exist. Run the generator first: python -m app.generator")
    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con
