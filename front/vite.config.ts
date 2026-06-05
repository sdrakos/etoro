/// <reference types="vitest" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/screener": "http://localhost:8765",
      "/portfolio": "http://localhost:8765",
      "/charts": "http://localhost:8765",
      "/ws": { target: "ws://localhost:8765", ws: true },
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/__tests__/setup.ts"],
    exclude: ["node_modules", "dist", "e2e/**"],
    fakeTimers: {
      toFake: ["setTimeout", "clearTimeout", "setInterval", "clearInterval", "Date"],
      shouldAdvanceTime: true,
      advanceTimeDelta: 20,
    },
    coverage: {
      reporter: ["text", "html"],
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/__tests__/**", "src/main.tsx"],
    },
  },
});
