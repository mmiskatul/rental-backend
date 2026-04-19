from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_bookings_collection, get_customer_settings_collection, get_reviews_collection, get_users_collection
from app.schemas.customer_settings import CustomerSettingsPublic, CustomerSettingsUpdate, CustomerStats

router = APIRouter(prefix="/api/customer/settings", tags=["customer-settings"])

DEFAULT_PREFERENCES = {
    "booking_confirmations": True,
    "promotional_emails": False,
    "sms_reminders": True,
}


@router.get("", response_model=CustomerSettingsPublic)
async def get_customer_settings(current_user: Annotated[dict, Depends(get_current_user)]) -> CustomerSettingsPublic:
    require_customer(current_user)
    settings = await get_or_create_customer_settings(current_user)
    return await serialize_settings(settings, current_user)


@router.patch("", response_model=CustomerSettingsPublic)
async def update_customer_settings(
    payload: CustomerSettingsUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> CustomerSettingsPublic:
    require_customer(current_user)
    updates = payload.model_dump(exclude_none=True)
    now = datetime.now(timezone.utc)

    if "profile" in updates:
        profile = updates["profile"]
        await get_users_collection().update_one(
            {"_id": current_user["_id"]},
            {
                "$set": {
                    "name": profile["name"],
                    "email": profile["email"].lower(),
                    "phone": profile.get("phone"),
                    "updated_at": now,
                }
            },
        )

    settings_updates = {}
    if "profile" in updates:
        settings_updates["profile"] = updates["profile"]
    if "preferences" in updates:
        settings_updates["preferences"] = updates["preferences"]
    if settings_updates:
        settings_updates["updated_at"] = now
        await get_customer_settings_collection().update_one(
            {"user_id": str(current_user["_id"])},
            {
                "$set": settings_updates,
                "$setOnInsert": {"user_id": str(current_user["_id"]), "created_at": now},
            },
            upsert=True,
        )

    refreshed_user = await get_users_collection().find_one({"_id": current_user["_id"]})
    settings = await get_or_create_customer_settings(refreshed_user)
    return await serialize_settings(settings, refreshed_user)


async def get_or_create_customer_settings(user: dict) -> dict:
    collection = get_customer_settings_collection()
    user_id = str(user["_id"])
    settings = await collection.find_one({"user_id": user_id})
    if settings:
        return settings

    now = datetime.now(timezone.utc)
    document = {
        "user_id": user_id,
        "profile": {
            "name": user["name"],
            "email": user["email"],
            "phone": user.get("phone"),
            "address": "",
        },
        "preferences": DEFAULT_PREFERENCES,
        "created_at": now,
        "updated_at": now,
    }
    await collection.insert_one(document)
    return document


async def serialize_settings(settings: dict, user: dict) -> CustomerSettingsPublic:
    profile = {
        **settings.get("profile", {}),
        "name": user["name"],
        "email": user["email"],
        "phone": user.get("phone"),
    }
    preferences = {**DEFAULT_PREFERENCES, **settings.get("preferences", {})}
    return CustomerSettingsPublic(
        profile=profile,
        preferences=preferences,
        stats=await get_customer_stats(str(user["_id"])),
        updated_at=settings["updated_at"],
    )


async def get_customer_stats(user_id: str) -> CustomerStats:
    bookings = await get_bookings_collection().find({"customer_id": user_id}).to_list(length=None)
    reviews = await get_reviews_collection().find({"customer_id": user_id}).to_list(length=None)
    paid_statuses = {"approved", "pickup_requested", "active", "return_requested", "completed"}
    total_spend = sum(float(booking.get("total", 0)) for booking in bookings if booking.get("status") in paid_statuses)
    average_rating = round(sum(int(review.get("rating", 0)) for review in reviews) / len(reviews), 1) if reviews else 0
    return CustomerStats(total_bookings=len(bookings), total_spend=round(total_spend, 2), average_rating=average_rating)


def require_customer(user: dict) -> None:
    if user.get("role") == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Customer access is required.")
