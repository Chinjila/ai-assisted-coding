"""
Unit tests for JWT authentication helpers.
"""

import pytest
from unittest.mock import patch
from jose import jwt

from backend.app.api import create_access_token, verify_token
from backend.app import config
from backend.app.errors import AuthenticationError


class TestCreateAccessToken:
    def test_creates_valid_jwt(self):
        token = create_access_token({"sub": "testuser"})
        assert isinstance(token, str)
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_token_contains_custom_data(self):
        token = create_access_token({"sub": "admin", "role": "superuser"})
        payload = jwt.decode(token, config.JWT_SECRET_KEY, algorithms=[config.JWT_ALGORITHM])
        assert payload["sub"] == "admin"
        assert payload["role"] == "superuser"


class TestVerifyToken:
    def test_verify_valid_token(self):
        token = create_access_token({"sub": "testuser"})
        payload = verify_token(token)
        assert payload["sub"] == "testuser"

    def test_verify_invalid_token(self):
        with pytest.raises(AuthenticationError):
            verify_token("invalid.token.string")

    def test_verify_tampered_token(self):
        token = create_access_token({"sub": "testuser"})
        # Tamper with the token
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(AuthenticationError):
            verify_token(tampered)
