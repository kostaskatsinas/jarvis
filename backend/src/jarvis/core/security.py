"""Password hashing (argon2) and JWT creation/verification.

Stateless tokens: short-lived access tokens in the Authorization header,
a longer-lived refresh token in an httponly cookie. Single user, no
server-side session store — revocation is "rotate JARVIS_SECRET_KEY",
which is an acceptable trade at this scale.
"""

import time

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import Argon2Error, InvalidHashError, VerifyMismatchError

from jarvis.config import get_settings

_hasher = PasswordHasher()

ACCESS = "access"
REFRESH = "refresh"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, Argon2Error):
        return False


class InvalidToken(Exception):
    pass


def create_token(subject: str, token_type: str, ttl_seconds: int) -> str:
    now = int(time.time())
    payload = {"sub": subject, "type": token_type, "iat": now, "exp": now + ttl_seconds}
    return jwt.encode(payload, get_settings().secret_key, algorithm="HS256")


def decode_token(token: str, expected_type: str) -> str:
    """Return the subject (user email) or raise InvalidToken."""
    try:
        payload = jwt.decode(token, get_settings().secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise InvalidToken(str(exc))
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise InvalidToken("wrong token type")
    return payload["sub"]
