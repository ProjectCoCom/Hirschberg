/**
 * Summary: Vite bundler configuration.
 *
 * What it does: Configures development port, asset proxies, and bundling plugins for building dashboard assets.
 *
 * How it fits in: Used by pnpm build/dev commands.
 */



import react from "@vitejs/plugin-react";
import { resolve } from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@octogent/core": resolve(__dirname, "core/index.ts"),
    },
  },
  server: {
    port: 3000,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        ws: true,
      },
    },
  },
});
