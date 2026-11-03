"""Download the real-world inputs the Generator is built on.

Only three things in the app come from real data: building shapes, building
sizes and weather. Everything else is synthetic (made by the Generator).

Writes, into data/inputs/:
  campus.geojson  İTÜ Ayazağa campus boundary + every building footprint inside it (OpenStreetMap)
  buildings.csv   the demo buildings, real fields only (floors, footprint, gross floor area)
  weather.csv     one academic year of hourly weather for the campus (Open-Meteo, ERA5)

Run from the repo root:  python data/fetch_inputs.py
Uses only the Python standard library.
"""

import csv
import io
import json
import math
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).parent / "inputs"
USER_AGENT = "cop31-itu-campus-monitor (student demo project)"

# OpenStreetMap way ids
CAMPUS_WAY = 549717756  # İstanbul Teknik Üniversitesi (Ayazağa)
DEMO_BUILDINGS = {  # demo id -> OSM way id
    "bbf": 1157382425,  # Bilgisayar ve Bilişim Fakültesi
    "meda": 230687436,  # Merkezi Derslik A
    "lib": 145342395,  # İTÜ Mustafa İnan Kütüphanesi
}

# Weather: campus point, one academic year
LAT, LON = 41.1045, 29.0235
START, END = "2025-09-01", "2026-08-31"
WEATHER_VARS = {  # Open-Meteo name -> our column name
    "temperature_2m": "temp_c",
    "relative_humidity_2m": "rel_humidity_pct",
    "precipitation": "precip_mm",
    "cloud_cover": "cloud_cover_pct",
    "wind_speed_10m": "wind_kmh",
    "shortwave_radiation": "solar_wm2",
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OPEN_METEO_URL = "https://archive-api.open-meteo.com/v1/archive"


def get(url: str, data: dict | None = None) -> bytes:
    body = urllib.parse.urlencode(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=180) as r:
        return r.read()


def area_m2(points: list[dict]) -> float:
    """Polygon area from lat/lon points (flat projection, fine at campus scale)."""
    lat0 = math.radians(sum(p["lat"] for p in points) / len(points))
    r = 6371000
    xy = [(math.radians(p["lon"]) * r * math.cos(lat0), math.radians(p["lat"]) * r) for p in points]
    return abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(xy, xy[1:] + xy[:1]))) / 2


def number(v: str | None) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def fetch_campus() -> None:
    demo_ids = ",".join(str(i) for i in DEMO_BUILDINGS.values())
    query = f"""[out:json][timeout:90];
way({CAMPUS_WAY});map_to_area->.a;
(way({CAMPUS_WAY});way["building"](area.a);way(id:{demo_ids}););
out tags geom;"""
    elements = json.loads(get(OVERPASS_URL, {"data": query}))["elements"]
    demo_by_osm = {v: k for k, v in DEMO_BUILDINGS.items()}

    features, rows = [], []
    for e in sorted(elements, key=lambda e: e["id"]):
        if e["type"] != "way" or "geometry" not in e:
            continue
        tags = e.get("tags", {})
        ring = [[p["lon"], p["lat"]] for p in e["geometry"]]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        props = {
            "kind": "campus" if e["id"] == CAMPUS_WAY else "building",
            "osm_id": e["id"],
            "name": tags.get("name"),
            "building": tags.get("building"),
            "levels": number(tags.get("building:levels")),
            "levels_underground": number(tags.get("building:levels:underground")),
            "height_m": number(tags.get("height")),
            "footprint_m2": round(area_m2(e["geometry"]), 1),
            "demo_id": demo_by_osm.get(e["id"]),
        }
        features.append({"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [ring]}})

        if props["demo_id"]:
            if props["levels"] is None:
                raise SystemExit(f"{props['name']} has no building:levels in OSM; can't compute floor area.")
            floors = props["levels"] + (props["levels_underground"] or 0)
            rows.append({
                "id": props["demo_id"],
                "osm_id": e["id"],
                "name": props["name"],
                "levels": int(props["levels"]),
                "levels_underground": int(props["levels_underground"] or 0),
                "height_m": props["height_m"] or "",
                "footprint_m2": props["footprint_m2"],
                "gross_floor_area_m2": round(props["footprint_m2"] * floors),
            })

    missing = set(DEMO_BUILDINGS) - {r["id"] for r in rows}
    if missing:
        raise SystemExit(f"Demo buildings not found in OSM: {sorted(missing)}")

    (OUT / "campus.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8"
    )
    order = list(DEMO_BUILDINGS)
    rows.sort(key=lambda r: order.index(r["id"]))
    with open(OUT / "buildings.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    n = sum(1 for f in features if f["properties"]["kind"] == "building")
    print(f"campus.geojson: {n} buildings + campus boundary | buildings.csv: {len(rows)} demo buildings")


def fetch_weather() -> None:
    params = {
        "latitude": LAT,
        "longitude": LON,
        "start_date": START,
        "end_date": END,
        "hourly": ",".join(WEATHER_VARS),
        "timezone": "Europe/Istanbul",
        "format": "csv",
    }
    text = get(f"{OPEN_METEO_URL}?{urllib.parse.urlencode(params)}").decode()
    lines = list(csv.reader(io.StringIO(text)))
    # Open-Meteo CSV: 2 lines of location info, a blank line, then the hourly table.
    start = next(i for i, row in enumerate(lines) if row and row[0] == "time")
    got = [c.split(" (")[0] for c in lines[start][1:]]  # "temperature_2m (°C)" -> "temperature_2m"
    if got != list(WEATHER_VARS):
        raise SystemExit(f"Unexpected weather columns: {got}")
    data = [row for row in lines[start + 1 :] if row]
    if any("" in row for row in data):
        raise SystemExit("Weather has empty values; check the date range.")
    with open(OUT / "weather.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["time", *WEATHER_VARS.values()])
        w.writerows(data)
    print(f"weather.csv: {len(data)} hours, {START} to {END}")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    fetch_campus()
    fetch_weather()
