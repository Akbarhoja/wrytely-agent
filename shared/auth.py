import jwt

from contracts.models import Identity
from shared.config import Settings


class AuthenticationError(Exception):
    pass


class ClerkSessionVerifier:
    """Manual RS256 session verification against the existing Clerk instance's public key.

    Bearer-only: the API does not accept cookies or a client-supplied user ID.
    Public key rotation requires updating configuration in this initial implementation.
    """

    def __init__(self, settings: Settings):
        self.settings = settings

    def verify(self, token: str) -> Identity:
        s = self.settings
        if not s.readiness()["authentication"]:
            raise AuthenticationError("Authentication is not configured")
        try:
            claims = jwt.decode(
                token,
                s.clerk_jwt_key.get_secret_value().replace("\\n", "\n"),
                algorithms=["RS256"],
                issuer=s.clerk_issuer,
                options={
                    "require": ["exp", "nbf", "iat", "iss", "sub", "sid", "azp"],
                    "verify_aud": False,
                },
            )
            if claims["azp"] not in s.authorized_parties:
                raise AuthenticationError("Origin not authorized")
            if claims.get("sts") == "pending":
                raise AuthenticationError("Session is pending")
            if not str(claims["sub"]).startswith("user_") or not str(claims["sid"]).startswith(
                "sess_"
            ):
                raise AuthenticationError("Session identity is invalid")
            return Identity(user_id=claims["sub"], session_id=claims["sid"])
        except jwt.InvalidTokenError as exc:
            raise AuthenticationError("Invalid session") from exc
