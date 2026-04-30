import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite dev server default: http://localhost:5173
// API calls go directly to http://127.0.0.1:8000 (CORS must be enabled on FastAPI).
export default defineConfig({
  plugins: [react()],
});
