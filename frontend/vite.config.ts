import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve, join } from "node:path";

const repoRoot = existsSync(resolve(__dirname, "../app/web"))
  ? resolve(__dirname, "..")
  : resolve(__dirname, ".");

const outputDir = resolve(repoRoot, "app/web");
const spaAssetsDir = "spa-assets";

type StaticFile = {
  source: string;
  destName: string;
};

const staticFiles: StaticFile[] = [
  { source: resolve(repoRoot, "app/web/fallback.png"), destName: "fallback.png" },
];

const staticBuffers = new Map<string, Buffer>();
const reportedMissing = new Set<string>();

function refreshStaticBuffers(): void {
  for (const file of staticFiles) {
    try {
      const buffer = readFileSync(file.source);
      staticBuffers.set(file.destName, buffer);
      reportedMissing.delete(file.destName);
    } catch (error) {
      if (!staticBuffers.has(file.destName) && !reportedMissing.has(file.destName)) {
        console.warn(
          `[vite] Unable to read static asset at ${file.source}:`,
          error
        );
        reportedMissing.add(file.destName);
      }
    }
  }
}

refreshStaticBuffers();

function copySharedStaticPlugin(): Plugin {
  return {
    name: "copy-shared-static",
    apply: "build",
    buildStart() {
      refreshStaticBuffers();
    },
    closeBundle() {
      if (!staticBuffers.size) {
        return;
      }
      mkdirSync(outputDir, { recursive: true });
      for (const file of staticFiles) {
        const buffer = staticBuffers.get(file.destName);
        if (!buffer) continue;
        writeFileSync(join(outputDir, file.destName), buffer);
      }
    },
  };
}

export default defineConfig({
  build: {
    outDir: outputDir,
    emptyOutDir: true,
    assetsDir: spaAssetsDir,
  },
  publicDir: "public",
  plugins: [react(), copySharedStaticPlugin()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/auth": "http://localhost:8000",
      "/collections": "http://localhost:8000",
      "/fileproxy": "http://localhost:8000",
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/setupTests.js",
  },
});
