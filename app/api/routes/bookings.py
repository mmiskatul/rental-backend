from datetime import date, datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_bookings_collection, get_cars_collection
from app.schemas.bookings import BookingCreate, BookingPublic, BookingStatusUpdate
from app.schemas.cars import MessageResponse

router = APIRouter(prefix="/api/bookings", tags=["bookings"])


@router.post("", response_model=BookingPublic, status_code=status.HTTP_201_CREATED)
async def create_booking(
    payload: BookingCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> BookingPublic:
    if current_user.get("role") == "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot create customer bookings.")

    car_id = parse_object_id(payload.car_id, "Car not found.")
    car = await get_cars_collection().find_one({"_id": car_id})
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")

    days = calculate_days(payload.start_date, payload.end_date)
    now = datetime.now(timezone.utc)
    subtotal = float(car["price_per_day"]) * days
    total = round(subtotal + (subtotal * 0.08), 2)
    booking = {
        "car_id": str(car["_id"]),
        "car_title": car["title"],
        "car_image_url": car.get("image_url"),
        "customer_id": str(current_user["_id"]),
        "customer_name": current_user["name"],
        "customer_email": current_user["email"],
        "customer_phone": current_user.get("phone"),
        "start_date": payload.start_date.isoformat(),
        "end_date": payload.end_date.isoformat(),
        "days": days,
        "pickup_location": payload.pickup_location,
        "total": total,
        "status": "pending",
        "payment_status": "pending",
        "notes": payload.notes,
        "created_at": now,
        "updated_at": now,
    }

    result = await get_bookings_collection().insert_one(booking)
    booking["_id"] = result.inserted_id
    return serialize_booking(booking)


@router.get("", response_model=list[BookingPublic])
async def list_bookings(current_user: Annotated[dict, Depends(get_current_user)]) -> list[BookingPublic]:
    query = {} if current_user.get("role") == "admin" else {"customer_id": str(current_user["_id"])}
    cursor = get_bookings_collection().find(query).sort("created_at", -1)
    return [serialize_booking(booking) async for booking in cursor]


@router.get("/{booking_id}", response_model=BookingPublic)
async def get_booking(
    booking_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> BookingPublic:
    booking = await find_booking_for_user(booking_id, current_user)
    return serialize_booking(booking)


@router.patch("/{booking_id}/status", response_model=BookingPublic)
async def update_booking_status(
    booking_id: str,
    payload: BookingStatusUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> BookingPublic:
    require_admin(current_user)
    object_id = parse_object_id(booking_id, "Booking not found.")
    updates = {
        "status": payload.status,
        "updated_at": datetime.now(timezone.utc),
    }
    if payload.notes is not None:
        updates["notes"] = payload.notes
    if payload.status == "approved":
        updates["payment_status"] = "paid"
    if payload.status in {"rejected", "cancelled"}:
        updates["payment_status"] = "refunded"

    result = await get_bookings_collection().update_one({"_id": object_id}, {"$set": updates})
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")

    booking = await get_bookings_collection().find_one({"_id": object_id})
    return serialize_booking(booking)


@router.delete("/{booking_id}", response_model=MessageResponse)
async def cancel_booking(
    booking_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MessageResponse:
    booking = await find_booking_for_user(booking_id, current_user)
    if booking["status"] not in {"pending", "approved"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This booking cannot be cancelled.")

    await get_bookings_collection().update_one(
        {"_id": booking["_id"]},
        {
            "$set": {
                "status": "cancelled",
                "payment_status": "refunded",
                "updated_at": datetime.now(timezone.utc),
            }
        },
    )
    return MessageResponse(message="Booking cancelled successfully.")


async def find_booking_for_user(booking_id: str, user: dict) -> dict:
    object_id = parse_object_id(booking_id, "Booking not found.")
    query = {"_id": object_id}
    if user.get("role") != "admin":
        query["customer_id"] = str(user["_id"])

    booking = await get_bookings_collection().find_one(query)
    if not booking:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found.")
    return booking


def calculate_days(start_date: date, end_date: date) -> int:
    if end_date <= start_date:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Drop-off date must be after pick-up date.")
    return (end_date - start_date).days


def parse_object_id(value: str, not_found_message: str) -> ObjectId:
    if not ObjectId.is_valid(value):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=not_found_message)
    return ObjectId(value)


def require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")


def serialize_booking(booking: dict) -> BookingPublic:
    return BookingPublic(
        id=str(booking["_id"]),
        car_id=booking["car_id"],
        car_title=booking["car_title"],
        car_image_url=booking.get("car_image_url"),
        customer_id=booking["customer_id"],
        customer_name=booking["customer_name"],
        customer_email=booking["customer_email"],
        customer_phone=booking.get("customer_phone"),
        start_date=date.fromisoformat(booking["start_date"]) if isinstance(booking["start_date"], str) else booking["start_date"],
        end_date=date.fromisoformat(booking["end_date"]) if isinstance(booking["end_date"], str) else booking["end_date"],
        days=booking["days"],
        pickup_location=booking["pickup_location"],
        total=booking["total"],
        status=booking["status"],
        payment_status=booking["payment_status"],
        notes=booking.get("notes"),
        created_at=booking["created_at"],
        updated_at=booking["updated_at"],
    )
