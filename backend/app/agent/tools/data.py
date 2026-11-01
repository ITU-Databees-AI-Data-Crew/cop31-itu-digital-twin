"""Campus data tools.

STUB: these return a few hard-coded fake buildings so the agent can be built and
tested before the Data API exists. When it does, keep the tool names and arguments
and replace each body with a Data API / Simulation engine call.
"""

from langchain_core.tools import tool

from app.contract import System

_FAKE_BUILDINGS = {
    "b01": {"id": "b01", "name": "Mustafa İnan Library", "type": "library", "floor_area_m2": 12000, "people_capacity": 1500},
    "b02": {"id": "b02", "name": "Faculty of Computer and Informatics", "type": "faculty", "floor_area_m2": 9000, "people_capacity": 1200},
    "b03": {"id": "b03", "name": "Faculty of Civil Engineering", "type": "faculty", "floor_area_m2": 15000, "people_capacity": 2000},
}

_FAKE_NOW = {
    "energy": {"electricity_kwh": 310.0, "natural_gas_kwh": 540.0},
    "emissions": {"co2e_kg": 251.0},
    "water": {"water_m3": 4.2},
    "waste": {"recyclable_kg": 6.0, "organic_kg": 9.5, "residual_kg": 12.0, "hazardous_kg": 0.1, "recycling_rate": 0.22},
    "occupancy": {"people": 640},
}


@tool
def list_buildings() -> list[dict]:
    """List all buildings in the model, with id, name, type, floor area and capacity."""
    return list(_FAKE_BUILDINGS.values())


@tool
def get_building(building_id: str) -> dict:
    """Get one building's details by its id."""
    if building_id not in _FAKE_BUILDINGS:
        return {"error": f"No building with id {building_id!r}. Use list_buildings to see the ids."}
    return _FAKE_BUILDINGS[building_id]


@tool
def get_current_values(building_id: str, system: System) -> dict:
    """Get a building's values for one system at the current app time (the last hour)."""
    if building_id not in _FAKE_BUILDINGS:
        return {"error": f"No building with id {building_id!r}. Use list_buildings to see the ids."}
    return {"building_id": building_id, "system": system, "per_hour": _FAKE_NOW[system]}


DATA_TOOLS = [list_buildings, get_building, get_current_values]
