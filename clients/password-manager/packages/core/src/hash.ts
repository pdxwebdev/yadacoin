import { sha256 } from "@noble/hashes/sha256";
import { bytesToHex } from "./bytes.js";

const PASSWORD_DOMAIN = "yada-password-v1|";

/** Domain-separated password digest — matches plugins/passwordrotation. */
export function hashPassword(password: string): string {
  const data = new TextEncoder().encode(PASSWORD_DOMAIN + password);
  return bytesToHex(sha256(data));
}

export function isPasswordHash(value: string): boolean {
  return /^[0-9a-f]{64}$/i.test(value);
}

export function sha256Hex(data: string | Uint8Array): string {
  const bytes =
    typeof data === "string" ? new TextEncoder().encode(data) : data;
  return bytesToHex(sha256(bytes));
}
