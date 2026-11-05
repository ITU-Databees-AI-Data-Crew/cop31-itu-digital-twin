// Times from the backend are local Istanbul time without a zone ("2025-12-10T12:00").
// We keep them as Date objects in UTC so the browser's own time zone never shifts them.

const pad = (n) => String(n).padStart(2, "0");
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

export const parse = (s) => new Date((s.length === 16 ? s + ":00" : s.slice(0, 19)) + "Z");
export const fmt = (d) => d.toISOString().slice(0, 16);
export const addHours = (d, h) => new Date(d.getTime() + h * 3600e3);
export const floorHour = (d) => new Date(Math.floor(d.getTime() / 3600e3) * 3600e3);
export const floorDay = (d) => new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));

export const prettyTime = (d) =>
  `${DAYS[d.getUTCDay()]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()} · ${pad(d.getUTCHours())}:00`;

export function tick(time, resolution) {
  const d = parse(time);
  if (resolution === "month") return MONTHS[d.getUTCMonth()];
  if (resolution === "day") return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  return `${DAYS[d.getUTCDay()]} ${pad(d.getUTCHours())}:00`;
}

// The app clock, computed locally from the server's anchor so it animates without polling.
export function simNow(clock, receivedAt) {
  if (!clock) return null;
  let t = parse(clock.anchor.sim_time);
  if (clock.playing) {
    t = addHours(t, ((Date.now() - receivedAt) / 1000) * clock.speed_hours_per_second);
    const start = parse(clock.range.start).getTime();
    const span = parse(clock.range.end).getTime() + 3600e3 - start;
    t = new Date(start + ((((t.getTime() - start) % span) + span) % span));
  }
  return t;
}

export const SHORT = { bbf: "BBF", meda: "MED-A", lib: "Library" };

export const SYSTEMS = ["energy", "emissions", "water", "waste", "occupancy"];
export const SYSTEM_LABEL = { energy: "Energy", emissions: "Emissions", water: "Water", waste: "Waste", occupancy: "Occupancy" };

// The one number per system used to colour the 3D campus.
export const HEADLINE = {
  energy: "electricity_grid_kwh",
  emissions: "co2e_kg",
  water: "water_m3",
  waste: "recycling_rate",
  occupancy: "people",
};

// Metrics you can chart in each tab (first = default).
export const CHART_METRICS = {
  energy: ["electricity_kwh", "electricity_grid_kwh", "pv_generation_kwh", "natural_gas_kwh",
    "electricity_lighting_kwh", "electricity_plug_kwh", "electricity_hvac_kwh"],
  emissions: ["co2e_kg", "co2e_electricity_kg", "co2e_gas_kg"],
  water: ["water_m3"],
  waste: ["recycling_rate", "residual_kg", "recyclable_kg", "organic_kg", "hazardous_kg"],
  occupancy: ["people"],
};

export const LABEL = {
  people: "People inside",
  electricity_kwh: "Electricity used",
  electricity_grid_kwh: "Electricity from the grid",
  pv_generation_kwh: "Rooftop solar",
  electricity_lighting_kwh: "Lighting",
  electricity_plug_kwh: "Plug loads",
  electricity_hvac_kwh: "Fans & cooling",
  natural_gas_kwh: "Gas (heating)",
  co2e_kg: "CO₂e total",
  co2e_electricity_kg: "CO₂e from electricity",
  co2e_gas_kg: "CO₂e from gas",
  water_m3: "Water",
  recyclable_kg: "Recyclable",
  organic_kg: "Organic",
  residual_kg: "Residual",
  hazardous_kg: "Hazardous",
  recycling_rate: "Recycling rate",
};

export function value(v, unit) {
  if (v == null) return "–";
  if (unit === "share") return `${(v * 100).toFixed(1)} %`;
  const digits = Math.abs(v) >= 100 ? 0 : Math.abs(v) >= 10 ? 1 : 2;
  return `${v.toLocaleString("en-US", { maximumFractionDigits: digits })} ${unit}`;
}
