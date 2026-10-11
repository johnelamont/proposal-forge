"""Encryption at rest for per-user secrets (F6 refresh tokens).

AES-256-GCM with a random 96-bit nonce per value; the stored form is
base64url(nonce || ciphertext || tag). The key is TOKEN_ENCRYPTION_KEY (32
random bytes, base64url), held only by the backend. Rotating the key means
re-encrypting stored values; losing it means every user must reconnect.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12


class CryptoError(Exception):
    pass


def _key(b64: str) -> bytes:
    try:
        raw = base64.urlsafe_b64decode(b64 + "=" * (-len(b64) % 4))
    except Exception as e:  # noqa: BLE001 - any decode failure is a config error
        raise CryptoError("TOKEN_ENCRYPTION_KEY is not valid base64") from e
    if len(raw) != 32:
        raise CryptoError("TOKEN_ENCRYPTION_KEY must decode to 32 bytes")
    return raw


def encrypt(plaintext: str, key_b64: str, *, aad: str = "") -> str:
    nonce = os.urandom(NONCE_BYTES)
    sealed = AESGCM(_key(key_b64)).encrypt(
        nonce, plaintext.encode("utf-8"), aad.encode("utf-8") or None
    )
    return base64.urlsafe_b64encode(nonce + sealed).decode("ascii")


def decrypt(token: str, key_b64: str, *, aad: str = "") -> str:
    try:
        raw = base64.urlsafe_b64decode(token)
        nonce, sealed = raw[:NONCE_BYTES], raw[NONCE_BYTES:]
        return (
            AESGCM(_key(key_b64))
            .decrypt(nonce, sealed, aad.encode("utf-8") or None)
            .decode("utf-8")
        )
    except InvalidTag as e:
        raise CryptoError("Stored token does not match this key") from e
    except CryptoError:
        raise
    except Exception as e:  # noqa: BLE001
        raise CryptoError("Stored token is malformed") from e
