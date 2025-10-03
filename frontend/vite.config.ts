import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { resolve, join } from "node:path";

const repoRoot = existsSync(resolve(__dirname, "../app/web"))
  ? resolve(__dirname, "..")
  : resolve(__dirname, ".");

const outputDir = resolve(repoRoot, "app/web");
const fallbackSource = resolve(repoRoot, "app/web/fallback.png");

let fallbackBuffer: Buffer | null = null;
let reportedMissing = false;

function refreshFallbackBuffer(): void {
  try {
    fallbackBuffer = readFileSync(fallbackSource);
    reportedMissing = false;
  } catch (error) {
    if (!fallbackBuffer && !reportedMissing) {
      console.warn(
        `[vite] Unable to read fallback image at ${fallbackSource}:`,
        error
      );
      reportedMissing = true;
    }
  }
}

refreshFallbackBuffer();

function copyFallbackPlugin(): Plugin {
  return {
    name: "copy-shared-fallback",
    apply: "build",
    buildStart() {
      refreshFallbackBuffer();
    },
    closeBundle() {
      if (!fallbackBuffer) {
        return;
      }
      mkdirSync(outputDir, { recursive: true });
      writeFileSync(join(outputDir, "fallback.png"), fallbackBuffer);
    },
  };
}

export default defineConfig({
  build: {
    outDir: outputDir,
    emptyOutDir: true,
  },
  publicDir: "public",
  plugins: [react(), copyFallbackPlugin()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/collections": "http://localhost:8000",
      "/fileproxy": "http://localhost:8000",
    },
  },
});
