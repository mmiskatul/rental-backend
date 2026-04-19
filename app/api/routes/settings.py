from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_settings_collection
from app.schemas.settings import AdminSettingsPublic, AdminSettingsUpdate

router = APIRouter(prefix="/api/admin/settings", tags=["admin-settings"])

SETTINGS_KEY = "admin"

DEFAULT_SETTINGS = {
    "business": {
        "company_name": "DriveFlow Inc.",
        "support_email": "support@driveflow.com",
        "support_phone": "+1 (800) 555-0199",
        "business_hours": "Mon-Sun, 7am-11pm ET",
        "hq_address": "350 5th Ave, New York, NY",
        "about": "DriveFlow is a premium car rental platform.",
    },
    "booking_policy": {
        "auto_approve_verified_customers": False,
        "require_deposit": True,
        "allow_same_day_bookings": True,
        "enforce_minimum_rental_period": False,
    },
    "cancellation": {
        "free_cancellation_hours": 24,
        "late_cancellation_fee_percent": 25,
        "no_show_fee": "100% of first day",
        "refund_processing_time": "5 business days",
    },
    "pricing": {
        "service_fee_percent": 8,
        "tax_rate_percent": 9,
        "weekly_discount_percent": 10,
        "monthly_discount_percent": 20,
    },
    "notifications": {
        "email_new_bookings": True,
        "sms_urgent_alerts": True,
        "daily_summary_report": False,
    },
}


@router.get("", response_model=AdminSettingsPublic)
async def get_admin_settings(current_user: Annotated[dict, Depends(get_current_user)]) -> AdminSettingsPublic:
    require_admin(current_user)
    settings = await get_or_create_settings()
    return serialize_settings(settings)


@router.patch("", response_model=AdminSettingsPublic)
async def update_admin_settings(
    payload: AdminSettingsUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> AdminSettingsPublic:
    require_admin(current_user)
    updates = payload.model_dump(exclude_none=True)
    if not updates:
        return serialize_settings(await get_or_create_settings())

    set_updates = {key: value for key, value in updates.items()}
    set_updates["updated_at"] = datetime.now(timezone.utc)
    await get_settings_collection().update_one(
        {"key": SETTINGS_KEY},
        {"$set": set_updates, "$setOnInsert": {"key": SETTINGS_KEY, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
    settings = await get_or_create_settings()
    return serialize_settings(settings)


async def get_or_create_settings() -> dict:
    collection = get_settings_collection()
    settings = await collection.find_one({"key": SETTINGS_KEY})
    if settings:
        return settings

    now = datetime.now(timezone.utc)
    document = {
        "key": SETTINGS_KEY,
        **DEFAULT_SETTINGS,
        "created_at": now,
        "updated_at": now,
    }
    await collection.insert_one(document)
    return document


def serialize_settings(settings: dict) -> AdminSettingsPublic:
    merged = {**DEFAULT_SETTINGS, **settings}
    return AdminSettingsPublic(
        business=merged["business"],
        booking_policy=merged["booking_policy"],
        cancellation=merged["cancellation"],
        pricing=merged["pricing"],
        notifications=merged["notifications"],
        updated_at=merged["updated_at"],
    )


def require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")
