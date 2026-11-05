# Frontend

The screen: chat (left), 3D campus (middle), building panel (right). React + Vite,
react-three-fiber for 3D, Recharts for charts. It only talks to the Backend API (`/api`).

```bash
npm install
npm run dev      # http://localhost:5173, forwards /api to the backend on :8000
npm run build    # writes dist/, which the backend serves at http://localhost:8000
```

| File | Part |
|---|---|
| `src/api.js` | every backend call, incl. the streamed chat |
| `src/state.jsx` | shared screen state (selected building, tab, what-if, clock) and how agent screen actions change it |
| `src/components/Campus3D.jsx` | OSM footprints extruded by floor count; the 3 modelled buildings are clickable |
| `src/components/BuildingPanel.jsx`, `Chart.jsx`, `WhatIf.jsx` | right panel |
| `src/components/Chat.jsx` | left panel |
| `src/components/ClockBar.jsx` | app clock |
