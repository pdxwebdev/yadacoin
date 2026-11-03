import { AppKey, Builder, PinnedObject, generateRecoveryPhrase, initSia } from "@siafoundation/sia-storage";
import { bytesToHex, hexToBytes } from "@yadacoin/password-core";

const INDEXER = "https://sia.storage";
const APP_ID = "ef771f39d74338072dd10ba7d13c99120659a7e383233d627f7f54727cdd2f6d";

let dialGate = Promise.resolve();
let dialsQueued = false;
let dials = 0;
let ready = 0;
let onStatus: (message: string) => void = () => {};

export function setSiaStatus(fn: (message: string) => void): void {
  onStatus = fn;
}

function queueWebTransport(): void {
  if (dialsQueued) return;
  dialsQueued = true;
  const Native = globalThis.WebTransport;
  function Queued(this: WebTransport, url: string, options?: WebTransportOptions) {
    const started = dialGate.then(() => {
      dials += 1;
      const host = url.replace(/^https:\/\//, "").replace(/\/sia\/rhp\/v4$/, "");
      onStatus(`Dialing ${host} (${dials} tried, ${ready} up)`);
      const wt = new Native(url, options);
      return wt.ready.then(
        () => {
          ready += 1;
          onStatus(`Connected ${host} (${ready} up)`);
          return wt;
        },
        (e: unknown) => {
          onStatus(`No answer from ${host}, trying the next host`);
          try {
            wt.close();
          } catch {
            /* already closed */
          }
          throw e;
        }
      );
    });
    dialGate = started.then(
      () => undefined,
      () => undefined
    );
    return {
      ready: started.then(() => undefined),
      closed: started.then((wt) => wt.closed),
      createBidirectionalStream: () => started.then((wt) => wt.createBidirectionalStream()),
      createUnidirectionalStream: () => started.then((wt) => wt.createUnidirectionalStream()),
      close: (info?: WebTransportCloseInfo) => {
        void started.then((wt) => wt.close(info)).catch(() => undefined);
      },
    } as WebTransport;
  }
  Queued.prototype = Native.prototype;
  globalThis.WebTransport = Queued as unknown as typeof WebTransport;
}

const appMeta = {
  appId: APP_ID,
  name: "Yada Scroller",
  description: "Comments, likes, and posts",
  serviceUrl: "https://yadacoin.io",
  logoUrl: undefined,
  callbackUrl: undefined,
};

export async function connectSia(): Promise<string> {
  await initSia();
  const builder = new Builder(INDEXER, appMeta);
  await builder.requestConnection();
  const url = builder.responseUrl();
  if (!url) throw new Error("Sia did not return an approval URL");
  const opened = window.open(url, "_blank");
  if (!opened) throw new Error("allow the Sia approval window");
  await builder.waitForApproval();
  const sdk = await builder.register(generateRecoveryPhrase());
  return bytesToHex(sdk.appKey().export());
}

export async function uploadWithKey(
  appKeyHex: string,
  blob: Blob
): Promise<{ file_id: string; share_url: string; size: number }> {
  queueWebTransport();
  await initSia();
  const sdk = await new Builder(INDEXER, appMeta).connected(new AppKey(hexToBytes(appKeyHex)));
  if (!sdk) throw new Error("Sia app key is not connected to this app");
  onStatus("Uploading. Hosts are dialed one at a time.");
  const obj = await sdk.upload(new PinnedObject(), blob.stream(), {
    onShardUploaded: (progress) => {
      onStatus(`Shard ${progress.shardIndex + 1} stored (${ready} hosts up)`);
    },
  });
  await sdk.pinObject(obj);
  const expires = new Date(Date.now() + 3650 * 24 * 60 * 60 * 1000);
  const key = await sdk.createSharingKey("yadacoin-file-announcement", expires);
  await sdk.shareObject(key, obj);
  const seed = String(key.seed() || "").replace(/^0x/, "");
  if (!/^[0-9a-fA-F]{64}$/.test(seed)) throw new Error("sharing key seed is not 64 hex");
  const id = typeof obj.id === "function" ? obj.id() : obj.id;
  return { file_id: String(id), share_url: "sia-share:v1:" + seed.toLowerCase(), size: blob.size };
}
