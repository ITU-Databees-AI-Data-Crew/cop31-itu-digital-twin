# İTÜ Campus Monitor

**A screen that shows how İTÜ's campus uses energy, water and resources, and a helper you can ask about it.**
Made by the İTÜ DataBees AI & Data Crew for COP31.

> 🚧 **Work in progress.** This page describes how the app *will* work. Setup steps get filled in as each part is built.

## What is it?

Imagine the whole campus as a 3D model on your screen. Click any building and you see:
how much electricity and gas it uses, how much water, how much waste it makes, and how many people are inside.

Next to it there's a chat helper. You can ask it things like
*"Which building uses the most gas?"* and it answers **and** shows you the building on the map.

You can also ask **"what if?"**: *"What if this building got LED lights?"*
The app shows the numbers **before and after**, so you can decide whether it's worth doing.

**About the data:** we don't have real meter readings from İTÜ, so the numbers are **modelled**.
They come from real building shapes, real Istanbul weather and published energy numbers. They're realistic, but they're not real meter readings.

## How to use it

The screen has three panels:

```
┌──────────────┬──────────────────────────┬──────────────────┐
│  CHAT        │   3D CAMPUS              │  BUILDING        │
│              │                          │                  │
│  Ask the     │   Click a building       │  Details         │
│  helper      │   to select it           │  [Energy][Water] │
│  anything    │                          │  [Waste][...]    │
│              │   Colour buildings by    │  Charts          │
│              │   a number               │  What-if: before │
│              │                          │  vs after        │
└──────────────┴──────────────────────────┴──────────────────┘
                        🕒 app clock
```

### Look around
- **Drag** to rotate the campus, **scroll** to zoom.
- **Click a building** to select it. The right panel shows its details.
- **Grey buildings** are not part of the model and can't be selected.

### Read a building
- Use the **tabs** on the right: Energy, Emissions, Water, Waste, Occupancy.
- The **clock** shows the app's current time. Numbers marked "now" are for that time.

### Ask the helper
Type into the chat on the left. Things you can try:
- *"Which building used the most electricity this month?"*
- *"Compare the library and the stadium on water."*
- *"Colour the campus by CO₂."*
- *"Why is gas use so high in January?"*

The helper may also move things on screen for you. For example, it might select the building it's talking about.

### Try a what-if
1. Ask: *"What if building X switched to LED lighting?"* (or use the what-if button on the right panel).
2. A **draft** appears in the right panel, with before and after side by side.
3. Press **Apply** to keep it, or **Discard** to drop it.

The real numbers are never changed. A what-if is a layer on top, and you can always remove it.

## How it works (short version)

Six parts, each with one job:

1. **Generator.** Makes up a believable year of campus data before the app starts.
2. **Simulation engine.** Keeps the clock and works out what-ifs.
3. **Data API.** Stores all numbers and answers questions about them.
4. **Agent.** The chat helper.
5. **Backend API.** The front desk the screen talks to.
6. **Frontend.** The screen.

More detail:
- [docs/dataflow.md](docs/dataflow.md): a picture of how data moves
- [docs/components.md](docs/components.md): what each part does, exactly

## Running it on your computer

🚧 *Coming soon.* What we know so far:

- **Backend:** Python 3.11+, in `backend/`
- **Frontend:** Node.js, in `frontend/`
- **You'll need:** an OpenRouter API key for the chat helper (`OPENROUTER_API_KEY`).
  Optional: `TAVILY_API_KEY` for better web search (without it, the helper uses DuckDuckGo).
- **For the demo,** everything runs as one program on one laptop. Nothing is put online.

**Already works: make the data.** This builds a year of synthetic campus data into `data/generated/campus.db`
(same result every time). Run it once before anything else:

```bash
cd backend
pip install -e ".[generator]"
python -m app.generator --plot    # --plot also draws charts into data/generated/plots/
```

The real inputs (building shapes and sizes, weather, academic calendar) are already in `data/inputs/`.
To download them again: `python data/fetch_inputs.py` from the repo root.

**Easiest: Docker.** Needs only Docker (with Compose). Put your keys in `backend/.env` first (copy `backend/.env.example`);
without them everything works except the chat.

```bash
docker compose up --build      # then open http://localhost:8080
```

The data is generated while the image builds, so there's nothing else to run. What-ifs are kept in a Docker volume,
so they survive restarts. `docker compose down -v` also deletes them.

**Without Docker: the whole app as one program.** After making the data (above):

```bash
cd frontend && npm install && npm run build && cd ..   # once, and after frontend changes
cd backend && uvicorn app.main:app                     # then open http://localhost:8000
```

To work on the screen with live reload instead: run the backend as below, and `npm run dev` in `frontend/` (http://localhost:5173).

**The backend on its own.** Put your keys in `backend/.env` (copy `backend/.env.example`), then:

```bash
cd backend
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs to see and try every route (buildings, clock, numbers, what-ifs, chat).
Without an OpenRouter key everything works except the chat.

**Already works: chat with the helper in your terminal**, no frontend needed:

```bash
cd backend
python -m app.agent
```

The default model is `xiaomi/mimo-v2.6-pro`. Set `COP31_MODEL` to try another one (it must support tool calling on OpenRouter).

## Contributing

Want to help? Read [CONTRIBUTING.md](CONTRIBUTING.md) first. It's short.

## Folder layout

```
backend/    Python: Generator, Simulation engine, Data API, Agent, Backend API
data/       Real inputs (inputs/) and generated data (generated/, not in git)
frontend/   The screen (React)
docs/       How the app works
```
