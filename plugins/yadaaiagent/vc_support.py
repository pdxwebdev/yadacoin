"""
W3C Verifiable Credential support utilities for YadaCoin AI Agent.

Implements:
  - RDFC-1.0 (URDNA2015) canonicalization via pyld with bundled contexts
  - W3C Data Integrity ECDSA signing (ecdsa-secp256k1-2019)
  - Multibase base58btc proof encoding

Signing algorithm follows W3C Data Integrity spec §3.3:
  hashData = SHA-256(RDFC-1.0(proofConfig)) || SHA-256(RDFC-1.0(document))
  proofValue = multibase.base58btc(ECDSA.sign(hashData))
"""

import hashlib

# ── Bundled JSON-LD contexts ──────────────────────────────────────────────────
# These are cached copies of remote contexts, used so signing never requires
# an outbound network call.  Update by re-fetching from the canonical URLs.

# Snapshot of https://www.w3.org/ns/credentials/v2
_VC_V2_CONTEXT_DOC = {
    "@context": {
        "@protected": True,
        "id": "@id",
        "type": "@type",
        "name": "https://schema.org/name",
        "description": "https://schema.org/description",
        "digestMultibase": {
            "@id": "https://w3id.org/security#digestMultibase",
            "@type": "https://w3id.org/security#multibase",
        },
        "VerifiableCredential": {
            "@id": "https://www.w3.org/2018/credentials#VerifiableCredential",
            "@context": {
                "@protected": True,
                "id": "@id",
                "type": "@type",
                "confidenceMethod": {
                    "@id": "https://www.w3.org/2018/credentials#confidenceMethod",
                    "@type": "@id",
                },
                "credentialSchema": {
                    "@id": "https://www.w3.org/2018/credentials#credentialSchema",
                    "@type": "@id",
                },
                "credentialStatus": {
                    "@id": "https://www.w3.org/2018/credentials#credentialStatus",
                    "@type": "@id",
                },
                "credentialSubject": {
                    "@id": "https://www.w3.org/2018/credentials#credentialSubject",
                    "@type": "@id",
                },
                "description": "https://schema.org/description",
                "evidence": {
                    "@id": "https://www.w3.org/2018/credentials#evidence",
                    "@type": "@id",
                },
                "issuer": {
                    "@id": "https://www.w3.org/2018/credentials#issuer",
                    "@type": "@id",
                },
                "name": "https://schema.org/name",
                "proof": {
                    "@id": "https://w3id.org/security#proof",
                    "@type": "@id",
                    "@container": "@graph",
                },
                "refreshService": {
                    "@id": "https://www.w3.org/2018/credentials#refreshService",
                    "@type": "@id",
                },
                "relatedResource": {
                    "@id": "https://www.w3.org/2018/credentials#relatedResource",
                    "@type": "@id",
                },
                "renderMethod": {
                    "@id": "https://www.w3.org/2018/credentials#renderMethod",
                    "@type": "@id",
                },
                "termsOfUse": {
                    "@id": "https://www.w3.org/2018/credentials#termsOfUse",
                    "@type": "@id",
                },
                "validFrom": {
                    "@id": "https://www.w3.org/2018/credentials#validFrom",
                    "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
                },
                "validUntil": {
                    "@id": "https://www.w3.org/2018/credentials#validUntil",
                    "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
                },
            },
        },
        "VerifiablePresentation": {
            "@id": "https://www.w3.org/2018/credentials#VerifiablePresentation",
            "@context": {
                "@protected": True,
                "id": "@id",
                "type": "@type",
                "holder": {
                    "@id": "https://www.w3.org/2018/credentials#holder",
                    "@type": "@id",
                },
                "proof": {
                    "@id": "https://w3id.org/security#proof",
                    "@type": "@id",
                    "@container": "@graph",
                },
                "termsOfUse": {
                    "@id": "https://www.w3.org/2018/credentials#termsOfUse",
                    "@type": "@id",
                },
                "verifiableCredential": {
                    "@id": "https://www.w3.org/2018/credentials#verifiableCredential",
                    "@type": "@id",
                    "@container": "@graph",
                    "@context": None,
                },
            },
        },
        "EnvelopedVerifiableCredential": "https://www.w3.org/2018/credentials#EnvelopedVerifiableCredential",
        "EnvelopedVerifiablePresentation": "https://www.w3.org/2018/credentials#EnvelopedVerifiablePresentation",
        "DataIntegrityProof": {
            "@id": "https://w3id.org/security#DataIntegrityProof",
            "@context": {
                "@protected": True,
                "id": "@id",
                "type": "@type",
                "challenge": "https://w3id.org/security#challenge",
                "created": {
                    "@id": "http://purl.org/dc/terms/created",
                    "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
                },
                "cryptosuite": {
                    "@id": "https://w3id.org/security#cryptosuite",
                    "@type": "https://w3id.org/security#cryptosuiteString",
                },
                "domain": "https://w3id.org/security#domain",
                "expires": {
                    "@id": "https://w3id.org/security#expiration",
                    "@type": "http://www.w3.org/2001/XMLSchema#dateTime",
                },
                "nonce": "https://w3id.org/security#nonce",
                "previousProof": {
                    "@id": "https://w3id.org/security#previousProof",
                    "@type": "@id",
                },
                "proofPurpose": {
                    "@id": "https://w3id.org/security#proofPurpose",
                    "@type": "@vocab",
                    "@context": {
                        "@protected": True,
                        "id": "@id",
                        "type": "@type",
                        "assertionMethod": {
                            "@id": "https://w3id.org/security#assertionMethod",
                            "@type": "@id",
                            "@container": "@set",
                        },
                        "authentication": {
                            "@id": "https://w3id.org/security#authenticationMethod",
                            "@type": "@id",
                            "@container": "@set",
                        },
                        "capabilityDelegation": {
                            "@id": "https://w3id.org/security#capabilityDelegationMethod",
                            "@type": "@id",
                            "@container": "@set",
                        },
                        "capabilityInvocation": {
                            "@id": "https://w3id.org/security#capabilityInvocationMethod",
                            "@type": "@id",
                            "@container": "@set",
                        },
                        "keyAgreement": {
                            "@id": "https://w3id.org/security#keyAgreementMethod",
                            "@type": "@id",
                            "@container": "@set",
                        },
                    },
                },
                "proofValue": {
                    "@id": "https://w3id.org/security#proofValue",
                    "@type": "https://w3id.org/security#multibase",
                },
                "verificationMethod": {
                    "@id": "https://w3id.org/security#verificationMethod",
                    "@type": "@id",
                },
            },
        },
    }
}

