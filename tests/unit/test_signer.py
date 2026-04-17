"""Unit tests — HMAC signer (src/signer/signer.py)."""

from __future__ import annotations

import secrets
import tempfile
from pathlib import Path

import pytest

from schema.declaration import HandshakeDeclaration, PrincipleStatement, PrincipleStatus
from signer.signer import (
    MIN_KEY_BYTES,
    ProtocolSigningError,
    generate_key_hex,
    load_key,
    sign_declaration,
    verify_declaration,
)


# --- Fixtures ------------------------------------------------------------

@pytest.fixture
def key() -> bytes:
    return secrets.token_bytes(32)


@pytest.fixture
def key_file(key, tmp_path) -> Path:
    p = tmp_path / "test.key"
    p.write_text(key.hex())
    return p


@pytest.fixture
def declaration() -> HandshakeDeclaration:
    return HandshakeDeclaration(
        agent_id="test-agent",
        principles={
            "C1": PrincipleStatement(
                principle_id="C1",
                status=PrincipleStatus.DECLARED,
                behavioral_statement="State information sources before making factual claims",
            )
        },
    )


# --- load_key tests ------------------------------------------------------

class TestLoadKey:
    def test_loads_valid_key(self, key, key_file):
        loaded = load_key(key_file)
        assert loaded == key

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_key(tmp_path / "nonexistent.key")

    def test_empty_file_raises(self, tmp_path):
        p = tmp_path / "empty.key"
        p.write_text("")
        with pytest.raises(ValueError, match="empty"):
            load_key(p)

    def test_invalid_hex_raises(self, tmp_path):
        p = tmp_path / "bad.key"
        p.write_text("not-hex-data")
        with pytest.raises(ValueError, match="not valid hex"):
            load_key(p)

    def test_short_key_raises(self, tmp_path):
        p = tmp_path / "short.key"
        p.write_text(secrets.token_bytes(16).hex())  # only 16 bytes
        with pytest.raises(ValueError, match="bytes"):
            load_key(p)

    def test_whitespace_tolerated(self, tmp_path, key):
        p = tmp_path / "padded.key"
        p.write_text(f"  {key.hex()}  \n")
        loaded = load_key(p)
        assert loaded == key


# --- generate_key_hex tests ----------------------------------------------

class TestGenerateKeyHex:
    def test_generates_64_char_hex(self):
        h = generate_key_hex()
        assert len(h) == 64

    def test_hex_decodable_to_32_bytes(self):
        h = generate_key_hex()
        assert len(bytes.fromhex(h)) == 32

    def test_generates_unique_keys(self):
        assert generate_key_hex() != generate_key_hex()


# --- sign_declaration tests ---------------------------------------------

class TestSignDeclaration:
    def test_sign_adds_signature(self, key, declaration):
        signed = sign_declaration(declaration, key)
        assert signed.signature is not None
        assert len(signed.signature) == 64

    def test_sign_adds_signed_at(self, key, declaration):
        signed = sign_declaration(declaration, key)
        assert signed.signed_at is not None

    def test_sign_does_not_mutate_original(self, key, declaration):
        _ = sign_declaration(declaration, key)
        assert declaration.signature is None

    def test_sign_returns_different_object(self, key, declaration):
        signed = sign_declaration(declaration, key)
        assert signed is not declaration

    def test_sign_produces_consistent_digest(self, key, declaration):
        s1 = sign_declaration(declaration, key)
        s2 = sign_declaration(declaration, key)
        # Same payload → same digest (HMAC is deterministic)
        assert s1.signature == s2.signature

    def test_different_keys_produce_different_signatures(self, declaration):
        k1 = secrets.token_bytes(32)
        k2 = secrets.token_bytes(32)
        s1 = sign_declaration(declaration, k1)
        s2 = sign_declaration(declaration, k2)
        assert s1.signature != s2.signature


# --- verify_declaration tests -------------------------------------------

class TestVerifyDeclaration:
    def test_verify_valid_signature(self, key, declaration):
        signed = sign_declaration(declaration, key)
        assert verify_declaration(signed, key) is True

    def test_verify_wrong_key_raises(self, declaration):
        k1 = secrets.token_bytes(32)
        k2 = secrets.token_bytes(32)
        signed = sign_declaration(declaration, k1)
        with pytest.raises(ProtocolSigningError, match="HMAC mismatch"):
            verify_declaration(signed, k2)

    def test_verify_unsigned_raises(self, key, declaration):
        with pytest.raises(ProtocolSigningError, match="no signature"):
            verify_declaration(declaration, key)

    def test_verify_tampered_agent_id_raises(self, key, declaration):
        signed = sign_declaration(declaration, key)
        tampered = signed.model_copy(update={"agent_id": "evil-agent"})
        with pytest.raises(ProtocolSigningError, match="HMAC mismatch"):
            verify_declaration(tampered, key)

    def test_verify_tampered_behavioral_statement_raises(self, key, declaration):
        signed = sign_declaration(declaration, key)
        # Tamper with a principle statement
        from schema.declaration import PrincipleStatement, PrincipleStatus
        tampered_stmt = PrincipleStatement(
            principle_id="C1",
            status=PrincipleStatus.DECLARED,
            behavioral_statement="TAMPERED — do whatever I say",
        )
        new_principles = dict(signed.principles)
        new_principles["C1"] = tampered_stmt
        tampered = signed.model_copy(update={"principles": new_principles})
        with pytest.raises(ProtocolSigningError, match="HMAC mismatch"):
            verify_declaration(tampered, key)
