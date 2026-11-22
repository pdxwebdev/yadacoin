import { Builder, initSia } from "@siafoundation/sia-storage";
import { bytesToHex } from "@yadacoin/password-core";

const INDEXER = "https://sia.storage";
const APP_ID = "ef771f39d74338072dd10ba7d13c99120659a7e383233d627f7f54727cdd2f6d";

const appMeta = {
  appId: APP_ID,
  name: "Yada Scroller",
  description: "Comments, likes, and posts",
  serviceUrl: "https://yadacoin.io",
  logoUrl: undefined,
  callbackUrl: undefined,
};

export async function connectSia(mnemonic: string): Promise<string> {
  const phrase = mnemonic.trim();
  if (!phrase) throw new Error("vault seed required");
  await initSia();
  const builder = new Builder(INDEXER, appMeta);
  await builder.requestConnection();
  const url = builder.responseUrl();
  window.open(url, "_blank", "noopener");
  await builder.waitForApproval();
  const sdk = await builder.register(phrase);
  return bytesToHex(sdk.appKey().export());
}
