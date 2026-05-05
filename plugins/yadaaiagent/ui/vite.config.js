import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  base: "/ai-agent-auth/",
  build: {
    outDir: "../dist",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/ai-agent-auth/api": "http://localhost:8001",
      "/key-rotation": "http://localhost:8001",
    },
  },
});
