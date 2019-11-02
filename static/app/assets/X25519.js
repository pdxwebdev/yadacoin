'use strict'
/*
 * Javascript implementation of Elliptic curve Diffie-Hellman key exchange over Curve25519
 *
 * Copyright (c) 2017, Bubelich Mykola
 * https://bubelich.com
 *
 * (｡◕‿‿◕｡)
 *
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met, 0x
 *
 * Redistributions of source code must retain the above copyright notice,
 * this list of conditions and the following disclaimer.
 *
 * Redistributions in binary form must reproduce the above copyright notice,
 * this list of conditions and the following disclaimer in the documentation
 * and/or other materials provided with the distribution.
 *
 * Neither the name of the copyright holder nor the names of its contributors
 * may be used to endorse or promote products derived from this software without
 * specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDER AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 * Inspired by TeetNacl
 *
 * More information
 * https://github.com/CryptoEsel/js-x25519
 *
 * Project
 * CryptoEsel - https://cryptoesel.com
 *
 * References
 * TweetNaCl 20140427 - http://tweetnacl.cr.yp.to/
 * TweetNaCl.js v0.14.5 - https://github.com/dchest/tweetnacl-js
 *
 */
const _X25519_ZERO = new Float64Array([0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000])
const _X25519_ONE = new Float64Array([0x0001, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000])
const _X25519_NINE = new Uint8Array(32)
const _X25519_121665 = new Float64Array([0xDB41, 0x0001, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000])

_X25519_NINE[0] = 9

class X25519 {
  /**
   * *********************
   * PUBLIC STATIC METHOD
   * *********************
   */

  /**
   * Generate and return public key as Uint8Array[32] array
   *
   * @param {Uint8Array} secret
   * @return {Uint8Array}
   */
  static getPublic (secret) {
    if (secret.byteLength !== 32) {
      throw new Error('Secret wrong length, should be 32 bytes.')
    }

    const p = new Uint8Array(secret)
    X25519._clamp(p)

    return X25519._scalarMul(p, _X25519_NINE)
  }

  /**
   * Generate shared key from secret and public key
   * Length is 32 bytes for every key
   *
   * @param {Uint8Array} secretKey
   * @param {Uint8Array} publicKey
   * @return {Uint8Array}
   */
  static getSharedKey (secretKey, publicKey) {
    if (secretKey.byteLength !== 32 || publicKey.byteLength !== 32) {
      throw new Error('Secret key or public key wrong length, should be 32 bytes.')
    }

    const p = new Uint8Array(secretKey)
    X25519._clamp(p)

    return X25519._scalarMul(p, publicKey)
  }

  /**
   * **********************
   * PRIVATE STATIC METHOD
   * **********************
   */

  /**
   *  Addition
   *
   * @param {Float64Array} result
   * @param {Float64Array} augent
   * @param {Float64Array} addend
   * @private
   */
  static _add (result, augent, addend) {
    for (let i = 0; i < 16; i++) {
      result[i] = (augent[i] + addend[i]) | 0
    }
  }

  /**
   * Subtraction
   *
   * @param {Float64Array} result
   * @param {Float64Array} minuend
   * @param {Float64Array} subtrahend
   * @private
   */
  static _sub (result, minuend, subtrahend) {
    for (let i = 0; i < 16; i++) {
      result[i] = (minuend[i] - subtrahend[i]) | 0
    }
  }

  /**
   *  Multiplication
   *
   * @param {Float64Array} result
   * @param {Float64Array} multiplier
   * @param {Float64Array} multiplicand
   * @private
   */
  static _mul (result, multiplier, multiplicand) {
    let i = 0
    let j = 0
    let carry = new Float64Array(31)

    for (i = 0; i < 16; i++) {
      for (j = 0; j < 16; j++) {
        carry[i + j] += multiplier[i] * multiplicand[j]
      }
    }

    /** mul 2 x 19 **/
    for (i = 0; i < 15; i++) {
      carry[i] += 38 * carry[i + 16]
    }

    X25519._car25519(carry)
    X25519._car25519(carry)

    /** copy results **/
    X25519._copy(result, carry)
  }

  /**
   * Compute values^2
   *
   * @param {Float64Array} result
   * @param {Float64Array} values
   * @private
   */
  static _sqr (result, values) {
    X25519._mul(result, values, values)
  }

