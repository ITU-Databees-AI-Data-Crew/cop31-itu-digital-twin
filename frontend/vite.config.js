import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev: the backend runs on :8000 (uvicorn app.main:app --reload); /api is forwarded to it.
// Demo: `npm run build` and the backend serves frontend/dist itself.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": "http://127.0.0.1:8000" } },
});
