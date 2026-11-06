// One metric over time for the selected building. With a what-if shown: current vs with what-if.

import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "../api";
import { useApp, useFetch } from "../state";
import { CHART_METRICS, LABEL, addHours, floorDay, fmt, parse, tick, value } from "../util";

const RANGES = {
  day: { label: "Today", make: (now) => [floorDay(now), addHours(floorDay(now), 24)], resolution: "hour" },
  week: { label: "7 days", make: (now) => [addHours(floorDay(now), -24 * 6), addHours(floorDay(now), 24)], resolution: "hour" },
  year: { label: "Year", resolution: "month" },
};

export default function Chart({ buildingId, hour }) {
  const { state, meta } = useApp();
  const options = CHART_METRICS[state.system];
  const [picked, setPicked] = useState({});
  const metric = options.includes(picked[state.system]) ? picked[state.system] : options[0];
  const unit = meta.metrics[metric]?.unit;
  const daily = meta.metrics[metric]?.resolution === "day"; // waste: one value per day, so no "Today" view
  const [picked_range, setRange] = useState("week");
  const range = daily && picked_range === "day" ? "week" : picked_range;

  const [start, end, resolution] = useMemo(() => {
    const r = RANGES[range];
    if (range === "year" || !hour) return [state.clock.range.start, fmt(addHours(parse(state.clock.range.end), 1)), "month"];
    const [s, e] = r.make(parse(hour));
    return [fmt(s), fmt(e), daily ? "day" : r.resolution];
    // the day only changes when the date changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [range, hour?.slice(0, 10), daily]);

  const res = useFetch(async () => {
    const base = await api.series(buildingId, metric, start, end, resolution);
    const what = state.scenarioId ? await api.series(buildingId, metric, start, end, resolution, state.scenarioId) : null;
    return base.points.map((p, i) => ({ time: p.time, current: p.value, whatif: what?.points[i]?.value ?? null }));
  }, [buildingId, metric, start, end, resolution, state.scenarioId, state.version]);

  const fmtV = (v) => value(v, unit);
  const nowTick = resolution === "hour" && hour;

  return (
    <div className="chart">
      <div className="chart-bar">
        <select value={metric} onChange={(e) => setPicked({ ...picked, [state.system]: e.target.value })}>
          {options.map((m) => <option key={m} value={m}>{LABEL[m]}</option>)}
        </select>
        <div className="seg">
          {Object.entries(RANGES).filter(([k]) => !(daily && k === "day")).map(([k, r]) => (
            <button key={k} className={k === range ? "on" : ""} onClick={() => setRange(k)}>{r.label}</button>
          ))}
        </div>
      </div>
      {res.error && <div className="error">{res.error}</div>}
      <ResponsiveContainer width="100%" height={210}>
        <LineChart data={res.data ?? []} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
          <CartesianGrid stroke="#263241" vertical={false} />
          <XAxis dataKey="time" tickFormatter={(t) => tick(t, resolution)} minTickGap={40} stroke="#8a97a6" fontSize={11} />
          <YAxis width={52} stroke="#8a97a6" fontSize={11} tickFormatter={(v) => (unit === "share" ? `${Math.round(v * 100)}%` : v.toLocaleString("en-US", { notation: "compact" }))} />
          <Tooltip contentStyle={{ background: "#16202b", border: "1px solid #2c3a4a" }} labelFormatter={(t) => tick(t, resolution === "month" ? "day" : resolution)} formatter={(v, name) => [fmtV(v), name]} />
          {nowTick && <ReferenceLine x={hour} stroke="#f5b942" strokeDasharray="3 3" label={{ value: "now", fill: "#f5b942", fontSize: 11 }} />}
          <Line type="monotone" dataKey="current" name="Current" stroke="#4ea8de" dot={false} strokeWidth={2} isAnimationActive={false} />
          {state.scenarioId && <Line type="monotone" dataKey="whatif" name="With what-if" stroke="#3fb27f" dot={false} strokeWidth={2} isAnimationActive={false} />}
          {state.scenarioId && <Legend wrapperStyle={{ fontSize: 12 }} />}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
