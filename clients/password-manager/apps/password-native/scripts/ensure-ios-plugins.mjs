import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const cfgPath = join(root, "ios/App/App/capacitor.config.json");
const extra = "CallerIdentityPlugin";
if (!existsSync(cfgPath)) process.exit(0);
const j = JSON.parse(readFileSync(cfgPath, "utf8"));
const list = Array.isArray(j.packageClassList) ? j.packageClassList : [];
if (!list.includes(extra)) {
  list.push(extra);
  j.packageClassList = list;
  writeFileSync(cfgPath, JSON.stringify(j, null, "\t") + "\n");
  console.log("ensured", extra, "in packageClassList");
}
