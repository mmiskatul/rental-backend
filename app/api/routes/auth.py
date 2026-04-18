from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_reset_token,
    hash_token,
    make_reset_token,
    make_verification_code,
    verify_password,
)
from app.db.mongodb import get_users_collection
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    ProfileUpdateRequest,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenPair,
    UserPublic,
    VerifyEmailRequest,
)
from app.services.email import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/api/auth", tags=["authentication"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"


async def get_current_user(
    request: Request,
    bearer_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
) -> dict:
    token = bearer_token or request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token is required.")

    claims = decode_token(token, settings.jwt_access_secret)
    if claims.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token.")

    user = await find_user_by_id(claims["sub"])
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")
    ensure_user_can_authenticate(user)
    return user


async def get_optional_current_user(request: Request) -> dict | None:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        return None
    try:
        return await get_current_user(request)
    except HTTPException:
        return None


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(payload: RegisterRequest) -> RegisterResponse:
    if payload.role == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin accounts are seeded by the backend.")

    users = get_users_collection()
    now = datetime.now(timezone.utc)
    code = make_verification_code()
    document = {
        "name": payload.name,
        "email": payload.email.lower(),
        "phone": payload.phone,
        "role": payload.role,
        "password_hash": hash_password(payload.password),
        "is_active": True,
        "is_verified": False,
        "verification_code_hash": hash_token(code),
        "verification_code_expires_at": now + settings.verification_code_delta,
        "created_at": now,
        "updated_at": now,
    }

    try:
        await users.insert_one(document)
    except DuplicateKeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        ) from exc

    await send_verification_email(document["email"], code)
    return RegisterResponse(
        message="Account created. Enter the verification code sent to your email.",
        email=document["email"],
    )


@router.post("/verify-email", response_model=AuthResponse)
async def verify_email(payload: VerifyEmailRequest, response: Response) -> AuthResponse:
    users = get_users_collection()
    user = await users.find_one(
        {
            "email": payload.email.lower(),
            "verification_code_hash": hash_token(payload.code),
            "verification_code_expires_at": {"$gt": datetime.now(timezone.utc)},
        }
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Verification code is invalid or expired.")

    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "is_verified": True,
                "updated_at": datetime.now(timezone.utc),
            },
            "$unset": {"verification_code_hash": "", "verification_code_expires_at": ""},
        },
    )
    user["is_verified"] = True
    tokens = await issue_tokens(user)
    set_auth_cookies(response, tokens)
    return AuthResponse(user=serialize_user(user), tokens=tokens)


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(payload: ResendVerificationRequest) -> MessageResponse:
    users = get_users_collection()
    user = await find_user_by_email(payload.email)
    if not user:
        return MessageResponse(message="If this account exists, a new verification code has been sent.")
    if user.get("is_verified", False):
        return MessageResponse(message="This account is already verified.")

    code = make_verification_code()
    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "verification_code_hash": hash_token(code),
                "verification_code_expires_at": datetime.now(timezone.utc) + settings.verification_code_delta,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    await send_verification_email(user["email"], code)
    return MessageResponse(message="A new verification code has been sent.")


@router.post("/login", response_model=AuthResponse)
async def login(payload: LoginRequest, response: Response) -> AuthResponse:
    user = await find_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    ensure_user_can_authenticate(user)

    tokens = await issue_tokens(user)
    set_auth_cookies(response, tokens)
    return AuthResponse(user=serialize_user(user), tokens=tokens)


