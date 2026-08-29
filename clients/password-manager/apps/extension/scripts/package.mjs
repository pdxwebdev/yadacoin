import { existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { execSync } from "node:child_process";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const out = join(root, "yada-password-extension.zip");

if (!existsSync(dist)) {
  throw new Error("dist/ missing; run npm run build first");
}

execSync(`rm -f "${out}" && cd "${dist}" && zip -r "${out}" . -x "*.map"`, {
  stdio: "inherit",
});
console.log("packed", out);
