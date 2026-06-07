"""
Tests del cifrado en reposo del token store OAuth.

El cifrador se inyecta vía monkeypatch de _resolve_cipher para no depender del
keyring del SO en CI.
"""

import json

from cryptography.fernet import Fernet

from loombit_operator import skill_blanca_oauth as ob


def test_token_store_encrypts_secrets_at_rest(tmp_path, monkeypatch):
    cipher = Fernet(Fernet.generate_key())
    monkeypatch.setattr(ob, "_resolve_cipher", lambda: cipher)

    store = ob.OAuthTokenStore(tmp_path / "tokens.json")
    store.store_token(
        "google",
        {"access_token": "SECRET-AT", "refresh_token": "SECRET-RT", "expires_in": 3600},
    )

    raw = (tmp_path / "tokens.json").read_text(encoding="utf-8")
    assert raw.startswith("LBENC1:")
    assert "SECRET-AT" not in raw
    assert "SECRET-RT" not in raw

    # Round-trip: se descifra y se recupera el secreto
    assert store.token_for("google")["access_token"] == "SECRET-AT"
    assert store.token_for("google")["refresh_token"] == "SECRET-RT"


def test_token_store_plaintext_when_no_keystore(tmp_path, monkeypatch):
    monkeypatch.setattr(ob, "_resolve_cipher", lambda: None)

    store = ob.OAuthTokenStore(tmp_path / "tokens.json")
    store.store_token("google", {"access_token": "AT", "expires_in": 3600})

    raw = (tmp_path / "tokens.json").read_text(encoding="utf-8")
    assert raw.lstrip().startswith("{")  # JSON en claro (fallback)
    assert store.token_for("google")["access_token"] == "AT"


def test_token_store_reads_legacy_plaintext_even_with_cipher(tmp_path, monkeypatch):
    path = tmp_path / "tokens.json"
    path.write_text(
        json.dumps(
            {
                "providers": {"google": {"provider": "google", "access_token": "LEGACY"}},
                "pending_authorizations": {},
            }
        ),
        encoding="utf-8",
    )

    cipher = Fernet(Fernet.generate_key())
    monkeypatch.setattr(ob, "_resolve_cipher", lambda: cipher)

    store = ob.OAuthTokenStore(path)
    assert store.token_for("google")["access_token"] == "LEGACY"


def test_encrypted_store_unreadable_without_key(tmp_path, monkeypatch):
    cipher = Fernet(Fernet.generate_key())
    monkeypatch.setattr(ob, "_resolve_cipher", lambda: cipher)
    store = ob.OAuthTokenStore(tmp_path / "tokens.json")
    store.store_token("google", {"access_token": "AT", "expires_in": 3600})

    # Sin clave (otro equipo / keyring caído) → no se filtra el token
    monkeypatch.setattr(ob, "_resolve_cipher", lambda: None)
    assert store.token_for("google") == {}
