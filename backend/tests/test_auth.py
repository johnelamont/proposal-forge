"""JWT verification: asymmetric (Supabase default) and legacy HS256."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jwt import PyJWK
from jwt.algorithms import ECAlgorithm

from app.core import auth
from app.core.config import Settings

SETTINGS = Settings(
    supabase_url="http://127.0.0.1:54321",
    supabase_jwt_secret="x" * 40,
    _env_file=None,
)


def _claims(**extra):
    now = int(time.time())
    return {
        "sub": "user-123",
        "aud": "authenticated",
        "role": "authenticated",
        "iat": now,
        "exp": now + 600,
        **extra,
    }


@pytest.fixture
def es256(monkeypatch):
    """A fresh EC keypair, with the JWKS client patched to return its public key."""
    private = ec.generate_private_key(ec.SECP256R1())
    public_jwk = PyJWK.from_dict(
        {**ECAlgorithm.to_jwk(private.public_key(), as_dict=True), "kid": "k1"}
    )

    class FakeJwkClient:
        def get_signing_key_from_jwt(self, token):
            return public_jwk

    monkeypatch.setattr(auth, "_jwk_client", lambda url: FakeJwkClient())
    return private


def test_es256_token_is_accepted(es256):
    token = jwt.encode(_claims(), es256, algorithm="ES256", headers={"kid": "k1"})
    claims = auth.verify_token(token, SETTINGS)
    assert claims["sub"] == "user-123"


def test_es256_token_signed_by_another_key_is_rejected(es256):
    other = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(_claims(), other, algorithm="ES256", headers={"kid": "k1"})
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(token, SETTINGS)
    assert exc.value.status_code == 401


def test_expired_token_is_rejected(es256):
    token = jwt.encode(_claims(exp=int(time.time()) - 10), es256, algorithm="ES256")
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(token, SETTINGS)
    assert exc.value.status_code == 401


def test_wrong_audience_is_rejected(es256):
    token = jwt.encode(_claims(aud="anon"), es256, algorithm="ES256")
    with pytest.raises(HTTPException):
        auth.verify_token(token, SETTINGS)


def test_hs256_legacy_token_is_accepted():
    token = jwt.encode(_claims(), SETTINGS.supabase_jwt_secret, algorithm="HS256")
    assert auth.verify_token(token, SETTINGS)["sub"] == "user-123"


def test_hs256_with_wrong_secret_is_rejected():
    token = jwt.encode(_claims(), "not-the-secret-" * 3, algorithm="HS256")
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(token, SETTINGS)
    assert exc.value.status_code == 401


def test_unsigned_token_is_rejected():
    token = jwt.encode(_claims(), key=None, algorithm="none")
    with pytest.raises(HTTPException) as exc:
        auth.verify_token(token, SETTINGS)
    assert exc.value.status_code == 401


def test_garbage_is_rejected():
    with pytest.raises(HTTPException) as exc:
        auth.verify_token("not.a.jwt", SETTINGS)
    assert exc.value.status_code == 401
