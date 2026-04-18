from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_password_strength(value: str) -> str:
    has_letter = any(character.isalpha() for character in value)
    has_number = any(character.isdigit() for character in value)
    if not has_letter or not has_number:
        raise ValueError("Password must contain at least one letter and one number.")
    return value


class UserRole(StrEnum):
    customer = "customer"
    landlord = "landlord"
    admin = "admin"


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=30)
    role: UserRole = UserRole.customer

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        return validate_password_strength(value)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8, max_length=128)

    _validate_password_strength = field_validator("new_password")(validate_password_strength)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)

    _validate_password_strength = field_validator("new_password")(validate_password_strength)


class ProfileUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=80)
    phone: str | None = Field(default=None, max_length=30)


class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class UserPublic(BaseModel):
    id: str
    name: str
    email: EmailStr
    phone: str | None = None
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponse(BaseModel):
    user: UserPublic
    tokens: TokenPair


class RegisterResponse(BaseModel):
    message: str
    email: EmailStr
    redirect_to: str = "/verify-email"


class MessageResponse(BaseModel):
    message: str
