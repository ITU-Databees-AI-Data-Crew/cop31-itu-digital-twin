// Right panel: the selected building, its system tabs, values for "now", a chart, and what-ifs.
// With nothing selected: every modelled building's headline value for the open tab.

import { api } from "../api";
import { useApp, useDataHour, useFetch } from "../state";
import { HEADLINE, LABEL, SHORT, SYSTEMS, SYSTEM_LABEL, value } from "../util";
import Chart from "./Chart";
import WhatIf, { Comparison } from "./WhatIf";

function Tabs() {
  const { state, dispatch } = useApp();
  return (
    <div className="tabs">
      {SYSTEMS.map((s) => (
        <button key={s} className={s === state.system ? "on" : ""} onClick={() => dispatch({ type: "system", system: s })}>
          {SYSTEM_LABEL[s]}
        </button>
      ))}
    </div>
  );
}

function NowValues({ buildingId, hour }) {
  const { state } = useApp();
  const now = useFetch(
    () => (hour ? api.now(buildingId, state.system, state.scenarioId) : null),
    [buildingId, state.system, hour, state.scenarioId, state.version],
  );
  if (now.error) return <div className="error">{now.error}</div>;
  if (!now.data) return <div className="muted">Loading…</div>;
  const entries = Object.entries(now.data.values).filter(([m]) => LABEL[m]);
  const headline = HEADLINE[state.system];
  return (
    <div>
      <div className="muted small">
        {state.system === "waste" ? "Today" : "This hour"}
        {state.scenarioId ? " · with the what-if shown" : ""}
      </div>
      <div className="cards">
        {entries.map(([m, v]) => (
          <div key={m} className={`card ${m === headline ? "card-main" : ""}`}>
            <div className="card-v">{value(v, now.data.units[m])}</div>
            <div className="card-l">{LABEL[m]}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function CampusOverview({ hour }) {
  const { state, dispatch } = useApp();
  const metric = HEADLINE[state.system];
  const rows = useFetch(() => (hour ? api.campusNow(state.system, state.scenarioId) : null), [state.system, hour, state.scenarioId, state.version]);
  return (
    <div className="panel-body">
      <h2>Campus</h2>
      <p className="muted">Three buildings are modelled. Pick one on the map or below.</p>
      {state.scenarioId && <Comparison id={state.scenarioId} />}
      <Tabs />
      <div className="muted small">{LABEL[metric]}, {state.system === "waste" ? "today" : "this hour"}</div>
      <ul className="overview">
        {(rows.data ?? []).map((r) => (
          <li key={r.building_id} onClick={() => dispatch({ type: "select", id: r.building_id })}>
            <span>{SHORT[r.building_id]}</span>
            <b>{value(r.values[metric], r.units[metric])}</b>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function BuildingPanel() {
  const { state, dispatch, meta } = useApp();
  const hour = useDataHour();
  const b = meta.buildings.find((x) => x.id === state.selected);
  if (!state.clock) return <div className="panel-body muted">Loading…</div>;
  if (!b) return <CampusOverview hour={hour} />;

  return (
    <div className="panel-body">
      <div className="bhead">
        <div>
          <h2>{b.name}</h2>
          <div className="muted small">
            {b.levels} floors{b.levels_underground ? ` + ${b.levels_underground} underground` : ""} ·{" "}
            {Math.round(b.gross_floor_area_m2).toLocaleString("en-US")} m² · up to {b.capacity.toLocaleString("en-US")} people
          </div>
        </div>
        <button className="x" title="Back to campus" onClick={() => dispatch({ type: "select", id: null })}>×</button>
      </div>
      <Tabs />
      <NowValues buildingId={b.id} hour={hour} />
      <Chart buildingId={b.id} hour={hour} />
      <WhatIf buildingId={b.id} />
    </div>
  );
}
