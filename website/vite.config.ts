import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";
import fs from "fs";

function collectHtmlInputs() {
  const inputs: Record<string, string> = {
    main: path.resolve(import.meta.dirname, "index.html"),
  };

  const routeRoots = ["notice", "contact", "samples", "privacy"];
  for (const routeRoot of routeRoots) {
    const rootPath = path.resolve(import.meta.dirname, routeRoot);
    if (!fs.existsSync(rootPath)) continue;

    const rootIndex = path.join(rootPath, "index.html");
    if (fs.existsSync(rootIndex)) {
      inputs[routeRoot] = rootIndex;
    }

    for (const entry of fs.readdirSync(rootPath, { withFileTypes: true })) {
      if (!entry.isDirectory()) continue;
      const routeIndex = path.join(rootPath, entry.name, "index.html");
      if (fs.existsSync(routeIndex)) {
        inputs[`${routeRoot}-${entry.name}`] = routeIndex;
      }
    }
  }

  return inputs;
}

// https://vitejs.dev/config/
export default defineConfig(() => ({
  server: {
    host: process.env.VITE_EXPOSE_DEV === "1" ? "::" : "127.0.0.1",
    port: 8080,
    hmr: {
      overlay: false,
    },
  },
  build: {
    // Multi-page entries ensure each route has real, static meta tags for bots/share crawlers.
    rollupOptions: {
      input: collectHtmlInputs(),
      // Dozens of intentional HTML entries make Vite's timing heuristic noisy; bundle size is enforced separately.
      checks: { pluginTimings: false },
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
}));
