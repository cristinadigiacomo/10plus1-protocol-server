"""
Phase 1 — HMAC-SHA256 posture declaration signer.

Adapted from governance/src/hmac_signer/signer.py. The algorithm is identical —
HMAC-SHA256 over canonical JSON with sort_keys. The only difference is the
payload type: Protocol signs HandshakeDeclaration objects rather than
governance Event objects.

The signature covers the canonical JSON of the declaration with the
'signature' and 'signed_at' fields excluded (you cannot sign a payload that
contains its own signature). The 'context_summary' field IS covered —
if someone alters the human-readable summary after signing, verification fails.

Key management
--------------
The HMAC key is a 32-byte secret stored as hex in a key file (path configured
via PROTOCOL_HMAC_KEY_PATH env var, default .protocol.key). The file is
gitignored. load_key() reads the hex and rejects keys shorter than 32 bytes.

Authoritative sources
---------------------
PATTERNS.md PATTERN-001
DECISIONS.md DEC-007
"""

from __future__ import annotations

import hmac as _stdlib_hmac
import hashlib
from datetime import datetime, timezone
from pathlib import Path

from schema.declaration import HandshakeDeclaration


MIN_KEY_BYTES = 32  # 256 bits — matches HMAC-SHA256 output size


class ProtocolSigningError(Exception):
    """Raised when signing or verification of a declaration fails."""


def load_key(path: str | Path) -> bytes:
    """Load an HMAC key from a hex file.

    The file must contain a hex string (whitespace tolerated) that decodes to
    at least 32 bytes. Raises ValueError or FileNotFoundError on any issue.
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"HMAC key file not found: {p}")
    hex_text = p.read_text(encoding="utf-8").strip()
    if not hex_text:
        raise ValueError(f"HMAC key file is empty: {p}")
    try:
        key = bytes.fromhex(hex_text)
    except ValueError as exc:
        raise ValueError(f"HMAC key file {p} is not valid hex: {exc}") from None
    if len(key) < MIN_KEY_BYTES:
        raise ValueError(
            f"HMAC key is {len(key)} bytes; need at least {MIN_KEY_BYTES}."
        )
    return key


def generate_key_hex() -> str:
    """Generate a new 32-byte HMAC key and return it as a hex string.

    Use this once to create a key file:
        python -c "from src.signer.signer import generate_key_hex; \
                   open('.protocol.key','w').write(generate_key_hex())"
    """
    import secrets
    return secrets.token_bytes(32).hex()


def _compute_hmac(declaration: HandshakeDeclaration, key: bytes) -> str:
    """Compute HMAC-SHA256 hex digest over the declaration's signing payload."""
    if not isinstance(key, (bytes, bytearray)):
        raise TypeError("key must be bytes")
    if len(key) < MIN_KEY_BYTES:
        raise ValueError(f"key must be >= {MIN_KEY_BYTES} bytes")
    payload = declaration.signing_payload()
    return _stdlib_hmac.new(key, payload, hashlib.sha256).hexdigest()


def sign_declaration(declaration: HandshakeDeclaration, key: bytes) -> HandshakeDeclaration:
    """Return a copy of the declaration with 'signature' and 'signed_at' populated.

    The original is not mutated. Signing a declaration that is already signed
    re-signs it (updates both signature and signed_at).
    """
    digest   = _compute_hmac(declaration, key)
    signed_at = datetime.now(timezone.utc).isoformat()
    return declaration.model_copy(update={"signature": digest, "signed_at": signed_at})


def verify_declaration(declaration: HandshakeDeclaration, key: bytes) -> bool:
    """Verify the declaration's HMAC. Returns True on match; raises on mismatch.

    Raising (rather than returning False) is deliberate: a silent False is easy
    to miss, and a failed HMAC is a security-relevant event that must not be
    swallowed silently. Callers who want a boolean should catch ProtocolSigningError.
    """
    if not declaration.is_signed():
        raise ProtocolSigningError(
            f"Declaration {declaration.id} has no signature — "
            "call sign_declaration() before verifying."
        )
    expected = _compute_hmac(declaration, key)
    if not _stdlib_hmac.compare_digest(expected, declaration.signature.lower()):
        raise ProtocolSigningError(
            f"HMAC mismatch for declaration {declaration.id} — "
            "signature does not match recomputed digest. "
            "The declaration may have been tampered with."
        )
    return True