# Context for YadaCoin booking credentials.
# Canonical URL: https://yadacoin.io/contexts/booking/v1
# Also served locally at GET /contexts/booking/v1
BOOKING_V1_CONTEXT_URL = "https://yadacoin.io/contexts/booking/v1"
BOOKING_V1_CONTEXT_DOC = {
    "@context": {
        "yada": "https://yadacoin.io/vocab#",
        "BookingConfirmationCredential": "yada:BookingConfirmationCredential",
        "bookingDetails": {
            "@id": "yada:bookingDetails",
            "@type": "@json",
        },
        "confirmation": "yada:confirmation",
        "scope": {
            "@id": "yada:scope",
            "@type": "@json",
        },
        "vendor": "yada:vendor",
        "service": "yada:service",
    }
}

# ── Document loader ───────────────────────────────────────────────────────────

_BUNDLED_CONTEXTS = {
    "https://www.w3.org/ns/credentials/v2": _VC_V2_CONTEXT_DOC,
    BOOKING_V1_CONTEXT_URL: BOOKING_V1_CONTEXT_DOC,
}


def _make_document_loader(extra=None):
    """
    Return a pyld document loader that serves bundled contexts without network,
    falling back to the network for any unknown URL.
    """
    cache = dict(_BUNDLED_CONTEXTS)
    if extra:
        cache.update(extra)

    try:
        from pyld.documentloader.requests import requests_document_loader

        _net = requests_document_loader()
    except Exception:
        _net = None

    def loader(url, options=None):
        if url in cache:
            return {
                "contextUrl": None,
                "documentUrl": url,
                "document": cache[url],
                "contentType": "application/ld+json",
            }
        if _net is not None:
            return _net(url, options)
        raise Exception(f"Context not bundled and no network loader available: {url}")

    return loader


# ── Canonicalization ──────────────────────────────────────────────────────────


def rdfc_canonicalize(doc, doc_loader=None):
    """Canonicalize a JSON-LD document to N-Quads using RDFC-1.0 (URDNA2015)."""
    from pyld import jsonld

    opts = {"algorithm": "URDNA2015", "format": "application/n-quads"}
    if doc_loader is not None:
        opts["documentLoader"] = doc_loader
    return jsonld.normalize(doc, opts)


# ── Signing ───────────────────────────────────────────────────────────────────


def sign_credential(credential, private_key_hex):
    """
    Sign a credential following the W3C Data Integrity ECDSA §3.3 algorithm.

    ``credential`` must already contain a ``proof`` block with all fields
    EXCEPT ``proofValue``.  Returns a new dict with ``proof.proofValue`` set.

    Algorithm:
      1. RDFC-1.0-canonicalize the proof options (with credential's @context)
      2. SHA-256 → proofHash (32 bytes)
      3. RDFC-1.0-canonicalize the document (without proof key)
      4. SHA-256 → documentHash (32 bytes)
      5. ECDSA-secp256k1.sign(proofHash + documentHash)  [64 bytes input]
      6. Encode as multibase base58btc (prefix 'z')
    """
    import base58
    from coincurve import PrivateKey

    context = credential.get("@context", [])
    proof_config = {k: v for k, v in credential["proof"].items() if k != "proofValue"}
    loader = _make_document_loader()

    # Step 1-2: canonicalize and hash the proof options
    proof_options_doc = {"@context": context, **proof_config}
    canonical_proof = rdfc_canonicalize(proof_options_doc, loader)
    proof_hash = hashlib.sha256(canonical_proof.encode("utf-8")).digest()

    # Step 3-4: canonicalize and hash the document (without proof)
    doc_without_proof = {k: v for k, v in credential.items() if k != "proof"}
    canonical_doc = rdfc_canonicalize(doc_without_proof, loader)
    doc_hash = hashlib.sha256(canonical_doc.encode("utf-8")).digest()

    # Step 5: sign the concatenated 64-byte hash
    hash_data = proof_hash + doc_hash
    key = PrivateKey.from_hex(private_key_hex)
    sig_bytes = key.sign(hash_data)  # RFC 6979 deterministic ECDSA

    # Step 6: multibase base58btc
    proof_value = "z" + base58.b58encode(sig_bytes).decode("ascii")

    result = dict(credential)
    result["proof"] = {**proof_config, "proofValue": proof_value}
    return result
