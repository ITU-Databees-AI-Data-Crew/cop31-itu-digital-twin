# The six parts of the app

The app is built from six parts. Each part has **one job**,
gets something **in**, gives something **out**, and has things it **never does**.
If you're changing one part, you only need to know the "in" and "out" of the parts next to it.

See [dataflow.md](dataflow.md) for the picture of how they connect.

| # | Part | One-line job | When it runs |
|---|---|---|---|
| 1 | Generator | Makes up a believable year of campus data | Once, before the app |
| 2 | Simulation engine | Keeps the clock and does what-ifs | While the app runs |
| 3 | Data API | Keeps all the numbers and answers questions about them | While the app runs |
| 4 | Agent | The helper you chat with | While the app runs |
| 5 | Backend API | The front desk between the screen and everything else | While the app runs |
| 6 | Frontend | The screen you look at and click | While the app runs |

---

## 1 · Generator

**Think of it as** a storyteller who writes the campus's diary for a whole year before anyone opens the app.
For every building and every hour, the diary says how much electricity, gas and water was used and how much waste came out.

**Why we need it:** we don't have real meter readings from İTÜ. So we *model* them from things that are real:
real building shapes and sizes, real Istanbul weather, real published numbers like "an office uses about X kWh per m² per year".
The data is made up, but it's made up carefully, and we can explain every number.

**In:**
- `campus.geojson`: building shapes from OpenStreetMap
- `buildings.csv`: our list of buildings (name, type, floor area, how many people, …)
- `weather.csv`: hourly Istanbul weather from Open-Meteo
- `factors.yaml`: rule-of-thumb numbers (energy per m², CO₂ per kWh, …), each with its source written next to it

**How it works, simply:**
- Colder day → more gas for heating. Hotter day → more electricity for cooling.
- More people in the building → more electricity, water and waste.
- People follow the calendar: busy during term, quiet in summer and on holidays, different during exams.
- A fixed random seed adds small natural-looking wiggles. Same seed = exactly the same data every time.

**Out:** one year of hourly numbers, written into the Data API's store.

**Never:** runs while the app is running. If you change it, you run it again and restart the app.

---

## 2 · Simulation engine

**Think of it as** a time machine with "what-if glasses".
- **Time machine:** it decides what time it is in the app ("now"). It can stand still or move forward on its own,
  so the dashboard looks live.
- **What-if glasses:** it shows how the numbers *would* look if something changed
  ("LED lights in building X", "solar panels on the roof").

**In:**
- Raw numbers from the Data API
- Requests like "what's building X's electricity now?" or "make a what-if: building X, −15% electricity"

**Out:**
- The current time
- Numbers for "now", with any active what-if applied
- Before/after comparisons

**How what-ifs work:** a what-if is a small note, like "building X · electricity · −15% · from 1 March".
The real numbers are never edited. When someone asks for numbers, the engine takes the real ones and applies the notes on top, right then.
Delete the note and you're back to the real numbers. Nothing breaks.

**What-if life cycle:** `draft` → (you press Apply) → `applied`, or → (you press Discard) → deleted.

**Never:** changes the year of numbers. Never talks to the screen directly.

> Design note: the Simulation engine sits *on top of* the Data API. Anyone who wants "now" or "what-if" numbers asks the
> Simulation engine. Anyone who wants plain history can ask the Data API directly. That way the what-if math lives in one place only.

---

## 3 · Data API

**Think of it as** a librarian with a very organised shelf. It keeps every number,
and when you ask a question it finds the answer. You never touch the shelf yourself.

**It has two halves:**
- **The store:** a single SQLite database file. Three tables:
  - `buildings`: one row per building (id, name, type, area, people, …)
  - `measurements`: one row per number: *which building · which system · which metric · which hour · value*
  - `scenarios`: the what-if notes from the Simulation engine
- **The questions** (Python functions in `campus.py`), for example:
  - "list all buildings"
  - "give me building X's gas use between these two dates"
  - "campus totals for this month"
  - "rank buildings by water use"

**In:** questions from the Simulation engine, the Backend API, and the Agent's tools.
**Out:** answers as plain data (lists and tables of numbers).

**Never:** decides what time it is, or does what-if math. That's the Simulation engine's job.

**Systems it keeps numbers for:**

| System | Examples of what's measured |
|---|---|
| Energy | electricity (kWh), natural gas (m³ / kWh) |
| Emissions | CO₂e (kg). Calculated from energy, not measured separately |
| Water | water used (m³) |
| Waste | recyclable, organic, residual, hazardous (kg) + recycling rate |
| Occupancy | how many people are in the building |

---

## 4 · Agent

**Think of it as** a smart helper sitting next to you who can look things up and point at the screen for you.

**In:**
- Your message
- What's on the screen right now (which building is selected, which tab is open, what time it is)
- The chat so far. Each chat session has its own memory.

**What it can do (its tools):**
- **Ask:** look up numbers through the Simulation engine and the Data API
- **Suggest:** create a *draft* what-if
- **Point:** ask the screen to do things, like select a building, open a tab, or colour the campus by a number
- **Search the web:** for things outside our data (prices, regulations, news)

**Out:** an answer in words + a list of **screen actions** for the screen to carry out.

**Never:**
- changes the year of numbers
- applies a what-if by itself (it can only make a draft. A person presses Apply)
- sees or touches the screen directly (it only gets told what's on it, and only sends requests back)

**Under the hood:** LangChain, a language model on OpenRouter, and our own agent loop.

---

## 5 · Backend API

**Think of it as** the front desk. The screen only ever talks to the front desk,
and the front desk passes each request to the right part.

**It has no ideas of its own.** Every route just hands the request on:

| Route (planned) | Hands it to |
|---|---|
| `GET /buildings` | Data API |
| `GET /buildings/{id}/systems/{system}` | Simulation engine (now / what-if) or Data API (history) |
| `GET /campus/summary` | Simulation engine |
| `GET /clock` | Simulation engine |
| `GET/POST /scenarios` | Simulation engine |
| `POST /chat` | Agent |

**Built with:** FastAPI (Python).
**For the demo** it also serves the finished screen files, so the whole app runs as **one program** on the laptop.

---

## 6 · Frontend

**Think of it as** the window you look through. Three panels side by side:

| Left | Middle | Right |
|---|---|---|
| **Chat** with the Agent | **3D campus**: click a building, colour buildings by a number | **Building panel**: details, system tabs, charts, what-if before/after |

**Shared screen state:** one small "memory" that all three panels read and write:
- selected building
- selected system tab
- active what-if
- current time (copied from the Simulation engine)

When you click a building in 3D, the right panel updates *because* this shared memory changed.
When the Agent says "select building X", the chat panel writes to the same memory, and the other panels follow.
This shared memory is also what gets sent to the Agent as "what's on the screen right now".

**In:** data from the Backend API, your clicks, the Agent's screen actions.
**Out:** requests to the Backend API, and pictures for your eyes.

**Built with:** React + react-three-fiber for 3D.
**While developing:** runs on its own dev server (it reloads on every save).
**For the demo:** built into plain files that the Backend API serves.

---

## The three agreements that let us work in parallel

If these three stay fixed, people can build different parts at the same time without waiting for each other:

1. **The shape of a measurement:** *building · system · metric · hour · value*. Connects the Generator to everything else.
2. **The Data API's questions:** the function names and what they return. Connects the data to the Simulation engine, the Backend API and the Agent.
3. **The shared screen state:** its exact fields. Connects the three panels and the Agent.

Until a part is ready, the parts next to it can use **fake versions** that follow the same agreement.
