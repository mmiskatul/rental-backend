from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_bookings_collection, get_users_collection
from app.schemas.customers import CustomerPublic

router = APIRouter(prefix="/api/customers", tags=["customers"])


@router.get("", response_model=list[CustomerPublic])
async def list_customers(current_user: Annotated[dict, Depends(get_current_user)]) -> list[CustomerPublic]:
    require_admin(current_user)
    users = get_users_collection().find({"role": "customer"}).sort("created_at", -1)
    return [await serialize_customer(user) async for user in users]


async def serialize_customer(user: dict) -> CustomerPublic:
    customer_id = str(user["_id"])
    bookings = await get_bookings_collection().find({"customer_id": customer_id}).to_list(length=None)
    active_statuses = {"approved", "active"}
    return CustomerPublic(
        id=customer_id,
        name=user["name"],
        email=user["email"],
        phone=user.get("phone"),
        joined_at=user["created_at"],
        total_bookings=len(bookings),
        active_bookings=sum(1 for booking in bookings if booking.get("status") in active_statuses),
        total_spend=sum(float(booking.get("total", 0)) for booking in bookings if booking.get("status") in {"approved", "active", "completed"}),
        status="active" if user.get("is_active", True) else "inactive",
    )


def require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")
