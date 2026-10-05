const SHA_K = new Uint32Array([
  0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
  0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
  0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
  0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
  0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
  0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
  0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
  0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2,
]);

const RL = [
  0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 7, 4, 13, 1, 10, 6, 15, 3, 12, 0, 9, 5, 2,
  14, 11, 8, 3, 10, 14, 4, 9, 15, 8, 1, 2, 7, 0, 6, 13, 11, 5, 12, 1, 9, 11, 10, 0, 8, 12, 4, 13, 3,
  7, 15, 14, 5, 6, 2, 4, 0, 5, 9, 7, 12, 2, 10, 14, 1, 3, 8, 11, 6, 15, 13,
];
const RR = [
  5, 14, 7, 0, 9, 2, 11, 4, 13, 6, 15, 8, 1, 10, 3, 12, 6, 11, 3, 7, 0, 13, 5, 10, 14, 15, 8, 12, 4,
  9, 1, 2, 15, 5, 1, 3, 7, 14, 6, 9, 11, 8, 12, 2, 10, 0, 4, 13, 8, 6, 4, 1, 3, 11, 15, 0, 5, 12, 2,
  13, 9, 7, 10, 14, 12, 15, 10, 4, 1, 5, 8, 7, 6, 2, 13, 14, 0, 3, 9, 11,
];
const SL = [
  11, 14, 15, 12, 5, 8, 7, 9, 11, 13, 14, 15, 6, 7, 9, 8, 7, 6, 8, 13, 11, 9, 7, 15, 7, 12, 15, 9,
  11, 7, 13, 12, 11, 13, 6, 7, 14, 9, 13, 15, 14, 8, 13, 6, 5, 12, 7, 5, 11, 12, 14, 15, 14, 15, 9, 8,
  9, 14, 5, 6, 8, 6, 5, 12, 9, 15, 5, 11, 6, 8, 13, 12, 5, 12, 13, 14, 11, 8, 5, 6,
];
const SR = [
  8, 9, 9, 11, 13, 15, 15, 5, 7, 7, 8, 11, 14, 14, 12, 6, 9, 13, 15, 7, 12, 8, 9, 11, 7, 7, 12, 7, 6,
  15, 13, 11, 9, 7, 15, 11, 8, 6, 6, 14, 12, 13, 5, 14, 13, 13, 7, 5, 15, 5, 8, 11, 14, 14, 6, 14, 6,
  9, 12, 9, 12, 5, 15, 8, 8, 5, 12, 9, 12, 5, 14, 6, 8, 13, 6, 5, 15, 13, 11, 11,
];

const ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz";
const addressCache = new Map<string, string>();

function rotr(value: number, bits: number) {
  return (value >>> bits) | (value << (32 - bits));
}

function rotl(value: number, bits: number) {
  return ((value << bits) | (value >>> (32 - bits))) >>> 0;
}

function sha256(bytes: Uint8Array) {
  const bitLen = bytes.length * 8;
  const padded = new Uint8Array(((bytes.length + 9 + 63) >> 6) << 6);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 8, Math.floor(bitLen / 0x100000000));
  view.setUint32(padded.length - 4, bitLen >>> 0);

  let h0 = 0x6a09e667;
  let h1 = 0xbb67ae85;
  let h2 = 0x3c6ef372;
  let h3 = 0xa54ff53a;
  let h4 = 0x510e527f;
  let h5 = 0x9b05688c;
  let h6 = 0x1f83d9ab;
  let h7 = 0x5be0cd19;
  const w = new Uint32Array(64);

  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i += 1) {
      w[i] = view.getUint32(offset + i * 4);
    }
    for (let i = 16; i < 64; i += 1) {
      const s0 = rotr(w[i - 15], 7) ^ rotr(w[i - 15], 18) ^ (w[i - 15] >>> 3);
      const s1 = rotr(w[i - 2], 17) ^ rotr(w[i - 2], 19) ^ (w[i - 2] >>> 10);
      w[i] = (w[i - 16] + s0 + w[i - 7] + s1) >>> 0;
    }
    let a = h0;
    let b = h1;
    let c = h2;
    let d = h3;
    let e = h4;
    let f = h5;
    let g = h6;
    let h = h7;
    for (let i = 0; i < 64; i += 1) {
      const s1 = rotr(e, 6) ^ rotr(e, 11) ^ rotr(e, 25);
      const ch = (e & f) ^ (~e & g);
      const t1 = (h + s1 + ch + SHA_K[i] + w[i]) >>> 0;
      const s0 = rotr(a, 2) ^ rotr(a, 13) ^ rotr(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const t2 = (s0 + maj) >>> 0;
      h = g;
      g = f;
      f = e;
      e = (d + t1) >>> 0;
      d = c;
      c = b;
      b = a;
      a = (t1 + t2) >>> 0;
    }
    h0 = (h0 + a) >>> 0;
    h1 = (h1 + b) >>> 0;
    h2 = (h2 + c) >>> 0;
    h3 = (h3 + d) >>> 0;
    h4 = (h4 + e) >>> 0;
    h5 = (h5 + f) >>> 0;
    h6 = (h6 + g) >>> 0;
    h7 = (h7 + h) >>> 0;
  }

  const out = new Uint8Array(32);
  const outView = new DataView(out.buffer);
  [h0, h1, h2, h3, h4, h5, h6, h7].forEach((word, index) => {
    outView.setUint32(index * 4, word);
  });
  return out;
}

