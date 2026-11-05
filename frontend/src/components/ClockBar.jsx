// The app clock: what "now" means everywhere on screen.

import { useState } from "react";
import { controlClock, useApp, useSimTime } from "../state";
import { fmt, prettyTime } from "../util";

const SPEEDS = [
  [1, "1 hour / s"],
  [6, "6 hours / s"],
  [24, "1 day / s"],
  [168, "1 week / s"],
];

export default function ClockBar() {
  const { state, dispatch } = useApp();
  const now = useSimTime();
  const [error, setError] = useState(null);
  const clock = state.clock;
  if (!clock || !now) return <div className="clock">…</div>;

  const run = (body) => controlClock(dispatch, body).then(() => setError(null), (e) => setError(e.message));

  return (
    <div className="clock">
      <span className="clock-time" title="App time (simulated)">🕒 {prettyTime(now)}</span>
      <button onClick={() => run({ action: clock.playing ? "pause" : "play" })}>{clock.playing ? "⏸ Pause" : "▶ Play"}</button>
      <select value={clock.speed_hours_per_second} onChange={(e) => run({ action: "play", speed: Number(e.target.value) })}>
        {SPEEDS.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
      </select>
      <input
        type="datetime-local"
        step="3600"
        min={clock.range.start}
        max={clock.range.end}
        value={fmt(now)}
        onChange={(e) => e.target.value && run({ action: "set", time: e.target.value })}
      />
      {error && <span className="error">{error}</span>}
    </div>
  );
}
