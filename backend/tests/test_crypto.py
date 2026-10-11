import base64
import secrets

import pytest

from app.services import crypto

KEY = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
OTHER = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()


def test_round_trip_with_binding():
    sealed = crypto.encrypt("1000.refresh.token", KEY, aad="user-1")
    assert sealed != "1000.refresh.token"
    assert crypto.decrypt(sealed, KEY, aad="user-1") == "1000.refresh.token"


def test_each_encryption_is_different():
    assert crypto.encrypt("x", KEY) != crypto.encrypt("x", KEY)


def test_wrong_key_or_wrong_user_fails():
    sealed = crypto.encrypt("secret", KEY, aad="user-1")
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(sealed, OTHER, aad="user-1")
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt(sealed, KEY, aad="user-2")


def test_bad_key_material_is_a_config_error():
    with pytest.raises(crypto.CryptoError):
        crypto.encrypt("x", "not-32-bytes")
    with pytest.raises(crypto.CryptoError):
        crypto.decrypt("garbage", KEY)
