import { argon2id } from "@noble/hashes/argon2";
import { pbkdf2 } from "@noble/hashes/pbkdf2";
import { scrypt } from "@noble/hashes/scrypt";
import { sha256 } from "@noble/hashes/sha256";
import { bytesToHex } from "@noble/hashes/utils";
import bcrypt from "bcryptjs";

export const DEFAULT_PASSWORD_PHC = "$pbkdf2-sha256$i=310000";

const MAX_PBKDF2_ITERS = 1_000_000;
const MAX_SCRYPT_LN = 20;
const MAX_ARGON2_M = 1_048_576;
const MAX_ARGON2_T = 32;
const MAX_BCRYPT_ROUNDS = 15;
const BCRYPT_MODULAR = /^\$2[aby]\$(\d{2})\$/;

export interface PhcParts {
  id: string;
  version?: string;
  params: Record<string, string>;
  salt?: string;
  hash?: string;
}

export function sha256Hex(data: string | Uint8Array): string {
  const bytes = typeof data === "string" ? new TextEncoder().encode(data) : data;
  return bytesToHex(sha256(bytes));
}

const HEX64 = /^[0-9a-f]{64}$/i;

export function isPasswordHash(value: string): boolean {
  const v = (value || "").trim();
  if (HEX64.test(v)) return true;
  return parsePhc(v) !== null;
}

function normalizeId(id: string): string {
  const n = id.toLowerCase();
  if (n === "pbkdf2-hmac-sha256" || n === "pbkdf2-hmac-sha-256") return "pbkdf2-sha256";
  if (n === "2a" || n === "2b" || n === "2y") return "bcrypt";
  return n;
}

export function parsePhc(value: string): PhcParts | null {
  const s = value.trim();
  if (!s.startsWith("$")) return null;
  const bcryptMod = s.match(BCRYPT_MODULAR);
  if (bcryptMod) {
    return {
      id: "bcrypt",
      version: "2b",
      params: { t: String(Number(bcryptMod[1])) },
      hash: s,
    };
  }
  const parts = s.split("$");
  if (parts.length < 2 || parts[0] !== "" || !parts[1]) return null;
  const id = normalizeId(parts[1]);
  if (!["pbkdf2-sha256", "scrypt", "argon2id", "bcrypt"].includes(id)) return null;
  let i = 2;
  let version: string | undefined;
  if (parts[i] && /^v=/.test(parts[i])) {
    version = parts[i].slice(2);
    i += 1;
  }
  const params: Record<string, string> = {};
  if (parts[i] && parts[i].includes("=")) {
    for (const kv of parts[i].split(",")) {
      const eq = kv.indexOf("=");
      if (eq <= 0) return null;
      params[kv.slice(0, eq)] = kv.slice(eq + 1);
    }
    i += 1;
  }
  const salt = parts[i] || undefined;
  const hash = parts[i + 1] || undefined;
  return { id, version, params, salt, hash };
}

export function formatPhc(p: PhcParts): string {
  if (p.id === "bcrypt" && p.hash && BCRYPT_MODULAR.test(p.hash)) return p.hash;
  let out = `$${p.id}`;
  if (p.version) out += `$v=${p.version}`;
  const keys = Object.keys(p.params);
  if (keys.length) {
    out += "$" + keys.map((k) => `${k}=${p.params[k]}`).join(",");
  }
  if (p.salt !== undefined) out += `$${p.salt}`;
  if (p.hash !== undefined) out += `$${p.hash}`;
  return out;
}

function b64encode(bytes: Uint8Array): string {
  let bin = "";
  for (const b of bytes) bin += String.fromCharCode(b);
  return btoa(bin).replace(/=+$/, "");
}

