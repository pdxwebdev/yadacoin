import { sha256Hex } from "./hash.js";
import { isPasswordHash } from "./hash.js";
import { utf8ToBase64 } from "./bytes.js";

export const PASSWORD_RELATIONSHIP_KEY = "password";

export interface PasswordDualCommit {
  prerotated_password_hash: string;
  twice_prerotated_password_hash: string;
}

export function buildPasswordRelationshipJson(commit: PasswordDualCommit): string {
  validateDualCommit(commit);
  return JSON.stringify({
    [PASSWORD_RELATIONSHIP_KEY]: {
      prerotated_password_hash: normalizeStoredHash(
        commit.prerotated_password_hash
      ),
      twice_prerotated_password_hash: normalizeStoredHash(
        commit.twice_prerotated_password_hash
      ),
    },
  });
}

export function encodePasswordRelationshipB64(commit: PasswordDualCommit): string {
  return utf8ToBase64(buildPasswordRelationshipJson(commit));
}

export function validateDualCommit(commit: PasswordDualCommit): void {
  const pre = commit.prerotated_password_hash?.trim() ?? "";
  const twice = commit.twice_prerotated_password_hash?.trim() ?? "";
  if (!pre || !twice) throw new Error("both password hashes required");
  if (!isPasswordHash(pre) || !isPasswordHash(twice)) {
    throw new Error("password hashes must be PHC strings or legacy 64-char hex");
  }
  if (normalizeStoredHash(pre) === normalizeStoredHash(twice)) {
    throw new Error("password hashes must differ");
  }
}

function normalizeStoredHash(value: string): string {
  const v = value.trim();
  return /^[0-9a-f]{64}$/i.test(v) ? v.toLowerCase() : v;
}

export function identityRelationshipString(
  username: string,
  usernameSignature: string,
  identityType = "social"
): string {
  return username + usernameSignature + identityType;
}

export function identityRelationshipHash(
  username: string,
  usernameSignature: string,
  identityType = "social"
): string {
  return sha256Hex(
    identityRelationshipString(username, usernameSignature, identityType)
  );
}

export function identityRelationshipDict(
  username: string,
  usernameSignature: string,
  identityType = "social"
): { identity: Record<string, string> } {
  return {
    identity: {
      username,
      username_signature: usernameSignature,
      identity_type: identityType,
    },
  };
}

export function branchRelationshipString(pre: string, twice: string): string {
  return pre + twice;
}

export function branchRelationshipHash(pre: string, twice: string): string {
  return sha256Hex(branchRelationshipString(pre, twice));
}

export function branchRelationshipDict(
  pre: string,
  twice: string
): { branch: { prerotated_key_hash: string; twice_prerotated_key_hash: string } } {
  return {
    branch: {
      prerotated_key_hash: pre,
      twice_prerotated_key_hash: twice,
    },
  };
}
