// The shared screen state: one small memory all three panels read and write.
// It is also what the chat sends to the agent as "what's on the screen right now".

import { createContext, useContext, useEffect, useReducer, useState } from "react";
import { api } from "./api";
import { floorHour, fmt, simNow } from "./util";

const Ctx = createContext(null);

const initial = {
  selected: null, // building id
  system: "energy", // open tab
  scenarioId: null, // what-if being shown
  colorBy: null, // system the 3D campus is coloured by
  clock: null, // server clock state
  clockAt: 0, // Date.now() when the clock state arrived
  version: 0, // bumped when what-ifs change, so everything refetches
};

function reducer(s, a) {
  switch (a.type) {
    case "select":
      return { ...s, selected: a.id };
    case "system":
      return { ...s, system: a.system };
    case "scenario":
      return { ...s, scenarioId: a.id };
    case "colorBy":
      return { ...s, colorBy: a.system };
    case "clock":
      return { ...s, clock: a.clock, clockAt: Date.now() };
    case "bump":
      return { ...s, version: s.version + 1 };
    default:
      throw new Error(a.type);
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(reducer, initial);
  const [meta, setMeta] = useState({ buildings: [], metrics: {}, health: null, error: null });

  useEffect(() => {
    Promise.all([api.buildings(), api.metrics(), api.health(), api.clock()])
      .then(([buildings, metrics, health, clock]) => {
        setMeta({ buildings, metrics: Object.fromEntries(metrics.map((m) => [m.metric, m])), health, error: null });
        dispatch({ type: "clock", clock });
      })
      .catch((e) => setMeta((m) => ({ ...m, error: e.message })));
  }, []);

  return <Ctx.Provider value={{ state, dispatch, meta }}>{children}</Ctx.Provider>;
}

export const useApp = () => useContext(Ctx);

// Clock controls; the server clock is the source of truth.
export async function controlClock(dispatch, body) {
  dispatch({ type: "clock", clock: await api.clockControl(body) });
}

// Carry out a screen action the agent asked for.
export async function runUiAction(dispatch, action) {
  const a = action.args;
  switch (action.type) {
    case "SelectBuilding":
      return dispatch({ type: "select", id: a.building_id });
    case "OpenSystem":
      return dispatch({ type: "system", system: a.system });
    case "ColorCampus":
      return dispatch({ type: "colorBy", system: a.system });
    case "ShowScenario":
      dispatch({ type: "bump" });
      return dispatch({ type: "scenario", id: a.scenario_id });
    case "SetTime":
      return controlClock(dispatch, { action: "set", time: String(a.time).slice(0, 16) });
  }
}

// The current app time, re-rendering 4x a second while the clock plays.
export function useSimTime() {
  const { state } = useApp();
  const [, force] = useState(0);
  useEffect(() => {
    if (!state.clock?.playing) return;
    const t = setInterval(() => force((x) => x + 1), 250);
    return () => clearInterval(t);
  }, [state.clock]);
  return simNow(state.clock, state.clockAt);
}

// The current app hour as a string, changing at most once a second (for data fetches).
export function useDataHour() {
  const { state } = useApp();
  const [hour, setHour] = useState(null);
  useEffect(() => {
    if (!state.clock) return;
    const update = () => setHour(fmt(floorHour(simNow(state.clock, state.clockAt))));
    update();
    if (!state.clock.playing) return;
    const t = setInterval(update, 1000);
    return () => clearInterval(t);
  }, [state.clock, state.clockAt]);
  return hour;
}

// Fetch when deps change; keeps the previous data while reloading (no flicker).
export function useFetch(fn, deps) {
  const [s, setS] = useState({ data: null, error: null, loading: true });
  useEffect(() => {
    let live = true;
    setS((p) => ({ ...p, loading: true }));
    Promise.resolve()
      .then(fn)
      .then(
        (data) => live && setS({ data, error: null, loading: false }),
        (e) => live && setS((p) => ({ ...p, error: e.message, loading: false })),
      );
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return s;
}
