// Left panel: chat with the agent. Answers stream in; screen actions happen while it writes.

import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, streamChat } from "../api";
import { runUiAction, useApp, useSimTime } from "../state";
import { SHORT, SYSTEM_LABEL, fmt } from "../util";

const newSession = () => Math.random().toString(36).slice(2, 10);

const TOOL_LABEL = {
  get_clock: "Checking the app time",
  list_buildings: "Looking up the buildings",
  list_metrics: "Looking up the metrics",
  get_now: "Reading current values",
  get_totals: "Adding up totals",
  get_series: "Reading a time series",
  rank_buildings: "Ranking the buildings",
  get_weather: "Checking the weather",
  list_presets: "Looking at typical what-ifs",
  create_whatif: "Building a what-if",
  compare_whatif: "Comparing before and after",
  list_whatifs: "Looking at existing what-ifs",
  web_search: "Searching the web",
};

function actionLabel({ type, args }) {
  switch (type) {
    case "SelectBuilding": return `Selected ${SHORT[args.building_id] ?? args.building_id}`;
    case "OpenSystem": return `Opened ${SYSTEM_LABEL[args.system]}`;
    case "ColorCampus": return args.system ? `Coloured the campus by ${SYSTEM_LABEL[args.system]}` : "Cleared the colours";
    case "ShowScenario": return "Showing the what-if";
    case "SetTime": return `Moved the clock to ${String(args.time).slice(0, 16).replace("T", " ")}`;
    default: return type;
  }
}

const SUGGESTIONS = [
  "Which building uses the most gas per m² this winter?",
  "What's going on in MED-A right now?",
  "What if the library got LED lighting and rooftop solar?",
  "Show me the library during the January exam weeks.",
];

export default function Chat() {
  const { state, dispatch, meta } = useApp();
  const now = useSimTime();
  const [session, setSession] = useState(newSession);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef(null);
  const end = useRef(null);

  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [messages]);

  const update = (fn) => setMessages((ms) => [...ms.slice(0, -1), fn(ms[ms.length - 1])]);

  const send = async (text) => {
    text = text.trim();
    if (!text || busy) return;
    setInput("");
    setBusy(true);
    setMessages((ms) => [...ms, { role: "user", text }, { role: "assistant", text: "", steps: [], pending: true }]);
    const ui_state = {
      selected_building: state.selected,
      system: state.selected ? state.system : null,
      scenario_id: state.scenarioId,
      sim_time: fmt(now),
    };
    abort.current = new AbortController();
    try {
      await streamChat({ session_id: session, message: text, ui_state }, (e) => {
        if (e.type === "text") update((m) => ({ ...m, text: m.text + e.delta }));
        else if (e.type === "tool") update((m) => ({ ...m, steps: [...m.steps, { kind: "tool", label: TOOL_LABEL[e.name] ?? e.name }] }));
        else if (e.type === "ui_action") {
          runUiAction(dispatch, e.action);
          update((m) => ({ ...m, steps: [...m.steps, { kind: "action", label: actionLabel(e.action) }] }));
        } else if (e.type === "error") update((m) => ({ ...m, error: e.detail }));
        else if (e.type === "done") {
          dispatch({ type: "bump" }); // the agent may have made a what-if
          update((m) => ({ ...m, text: e.reply || m.text }));
        }
      }, abort.current.signal);
    } catch (err) {
      if (err.name !== "AbortError") update((m) => ({ ...m, error: err.message }));
    } finally {
      update((m) => ({ ...m, pending: false }));
      setBusy(false);
    }
  };

  const reset = () => {
    abort.current?.abort();
    api.resetChat(session).catch(() => {});
    setSession(newSession());
    setMessages([]);
  };

  const ready = meta.health?.agent_ready;

  return (
    <div className="chat">
      <div className="chat-head">
        <b>Assistant</b>
        <button className="link" onClick={reset} disabled={!messages.length}>New chat</button>
      </div>
      <div className="chat-log">
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Ask about the campus's energy, emissions, water, waste or occupancy, or try a what-if. The assistant can also move things on screen for you.</p>
            {SUGGESTIONS.map((s) => (
              <button key={s} className="suggest" onClick={() => send(s)} disabled={!ready}>{s}</button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.steps?.length > 0 && (
              <div className="steps">
                {m.steps.map((s, j) => <span key={j} className={`step ${s.kind}`}>{s.kind === "action" ? "↳ " : "· "}{s.label}</span>)}
              </div>
            )}
            {m.role === "assistant" ? (
              <div className="md">{m.text ? <Markdown remarkPlugins={[remarkGfm]}>{m.text}</Markdown> : m.pending && <span className="dots">thinking</span>}</div>
            ) : (
              <div>{m.text}</div>
            )}
            {m.error && <div className="error">Something went wrong: {m.error}</div>}
          </div>
        ))}
        <div ref={end} />
      </div>
      {meta.health && !ready && <div className="error small">The assistant needs OPENROUTER_API_KEY in backend/.env.</div>}
      <form className="chat-input" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <textarea
          value={input}
          rows={2}
          placeholder={state.selected ? `Ask about ${SHORT[state.selected]}…` : "Ask anything about the campus…"}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); } }}
          disabled={!ready}
        />
        {busy ? (
          <button type="button" onClick={() => abort.current?.abort()}>Stop</button>
        ) : (
          <button type="submit" className="primary" disabled={!input.trim() || !ready}>Send</button>
        )}
      </form>
      <div className="muted small foot">Numbers are modelled: real building sizes, weather and calendar; synthetic usage.</div>
    </div>
  );
}
