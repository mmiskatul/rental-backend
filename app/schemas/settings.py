from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class BusinessSettings(BaseModel):
    company_name: str = Field(min_length=1, max_length=120)
    support_email: EmailStr
    support_phone: str = Field(min_length=1, max_length=40)
    business_hours: str = Field(min_length=1, max_length=120)
    hq_address: str = Field(min_length=1, max_length=200)
    about: str = Field(min_length=1, max_length=1000)


class BookingPolicySettings(BaseModel):
    auto_approve_verified_customers: bool
    require_deposit: bool
    allow_same_day_bookings: bool
    enforce_minimum_rental_period: bool


class CancellationSettings(BaseModel):
    free_cancellation_hours: int = Field(ge=0, le=720)
    late_cancellation_fee_percent: int = Field(ge=0, le=100)
    no_show_fee: str = Field(min_length=1, max_length=80)
    refund_processing_time: str = Field(min_length=1, max_length=80)


class PricingSettings(BaseModel):
    service_fee_percent: int = Field(ge=0, le=100)
    tax_rate_percent: int = Field(ge=0, le=100)
    weekly_discount_percent: int = Field(ge=0, le=100)
    monthly_discount_percent: int = Field(ge=0, le=100)


class NotificationSettings(BaseModel):
    email_new_bookings: bool
    sms_urgent_alerts: bool
    daily_summary_report: bool


class AdminSettingsPublic(BaseModel):
    business: BusinessSettings
    booking_policy: BookingPolicySettings
    cancellation: CancellationSettings
    pricing: PricingSettings
    notifications: NotificationSettings
    updated_at: datetime


class AdminSettingsUpdate(BaseModel):
    business: BusinessSettings | None = None
    booking_policy: BookingPolicySettings | None = None
    cancellation: CancellationSettings | None = None
    pricing: PricingSettings | None = None
    notifications: NotificationSettings | None = None
