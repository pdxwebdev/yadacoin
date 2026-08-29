import * as esbuild from "esbuild";
import { cpSync, mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const dist = join(root, "dist");
const watch = process.argv.includes("--watch");

mkdirSync(dist, { recursive: true });

const sharedUiCss = join(root, "../../packages/shared-ui/src/styles/base.css");

function copyStatic() {
  cpSync(join(root, "public"), dist, { recursive: true });
  if (existsSync(sharedUiCss)) {
    mkdirSync(join(dist, "styles"), { recursive: true });
    cpSync(sharedUiCss, join(dist, "styles", "base.css"));
  }
  const manifest = JSON.parse(readFileSync(join(root, "manifest.json"), "utf8"));
  if (process.env.EXTENSION_VERSION) {
    manifest.version = process.env.EXTENSION_VERSION;
  }
  writeFileSync(join(dist, "manifest.json"), JSON.stringify(manifest, null, 2));
}

const common = {
  bundle: true,
  target: ["chrome110", "firefox110"],
  sourcemap: true,
  logLevel: "info",
};

async function buildOnce() {
  copyStatic();
  await Promise.all([
    esbuild.build({
      ...common,
      entryPoints: {
        background: join(root, "src/background/service-worker.ts"),
        popup: join(root, "src/popup/popup.ts"),
        options: join(root, "src/options/options.ts"),
      },
      outdir: dist,
      format: "esm",
    }),
    esbuild.build({
      ...common,
      entryPoints: [join(root, "src/content/content.ts")],
      outfile: join(dist, "content.js"),
      format: "iife",
    }),
  ]);
  console.log("extension build →", dist);
}

if (watch) {
  copyStatic();
  const ctxMain = await esbuild.context({
    ...common,
    entryPoints: {
      background: join(root, "src/background/service-worker.ts"),
      popup: join(root, "src/popup/popup.ts"),
      options: join(root, "src/options/options.ts"),
    },
    outdir: dist,
    format: "esm",
  });
  const ctxContent = await esbuild.context({
    ...common,
    entryPoints: [join(root, "src/content/content.ts")],
    outfile: join(dist, "content.js"),
    format: "iife",
  });
  await Promise.all([ctxMain.watch(), ctxContent.watch()]);
  console.log("watching extension…");
} else {
  await buildOnce();
}
