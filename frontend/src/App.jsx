import BuildingPanel from "./components/BuildingPanel";
import Campus3D from "./components/Campus3D";
import Chat from "./components/Chat";
import ClockBar from "./components/ClockBar";
import { AppProvider, useApp } from "./state";

function Layout() {
  const { meta } = useApp();
  return (
    <div className="app">
      <header>
        <div className="brand">
          <b>İTÜ Campus Monitor</b>
          <span className="muted">Ayazağa · COP31 · DataBees</span>
        </div>
        <ClockBar />
      </header>
      {meta.error ? (
        <div className="center-note">
          Can't reach the backend: {meta.error}
          <br />
          Start it with <code>cd backend && uvicorn app.main:app --reload</code>
        </div>
      ) : (
        <main>
          <aside className="left"><Chat /></aside>
          <section className="middle"><Campus3D /></section>
          <aside className="right"><BuildingPanel /></aside>
        </main>
      )}
    </div>
  );
}

export default function App() {
  return (
    <AppProvider>
      <Layout />
    </AppProvider>
  );
}
