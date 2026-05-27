import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";
import { execSync } from "node:child_process";
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
  { source: resolve(repoRoot, "app/web/movie.html"), destName: "movie.html" },
];

const staticBuffers = new Map<string, Buffer>();
const reportedMissing = new Set<string>();

function normalizeBranchName(value: string | undefined): string {
  const text = String(value || "").trim();
  if (!text) return "dev";
  return (
    text
      .replace(/^refs\/heads\//, "")
      .replace(/^origin\//, "")
      .replace(/[^0-9A-Za-z._-]+/g, "-")
      .replace(/^-+|-+$/g, "") || "dev"
  );
}

function readGitHeadBranch(): string {
  try {
    const headPath = resolve(repoRoot, ".git/HEAD");
    const head = readFileSync(headPath, "utf8").trim();
    const refPrefix = "ref: refs/heads/";
    if (head.startsWith(refPrefix)) {
      return normalizeBranchName(head.slice(refPrefix.length));
    }
  } catch {
    // Fall through to git executable or default.
  }
  return "";
}

function resolveKamBranch(): string {
  const envBranch =
    process.env.VITE_KAM_BRANCH ||
    process.env.VITE_GIT_BRANCH ||
    process.env.KAM_BRANCH ||
    process.env.GITHUB_REF_NAME ||
    process.env.BRANCH_NAME;
  if (envBranch) {
    return normalizeBranchName(envBranch);
  }

  const gitHeadBranch = readGitHeadBranch();
  if (gitHeadBranch) {
    return gitHeadBranch;
  }

  try {
    return normalizeBranchName(
      execSync("git rev-parse --abbrev-ref HEAD", {
        cwd: repoRoot,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "ignore"],
      })
    );
  } catch {
    return "dev";
  }
}

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
  define: {
    __KAM_BRANCH__: JSON.stringify(resolveKamBranch()),
  },
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
