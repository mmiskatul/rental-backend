from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class CustomerProfileSettings(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    address: str | None = Field(default=None, max_length=200)


class CustomerPreferenceSettings(BaseModel):
    booking_confirmations: bool
    promotional_emails: bool
    sms_reminders: bool


class CustomerStats(BaseModel):
    total_bookings: int
    total_spend: float
    average_rating: float


class CustomerSettingsPublic(BaseModel):
    profile: CustomerProfileSettings
    preferences: CustomerPreferenceSettings
    stats: CustomerStats
    updated_at: datetime


class CustomerSettingsUpdate(BaseModel):
    profile: CustomerProfileSettings | None = None
    preferences: CustomerPreferenceSettings | None = None
