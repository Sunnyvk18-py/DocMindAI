import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Lock project root to this folder so stray CLI args never confuse Vite.
const __dirname = path.dirname(fileURLToPath(import.meta.url));

// API: http://127.0.0.1:8000 (FastAPI must allow CORS for this dev origin).
export default defineConfig({
  root: __dirname,
  appType: "spa",
  plugins: [react()],
  server: {
    port: 5173,
    // Listen on all interfaces; use the URL Vite prints (localhost or 127.0.0.1).
    host: true,
    strictPort: false,
  },
});
