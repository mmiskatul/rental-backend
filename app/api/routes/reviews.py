from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pymongo.errors import DuplicateKeyError

from app.api.routes.auth import get_current_user
from app.api.routes.notifications import create_notification
from app.db.mongodb import get_bookings_collection, get_reviews_collection
from app.schemas.reviews import ReviewCreate, ReviewPublic

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.post("", response_model=ReviewPublic, status_code=status.HTTP_201_CREATED)
async def create_review(
    payload: ReviewCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> ReviewPublic:
    if current_user.get("role") == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot submit customer reviews.")

    booking = await get_bookings_collection().find_one(
        {
            "_id": parse_object_id(payload.booking_id, "Booking not found."),
            "customer_id": str(current_user["_id"]),
        }
    )
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    if booking["status"] != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only completed bookings can be reviewed.")

    now = datetime.now(timezone.utc)
    review = {
        "booking_id": str(booking["_id"]),
        "car_id": booking["car_id"],
        "car_title": booking["car_title"],
        "customer_id": str(current_user["_id"]),
        "customer_name": current_user["name"],
        "customer_email": current_user["email"],
        "rating": payload.rating,
        "comment": payload.comment,
        "created_at": now,
        "updated_at": now,
    }

    try:
        result = await get_reviews_collection().insert_one(review)
    except DuplicateKeyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This booking has already been reviewed.") from exc

    review["_id"] = result.inserted_id
    await create_notification(
        role="admin",
        notification_type="review",
        title=f"New review from {current_user['name']}",
        description=f"{payload.rating}/5 rating for {booking['car_title']}.",
    )
    return serialize_review(review)


@router.get("", response_model=list[ReviewPublic])
async def list_reviews(
    current_user: Annotated[dict, Depends(get_current_user)],
    booking_id: str | None = Query(default=None),
    car_id: str | None = Query(default=None),
) -> list[ReviewPublic]:
    query: dict[str, str] = {}
    if current_user.get("role") != "admin":
        query["customer_id"] = str(current_user["_id"])
    if booking_id:
        query["booking_id"] = booking_id
    if car_id:
        query["car_id"] = car_id

    cursor = get_reviews_collection().find(query).sort("created_at", -1)
    return [serialize_review(review) async for review in cursor]


def parse_object_id(value: str, not_found_message: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_message)
    return ObjectId(value)


def serialize_review(review: dict) -> ReviewPublic:
    return ReviewPublic(
        id=str(review["_id"]),
        booking_id=review["booking_id"],
        car_id=review["car_id"],
        car_title=review["car_title"],
        customer_id=review["customer_id"],
        customer_name=review["customer_name"],
        customer_email=review["customer_email"],
        rating=review["rating"],
        comment=review["comment"],
        created_at=review["created_at"],
        updated_at=review["updated_at"],
    )
