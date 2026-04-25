import pytest
from pydantic import ValidationError
from app.schemas.auth import UserCreate, Token


def test_user_create_valid():
    user = UserCreate(email="alice@example.com", password="securepass", tenant_name="Acme")
    assert user.email == "alice@example.com"
    assert user.tenant_name == "Acme"


def test_user_create_short_password():
    with pytest.raises(ValidationError) as exc_info:
        UserCreate(email="bob@example.com", password="short", tenant_name="Acme")
    assert "at least 8 characters" in str(exc_info.value)


def test_token_default_type():
    token = Token(access_token="abc123")
    assert token.token_type == "bearer"
