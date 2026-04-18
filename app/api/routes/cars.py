from datetime import datetime, timezone
from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.api.routes.auth import get_current_user
from app.db.mongodb import get_cars_collection
from app.schemas.cars import CarPublic, MessageResponse
from app.services.cloudinary_upload import upload_car_image

router = APIRouter(prefix="/api/cars", tags=["cars"])

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("", response_model=CarPublic, status_code=status.HTTP_201_CREATED)
async def create_car(
    current_user: Annotated[dict, Depends(get_current_user)],
    title: Annotated[str, Form(min_length=2, max_length=120)],
    brand: Annotated[str, Form(min_length=1, max_length=80)],
    model: Annotated[str, Form(min_length=1, max_length=80)],
    year: Annotated[int, Form(ge=1990, le=2100)],
    price_per_day: Annotated[float, Form(gt=0)],
    location: Annotated[str, Form(min_length=2, max_length=120)],
    image: Annotated[UploadFile, File()],
    description: Annotated[str | None, Form(max_length=1000)] = None,
    seats: Annotated[int | None, Form(ge=1, le=20)] = None,
    transmission: Annotated[str | None, Form(max_length=40)] = None,
    fuel_type: Annotated[str | None, Form(max_length=40)] = None,
) -> CarPublic:
    require_admin(current_user)
    if image.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image must be a JPEG, PNG, or WEBP file.",
        )

    upload_result = await upload_car_image(image)
    now = datetime.now(timezone.utc)
    car = {
        "owner_id": str(current_user["_id"]),
        "title": title,
        "brand": brand,
        "model": model,
        "year": year,
        "price_per_day": price_per_day,
        "location": location,
        "description": description,
        "seats": seats,
        "transmission": transmission,
        "fuel_type": fuel_type,
        "image_url": upload_result["secure_url"],
        "image_public_id": upload_result["public_id"],
        "created_at": now,
        "updated_at": now,
    }

    result = await get_cars_collection().insert_one(car)
    car["_id"] = result.inserted_id
    return serialize_car(car)


@router.patch("/{car_id}", response_model=CarPublic)
async def update_car(
    car_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
    title: Annotated[str | None, Form(min_length=2, max_length=120)] = None,
    brand: Annotated[str | None, Form(min_length=1, max_length=80)] = None,
    model: Annotated[str | None, Form(min_length=1, max_length=80)] = None,
    year: Annotated[int | None, Form(ge=1990, le=2100)] = None,
    price_per_day: Annotated[float | None, Form(gt=0)] = None,
    location: Annotated[str | None, Form(min_length=2, max_length=120)] = None,
    image: UploadFile | None = File(default=None),
    description: Annotated[str | None, Form(max_length=1000)] = None,
    seats: Annotated[int | None, Form(ge=1, le=20)] = None,
    transmission: Annotated[str | None, Form(max_length=40)] = None,
    fuel_type: Annotated[str | None, Form(max_length=40)] = None,
) -> CarPublic:
    require_admin(current_user)
    object_id = parse_car_id(car_id)
    updates = {
        "title": title,
        "brand": brand,
        "model": model,
        "year": year,
        "price_per_day": price_per_day,
        "location": location,
        "description": description,
        "seats": seats,
        "transmission": transmission,
        "fuel_type": fuel_type,
    }
    updates = {key: value for key, value in updates.items() if value is not None}

    if image:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Image must be a JPEG, PNG, or WEBP file.",
            )
        upload_result = await upload_car_image(image)
        updates["image_url"] = upload_result["secure_url"]
        updates["image_public_id"] = upload_result["public_id"]

    if updates:
        updates["updated_at"] = datetime.now(timezone.utc)
        result = await get_cars_collection().update_one({"_id": object_id}, {"$set": updates})
        if result.matched_count == 0:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")

    car = await get_cars_collection().find_one({"_id": object_id})
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return serialize_car(car)


@router.delete("/{car_id}", response_model=MessageResponse)
async def delete_car(
    car_id: str,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> MessageResponse:
    require_admin(current_user)
    result = await get_cars_collection().delete_one({"_id": parse_car_id(car_id)})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return MessageResponse(message="Car deleted successfully.")


@router.get("", response_model=list[CarPublic])
async def list_cars() -> list[CarPublic]:
    cars = get_cars_collection().find().sort("created_at", -1)
    return [serialize_car(car) async for car in cars]


@router.get("/{car_id}", response_model=CarPublic)
async def get_car(car_id: str) -> CarPublic:
    car = await get_cars_collection().find_one({"_id": parse_car_id(car_id)})
    if not car:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")

    return serialize_car(car)


def parse_car_id(car_id: str) -> ObjectId:
    if not ObjectId.is_valid(car_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Car not found.")
    return ObjectId(car_id)


def require_admin(user: dict) -> None:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access is required.")


def serialize_car(car: dict) -> CarPublic:
    return CarPublic(
        id=str(car["_id"]),
        owner_id=car["owner_id"],
        title=car["title"],
        brand=car["brand"],
        model=car["model"],
        year=car["year"],
        price_per_day=car["price_per_day"],
        location=car["location"],
        description=car.get("description"),
        seats=car.get("seats"),
        transmission=car.get("transmission"),
        fuel_type=car.get("fuel_type"),
        image_url=car["image_url"],
        image_public_id=car["image_public_id"],
        created_at=car["created_at"],
        updated_at=car["updated_at"],
    )
