import * as esbuild from "esbuild";
import {
  cpSync,
  mkdirSync,
  existsSync,
  rmSync,
} from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const root = join(__dirname, "..");
const www = join(root, "www");
mkdirSync(join(www, "js"), { recursive: true });
mkdirSync(join(www, "styles"), { recursive: true });

const css = join(root, "../../packages/shared-ui/src/styles/base.css");
if (existsSync(css)) cpSync(css, join(www, "styles/base.css"));

await esbuild.build({
  entryPoints: [join(root, "src/main.ts")],
  bundle: true,
  outfile: join(www, "js/main.js"),
  format: "esm",
  target: ["es2022"],
  sourcemap: true,
  logLevel: "info",
});

// Publish into node plugin so phones can open http://node/password-rotation/mobile
const pluginStatic = join(
  root,
  "../../../../plugins/passwordrotation/static/mobile"
);
try {
  if (existsSync(pluginStatic)) rmSync(pluginStatic, { recursive: true, force: true });
  mkdirSync(pluginStatic, { recursive: true });
  cpSync(www, pluginStatic, { recursive: true });
  console.log("published → plugins/passwordrotation/static/mobile");
} catch (e) {
  console.warn("plugin static publish skipped:", e.message);
}

console.log("mobile www build ok");
