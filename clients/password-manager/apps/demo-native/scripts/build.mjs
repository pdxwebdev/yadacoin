import * as esbuild from "esbuild";
import { cpSync, mkdirSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const www = join(root, "www");
mkdirSync(join(www, "js"), { recursive: true });
mkdirSync(join(www, "styles"), { recursive: true });

const baseCss = join(root, "../../packages/shared-ui/src/styles/base.css");
if (existsSync(baseCss)) cpSync(baseCss, join(www, "styles/base.css"));

await esbuild.build({
  entryPoints: [join(root, "src/main.ts")],
  bundle: true,
  outfile: join(www, "js/main.js"),
  format: "esm",
  target: ["es2022"],
  sourcemap: true,
  logLevel: "info",
});
console.log("demo-native www build ok");