function ripemdRound(j: number, x: number, y: number, z: number) {
  if (j < 16) {
    return x ^ y ^ z;
  }
  if (j < 32) {
    return (x & y) | (~x & z);
  }
  if (j < 48) {
    return (x | ~y) ^ z;
  }
  if (j < 64) {
    return (x & z) | (y & ~z);
  }
  return x ^ (y | ~z);
}

function ripemdLeftConst(j: number) {
  if (j < 16) {
    return 0;
  }
  if (j < 32) {
    return 0x5a827999;
  }
  if (j < 48) {
    return 0x6ed9eba1;
  }
  if (j < 64) {
    return 0x8f1bbcdc;
  }
  return 0xa953fd4e;
}

function ripemdRightConst(j: number) {
  if (j < 16) {
    return 0x50a28be6;
  }
  if (j < 32) {
    return 0x5c4dd124;
  }
  if (j < 48) {
    return 0x6d703ef3;
  }
  if (j < 64) {
    return 0x7a6d76e9;
  }
  return 0;
}

function ripemd160(bytes: Uint8Array) {
  const bitLen = bytes.length * 8;
  const padded = new Uint8Array(((bytes.length + 9 + 63) >> 6) << 6);
  padded.set(bytes);
  padded[bytes.length] = 0x80;
  const view = new DataView(padded.buffer);
  view.setUint32(padded.length - 8, bitLen >>> 0, true);
  view.setUint32(padded.length - 4, Math.floor(bitLen / 0x100000000), true);

  let h0 = 0x67452301;
  let h1 = 0xefcdab89;
  let h2 = 0x98badcfe;
  let h3 = 0x10325476;
  let h4 = 0xc3d2e1f0;
  const x = new Uint32Array(16);

  for (let offset = 0; offset < padded.length; offset += 64) {
    for (let i = 0; i < 16; i += 1) {
      x[i] = view.getUint32(offset + i * 4, true);
    }
    let al = h0;
    let bl = h1;
    let cl = h2;
    let dl = h3;
    let el = h4;
    let ar = h0;
    let br = h1;
    let cr = h2;
    let dr = h3;
    let er = h4;
    for (let j = 0; j < 80; j += 1) {
      let t = (al + ripemdRound(j, bl, cl, dl) + x[RL[j]] + ripemdLeftConst(j)) >>> 0;
      t = (rotl(t, SL[j]) + el) >>> 0;
      al = el;
      el = dl;
      dl = rotl(cl, 10);
      cl = bl;
      bl = t;

      t = (ar + ripemdRound(79 - j, br, cr, dr) + x[RR[j]] + ripemdRightConst(j)) >>> 0;
      t = (rotl(t, SR[j]) + er) >>> 0;
      ar = er;
      er = dr;
      dr = rotl(cr, 10);
      cr = br;
      br = t;
    }
    const next = (h1 + cl + dr) >>> 0;
    h1 = (h2 + dl + er) >>> 0;
    h2 = (h3 + el + ar) >>> 0;
    h3 = (h4 + al + br) >>> 0;
    h4 = (h0 + bl + cr) >>> 0;
    h0 = next;
  }

  const out = new Uint8Array(20);
  const outView = new DataView(out.buffer);
  [h0, h1, h2, h3, h4].forEach((word, index) => {
    outView.setUint32(index * 4, word, true);
  });
  return out;
}

function hexToBytes(hex: string) {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i += 1) {
    bytes[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

function base58Check(payload: Uint8Array) {
  const checksum = sha256(sha256(payload)).subarray(0, 4);
  const data = new Uint8Array(payload.length + 4);
  data.set(payload);
  data.set(checksum, payload.length);
  let zeros = 0;
  while (zeros < data.length && data[zeros] === 0) {
    zeros += 1;
  }
  let value = 0n;
  for (const byte of data) {
    value = (value << 8n) + BigInt(byte);
  }
  let encoded = "";
  while (value > 0n) {
    const remainder = Number(value % 58n);
    value /= 58n;
    encoded = ALPHABET[remainder] + encoded;
  }
  return "1".repeat(zeros) + encoded;
}

export function addressFromPublicKey(publicKey: string) {
  const key = publicKey.trim();
  const cached = addressCache.get(key);
  if (cached !== undefined) {
    return cached;
  }
  if (!/^(02|03)[0-9a-fA-F]{64}$/.test(key) && !/^04[0-9a-fA-F]{128}$/.test(key)) {
    addressCache.set(key, "");
    return "";
  }
  const hash = ripemd160(sha256(hexToBytes(key)));
  const payload = new Uint8Array(21);
  payload.set(hash, 1);
  const address = base58Check(payload);
  addressCache.set(key, address);
  return address;
}