function b64decode(s: string): Uint8Array {
  const pad = "=".repeat((4 - (s.length % 4)) % 4);
  const bin = atob(s + pad);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function utf8(password: string): Uint8Array {
  return new TextEncoder().encode(password);
}

function digestFor(
  id: string,
  password: string,
  parts: PhcParts,
  salt: Uint8Array
): string {
  if (id === "pbkdf2-sha256") {
    const iters = Number(parts.params.i || parts.params.iterations || 310000);
    if (!Number.isFinite(iters) || iters < 1 || iters > MAX_PBKDF2_ITERS) {
      throw new Error("invalid PHC pbkdf2 iteration count");
    }
    return b64encode(pbkdf2(sha256, utf8(password), salt, { c: iters, dkLen: 32 }));
  }
  if (id === "scrypt") {
    const ln = Number(parts.params.ln ?? 14);
    const r = Number(parts.params.r ?? 8);
    const p = Number(parts.params.p ?? 1);
    if (!Number.isFinite(ln) || ln < 1 || ln > MAX_SCRYPT_LN) {
      throw new Error("invalid PHC scrypt ln");
    }
    return b64encode(scrypt(utf8(password), salt, { N: 2 ** ln, r, p, dkLen: 32 }));
  }
  if (id === "argon2id") {
    const m = Number(parts.params.m ?? 19456);
    const t = Number(parts.params.t ?? 2);
    const p = Number(parts.params.p ?? 1);
    if (!Number.isFinite(m) || m < 8 || m > MAX_ARGON2_M) {
      throw new Error("invalid PHC argon2 memory");
    }
    if (!Number.isFinite(t) || t < 1 || t > MAX_ARGON2_T) {
      throw new Error("invalid PHC argon2 time cost");
    }
    return b64encode(argon2id(utf8(password), salt, { t, m, p, dkLen: 32 }));
  }
  throw new Error(`unsupported PHC id ${id}`);
}

function bcryptRounds(parts: PhcParts): number {
  const t = Number(parts.params.t || parts.params.r || parts.params.cost || 12);
  if (!Number.isFinite(t) || t < 4 || t > MAX_BCRYPT_ROUNDS) {
    throw new Error("invalid bcrypt cost");
  }
  return t;
}

function hashPasswordLegacySha256(password: string): string {
  return bytesToHex(sha256(new TextEncoder().encode("yada-password-v1|" + password)));
}

export function hashPassword(password: string, phc: string = DEFAULT_PASSWORD_PHC): string {
  const parsed = parsePhc(phc);
  if (!parsed) throw new Error("invalid PHC string");
  if (parsed.id === "bcrypt") {
    return bcrypt.hashSync(password, bcryptRounds(parsed));
  }
  const saltBytes = parsed.salt
    ? b64decode(parsed.salt)
    : sha256(new TextEncoder().encode("yada-phc-salt-v1|" + password)).slice(0, 16);
  const hash = digestFor(parsed.id, password, parsed, saltBytes);
  return formatPhc({
    id: parsed.id,
    version: parsed.version || (parsed.id === "argon2id" ? "19" : undefined),
    params: parsed.params,
    salt: b64encode(saltBytes),
    hash,
  });
}

export function verifyPassword(password: string, stored: string): boolean {
  const s = (stored || "").trim();
  if (HEX64.test(s)) {
    return (
      hashPasswordLegacySha256(password).toLowerCase() === s.toLowerCase()
    );
  }
  const parsed = parsePhc(s);
  if (!parsed) return false;
  try {
    if (parsed.id === "bcrypt") {
      const crypt = parsed.hash && BCRYPT_MODULAR.test(parsed.hash) ? parsed.hash : stored;
      return bcrypt.compareSync(password, crypt);
    }
    if (!parsed.hash) return false;
    const recomputed = hashPassword(password, stored);
    return recomputed === stored || recomputed === formatPhc(parsed);
  } catch {
    return false;
  }
}

export function phcTemplate(phc: string): string {
  const parsed = parsePhc(phc);
  if (!parsed) throw new Error("invalid PHC string");
  if (parsed.id === "bcrypt") {
    return formatPhc({ id: "bcrypt", params: { t: parsed.params.t || "12" } });
  }
  return formatPhc({
    id: parsed.id,
    version: parsed.version,
    params: parsed.params,
  });
}