@router.get("/me", response_model=UserPublic)
async def me(current_user: Annotated[dict, Depends(get_current_user)]) -> UserPublic:
    return serialize_user(current_user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = Body(default=None),
) -> TokenPair:
    refresh_token = payload.refresh_token if payload else None
    refresh_token = refresh_token or request.cookies.get(REFRESH_COOKIE)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is required.")

    claims = decode_token(refresh_token, settings.jwt_refresh_secret)
    if claims.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")

    user = await find_user_by_id(claims["sub"])
    if not user or user.get("refresh_token_hash") != hash_token(refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token.")
    ensure_user_can_authenticate(user)

    tokens = await issue_tokens(user)
    set_auth_cookies(response, tokens)
    return tokens


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response, current_user: Annotated[dict | None, Depends(get_optional_current_user)]) -> MessageResponse:
    if current_user:
        await get_users_collection().update_one(
            {"_id": current_user["_id"]},
            {"$unset": {"refresh_token_hash": "", "refresh_token_expires_at": ""}},
        )
    clear_auth_cookies(response)
    return MessageResponse(message="Logged out successfully.")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(payload: ForgotPasswordRequest) -> MessageResponse:
    users = get_users_collection()
    user = await find_user_by_email(payload.email)

    if user:
        reset_code = make_verification_code()
        await users.update_one(
            {"_id": user["_id"]},
            {
                "$set": {
                    "reset_token_hash": hash_reset_token(reset_code),
                    "reset_token_expires_at": datetime.now(timezone.utc) + settings.reset_token_delta,
                    "updated_at": datetime.now(timezone.utc),
                }
            },
        )
        await send_password_reset_email(user["email"], reset_code)

    return MessageResponse(message="If this email exists, a password reset code has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(payload: ResetPasswordRequest) -> MessageResponse:
    users = get_users_collection()
    user = await users.find_one(
        {
            "email": payload.email.lower(),
            "reset_token_hash": hash_reset_token(payload.code),
            "reset_token_expires_at": {"$gt": datetime.now(timezone.utc)},
        }
    )

    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reset code is invalid or expired.")

    await users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "updated_at": datetime.now(timezone.utc),
            },
            "$unset": {
                "reset_token_hash": "",
                "reset_token_expires_at": "",
                "refresh_token_hash": "",
                "refresh_token_expires_at": "",
            },
        },
    )
    return MessageResponse(message="Password reset successfully.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    payload: ChangePasswordRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MessageResponse:
    if not verify_password(payload.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect.")

    await get_users_collection().update_one(
        {"_id": current_user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(payload.new_password),
                "updated_at": datetime.now(timezone.utc),
            },
            "$unset": {"refresh_token_hash": "", "refresh_token_expires_at": ""},
        },
    )
    return MessageResponse(message="Password changed successfully. Sign in again on other devices.")


@router.patch("/profile", response_model=UserPublic)
async def update_profile(
    payload: ProfileUpdateRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> UserPublic:
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        return serialize_user(current_user)

    updates["updated_at"] = datetime.now(timezone.utc)
    await get_users_collection().update_one({"_id": current_user["_id"]}, {"$set": updates})
    updated = await find_user_by_id(str(current_user["_id"]))
    return serialize_user(updated)


async def find_user_by_email(email: str) -> dict | None:
    return await get_users_collection().find_one({"email": email.lower()})


async def find_user_by_id(user_id: str) -> dict | None:
    if not ObjectId.is_valid(user_id):
        return None
    return await get_users_collection().find_one({"_id": ObjectId(user_id)})


async def issue_tokens(user: dict) -> TokenPair:
    tokens = create_tokens(user)
    await get_users_collection().update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "refresh_token_hash": hash_token(tokens.refresh_token),
                "refresh_token_expires_at": datetime.now(timezone.utc) + settings.refresh_token_delta,
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return tokens


def ensure_user_can_authenticate(user: dict) -> None:
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled.")
    if not user.get("is_verified", False):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account email is not verified.")


def create_tokens(user: dict) -> TokenPair:
    user_id = str(user["_id"])
    return TokenPair(
        access_token=create_access_token(user_id, user["email"], user["role"]),
        refresh_token=create_refresh_token(user_id, user["email"], user["role"]),
        token_type="bearer",
    )


def set_auth_cookies(response: Response, tokens: TokenPair) -> None:
    secure = settings.app_env == "production"
    response.set_cookie(
        ACCESS_COOKIE,
        tokens.access_token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        tokens.refresh_token,
        max_age=settings.refresh_token_expire_days * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/auth",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/auth")


def serialize_user(user: dict) -> UserPublic:
    return UserPublic(
        id=str(user["_id"]),
        name=user["name"],
        email=user["email"],
        phone=user.get("phone"),
        role=user["role"],
        is_active=user.get("is_active", True),
        is_verified=user.get("is_verified", False),
        created_at=user["created_at"],
        updated_at=user["updated_at"],
    )
