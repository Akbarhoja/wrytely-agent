import time

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from shared.auth import AuthenticationError, ClerkSessionVerifier
from shared.config import Settings


@pytest.fixture(scope="module")
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = (
        private.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    return private, public


def claims():
    now = int(time.time())
    return {
        "sub": "user_alice",
        "sid": "sess_alice",
        "iss": "https://clerk.example.test",
        "azp": "https://agent.example.test",
        "exp": now + 60,
        "nbf": now - 1,
        "iat": now - 1,
    }


def verifier(keys):
    return ClerkSessionVerifier(
        Settings(
            clerk_issuer="https://clerk.example.test",
            clerk_jwt_key=keys[1],
            authorized_parties=["https://agent.example.test"],
        )
    )


def test_valid_signed_session(keys):
    token = jwt.encode(claims(), keys[0], algorithm="RS256")
    assert verifier(keys).verify(token).user_id == "user_alice"


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": 1},
        {"nbf": 9999999999},
        {"iat": 9999999999},
        {"iss": "https://attacker.test"},
        {"azp": "https://attacker.test"},
        {"sub": "someone"},
        {"sid": "machine"},
        {"sts": "pending"},
    ],
)
def test_bad_claims_rejected(keys, overrides):
    token = jwt.encode(claims() | overrides, keys[0], algorithm="RS256")
    with pytest.raises(AuthenticationError):
        verifier(keys).verify(token)


@pytest.mark.parametrize("missing", ["sid", "sub", "iss", "exp", "nbf", "azp", "iat"])
def test_missing_required_claim_rejected(keys, missing):
    payload = claims()
    del payload[missing]
    with pytest.raises(AuthenticationError):
        verifier(keys).verify(jwt.encode(payload, keys[0], algorithm="RS256"))


def test_algorithm_confusion_rejected(keys):
    token = jwt.encode(claims(), "attacker-secret", algorithm="HS256")
    with pytest.raises(AuthenticationError):
        verifier(keys).verify(token)


def test_wrong_signing_key_rejected(keys):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    with pytest.raises(AuthenticationError):
        verifier(keys).verify(jwt.encode(claims(), other, algorithm="RS256"))


def test_unconfigured_auth_fails_closed():
    with pytest.raises(AuthenticationError):
        ClerkSessionVerifier(Settings()).verify("anything")
