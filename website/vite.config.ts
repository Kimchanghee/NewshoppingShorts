import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import fs from "fs";

function collectHtmlInputs() {
  const inputs: Record<string, string> = {
    main: path.resolve(__dirname, "index.html"),
  };

  const routeRoots = ["notice", "contact"];
  for (const routeRoot of routeRoots) {
    const rootPath = path.resolve(__dirname, routeRoot);
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
    host: "::",
    port: 8080,
    hmr: {
      overlay: false,
    },
  },
  build: {
    // Multi-page entries ensure each route has real, static meta tags for bots/share crawlers.
    rollupOptions: {
      input: collectHtmlInputs(),
    },
  },
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
}));
