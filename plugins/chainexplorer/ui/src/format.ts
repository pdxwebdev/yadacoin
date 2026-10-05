import { addressFromPublicKey } from "./address";
import type { Block, Txn } from "./types";

const MAX_TARGET = (1n << 256n) - 1n;

export function isBlock(value: unknown): value is Block {
  if (!value || typeof value !== "object") {
    return false;
  }
  const block = value as Block;
  return typeof block.index === "number" && typeof block.hash === "string";
}

export function txnsOf(block: Block): Txn[] {
  return Array.isArray(block.transactions) ? block.transactions : [];
}

export function isCoinbase(txn: Txn, block?: Block): boolean {
  if (!block?.public_key || txn.public_key !== block.public_key) {
    return false;
  }
  if (txn.inputs && txn.inputs.length > 0) {
    return false;
  }
  const outputs = (txn.outputs || []).map((output) => output.to).filter(Boolean);
  const prerotated = txn.prerotated_key_hash || "";
  if (prerotated && outputs.includes(prerotated)) {
    return true;
  }
  const address = addressFromPublicKey(block.public_key);
  return Boolean(address && outputs.includes(address));
}

export function outputTotal(txn: Txn): number {
  const sum = (txn.outputs || []).reduce((total, output) => {
    const value = typeof output.value === "number" ? output.value : Number(output.value);
    return Number.isFinite(value) ? total + value : total;
  }, 0);
  return Math.round(sum * 1e8) / 1e8;
}

export function minerOf(block: Block): string {
  const coinbase = txnsOf(block).find((txn) => isCoinbase(txn, block));
  if (!coinbase) {
    return block.public_key || "";
  }
  const address = addressFromPublicKey(block.public_key || "");
  const match = coinbase.outputs?.find(
    (output) => output.to === address || output.to === coinbase.prerotated_key_hash,
  );
  return match?.to || coinbase.outputs?.[0]?.to || block.public_key || "";
}

export function difficultyFromTarget(target?: string): string {
  if (!target) {
    return "";
  }
  try {
    const parsed = BigInt(`0x${target}`);
    if (parsed <= 0n) {
      return "";
    }
    return (MAX_TARGET / parsed).toLocaleString();
  } catch {
    return "";
  }
}

export function formatNumber(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return value.toLocaleString();
}

export function formatCoins(value: number | string | undefined): string {
  if (value === undefined || value === null || value === "") {
    return "";
  }
  const amount = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(amount)) {
    return String(value);
  }
  return amount.toLocaleString(undefined, { maximumFractionDigits: 8 });
}

export function formatRate(value: number | undefined): string {
  if (value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  const units = ["H/s", "KH/s", "MH/s", "GH/s", "TH/s", "PH/s"];
  let amount = value;
  let index = 0;
  while (amount >= 1000 && index < units.length - 1) {
    amount /= 1000;
    index += 1;
  }
  const digits = amount >= 100 || index === 0 ? 0 : 2;
  return `${amount.toLocaleString(undefined, { maximumFractionDigits: digits })} ${units[index]}`;
}

export function formatBytes(value: unknown): string {
  const bytes = new TextEncoder().encode(JSON.stringify(value)).length;
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function epochMs(time: number | string | undefined): number | null {
  if (typeof time === "number" && Number.isFinite(time)) {
    return time * 1000;
  }
  if (typeof time !== "string" || !time) {
    return null;
  }
  const parsed = Date.parse(time.replace(" UTC", "Z"));
  return Number.isNaN(parsed) ? null : parsed;
}

export function formatTime(time: number | string | undefined): string {
  if (time === undefined || time === null || time === "") {
    return "";
  }
  if (typeof time === "string") {
    return time;
  }
  const ms = epochMs(time);
  if (ms === null) {
    return String(time);
  }
  return new Date(ms).toISOString().replace(".000Z", "Z");
}

export function age(time: number | string | undefined): string {
  const ms = epochMs(time);
  if (ms === null) {
    return "";
  }
  const seconds = Math.max(0, (Date.now() - ms) / 1000);
  if (seconds < 60) {
    return `${Math.floor(seconds)}s`;
  }
  if (seconds < 3600) {
    return `${Math.floor(seconds / 60)}m`;
  }
  if (seconds < 86400) {
    return `${Math.floor(seconds / 3600)}h`;
  }
  return `${Math.floor(seconds / 86400)}d`;
}

export function shortId(value: string | undefined, head = 8, tail = 6): string {
  if (!value) {
    return "";
  }
  if (value.length <= head + tail + 1) {
    return value;
  }
  return `${value.slice(0, head)}…${value.slice(-tail)}`;
}

export function txnTone(txn: Txn, block?: Block): string {
  if (isCoinbase(txn, block)) {
    return "#3fb950";
  }
  if (txn.relationship?.file) {
    return "#ffa657";
  }
  if (txn.relationship?.identity) {
    return "#d2a8ff";
  }
  if ((txn.fee || 0) > 0) {
    return "#f78166";
  }
  return "#58a6ff";
}

export function feeTone(fee: number, maxFee: number): string {
  if (maxFee <= 0) {
    return "#79c0ff";
  }
  const rank = fee / maxFee;
  if (rank > 0.75) {
    return "#ff2bd6";
  }
  if (rank > 0.4) {
    return "#f78166";
  }
  if (rank > 0.15) {
    return "#ffa657";
  }
  return "#79c0ff";
}

export function resultLabel(resultType: string | undefined): string {
  if (!resultType) {
    return "Result";
  }
  const labels: Record<string, string> = {
    block_height: "Block",
    block_hash: "Block hash",
    block_id: "Block id",
    txn_hash: "Transaction",
    txn_rid: "Relationship",
    txn_id: "Signature",
    txn_outputs_to: "Address",
    txn_identity_username: "Identity",
    txn_identity_username_signature: "Identity signature",
    username_profile: "Username",
    txn_file_announcement: "File announcement",
  };
  if (labels[resultType]) {
    return labels[resultType];
  }
  if (resultType.startsWith("mempool")) {
    return "Mempool";
  }
  if (resultType.startsWith("failed")) {
    return "Failed";
  }
  return resultType.replaceAll("_", " ");
}

export function asList(result: unknown): unknown[] {
  if (Array.isArray(result)) {
    return result;
  }
  if (result && typeof result === "object") {
    return [result];
  }
  return [];
}

export function txnMatches(txn: Txn, term: string): boolean {
  const needle = term.trim();
  if (!needle) {
    return false;
  }
  const fields = [
    txn.hash,
    txn.id,
    txn.rid,
    txn.public_key,
    txn.dh_public_key,
    txn.relationship_hash,
    txn.public_key_hash,
    txn.prev_public_key_hash,
    txn.prerotated_key_hash,
    txn.twice_prerotated_key_hash,
    txn.miner_signature,
    txn.requester_rid,
    txn.requested_rid,
    txn.relationship?.identity?.username,
    txn.relationship?.identity?.username_signature,
    txn.relationship?.file?.file_id,
    txn.relationship?.file?.filename,
    txn.relationship?.file?.title,
  ];
  if (fields.some((field) => field === needle)) {
    return true;
  }
  if (txn.outputs?.some((output) => output.to === needle)) {
    return true;
  }
  return Boolean(txn.inputs?.some((input) => input.id === needle));
}
