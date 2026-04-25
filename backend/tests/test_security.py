import pytest
from datetime import timedelta
from jose import JWTError

from app.core.security import hash_password, verify_password, create_access_token, decode_token


def test_hash_and_verify():
    hashed = hash_password("mysecret1")
    assert verify_password("mysecret1", hashed) is True


def test_wrong_password():
    hashed = hash_password("mysecret1")
    assert verify_password("wrongpass", hashed) is False


def test_token_roundtrip():
    token = create_access_token({"sub": "user-123"})
    data = decode_token(token)
    assert data.user_id == "user-123"


def test_token_expired():
    token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(minutes=-1))
    with pytest.raises(JWTError):
        decode_token(token)
