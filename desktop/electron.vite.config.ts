import { defineConfig, externalizeDepsPlugin } from "electron-vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  main: {
    plugins: [externalizeDepsPlugin()],
    build: {
      rollupOptions: {
        input: "src/main.ts"
      }
    }
  },
  preload: {
    build: {
      rollupOptions: {
        input: "src/preload.ts"
      }
    }
  },
  renderer: {
    plugins: [react()],
    server: {
      host: "127.0.0.1",
      port: 5173
    }
  }
});
