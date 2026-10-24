import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "path";

// Builds only the client app (no admin panel) for the Android project.
export default defineConfig({
  root: resolve(__dirname, "mobile"),
  base: "./",
  envDir: __dirname,
  plugins: [react()],
  resolve: {
    alias: {
      "@": resolve(__dirname, "src"),
    },
  },
  build: {
    outDir: resolve(__dirname, "dist-app"),
    emptyOutDir: true,
  },
  server: {
    port: 5174,
  },
});
