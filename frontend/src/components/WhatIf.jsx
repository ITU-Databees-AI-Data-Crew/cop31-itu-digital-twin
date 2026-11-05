// What-ifs in the building panel: the one being shown (before/after, Apply/Discard),
// the building's existing what-ifs, and typical ones to try.

import { useState } from "react";
import { api } from "../api";
import { useApp, useFetch } from "../state";
import { LABEL, SHORT, value } from "../util";

export function Comparison({ id }) {
  const { state, dispatch } = useApp();
  const cmp = useFetch(() => api.compare(id), [id, state.version]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const act = async (fn) => {
    setBusy(true);
    try {
      await fn();
      dispatch({ type: "bump" });
      setError(null);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const apply = () => act(() => api.apply(id));
  const discard = () => act(async () => { await api.discard(id); dispatch({ type: "scenario", id: null }); });

  if (cmp.error) return <div className="error">{cmp.error}</div>;
  if (!cmp.data) return <div className="muted">Comparing…</div>;
  const s = cmp.data.scenario;
  const rows = Object.values(cmp.data.systems).flatMap((sys) => Object.entries(sys));
  const shown = rows.filter(([m, r]) => r.change && LABEL[m]);

  return (
    <div className="whatif-shown">
      <div className="whatif-head">
        <div>
          <b>{s.name}</b>
          <div className="muted">
            <span className={`badge ${s.status}`}>{s.status === "draft" ? "Draft" : "Applied"}</span>
            {" "}made by {s.source === "agent" ? "the assistant" : "you"} · whole year · {cmp.data.building_id === "campus" ? "campus" : SHORT[cmp.data.building_id]}
          </div>
        </div>
        <button className="x" title="Hide" onClick={() => dispatch({ type: "scenario", id: null })}>×</button>
      </div>
      <table className="cmp">
        <thead><tr><th></th><th>Before</th><th>After</th><th>Change</th></tr></thead>
        <tbody>
          {shown.map(([m, r]) => (
            <tr key={m}>
              <td>{LABEL[m]}</td>
              <td>{value(r.before, r.unit)}</td>
              <td>{value(r.after, r.unit)}</td>
              <td className={(m === "recycling_rate" || m === "pv_generation_kwh" ? r.change > 0 : r.change < 0) ? "good" : "bad"}>
                {r.unit === "share" ? `${(r.change * 100).toFixed(1)} pts` : r.change_pct == null ? "new" : `${r.change_pct > 0 ? "+" : ""}${r.change_pct} %`}
              </td>
            </tr>
          ))}
          {shown.length === 0 && <tr><td colSpan={4} className="muted">No change.</td></tr>}
        </tbody>
      </table>
      <div className="row">
        {s.status === "draft" && <button className="primary" disabled={busy} onClick={apply}>Apply</button>}
        <button disabled={busy} onClick={discard}>{s.status === "draft" ? "Discard" : "Remove"}</button>
        {s.status === "draft" && <span className="muted">Apply makes it part of every number in the app.</span>}
      </div>
      {error && <div className="error">{error}</div>}
    </div>
  );
}

export default function WhatIf({ buildingId }) {
  const { state, dispatch } = useApp();
  const all = useFetch(() => api.scenarios(), [state.version]);
  const presets = useFetch(() => api.presets(buildingId), [buildingId]);
  const [error, setError] = useState(null);

  const mine = (all.data ?? []).filter((s) => s.interventions.some((iv) => iv.building_id === buildingId));
  const tryPreset = async (preset) => {
    try {
      const s = await api.createScenario({ preset, building_id: buildingId });
      dispatch({ type: "bump" });
      dispatch({ type: "scenario", id: s.id });
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  };

  return (
    <section className="whatif">
      <h3>What if…?</h3>
      {state.scenarioId && <Comparison id={state.scenarioId} />}
      {mine.length > 0 && (
        <ul className="scenarios">
          {mine.map((s) => (
            <li key={s.id} className={s.id === state.scenarioId ? "on" : ""} onClick={() => dispatch({ type: "scenario", id: s.id === state.scenarioId ? null : s.id })}>
              <span className={`badge ${s.status}`}>{s.status === "draft" ? "Draft" : "Applied"}</span> {s.name}
            </li>
          ))}
        </ul>
      )}
      <div className="presets">
        {(presets.data ?? []).map((p) => (
          <button key={p.preset} title={p.description} onClick={() => tryPreset(p.preset)}>
            {p.name}
            <small>{p.default_amount} {p.amount_unit}</small>
          </button>
        ))}
      </div>
      <p className="muted small">Typical amounts, adjustable through the chat. A what-if never changes the underlying data.</p>
      {error && <div className="error">{error}</div>}
    </section>
  );
}