  /**
   * Core scalar multiplies for curve 25519
   *
   * @param {Uint8Array} multiplier; 32 bytes array
   * @param {Uint8Array} multiplicand; 32 bytes array
   * @private
   */
  static _scalarMul (multiplier, multiplicand) {
    const carry = new Float64Array(80)

    const a = new Float64Array(_X25519_ONE)
    const b = new Float64Array(_X25519_ZERO)
    const c = new Float64Array(_X25519_ZERO)
    const d = new Float64Array(_X25519_ONE)
    const e = new Float64Array(_X25519_ZERO)
    const f = new Float64Array(_X25519_ZERO)

    const z = new Uint8Array(multiplier)

    let r = 0

    X25519._unpack(carry, multiplicand)

    // copy carry to b //
    X25519._copy(b, carry)

    for (let i = 254; i >= 0; --i) {
      r = (z[i >>> 3] >>> (i & 7)) & 1

      X25519._sel25519(a, b, r)
      X25519._sel25519(c, d, r)

      X25519._add(e, a, c)
      X25519._sub(a, a, c)

      X25519._add(c, b, d)
      X25519._sub(b, b, d)

      X25519._sqr(d, e)
      X25519._sqr(f, a)

      X25519._mul(a, c, a)
      X25519._mul(c, b, e)

      X25519._add(e, a, c)
      X25519._sub(a, a, c)

      X25519._sqr(b, a)
      X25519._sub(c, d, f)

      X25519._mul(a, c, _X25519_121665)
      X25519._add(a, a, d)

      X25519._mul(c, c, a)
      X25519._mul(a, d, f)
      X25519._mul(d, b, carry)

      X25519._sqr(b, e)

      X25519._sel25519(a, b, r)
      X25519._sel25519(c, d, r)
    }

    for (let i = 0; i < 16; i++) {
      carry[i + 16] = a[i]
      carry[i + 32] = c[i]
      carry[i + 48] = b[i]
      carry[i + 64] = d[i]
    }

    const x32 = carry.subarray(32)
    const x16 = carry.subarray(16)

    X25519._inv25519(x32, x32)
    X25519._mul(x16, x16, x32)

    const result = new Uint8Array(32)

    X25519._pack(result, x16)

    return result
  }

  /**
   *
   * @param {Float64Array} result
   * @param {Float64Array} values
   * @private
   */
  static _inv25519 (result, values) {
    const carry = new Float64Array(16)

    // copy values to carry //
    X25519._copy(carry, values)

    // compute //
    for (let i = 253; i >= 0; i--) {
      X25519._sqr(carry, carry)
      if (i !== 2 && i !== 4) {
        X25519._mul(carry, carry, values)
      }
    }

    // copy carry to results //
    X25519._copy(result, carry)
  }

  /**
   *
   * @param {Float64Array} result
   * @param {Float64Array} q
   * @param {Number} b
   * @private
   */
  static _sel25519 (result, q, b) {
    let tmp = 0
    let carry = ~(b - 1)

    // compute //
    for (let i = 0; i < 16; i++) {
      tmp = carry & (result[i] ^ q[i])
      result[i] ^= tmp
      q[i] ^= tmp
    }
  }

  /**
   *
   * @param {Float64Array} values
   * @private
   */
  static _car25519 (values) {
    let carry = 0

    for (let i = 0; i < 16; i++) {
      values[i] += 65536
      carry = Math.floor(values[i] / 65536)
      values[(i + 1) * (i < 15 ? 1 : 0)] += carry - 1 + 37 * (carry - 1) * (i === 15 ? 1 : 0)
      values[i] -= (carry * 65536)
    }
  }

  /**
   * Upack 1x32 -> 8x16 bytes arrays
   *
   * @param {Float64Array} result
   * @param {Uint8Array} values
   * @private
   */
  static _unpack (result, values) {
    for (let i = 0; i < 16; i++) {
      result[i] = values[2 * i] + (values[2 * i + 1] << 8)
    }
  }

  /**
   * Pack from 8x16 -> 1x32 bytes array
   *
   * @param {Float64Array} result
   * @param {Float64Array} values
   * @private
   */
  static _pack (result, values) {
    const m = new Float64Array(16)
    const tmp = new Float64Array(16)
    let i = 0
    let carry = 0

    // copy //
    X25519._copy(tmp, values)

    X25519._car25519(tmp)
    X25519._car25519(tmp)
    X25519._car25519(tmp)

    for (let j = 0; j < 2; j++) {
      m[0] = tmp[0] - 0xFFED

      for (i = 1; i < 15; i++) {
        m[i] = tmp[i] - 0xFFFF - ((m[i - 1] >> 16) & 1)
        m[i - 1] &= 0xFFFF
      }

      m[15] = tmp[15] - 0x7FFF - ((m[14] >> 16) & 1)
      carry = (m[15] >> 16) & 1
      m[14] &= 0xFFFF

      X25519._sel25519(tmp, m, 1 - carry)
    }

    for (i = 0; i < 16; i++) {
      result[2 * i] = tmp[i] & 0xFF
      result[2 * i + 1] = tmp[i] >> 8
    }
  }

  /**
   * Copy source to destination
   * Warning! length not checked!
   *
   * @param {Float64Array} destination
   * @param {Float64Array} source
   * @private
   */
  static _copy (destination, source) {
    const len = source.length
    for (let i = 0; i < len; i++) {
      destination[i] = source[i]
    }
  }

  /**
   * Curve 25516 clamp input seed bytes
   *
   * @param {Uint8Array} bytes
   * @private
   */
  static _clamp (bytes) {
    bytes[0] = bytes[0] & 0xF8
    bytes[31] = (bytes[31] & 0x7F) | 0x40
  }
}

if (typeof module !== 'undefined') {
  module.exports = X25519
}