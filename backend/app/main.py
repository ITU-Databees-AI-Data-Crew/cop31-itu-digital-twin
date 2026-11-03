"""Backend API: the front desk. Every route just hands the request to the right part.

    cd backend
    uvicorn app.main:app --reload      # http://localhost:8000/docs lists every route

Numbers come from the Simulation engine (current campus = baseline + applied what-ifs;
pass scenario_id to preview a draft). Bad input -> 400 with a message saying what's valid.
"""

import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from app.contract import AgentReply, ChatRequest, System
from app.data import campus
from app.data.campus import DataError
from app.sim import engine, presets, scenarios
from app.sim.clock import CLOCK

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # Vite dev server

app = FastAPI(title="İTÜ Campus Monitor", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(DataError)
async def _data_error(_: Request, exc: DataError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def _validation_error(_: Request, exc: ValidationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": exc.errors(include_url=False, include_context=False)})


@app.exception_handler(FileNotFoundError)
async def _no_store(_: Request, exc: FileNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail": str(exc)})


api = APIRouter(prefix="/api")


# --- health ------------------------------------------------------------------


@api.get("/health")
def health() -> dict:
    from app.agent.llm import DEFAULT_MODEL

    return {"ok": True, "data": campus.time_range(), "agent_ready": bool(os.environ.get("OPENROUTER_API_KEY")),
            "model": os.environ.get("COP31_MODEL", DEFAULT_MODEL)}


# --- static data -------------------------------------------------------------


@api.get("/buildings")
def buildings() -> list[dict]:
    return campus.list_buildings()


@api.get("/buildings/{building_id}")
def building(building_id: str) -> dict:
    return campus.get_building(building_id)


@api.get("/campus/geojson")
def campus_geojson() -> dict:
    return campus.get_campus_geojson()


@api.get("/metrics")
def metrics() -> list[dict]:
    return campus.list_metrics()


@api.get("/weather")
def weather(start: str, end: str, resolution: Literal["hour", "day", "month"] = "day") -> dict:
    return campus.get_weather(start, end, resolution)


# --- clock -------------------------------------------------------------------


class ClockRequest(BaseModel):
    action: Literal["play", "pause", "set"]
    time: str | None = None  # for set
    speed: float | None = None  # sim hours per real second, for play


@api.get("/clock")
def clock() -> dict:
    return CLOCK.state()


@api.post("/clock")
def clock_control(req: ClockRequest) -> dict:
    if req.action == "set":
        if not req.time:
            raise DataError("action 'set' needs a time, e.g. 2026-01-07T10:00.")
        return CLOCK.set_time(req.time)
    if req.action == "play":
        return CLOCK.play(req.speed)
    return CLOCK.pause()


# --- numbers (current campus, optional draft preview) ------------------------


@api.get("/buildings/{building_id}/now")
def building_now(building_id: str, system: System, scenario_id: str | None = None) -> dict:
    return engine.now(building_id, system, scenario_id)


@api.get("/campus/now")
def campus_now(system: System, scenario_id: str | None = None) -> list[dict]:
    return engine.campus_now(system, scenario_id)


@api.get("/buildings/{building_id}/series")
def building_series(building_id: str, metric: str, start: str, end: str,
                    resolution: Literal["hour", "day", "month"] = "hour", scenario_id: str | None = None) -> dict:
    return engine.series(building_id, metric, start, end, resolution, scenario_id)


@api.get("/totals")
def totals(system: System, start: str, end: str, building_id: str | None = None, scenario_id: str | None = None) -> dict:
    """building_id empty (or 'campus') = the whole campus."""
    return engine.totals(None if building_id in (None, "campus") else building_id, system, start, end, scenario_id)


@api.get("/rank")
def rank(metric: str, start: str, end: str, per: Literal["total", "m2", "person_hour"] = "total",
         scenario_id: str | None = None) -> list[dict]:
    return engine.rank(metric, start, end, per, scenario_id)


# --- what-ifs ----------------------------------------------------------------


class ScenarioCreate(BaseModel):
    """Either a preset (preset + building_id, optional amount/start) or your own interventions (name + interventions)."""

    name: str | None = None
    preset: str | None = None
    building_id: str | None = None
    amount: float | None = None
    start: str | None = None
    interventions: list[dict] | None = None


@api.get("/presets")
def list_presets(building_id: str | None = None) -> list[dict]:
    return presets.list_presets(building_id)


@api.get("/scenarios")
def list_scenarios(status: Literal["draft", "applied"] | None = None) -> list[dict]:
    return [s.model_dump(mode="json") for s in scenarios.list_scenarios(status)]


@api.post("/scenarios", status_code=201)
def create_scenario(req: ScenarioCreate) -> dict:
    if req.preset:
        if not req.building_id:
            raise DataError("A preset needs a building_id.")
        s = presets.create_from_preset(req.preset, req.building_id, req.amount, req.start, source="user", name=req.name)
    elif req.interventions:
        s = scenarios.create_draft(req.name or "My what-if", req.interventions, source="user")
    else:
        raise DataError("Send either preset + building_id, or interventions.")
    return s.model_dump(mode="json")


@api.get("/scenarios/{scenario_id}")
def get_scenario(scenario_id: str) -> dict:
    return scenarios.get_scenario(scenario_id).model_dump(mode="json")


@api.get("/scenarios/{scenario_id}/compare")
def compare_scenario(scenario_id: str, building_id: str | None = None, start: str | None = None, end: str | None = None) -> dict:
    return engine.compare(scenario_id, None if building_id in (None, "campus") else building_id, start, end)


@api.post("/scenarios/{scenario_id}/apply")
def apply_scenario(scenario_id: str) -> dict:
    return scenarios.apply_scenario(scenario_id).model_dump(mode="json")


@api.delete("/scenarios/{scenario_id}", status_code=204)
def discard_scenario(scenario_id: str) -> None:
    scenarios.discard_scenario(scenario_id)


# --- chat --------------------------------------------------------------------

_agent = None


def get_agent():
    global _agent
    if _agent is None:
        if not os.environ.get("OPENROUTER_API_KEY"):
            raise HTTPException(503, "The chat helper needs OPENROUTER_API_KEY (environment or backend/.env).")
        from app.agent import Agent

        _agent = Agent()
    return _agent


@api.post("/chat")
def chat(req: ChatRequest) -> AgentReply:
    """One chat turn. The app clock is the source of truth for "now", whatever the screen sent."""
    agent = get_agent()
    req.ui_state.sim_time = CLOCK.now().to_pydatetime()
    return agent.run(req.session_id, req.message, req.ui_state)


@api.post("/chat/{session_id}/reset", status_code=204)
def chat_reset(session_id: str) -> None:
    get_agent().sessions.reset(session_id)


app.include_router(api)

# The built frontend (npm run build) is served from / for the demo: one program, one laptop.
if FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
