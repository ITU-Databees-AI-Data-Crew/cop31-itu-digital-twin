# How data moves through the app

This page shows where every number in the app comes from and where it goes.
If you only read one page, read this one.

## The big picture

```mermaid
flowchart LR
  subgraph BEFORE["① Before the app starts (run once)"]
    SRC["Real-world inputs<br/>campus map · weather · building list · factors"]
    GEN["Generator"]
  end

  subgraph BACKEND["② Backend (Python, on the laptop)"]
    DATA["Data API<br/>keeps all numbers + answers questions"]
    SIM["Simulation engine<br/>clock + what-ifs"]
    AGENT["Agent<br/>the helper you chat with"]
    API["Backend API<br/>the front desk"]
  end

  subgraph FRONTEND["③ Frontend (in the browser)"]
    UI["Screen<br/>chat · 3D campus · building panel"]
  end

  YOU(("You"))

  SRC --> GEN
  GEN -- "one year of hourly numbers" --> DATA
  DATA -- "raw numbers" --> SIM
  SIM -- "saves what-ifs" --> DATA
  SIM -- "numbers for 'now' and what-ifs" --> API
  DATA -- "old numbers (history)" --> API
  AGENT -- "asks questions (tools)" --> SIM
  AGENT -- "asks questions (tools)" --> DATA
  API -- "your message + what's on screen" --> AGENT
  AGENT -- "answer + screen actions" --> API
  API <-- "web requests" --> UI
  YOU <--> UI
```

There are three zones, and you read them from left to right:

1. **Before the app starts.** The Generator makes up a believable year of data for the campus. It runs once and then stops.
2. **Backend.** This is where the numbers live and where the thinking happens.
3. **Frontend.** What you see and click.

**The one rule that keeps it simple:** the screen never talks to the data directly.
Everything goes through the Backend API, like ordering at a counter instead of walking into the kitchen.

## What happens when…

### …you open the app

1. The screen asks the Backend API: "Which buildings are there, and what time is it?"
2. The Backend API asks the Data API for the building list and asks the Simulation engine for the time.
3. The screen draws the 3D campus and shows the clock.

### …you click a building

1. The screen says: "Building X was selected."
2. It asks the Backend API: "What are building X's numbers right now?"
3. The Simulation engine takes building X's raw numbers from the Data API, picks the ones for "now",
   and applies any what-if that's switched on.
4. The building panel on the right shows the result.

### …you ask the Agent a question

```mermaid
sequenceDiagram
  participant You
  participant Screen
  participant API as Backend API
  participant Agent
  participant Sim as Simulation engine
  participant Data as Data API

  You->>Screen: "Which building wastes the most gas?"
  Screen->>API: message + what's on screen now
  API->>Agent: message + what's on screen now
  Agent->>Sim: tool: rank buildings by gas, now
  Sim->>Data: give me the raw gas numbers
  Data-->>Sim: numbers
  Sim-->>Agent: ranked list
  Agent-->>API: answer + "select building X"
  API-->>Screen: answer + "select building X"
  Screen-->>You: shows the answer AND jumps to building X
```

The Agent can't see the screen. The screen tells it what's showing (which building, which tab, what time).
The Agent also can't touch the screen. It sends back **screen actions** ("select building X"), and the screen carries them out.

### …you try a what-if

Example: "What if Building X switched to LED lights?"

1. The Agent (or you, with a button) asks the Simulation engine to make a **draft what-if**.
2. The Simulation engine saves the draft in the Data API. **The real numbers are never changed.**
   The what-if is stored as a separate note: "building X, electricity, −15%".
3. The building panel shows **before vs after** side by side.
4. You press **Apply** to keep it, or **Discard** to throw it away.

## Who is allowed to change what

| Thing | Who can change it |
|---|---|
| The year of numbers | Only the Generator, before the app starts |
| What-ifs | The Simulation engine (when you or the Agent ask) |
| The clock | Only the Simulation engine |
| What's selected on screen | Only the screen (the Agent can *ask* it to) |
