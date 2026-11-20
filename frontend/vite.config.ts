import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// En développement, on proxifie l'API vers le backend FastAPI (port 8000).
// En production, le backend sert le build (dossier dist) directement.
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
      "/healthz": {
        target: "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
});
