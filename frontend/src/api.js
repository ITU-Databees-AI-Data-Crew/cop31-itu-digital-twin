// Every call to the Backend API. The screen never talks to anything else.

const BASE = "/api";

async function req(path, opts = {}) {
  const r = await fetch(BASE + path, { headers: { "Content-Type": "application/json" }, ...opts });
  if (r.status === 204) return null;
  const body = await r.json().catch(() => null);
  if (!r.ok) {
    const d = body?.detail;
    throw new Error(typeof d === "string" ? d : d ? JSON.stringify(d) : r.statusText);
  }
  return body;
}

const qs = (params) => {
  const s = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== ""));
  return s.toString() ? "?" + s : "";
};
const post = (body) => ({ method: "POST", body: JSON.stringify(body ?? {}) });

export const api = {
  health: () => req("/health"),
  buildings: () => req("/buildings"),
  metrics: () => req("/metrics"),
  geojson: () => req("/campus/geojson"),
  clock: () => req("/clock"),
  clockControl: (body) => req("/clock", post(body)),
  now: (id, system, scenario_id) => req(`/buildings/${id}/now` + qs({ system, scenario_id })),
  campusNow: (system, scenario_id) => req("/campus/now" + qs({ system, scenario_id })),
  series: (id, metric, start, end, resolution, scenario_id) =>
    req(`/buildings/${id}/series` + qs({ metric, start, end, resolution, scenario_id })),
  presets: (building_id) => req("/presets" + qs({ building_id })),
  scenarios: () => req("/scenarios"),
  createScenario: (body) => req("/scenarios", post(body)),
  compare: (id) => req(`/scenarios/${id}/compare`),
  apply: (id) => req(`/scenarios/${id}/apply`, { method: "POST" }),
  discard: (id) => req(`/scenarios/${id}`, { method: "DELETE" }),
  resetChat: (sid) => req(`/chat/${sid}/reset`, { method: "POST" }),
};

// One streamed chat turn. Calls onEvent for each event: text | tool | ui_action | done | error.
export async function streamChat(body, onEvent, signal) {
  const r = await fetch(BASE + "/chat/stream", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!r.ok) {
    const b = await r.json().catch(() => null);
    throw new Error(typeof b?.detail === "string" ? b.detail : r.statusText);
  }
  const reader = r.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) onEvent(JSON.parse(line));
    }
  }
  if (buf.trim()) onEvent(JSON.parse(buf));
}
