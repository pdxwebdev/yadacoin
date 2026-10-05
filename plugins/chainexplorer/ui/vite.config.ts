import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  base: "/chain-explorer/",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api-stats": api,
      "/explorer-search": api,
      "/explorer-get-balance": api,
      "/explorer-latest": api,
      "/get-mempool": api,
      "/get-blocks": api,
      "/get-latest-block": api,
      "/get-block": api,
      "/get-height": api,
      "/getheight": api,
      "/fee-estimate": api,
      "/convert-public-key-to-address": api,
      "/yadacoinstatic": api,
    },
  },
});
