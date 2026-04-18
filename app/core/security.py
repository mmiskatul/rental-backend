from datetime import datetime, timedelta, timezone
from hashlib import sha256
from random import SystemRandom
from secrets import token_urlsafe

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from fastapi import HTTPException, status


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerifyMismatchError):
        return False


def create_access_token(user_id: str, email: str, role: str) -> str:
    from app.core.config import settings

    return create_token(user_id, email, role, "access", settings.jwt_access_secret, settings.access_token_delta)


def create_refresh_token(user_id: str, email: str, role: str) -> str:
    from app.core.config import settings

    return create_token(user_id, email, role, "refresh", settings.jwt_refresh_secret, settings.refresh_token_delta)


def create_token(user_id: str, email: str, role: str, token_type: str, secret: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "email": email,
        "role": role,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token is invalid or expired.") from exc


def make_reset_token() -> str:
    return token_urlsafe(32)


def hash_reset_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


def make_verification_code() -> str:
    return f"{SystemRandom().randint(100000, 999999)}"


def hash_token(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()
